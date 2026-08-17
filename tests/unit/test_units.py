from decimal import Decimal

import pytest

from juval.domain.units import UnsupportedUnitError, cubic_inches, to_inches, to_pounds


def test_to_pounds_identity():
    assert to_pounds(Decimal("10"), "lb") == Decimal("10")


def test_to_pounds_from_kg():
    result = to_pounds(Decimal("1"), "kg")
    assert abs(result - Decimal("2.2046226218")) < Decimal("0.0000001")


def test_to_pounds_from_ounces():
    result = to_pounds(Decimal("16"), "oz")
    assert result == Decimal("1")


def test_to_pounds_unit_is_case_and_whitespace_insensitive():
    assert to_pounds(Decimal("1"), " KG ") == to_pounds(Decimal("1"), "kg")


def test_to_pounds_rejects_unsupported_unit():
    with pytest.raises(UnsupportedUnitError):
        to_pounds(Decimal("1"), "stone")


def test_to_inches_from_cm():
    result = to_inches(Decimal("2.54"), "cm")
    assert abs(result - Decimal("1")) < Decimal("0.0001")


def test_to_inches_from_feet():
    assert to_inches(Decimal("1"), "ft") == Decimal("12")


def test_to_inches_rejects_unsupported_unit():
    with pytest.raises(UnsupportedUnitError):
        to_inches(Decimal("1"), "furlong")


def test_cubic_inches():
    assert cubic_inches(Decimal("2"), Decimal("3"), Decimal("4")) == Decimal("24")
