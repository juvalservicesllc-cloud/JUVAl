"""Unit tests for application/record_snapshot.py -- specifically that
RiskFlag.severity's own provenance (ADR-020, FieldValue[Severity]) is
unwrapped correctly into the snapshot's hazmat_severity/bulky_severity
plain-string fields, without changing that field's shape (still a bare
string, not {value, status} -- API_CONTRACT.md unchanged) and without
crashing on a severity that could not be assessed (NOT_FOUND/INVALID).
"""

from datetime import datetime, timezone

from juval.application.record_snapshot import record_to_snapshot
from juval.domain.product import Identification, Product
from juval.domain.provenance import FieldValue
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity
from juval.domain.sourcing_record import SourcingRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record_with_risk(*flags: RiskFlag) -> SourcingRecord:
    asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    product = Product(identification=Identification(asin=asin, marketplace="US"))
    return SourcingRecord(record_ref="row_1", product=product, risk=RiskProfile(flags=flags))


def test_policy_derived_severity_survives_as_plain_string():
    flag = RiskFlag(
        risk_type=RiskType.HAZMAT, status=RiskStatus.PRESENT,
        verification_status=FieldValue.verified(True, source="s", method="m", retrieved_at=NOW).status,
        severity=FieldValue.inferred(
            Severity.HIGH, source="DEFAULT_RISK_SEVERITY", method="ADR-010", retrieved_at=NOW,
        ),
        source="s", timestamp=NOW,
    )
    snapshot = record_to_snapshot(_record_with_risk(flag))

    assert snapshot["hazmat_severity"] == "HIGH"
    assert isinstance(snapshot["hazmat_severity"], str)


def test_unassessable_severity_maps_to_none_not_a_crash():
    flag = RiskFlag(
        risk_type=RiskType.HAZMAT, status=RiskStatus.UNKNOWN,
        verification_status=FieldValue.not_found(source="s", method="m", retrieved_at=NOW).status,
        severity=FieldValue.not_found(source="s", method="risk_presence_unknown", retrieved_at=NOW),
        source="s", timestamp=NOW,
    )
    snapshot = record_to_snapshot(_record_with_risk(flag))

    assert snapshot["hazmat_severity"] is None


def test_no_risk_flag_maps_to_none():
    snapshot = record_to_snapshot(_record_with_risk())
    assert snapshot["hazmat_severity"] is None
    assert snapshot["bulky_severity"] is None
