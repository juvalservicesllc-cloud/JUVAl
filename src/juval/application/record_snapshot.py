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
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional

from juval.domain.provenance import FieldValue
from juval.application.demand_evidence import serialize_demand_evidence
from juval.application.suggested_price_evidence import serialize_suggested_price
from juval.domain.risk import RiskFlag, RiskType
from juval.domain.sourcing_record import SourcingRecord


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _fv(fv: Optional[FieldValue[Any]]) -> dict[str, Any]:
    if fv is None:
        return {"value": None, "status": None, "provenance": None, "unit": None, "raw_value": None}
    provenance = fv.provenance
    return {
        "value": _json_value(fv.value),
        "status": fv.status.value,
        "unit": fv.unit,
        "raw_value": _json_value(fv.raw_value),
        "provenance": {
            "source": provenance.source,
            "source_type": provenance.source_type.value,
            "verification_status": provenance.verification_status.value,
            "retrieved_at": provenance.retrieved_at.isoformat(),
            "method": provenance.method,
            "confidence": provenance.confidence,
            "evidence": provenance.evidence,
            "source_reference": provenance.source_reference,
        },
    }


def _decimal_str(value: Optional[Decimal]) -> Optional[str]:
    return str(value) if value is not None else None


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


def _severity_status(flag: Optional[RiskFlag]) -> Optional[str]:
    """The severity's own verification status, beside the plain value above
    (the additive field ADR-020 anticipated): INFERRED for the policy-derived
    HIGH/MEDIUM, VERIFIED for the certain NONE of an absent risk, NOT_FOUND or
    INVALID when presence could not be read. None when the file had no column."""

    return None if flag is None else flag.severity.status.value


def _severity_source_type(flag: Optional[RiskFlag]) -> Optional[str]:
    """Where that status comes from, so VERIFIED is never read as "verified by
    an authorized source": SUPPLIER_FILE for the NONE of a declared absence,
    CALCULATED for the policy HIGH/MEDIUM, NOT_FOUND for a blank cell."""

    return None if flag is None else flag.severity.provenance.source_type.value


#: Snapshot keys of the severity provenance, in export order. The same names
#: are the export column headers (CLI/run workbook and catalog export).
SEVERITY_PROVENANCE_KEYS: tuple[str, ...] = (
    "hazmat_severity_status", "hazmat_severity_source_type",
    "bulky_severity_status", "bulky_severity_source_type",
)


def severity_provenance(record: SourcingRecord) -> dict[str, Optional[str]]:
    """The one derivation of severity provenance, used by the snapshot/API and
    by the workbook export."""

    hazmat, bulky = record.risk.flag_for(RiskType.HAZMAT), record.risk.flag_for(RiskType.BULKY)
    return {
        "hazmat_severity_status": _severity_status(hazmat),
        "hazmat_severity_source_type": _severity_source_type(hazmat),
        "bulky_severity_status": _severity_status(bulky),
        "bulky_severity_source_type": _severity_source_type(bulky),
    }


def severity_provenance_cells(snapshot: Mapping[str, Any]) -> tuple[Optional[str], ...]:
    """Export cells from a stored snapshot. A snapshot written before these
    keys existed gives empty cells: nothing is reconstructed or assumed."""

    return tuple(snapshot.get(key) for key in SEVERITY_PROVENANCE_KEYS)


def record_to_snapshot(record: SourcingRecord) -> dict[str, Any]:
    """Same shape as interfaces/api/models.py::RecordOut, as a plain dict."""

    ident = record.product.identification
    info = record.product.info
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
        # Intermediate terms the Profitability Engine already computed
        # (ProfitabilityResult.total_fees/seller_proceeds/total_cost). They are
        # plain Decimals there, so they stay plain here -- same convention as
        # `cog`/`shipping_per_unit`. They are None exactly when selling_price
        # was unusable, which `profit.status` already reports; nothing is
        # coerced to zero.
        total_fees = _decimal_str(record.profitability.total_fees)
        seller_proceeds = _decimal_str(record.profitability.seller_proceeds)
        total_cost = _decimal_str(record.profitability.total_cost)
    else:
        profit = roi = margin = break_even_price = {"value": None, "status": None}
        max_cog_target_profit = max_cog_target_roi = {"value": None, "status": None}
        total_fees = seller_proceeds = total_cost = None

    hazmat_flag = record.risk.flag_for(RiskType.HAZMAT)
    bulky_flag = record.risk.flag_for(RiskType.BULKY)

    if record.decision is not None:
        decision = record.decision.decision.value
        decision_reasons = [f"{r.code}: {r.message}" for r in record.decision.reasons]
        decision_reason_codes = [r.code for r in record.decision.reasons]
    else:
        decision = None
        decision_reasons = []
        decision_reason_codes = []

    return {
        "record_ref": record.record_ref,
        "marketplace": ident.marketplace,
        "supplier_sku": ident.supplier_sku,
        "asin": _fv(ident.asin),
        "upc": _fv(ident.upc),
        "title": _fv(info.title),
        "brand": _fv(info.brand),
        "category": _fv(info.category),
        "weight": _fv(dims.weight),
        "height": _fv(dims.height),
        "width": _fv(dims.width),
        "length": _fv(dims.length),
        "selling_price": _fv(price.selling_price_used),
        "cog": str(cog) if cog is not None else None,
        "shipping_per_unit": str(shipping_per_unit) if shipping_per_unit is not None else None,
        "total_fees": total_fees,
        "seller_proceeds": seller_proceeds,
        "total_cost": total_cost,
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
        **severity_provenance(record),
        "decision": decision,
        "decision_reasons": decision_reasons,
        # The engine's DecisionReason codes, in order, beside the rendered
        # `decision_reasons` text (same reasoning as `issue_codes` below).
        # Absent on snapshots written before 2026-10-26; never reconstructed
        # from the text (application/review_classification.py).
        "decision_reason_codes": decision_reason_codes,
        "issue_count": len(record.issues),
        "issues": [f"[{i.level.value}] {i.code}: {i.message}" for i in record.issues],
        # Canonical ProcessingIssue codes, kept separately from the rendered
        # `issues` strings so issue-type analytics group by the real code and
        # never parse a display string back into one. Absent on snapshots
        # written before this field existed -- never reconstructed at read time.
        "issue_codes": [i.code for i in record.issues],
        # Declared demand evidence (ADR-052): null = the file declared no demand
        # columns; absent on snapshots written before it existed. Never read
        # by decisions.
        "demand_evidence": serialize_demand_evidence(record.market_evidence),
        # Supplier suggested price (ADR-053): null = neither column in the file;
        # absent on snapshots written before it existed. Never read by decisions.
        "supplier_suggested_price": serialize_suggested_price(record.supplier_suggested_price),
    }
