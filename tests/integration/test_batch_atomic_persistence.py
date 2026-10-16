"""Atomic batch persistence (ADR-050 unit 1) on temporary SQLite. Synthetic data only.

The scenarios are plain functions of (store, rows, store_module, tmp_path) so
the PostgreSQL suite runs exactly the same ones against a disposable cluster
(test_postgres_financial_persistence.py). Failures are real constraint
violations where one exists; otherwise a write helper of the store module is
made to raise mid-transaction.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

import pytest

import juval
from juval.application.batch_persistence import BatchChild, BatchIntegrityError, save_batch_with_runs
from juval.application.financial_persistence import (
    FinancialRecordIntegrityError, load_capture_diagnostics, load_financial_record,
)
from juval.application.native_financial_documents import build_financial_documents, capture_diagnostics_sets
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline_with_financial_evidence
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, aggregate_batch_status
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.risk import Severity
from juval.infrastructure.logging import sqlite_execution_run_store as sqlite_module
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

from .test_cli_native_financial import row
from .test_native_financial_capture import BASE, declared, xlsx

NOW = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
THRESHOLDS = Thresholds(Decimal("5"), Decimal("0.3"), 0, Severity.LOW)
FEES = FeeInputs(Decimal("3"), Decimal("0.15"), Decimal("2"))
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOC, DIAG = "execution_run_financial_records", "execution_run_capture_diagnostics"
TABLES = ("execution_runs", "execution_run_records", DOC, DIAG, "batches", "batch_files")
MIXED = [row("FULL"), row("BAD", **declared(T.COG, "abc")),                       # INVALID kept with its raw value
         row("INFERRED", **declared(T.COG, "4.50", applies_method="supplier estimate")),
         {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")}]       # diagnostics, no document


def child(tmp_path, execution_id, *rows):
    """A real child: the pipeline, documents and diagnostics of one synthetic file."""
    path = xlsx(tmp_path, *rows, name=f"{execution_id}/in.xlsx")
    outcome = run_pipeline_with_financial_evidence(path, THRESHOLDS, fees=FEES,
                                                   application_version=juval.__version__,
                                                   execution_id=execution_id, now=NOW)
    return BatchChild(outcome.run, [record_to_snapshot(r) for r in outcome.records],
                      build_financial_documents(outcome, calculated_at=NOW,
                                                application_version=outcome.run.application_version),
                      capture_diagnostics_sets(outcome))


def batch_of(batch_id, children, *, rejected=0):
    files = [BatchFile(i, f"{c.run.execution_id}.xlsx", XLSX, 100, BatchFileStatus(c.run.status.value),
                       c.run.execution_id, records_total=c.run.records_total,
                       records_processed=c.run.records_processed, records_with_errors=c.run.records_with_errors,
                       warning_count=c.run.warnings)
             for i, c in enumerate(children)]
    files += [BatchFile(len(files) + i, "notes.txt", "text/plain", 10, BatchFileStatus.REJECTED, None,
                        errors=("unsupported file type",)) for i in range(rejected)]
    return Batch(batch_id, NOW, aggregate_batch_status(tuple(files)), tuple(files))


def nothing_stored(rows):
    return all(rows(table) == [] for table in TABLES)


# -- Scenarios shared with the PostgreSQL suite ------------------------------------------

def all_children_and_the_batch_are_stored_together(store, rows, store_module, tmp_path):
    children = [child(tmp_path, "run-1", *MIXED), child(tmp_path, "run-2", row("B"))]
    batch = batch_of("batch-1", children)
    save_batch_with_runs(store, batch, children)
    assert store.load_batch("batch-1") == batch
    for item in children:
        execution_id = item.run.execution_id
        assert store.load_execution_run(execution_id) == item.run
        assert store.load_records(execution_id) == list(item.snapshots)
        assert store.load_batch_for_run(execution_id).batch_id == "batch-1"
        for document in item.documents:                                  # values, statuses, provenance intact
            ref = document.document.evidence.record_reference
            assert load_financial_record(store, execution_id, ref) == document
        for diagnostics in item.capture_diagnostics:
            assert load_capture_diagnostics(store, execution_id, diagnostics.record_ref) == diagnostics
    assert sorted(rows(DOC)) == ["run-1"] * 3 + ["run-2"]
    assert sorted(rows(DIAG)) == ["run-1"] * 4 + ["run-2"]


def a_rejected_file_is_stored_as_an_outcome_without_a_run(store, rows, store_module, tmp_path):
    children = [child(tmp_path, "run-1", row("A"))]
    batch = batch_of("batch-1", children, rejected=1)
    save_batch_with_runs(store, batch, children)
    loaded = store.load_batch("batch-1")
    assert [f.status for f in loaded.files] == [BatchFileStatus.SUCCESS, BatchFileStatus.REJECTED]
    assert loaded.files[1].execution_id is None and rows("execution_runs") == ["run-1"]


def a_failing_write_of_the_second_child_stores_nothing(store, rows, store_module, tmp_path):
    first, second = child(tmp_path, "run-1", row("A")), child(tmp_path, "run-2", row("B"))
    duplicated = BatchChild(second.run, [*second.snapshots, second.snapshots[0]], second.documents,
                            second.capture_diagnostics)                     # a real primary-key violation
    with pytest.raises(Exception):
        save_batch_with_runs(store, batch_of("batch-1", [first, duplicated]), [first, duplicated])
    assert nothing_stored(rows)


def a_failing_financial_document_write_stores_nothing(store, rows, store_module, tmp_path, monkeypatch):
    original = store_module._financial_row

    def fail_for_second(execution_id, payload):
        if execution_id == "run-2":
            raise ValueError("simulated failure after the run and snapshot inserts")
        return original(execution_id, payload)
    monkeypatch.setattr(store_module, "_financial_row", fail_for_second)
    children = [child(tmp_path, "run-1", *MIXED), child(tmp_path, "run-2", row("B"))]
    with pytest.raises(ValueError, match="simulated"):
        save_batch_with_runs(store, batch_of("batch-1", children), children)
    assert nothing_stored(rows)


def a_failing_batch_write_after_every_child_stores_nothing_new(store, rows, store_module, tmp_path):
    store.save_batch(Batch("batch-1", NOW, aggregate_batch_status(()), ()))      # the id is already taken
    children = [child(tmp_path, "run-1", *MIXED), child(tmp_path, "run-2", row("B"))]
    with pytest.raises(Exception):
        save_batch_with_runs(store, batch_of("batch-1", children), children)
    assert all(rows(table) == [] for table in TABLES if table != "batches")
    assert rows("batches") == ["batch-1"] and store.load_batch("batch-1").files == ()   # the earlier one, intact


def a_child_whose_execution_already_exists_stores_nothing_and_overwrites_nothing(store, rows, store_module,
                                                                                  tmp_path):
    existing = child(tmp_path, "run-2", row("OLD"))
    store.save_execution_run(existing.run, existing.snapshots)
    children = [child(tmp_path, "run-1", row("A")), child(tmp_path, "run-2", row("NEW"))]
    with pytest.raises(Exception):
        save_batch_with_runs(store, batch_of("batch-1", children), children)
    assert rows("execution_runs") == ["run-2"] and store.load_records("run-2") == list(existing.snapshots)
    assert rows("batches") == [] and rows(DOC) == []


def files_repeating_a_record_ref_stay_separate_documents(store, rows, store_module, tmp_path):
    children = [child(tmp_path, "run-1", row("SAME", **declared(T.COG, "1.00"))),
                child(tmp_path, "run-2", row("SAME", **declared(T.COG, "7.00")))]
    save_batch_with_runs(store, batch_of("batch-1", children), children)
    [ref] = {d.document.evidence.record_reference for c in children for d in c.documents}
    first, second = (load_financial_record(store, run, ref) for run in ("run-1", "run-2"))
    assert first == children[0].documents[0] and second == children[1].documents[0]
    assert first.document.evidence.execution_id == "run-1" and second.document.evidence.execution_id == "run-2"
    assert str(first.document.evidence.evidence_for(T.COG).amount.value) == "1.00"
    assert str(second.document.evidence.evidence_for(T.COG).amount.value) == "7.00"


SCENARIOS = [all_children_and_the_batch_are_stored_together,
             a_rejected_file_is_stored_as_an_outcome_without_a_run,
             a_failing_write_of_the_second_child_stores_nothing,
             a_failing_financial_document_write_stores_nothing,
             a_failing_batch_write_after_every_child_stores_nothing_new,
             a_child_whose_execution_already_exists_stores_nothing_and_overwrites_nothing,
             files_repeating_a_record_ref_stay_separate_documents]


def run_scenario(scenario, store, rows, store_module, tmp_path, monkeypatch):
    if scenario is a_failing_financial_document_write_stores_nothing:
        scenario(store, rows, store_module, tmp_path, monkeypatch)
    else:
        scenario(store, rows, store_module, tmp_path)


# -- SQLite ---------------------------------------------------------------------------------

@pytest.fixture
def sqlite_store(tmp_path):
    path = tmp_path / "batches.db"
    store = SqliteExecutionRunStore(path)

    def rows(table):
        column = "batch_id" if table.startswith("batch") else "execution_id"
        with sqlite3.connect(path) as conn:
            return [value for (value,) in conn.execute(f"SELECT {column} FROM {table}")]
    return store, rows


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.__name__)
def test_sqlite(scenario, sqlite_store, tmp_path, monkeypatch):
    store, rows = sqlite_store
    run_scenario(scenario, store, rows, sqlite_module, tmp_path, monkeypatch)


# -- Validation before any write ---------------------------------------------------------------

def test_children_and_batch_files_must_describe_the_same_executions(sqlite_store, tmp_path):
    store, rows = sqlite_store
    one, two = child(tmp_path, "run-1", row("A")), child(tmp_path, "run-2", row("B"))
    cases = [
        (batch_of("b", [one]), [one, two], "children without a batch file: \\['run-2'\\]"),
        (batch_of("b", [one, two]), [one], "batch files without a child: \\['run-2'\\]"),
        (batch_of("b", [one]), [one, one], "more than once"),
        (batch_of("b", [one, one]), [one], "more than once"),
    ]
    for batch, children, message in cases:
        with pytest.raises(BatchIntegrityError, match=message):
            save_batch_with_runs(store, batch, children)
    bad = batch_of("b", [one])
    rejected = Batch("b", NOW, bad.status, (bad.files[0], BatchFile(1, "x.txt", None, 1, BatchFileStatus.REJECTED,
                                                                    "run-9")))
    with pytest.raises(BatchIntegrityError, match="rejected file 1 names an execution"):
        save_batch_with_runs(store, rejected, [one])
    foreign = BatchChild(two.run, two.snapshots, one.documents)                       # run-1's document
    with pytest.raises(FinancialRecordIntegrityError, match="cannot be saved with 'run-2'"):
        save_batch_with_runs(store, batch_of("b", [one, foreign]), [one, foreign])
    assert nothing_stored(rows)


def test_existing_single_run_and_batch_writes_are_unchanged(sqlite_store, tmp_path):
    """The extracted write helpers serve save_execution_run and save_batch as before."""
    store, rows = sqlite_store
    one = child(tmp_path, "run-1", row("A"))
    store.save_execution_run(one.run, one.snapshots)
    batch = batch_of("batch-1", [one])
    store.save_batch(batch)
    assert store.load_execution_run("run-1") == one.run and store.load_records("run-1") == list(one.snapshots)
    assert store.load_batch("batch-1") == batch and rows(DOC) == []
