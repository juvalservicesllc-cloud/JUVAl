"""Profitable records held back only by demand, through the real engine.

`review_classification == PENDING_DEMAND_VERIFICATION` (D7-D) is the existing,
informative way to find them. The engine evaluates every REVIEW rule, so a
REVIEW whose only code is DEMAND_UNKNOWN has a usable profit and ROI at or above
the run's targets and no other blocker. These tests hold that guarantee on real
imports and show that a favourable ROI -- or a declared demand (ADR-052) --
never turns into BUY. No decision, rule or calculation is involved here.

Economics (exact): referral 0, fulfillment 5, cost 10 => profit = P - 15 and
ROI = (P - 15) / 10, so P = 18 meets both targets (3 and 0.30) exactly.
"""

import io
import json
from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.application.record_snapshot import record_to_snapshot
from juval.application.review_classification import PENDING_DEMAND_VERIFICATION, review_classification
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.risk import Severity
from juval.interfaces.api.main import app
from .api_lab import LOOPBACK

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
TARGET_PROFIT, TARGET_ROI = Decimal("3"), Decimal("0.30")
THRESHOLDS = Thresholds(target_profit=TARGET_PROFIT, target_roi=TARGET_ROI, minimum_estimated_monthly_sales=10,
                        maximum_risk_severity=Severity.MEDIUM)
FEES = FeeInputs(referral_fee=Decimal("0"), referral_fee_rate=Decimal("0"), fulfillment_fee=Decimal("5"))
CONTEXT = {"demand_window_start": "2026-09-01T00:00:00-04:00", "demand_window_end": "2026-10-01T00:00:00-04:00",
           "demand_observed_at": "2026-10-01T00:00:00-04:00", "demand_population": "all sellers of this listing on amazon.com",
           "demand_method": "synthetic test declaration"}
HEADER = ["marketplace", "asin", "cost", "selling_price", "hazmat", "bulky", "demand_estimated_sales", *CONTEXT]

# asin -> (cells, expected decision, expected codes, pending?)
CASES = {
    "B000000001": ({"selling_price": "40"}, "REVIEW", ["DEMAND_UNKNOWN"], True),                      # profit 25, ROI 2.5
    "B000000002": ({"selling_price": "18"}, "REVIEW", ["DEMAND_UNKNOWN"], True),                      # exactly on target
    "B000000003": ({"selling_price": "17.99"}, "REVIEW",
                   ["PROFIT_BELOW_TARGET", "ROI_BELOW_TARGET", "DEMAND_UNKNOWN"], False),
    "B000000004": ({"selling_price": "100", "hazmat": "true"}, "PASS", ["RISK_ABOVE_MAXIMUM"], False),
    "B000000005": ({"selling_price": "100", "bulky": "true"}, "REVIEW", ["DEMAND_UNKNOWN", "RISK_AT_MAXIMUM"], False),
    "B000000006": ({"selling_price": "100", "hazmat": ""}, "REVIEW", ["DEMAND_UNKNOWN", "RISK_UNKNOWN"], False),
    "B000000007": ({"selling_price": "abc"}, "REVIEW", ["PROFIT_UNKNOWN", "ROI_UNKNOWN", "DEMAND_UNKNOWN"], False),
    # A million declared units with full context: INFERRED evidence, never a decision input.
    "B000000008": ({"selling_price": "40", "demand_estimated_sales": "1000000", **CONTEXT}, "REVIEW", ["DEMAND_UNKNOWN"], True),
}


def _csv(tmp_path):
    rows = []
    for asin, (cells, *_) in CASES.items():
        values = {"marketplace": "US", "asin": asin, "cost": "10", "hazmat": "false", "bulky": "false", **cells}
        rows.append(",".join(values.get(h, "") for h in HEADER))
    path = tmp_path / "pending.csv"
    path.write_text("\n".join([",".join(HEADER), *rows]) + "\n", encoding="utf-8", newline="")
    return path


@pytest.fixture
def snapshots(tmp_path):
    _, records = run_pipeline(_csv(tmp_path), THRESHOLDS, fees=FEES, application_version="test",
                              execution_id="pending", now=NOW)
    return {s["asin"]["value"]: s for s in map(record_to_snapshot, records)}


def test_each_case_keeps_the_engine_decision_and_is_classified_from_its_codes(snapshots):
    for asin, (_, decision, codes, pending) in CASES.items():
        stored = snapshots[asin]
        assert (stored["decision"], stored["decision_reason_codes"]) == (decision, codes), asin
        assert (review_classification(stored) == PENDING_DEMAND_VERIFICATION) is pending, asin


def test_a_favourable_roi_never_reaches_buy_without_demand(snapshots):
    assert [s["decision"] for s in snapshots.values()].count("BUY") == 0
    best = max(snapshots.values(), key=lambda s: Decimal(s["roi"]["value"]) if s["roi"]["value"] else Decimal("-1"))
    assert Decimal(best["roi"]["value"]) >= Decimal("8.5") and best["decision"] != "BUY"


def test_pending_implies_usable_economics_at_or_above_the_run_targets(snapshots):
    pending = [s for s in snapshots.values() if review_classification(s) == PENDING_DEMAND_VERIFICATION]
    assert {s["asin"]["value"] for s in pending} == {"B000000001", "B000000002", "B000000008"}
    for stored in pending:
        assert stored["profit"]["status"] in ("VERIFIED", "INFERRED") and stored["roi"]["status"] in ("VERIFIED", "INFERRED")
        assert Decimal(stored["profit"]["value"]) >= TARGET_PROFIT and Decimal(stored["roi"]["value"]) >= TARGET_ROI


def test_declared_demand_is_kept_as_evidence_and_changes_nothing(snapshots):
    declared, plain = snapshots["B000000008"], snapshots["B000000001"]
    [observation] = declared["demand_evidence"]["observations"]
    assert observation["value"]["value"] == 1000000 and observation["value"]["status"] == "INFERRED"
    assert observation["value"]["provenance"]["source_type"] == "USER_INPUT"
    for key in ("decision", "decision_reason_codes", "profit", "roi"):
        assert declared[key] == plain[key], key


# -- API: the existing filters compose into "verified-profitable, demand pending" -----------

@pytest.fixture
def client(tmp_path, monkeypatch, auth_lab):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    return TestClient(app, **LOOPBACK)


def _upload(client, path):
    response = client.post("/api/v1/runs", files={"file": (path.name, path.read_bytes(), "text/csv")}, data={
        "thresholds": json.dumps({"target_profit": "3", "target_roi": "0.30", "minimum_estimated_monthly_sales": 10,
                                  "maximum_risk_severity": "MEDIUM"}),
        "fees": json.dumps({"referral_fee": "0", "referral_fee_rate": "0", "fulfillment_fee": "5"}), "persist": "true"})
    assert response.status_code == 200, response.text
    return response.json()["execution_id"]


def _asins(client, run_id, **params):
    body = client.get(f"/api/v1/runs/{run_id}/records", params={"limit": 50, **params}).json()
    assert all(r["decision"] == "REVIEW" for r in body["records"] if r["review_classification"] == PENDING_DEMAND_VERIFICATION)
    return sorted(r["asin"]["value"] for r in body["records"])


def test_api_filters_find_profitable_records_pending_demand_without_changing_them(client, tmp_path):
    run_id = _upload(client, _csv(tmp_path))
    pending = {"review_classification": PENDING_DEMAND_VERIFICATION}

    assert _asins(client, run_id, **pending) == ["B000000001", "B000000002", "B000000008"]
    # ROI >= 50 %, verified economics only: the on-target row drops out.
    assert _asins(client, run_id, **pending, min_roi="0.5", confidence="VERIFIED_ONLY") == ["B000000001", "B000000008"]
    assert len(_asins(client, run_id, confidence="INCLUDE_INFERRED")) == len(CASES)       # unfiltered: nothing hidden

    exported = client.get(f"/api/v1/runs/{run_id}/records/export", params={**pending, "min_roi": "0.5"})
    rows = list(openpyxl.load_workbook(io.BytesIO(exported.content))["catalog_export"].iter_rows(values_only=True))
    header, body = rows[0], rows[1:]
    assert {row[header.index("decision")] for row in body} == {"REVIEW"}
    assert {row[header.index("review_classification")] for row in body} == {PENDING_DEMAND_VERIFICATION}

    analytics = client.get(f"/api/v1/runs/{run_id}/analytics").json()
    assert analytics["review_classification"]["pending_demand_verification"] == 3
    assert "BUY" not in analytics["decisions"]
