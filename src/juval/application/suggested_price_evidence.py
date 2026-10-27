"""`juval.supplier-suggested-price` v1: the supplier suggested price in a record snapshot (ADR-053).

Serialization only: a stored document is reproduced exactly as captured. The
amount keeps its status, currency unit, raw text and full provenance. Evidence
only; nothing here feeds a decision.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from juval.application.demand_evidence import DECLARED, NOT_CAPTURED, NOT_DECLARED
from juval.domain.supplier_price import SupplierSuggestedPrice

FORMAT = "juval.supplier-suggested-price"
VERSION = 1
KEY = "supplier_suggested_price"


def serialize_suggested_price(capture: Optional[SupplierSuggestedPrice]) -> Optional[dict[str, Any]]:
    """None when the file had neither suggested-price column (NOT_DECLARED)."""
    if capture is None:
        return None
    from juval.application.record_snapshot import _fv   # one FieldValue JSON shape for every snapshot field

    return {
        "format": FORMAT,
        "version": VERSION,
        "amount": _fv(capture.amount),
        "currency_raw": capture.currency_raw,
        "diagnostics": [
            {"code": d.code, "column": d.column, "row": d.row, "raw_value": d.raw_value, "message": d.message}
            for d in capture.diagnostics
        ],
    }


def suggested_price_state(snapshot: Mapping[str, Any]) -> str:
    """NOT_CAPTURED (snapshot predates ADR-053), NOT_DECLARED (neither column
    in the file) or DECLARED (a document exists, usable or not)."""
    if KEY not in snapshot:
        return NOT_CAPTURED
    return NOT_DECLARED if snapshot[KEY] is None else DECLARED


def suggested_price_export_cells(snapshot: Mapping[str, Any]) -> tuple[Any, ...]:
    """Same cells, same order as `exporter.suggested_price_cells_from_capture`,
    read from a stored snapshot (so a historical one reports NOT_CAPTURED)."""
    from juval.infrastructure.excel.exporter import SUGGESTED_PRICE_EXPORT_HEADERS

    state = suggested_price_state(snapshot)
    if state != DECLARED:
        return (state,) + (None,) * (len(SUGGESTED_PRICE_EXPORT_HEADERS) - 1)
    document = snapshot[KEY]
    amount = document["amount"]
    provenance = amount.get("provenance") or {}
    diagnostics = "; ".join(d["code"] for d in document.get("diagnostics", [])) or None
    return (state, amount.get("value"), amount.get("unit"), amount.get("status"), amount.get("raw_value"),
            document.get("currency_raw"), provenance.get("source_reference"), diagnostics)
