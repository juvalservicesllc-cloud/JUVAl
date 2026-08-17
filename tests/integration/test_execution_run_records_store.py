"""Integration tests for the record-snapshot half of
SqliteExecutionRunStore (ADR-019) — real SQLite file I/O, mirroring the
pattern of test_execution_run_store.py. Covers save/load of run-scoped
record snapshots, stable ordering, cross-run record_ref reuse (ADR-012),
provenance round-trip, and the atomicity guarantee for
save_execution_run(run, records).
"""

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from juval.application.record_snapshot import record_to_snapshot
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.product import Identification, Product
from juval.domain.provenance import FieldValue
from juval.domain.sourcing_record import SourcingRecord
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)


def _run(**overrides) -> ExecutionRun:
    defaults = dict(
        execution_id="run-1",
        started_at=NOW,
        finished_at=LATER,
        status=ExecutionStatus.SUCCESS,
        input_filename="in.xlsx",
        input_hash="abc123",
        application_version="0.1.0",
        records_total=2,
        records_processed=2,
        records_successful=2,
        records_with_errors=0,
        warnings=0,
    )
    defaults.update(overrides)
    return ExecutionRun(**defaults)


def _record(record_ref: str, asin_status: str = "verified") -> SourcingRecord:
    if asin_status == "verified":
        asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    elif asin_status == "inferred":
        asin = FieldValue.inferred("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    else:
        asin = FieldValue.not_found(source="s", method="m", retrieved_at=NOW)
    product = Product(identification=Identification(asin=asin, marketplace="US", supplier_sku=record_ref))
    return SourcingRecord(record_ref=record_ref, product=product)


def test_save_then_load_records_round_trip(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    records = [record_to_snapshot(_record("row_1"))]

    store.save_execution_run(_run(), records)
    loaded = store.load_records("run-1")

    assert loaded == records


def test_records_load_in_original_processing_order(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    records = [record_to_snapshot(_record(f"row_{n}")) for n in range(5)]

    store.save_execution_run(_run(records_total=5, records_processed=5, records_successful=5), records)
    loaded = store.load_records("run-1")

    assert [r["record_ref"] for r in loaded] == ["row_0", "row_1", "row_2", "row_3", "row_4"]


def test_same_record_ref_in_different_runs_does_not_collide(tmp_path):
    # ADR-012: record_ref is unique only within one execution -- two runs
    # reusing "row_1" (e.g. the same catalog re-processed) must both persist.
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")

    store.save_execution_run(_run(execution_id="run-a", records_total=1, records_processed=1, records_successful=1),
                              [record_to_snapshot(_record("row_1", asin_status="verified"))])
    store.save_execution_run(_run(execution_id="run-b", records_total=1, records_processed=1, records_successful=1),
                              [record_to_snapshot(_record("row_1", asin_status="not_found"))])

    run_a_records = store.load_records("run-a")
    run_b_records = store.load_records("run-b")

    assert run_a_records[0]["record_ref"] == "row_1"
    assert run_b_records[0]["record_ref"] == "row_1"
    assert run_a_records[0]["asin"]["status"] == "VERIFIED"
    assert run_b_records[0]["asin"]["status"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "asin_status,expected_status,expected_value",
    [
        ("verified", "VERIFIED", "B0EXAMPLE1"),
        ("inferred", "INFERRED", "B0EXAMPLE1"),
        ("not_found", "NOT_FOUND", None),
    ],
)
def test_provenance_round_trips_through_persistence(tmp_path, asin_status, expected_status, expected_value):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = record_to_snapshot(_record("row_1", asin_status=asin_status))

    store.save_execution_run(
        _run(execution_id="run-prov", records_total=1, records_processed=1, records_successful=1), [original]
    )
    loaded = store.load_records("run-prov")[0]

    assert loaded["asin"] == {"value": expected_value, "status": expected_status}


def test_snapshot_is_structured_json_not_a_python_repr(tmp_path):
    db_path = tmp_path / "execution_runs.db"
    store = SqliteExecutionRunStore(db_path)
    store.save_execution_run(
        _run(execution_id="run-json", records_total=1, records_processed=1, records_successful=1),
        [record_to_snapshot(_record("row_1"))],
    )

    with sqlite3.connect(db_path) as conn:
        (raw,) = conn.execute(
            "SELECT snapshot FROM execution_run_records WHERE execution_id = ?", ("run-json",)
        ).fetchone()

    parsed = json.loads(raw)  # must be valid JSON, not repr()/pickle
    assert parsed["record_ref"] == "row_1"
    assert parsed["asin"] == {"value": "B0EXAMPLE1", "status": "VERIFIED"}


def test_load_records_for_unknown_execution_id_returns_empty_list(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    assert store.load_records("never-saved") == []


def test_load_records_for_run_with_no_persisted_records_returns_empty_list(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    store.save_execution_run(_run())  # no records passed
    assert store.load_records("run-1") == []


def test_save_execution_run_without_records_still_works(tmp_path):
    # Backward compatibility: CLI's --persist-db never passes records.
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    store.save_execution_run(_run())
    assert store.load_execution_run("run-1") is not None
    assert store.load_records("run-1") == []


def test_list_execution_runs_newest_first(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    store.save_execution_run(_run(execution_id="older", started_at=NOW, finished_at=LATER))
    store.save_execution_run(
        _run(execution_id="newer", started_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
             finished_at=datetime(2026, 1, 2, 0, 5, tzinfo=timezone.utc))
    )

    runs = store.list_execution_runs(limit=20)

    assert [r.execution_id for r in runs] == ["newer", "older"]


def test_list_execution_runs_respects_limit(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    for n in range(5):
        store.save_execution_run(_run(execution_id=f"run-{n}", started_at=datetime(2026, 1, n + 1, tzinfo=timezone.utc),
                                       finished_at=datetime(2026, 1, n + 1, 0, 5, tzinfo=timezone.utc)))

    assert len(store.list_execution_runs(limit=2)) == 2


def test_list_execution_runs_empty_store_returns_empty_list(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    assert store.list_execution_runs(limit=20) == []


def test_atomicity_failed_record_insert_rolls_back_the_run_too(tmp_path):
    """A duplicate record_ref within the same batch makes the second
    INSERT into execution_run_records violate its PRIMARY KEY -- the
    whole transaction (including the execution_runs row) must roll
    back, never leaving the run persisted with partial/no records."""

    db_path = tmp_path / "execution_runs.db"
    store = SqliteExecutionRunStore(db_path)
    duplicated_ref_records = [
        record_to_snapshot(_record("row_1")),
        record_to_snapshot(_record("row_1")),  # same record_ref -> PK collision
    ]

    with pytest.raises(sqlite3.IntegrityError):
        store.save_execution_run(_run(execution_id="run-atomic"), duplicated_ref_records)

    assert store.load_execution_run("run-atomic") is None
    assert store.load_records("run-atomic") == []
