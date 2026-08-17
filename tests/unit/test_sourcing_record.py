from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.domain.costs import CostInputs
from juval.domain.decision import Decision, DecisionReason, DecisionResult
from juval.domain.identifiers import is_valid_asin
from juval.domain.issues import IssueLevel, ProcessingIssue
from juval.domain.product import Identification, Product
from juval.domain.provenance import FieldValue, VerificationStatus
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity
from juval.domain.sourcing_record import SourcingRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _product():
    asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    assert is_valid_asin(asin.value)
    return Product(identification=Identification(asin=asin, marketplace="US"))


def test_construction_with_minimal_fields():
    record = SourcingRecord(record_ref="row_1", product=_product())
    assert record.costs is None
    assert record.fees is None
    assert record.risk == RiskProfile()
    assert record.profitability is None
    assert record.decision is None
    assert record.issues == ()


def test_record_ref_must_not_be_empty():
    with pytest.raises(ValueError):
        SourcingRecord(record_ref="", product=_product())


def test_composition_does_not_duplicate_product_fields():
    # SourcingRecord holds a Product reference; it exposes no shadow fields
    # like `.asin` or `.weight` of its own.
    record = SourcingRecord(record_ref="row_1", product=_product())
    assert not hasattr(record, "asin")
    assert record.product.identification.asin.value == "B0EXAMPLE1"


def test_with_costs_returns_new_instance_and_preserves_original():
    original = SourcingRecord(record_ref="row_1", product=_product())
    costs = CostInputs(cog=Decimal("5"))
    updated = original.with_costs(costs)
    assert original.costs is None  # immutability: original untouched
    assert updated.costs is costs
    assert updated is not original


def test_with_issues_accumulates():
    record = SourcingRecord(record_ref="row_1", product=_product())
    issue1 = ProcessingIssue(level=IssueLevel.WARNING, code="A", message="a")
    issue2 = ProcessingIssue(level=IssueLevel.RECORD_ERROR, code="B", message="b")
    updated = record.with_issues(issue1).with_issues(issue2)
    assert updated.issues == (issue1, issue2)
    assert record.issues == ()  # original untouched


def test_has_record_errors_and_warnings():
    record = SourcingRecord(record_ref="row_1", product=_product())
    with_warning = record.with_issues(ProcessingIssue(level=IssueLevel.WARNING, code="W", message="w"))
    assert with_warning.has_warnings
    assert not with_warning.has_record_errors

    with_error = record.with_issues(ProcessingIssue(level=IssueLevel.RECORD_ERROR, code="E", message="e"))
    assert with_error.has_record_errors
    assert not with_error.has_warnings


def test_with_decision_and_risk_preserve_untouched_fields():
    record = SourcingRecord(record_ref="row_1", product=_product())
    flag = RiskFlag(
        risk_type=RiskType.HAZMAT, status=RiskStatus.PRESENT,
        verification_status=VerificationStatus.VERIFIED,
        severity=Severity.HIGH, source="s", timestamp=NOW,
    )
    decision = DecisionResult(decision=Decision.PASS, reasons=(DecisionReason("X", "x"),), evaluated_at=NOW)
    updated = record.with_risk(RiskProfile(flags=(flag,))).with_decision(decision)

    # product (untouched) must be the exact same object, not rebuilt
    assert updated.product is record.product
    assert updated.risk.flags == (flag,)
    assert updated.decision.decision == Decision.PASS
