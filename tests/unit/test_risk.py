from datetime import datetime, timezone

import pytest

from juval.domain.provenance import VerificationStatus
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _flag(risk_type, status, severity, verification_status=VerificationStatus.VERIFIED):
    return RiskFlag(
        risk_type=risk_type,
        status=status,
        verification_status=verification_status,
        severity=severity,
        source="s",
        timestamp=NOW,
    )


def test_absent_risk_must_have_none_severity():
    with pytest.raises(ValueError):
        _flag(RiskType.HAZMAT, RiskStatus.ABSENT, Severity.HIGH)


def test_unknown_risk_must_carry_not_found_or_invalid_verification():
    with pytest.raises(ValueError):
        _flag(RiskType.HAZMAT, RiskStatus.UNKNOWN, Severity.NONE, verification_status=VerificationStatus.VERIFIED)
    # should not raise:
    _flag(RiskType.HAZMAT, RiskStatus.UNKNOWN, Severity.NONE, verification_status=VerificationStatus.NOT_FOUND)


def test_highest_severity_ignores_absent_and_unknown():
    profile = RiskProfile(
        flags=(
            _flag(RiskType.HAZMAT, RiskStatus.ABSENT, Severity.NONE),
            _flag(RiskType.BULKY, RiskStatus.PRESENT, Severity.MEDIUM),
            _flag(RiskType.FRAGILE, RiskStatus.PRESENT, Severity.HIGH),
        )
    )
    assert profile.highest_severity == Severity.HIGH


def test_highest_severity_none_when_no_flags():
    assert RiskProfile().highest_severity == Severity.NONE


def test_has_unknown_risk():
    profile = RiskProfile(
        flags=(
            _flag(
                RiskType.IP_COMPLAINTS,
                RiskStatus.UNKNOWN,
                Severity.NONE,
                verification_status=VerificationStatus.NOT_FOUND,
            ),
        )
    )
    assert profile.has_unknown_risk
    assert not RiskProfile().has_unknown_risk


def test_flag_for_returns_matching_type():
    flag = _flag(RiskType.RESTRICTED, RiskStatus.PRESENT, Severity.CRITICAL)
    profile = RiskProfile(flags=(flag,))
    assert profile.flag_for(RiskType.RESTRICTED) is flag
    assert profile.flag_for(RiskType.HAZMAT) is None
