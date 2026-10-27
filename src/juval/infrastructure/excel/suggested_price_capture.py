"""Supplier suggested price from one file row (ADR-053, GOLDEN 17).

Reads only `supplier_suggested_price` and `supplier_suggested_price_currency`
and returns evidence for `SourcingRecord.supplier_suggested_price`. It never
touches `Product`, `CostInputs` or anything a decision reads. Nothing is
repaired: no currency is inferred, no symbol is parsed, no case is changed and
no amount is rounded -- a problem leaves the raw cells and a diagnostic.

The file is delivered by whoever calls the API or the CLI; who wrote the
suggested price is not accredited, so the source type is USER_INPUT, never
SUPPLIER_FILE (ADR-052 §3.6, ADR-053 S2). The column name states what the file
claims, not who the claim comes from.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from juval.domain.provenance import FieldValue, SourceType
from juval.domain.supplier_price import PriceDiagnostic, SupplierSuggestedPrice, is_currency_code

AMOUNT, CURRENCY = "supplier_suggested_price", "supplier_suggested_price_currency"
METHOD = "declared_in_uploaded_file"
# Digits with an optional sign and decimal point: no symbol, thousands separator,
# underscore or exponent (all of which `Decimal()` would otherwise accept or need repairing).
_PLAIN_DECIMAL = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")
EVIDENCE = ("declared in uploaded file as the supplier's suggested price; author not accredited; not verified; "
            "not a selling price or cost")
EMPTY = "suggested price column present; amount cell empty"


def _raw(raw: Any) -> Optional[str]:
    """The cell as received, in text form (whitespace kept); None for an absent cell."""
    if raw is None:
        return None
    if isinstance(raw, (datetime, date)):
        return raw.isoformat()
    return str(raw)


def _blank(text: Optional[str]) -> bool:
    return text is None or text.strip() == ""


def capture_suggested_price(cells: dict[str, Any], headers: dict[str, str], *, row_number: int, source: str,
                            captured_at: datetime) -> SupplierSuggestedPrice:
    """`headers` maps the suggested-price canonicals present in the file to their original header text."""
    amount_raw, currency_raw = _raw(cells.get(AMOUNT)), _raw(cells.get(CURRENCY))
    currency_raw = None if _blank(currency_raw) else currency_raw
    column = headers.get(AMOUNT)
    reference = f"row={row_number};column={column}" if column else f"row={row_number}"
    common = dict(source=source, method=METHOD, retrieved_at=captured_at, source_type=SourceType.USER_INPUT,
                  source_reference=reference)
    if _blank(amount_raw):
        return SupplierSuggestedPrice(FieldValue.not_found(evidence=EMPTY, **common), currency_raw=currency_raw)

    diagnostics: list[PriceDiagnostic] = []

    def note(code: str, message: str, canonical: str, raw: Optional[str]) -> None:
        diagnostics.append(PriceDiagnostic(code, message, row_number, headers.get(canonical), raw))

    # Surrounding whitespace is the only thing ignored when reading (as for every other column).
    amount_text, currency_text = amount_raw.strip(), currency_raw.strip() if currency_raw else None
    plain = not isinstance(cells.get(AMOUNT), bool) and _PLAIN_DECIMAL.match(amount_text)
    amount = Decimal(amount_text) if plain else None
    if amount is None:
        note("SUGGESTED_PRICE_INVALID", "supplier_suggested_price is not a plain decimal number; kept as raw",
             AMOUNT, amount_raw)
    elif amount <= 0:
        note("SUGGESTED_PRICE_NOT_POSITIVE", "supplier_suggested_price must be greater than 0; kept as raw",
             AMOUNT, amount_raw)
    if currency_text is None:
        note("SUGGESTED_PRICE_CURRENCY_MISSING",
             "supplier_suggested_price_currency is not declared; no currency is inferred", CURRENCY, None)
    elif not is_currency_code(currency_text):
        note("SUGGESTED_PRICE_CURRENCY_INVALID",
             "supplier_suggested_price_currency must be three uppercase letters (e.g. USD); not converted",
             CURRENCY, currency_raw)

    if diagnostics:
        value = FieldValue.invalid(raw_value=amount_raw, evidence=EVIDENCE, **common)
        return SupplierSuggestedPrice(value, currency_raw=currency_raw, diagnostics=tuple(diagnostics))
    return SupplierSuggestedPrice(FieldValue.inferred(amount, unit=currency_text, evidence=EVIDENCE, **common),
                                  currency_raw=currency_raw)
