from decimal import Decimal

import pytest

from juval.domain.costs import CostInputs, FeeInputs


def test_cost_inputs_total_landed_cost_excl_cog():
    costs = CostInputs(cog=Decimal("5"), vat=Decimal("1"), prep=Decimal("0.5"), storage=Decimal("0.25"))
    assert costs.total_landed_cost_excl_cog() == Decimal("1.75")
    assert costs.total_landed_cost() == Decimal("6.75")


def test_cost_inputs_weight_based_shipping():
    costs = CostInputs(cog=Decimal("5"), shipping_per_pound=Decimal("0.5"))
    assert costs.total_landed_cost_excl_cog(weight_lb=Decimal("4")) == Decimal("2.0")


def test_cost_inputs_rejects_negative_values():
    with pytest.raises(ValueError):
        CostInputs(cog=Decimal("-1"))


def test_fee_inputs_total():
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("4"))
    assert fees.total == Decimal("7")


def test_fee_inputs_rejects_rate_of_one_or_more():
    with pytest.raises(ValueError):
        FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("1"))


def test_fee_inputs_rejects_negative_fee():
    with pytest.raises(ValueError):
        FeeInputs(referral_fee=Decimal("-1"), referral_fee_rate=Decimal("0.15"))
