from datetime import datetime, timezone
from decimal import Decimal

from juval.domain.costs import CostInputs, FeeInputs
from juval.domain.decision import Decision, Thresholds
from juval.domain.issues import IssueLevel, ProcessingIssue
from juval.domain.product import Identification, Price, Product, SellingPriceSource
from juval.domain.provenance import FieldValue, SourceType
from juval.domain.risk import Severity
from juval.domain.sourcing_record import SourcingRecord
from juval.processing.pipeline import process_batch, process_record

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _thresholds(**overrides):
    defaults = dict(
        target_profit=Decimal("5"), target_roi=Decimal("0.3"),
        minimum_estimated_monthly_sales=0, maximum_risk_severity=Severity.LOW,
    )
    defaults.update(overrides)
    return Thresholds(**defaults)


def _fees():
    return FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))


def _valid_record():
    asin = FieldValue.verified("B0PIPELINE1", source="s", method="m", retrieved_at=NOW)
    price = FieldValue.verified(Decimal("20"), source="s", method="m", retrieved_at=NOW)
    product = Product(
        identification=Identification(asin=asin, marketplace="US"),
        price=Price(current_buy_box=price, selling_price_used=price, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX),
    )
    return SourcingRecord(record_ref="row_1", product=product, costs=CostInputs(cog=Decimal("8")))


def test_process_record_computes_profitability_via_existing_engine():
    record = process_record(_valid_record(), _thresholds(), fees=_fees(), now=NOW)
    assert record.profitability is not None
    # 20 - 5(fees) = 15 proceeds; cost = 8; profit = 7
    assert record.profitability.profit.value == Decimal("7")


def test_process_record_reaches_a_decision():
    record = process_record(_valid_record(), _thresholds(), fees=_fees(), now=NOW)
    assert record.decision is not None
    assert record.decision.decision in (Decision.BUY, Decision.REVIEW, Decision.PASS)


def test_process_record_without_costs_skips_profitability_not_a_crash():
    record = SourcingRecord(record_ref="row_1", product=_valid_record().product, costs=None)
    result = process_record(record, _thresholds(), fees=_fees(), now=NOW)
    assert result.profitability is None
    assert result.decision.decision == Decision.REVIEW
    assert any(r.code == "PROFIT_UNKNOWN" for r in result.decision.reasons)


def test_process_record_without_fees_produces_warning_not_a_crash():
    record = process_record(_valid_record(), _thresholds(), fees=None, now=NOW)
    assert record.profitability is None
    assert any(i.code == "MISSING_FEES" for i in record.issues)


def test_process_record_accumulates_data_quality_issues():
    # A FieldValue claiming VERIFIED but structurally malformed is exactly
    # the contradiction validate_identification's defense-in-depth check
    # exists to catch (an already-INVALID FieldValue is not re-flagged —
    # its own status already carries that information).
    asin = FieldValue.verified("NOT-TEN-CHARS", source="s", method="m", retrieved_at=NOW, source_type=SourceType.SUPPLIER_FILE)
    product = Product(identification=Identification(asin=asin, marketplace="US"))
    record = SourcingRecord(record_ref="row_1", product=product)
    result = process_record(record, _thresholds(), fees=_fees(), now=NOW)
    assert any(i.code == "INVALID_ASIN_FORMAT" for i in result.issues)


def test_process_batch_processes_every_record_independently():
    records = (_valid_record(), _valid_record())
    results = process_batch(records, _thresholds(), fees=_fees(), now=NOW)
    assert len(results) == 2
    assert all(r.profitability is not None for r in results)


def test_process_record_preserves_prior_issues():
    record = _valid_record().with_issues(ProcessingIssue(level=IssueLevel.WARNING, code="PRIOR", message="from import"))
    result = process_record(record, _thresholds(), fees=_fees(), now=NOW)
    assert any(i.code == "PRIOR" for i in result.issues)
