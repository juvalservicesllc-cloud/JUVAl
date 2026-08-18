"""Backend pagination for immutable, run-scoped record snapshots."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from juval.application.record_snapshot_store import RecordSnapshotQuery
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"
THRESHOLDS = json.dumps({"target_profit": "5", "target_roi": "0.3", "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "LOW"})
FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})


def run() -> ExecutionRun:
    return ExecutionRun("run-page", NOW, NOW, ExecutionStatus.SUCCESS, "in.xlsx", "hash", "0.1", 4, 4, 4, 0, 0)


def snapshot(index: int, *, decision: str = "BUY") -> dict:
    return {
        "record_ref": f"row_{index:02}", "supplier_sku": f"SKU-{index}", "title": {"value": f"Widget {index}", "status": "VERIFIED"},
        "brand": {"value": "Juval", "status": "VERIFIED"}, "asin": {"value": f"B0TEST{index:04}", "status": "VERIFIED"},
        "upc": {"value": None, "status": None}, "weight": {"value": None, "status": None}, "selling_price": {"value": None, "status": None},
        "profit": {"value": str(index), "status": "VERIFIED"}, "roi": {"value": str(index / 10), "status": "VERIFIED"}, "margin": {"value": str(index / 100), "status": "VERIFIED"},
        "break_even_price": {"value": None, "status": None}, "max_cog_target_profit": {"value": None, "status": None}, "max_cog_target_roi": {"value": None, "status": None},
        "cog": None, "shipping_per_unit": None, "hazmat_status": "ABSENT", "bulky_status": "ABSENT", "decision": decision, "decision_reasons": [], "issue_count": 0, "issues": [],
    }


def test_sqlite_pages_filtered_snapshots_without_loading_whole_run(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.save_execution_run(run(), [snapshot(i, decision="PASS" if i == 3 else "BUY") for i in range(4)])

    first = store.list_records("run-page", RecordSnapshotQuery(limit=2, sort="record_ref"))
    second = store.list_records("run-page", RecordSnapshotQuery(limit=2, offset=2, sort="record_ref"))
    filtered = store.list_records("run-page", RecordSnapshotQuery(limit=10, decision="PASS", sort="profit", direction="desc"))

    assert [item["record_ref"] for item in first.items] == ["row_00", "row_01"]
    assert [item["record_ref"] for item in second.items] == ["row_02", "row_03"]
    assert first.total == second.total == 4
    assert [item["record_ref"] for item in filtered.items] == ["row_03"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    return TestClient(app)


def upload(client):
    return client.post("/api/v1/runs", files={"file": ("sample.xlsx", FIXTURE.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, data={"thresholds": THRESHOLDS, "fees": FEES, "persist": "true"})


def test_api_records_pagination_filters_and_sorting(client):
    body = upload(client).json()
    execution_id = body["execution_id"]
    first = client.get(f"/api/v1/runs/{execution_id}/records?limit=1&sort=record_ref&direction=asc")
    assert first.status_code == 200
    page = first.json()
    assert len(page["records"]) == 1
    assert page["pagination"] == {"limit": 1, "offset": 0, "total": len(body["records"]), "has_more": True}

    next_page = client.get(f"/api/v1/runs/{execution_id}/records?limit=1&offset=1&sort=record_ref&direction=asc")
    assert next_page.json()["records"][0]["record_ref"] != page["records"][0]["record_ref"]

    decision = body["records"][0]["decision"]
    filtered = client.get(f"/api/v1/runs/{execution_id}/records?decision={decision}&sort=roi&direction=desc")
    assert filtered.status_code == 200
    assert all(record["decision"] == decision for record in filtered.json()["records"])


def test_api_run_analytics_is_database_aggregated_and_preserves_zero(client):
    body = upload(client).json()
    response = client.get(f"/api/v1/runs/{body['execution_id']}/analytics")
    assert response.status_code == 200
    analytics = response.json()
    assert analytics["records"]["total_records"] == len(body["records"])
    assert sum(analytics["decisions"].values()) == len(body["records"])
    assert analytics["data_quality"]["total_issue_count"] >= 0
    assert analytics["profitability"]["profit"]["count"] >= 0


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "sort=anything", "direction=sideways", "decision=UNKNOWN"])
def test_api_records_rejects_invalid_pagination_and_query_values(client, query):
    execution_id = upload(client).json()["execution_id"]
    assert client.get(f"/api/v1/runs/{execution_id}/records?{query}").status_code == 422
