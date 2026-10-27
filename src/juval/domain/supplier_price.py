"""Supplier suggested price declared in an input file (ADR-053, GOLDEN 17).

Evidence only: it lives on `SourcingRecord.supplier_suggested_price`, outside
`Product`, and nothing in `processing/` reads it. It is not a selling price, not
a cost (COG) and not an ADR-046 `PriceObservation`: no `PriceKind` means
"suggested resale price", and the file declares neither `observed_at` nor a
`price_basis`. A usable amount is INFERRED by construction -- appearing in a
file does not verify it -- and its `unit` is the declared currency.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .provenance import FieldValue, VerificationStatus


def is_currency_code(value: object) -> bool:
    """Three uppercase ASCII letters (ADR-046 §12): checks form, not ISO 4217 membership."""
    return isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper()


@dataclass(frozen=True)
class PriceDiagnostic:
    """Why a declared suggested price is not usable."""

    code: str
    message: str
    row: int
    column: Optional[str] = None      # original header of the failing cell
    raw_value: Optional[str] = None   # the cell as received, text form

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("PriceDiagnostic requires a code and a message")


@dataclass(frozen=True)
class SupplierSuggestedPrice:
    amount: FieldValue[Decimal]
    currency_raw: Optional[str] = None   # the currency cell as received, whatever it held
    diagnostics: tuple[PriceDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        status = self.amount.status
        if status == VerificationStatus.VERIFIED:
            raise ValueError("a declared suggested price is never VERIFIED (ADR-053 S2)")
        if status == VerificationStatus.INFERRED:
            value = self.amount.value
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError("a usable suggested price is a finite Decimal > 0")
            if not is_currency_code(self.amount.unit):
                raise ValueError("a usable suggested price carries its declared currency as unit")
            if self.diagnostics:
                raise ValueError("a usable suggested price carries no diagnostics")
        elif self.amount.unit is not None:
            raise ValueError("an unusable suggested price carries no currency unit")
