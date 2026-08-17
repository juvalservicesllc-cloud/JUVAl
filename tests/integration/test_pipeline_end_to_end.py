from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

import juval
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Decision, Thresholds
from juval.domain.execution_run import ExecutionStatus
from juval.domain.risk import Severity

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"


def _thresholds(**overrides):
    defaults = dict(
        target_profit=Decimal("5"),
        target_roi=Decimal("0.3"),
        minimum_estimated_monthly_sales=0,
        maximum_risk_severity=Severity.LOW,
    )
    defaults.update(overrides)
    return Thresholds(**defaults)


def _fees():
    return FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))


def _run():
    return run_pipeline(
        FIXTURE, _thresholds(), fees=_fees(), application_version=juval.__version__,
        execution_id="e2e-test", now=NOW,
    )


def _by_ref(records, suffix):
    for r in records:
        if r.record_ref.endswith(suffix):
            return r
    raise AssertionError(f"no record ending with {suffix!r}")


def test_pipeline_produces_execution_run_with_consistent_counts():
    run, records = _run()
    assert run.records_total == 5  # 5 non-blank rows scanned
    assert run.records_processed == 4  # SUP-005 dropped (missing marketplace)
    assert run.records_successful + run.records_with_errors == run.records_processed
    assert run.status == ExecutionStatus.PARTIAL_SUCCESS  # SUP-003 has RECORD_ERRORs


def test_valid_record_gets_correct_profitability():
    _, records = _run()
    record = _by_ref(records, "SUP-001")
    assert record.profitability is not None
    # selling_price=19.99, fees=3+2=5, seller_proceeds=14.99, cost=cog5+shipping1=6
    assert record.profitability.profit.value == Decimal("19.99") - Decimal("5") - Decimal("6")


def test_record_with_disqualifying_risk_is_pass():
    _, records = _run()
    record = _by_ref(records, "SUP-004")  # hazmat present, severity HIGH > threshold LOW
    assert record.decision.decision == Decision.PASS
    assert any(r.code == "RISK_ABOVE_MAXIMUM" for r in record.decision.reasons)


def test_record_with_missing_cost_has_no_profitability_but_gets_reviewed():
    _, records = _run()
    record = _by_ref(records, "SUP-003")
    assert record.profitability is None
    assert record.decision.decision == Decision.REVIEW
    assert any(r.code == "PROFIT_UNKNOWN" for r in record.decision.reasons)


def test_missing_data_record_never_invents_a_price_or_asin():
    _, records = _run()
    record = _by_ref(records, "SUP-002")
    assert record.product.identification.asin.value is None
    assert record.product.price.selling_price_used is None
    assert record.profitability is None


def test_fatal_import_yields_failed_execution_run(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Supplier SKU", "Marketplace", "ASIN"])  # no "cost" column -> fatal
    ws.append(["X-1", "US", "B0TESTAAAA"])
    path = tmp_path / "broken.xlsx"
    wb.save(path)

    run, records = run_pipeline(
        path, _thresholds(), fees=_fees(), application_version=juval.__version__,
        execution_id="fatal-test", now=NOW,
    )
    assert run.status == ExecutionStatus.FAILED
    assert run.records_total == 0
    assert records == ()
