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

Two legacy sources are read: in-memory CostInputs/FeeInputs, and persisted
record snapshots (application/record_snapshot.py), which keep only `cog` and
`shipping_per_unit`. What a snapshot never stored stays structurally absent;
it is not rebuilt from today's defaults, the runtime record or the importer.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, Mapping, Optional

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


#: Record snapshot key -> FinancialTerm, for the only financial inputs
#: record_to_snapshot persists. total_fees/seller_proceeds/total_cost are
#: calculated results, not terms, and are deliberately not projected.
LEGACY_SNAPSHOT_TERMS: Mapping[str, FinancialTerm] = MappingProxyType({
    "cog": FinancialTerm.COG,
    "shipping_per_unit": FinancialTerm.SHIPPING_PER_UNIT,
})


def _snapshot_decimal(key: str, raw: Any) -> Optional[Decimal]:
    """Parse one persisted slot; parsing is syntax, not accreditation.

    The writer stores str(Decimal) of a non-negative CostInputs value, or None.
    Anything else is corruption and fails loudly: never read as zero, absence
    or NOT_FOUND. The exact round-trip check rejects float-like drift,
    whitespace and signs the writer never produces.
    """
    if raw is None:
        return None
    try:
        value = Decimal(raw) if isinstance(raw, str) else None
    except InvalidOperation:
        value = None
    if value is None or str(value) != raw or value.is_nan() or value < 0:
        raise ValueError(f"Corrupt legacy snapshot {key!r}: {raw!r} is not a persisted Decimal string")
    return value


def legacy_snapshot_financial_operands(
    snapshot: Mapping[str, Any],
) -> dict[FinancialTerm, Optional[Decimal]]:
    """Legacy slots of one persisted record snapshot, keyed by FinancialTerm.

    Only `cog` and `shipping_per_unit` are read; the other 14 terms are
    structurally absent because the snapshot never stored them. Both keys have
    been written since the snapshot format exists, so a snapshot missing
    either is not this contract and is rejected rather than read as absence.
    """
    if not isinstance(snapshot, Mapping):
        raise ValueError(f"Expected a record snapshot mapping, got {type(snapshot).__name__}")
    missing = [key for key in LEGACY_SNAPSHOT_TERMS if key not in snapshot]
    if missing:
        raise ValueError(f"Not a legacy record snapshot: missing {', '.join(missing)}")
    operands: dict[FinancialTerm, Optional[Decimal]] = dict.fromkeys(
        (*LEGACY_COST_TERMS.values(), *LEGACY_FEE_TERMS.values()))
    for key, term in LEGACY_SNAPSHOT_TERMS.items():
        operands[term] = _snapshot_decimal(key, snapshot[key])
    return operands
