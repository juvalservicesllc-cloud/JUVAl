"""Requirement 12: same input + same thresholds + same engine version must
produce a deterministic result. `now` and `execution_id` are supplied by
the caller precisely so this holds — see application/run_pipeline.py.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import juval
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.risk import Severity

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"


def _thresholds():
    return Thresholds(
        target_profit=Decimal("5"), target_roi=Decimal("0.3"),
        minimum_estimated_monthly_sales=0, maximum_risk_severity=Severity.LOW,
    )


def _fees():
    return FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))


def test_same_input_same_thresholds_same_version_is_deterministic():
    run1, records1 = run_pipeline(
        FIXTURE, _thresholds(), fees=_fees(), application_version=juval.__version__,
        execution_id="repro-test", now=NOW,
    )
    run2, records2 = run_pipeline(
        FIXTURE, _thresholds(), fees=_fees(), application_version=juval.__version__,
        execution_id="repro-test", now=NOW,
    )

    assert run1 == run2
    assert records1 == records2
    assert len(records1) > 0  # sanity: the fixture actually produced records


def test_different_thresholds_can_change_the_decision():
    lenient = Thresholds(
        target_profit=Decimal("0"), target_roi=Decimal("0"),
        minimum_estimated_monthly_sales=0, maximum_risk_severity=Severity.CRITICAL,
        allow_unknown_risk=True,
    )
    run_a, records_a = run_pipeline(
        FIXTURE, _thresholds(), fees=_fees(), application_version=juval.__version__,
        execution_id="threshold-a", now=NOW,
    )
    run_b, records_b = run_pipeline(
        FIXTURE, lenient, fees=_fees(), application_version=juval.__version__,
        execution_id="threshold-b", now=NOW,
    )
    decisions_a = {r.record_ref: r.decision.decision for r in records_a}
    decisions_b = {r.record_ref: r.decision.decision for r in records_b}
    assert decisions_a != decisions_b  # different, explicit, caller-supplied thresholds -> different outcome
