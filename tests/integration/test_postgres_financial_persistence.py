"""ADR-047 financial persistence against a DISPOSABLE PostgreSQL cluster. Synthetic data only.

Runs only when JUVAL_POSTGRES_BIN names a PostgreSQL server bin directory
(e.g. /usr/lib/postgresql/16/bin). The module then creates its own cluster
with initdb in a private temporary directory, listening only on a Unix socket
inside it (no TCP), and destroys it afterwards. No DSN is read from the
environment, so a runtime or production database can never be reached, and
JUVAL_*/PG* variables are stripped from the server's environment.

Each test owns a fresh schema and applies the real files of
supabase/migrations/ to it, so the schema under test is the one that would
be deployed, not a copy.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import sql  # noqa: E402
from psycopg.conninfo import make_conninfo  # noqa: E402

from juval.application.capture_diagnostics import RecordCaptureDiagnostics  # noqa: E402
from juval.application.financial_persistence import (  # noqa: E402
    FinancialRecordIntegrityError, load_capture_diagnostics, load_financial_record,
    save_run_with_financial_records,
)
from juval.application.financial_serialization import (  # noqa: E402
    FinancialSerializationError, serialize_financial_record,
)
from juval.application.financial_serialization_v2 import FinancialRecordDocumentV2  # noqa: E402
from juval.application.record_snapshot import record_to_snapshot  # noqa: E402
from juval.domain.financial_evidence import FinancialTerm as T  # noqa: E402
from juval.domain.provenance import VerificationStatus  # noqa: E402
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore  # noqa: E402
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore  # noqa: E402

from .test_cli_native_financial import FINANCIAL, cli_run, fixed_now, refs  # noqa: E402,F401 (fixture)
from .test_cli_native_financial import row as cli_row  # noqa: E402
from .test_financial_persistence import build, row  # noqa: E402
from .test_native_financial_capture import BASE, declared, xlsx  # noqa: E402
from .test_pipeline_financial_evidence import legacy  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
NEW = "20260925000005_execution_run_financial_records"
DOC, DIAG = "execution_run_financial_records", "execution_run_capture_diagnostics"
# The run-audit migrations this one builds on; identity sessions are unrelated.
PRIOR = ("20260817000000_execution_runs", "20260817000001_execution_run_records",
         "20260819000002_batches", "20260819000003_batch_file_counts")

BIN = os.environ.get("JUVAL_POSTGRES_BIN")
pytestmark = pytest.mark.skipif(not BIN, reason="JUVAL_POSTGRES_BIN not set -- no disposable PostgreSQL cluster")


@pytest.fixture(scope="module")
def cluster():
    if os.geteuid() == 0:
        pytest.skip("disposable cluster must run as an unprivileged user")
    initdb, pg_ctl = Path(BIN) / "initdb", Path(BIN) / "pg_ctl"
    scratch = Path(tempfile.mkdtemp(prefix="juval-financial-pg-"))
    data, log = scratch / "data", scratch / "postgres.log"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("JUVAL_", "PG"))}
    started = False
    try:
        subprocess.run([initdb, "-D", data, "-A", "trust", "--no-locale", "--encoding=UTF8"],
                       env=env, check=True, capture_output=True)
        with (data / "postgresql.conf").open("a") as config:
            config.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{scratch}'\n")
        subprocess.run([pg_ctl, "-D", data, "-l", log, "-w", "start"], env=env, check=True, capture_output=True)
        started = True
        yield f"host={scratch} dbname=postgres"
    finally:
        if started:
            subprocess.run([pg_ctl, "-D", data, "-m", "immediate", "-w", "stop"], env=env, capture_output=True)
        shutil.rmtree(scratch, ignore_errors=True)


def apply(dsn, name):
    with psycopg.connect(dsn) as conn:
        conn.execute((MIGRATIONS / f"{name}.sql").read_text(encoding="utf-8"))


@pytest.fixture
def prior_dsn(cluster):
    """A schema holding only the pre-ADR-047 run tables, as deployed today."""
    schema = "juval_fin_" + secrets.token_hex(8)
    with psycopg.connect(cluster) as conn:
        conn.execute(sql.SQL("create schema {}").format(sql.Identifier(schema)))
    dsn = make_conninfo(cluster, options=f"-c search_path={schema}")
    for name in PRIOR:
        apply(dsn, name)
    yield dsn
    with psycopg.connect(cluster) as conn:
        conn.execute(sql.SQL("drop schema {} cascade").format(sql.Identifier(schema)))


@pytest.fixture
def dsn(prior_dsn):
    apply(prior_dsn, NEW)
    return prior_dsn


@pytest.fixture
def store(dsn):
    return SupabaseExecutionRunStore(dsn)


def count(dsn, table):
    with psycopg.connect(dsn) as conn:
        return conn.execute(sql.SQL("select count(*) from {}").format(sql.Identifier(table))).fetchone()[0]


def execute(dsn, statement, *params):
    with psycopg.connect(dsn) as conn:
        conn.execute(statement, params)


# -- Schema ------------------------------------------------------------------------

def test_migration_creates_both_tables_with_the_sqlite_contract(dsn):
    with psycopg.connect(dsn) as conn:
        for table in (DOC, DIAG):
            columns = conn.execute(
                "select column_name, data_type, is_nullable from information_schema.columns "
                "where table_schema = current_schema() and table_name = %s order by ordinal_position",
                (table,)).fetchall()
            assert columns == [("execution_id", "text", "NO"), ("record_ref", "text", "NO"),
                               ("format", "text", "NO"), ("format_version", "integer", "NO"),
                               ("payload", "text", "NO")]                           # TEXT, not JSONB
            constraints = dict(conn.execute(
                "select contype, pg_get_constraintdef(oid) from pg_constraint "
                "where conrelid = %s::regclass and contype in ('p', 'f')", (table,)).fetchall())
            assert constraints["p"] == "PRIMARY KEY (execution_id, record_ref)"
            assert constraints["f"] == ("FOREIGN KEY (execution_id, record_ref) "
                                        "REFERENCES execution_run_records(execution_id, record_ref)")


def test_migration_is_additive_and_legacy_runs_stay_readable(tmp_path, prior_dsn):
    legacy_run, legacy_records = legacy(xlsx(tmp_path, row("A"), name="legacy/in.xlsx"), "run-L")
    snapshots = [record_to_snapshot(record) for record in legacy_records]
    SupabaseExecutionRunStore(prior_dsn).save_execution_run(legacy_run, snapshots)   # before the migration
    apply(prior_dsn, NEW)
    apply(prior_dsn, NEW)                                                           # re-applying is a no-op
    store = SupabaseExecutionRunStore(prior_dsn)
    assert store.load_execution_run("run-L") == legacy_run
    assert store.load_records("run-L") == snapshots
    ref = legacy_records[0].record_ref
    assert load_financial_record(store, "run-L", ref) is None                       # absent, not backfilled
    assert load_capture_diagnostics(store, "run-L", ref) is None
    assert count(prior_dsn, DOC) == count(prior_dsn, DIAG) == 0


def test_rollback_drops_only_the_new_tables_and_can_be_reapplied(tmp_path, dsn, store):
    result, snapshots, docs = build(tmp_path, [row("A")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    apply(dsn, f"{NEW}.down")
    with psycopg.connect(dsn) as conn:
        assert conn.execute("select to_regclass(%s), to_regclass(%s)", (DOC, DIAG)).fetchone() == (None, None)
    assert store.load_execution_run("run-A") == result.run                          # run and snapshots survive
    assert store.load_records("run-A") == snapshots
    with pytest.raises(psycopg.errors.UndefinedTable):                              # loud, never "no document"
        store.load_financial_record("run-A", snapshots[0]["record_ref"])
    apply(dsn, NEW)
    assert load_financial_record(store, "run-A", snapshots[0]["record_ref"]) is None


# -- Round-trip and parity with SQLite ------------------------------------------------

def test_v1_document_round_trips_as_the_same_canonical_text_as_sqlite(tmp_path, store):
    result, snapshots, [document] = build(tmp_path, [row("A", **{T.COG: "4.50"})])
    save_run_with_financial_records(store, result.run, snapshots, [document])
    ref = document.evidence.record_reference
    loaded = load_financial_record(store, "run-A", ref)
    assert loaded == document
    assert str(loaded.evidence.evidence_for(T.COG).amount.value) == "4.50"          # scale kept
    assert loaded.evidence.evidence_for(T.VAT).amount is None                       # exclusion, not zero
    sqlite_store = SqliteExecutionRunStore(tmp_path / "parity.db")
    save_run_with_financial_records(sqlite_store, result.run, snapshots, [document])
    text = json.dumps(serialize_financial_record(document), sort_keys=True)
    assert store.load_financial_record("run-A", ref) == sqlite_store.load_financial_record("run-A", ref) \
        == ("juval.adr047.financial-record", 1, text)                               # byte-identical


def test_cli_v2_documents_and_diagnostics_round_trip_byte_identically(tmp_path, store):
    """Real CLI output (v2 documents, empty and non-empty diagnostics sets, a record
    without a scenario) copied from SQLite into PostgreSQL through the shared
    application functions."""
    rows = [cli_row("FULL"),
            cli_row("PARTIAL", **declared(T.COG, "4.50", source_basis="carton")),
            {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")},
            cli_row("INFERRED", **declared(T.COG, "4.50", applies_method="supplier estimate"))]
    code, _, source = cli_run(tmp_path, rows, *FINANCIAL)
    assert code == 0
    record_refs = refs(source)
    documents = [d for d in (load_financial_record(source, "run-A", r) for r in record_refs) if d is not None]
    diagnostics = [load_capture_diagnostics(source, "run-A", r) for r in record_refs]
    assert len(documents) == 3 and all(type(d) is FinancialRecordDocumentV2 for d in documents)
    save_run_with_financial_records(store, source.load_execution_run("run-A"), source.load_records("run-A"),
                                    documents, diagnostics)
    for ref in record_refs:
        assert store.load_financial_record("run-A", ref) == source.load_financial_record("run-A", ref)
        assert store.load_capture_diagnostics("run-A", ref) == source.load_capture_diagnostics("run-A", ref)
        assert load_financial_record(store, "run-A", ref) == load_financial_record(source, "run-A", ref)
        assert load_capture_diagnostics(store, "run-A", ref) == load_capture_diagnostics(source, "run-A", ref)
    full, partial, no_scenario, inferred = record_refs
    assert load_financial_record(store, "run-A", no_scenario) is None               # no document, not blocked
    assert len(load_capture_diagnostics(store, "run-A", no_scenario).diagnostics) >= 1
    assert load_capture_diagnostics(store, "run-A", full).diagnostics == ()         # stored and empty
    cog = load_financial_record(store, "run-A", inferred).document.evidence.evidence_for(T.COG)
    assert cog.applicability.applies.status is VerificationStatus.INFERRED        # never promoted


# -- Identity, isolation and duplicates ------------------------------------------------

def test_runs_are_isolated(tmp_path, store):
    a = build(tmp_path, [row("A", **{T.COG: "1.00"})], execution_id="run-A")
    b = build(tmp_path, [row("A", **{T.COG: "7.00"})], execution_id="run-B")
    for result, snapshots, docs in (a, b):
        save_run_with_financial_records(store, result.run, snapshots, docs)
    ref = a[0].records[0].record_ref
    assert ref == b[0].records[0].record_ref
    assert str(load_financial_record(store, "run-A", ref).evidence.evidence_for(T.COG).amount.value) == "1.00"
    assert str(load_financial_record(store, "run-B", ref).evidence.evidence_for(T.COG).amount.value) == "7.00"
    assert load_financial_record(store, "run-C", ref) is None


def test_saving_a_run_twice_is_refused_and_changes_nothing(tmp_path, dsn, store):
    result, snapshots, docs = build(tmp_path, [row("A")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    with pytest.raises(psycopg.errors.UniqueViolation):
        save_run_with_financial_records(store, result.run, snapshots, docs)
    assert count(dsn, DOC) == 1


# -- Atomicity -------------------------------------------------------------------------

@pytest.mark.parametrize("failure", ["foreign_key", "duplicate_document", "duplicate_diagnostics", "other_run"])
def test_any_failure_rolls_back_run_snapshots_and_financial_rows(tmp_path, dsn, store, failure):
    """The failing INSERT runs after the run and snapshot INSERTs of the same transaction."""
    result, snapshots, docs = build(tmp_path, [row("A"), row("B")])
    payloads = [serialize_financial_record(d) for d in docs]
    diagnostics = [{"format": "juval.adr047.capture-diagnostics", "version": 1, "execution_id": "run-A",
                    "record_ref": s["record_ref"], "diagnostics": []} for s in snapshots]
    if failure == "foreign_key":
        snapshots = snapshots[:1]                     # B's payload has no snapshot row
    elif failure == "duplicate_document":
        payloads = [payloads[0], payloads[0]]
    elif failure == "duplicate_diagnostics":
        diagnostics = [diagnostics[0], diagnostics[0]]
    else:
        payloads[1]["evidence"]["execution_id"] = "run-Z"
    with pytest.raises((psycopg.errors.IntegrityError, ValueError)):
        store.save_execution_run(result.run, snapshots, financial_records=payloads, capture_diagnostics=diagnostics)
    assert store.load_execution_run("run-A") is None
    assert store.load_records("run-A") == []
    assert count(dsn, DOC) == count(dsn, DIAG) == 0


def test_invalid_document_set_is_refused_before_any_write(tmp_path, dsn, store):
    result, snapshots, docs = build(tmp_path, [row("A")])
    foreign = RecordCaptureDiagnostics("run-Z", snapshots[0]["record_ref"], ())
    with pytest.raises(FinancialRecordIntegrityError):
        save_run_with_financial_records(store, result.run, snapshots, docs, [foreign])
    assert store.load_execution_run("run-A") is None and count(dsn, DOC) == 0


# -- Read integrity ---------------------------------------------------------------------

def saved(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A"), row("B")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    return [s["record_ref"] for s in snapshots]


def test_corrupt_payload_is_a_serialization_error_not_absence(tmp_path, dsn, store):
    ref = saved(tmp_path, store)[0]
    execute(dsn, f"update {DOC} set payload = 'not json {{' where record_ref = %s", ref)
    with pytest.raises(FinancialSerializationError):
        load_financial_record(store, "run-A", ref)


def test_columns_contradicting_the_payload_are_an_integrity_error(tmp_path, dsn, store):
    first, second = saved(tmp_path, store)
    execute(dsn, f"update {DOC} set format_version = 2 where record_ref = %s", first)
    with pytest.raises(FinancialRecordIntegrityError):
        load_financial_record(store, "run-A", first)
    other = store.load_financial_record("run-A", first)[2]
    execute(dsn, f"update {DOC} set payload = %s where record_ref = %s", other, second)
    with pytest.raises(FinancialRecordIntegrityError):
        load_financial_record(store, "run-A", second)


@pytest.mark.parametrize("column, value", [("format", "juval.adr047.capture-diagnostics"), ("format_version", 0)])
def test_schema_refuses_a_foreign_format_or_version(tmp_path, dsn, store, column, value):
    ref = saved(tmp_path, store)[0]
    with pytest.raises(psycopg.errors.CheckViolation):
        execute(dsn, f"update {DOC} set {column} = %s where record_ref = %s", value, ref)


# -- Access ----------------------------------------------------------------------------

def test_a_granted_non_owner_role_reads_and_writes_nothing(tmp_path, dsn, store):
    """Supabase grants table privileges to its API roles by default; RLS with no
    policy must still hide every financial row, as it hides the run's records."""
    saved(tmp_path, store)
    role = "juval_probe_" + secrets.token_hex(6)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("create role {} nologin").format(sql.Identifier(role)))
        try:
            conn.execute(sql.SQL("grant usage on schema {} to {}").format(
                sql.Identifier(conn.execute("select current_schema()").fetchone()[0]), sql.Identifier(role)))
            conn.execute(sql.SQL("grant select, insert on {}, {}, {} to {}").format(
                sql.Identifier(DOC), sql.Identifier(DIAG), sql.Identifier("execution_run_records"),
                sql.Identifier(role)))
            with conn.transaction():
                conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
                for table in (DOC, DIAG, "execution_run_records"):
                    assert conn.execute(sql.SQL("select count(*) from {}").format(
                        sql.Identifier(table))).fetchone()[0] == 0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
                    conn.execute(f"insert into {DOC} values ('run-A', 'row_x', 'juval.adr047.financial-record', 1, '{{}}')")
            policies = conn.execute("select count(*) from pg_policies where tablename in (%s, %s)",
                                    (DOC, DIAG)).fetchone()[0]
            forced = conn.execute("select bool_and(relrowsecurity), bool_or(relforcerowsecurity) from pg_class "
                                  "where oid in (%s::regclass, %s::regclass)", (DOC, DIAG)).fetchone()
            assert policies == 0 and forced == (True, False)
        finally:
            conn.execute(sql.SQL("drop owned by {}").format(sql.Identifier(role)))
            conn.execute(sql.SQL("drop role {}").format(sql.Identifier(role)))


def test_stored_documents_leave_the_commercial_snapshot_untouched(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    assert store.load_records("run-A") == snapshots
    assert "financial" not in json.dumps(store.load_records("run-A"))
