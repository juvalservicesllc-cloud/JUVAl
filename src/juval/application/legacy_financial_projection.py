"""Read-only projection of legacy financial operands (ADR-047 §20, §22 step 2).

Maps the numeric slots of the legacy CostInputs/FeeInputs contracts to their
FinancialTerm so domain.financial_evidence.assess_legacy_financial_operands
can report why they do not satisfy ADR-047. The mapping declares which legacy
slot corresponds to which term, never that its value is accredited: values
pass through exactly as stored, including Decimal("0") defaults, and no
provenance, applicability, currency, effective context or allocation is added.

This is the LEGACY diagnostic path only. It is not how new imports capture
financial evidence, and nothing here builds FinancialTermEvidence, a
FinancialEvidenceSet or a price observation. The selling price has no
FinancialTerm (ADR-047 §9) and is deliberately not projected.
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from typing import Mapping, Optional

from juval.domain.costs import CostInputs, FeeInputs
from juval.domain.financial_evidence import FinancialTerm

#: CostInputs field -> the FinancialTerm slot it corresponds to.
LEGACY_COST_TERMS: Mapping[str, FinancialTerm] = MappingProxyType({
    "cog": FinancialTerm.COG,
    "vat": FinancialTerm.VAT,
    "inbound_shipping": FinancialTerm.INBOUND_SHIPPING,
    "shipping_per_unit": FinancialTerm.SHIPPING_PER_UNIT,
    "shipping_per_pound": FinancialTerm.SHIPPING_PER_POUND,
    "prep": FinancialTerm.PREP,
    "labeling": FinancialTerm.LABELING,
    "fragile_prep": FinancialTerm.FRAGILE_PREP,
    "storage": FinancialTerm.STORAGE,
    "inbound_placement": FinancialTerm.INBOUND_PLACEMENT,
    "taxes": FinancialTerm.TAXES,
    "other_costs": FinancialTerm.OTHER_COSTS,
})

#: FeeInputs field -> the FinancialTerm slot it corresponds to.
LEGACY_FEE_TERMS: Mapping[str, FinancialTerm] = MappingProxyType({
    "referral_fee": FinancialTerm.REFERRAL_FEE,
    "referral_fee_rate": FinancialTerm.REFERRAL_FEE_RATE,
    "fulfillment_fee": FinancialTerm.FULFILLMENT_FEE,
    "other_selling_fees": FinancialTerm.OTHER_SELLING_FEES,
})


def legacy_financial_operands(
    costs: Optional[CostInputs], fees: Optional[FeeInputs]
) -> dict[FinancialTerm, Optional[Decimal]]:
    """Legacy slots keyed by FinancialTerm, values exactly as stored.

    A missing CostInputs/FeeInputs leaves its terms None (structural absence),
    never zero. `fees` is whichever FeeInputs the caller actually used — the
    pipeline may take it from a batch argument rather than record.fees — so
    the choice stays with the caller instead of being guessed here.
    """
    operands: dict[FinancialTerm, Optional[Decimal]] = {}
    for legacy, terms, kind in ((costs, LEGACY_COST_TERMS, CostInputs),
                                (fees, LEGACY_FEE_TERMS, FeeInputs)):
        if legacy is not None and not isinstance(legacy, kind):
            raise ValueError(f"Expected {kind.__name__} or None, got {type(legacy).__name__}")
        for name, term in terms.items():
            operands[term] = getattr(legacy, name) if legacy is not None else None
    return operands
