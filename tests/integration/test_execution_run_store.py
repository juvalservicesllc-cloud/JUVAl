"""Integration tests for SqliteExecutionRunStore — real file I/O (a real
.xlsx-style artifact on disk: a SQLite file), never a shared/production
database. Every test uses pytest's `tmp_path` for an isolated file.
"""

import sqlite3
from datetime import datetime, timezone

import pytest

from juval.domain.execution_run import ExecutionRun, ExecutionStatus
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
        records_total=5,
        records_processed=5,
        records_successful=5,
        records_with_errors=0,
        warnings=0,
    )
    defaults.update(overrides)
    return ExecutionRun(**defaults)


def test_schema_initialization_creates_table(tmp_path):
    db_path = tmp_path / "execution_runs.db"
    SqliteExecutionRunStore(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_runs'"
        ).fetchall()
    assert tables == [("execution_runs",)]


def test_save_then_load_round_trip_is_equal(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = _run()

    store.save_execution_run(original)
    loaded = store.load_execution_run(original.execution_id)

    assert loaded == original


def test_finished_at_none_round_trips_for_running_status(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = _run(status=ExecutionStatus.RUNNING, finished_at=None)

    store.save_execution_run(original)
    loaded = store.load_execution_run(original.execution_id)

    assert loaded == original
    assert loaded.finished_at is None


def test_finished_at_timezone_aware_round_trips_exactly(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = _run(started_at=NOW, finished_at=LATER)

    store.save_execution_run(original)
    loaded = store.load_execution_run(original.execution_id)

    assert loaded.started_at == NOW
    assert loaded.finished_at == LATER
    assert loaded.started_at.tzinfo is not None
    assert loaded.finished_at.tzinfo is not None


@pytest.mark.parametrize("status", [ExecutionStatus.SUCCESS, ExecutionStatus.PARTIAL_SUCCESS, ExecutionStatus.FAILED])
def test_terminal_statuses_round_trip(tmp_path, status):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = _run(status=status)

    store.save_execution_run(original)
    loaded = store.load_execution_run(original.execution_id)

    assert loaded.status == status


def test_running_status_round_trips(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = _run(status=ExecutionStatus.RUNNING, finished_at=None)

    store.save_execution_run(original)
    loaded = store.load_execution_run(original.execution_id)

    assert loaded.status == ExecutionStatus.RUNNING


def test_counters_are_preserved_exactly(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    original = _run(records_total=10, records_processed=8, records_successful=6, records_with_errors=2, warnings=3)

    store.save_execution_run(original)
    loaded = store.load_execution_run(original.execution_id)

    assert loaded.records_total == 10
    assert loaded.records_processed == 8
    assert loaded.records_successful == 6
    assert loaded.records_with_errors == 2
    assert loaded.warnings == 3


def test_duplicate_execution_id_raises_instead_of_overwriting(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    store.save_execution_run(_run(execution_id="dup"))

    with pytest.raises(sqlite3.IntegrityError):
        store.save_execution_run(_run(execution_id="dup", records_total=999))

    # the original row must be untouched -- no silent overwrite of an audit record
    loaded = store.load_execution_run("dup")
    assert loaded.records_total == 5


def test_load_nonexistent_execution_id_returns_none(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    assert store.load_execution_run("never-saved") is None


def test_persistence_survives_across_separate_store_instances(tmp_path):
    """The whole point of this store: data must survive the end of the
    connection/process that wrote it, not just live inside one Python
    object in memory."""

    db_path = tmp_path / "execution_runs.db"
    original = _run(execution_id="cross-connection")

    writer = SqliteExecutionRunStore(db_path)
    writer.save_execution_run(original)
    del writer  # simulate the writing connection/process going away

    reader = SqliteExecutionRunStore(db_path)
    loaded = reader.load_execution_run("cross-connection")

    assert loaded == original
