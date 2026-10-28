from datetime import datetime, timedelta, timezone
from decimal import Decimal

from juval.domain.product import Competition, Dimensions, Identification, Price, SellingPriceSource
from juval.domain.provenance import FieldValue, SourceType
from juval.domain.costs import CostInputs, FeeInputs
from juval.processing.data_quality import (
    DataQualityConfig,
    validate_competition_consistency,
    validate_dimensions,
    validate_financial_consistency,
    validate_freshness,
    validate_identification,
    validate_price,
    validate_source,
)
from juval.processing.profitability import compute_profitability

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _fv(value, **kwargs):
    return FieldValue.verified(value, source=kwargs.pop("source", "s"), method="m", retrieved_at=NOW, **kwargs)


def test_validate_identification_flags_verified_but_malformed_asin():
    ident = Identification(asin=_fv("not-an-asin"), marketplace="US")
    issues = validate_identification(ident)
    assert any(i.code == "INVALID_ASIN_FORMAT" for i in issues)


def test_validate_identification_accepts_well_formed_asin():
    ident = Identification(asin=_fv("B0EXAMPLE1"), marketplace="US")
    assert validate_identification(ident) == []


def test_validate_dimensions_flags_zero_weight():
    dims = Dimensions(weight=_fv(Decimal("0"), unit="lb"))
    issues = validate_dimensions(dims)
    assert any(i.code == "IMPOSSIBLE_WEIGHT" for i in issues)


def test_validate_dimensions_flags_absurd_weight_as_warning():
    dims = Dimensions(weight=_fv(Decimal("99999"), unit="lb"))
    issues = validate_dimensions(dims, config=DataQualityConfig(max_reasonable_weight_lb=Decimal("500")))
    assert any(i.code == "WEIGHT_EXCEEDS_SANITY_BOUND" for i in issues)


def test_validate_dimensions_accepts_reasonable_weight():
    dims = Dimensions(weight=_fv(Decimal("2.5"), unit="lb"))
    assert validate_dimensions(dims) == []


def test_validate_price_flags_negative_price():
    price = Price(
        selling_price_used=_fv(Decimal("-5")), selling_price_source=SellingPriceSource.CURRENT_BUY_BOX
    )
    issues = validate_price(price)
    assert any(i.code == "NEGATIVE_PRICE" for i in issues)


def test_validate_price_accepts_positive_price():
    price = Price(
        selling_price_used=_fv(Decimal("19.99")), selling_price_source=SellingPriceSource.CURRENT_BUY_BOX
    )
    assert validate_price(price) == []


def test_validate_financial_consistency_detects_tampered_profit():
    costs = CostInputs(cog=Decimal("8"))
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"))
    result = compute_profitability(selling_price=_fv(Decimal("20")), costs=costs, fees=fees, now=NOW)
    import dataclasses

    tampered_profit = dataclasses.replace(result.profit, value=Decimal("999"))
    tampered = dataclasses.replace(result, profit=tampered_profit)
    issues = validate_financial_consistency(tampered)
    assert any(i.code == "PROFIT_INCONSISTENT" for i in issues)


def test_validate_financial_consistency_accepts_correct_result():
    costs = CostInputs(cog=Decimal("8"))
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"))
    result = compute_profitability(selling_price=_fv(Decimal("20")), costs=costs, fees=fees, now=NOW)
    assert validate_financial_consistency(result) == []


def test_validate_competition_consistency_detects_contradiction():
    competition = Competition(
        total_offers=_fv(0),
        amazon_in_buy_box=_fv(True),
    )
    issues = validate_competition_consistency(competition)
    assert any(i.code == "CONTRADICTORY_BUY_BOX_DATA" for i in issues)


def test_validate_competition_consistency_detects_eligible_exceeding_total():
    competition = Competition(
        total_offers=_fv(3),
        buy_box_eligible_fba=_fv(2),
        buy_box_eligible_fbm=_fv(2),
    )
    issues = validate_competition_consistency(competition)
    assert any(i.code == "CONTRADICTORY_OFFER_COUNTS" for i in issues)


def test_validate_freshness_flags_stale_data():
    old = FieldValue.verified(Decimal("1"), source="s", method="m", retrieved_at=NOW - timedelta(days=60))
    issues = validate_freshness(old, field_name="weight", now=NOW)
    assert any(i.code == "STALE_DATA" for i in issues)


def test_validate_freshness_accepts_recent_data():
    recent = FieldValue.verified(Decimal("1"), source="s", method="m", retrieved_at=NOW - timedelta(days=1))
    assert validate_freshness(recent, field_name="weight", now=NOW) == []


def test_validate_source_flags_placeholder_source():
    fv = FieldValue.verified(Decimal("1"), source="unknown", method="m", retrieved_at=NOW)
    issues = validate_source(fv, field_name="weight")
    assert any(i.code == "UNKNOWN_SOURCE" for i in issues)


def test_validate_source_accepts_real_source():
    fv = FieldValue.verified(Decimal("1"), source="keepa_api", method="m", retrieved_at=NOW)
    assert validate_source(fv, field_name="weight") == []


# -- one issue per logical price (selling_price_used is a copy of its source) -------

def _negative_codes(price):
    return [(i.code, i.field) for i in validate_price(price, record_ref="row_2") if i.code == "NEGATIVE_PRICE"]


def test_a_negative_price_used_as_its_own_source_is_reported_once():
    same = _fv(Decimal("-5"))
    price = Price(current_buy_box=same, selling_price_used=same, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)

    issues = validate_price(price, record_ref="row_2")
    assert [(i.code, i.field, i.level.value) for i in issues] == [("NEGATIVE_PRICE", "selling_price_used", "RECORD_ERROR")]
    assert issues[0].record_ref == "row_2" and "-5" in issues[0].message


def test_an_equal_copy_is_recognised_for_every_declared_source():
    fields = {
        SellingPriceSource.CURRENT_BUY_BOX: "current_buy_box", SellingPriceSource.AVERAGE_BUY_BOX_30D: "average_buy_box_30d",
        SellingPriceSource.AVERAGE_BUY_BOX_90D: "average_buy_box_90d", SellingPriceSource.AVERAGE_BUY_BOX_180D: "average_buy_box_180d",
        SellingPriceSource.MIN_FBA: "min_fba_price", SellingPriceSource.MIN_FBM: "min_fbm_price",
    }
    for source, field in fields.items():
        same = _fv(Decimal("-1"))
        assert _negative_codes(Price(**{field: same}, selling_price_used=same, selling_price_source=source)) == [
            ("NEGATIVE_PRICE", "selling_price_used")], source


def test_independent_negative_prices_are_each_reported():
    # current_buy_box is a different datum from the MIN_FBA price used: two problems.
    used = _fv(Decimal("-3"), source="other")
    price = Price(current_buy_box=_fv(Decimal("-5")), min_fba_price=used, selling_price_used=used,
                  selling_price_source=SellingPriceSource.MIN_FBA)

    assert _negative_codes(price) == [("NEGATIVE_PRICE", "current_buy_box"), ("NEGATIVE_PRICE", "selling_price_used")]


def test_a_used_price_that_differs_from_its_declared_source_is_not_merged():
    # Same declared source but a different value (or provenance): both are checked.
    price = Price(current_buy_box=_fv(Decimal("-5")), selling_price_used=_fv(Decimal("-5"), source="elsewhere"),
                  selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)

    assert _negative_codes(price) == [("NEGATIVE_PRICE", "current_buy_box"), ("NEGATIVE_PRICE", "selling_price_used")]


def test_a_negative_source_is_still_reported_when_the_used_price_is_fine():
    price = Price(current_buy_box=_fv(Decimal("-5")), min_fba_price=_fv(Decimal("12")), selling_price_used=_fv(Decimal("12")),
                  selling_price_source=SellingPriceSource.MIN_FBA)

    assert _negative_codes(price) == [("NEGATIVE_PRICE", "current_buy_box")]


def test_zero_unusable_and_missing_prices_raise_no_negative_issue():
    zero = _fv(Decimal("0"))
    invalid = FieldValue.invalid("abc", source="s", method="m", retrieved_at=NOW, source_type=SourceType.SUPPLIER_FILE)
    missing = FieldValue.not_found(source="s", method="m", retrieved_at=NOW)
    assert validate_price(Price(current_buy_box=zero, selling_price_used=zero, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)) == []
    assert validate_price(Price(current_buy_box=invalid, selling_price_used=invalid, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)) == []
    assert validate_price(Price(current_buy_box=missing)) == []
    assert validate_price(Price()) == []
