"""Synthetic fixtures only: no fee schedule, supplier or Amazon data."""
import ast
import copy
import pathlib
from decimal import Decimal

import pytest

from juval.domain import financial_fees as module
from juval.domain.financial_evidence import (
    Applicability, DeclaredSellingPrice, FinancialDependency, FinancialTermEvidence,
)
from juval.domain.financial_fees import FEE_TERMS, FeeEvidenceState as S, accredited_fee_evidence
from juval.domain.provenance import FieldValue, SourceType

from .test_financial_dependencies import CONTEXT, FULL, INV, I, NF, NOW, T, V, evidence, fv, term


def states(ev):
    return {item.term: item.state for item in accredited_fee_evidence(ev)}


def sourced(value, unit, source_type, status=V):
    build = FieldValue.verified if status is V else FieldValue.inferred
    return build(value, unit=unit, source="synthetic", method="m", retrieved_at=NOW, source_type=source_type)


# -- Fee evidence classification ------------------------------------------------

def test_supplier_declared_fees_are_declared_not_observed():
    assert states(evidence(*FULL)) == {T.REFERRAL_FEE: S.DECLARED, T.FULFILLMENT_FEE: S.DECLARED,
                                       T.OTHER_SELLING_FEES: S.STRUCTURALLY_ABSENT,
                                       T.REFERRAL_FEE_RATE: S.DECLARED}


def test_each_fee_state_is_kept_distinct():
    ev = evidence(term(T.REFERRAL_FEE, "x", status=NF), term(T.FULFILLMENT_FEE, "x", status=INV),
                  term(T.OTHER_SELLING_FEES, None, applies=False), term(T.REFERRAL_FEE_RATE, "0.15", status=I),
                  required=(T.COG,))
    assert states(ev) == {T.REFERRAL_FEE: S.NOT_FOUND, T.FULFILLMENT_FEE: S.INVALID,
                          T.OTHER_SELLING_FEES: S.EXCLUDED, T.REFERRAL_FEE_RATE: S.INFERRED}
    by_term = {item.term: item for item in accredited_fee_evidence(ev)}
    assert by_term[T.OTHER_SELLING_FEES].evidence.amount is None  # exclusion is not a zero
    assert not by_term[T.OTHER_SELLING_FEES].usable and by_term[T.REFERRAL_FEE_RATE].usable


def test_unresolved_applicability_and_absent_amount():
    ev = evidence(term(T.REFERRAL_FEE, "3.00", applies_status=NF), term(T.FULFILLMENT_FEE, None),
                  required=(T.COG,))
    assert states(ev)[T.REFERRAL_FEE] is S.APPLICABILITY_UNRESOLVED
    assert states(ev)[T.FULFILLMENT_FEE] is S.AMOUNT_ABSENT


def test_explicit_zero_fee_is_declared_not_excluded():
    item = accredited_fee_evidence(evidence(term(T.FULFILLMENT_FEE, "0"), required=(T.COG,)))[1]
    assert item.state is S.DECLARED and item.evidence.amount.value == Decimal("0")


def test_observed_fee_needs_an_authorized_source():
    observed = FinancialTermEvidence(T.FULFILLMENT_FEE, term(T.FULFILLMENT_FEE).applicability, CONTEXT,
                                     sourced(Decimal("3.20"), "USD", SourceType.OFFICIAL_API))
    assert states(evidence(observed, required=(T.COG,)))[T.FULFILLMENT_FEE] is S.OBSERVED


def test_derived_fee_must_declare_its_dependencies():
    derived = sourced(Decimal("3.00"), "USD", SourceType.CALCULATED)
    with pytest.raises(ValueError, match="must declare what it depends on"):
        FinancialTermEvidence(T.REFERRAL_FEE, term(T.REFERRAL_FEE).applicability, CONTEXT, derived)
    linked = FinancialTermEvidence(
        T.REFERRAL_FEE, term(T.REFERRAL_FEE).applicability, CONTEXT, derived,
        depends_on=(FinancialDependency("fixture:rate", "rate used", T.REFERRAL_FEE_RATE),))
    ev = evidence(linked, term(T.REFERRAL_FEE_RATE, "0.15"), required=(T.COG,))
    assert states(ev)[T.REFERRAL_FEE] is S.DERIVED


def test_verified_fee_without_an_accrediting_origin_is_refused():
    anonymous = FinancialTermEvidence(T.FULFILLMENT_FEE, term(T.FULFILLMENT_FEE).applicability, CONTEXT,
                                      sourced(Decimal("3.20"), "USD", SourceType.DATABASE))
    with pytest.raises(ValueError, match="accredits no fee origin"):
        accredited_fee_evidence(evidence(anonymous, required=(T.COG,)))


def test_ai_analysis_never_produces_financial_amounts_or_applicability():
    with pytest.raises(ValueError, match="AI_ANALYSIS"):
        FinancialTermEvidence(T.FULFILLMENT_FEE, term(T.FULFILLMENT_FEE).applicability, CONTEXT,
                              sourced(Decimal("3.20"), "USD", SourceType.AI_ANALYSIS))
    with pytest.raises(ValueError, match="AI_ANALYSIS"):
        Applicability(sourced(True, None, SourceType.AI_ANALYSIS), "synthetic")


def test_referral_fee_and_rate_stay_independent():
    only_rate = states(evidence(term(T.REFERRAL_FEE_RATE, "0.15"), required=(T.COG,)))
    assert only_rate[T.REFERRAL_FEE] is S.STRUCTURALLY_ABSENT  # never derived from the rate
    only_fee = states(evidence(term(T.REFERRAL_FEE, "3.00"), required=(T.COG,)))
    assert only_fee[T.REFERRAL_FEE_RATE] is S.STRUCTURALLY_ABSENT  # never derived from the fee


def test_fee_view_is_deterministic_pure_and_computes_nothing():
    ev = evidence(*FULL)
    before = copy.deepcopy(ev)
    assert accredited_fee_evidence(ev) == accredited_fee_evidence(ev)
    assert ev == before
    assert [item.term for item in accredited_fee_evidence(ev)] == list(FEE_TERMS)
    assert accredited_fee_evidence(ev)[0].evidence is ev.evidence_for(T.REFERRAL_FEE)
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported == {"__future__", "dataclasses", "enum", "typing", "financial_evidence", "provenance"}
    with pytest.raises(ValueError):
        accredited_fee_evidence("not a set")


# -- Declared selling price ----------------------------------------------------

def test_declared_price_keeps_its_own_currency_context_and_status():
    for status in (V, I):
        price = DeclaredSellingPrice(fv(Decimal("19.99"), "USD", status), CONTEXT)
        assert (price.amount.unit, price.amount.status, price.context) == ("USD", status, CONTEXT)
    for status in (NF, INV):
        assert not DeclaredSellingPrice(fv("x", status=status), CONTEXT).amount.is_usable


@pytest.mark.parametrize("amount", [
    fv(Decimal("19.99")),                   # no currency
    fv(Decimal("19.99"), "usd"), fv(Decimal("19.99"), "USD/lb"), fv(Decimal("19.99"), "ratio"),
    fv(Decimal("-1"), "USD"), fv(Decimal("NaN"), "USD"), fv(Decimal("Infinity"), "USD"),
    Decimal("19.99"),
])
def test_declared_price_rejects_missing_or_incompatible_currency_and_bad_values(amount):
    with pytest.raises(ValueError):
        DeclaredSellingPrice(amount, CONTEXT)


def test_declared_price_requires_effective_context():
    with pytest.raises(ValueError):
        DeclaredSellingPrice(fv(Decimal("19.99"), "USD"), None)
