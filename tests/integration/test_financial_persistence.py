"""Native financial records persisted in a temporary SQLite database. Synthetic data only."""
import ast
import json
import pathlib
import sqlite3
from decimal import Decimal

import pytest

from juval.application import financial_persistence as module
from juval.application.financial_calculation import CalculationBlocker, calculate_financial_results
from juval.application.financial_persistence import (
    FinancialRecordIntegrityError, load_financial_record, save_run_with_financial_records,
)
from juval.application.financial_serialization import (
    FinancialRecordDocument, FinancialSerializationError, serialize_financial_record,
)
from juval.application.native_financial_resolution import resolve_record_financial_dependencies
from juval.application.record_snapshot import record_to_snapshot
from juval.domain.financial_dependencies import FinancialResult as R
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.provenance import SourceType, VerificationStatus
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

from .test_native_financial_calculation import AMOUNTS, every_term_declared
from .test_native_financial_capture import NOW, xlsx
from .test_native_price_and_fees import TP
from .test_pipeline_financial_evidence import legacy, run

TABLE = "execution_run_financial_records"


def build(tmp_path, rows, *, execution_id="run-A", name="in.xlsx", requested=None, resolve=True, calculate=True):
    result = run(xlsx(tmp_path, *rows, name=f"{execution_id}/{name}"), execution_id)
    documents = []
    for item in result.financial_evidence:
        resolution = resolve_record_financial_dependencies(item, target_profit=TP) if resolve else None
        calcs = (calculate_financial_results(resolution, calculated_at=NOW, requested=requested)
                 if resolve and calculate else None)
        documents.append(FinancialRecordDocument(item.evidence, item.capture.selling_price, resolution, calcs))
    snapshots = [record_to_snapshot(record) for record in result.records]
    return result, snapshots, documents


def row(sku, **amounts):
    return {**every_term_declared(**{**AMOUNTS, **amounts}), "supplier_sku": sku}


@pytest.fixture
def store(tmp_path):
    return SqliteExecutionRunStore(tmp_path / "runs.db")


def rows_in(db, table):
    with sqlite3.connect(db) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# -- Round-trip -----------------------------------------------------------------

def test_complete_document_round_trips_through_sqlite(tmp_path, store):
    result, snapshots, documents = build(tmp_path, [row("A", **{T.COG: "4.50"})])
    save_run_with_financial_records(store, result.run, snapshots, documents)
    [original] = documents
    loaded = load_financial_record(store, "run-A", original.evidence.record_reference)
    assert loaded == original
    assert serialize_financial_record(loaded) == serialize_financial_record(original)
    assert str(loaded.evidence.evidence_for(T.COG).amount.value) == "4.50"            # scale kept
    assert loaded.evidence.evidence_for(T.COG).amount.provenance.source_type is SourceType.SUPPLIER_FILE
    assert loaded.evidence.evidence_for(T.VAT).applicability.excludes                  # exclusion, no amount
    assert loaded.evidence.evidence_for(T.VAT).amount is None
    assert loaded.selling_price.amount.value == Decimal("20.00")
    profit = loaded.calculations.for_result(R.PROFIT)
    assert profit.value.value == Decimal("9.30") and profit.value.provenance.source_type is SourceType.CALCULATED
    blocked = loaded.calculations.for_result(R.MAX_COG_TARGET_ROI)                     # no target ROI supplied
    assert blocked.blocker is CalculationBlocker.DEPENDENCIES_UNRESOLVED
    assert blocked.value.status is VerificationStatus.NOT_FOUND
    cog = next(d for d in loaded.resolution.for_result(R.PROFIT).dependencies if d.dependency == "COG")
    assert cog.evidence is loaded.evidence.evidence_for(T.COG)                          # dependency restored
    assert loaded.calculations.decimal_precision == 28 and loaded.calculations.for_result(R.ROI).exact is False


def test_unrequested_results_and_partial_documents_round_trip(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A"), row("B"), row("C")], requested=frozenset({R.PROFIT}))
    no_resolution = FinancialRecordDocument(docs[1].evidence, docs[1].selling_price)
    no_calculations = FinancialRecordDocument(docs[2].evidence, None, docs[2].resolution)
    save_run_with_financial_records(store, result.run, snapshots, [docs[0], no_resolution, no_calculations])
    refs = [r.record_ref for r in result.records]
    first = load_financial_record(store, "run-A", refs[0])
    assert [c.result for c in first.calculations.calculations] == [R.PROFIT]
    assert load_financial_record(store, "run-A", refs[1]) == no_resolution
    assert load_financial_record(store, "run-A", refs[2]) == no_calculations


def test_stored_payload_is_the_canonical_v1_text(tmp_path, store):
    result, snapshots, [document] = build(tmp_path, [row("A")])
    save_run_with_financial_records(store, result.run, snapshots, [document])
    stored = store.load_financial_record("run-A", document.evidence.record_reference)
    assert stored == ("juval.adr047.financial-record", 1,
                      json.dumps(serialize_financial_record(document), sort_keys=True))
    assert load_financial_record(store, "run-A", document.evidence.record_reference) == \
        load_financial_record(store, "run-A", document.evidence.record_reference)


# -- Identity and isolation ----------------------------------------------------

def test_duplicate_asin_records_keep_their_own_documents(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A", **{T.COG: "1.00"}), row("B", **{T.COG: "2.00"})])
    assert len({s["asin"]["value"] for s in snapshots}) == 1                           # same ASIN, two records
    save_run_with_financial_records(store, result.run, snapshots, docs)
    for record, cog in zip(result.records, ("1.00", "2.00")):
        loaded = load_financial_record(store, "run-A", record.record_ref)
        assert str(loaded.evidence.evidence_for(T.COG).amount.value) == cog


def test_runs_are_isolated_and_never_cross_read(tmp_path, store):
    a = build(tmp_path, [row("A", **{T.COG: "1.00"})], execution_id="run-A")
    b = build(tmp_path, [row("A", **{T.COG: "7.00"})], execution_id="run-B")
    for result, snapshots, docs in (a, b):
        save_run_with_financial_records(store, result.run, snapshots, docs)
    ref = a[0].records[0].record_ref
    assert ref == b[0].records[0].record_ref                                           # same record_ref
    assert str(load_financial_record(store, "run-A", ref).evidence.evidence_for(T.COG).amount.value) == "1.00"
    assert str(load_financial_record(store, "run-B", ref).evidence.evidence_for(T.COG).amount.value) == "7.00"
    assert load_financial_record(store, "run-C", ref) is None


def test_missing_document_is_none_not_empty_evidence(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A"), row("B")])
    save_run_with_financial_records(store, result.run, snapshots, docs[:1])            # B has no document
    assert load_financial_record(store, "run-A", result.records[1].record_ref) is None
    assert load_financial_record(store, "run-A", "row_99") is None


# -- Write validation and atomicity ---------------------------------------------

@pytest.mark.parametrize("tamper", ["other_run", "unknown_record", "duplicate"])
def test_invalid_document_set_writes_nothing(tmp_path, store, tamper):
    result, snapshots, docs = build(tmp_path, [row("A"), row("B")])
    if tamper == "other_run":
        _, _, foreign = build(tmp_path, [row("A")], execution_id="run-Z")
        docs = [docs[0], foreign[0]]
    elif tamper == "unknown_record":
        snapshots = snapshots[:1]
    else:
        docs = [docs[0], docs[0]]
    with pytest.raises(FinancialRecordIntegrityError):
        save_run_with_financial_records(store, result.run, snapshots, docs)
    assert store.load_execution_run("run-A") is None
    assert rows_in(tmp_path / "runs.db", TABLE) == 0


@pytest.mark.parametrize("failure", ["foreign_key", "primary_key", "other_run"])
def test_store_rolls_back_run_records_and_financial_rows_together(tmp_path, store, failure):
    """Joint atomicity at the store: the financial INSERT fails after the run and
    snapshot INSERTs already ran in the same transaction."""
    result, snapshots, docs = build(tmp_path, [row("A"), row("B")])
    payloads = [serialize_financial_record(d) for d in docs]
    if failure == "foreign_key":
        snapshots = snapshots[:1]                     # payload of B has no snapshot row -> FK violation
    elif failure == "primary_key":
        payloads = [payloads[0], payloads[0]]         # same (execution_id, record_ref) twice
    else:
        payloads[1]["evidence"]["execution_id"] = "run-Z"
    with pytest.raises((sqlite3.IntegrityError, ValueError)):
        store.save_execution_run(result.run, snapshots, financial_records=payloads)
    assert store.load_execution_run("run-A") is None
    assert store.load_records("run-A") == []
    assert rows_in(tmp_path / "runs.db", TABLE) == 0


def test_documents_cannot_be_overwritten(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    with pytest.raises(sqlite3.IntegrityError):
        save_run_with_financial_records(store, result.run, snapshots, docs)
    assert rows_in(tmp_path / "runs.db", TABLE) == 1


# -- Read failures -------------------------------------------------------------------

def saved(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A"), row("B")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    return [r.record_ref for r in result.records]


def tamper(tmp_path, sql, *params):
    with sqlite3.connect(tmp_path / "runs.db") as conn:
        conn.execute(sql, params)


@pytest.mark.parametrize("payload", ["not json {", "[]", '{"format": "juval.adr047.financial-record"}'])
def test_corrupt_payload_is_a_serialization_error_not_absence(tmp_path, store, payload):
    ref = saved(tmp_path, store)[0]
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ? WHERE record_ref = ?", payload, ref)
    with pytest.raises(FinancialSerializationError):
        load_financial_record(store, "run-A", ref)


def test_unknown_payload_version_is_rejected(tmp_path, store):
    ref = saved(tmp_path, store)[0]
    text = store.load_financial_record("run-A", ref)[2]
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ? WHERE record_ref = ?", text.replace('"version": 1', '"version": 3'), ref)
    with pytest.raises(FinancialSerializationError, match="version 3"):
        load_financial_record(store, "run-A", ref)


def test_v1_payload_relabelled_as_v2_is_rejected_not_upgraded(tmp_path, store):
    ref = saved(tmp_path, store)[0]
    text = store.load_financial_record("run-A", ref)[2]
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ?, format_version = 2 WHERE record_ref = ?",
           text.replace('"version": 1', '"version": 2'), ref)
    with pytest.raises(FinancialSerializationError, match="supplied_inputs"):
        load_financial_record(store, "run-A", ref)


def test_stored_columns_contradicting_the_payload_are_an_integrity_error(tmp_path, store):
    ref = saved(tmp_path, store)[0]
    tamper(tmp_path, f"UPDATE {TABLE} SET format_version = 2 WHERE record_ref = ?", ref)
    with pytest.raises(FinancialRecordIntegrityError):
        load_financial_record(store, "run-A", ref)


def test_payload_of_another_record_is_an_integrity_error(tmp_path, store):
    first, second = saved(tmp_path, store)
    other = store.load_financial_record("run-A", second)[2]
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ? WHERE record_ref = ?", other, first)
    with pytest.raises(FinancialRecordIntegrityError, match="stored under"):
        load_financial_record(store, "run-A", first)


# -- Legacy compatibility and isolation ------------------------------------------------

def test_legacy_runs_are_unchanged_and_not_backfilled(tmp_path, store):
    legacy_run, legacy_records = legacy(xlsx(tmp_path, row("A"), name="legacy/in.xlsx"), "run-L")
    snapshots = [record_to_snapshot(record) for record in legacy_records]
    store.save_execution_run(legacy_run, snapshots)                                     # legacy call shape
    assert store.load_records("run-L") == snapshots
    assert store.load_execution_run("run-L") == legacy_run
    assert load_financial_record(store, "run-L", legacy_records[0].record_ref) is None
    assert rows_in(tmp_path / "runs.db", TABLE) == 0


def test_financial_table_is_added_to_a_pre_existing_database(tmp_path):
    db = tmp_path / "old.db"
    SqliteExecutionRunStore(db)
    with sqlite3.connect(db) as conn:
        conn.execute(f"DROP TABLE {TABLE}")                                           # a database from before 4I
    legacy_run, legacy_records = legacy(xlsx(tmp_path, row("A"), name="old/in.xlsx"), "run-L")
    SqliteExecutionRunStore(db).save_execution_run(legacy_run, [record_to_snapshot(r) for r in legacy_records])
    reopened = SqliteExecutionRunStore(db)
    assert reopened.load_execution_run("run-L") == legacy_run
    assert load_financial_record(reopened, "run-L", legacy_records[0].record_ref) is None


def test_persisting_documents_changes_no_commercial_snapshot(tmp_path, store):
    result, snapshots, docs = build(tmp_path, [row("A")])
    save_run_with_financial_records(store, result.run, snapshots, docs)
    _, legacy_records = legacy(xlsx(tmp_path, row("A"), name="plain/in.xlsx"), "run-A")
    [stored_snapshot] = store.load_records("run-A")
    assert stored_snapshot == record_to_snapshot(legacy_records[0])                     # same profit/decision
    assert "financial" not in json.dumps(stored_snapshot)


def test_persistence_module_uses_no_supabase_network_or_legacy_operands():
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "typing", "juval.application.financial_serialization",
                       "juval.application.financial_serialization_v2", "juval.domain.execution_run"}
    store_source = pathlib.Path(SqliteExecutionRunStore.__module__.replace(".", "/") + ".py")
    text = (pathlib.Path("src") / store_source).read_text(encoding="utf-8")
    assert "supabase" not in text.lower() and "requests" not in text and "http" not in text.lower()
