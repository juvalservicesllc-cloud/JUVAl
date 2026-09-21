from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.domain.decision import Decision, DecisionInputs, Thresholds
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus
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


def _severity(value):
    return FieldValue.verified(value, source="s", method="test", retrieved_at=NOW)


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
        severity=_severity(Severity.HIGH),
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
        severity=_severity(Severity.NONE),
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
        severity=_severity(Severity.NONE),
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
        severity=_severity(Severity.NONE),
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
        severity=_severity(Severity.NONE),
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


@pytest.mark.parametrize("risk_type", [RiskType.HAZMAT, RiskType.BULKY])
@pytest.mark.parametrize("verification", [VerificationStatus.VERIFIED, VerificationStatus.INFERRED])
@pytest.mark.parametrize("severity,expected,code", [
    (Severity.LOW, Decision.BUY, None),
    (Severity.MEDIUM, Decision.REVIEW, "RISK_AT_MAXIMUM"),
    (Severity.HIGH, Decision.PASS, "RISK_ABOVE_MAXIMUM"),
])
def test_risk_limit_policy(risk_type, verification, severity, expected, code):
    build = FieldValue.verified if verification == VerificationStatus.VERIFIED else FieldValue.inferred
    severity_field = build(severity, source="risk-test", method="explicit test classification", retrieved_at=NOW)
    flag = RiskFlag(risk_type, RiskStatus.PRESENT, verification, severity_field, "risk-test", NOW)
    profile = RiskProfile(flags=(flag,))
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), profile)
    result = evaluate_decision(inputs, _thresholds(maximum_risk_severity=Severity.MEDIUM), now=NOW)
    assert result.decision == expected
    assert [r.code for r in result.reasons] == ([code] if code else [])
    if code == "RISK_AT_MAXIMUM":
        assert risk_type.value in result.reasons[0].message
        assert "MEDIUM" in result.reasons[0].message
        assert verification.value in result.reasons[0].message
    assert inputs.risk_profile is profile
    assert flag.severity is severity_field
    assert flag.severity.status == verification
    assert flag.verification_status == verification
    assert result == evaluate_decision(inputs, _thresholds(maximum_risk_severity=Severity.MEDIUM), now=NOW)


@pytest.mark.parametrize("risk_type", [RiskType.HAZMAT, RiskType.BULKY])
def test_equal_risk_keeps_independent_pass_precedence(risk_type):
    flag = RiskFlag(risk_type, RiskStatus.PRESENT, VerificationStatus.VERIFIED, _severity(Severity.LOW), "s", NOW)
    inputs = _inputs(_fv(Decimal("-1")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(flag,)))
    result = evaluate_decision(inputs, _thresholds(), now=NOW)
    assert result.decision == Decision.PASS
    assert [r.code for r in result.reasons] == ["NEGATIVE_PROFIT"]


@pytest.mark.parametrize("risk_type", [RiskType.HAZMAT, RiskType.BULKY])
def test_below_limit_continues_other_review_rules(risk_type):
    flag = RiskFlag(risk_type, RiskStatus.PRESENT, VerificationStatus.VERIFIED, _severity(Severity.LOW), "s", NOW)
    inputs = _inputs(_fv(Decimal("1")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(flag,)))
    result = evaluate_decision(inputs, _thresholds(maximum_risk_severity=Severity.MEDIUM), now=NOW)
    assert result.decision == Decision.REVIEW
    assert [r.code for r in result.reasons] == ["PROFIT_BELOW_TARGET"]


@pytest.mark.parametrize("risk_type", [RiskType.HAZMAT, RiskType.BULKY])
@pytest.mark.parametrize("verification", [VerificationStatus.NOT_FOUND, VerificationStatus.INVALID])
def test_unknown_severity_is_not_compared_to_limit_or_promoted(risk_type, verification):
    severity = (FieldValue.not_found(source="s", method="missing", retrieved_at=NOW)
                if verification == VerificationStatus.NOT_FOUND else
                FieldValue.invalid("bad", source="s", method="invalid", retrieved_at=NOW, source_type=SourceType.SUPPLIER_FILE))
    flag = RiskFlag(risk_type, RiskStatus.UNKNOWN, verification, severity, "s", NOW)
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(flag,)))
    result = evaluate_decision(inputs, _thresholds(maximum_risk_severity=Severity.NONE), now=NOW)
    assert result.decision == Decision.REVIEW
    assert [r.code for r in result.reasons] == ["RISK_UNKNOWN"]
    assert flag.severity is severity
    assert flag.verification_status == verification


@pytest.mark.parametrize("risk_type", [RiskType.HAZMAT, RiskType.BULKY])
def test_absent_risk_at_none_limit_does_not_trigger_review(risk_type):
    flag = RiskFlag(risk_type, RiskStatus.ABSENT, VerificationStatus.VERIFIED, _severity(Severity.NONE), "s", NOW)
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(flag,)))
    result = evaluate_decision(inputs, _thresholds(maximum_risk_severity=Severity.NONE), now=NOW)
    assert result.decision == Decision.BUY


def test_explicit_custom_review_rules_still_replace_defaults():
    flag = RiskFlag(RiskType.HAZMAT, RiskStatus.PRESENT, VerificationStatus.VERIFIED, _severity(Severity.LOW), "s", NOW)
    inputs = _inputs(_fv(Decimal("10")), _fv(Decimal("0.5")), _fv(100), RiskProfile(flags=(flag,)))
    assert evaluate_decision(inputs, _thresholds(), now=NOW, review_rules=()).decision == Decision.BUY


@pytest.mark.parametrize("hazmat,bulky,profit,expected,codes", [
    (Severity.LOW, Severity.LOW, "10", Decision.BUY, []),
    (Severity.MEDIUM, Severity.LOW, "10",
     Decision.REVIEW, ["RISK_AT_MAXIMUM"]),
    (Severity.LOW, Severity.MEDIUM, "10",
     Decision.REVIEW, ["RISK_AT_MAXIMUM"]),
    (Severity.HIGH, Severity.MEDIUM, "10",
     Decision.PASS, ["RISK_ABOVE_MAXIMUM"]),
    (Severity.MEDIUM, Severity.HIGH, "10",
     Decision.PASS, ["RISK_ABOVE_MAXIMUM"]),
    (Severity.MEDIUM, Severity.MEDIUM, "-1",
     Decision.PASS, ["NEGATIVE_PROFIT"]),
])
def test_multiple_risks_keep_individual_rules_without_count_gate(
    hazmat, bulky, profit, expected, codes,
):
    profile = RiskProfile(flags=tuple(
        RiskFlag(
            kind, RiskStatus.PRESENT, VerificationStatus.VERIFIED,
            _severity(level), "s", NOW,
        )
        for kind, level in [
            (RiskType.HAZMAT, hazmat), (RiskType.BULKY, bulky),
        ]
    ))
    inputs = _inputs(
        _fv(Decimal(profit)), _fv(Decimal("0.5")), _fv(100), profile,
    )
    result = evaluate_decision(
        inputs, _thresholds(maximum_risk_severity=Severity.MEDIUM),
        now=NOW,
    )
    assert result.decision == expected
    assert [reason.code for reason in result.reasons] == codes
    assert inputs.risk_profile is profile
