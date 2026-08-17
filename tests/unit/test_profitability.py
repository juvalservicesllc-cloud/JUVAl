from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.domain.costs import CostInputs, FeeInputs
from juval.domain.provenance import FieldValue, VerificationStatus
from juval.processing.profitability import (
    compute_break_even_price,
    compute_margin,
    compute_max_cog_for_target_profit,
    compute_max_cog_for_target_roi,
    compute_profit,
    compute_profitability,
    compute_roi,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_compute_profit():
    assert compute_profit(Decimal("20"), Decimal("12")) == Decimal("8")


def test_compute_roi():
    assert compute_roi(Decimal("8"), Decimal("12")) == Decimal("8") / Decimal("12")


def test_compute_roi_undefined_at_zero_cost():
    with pytest.raises(ZeroDivisionError):
        compute_roi(Decimal("8"), Decimal("0"))


def test_compute_margin():
    assert compute_margin(Decimal("8"), Decimal("20")) == Decimal("0.4")


def test_compute_margin_undefined_at_zero_price():
    with pytest.raises(ZeroDivisionError):
        compute_margin(Decimal("8"), Decimal("0"))


def test_break_even_price_known_case():
    # price*(1-0.15) = 12 + 4 + 0  =>  price = 16 / 0.85
    price = compute_break_even_price(
        total_cost=Decimal("12"), fulfillment_fee=Decimal("4"), other_selling_fees=Decimal("0"),
        referral_fee_rate=Decimal("0.15"),
    )
    assert price == Decimal("16") / Decimal("0.85")


def test_break_even_price_rejects_full_referral_rate():
    with pytest.raises(ValueError):
        compute_break_even_price(
            total_cost=Decimal("12"), fulfillment_fee=Decimal("0"), other_selling_fees=Decimal("0"),
            referral_fee_rate=Decimal("1"),
        )


def test_max_cog_for_target_profit():
    # seller_proceeds=20, landed_excl_cog=3, target_profit=5 => max_cog = 12
    cog = compute_max_cog_for_target_profit(
        seller_proceeds=Decimal("20"), landed_cost_excl_cog=Decimal("3"), target_profit=Decimal("5")
    )
    assert cog == Decimal("12")


def test_max_cog_for_target_roi():
    # cog = (seller_proceeds - landed_excl_cog*(1+roi)) / (1+roi)
    cog = compute_max_cog_for_target_roi(
        seller_proceeds=Decimal("20"), landed_cost_excl_cog=Decimal("2"), target_roi=Decimal("1")
    )
    # denom = 2 ; cog = (20 - 2*2)/2 = 8
    assert cog == Decimal("8")
    # sanity: with that COG, total_cost = 8+2=10, profit = seller_proceeds-total_cost = 20-10=10, roi=10/10=1 ✓


def test_max_cog_for_target_roi_rejects_roi_at_minus_one():
    with pytest.raises(ValueError):
        compute_max_cog_for_target_roi(
            seller_proceeds=Decimal("20"), landed_cost_excl_cog=Decimal("2"), target_roi=Decimal("-1")
        )


def _selling_price(value=Decimal("20"), status="verified"):
    if status == "verified":
        return FieldValue.verified(value, source="s", method="m", retrieved_at=NOW)
    if status == "inferred":
        return FieldValue.inferred(value, source="s", method="m", retrieved_at=NOW)
    return FieldValue.not_found(source="s", method="m", retrieved_at=NOW)


def test_compute_profitability_end_to_end():
    costs = CostInputs(cog=Decimal("8"), prep=Decimal("1"))
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))
    result = compute_profitability(
        selling_price=_selling_price(Decimal("20")), costs=costs, fees=fees, target_profit=Decimal("5"),
        target_roi=Decimal("0.3"), now=NOW,
    )
    # total_fees = 5, seller_proceeds = 15, total_cost = 9, profit = 6
    assert result.total_fees == Decimal("5")
    assert result.seller_proceeds == Decimal("15")
    assert result.total_cost == Decimal("9")
    assert result.profit.value == Decimal("6")
    assert result.profit.status == VerificationStatus.VERIFIED
    assert result.roi.value == Decimal("6") / Decimal("9")
    assert result.margin.value == Decimal("6") / Decimal("20")
    assert result.max_cog_target_profit is not None
    assert result.max_cog_target_roi is not None


def test_compute_profitability_propagates_inferred_status():
    costs = CostInputs(cog=Decimal("8"))
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"))
    result = compute_profitability(
        selling_price=_selling_price(Decimal("20"), status="inferred"), costs=costs, fees=fees, now=NOW
    )
    assert result.profit.status == VerificationStatus.INFERRED


def test_compute_profitability_selling_price_not_found_yields_not_found_everywhere():
    costs = CostInputs(cog=Decimal("8"))
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"))
    result = compute_profitability(
        selling_price=_selling_price(status="not_found"), costs=costs, fees=fees, now=NOW
    )
    assert result.profit.status == VerificationStatus.NOT_FOUND
    assert result.roi.status == VerificationStatus.NOT_FOUND
    assert result.margin.status == VerificationStatus.NOT_FOUND
    assert result.break_even_price.status == VerificationStatus.NOT_FOUND
    assert result.selling_price is None


def test_compute_profitability_zero_cost_yields_not_found_roi_not_a_crash():
    costs = CostInputs(cog=Decimal("0"))
    fees = FeeInputs(referral_fee=Decimal("0"), referral_fee_rate=Decimal("0"))
    result = compute_profitability(selling_price=_selling_price(Decimal("0.0001")), costs=costs, fees=fees, now=NOW)
    assert result.roi.status == VerificationStatus.NOT_FOUND
