"""Format/checksum validation for product identifiers.

Used by the data-quality layer (`processing/data_quality.py`) to decide
whether an identifier FieldValue should be accepted, or flagged INVALID.
This module only checks *shape* (does it look like a real ASIN/UPC/EAN/GTIN?)
— it never confirms a product actually exists; that would require an
authorized external source and belongs to enrichment, not here.
"""

from __future__ import annotations

import re

_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def is_valid_asin(value: str) -> bool:
    """Amazon ASINs are exactly 10 uppercase alphanumeric characters."""

    return bool(_ASIN_RE.fullmatch(value))


def _gs1_check_digit_valid(digits: str) -> bool:
    """Standard GS1 mod-10 check digit, used by UPC-A/EAN-8/EAN-13/GTIN-14.

    Weight alternates 3, 1, 3, 1, ... starting from the digit immediately to
    the left of the check digit (rightmost digit), independent of the total
    length. Verified against published reference codes for UPC-A and EAN-13.
    """

    if not digits.isdigit():
        return False
    total = 0
    check_digit: int | None = None
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i == 0:
            check_digit = d
            continue
        weight = 3 if (i % 2 == 1) else 1
        total += d * weight
    calculated = (10 - (total % 10)) % 10
    return calculated == check_digit


def is_valid_upc(value: str) -> bool:
    """UPC-A: 12 digits with a valid GS1 check digit."""

    return len(value) == 12 and _gs1_check_digit_valid(value)


def is_valid_ean(value: str) -> bool:
    """EAN-8 or EAN-13, with a valid GS1 check digit."""

    return len(value) in (8, 13) and _gs1_check_digit_valid(value)


def is_valid_gtin(value: str) -> bool:
    """GTIN-8/12/13/14, with a valid GS1 check digit."""

    return len(value) in (8, 12, 13, 14) and _gs1_check_digit_valid(value)
