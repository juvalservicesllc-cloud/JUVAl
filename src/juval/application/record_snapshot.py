"""SourcingRecord -> JSON-safe snapshot dict.

Single source of truth for "what does one processed record look like as
JSON" (ADR-019) -- shared by interfaces/api/service.py::record_to_json
(the live POST /api/v1/runs response) and the record-snapshot
persistence adapters, so the persisted shape and the live response
shape can never drift into two implementations of the same mapping.

Provenance rule (ADR-003/ADR-004) applies exactly as everywhere else: a
sensitive field is never collapsed to a bare value -- it always travels
as {"value": ..., "status": "VERIFIED"|"INFERRED"|"NOT_FOUND"|"INVALID"|None}.
Decimal values become strings (JSON has no exact decimal type, and this
dict must be safe to pass straight to json.dumps for persistence).

Kept framework-free on purpose: no Pydantic here (that belongs to
interfaces/api/), so infrastructure/ adapters can depend on this module
without pulling in an HTTP-layer dependency.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from juval.domain.provenance import FieldValue
from juval.domain.risk import RiskFlag, RiskType
from juval.domain.sourcing_record import SourcingRecord


def _fv(fv: Optional[FieldValue[Any]]) -> dict[str, Any]:
    if fv is None:
        return {"value": None, "status": None}
    value = str(fv.value) if isinstance(fv.value, Decimal) else fv.value
    return {"value": value, "status": fv.status.value}


def _severity_value(flag: Optional[RiskFlag]) -> Optional[str]:
    """A RiskFlag's severity is its own FieldValue[Severity] (ADR-020) --
    unwrapped here to the plain enum-value string this snapshot's
    `hazmat_severity`/`bulky_severity` fields have always held, so the
    API/export contract shape does not change. Severity's own
    verification status (VERIFIED for a certain NONE, INFERRED for
    today's policy-derived HIGH/MEDIUM) is intentionally not exposed
    yet -- no confirmed consumer needs it (see ADR-020 "Qué NO
    resuelve")."""

    if flag is None or flag.severity.value is None:
        return None
    return flag.severity.value.value


def record_to_snapshot(record: SourcingRecord) -> dict[str, Any]:
    """Same shape as interfaces/api/models.py::RecordOut, as a plain dict."""

    ident = record.product.identification
    dims = record.product.dimensions
    price = record.product.price

    cog = record.costs.cog if record.costs is not None else None
    shipping_per_unit = record.costs.shipping_per_unit if record.costs is not None else None

    if record.profitability is not None:
        profit = _fv(record.profitability.profit)
        roi = _fv(record.profitability.roi)
        margin = _fv(record.profitability.margin)
        break_even_price = _fv(record.profitability.break_even_price)
        max_cog_target_profit = _fv(record.profitability.max_cog_target_profit)
        max_cog_target_roi = _fv(record.profitability.max_cog_target_roi)
    else:
        profit = roi = margin = break_even_price = {"value": None, "status": None}
        max_cog_target_profit = max_cog_target_roi = {"value": None, "status": None}

    hazmat_flag = record.risk.flag_for(RiskType.HAZMAT)
    bulky_flag = record.risk.flag_for(RiskType.BULKY)

    if record.decision is not None:
        decision = record.decision.decision.value
        decision_reasons = [f"{r.code}: {r.message}" for r in record.decision.reasons]
    else:
        decision = None
        decision_reasons = []

    return {
        "record_ref": record.record_ref,
        "marketplace": ident.marketplace,
        "supplier_sku": ident.supplier_sku,
        "asin": _fv(ident.asin),
        "upc": _fv(ident.upc),
        "weight": _fv(dims.weight),
        "selling_price": _fv(price.selling_price_used),
        "cog": str(cog) if cog is not None else None,
        "shipping_per_unit": str(shipping_per_unit) if shipping_per_unit is not None else None,
        "profit": profit,
        "roi": roi,
        "margin": margin,
        "break_even_price": break_even_price,
        "max_cog_target_profit": max_cog_target_profit,
        "max_cog_target_roi": max_cog_target_roi,
        "hazmat_status": hazmat_flag.status.value if hazmat_flag is not None else None,
        "hazmat_severity": _severity_value(hazmat_flag),
        "bulky_status": bulky_flag.status.value if bulky_flag is not None else None,
        "bulky_severity": _severity_value(bulky_flag),
        "decision": decision,
        "decision_reasons": decision_reasons,
        "issue_count": len(record.issues),
        "issues": [f"[{i.level.value}] {i.code}: {i.message}" for i in record.issues],
    }
