"""Unit normalization for physical quantities.

Canonical units used throughout the domain model:
  * weight     -> pounds ("lb")
  * length     -> inches ("in")
  * volume     -> cubic inches ("in3"), derived from length x width x height

Normalization here is purely mathematical (unit conversion). It is NOT a
business decision and carries no provenance of its own — it operates on the
`.value`/`.unit` of an already-sourced FieldValue; the provenance travels
with the FieldValue unchanged.
"""

from __future__ import annotations

from decimal import Decimal

CANONICAL_WEIGHT_UNIT = "lb"
CANONICAL_LENGTH_UNIT = "in"
CANONICAL_VOLUME_UNIT = "in3"

_WEIGHT_TO_LB: dict[str, Decimal] = {
    "lb": Decimal("1"),
    "lbs": Decimal("1"),
    "pound": Decimal("1"),
    "pounds": Decimal("1"),
    "oz": Decimal("1") / Decimal("16"),
    "ounce": Decimal("1") / Decimal("16"),
    "ounces": Decimal("1") / Decimal("16"),
    "kg": Decimal("2.2046226218"),
    "kilogram": Decimal("2.2046226218"),
    "kilograms": Decimal("2.2046226218"),
    "g": Decimal("0.0022046226"),
    "gram": Decimal("0.0022046226"),
    "grams": Decimal("0.0022046226"),
}

_LENGTH_TO_IN: dict[str, Decimal] = {
    "in": Decimal("1"),
    "inch": Decimal("1"),
    "inches": Decimal("1"),
    "ft": Decimal("12"),
    "foot": Decimal("12"),
    "feet": Decimal("12"),
    "cm": Decimal("0.3937007874"),
    "centimeter": Decimal("0.3937007874"),
    "centimeters": Decimal("0.3937007874"),
    "mm": Decimal("0.0393700787"),
    "millimeter": Decimal("0.0393700787"),
    "millimeters": Decimal("0.0393700787"),
}


class UnsupportedUnitError(ValueError):
    """Raised when a unit string cannot be normalized.

    Deliberately a distinct error type: unit conversion failures are a data
    quality problem (unit -> INVALID), not a generic ValueError to be caught
    incidentally alongside unrelated bugs.
    """


def to_pounds(value: Decimal, unit: str) -> Decimal:
    key = unit.strip().lower()
    if key not in _WEIGHT_TO_LB:
        raise UnsupportedUnitError(f"Unsupported weight unit: {unit!r}")
    return value * _WEIGHT_TO_LB[key]


def to_inches(value: Decimal, unit: str) -> Decimal:
    key = unit.strip().lower()
    if key not in _LENGTH_TO_IN:
        raise UnsupportedUnitError(f"Unsupported length unit: {unit!r}")
    return value * _LENGTH_TO_IN[key]


def cubic_inches(length_in: Decimal, width_in: Decimal, height_in: Decimal) -> Decimal:
    """Volume derived from three already-normalized inch measurements."""

    return length_in * width_in * height_in
