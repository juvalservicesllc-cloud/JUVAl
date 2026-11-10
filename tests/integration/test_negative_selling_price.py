"""A negative selling_price is invalid input, not a VERIFIED price.

Before: the importer kept it VERIFIED, profitability turned it into a VERIFIED
negative profit and the engine answered PASS / NEGATIVE_PROFIT ("would lose
money") from bad data. Now it follows the non-numeric path (INVALID_PRICE, no
price used) and the native rule (financial_evidence.py: value < 0 is INVALID).
"""

from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest

from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Decision, Thresholds
from juval.domain.issues import IssueLevel
from juval.domain.provenance import SourceType, VerificationStatus
from juval.domain.risk import Severity
from juval.infrastructure.excel.importer import import_csv, import_excel
from juval.interfaces.api.service import record_to_json

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
HEADER = ["marketplace", "asin", "sku", "title", "cost", "selling_price", "hazmat", "bulky"]
THRESHOLDS = Thresholds(
    target_profit=Decimal("3"), target_roi=Decimal("0.30"), minimum_estimated_monthly_sales=10,
    maximum_risk_severity=Severity.MEDIUM, allow_restricted=False, allow_approval_required=False,
    allow_unknown_risk=False,
)
FEES = FeeInputs(referral_fee=Decimal("0"), referral_fee_rate=Decimal("0.15"),
                 fulfillment_fee=Decimal("5"), other_selling_fees=Decimal("0"))


def _csv(tmp_path, *rows):
    path = tmp_path / "in.csv"
    lines = [",".join(HEADER)] + [",".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return path


def _row(price, *, hazmat="no", cost="10"):
    return ["US", "B000000001", "S1", "item", cost, price, hazmat, "no"]


def _one(result):
    assert len(result.records) == 1
    return result.records[0]


def _codes(record):
    return [issue.code for issue in record.issues]


def _run(path):
    _, records = run_pipeline(path, THRESHOLDS, fees=FEES, application_version="test",
                              execution_id="neg-price", now=NOW)
    assert len(records) == 1
    return records[0]


# -- Import ------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["-25", "-0.01", "-1E2"])
def test_negative_price_is_rejected_like_a_non_numeric_one(tmp_path, raw):
    record = _one(import_csv(_csv(tmp_path, _row(raw)), now=NOW))

    assert record.product.price.selling_price_used is None
    assert record.product.price.current_buy_box is None
    issue = next(i for i in record.issues if i.code == "INVALID_PRICE")
    assert issue.level is IssueLevel.RECORD_ERROR and issue.field == "selling_price"
    assert issue.record_ref == record.record_ref and "must not be negative" in issue.message


def test_non_numeric_price_keeps_its_existing_behaviour(tmp_path):
    record = _one(import_csv(_csv(tmp_path, _row("abc")), now=NOW))

    assert record.product.price.selling_price_used is None
    assert _codes(record) == ["INVALID_PRICE"]


def test_zero_price_stays_a_declared_value(tmp_path):
    # Boundary: as in the native path (test_zero_price_is_a_declared_zero), 0 is
    # not rejected here; only values below zero are.
    record = _one(import_csv(_csv(tmp_path, _row("0")), now=NOW))

    price = record.product.price.selling_price_used
    assert price.value == Decimal("0") and price.status is VerificationStatus.VERIFIED
    assert "INVALID_PRICE" not in _codes(record)


def test_positive_price_is_verified_from_the_supplier_file(tmp_path):
    record = _one(import_csv(_csv(tmp_path, _row("40.50")), now=NOW))

    price = record.product.price.selling_price_used
    assert price.value == Decimal("40.50") and price.status is VerificationStatus.VERIFIED
    assert price.provenance.source_type is SourceType.SUPPLIER_FILE
    assert price.provenance.method == "manual_price_observation"
    assert _codes(record) == []


def test_csv_and_xlsx_reject_a_negative_price_identically(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(HEADER)
    sheet.append(["US", "B000000001", "S1", "item", 10, -25, "no", "no"])
    xlsx = tmp_path / "in.xlsx"
    workbook.save(xlsx)

    from_xlsx = _one(import_excel(xlsx, now=NOW))
    from_csv = _one(import_csv(_csv(tmp_path, _row("-25")), now=NOW))

    assert _codes(from_xlsx) == _codes(from_csv) == ["INVALID_PRICE"]
    assert from_xlsx.product.price.selling_price_used is None


# -- Pipeline -> decision -> API record ----------------------------------------

def test_negative_price_leads_to_review_not_a_verified_loss(tmp_path):
    record = _run(_csv(tmp_path, _row("-25")))
    out = record_to_json(record)

    assert record.decision.decision is Decision.REVIEW
    assert "NEGATIVE_PROFIT" not in out.decision_reason_codes
    assert {"PROFIT_UNKNOWN", "ROI_UNKNOWN"} <= set(out.decision_reason_codes)
    assert record.profitability is None
    assert out.profit.value is None and out.roi.value is None
    assert "INVALID_PRICE" in _codes(record) and "MISSING_SELLING_PRICE" in _codes(record)
    assert "NEGATIVE_PRICE" not in _codes(record)


def test_a_real_loss_from_a_valid_price_is_still_pass(tmp_path):
    # price 12 - fees (5 + 15% of 12) - cost 10 < 0: an economic loss from valid data.
    record = _run(_csv(tmp_path, _row("12")))
    out = record_to_json(record)

    assert record.decision.decision is Decision.PASS
    assert out.decision_reason_codes == ["NEGATIVE_PROFIT"]
    assert out.profit.status == VerificationStatus.VERIFIED.value
    assert Decimal(out.profit.value) < 0


def test_hazmat_block_still_applies_when_the_price_is_invalid(tmp_path):
    record = _run(_csv(tmp_path, _row("-25", hazmat="yes")))
    out = record_to_json(record)

    assert record.decision.decision is Decision.PASS
    assert "RISK_ABOVE_MAXIMUM" in out.decision_reason_codes
    assert "NEGATIVE_PROFIT" not in out.decision_reason_codes


# -- HTTP: upload -> pipeline -> decision -> JSON ---------------------------------

def test_api_upload_reports_the_negative_price_as_review_with_its_issue(tmp_path, monkeypatch, auth_lab):
    import json

    from fastapi.testclient import TestClient

    from juval.interfaces.api.main import app

    from .api_lab import LOOPBACK

    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "execution_runs.db"))
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    content = _csv(tmp_path, _row("-25"), ["US", "B000000002", "S2", "item", "10", "40", "no", "no"]).read_bytes()
    response = TestClient(app, **LOOPBACK).post(
        "/api/v1/runs",
        files={"file": ("supplier.csv", content, "text/csv")},
        data={"thresholds": json.dumps({"target_profit": "3", "target_roi": "0.30",
                                        "minimum_estimated_monthly_sales": 10, "maximum_risk_severity": "MEDIUM"}),
              "fees": json.dumps({"referral_fee": "0", "referral_fee_rate": "0.15", "fulfillment_fee": "5"})},
    )

    assert response.status_code == 200
    negative, valid = response.json()["records"]
    assert negative["decision"] == "REVIEW" and "NEGATIVE_PROFIT" not in negative["decision_reason_codes"]
    assert negative["profit"]["value"] is None and negative["roi"]["value"] is None
    assert "INVALID_PRICE" in negative["issue_codes"] and "NEGATIVE_PRICE" not in negative["issue_codes"]
    assert any("selling_price must not be negative" in text for text in negative["issues"])
    # The valid row in the same file is unaffected: profit and ROI computed and VERIFIED.
    assert valid["profit"]["status"] == "VERIFIED" and valid["roi"]["status"] == "VERIFIED"


def test_zero_price_keeps_the_previous_end_to_end_behaviour(tmp_path):
    # Unchanged by the negative-price fix: 0 is a declared price, so the loss is
    # computed (VERIFIED) and PASS; only margin is undefined.
    record = _run(_csv(tmp_path, _row("0")))
    out = record_to_json(record)

    assert record.decision.decision is Decision.PASS
    assert out.decision_reason_codes == ["NEGATIVE_PROFIT"]
    assert out.profit.status == VerificationStatus.VERIFIED.value and Decimal(out.profit.value) == Decimal("-15")
    assert out.margin.value is None and out.margin.status == VerificationStatus.NOT_FOUND.value
    assert "INVALID_PRICE" not in _codes(record)
