from datetime import datetime, timedelta, timezone

import pytest

from juval.domain.execution_run import ExecutionRun, ExecutionStatus, hash_file

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _run(**overrides):
    defaults = dict(
        execution_id="run-1",
        started_at=NOW,
        finished_at=NOW,
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


def test_valid_run_is_accepted():
    run = _run()
    assert run.status == ExecutionStatus.SUCCESS


def test_running_status_requires_no_finished_at():
    with pytest.raises(ValueError):
        _run(status=ExecutionStatus.RUNNING, finished_at=NOW)
    _run(status=ExecutionStatus.RUNNING, finished_at=None)  # should not raise


def test_non_running_status_requires_finished_at():
    with pytest.raises(ValueError):
        _run(status=ExecutionStatus.SUCCESS, finished_at=None)


def test_finished_before_started_is_rejected():
    with pytest.raises(ValueError):
        _run(finished_at=NOW - timedelta(hours=1))


def test_negative_counts_rejected():
    with pytest.raises(ValueError):
        _run(records_total=-1)


def test_records_processed_cannot_exceed_total():
    with pytest.raises(ValueError):
        _run(records_total=1, records_processed=2, records_successful=2, records_with_errors=0)


def test_successful_plus_errors_cannot_exceed_processed():
    with pytest.raises(ValueError):
        _run(records_processed=2, records_successful=2, records_with_errors=1)


def test_naive_started_at_rejected():
    with pytest.raises(ValueError):
        _run(started_at=datetime(2026, 1, 1))


def test_empty_execution_id_rejected():
    with pytest.raises(ValueError):
        _run(execution_id="")


def test_hash_file_is_deterministic(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"hello juval")
    h1 = hash_file(path)
    h2 = hash_file(path)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_hash_file_differs_for_different_content(tmp_path):
    path_a = tmp_path / "a.txt"
    path_b = tmp_path / "b.txt"
    path_a.write_bytes(b"content a")
    path_b.write_bytes(b"content b")
    assert hash_file(path_a) != hash_file(path_b)
