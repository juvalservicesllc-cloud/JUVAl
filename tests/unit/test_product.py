from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.domain.product import Dimensions, Identification, Price, SellingPriceSource
from juval.domain.provenance import FieldValue

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_dimensions_accepts_canonical_units():
    weight = FieldValue.verified(Decimal("2.5"), source="s", method="m", retrieved_at=NOW, unit="lb")
    Dimensions(weight=weight)  # should not raise


def test_dimensions_rejects_non_canonical_weight_unit():
    weight = FieldValue.verified(Decimal("2.5"), source="s", method="m", retrieved_at=NOW, unit="kg")
    with pytest.raises(ValueError):
        Dimensions(weight=weight)


def test_dimensions_rejects_non_canonical_length_unit():
    height = FieldValue.verified(Decimal("5"), source="s", method="m", retrieved_at=NOW, unit="cm")
    with pytest.raises(ValueError):
        Dimensions(height=height)


def test_dimensions_allows_not_found_without_unit():
    weight = FieldValue.not_found(source="s", method="m", retrieved_at=NOW)
    Dimensions(weight=weight)  # should not raise


def test_identification_requires_marketplace():
    asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    with pytest.raises(ValueError):
        Identification(asin=asin, marketplace="")


def test_price_requires_source_when_selling_price_used_is_set():
    price_fv = FieldValue.verified(Decimal("19.99"), source="s", method="m", retrieved_at=NOW)
    with pytest.raises(ValueError):
        Price(selling_price_used=price_fv)  # selling_price_source left at NOT_FOUND


def test_price_requires_selling_price_used_when_source_is_declared():
    with pytest.raises(ValueError):
        Price(selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)


def test_price_consistent_pair_is_accepted():
    price_fv = FieldValue.verified(Decimal("19.99"), source="s", method="m", retrieved_at=NOW)
    price = Price(selling_price_used=price_fv, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)
    assert price.selling_price_used.value == Decimal("19.99")
