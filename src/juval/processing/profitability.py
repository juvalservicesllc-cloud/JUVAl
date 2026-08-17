"""Profitability Engine — deterministic, code-computed financial math.

Nothing in this module ever calls an AI model. Every function here is a pure
function of Decimal inputs (or a thin FieldValue wrapper around one), so the
same inputs always produce the same output — required for reproducibility
and for the "AI never calculates financial values" rule (ADR-006).

Amazon's fee schedule is never hardcoded here: `FeeInputs` is a parameter
supplied by the caller (from an authorized fee source or user input).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from juval.domain.costs import CostInputs, FeeInputs
from juval.domain.provenance import (
    FieldValue,
    SourceType,
    VerificationStatus,
)

_SOURCE = "profitability_engine"


# --------------------------------------------------------------------------
# Pure formulas (Decimal in, Decimal out — no provenance, independently
# testable, and reused by the FieldValue-aware functions below).
# --------------------------------------------------------------------------


def compute_profit(seller_proceeds: Decimal, total_cost: Decimal) -> Decimal:
    return seller_proceeds - total_cost


def compute_roi(profit: Decimal, total_cost: Decimal) -> Decimal:
    if total_cost <= 0:
        raise ZeroDivisionError("ROI is undefined when total_cost <= 0")
    return profit / total_cost


def compute_margin(profit: Decimal, selling_price: Decimal) -> Decimal:
    if selling_price <= 0:
        raise ZeroDivisionError("margin is undefined when selling_price <= 0")
    return profit / selling_price


def compute_break_even_price(
    *, total_cost: Decimal, fulfillment_fee: Decimal, other_selling_fees: Decimal, referral_fee_rate: Decimal
) -> Decimal:
    """Selling price at which profit == 0, holding costs and fee *rate*
    fixed. Assumes the referral fee scales linearly with price (true for
    Amazon's model) while fulfillment/other fees stay flat at this price
    point — the standard simplifying assumption for a break-even quote."""

    denominator = Decimal("1") - referral_fee_rate
    if denominator <= 0:
        raise ValueError("referral_fee_rate must be < 1 to compute a break-even price")
    return (total_cost + fulfillment_fee + other_selling_fees) / denominator


def compute_max_cog_for_target_profit(
    *, seller_proceeds: Decimal, landed_cost_excl_cog: Decimal, target_profit: Decimal
) -> Decimal:
    """Highest COG that still yields at least `target_profit`, holding the
    current selling price (and therefore fees) and non-COG costs fixed."""

    return seller_proceeds - landed_cost_excl_cog - target_profit


def compute_max_cog_for_target_roi(
    *, seller_proceeds: Decimal, landed_cost_excl_cog: Decimal, target_roi: Decimal
) -> Decimal:
    """Highest COG that still yields at least `target_roi`, holding the
    current selling price (and therefore fees) and non-COG costs fixed."""

    denominator = Decimal("1") + target_roi
    if denominator <= 0:
        raise ValueError("target_roi must be > -1")
    return (seller_proceeds - landed_cost_excl_cog * denominator) / denominator


# --------------------------------------------------------------------------
# FieldValue-aware orchestration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProfitabilityResult:
    selling_price: Optional[Decimal]
    total_fees: Optional[Decimal]
    seller_proceeds: Optional[Decimal]
    total_cost: Optional[Decimal]
    profit: FieldValue[Decimal]
    roi: FieldValue[Decimal]
    margin: FieldValue[Decimal]
    break_even_price: FieldValue[Decimal]
    max_cog_target_profit: Optional[FieldValue[Decimal]] = None
    max_cog_target_roi: Optional[FieldValue[Decimal]] = None


def _calculated(value: Decimal, status: VerificationStatus, *, method: str, now: datetime) -> FieldValue[Decimal]:
    if status == VerificationStatus.VERIFIED:
        return FieldValue.verified(value, source=_SOURCE, method=method, retrieved_at=now, source_type=SourceType.CALCULATED)
    if status == VerificationStatus.INFERRED:
        return FieldValue.inferred(value, source=_SOURCE, method=method, retrieved_at=now, source_type=SourceType.CALCULATED)
    raise AssertionError(f"_calculated() called with non-computable status: {status}")


def _not_found(*, method: str, now: datetime, evidence: str) -> FieldValue[Decimal]:
    return FieldValue.not_found(source=_SOURCE, method=method, retrieved_at=now, evidence=evidence)


def compute_profitability(
    *,
    selling_price: FieldValue[Decimal],
    costs: CostInputs,
    fees: FeeInputs,
    weight_lb: Optional[Decimal] = None,
    target_profit: Optional[Decimal] = None,
    target_roi: Optional[Decimal] = None,
    now: datetime,
) -> ProfitabilityResult:
    """Compute the full profitability picture for one selling-price input.

    If `selling_price` is not usable (NOT_FOUND/INVALID), every derived
    field is NOT_FOUND too — a missing input is never silently treated as
    zero or skipped, it propagates (see `combine_verification_status`).
    """

    if not selling_price.is_usable:
        reason = f"selling_price is {selling_price.status.value}; profitability cannot be calculated"
        return ProfitabilityResult(
            selling_price=None,
            total_fees=None,
            seller_proceeds=None,
            total_cost=None,
            profit=_not_found(method="seller_proceeds - total_cost", now=now, evidence=reason),
            roi=_not_found(method="profit / total_cost", now=now, evidence=reason),
            margin=_not_found(method="profit / selling_price", now=now, evidence=reason),
            break_even_price=_not_found(method="break_even_price", now=now, evidence=reason),
        )

    price = selling_price.value
    input_status = selling_price.status  # single input today; combine_verification_status if more join in later
    total_fees = fees.total
    seller_proceeds = price - total_fees
    total_cost = costs.total_landed_cost(weight_lb=weight_lb)
    landed_cost_excl_cog = costs.total_landed_cost_excl_cog(weight_lb=weight_lb)

    profit_value = compute_profit(seller_proceeds, total_cost)
    profit = _calculated(profit_value, input_status, method="seller_proceeds - total_cost", now=now)

    if total_cost > 0:
        roi = _calculated(compute_roi(profit_value, total_cost), input_status, method="profit / total_cost", now=now)
    else:
        roi = _not_found(method="profit / total_cost", now=now, evidence="total_cost is zero or negative; ROI undefined")

    if price > 0:
        margin = _calculated(
            compute_margin(profit_value, price), input_status, method="profit / selling_price", now=now
        )
    else:
        margin = _not_found(method="profit / selling_price", now=now, evidence="selling_price is zero; margin undefined")

    try:
        break_even_value = compute_break_even_price(
            total_cost=total_cost,
            fulfillment_fee=fees.fulfillment_fee,
            other_selling_fees=fees.other_selling_fees,
            referral_fee_rate=fees.referral_fee_rate,
        )
        break_even = _calculated(break_even_value, input_status, method="break_even_price", now=now)
    except ValueError as exc:
        break_even = _not_found(method="break_even_price", now=now, evidence=str(exc))

    max_cog_target_profit = None
    if target_profit is not None:
        value = compute_max_cog_for_target_profit(
            seller_proceeds=seller_proceeds, landed_cost_excl_cog=landed_cost_excl_cog, target_profit=target_profit
        )
        max_cog_target_profit = _calculated(value, input_status, method="max_cog_for_target_profit", now=now)

    max_cog_target_roi = None
    if target_roi is not None:
        try:
            value = compute_max_cog_for_target_roi(
                seller_proceeds=seller_proceeds, landed_cost_excl_cog=landed_cost_excl_cog, target_roi=target_roi
            )
            max_cog_target_roi = _calculated(value, input_status, method="max_cog_for_target_roi", now=now)
        except ValueError as exc:
            max_cog_target_roi = _not_found(method="max_cog_for_target_roi", now=now, evidence=str(exc))

    return ProfitabilityResult(
        selling_price=price,
        total_fees=total_fees,
        seller_proceeds=seller_proceeds,
        total_cost=total_cost,
        profit=profit,
        roi=roi,
        margin=margin,
        break_even_price=break_even,
        max_cog_target_profit=max_cog_target_profit,
        max_cog_target_roi=max_cog_target_roi,
    )
