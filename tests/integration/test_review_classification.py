"""Informative REVIEW sub-classification: pending demand verification (D7-D).

A REVIEW whose only stored reason code is DEMAND_UNKNOWN is findable; nothing
else is, no decision changes, and a historical snapshot without codes is
NOT_CLASSIFIABLE rather than parsed from its reason text.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.application.record_snapshot_store import RecordSnapshotQuery
from juval.application.review_classification import NOT_CLASSIFIABLE, PENDING_DEMAND_VERIFICATION, review_classification
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.risk import Severity
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app
from .api_lab import LOOPBACK

from .test_record_snapshot_pagination import FIXTURE, FEES, THRESHOLDS, run, snapshot

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def classified(index, decision, codes, *, text=None):
    record = snapshot(index, decision=decision)
    record["decision_reasons"] = text if text is not None else [f"{code}: message" for code in codes or []]
    if codes is not None:
        record["decision_reason_codes"] = codes
    return record


def classification_records() -> list[dict]:
    return [
        classified(0, "REVIEW", ["DEMAND_UNKNOWN"]),                          # pending
        classified(1, "REVIEW", ["DEMAND_UNKNOWN", "PROFIT_BELOW_TARGET"]),   # another blocker too
        classified(2, "PASS", ["RISK_ABOVE_MAXIMUM"]),
        classified(3, "BUY", []),
        # Historical: no codes stored. Its text names DEMAND_UNKNOWN alone and
        # must still not be classified -- display text is never parsed.
        classified(4, "REVIEW", None, text=["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."]),
        classified(5, "REVIEW", ["PROFIT_UNKNOWN"]),
        classified(6, "REVIEW", ["DEMAND_UNKNOWN"]),                          # pending
    ]


EXPECTED_PENDING = ["row_00", "row_06"]


def test_the_definition_covers_every_case_and_never_reads_reason_text():
    labels = [review_classification(record) for record in classification_records()]
    assert labels == [PENDING_DEMAND_VERIFICATION, None, None, None, NOT_CLASSIFIABLE, None, PENDING_DEMAND_VERIFICATION]


def refs(store, **query):
    page = store.list_records("run-page", RecordSnapshotQuery(limit=50, **query))
    assert page.total == len(page.items)
    return [item["record_ref"] for item in page.items]


def test_sqlite_filter_selects_exactly_what_the_definition_selects(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.save_execution_run(run(), classification_records())
    assert refs(store, review_classification=PENDING_DEMAND_VERIFICATION) == EXPECTED_PENDING
    assert EXPECTED_PENDING == [r["record_ref"] for r in classification_records() if review_classification(r) == PENDING_DEMAND_VERIFICATION]
    assert refs(store, review_classification=PENDING_DEMAND_VERIFICATION, search="Widget 6") == ["row_06"]   # combines
    assert refs(store, review_classification=PENDING_DEMAND_VERIFICATION, decision="BUY") == []
    assert len(refs(store)) == 7                                                                          # unfiltered unchanged


def test_sqlite_analytics_counts_pending_and_unclassifiable_reviews(tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.save_execution_run(run(), classification_records())
    analytics = store.get_run_analytics("run-page")
    assert analytics["review_classification"] == {"pending_demand_verification": 2, "review_not_classifiable": 1}
    assert analytics["decisions"] == {"REVIEW": 5, "PASS": 1, "BUY": 1}   # decisions are only counted, never altered


def test_an_imported_record_with_permissive_thresholds_is_review_and_pending(tmp_path):
    """The real import path: demand is never imported, so even the most
    permissive thresholds give REVIEW with DEMAND_UNKNOWN as the only code."""
    path = tmp_path / "ideal.csv"
    path.write_text("marketplace,asin,cost,selling_price,hazmat,bulky\nUS,B000000001,3,30,false,false\n")
    permissive = Thresholds(target_profit=Decimal("0"), target_roi=Decimal("0"), minimum_estimated_monthly_sales=0,
                            maximum_risk_severity=Severity.CRITICAL, allow_restricted=True, allow_approval_required=True, allow_unknown_risk=True)
    _, records = run_pipeline(path, permissive, fees=FeeInputs(referral_fee=Decimal("1"), referral_fee_rate=Decimal("0.15")),
                              application_version="test", execution_id="ideal", now=NOW)
    from juval.application.record_snapshot import record_to_snapshot
    stored = record_to_snapshot(records[0])
    assert stored["decision"] == "REVIEW"
    assert stored["decision_reason_codes"] == ["DEMAND_UNKNOWN"]
    assert stored["decision_reasons"][0].startswith("DEMAND_UNKNOWN: ")   # text kept as before
    assert review_classification(stored) == PENDING_DEMAND_VERIFICATION


@pytest.fixture
def client(tmp_path, monkeypatch, auth_lab):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    return TestClient(app, **LOOPBACK)


def upload(client):
    response = client.post("/api/v1/runs", files={"file": ("sample.xlsx", FIXTURE.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                           data={"thresholds": THRESHOLDS, "fees": FEES, "persist": "true"})
    assert response.status_code == 200, response.text
    return response.json()


def test_new_snapshots_store_codes_beside_unchanged_reasons_and_decisions(client):
    created = upload(client)
    records = client.get(f"/api/v1/runs/{created['execution_id']}/records", params={"limit": 50, "confidence": "INCLUDE_INFERRED"}).json()["records"]
    # Decisions of the repository fixture are exactly what they were before (REVIEW x3, PASS x1).
    assert sorted(r["decision"] for r in records) == ["PASS", "REVIEW", "REVIEW", "REVIEW"]
    for record in records:
        assert record["decision_reason_codes"] == [reason.split(":", 1)[0] for reason in record["decision_reasons"]]
    by_ref = {r["record_ref"]: r for r in records}
    assert by_ref["row_2:SUP-001"]["review_classification"] == PENDING_DEMAND_VERIFICATION
    assert by_ref["row_5:SUP-004"]["review_classification"] is None            # PASS
    assert by_ref["row_3:SUP-002"]["review_classification"] is None            # REVIEW with other blockers
    # The POST response carries the same projection.
    assert {r["record_ref"]: r["review_classification"] for r in created["records"]} == {k: v["review_classification"] for k, v in by_ref.items()}


def test_api_filter_export_and_analytics_agree(client):
    run_id = upload(client)["execution_id"]
    params = {"review_classification": PENDING_DEMAND_VERIFICATION, "confidence": "INCLUDE_INFERRED"}
    listed = client.get(f"/api/v1/runs/{run_id}/records", params={**params, "limit": 50}).json()
    assert [r["record_ref"] for r in listed["records"]] == ["row_2:SUP-001"]
    assert listed["pagination"]["total"] == 1
    assert all(r["decision"] == "REVIEW" for r in listed["records"])

    exported = client.get(f"/api/v1/runs/{run_id}/records/export", params=params)
    assert exported.status_code == 200
    workbook = openpyxl.load_workbook(io.BytesIO(exported.content))
    rows = list(workbook["catalog_export"].iter_rows(values_only=True))
    header, body = rows[0], rows[1:]
    assert [row[header.index("record_ref")] for row in body] == [r["record_ref"] for r in listed["records"]]
    assert [row[header.index("review_classification")] for row in body] == [PENDING_DEMAND_VERIFICATION]
    assert [row[header.index("decision")] for row in body] == ["REVIEW"]
    filters = dict(workbook["query_metadata"].iter_rows(values_only=True))["filters"]
    assert json.loads(filters)["review_classification"] == PENDING_DEMAND_VERIFICATION

    analytics = client.get(f"/api/v1/runs/{run_id}/analytics").json()
    assert analytics["review_classification"] == {"pending_demand_verification": 1, "review_not_classifiable": 0}


def test_unfiltered_export_labels_rows_without_changing_their_decision(client):
    run_id = upload(client)["execution_id"]
    exported = client.get(f"/api/v1/runs/{run_id}/records/export", params={"confidence": "INCLUDE_INFERRED"})
    rows = list(openpyxl.load_workbook(io.BytesIO(exported.content))["catalog_export"].iter_rows(values_only=True))
    header = rows[0]
    labels = {row[header.index("record_ref")]: (row[header.index("decision")], row[header.index("review_classification")]) for row in rows[1:]}
    assert labels["row_2:SUP-001"] == ("REVIEW", PENDING_DEMAND_VERIFICATION)
    assert labels["row_5:SUP-004"] == ("PASS", None)


def test_historical_snapshots_keep_their_decision_and_are_not_classified(client, tmp_path):
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.save_execution_run(run(), classification_records())
    record = client.get("/api/v1/runs/run-page/records/row_04").json()
    assert record["decision"] == "REVIEW"
    assert record["decision_reason_codes"] is None
    assert record["review_classification"] == NOT_CLASSIFIABLE
    assert record["decision_reasons"] == ["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."]
    listed = client.get("/api/v1/runs/run-page/records", params={"review_classification": PENDING_DEMAND_VERIFICATION, "limit": 50}).json()
    assert [r["record_ref"] for r in listed["records"]] == EXPECTED_PENDING
    assert client.get("/api/v1/runs/run-page/analytics").json()["review_classification"]["review_not_classifiable"] == 1


@pytest.mark.parametrize("path", ["records", "records/export"])
def test_only_the_pending_demand_classification_is_accepted(client, tmp_path, path):
    SqliteExecutionRunStore(tmp_path / "runs.db").save_execution_run(run(), classification_records())
    for value in ("NOT_CLASSIFIABLE", "BUY", "pending"):
        assert client.get(f"/api/v1/runs/run-page/{path}", params={"review_classification": value}).status_code == 422
