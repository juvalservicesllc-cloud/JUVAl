"""Integration tests for interfaces/api/main.py (Fase 4A).

Uses FastAPI's TestClient (httpx under the hood) -- no real server, no
network socket, same "invoke directly" philosophy as test_cli.py. The
main path drives the real Excel fixture through the real Core
(run_pipeline -> processing -> domain), never a mock, per the Fase 4A
brief ("no crear un mock que sustituya completamente al Core").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"

_THRESHOLDS = json.dumps(
    {
        "target_profit": "5",
        "target_roi": "0.3",
        "minimum_estimated_monthly_sales": 0,
        "maximum_risk_severity": "LOW",
    }
)
_FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "execution_runs.db"))
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    return TestClient(app)


def _upload(client, *, thresholds=_THRESHOLDS, fees=_FEES, persist=None, filename="sample.xlsx", content=None):
    data = {"thresholds": thresholds, "fees": fees}
    if persist is not None:
        data["persist"] = persist
    file_bytes = content if content is not None else FIXTURE.read_bytes()
    return client.post(
        "/api/v1/runs",
        files={"file": (filename, file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data=data,
    )


def test_endpoint_exists(client):
    resp = _upload(client)
    assert resp.status_code != 404


def test_valid_upload_runs_the_real_pipeline(client):
    resp = _upload(client)
    assert resp.status_code == 200
    body = resp.json()
    # Same fixture, same thresholds as test_pipeline_end_to_end.py -> same counts.
    assert body["records_total"] == 5
    assert body["records_processed"] == 4
    assert body["status"] == "PARTIAL_SUCCESS"


def test_response_contains_execution_id(client):
    resp = _upload(client)
    body = resp.json()
    assert body["execution_id"]
    import uuid

    uuid.UUID(body["execution_id"])  # does not raise -> a real UUID4


def test_result_matches_core_calculation(client):
    resp = _upload(client)
    records = resp.json()["records"]
    sup001 = next(r for r in records if r["record_ref"].endswith("SUP-001"))
    # Same fixture/thresholds/fees as test_pipeline_end_to_end.py::test_valid_record_gets_correct_profitability:
    # selling_price=19.99, fees=3+2=5, seller_proceeds=14.99, cost=cog5+shipping1=6 -> profit=8.99
    assert sup001["profit"]["value"] == "8.99"
    assert sup001["profit"]["status"] == "VERIFIED"


def test_result_never_flattens_field_value_to_a_bare_value(client):
    """ADR-003/ADR-004: value and verification_status must travel together."""
    resp = _upload(client)
    record = resp.json()["records"][0]
    assert set(record["asin"].keys()) == {"value", "status"}
    assert record["asin"]["status"] in {"VERIFIED", "NOT_FOUND", "INFERRED", "INVALID"}


def test_missing_data_record_never_invents_asin_or_price(client):
    resp = _upload(client)
    records = resp.json()["records"]
    sup002 = next(r for r in records if r["record_ref"].endswith("SUP-002"))
    assert sup002["asin"]["value"] is None
    assert sup002["asin"]["status"] == "NOT_FOUND"
    assert sup002["selling_price"]["value"] is None


def test_disqualifying_hazmat_risk_is_pass_with_reason(client):
    resp = _upload(client)
    records = resp.json()["records"]
    sup004 = next(r for r in records if r["record_ref"].endswith("SUP-004"))
    assert sup004["decision"] == "PASS"
    assert any("RISK_ABOVE_MAXIMUM" in reason for reason in sup004["decision_reasons"])
    assert sup004["hazmat_severity"] == "HIGH"  # unchanged, still provisional (ADR-010)


def test_thresholds_are_required(client):
    resp = client.post(
        "/api/v1/runs",
        files={"file": ("s.xlsx", FIXTURE.read_bytes())},
        data={"fees": _FEES},  # no thresholds field at all
    )
    assert resp.status_code == 422


def test_thresholds_missing_field_is_rejected(client):
    resp = _upload(client, thresholds=json.dumps({"target_profit": "5"}))
    assert resp.status_code == 422


def test_fees_are_required(client):
    resp = client.post(
        "/api/v1/runs",
        files={"file": ("s.xlsx", FIXTURE.read_bytes())},
        data={"thresholds": _THRESHOLDS},  # no fees field at all
    )
    assert resp.status_code == 422


def test_fees_invariant_violation_is_rejected_not_a_500(client):
    # referral_fee_rate must be in [0, 1) -- FeeInputs.__post_init__ enforces this.
    bad_fees = json.dumps({"referral_fee": "3", "referral_fee_rate": "1.5"})
    resp = _upload(client, fees=bad_fees)
    assert resp.status_code == 422


def test_invalid_excel_file_returns_422_not_500(client):
    resp = _upload(client, filename="bad.xlsx", content=b"not a real xlsx file")
    assert resp.status_code == 422
    assert "not a valid" in resp.json()["detail"]


def test_fatal_import_returns_422_with_failed_status(client, tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Supplier SKU", "Marketplace", "ASIN"])  # no "cost" column -> fatal
    ws.append(["X-1", "US", "B0TESTAAAA"])
    path = tmp_path / "broken.xlsx"
    wb.save(path)

    resp = _upload(client, content=path.read_bytes())
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "FAILED"
    assert body["execution_id"]


def test_no_traceback_is_ever_exposed(client):
    resp = _upload(client, filename="bad.xlsx", content=b"garbage")
    assert "Traceback" not in resp.text
    assert "site-packages" not in resp.text
    assert str(FIXTURE.parent.parent.parent) not in resp.text  # no server filesystem path leaked


def test_execution_run_not_persisted_by_default(client, tmp_path):
    resp = _upload(client)  # no persist field at all
    body = resp.json()
    assert body["persisted"] is False
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    assert store.load_execution_run(body["execution_id"]) is None


def test_execution_run_persisted_when_requested(client, tmp_path):
    resp = _upload(client, persist="true")
    body = resp.json()
    assert body["persisted"] is True
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    saved = store.load_execution_run(body["execution_id"])
    assert saved is not None
    assert saved.status.value == "PARTIAL_SUCCESS"
    assert saved.input_hash == body["input_hash"]


def test_download_returns_the_generated_excel(client):
    resp = _upload(client)
    execution_id = resp.json()["execution_id"]

    download = client.get(f"/api/v1/runs/{execution_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/vnd.openxmlformats")

    import io

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(download.content))
    rows = list(wb.active.iter_rows(values_only=True))
    assert len(rows) == 1 + 4  # header + 4 processed records, same as test_cli.py


def test_unknown_execution_id_returns_404(client):
    resp = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000/download")
    assert resp.status_code == 404


def test_uploaded_input_file_is_deleted_after_processing(client, tmp_path):
    resp = _upload(client)
    execution_id = resp.json()["execution_id"]
    run_dir = tmp_path / "juval_runs" / execution_id
    assert not (run_dir / "input.xlsx").exists()
    assert (run_dir / "output.xlsx").exists()


# -- GET /api/v1/runs/{execution_id}/records (ADR-019) ------------------


def test_get_run_records_after_persist_returns_the_same_records(client):
    resp = _upload(client, persist="true")
    body = resp.json()

    records_resp = client.get(f"/api/v1/runs/{body['execution_id']}/records")

    assert records_resp.status_code == 200
    records_body = records_resp.json()
    assert records_body["execution_id"] == body["execution_id"]
    assert records_body["records"] == body["records"]


def test_get_run_records_unknown_execution_id_returns_404(client):
    resp = client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000/records")
    assert resp.status_code == 404


def test_get_run_records_for_run_with_no_persisted_records_returns_empty_list(client, tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "execution_runs.db")
    store.save_execution_run(_run_without_records())

    resp = client.get(f"/api/v1/runs/{_run_without_records().execution_id}/records")

    assert resp.status_code == 200
    assert resp.json()["records"] == []


def test_get_run_records_requires_a_configured_store(monkeypatch, tmp_path):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.delenv("JUVAL_EXECUTION_DB_PATH", raising=False)
    monkeypatch.delenv("JUVAL_EXECUTION_STORE", raising=False)
    unconfigured_client = TestClient(app)

    resp = unconfigured_client.get("/api/v1/runs/does-not-matter/records")

    assert resp.status_code == 500


def _run_without_records():
    from datetime import datetime, timezone

    from juval.domain.execution_run import ExecutionRun, ExecutionStatus

    return ExecutionRun(
        execution_id="pre-existing-run",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        finished_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        status=ExecutionStatus.SUCCESS,
        input_filename="in.xlsx",
        input_hash="abc123",
        application_version="0.1.0",
        records_total=0,
        records_processed=0,
        records_successful=0,
        records_with_errors=0,
        warnings=0,
    )


# -- GET /api/v1/runs (ADR-019) ------------------------------------------


def test_get_runs_list_is_empty_when_no_runs_persisted(client):
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_get_runs_list_returns_newest_first(client):
    first = _upload(client, persist="true").json()
    second = _upload(client, persist="true").json()

    resp = client.get("/api/v1/runs")

    assert resp.status_code == 200
    execution_ids = [item["execution_id"] for item in resp.json()["items"]]
    assert execution_ids[0] == second["execution_id"]
    assert execution_ids[1] == first["execution_id"]


def test_get_runs_list_respects_limit(client):
    for _ in range(3):
        _upload(client, persist="true")

    resp = client.get("/api/v1/runs", params={"limit": 2})

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_get_runs_list_rejects_limit_over_the_explicit_max(client):
    resp = client.get("/api/v1/runs", params={"limit": 1000})
    assert resp.status_code == 422


def test_get_runs_list_requires_a_configured_store(monkeypatch, tmp_path):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.delenv("JUVAL_EXECUTION_DB_PATH", raising=False)
    monkeypatch.delenv("JUVAL_EXECUTION_STORE", raising=False)
    unconfigured_client = TestClient(app)

    resp = unconfigured_client.get("/api/v1/runs")

    assert resp.status_code == 500
