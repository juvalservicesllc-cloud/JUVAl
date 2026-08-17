from datetime import datetime, timezone
from decimal import Decimal

from juval.domain.decision import Decision, DecisionInputs, Thresholds
from juval.domain.provenance import FieldValue, VerificationStatus
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity
from juval.processing.decision_engine import evaluate_decision

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _thresholds(**overrides):
    defaults = dict(
        target_profit=Decimal("5"),
        target_roi=Decimal("0.3"),
        minimum_estimated_monthly_sales=50,
        maximum_risk_severity=Severity.LOW,
    )
    defaults.update(overrides)
    return Thresholds(**defaults)


def _inputs(profit, roi, sales, risk_profile=None):
    return DecisionInputs(
        profit=profit,
        roi=roi,
        estimated_monthly_sales=sales,
        risk_profile=risk_profile or RiskProfile(),
    )


def _fv(value):
    return FieldValue.verified(value, source="s", method="m", retrieved_at=NOW)


def test_buy_when_all_thresholds_met():
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.BUY
    assert result.reasons == ()


def test_pass_on_negative_profit():
    inputs = _inputs(_fv(Decimal("-1")), _fv(Decimal("0.5")), _fv(100))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.PASS
    assert any(r.code == "NEGATIVE_PROFIT" for r in result.reasons)


def test_pass_on_disqualifying_risk_severity():
    risky_flag = RiskFlag(
        risk_type=RiskType.HAZMAT,
        status=RiskStatus.PRESENT,
        verification_status=VerificationStatus.VERIFIED,
        severity=Severity.HIGH,
        source="s",
        timestamp=NOW,
    )
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(risky_flag,)))
    result = evaluate_decision(inputs, _thresholds(maximum_risk_severity=Severity.LOW), now=NOW)
    assert result.decision == Decision.PASS
    assert any(r.code == "RISK_ABOVE_MAXIMUM" for r in result.reasons)


def test_pass_on_restricted_by_default():
    restricted_flag = RiskFlag(
        risk_type=RiskType.RESTRICTED,
        status=RiskStatus.PRESENT,
        verification_status=VerificationStatus.VERIFIED,
        severity=Severity.NONE,
        source="s",
        timestamp=NOW,
    )
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(restricted_flag,)))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.PASS
    assert any(r.code == "RESTRICTED" for r in result.reasons)


def test_restricted_allowed_when_configured():
    restricted_flag = RiskFlag(
        risk_type=RiskType.RESTRICTED,
        status=RiskStatus.PRESENT,
        verification_status=VerificationStatus.VERIFIED,
        severity=Severity.NONE,
        source="s",
        timestamp=NOW,
    )
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(restricted_flag,)))
    result = evaluate_decision(inputs, _thresholds(allow_restricted=True), now=NOW)
    assert result.decision == Decision.BUY


def test_review_when_profit_unknown():
    not_found_profit = FieldValue.not_found(source="s", method="m", retrieved_at=NOW)
    inputs = _inputs(not_found_profit, _fv(Decimal("0.5")), _fv(100))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.REVIEW
    assert any(r.code == "PROFIT_UNKNOWN" for r in result.reasons)


def test_review_when_profit_below_target():
    inputs = _inputs(_fv(Decimal("1")), _fv(Decimal("0.5")), _fv(100))
    result = evaluate_decision(inputs, _thresholds(target_profit=Decimal("5")), now=NOW)
    assert result.decision == Decision.REVIEW
    assert any(r.code == "PROFIT_BELOW_TARGET" for r in result.reasons)


def test_review_when_demand_below_minimum():
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(10))
    result = evaluate_decision(inputs, _thresholds(minimum_estimated_monthly_sales=50), now=NOW)
    assert result.decision == Decision.REVIEW
    assert any(r.code == "DEMAND_BELOW_MINIMUM" for r in result.reasons)


def test_review_when_risk_unknown_and_not_allowed():
    unknown_flag = RiskFlag(
        risk_type=RiskType.IP_COMPLAINTS,
        status=RiskStatus.UNKNOWN,
        verification_status=VerificationStatus.NOT_FOUND,
        severity=Severity.NONE,
        source="s",
        timestamp=NOW,
    )
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(unknown_flag,)))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.REVIEW
    assert any(r.code == "RISK_UNKNOWN" for r in result.reasons)


def test_unknown_risk_allowed_when_configured():
    unknown_flag = RiskFlag(
        risk_type=RiskType.IP_COMPLAINTS,
        status=RiskStatus.UNKNOWN,
        verification_status=VerificationStatus.NOT_FOUND,
        severity=Severity.NONE,
        source="s",
        timestamp=NOW,
    )
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(unknown_flag,)))
    result = evaluate_decision(inputs, _thresholds(allow_unknown_risk=True), now=NOW)
    assert result.decision == Decision.BUY


def test_pass_takes_precedence_over_review():
    # Both a PASS-triggering (negative profit) and REVIEW-triggering (low demand) condition present.
    inputs = _inputs(_fv(Decimal("-5")), _fv(Decimal("0.5")), _fv(1))
    result = evaluate_decision(inputs, _thresholds(minimum_estimated_monthly_sales=50), now=NOW)
    assert result.decision == Decision.PASS


def test_result_requires_reasons_unless_buy():
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.BUY
    assert result.reasons == ()
