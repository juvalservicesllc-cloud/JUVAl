"""ADR-058 migration and store against a private disposable PostgreSQL only.

Builds on the ADR-056 tenant database (baseline + ADR-048 + ADR-056 migrations,
with one historical run), applies 20261111000010 as postgres and then works as
the runtime role `juval_backend`. Never a runtime or Supabase DSN.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

import juval
from juval.application.acquisition_run import run_and_persist_with_acquisition
from juval.application.batch_store import RunWrite
from juval.application.tenancy import OutOfScopeError, Ownership, TenantScope
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.infrastructure.persistence.supabase_execution_run_store import (
    AcquisitionStorageUnavailable,
    SupabaseExecutionRunStore,
)

from tests.unit.acquisition_synthetic import ScriptedTransport, connector, found, no_match, ok

from .test_acquisition_run import FEES, FIXTURE, NOW, THRESHOLDS, eligible_asins
from .test_postgres_financial_persistence import cluster  # noqa: F401 (fixture)
from .test_postgres_runtime_role_security import MIGRATIONS, _apply
from .test_postgres_tenant_isolation import (  # noqa: F401 (fixtures)
    ISSUER,
    LEGACY_RUN,
    ORG_A,
    ORG_B,
    run,
    runtime,
    snapshot,
    tenant_database,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("JUVAL_POSTGRES_BIN"),
    reason="JUVAL_POSTGRES_BIN required: disposable PostgreSQL only",
)

MIGRATION = "20261111000010_execution_run_acquisition"
OWNER_A = Ownership(ORG_A, ISSUER, "user-a1")


@pytest.fixture
def acq_database(tenant_database):  # noqa: F811
    with psycopg.connect(tenant_database) as conn:
        _apply(conn, MIGRATION)
    return tenant_database


def acquire(store, execution_id="pg-acq-1"):
    asins = eligible_asins()
    transport = ScriptedTransport(ok(*[found(a) for a in asins[:-1]], no_match(asins[-1])))
    return run_and_persist_with_acquisition(
        FIXTURE, THRESHOLDS, connectors=[connector(transport)], store=store, fees=FEES,
        application_version=juval.__version__, execution_id=execution_id, now=NOW, owner=OWNER_A)


def test_history_stays_not_recorded_after_the_migration(acq_database):
    admin = SupabaseExecutionRunStore(acq_database)
    assert admin.load_acquisition(LEGACY_RUN) is None
    assert admin.load_execution_run(LEGACY_RUN).execution_id == LEGACY_RUN


def test_runtime_role_writes_and_reads_the_documents_in_one_insert(acq_database, runtime):  # noqa: F811
    store = SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A))
    result = acquire(store)
    assert store.load_acquisition("pg-acq-1") == result.acquisition
    assert store.load_records("pg-acq-1") == [dict(s) for s in result.snapshots]
    with psycopg.connect(acq_database) as conn:
        config_text, execution_text = conn.execute(
            "SELECT acquisition_configuration, acquisition_execution FROM execution_runs WHERE execution_id = %s",
            ("pg-acq-1",)).fetchone()
    assert '"format":"juval.adr058.acquisition-configuration"' in config_text
    assert '"format":"juval.adr058.acquisition-execution"' in execution_text


def test_tenant_isolation_covers_the_documents(acq_database, runtime):  # noqa: F811
    acquire(SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A)))
    with pytest.raises(OutOfScopeError):
        SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_B)).load_acquisition("pg-acq-1")
    with psycopg.connect(runtime) as conn:  # RLS alone, without the application's WHERE
        conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_B,))
        assert conn.execute("SELECT count(*) FROM execution_runs WHERE acquisition_configuration IS NOT NULL"
                            ).fetchone() == (0,)


def test_runtime_role_cannot_change_the_documents(acq_database, runtime):  # noqa: F811
    acquire(SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A)))
    with psycopg.connect(runtime) as conn:
        conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_A,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE execution_runs SET acquisition_execution = NULL, acquisition_configuration = NULL")


def test_check_constraint_refuses_one_null_column(acq_database):
    with psycopg.connect(acq_database) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO execution_runs (execution_id, started_at, finished_at, status, input_filename, "
                "input_hash, application_version, records_total, records_processed, records_successful, "
                "records_with_errors, warnings, organization_id, created_by_issuer, created_by_subject, "
                "acquisition_configuration) VALUES ('x', now(), now(), 'SUCCESS', 'f', 'h', 'v', 0, 0, 0, 0, 0, "
                "%s, 'i', 's', '{}')", (ORG_A,))


def test_failed_insert_leaves_nothing(acq_database, runtime):  # noqa: F811
    store = SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A))
    acquire(store)
    with pytest.raises(psycopg.errors.UniqueViolation):   # same execution_id: the whole write rolls back
        acquire(store)
    assert store.load_acquisition("pg-acq-1") is not None
    with psycopg.connect(acq_database) as conn:
        assert conn.execute("SELECT count(*) FROM execution_runs WHERE execution_id = 'pg-acq-1'").fetchone() == (1,)


def test_batch_children_carry_documents_atomically(acq_database, runtime):  # noqa: F811
    store = SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A))
    child = acquire(store, "pg-child-source")
    batch = Batch(batch_id="pg-batch", created_at=NOW, status=BatchStatus.SUCCESS,
                  files=(BatchFile(0, "a.xlsx", None, 1, BatchFileStatus.SUCCESS, "pg-child"),))
    child_run = child.run.__class__(**{**child.run.__dict__, "execution_id": "pg-child"})
    store.save_batch_with_runs(batch, [RunWrite(child_run, child.snapshots, acquisition=child.acquisition)], OWNER_A)
    assert store.load_acquisition("pg-child") == child.acquisition


def test_before_the_migration_plain_runs_still_save_and_reading_is_an_error(tenant_database, runtime):  # noqa: F811
    store = SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A))
    store.save_execution_run(run("pre-adr058"), [snapshot()], owner=OWNER_A)   # unchanged behaviour
    with pytest.raises(AcquisitionStorageUnavailable):                        # never NOT_RECORDED
        store.load_acquisition("pre-adr058")
    with pytest.raises(psycopg.errors.UndefinedColumn):
        acquire(store)
    with psycopg.connect(tenant_database) as conn:
        assert conn.execute("SELECT count(*) FROM execution_runs WHERE execution_id = 'pg-acq-1'").fetchone() == (0,)


def test_down_migration_restores_the_previous_shape(acq_database, runtime):  # noqa: F811
    acquire(SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A)))
    with psycopg.connect(acq_database) as conn:
        conn.execute((MIGRATIONS / f"{MIGRATION}.down.sql").read_text(encoding="utf-8"))
    with psycopg.connect(acq_database) as conn:
        columns = {r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'execution_runs'")}
    assert not {"acquisition_configuration", "acquisition_execution"} & columns
    assert SupabaseExecutionRunStore(acq_database).load_execution_run("pg-acq-1") is not None


def test_migration_adds_no_table_grant_or_policy(tenant_database):  # noqa: F811
    def inventory(conn):
        return (conn.execute("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'").fetchone(),
                conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone(),
                sorted(conn.execute("SELECT grantee, table_name, privilege_type FROM information_schema.table_privileges "
                                    "WHERE table_schema = 'public'").fetchall()))
    with psycopg.connect(tenant_database) as conn:
        before = inventory(conn)
        _apply(conn, MIGRATION)
        assert inventory(conn) == before


def test_migration_file_is_the_one_shipped():
    path = Path(MIGRATIONS) / f"{MIGRATION}.sql"
    text = path.read_text(encoding="utf-8")
    assert "current_user <> 'postgres'" in text and "execution_runs_acquisition_pair" in text
    assert (Path(MIGRATIONS) / f"{MIGRATION}.down.sql").exists()
