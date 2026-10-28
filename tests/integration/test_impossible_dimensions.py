"""A zero or negative weight/dimension is invalid input, not a VERIFIED value.

Before: the importer kept it VERIFIED and validate_dimensions only added an
IMPOSSIBLE_* issue, so the API showed e.g. "-2 lb VERIFIED". Now the importer
marks it INVALID (value kept in raw_value) and emits that same issue once.
"""

from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest

from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.issues import IssueLevel
from juval.domain.product import Dimensions
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus
from juval.domain.risk import Severity
from juval.infrastructure.excel.importer import import_csv, import_excel
from juval.interfaces.api.service import record_to_json
from juval.processing.data_quality import validate_dimensions

NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
HEADER = ["marketplace", "asin", "sku", "cost", "selling_price", "hazmat", "bulky",
          "weight", "weight_unit", "height", "width", "length", "dimension_unit"]
GOOD = {"weight": "1.5", "weight_unit": "lb", "height": "2", "width": "3", "length": "4", "dimension_unit": "in"}
THRESHOLDS = Thresholds(target_profit=Decimal("3"), target_roi=Decimal("0.30"), minimum_estimated_monthly_sales=10,
                        maximum_risk_severity=Severity.MEDIUM)
FEES = FeeInputs(referral_fee=Decimal("0"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("5"))


def _cells(**dims):
    values = {**GOOD, **dims}
    return ["US", "B000000001", "S1", "10", "40", "no", "no"] + [values[h] for h in HEADER[7:]]


def _csv(tmp_path, *rows, name="in.csv"):
    path = tmp_path / name
    path.write_text("\n".join([",".join(HEADER)] + [",".join(r) for r in rows]) + "\n", encoding="utf-8", newline="")
    return path


def _record(tmp_path, **dims):
    records = import_csv(_csv(tmp_path, _cells(**dims)), now=NOW).records
    assert len(records) == 1
    return records[0]


@pytest.mark.parametrize("field,dims,raw,normalized,unit", [
    ("weight", {"weight": "-2"}, "-2", "-2", "lb"),
    ("weight", {"weight": "0"}, "0", "0", "lb"),
    ("weight", {"weight": "-1", "weight_unit": "kg"}, "-1", None, "lb"),
    ("height", {"height": "0"}, "0", "0", "in"),
    ("length", {"length": "-10", "dimension_unit": "cm"}, "-10", None, "in"),
])
def test_non_positive_size_is_invalid_with_its_value_kept(tmp_path, field, dims, raw, normalized, unit):
    record = _record(tmp_path, **dims)
    fv = getattr(record.product.dimensions, field)

    assert fv.status is VerificationStatus.INVALID and fv.value is None and fv.raw_value == raw
    assert fv.provenance.source_type is SourceType.SUPPLIER_FILE
    issues = [i for i in record.issues if i.code == f"IMPOSSIBLE_{field.upper()}"]
    assert len(issues) == 1
    assert issues[0].level is IssueLevel.RECORD_ERROR and issues[0].field == field
    assert issues[0].message.startswith(f"{field} must be positive, got ") and issues[0].message.endswith(f" {unit}.")
    if normalized is not None:
        assert issues[0].message == f"{field} must be positive, got {normalized} {unit}."


def test_the_issue_is_the_one_validate_dimensions_reports(tmp_path):
    imported = next(i for i in _record(tmp_path, weight="-2").issues if i.code == "IMPOSSIBLE_WEIGHT")
    verified = FieldValue.verified(Decimal("-2"), source="s", method="m", retrieved_at=NOW, unit="lb")
    expected = validate_dimensions(Dimensions(weight=verified), record_ref=imported.record_ref)[0]

    assert (imported.code, imported.level, imported.message, imported.field) == (
        expected.code, expected.level, expected.message, expected.field)


def test_positive_sizes_stay_verified(tmp_path):
    record = _record(tmp_path)
    dims = record.product.dimensions

    assert all(fv.status is VerificationStatus.VERIFIED for fv in (dims.weight, dims.height, dims.width, dims.length))
    assert not [i for i in record.issues if i.code.startswith("IMPOSSIBLE_")]


def test_csv_and_xlsx_agree(tmp_path):
    workbook = openpyxl.Workbook()
    workbook.active.append(HEADER)
    workbook.active.append(["US", "B000000001", "S1", 10, 40, "no", "no", -2, "lb", 2, 3, 4, "in"])
    workbook.save(tmp_path / "in.xlsx")
    from_xlsx = import_excel(tmp_path / "in.xlsx", now=NOW).records[0]
    from_csv = _record(tmp_path, weight="-2")

    assert from_xlsx.product.dimensions.weight.status is from_csv.product.dimensions.weight.status is VerificationStatus.INVALID
    assert [i.code for i in from_xlsx.issues] == [i.code for i in from_csv.issues]


def test_pipeline_reports_once_and_the_decision_does_not_change(tmp_path):
    path = _csv(tmp_path, _cells(weight="-2"), ["US", "B000000002", "S2", "10", "40", "no", "no",
                                                *[GOOD[h] for h in HEADER[7:]]])
    _, (bad, good) = run_pipeline(path, THRESHOLDS, fees=FEES, application_version="test",
                                  execution_id="dims", now=NOW)
    out = record_to_json(bad)

    assert [i.code for i in bad.issues].count("IMPOSSIBLE_WEIGHT") == 1
    assert (out.weight.value, out.weight.status, out.weight.raw_value) == (None, "INVALID", "-2")
    # Dimensions do not feed profitability or decisions: same result as a valid row.
    assert bad.decision.decision is good.decision.decision
    assert [r.code for r in bad.decision.reasons] == [r.code for r in good.decision.reasons]
    assert bad.profitability.profit.value == good.profitability.profit.value
