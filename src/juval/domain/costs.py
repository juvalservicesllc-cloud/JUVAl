"""Cost and fee inputs for the Profitability Engine.

Every value here is a configurable INPUT supplied by the caller (user
config, supplier file, or an authorized fee source) — never a constant
baked into Juval's source code. Amazon's fee schedule and a seller's own
cost structure both change over time and by category/size-tier; hardcoding
either would go stale silently and violates the project's "no hardcoded
commercial thresholds" rule.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class CostInputs:
    """Per-unit landed cost inputs, excluding Amazon selling fees (see
    FeeInputs). A field left at its Decimal('0') default means "not
    applicable to this product", not "unknown" — if a cost is genuinely
    unknown, don't fabricate a CostInputs; raise a data-quality issue
    instead (see processing/data_quality.py).
    """

    cog: Decimal
    vat: Decimal = Decimal("0")
    inbound_shipping: Decimal = Decimal("0")
    shipping_per_unit: Decimal = Decimal("0")
    shipping_per_pound: Decimal = Decimal("0")
    prep: Decimal = Decimal("0")
    labeling: Decimal = Decimal("0")
    fragile_prep: Decimal = Decimal("0")
    storage: Decimal = Decimal("0")
    inbound_placement: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    other_costs: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if value < 0:
                raise ValueError(f"CostInputs.{f.name} must not be negative, got {value}")

    def total_landed_cost_excl_cog(self, *, weight_lb: Optional[Decimal] = None) -> Decimal:
        weight_component = self.shipping_per_pound * weight_lb if weight_lb is not None else Decimal("0")
        return (
            self.vat
            + self.inbound_shipping
            + self.shipping_per_unit
            + weight_component
            + self.prep
            + self.labeling
            + self.fragile_prep
            + self.storage
            + self.inbound_placement
            + self.taxes
            + self.other_costs
        )

    def total_landed_cost(self, *, weight_lb: Optional[Decimal] = None) -> Decimal:
        return self.cog + self.total_landed_cost_excl_cog(weight_lb=weight_lb)


@dataclass(frozen=True)
class FeeInputs:
    """Amazon selling fees applicable to one offer at a specific price.

    referral_fee_rate is carried alongside the absolute referral_fee so the
    Profitability Engine can recompute break-even price (which requires the
    *rate*, since referral fee scales with selling price) without ever
    guessing a category's rate itself.
    """

    referral_fee: Decimal
    referral_fee_rate: Decimal
    fulfillment_fee: Decimal = Decimal("0")
    other_selling_fees: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name in ("referral_fee", "fulfillment_fee", "other_selling_fees"):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"FeeInputs.{name} must not be negative, got {value}")
        if not (Decimal("0") <= self.referral_fee_rate < Decimal("1")):
            raise ValueError(
                f"FeeInputs.referral_fee_rate must be within [0, 1), got {self.referral_fee_rate}"
            )

    @property
    def total(self) -> Decimal:
        return self.referral_fee + self.fulfillment_fee + self.other_selling_fees
