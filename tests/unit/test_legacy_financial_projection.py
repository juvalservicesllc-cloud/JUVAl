"""Synthetic legacy fixtures only: real CostInputs/FeeInputs types, no provider data."""
import dataclasses
import sys
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.application import legacy_financial_projection as projection
from juval.application.legacy_financial_projection import (
    LEGACY_COST_TERMS, LEGACY_FEE_TERMS, legacy_financial_operands,
)
from juval.domain.costs import CostInputs, FeeInputs
from juval.domain.financial_evidence import (
    FinancialEvidenceSet, FinancialTerm, FinancialTermEvidence, LegacyGap,
    assess_legacy_financial_operands,
)
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus

NOW = datetime(2026, 2, 3, tzinfo=timezone.utc)
COSTS = CostInputs(cog=Decimal("4.50"), shipping_per_unit=Decimal("0.80"))
FEES = FeeInputs(referral_fee=Decimal("1.50"), referral_fee_rate=Decimal("0.15"))


def test_mapping_covers_every_legacy_field_and_every_term_exactly_once():
    assert set(LEGACY_COST_TERMS) == {f.name for f in dataclasses.fields(CostInputs)}
    assert set(LEGACY_FEE_TERMS) == {f.name for f in dataclasses.fields(FeeInputs)}
    terms = [*LEGACY_COST_TERMS.values(), *LEGACY_FEE_TERMS.values()]
    assert sorted(terms, key=lambda t: t.value) == sorted(FinancialTerm, key=lambda t: t.value)
    with pytest.raises(TypeError):
        LEGACY_COST_TERMS["cog"] = FinancialTerm.VAT


def test_cost_and_fee_slots_are_projected_exactly_as_stored():
    operands = legacy_financial_operands(COSTS, FEES)
    for name, term in {**LEGACY_COST_TERMS, **LEGACY_FEE_TERMS}.items():
        legacy = COSTS if name in LEGACY_COST_TERMS else FEES
        assert operands[term] is getattr(legacy, name)
        assert type(operands[term]) is Decimal  # no FieldValue, no provenance added


def test_default_zero_stays_indistinguishable_from_default():
    report = assess_legacy_financial_operands(legacy_financial_operands(COSTS, FEES))
    for term in (FinancialTerm.VAT, FinancialTerm.STORAGE, FinancialTerm.FULFILLMENT_FEE,
                 FinancialTerm.OTHER_SELLING_FEES):
        entry = report.gap_for(term)
        assert entry.represented and not entry.satisfies_contract
        assert {LegacyGap.NO_PROVENANCE, LegacyGap.ZERO_INDISTINGUISHABLE_FROM_DEFAULT,
                LegacyGap.APPLICABILITY_UNRESOLVED} <= set(entry.gaps)
    assert LegacyGap.ZERO_INDISTINGUISHABLE_FROM_DEFAULT not in report.gap_for(FinancialTerm.COG).gaps


@pytest.mark.parametrize("costs,fees,absent", [
    (None, FEES, set(LEGACY_COST_TERMS.values())),
    (COSTS, None, set(LEGACY_FEE_TERMS.values())),
    (None, None, set(FinancialTerm)),
])
def test_missing_legacy_object_is_structural_absence_not_zero(costs, fees, absent):
    operands = legacy_financial_operands(costs, fees)
    assert {term for term, value in operands.items() if value is None} == absent
    report = assess_legacy_financial_operands(operands)
    for entry in report.terms:
        if entry.term in absent:
            assert entry.gaps == (LegacyGap.STRUCTURALLY_ABSENT,) and not entry.represented
        else:
            assert entry.represented


def test_every_projected_slot_fails_the_contract_and_order_is_stable():
    report = assess_legacy_financial_operands(legacy_financial_operands(COSTS, FEES))
    assert not report.satisfies_contract
    assert [entry.term.value for entry in report.terms] == sorted(t.value for t in FinancialTerm)
    assert all(entry.represented for entry in report.terms)


def test_field_value_operands_keep_status_and_represented_is_not_usable():
    # CostInputs/FeeInputs hold only bare Decimals; a FieldValue slot is the
    # domain assessment's concern and keeps its own status unpromoted.
    common = dict(source="synthetic-supplier-file", source_type=SourceType.SUPPLIER_FILE,
                  retrieved_at=NOW, method="synthetic supplier column")
    verified = FieldValue.verified(Decimal("4.50"), unit="USD", **common)
    missing = FieldValue.not_found(**common)
    operands = {**legacy_financial_operands(COSTS, FEES),
                FinancialTerm.COG: verified, FinancialTerm.PREP: missing}
    report = assess_legacy_financial_operands(operands)
    assert report.gap_for(FinancialTerm.PREP).represented and not missing.is_usable
    assert not report.gap_for(FinancialTerm.COG).satisfies_contract
    assert (verified.status, verified.provenance.source_type) == (
        VerificationStatus.VERIFIED, SourceType.SUPPLIER_FILE)
    assert missing.status is VerificationStatus.NOT_FOUND


def test_projection_creates_no_evidence_price_observation_or_mutation():
    before = (dataclasses.replace(COSTS), dataclasses.replace(FEES))
    operands = legacy_financial_operands(COSTS, FEES)
    report = assess_legacy_financial_operands(operands)
    assert (COSTS, FEES) == before
    values = [*operands.values(), *(g for e in report.terms for g in e.gaps)]
    assert not any(isinstance(v, (FieldValue, FinancialTermEvidence, FinancialEvidenceSet))
                   for v in values)
    module_names = set(vars(projection))
    assert not {"PriceObservation", "FinancialTermEvidence", "FinancialEvidenceSet",
                "FieldValue", "Provenance"} & module_names
    assert "juval.domain.market_evidence" not in {
        getattr(v, "__module__", None) for v in vars(projection).values()}


def test_projection_and_assessment_are_deterministic():
    first = legacy_financial_operands(COSTS, FEES)
    assert first == legacy_financial_operands(COSTS, FEES)
    assert list(first) == list(legacy_financial_operands(COSTS, FEES))
    assert assess_legacy_financial_operands(first) == assess_legacy_financial_operands(
        legacy_financial_operands(COSTS, FEES))


@pytest.mark.parametrize("costs,fees", [(FEES, None), (None, COSTS), ({"cog": Decimal("1")}, None)])
def test_projection_rejects_swapped_or_untyped_legacy_objects(costs, fees):
    with pytest.raises(ValueError):
        legacy_financial_operands(costs, fees)
