from datetime import datetime, timezone

import pytest

from juval.domain.provenance import FieldValue, VerificationStatus
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _flag(risk_type, status, severity, verification_status=VerificationStatus.VERIFIED):
    return RiskFlag(
        risk_type=risk_type,
        status=status,
        verification_status=verification_status,
        severity=FieldValue.verified(severity, source="s", method="test", retrieved_at=NOW),
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


# -- ADR-020: a VERIFIED NONE needs a VERIFIED absence ------------------------------

def _absent(presence, severity_status):
    severity = (FieldValue.verified if severity_status is VerificationStatus.VERIFIED else FieldValue.inferred)(
        Severity.NONE, source="s", method="no_risk_present", retrieved_at=NOW)
    return RiskFlag(risk_type=RiskType.HAZMAT, status=RiskStatus.ABSENT, verification_status=presence,
                    severity=severity, source="s", timestamp=NOW)


def test_verified_absence_gives_a_verified_none():
    assert _absent(VerificationStatus.VERIFIED, VerificationStatus.VERIFIED).severity.status is VerificationStatus.VERIFIED


def test_inferred_absence_cannot_claim_a_verified_none():
    with pytest.raises(ValueError, match="VERIFIED NONE severity requires a VERIFIED absence"):
        _absent(VerificationStatus.INFERRED, VerificationStatus.VERIFIED)
    # the honest form is accepted: inferred absence, inferred NONE
    assert _absent(VerificationStatus.INFERRED, VerificationStatus.INFERRED).severity.status is VerificationStatus.INFERRED


@pytest.mark.parametrize("presence", [VerificationStatus.NOT_FOUND, VerificationStatus.INVALID])
def test_an_unread_presence_is_never_absent(presence):
    with pytest.raises(ValueError, match="never ABSENT"):
        _absent(presence, VerificationStatus.INFERRED)
