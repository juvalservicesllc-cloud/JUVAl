"""Excel Exporter — Fase 2 vertical slice.

Internal Model (SourcingRecord) -> Result Model (flat rows) -> XLSX

A `FieldValue` is never collapsed to a single cell: every sensitive field
gets a `<field>` column and a `<field>_status` column side by side, so the
verification status travels with the value into the artifact the user
actually reads (Fase 0 ARCHITECTURE.md §6).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

import openpyxl
from openpyxl.cell import Cell
from openpyxl.worksheet.worksheet import Worksheet

from juval.domain.provenance import FieldValue
from juval.domain.risk import RiskFlag, RiskType
from juval.domain.sourcing_record import SourcingRecord

HEADERS: tuple[str, ...] = (
    "record_ref",
    "marketplace",
    "supplier_sku",
    "asin",
    "asin_status",
    "asin_source",
    "upc",
    "upc_status",
    "title",
    "brand",
    "category",
    "weight_lb",
    "weight_status",
    "height_in",
    "width_in",
    "length_in",
    "cog",
    "shipping_per_unit",
    "selling_price",
    "selling_price_status",
    "selling_price_source",
    "profit",
    "profit_status",
    "roi",
    "roi_status",
    "margin",
    "margin_status",
    "break_even_price",
    "break_even_price_status",
    "max_cog_target_profit",
    "max_cog_target_profit_status",
    "max_cog_target_roi",
    "max_cog_target_roi_status",
    "hazmat_status",
    "hazmat_severity",
    "bulky_status",
    "bulky_severity",
    "decision",
    "decision_reasons",
    "issue_count",
    "issues",
)

#: Declared demand evidence (ADR-052), appended to both exports. Evidence only:
#: never a decision input. An absent value is an empty cell, never 0.
DEMAND_EXPORT_HEADERS: tuple[str, ...] = (
    "demand_evidence_state", "demand_declared_units", "demand_status", "demand_raw_value",
    "demand_window_start", "demand_window_end", "demand_observed_at", "demand_population",
    "demand_method", "demand_source_reference", "demand_diagnostics",
)
HEADERS = HEADERS + DEMAND_EXPORT_HEADERS


def demand_cells_from_capture(capture) -> tuple[Any, ...]:
    """Export cells for one record's DeclaredDemandCapture (None = NOT_DECLARED)."""
    if capture is None:
        return ("NOT_DECLARED",) + (None,) * (len(DEMAND_EXPORT_HEADERS) - 1)
    diagnostics = "; ".join(d.code for d in capture.diagnostics) or None
    if not capture.observations:
        return ("DECLARED",) + (None,) * (len(DEMAND_EXPORT_HEADERS) - 2) + (diagnostics,)
    item = capture.observations[0]
    observation, value = item.observation, item.observation.value
    return ("DECLARED", value.value, value.status.value, value.raw_value,
            observation.window.start.isoformat(), observation.window.end.isoformat(), observation.observed_at.isoformat(),
            observation.population_definition, value.provenance.method, value.provenance.source_reference, diagnostics)


def _value_and_status(fv: Optional[FieldValue]) -> tuple[Any, Any]:
    if fv is None:
        return None, None
    return fv.value, fv.status.value


def _severity_value(flag: Optional[RiskFlag]) -> Optional[str]:
    """A RiskFlag's severity is its own FieldValue[Severity] (ADR-020) --
    this unwraps to the plain enum-value string a cell can hold, distinct
    from that FieldValue's own verification status (not exported here,
    same scope as before this ADR: only presence status is a column)."""

    if flag is None or flag.severity.value is None:
        return None
    return flag.severity.value.value


def _row_for_record(record: SourcingRecord) -> tuple[Any, ...]:
    ident = record.product.identification
    info = record.product.info
    dims = record.product.dimensions
    price = record.product.price

    asin_value, asin_status = _value_and_status(ident.asin)
    upc_value, upc_status = _value_and_status(ident.upc)
    weight_value, weight_status = _value_and_status(dims.weight)
    height_value, _ = _value_and_status(dims.height)
    width_value, _ = _value_and_status(dims.width)
    length_value, _ = _value_and_status(dims.length)
    title_value, _ = _value_and_status(info.title)
    brand_value, _ = _value_and_status(info.brand)
    category_value, _ = _value_and_status(info.category)
    selling_price_value, selling_price_status = _value_and_status(price.selling_price_used)

    cog = record.costs.cog if record.costs is not None else None
    shipping_per_unit = record.costs.shipping_per_unit if record.costs is not None else None

    if record.profitability is not None:
        profit_value, profit_status = _value_and_status(record.profitability.profit)
        roi_value, roi_status = _value_and_status(record.profitability.roi)
        margin_value, margin_status = _value_and_status(record.profitability.margin)
        break_even_value, break_even_status = _value_and_status(record.profitability.break_even_price)
        max_cog_profit_value, max_cog_profit_status = _value_and_status(record.profitability.max_cog_target_profit)
        max_cog_roi_value, max_cog_roi_status = _value_and_status(record.profitability.max_cog_target_roi)
    else:
        profit_value = profit_status = roi_value = roi_status = None
        margin_value = margin_status = break_even_value = break_even_status = None
        max_cog_profit_value = max_cog_profit_status = max_cog_roi_value = max_cog_roi_status = None

    hazmat_flag = record.risk.flag_for(RiskType.HAZMAT)
    bulky_flag = record.risk.flag_for(RiskType.BULKY)

    if record.decision is not None:
        decision_value = record.decision.decision.value
        decision_reasons = "; ".join(f"{r.code}: {r.message}" for r in record.decision.reasons)
    else:
        decision_value = None
        decision_reasons = None

    issues_text = "; ".join(f"[{i.level.value}] {i.code}: {i.message}" for i in record.issues)

    return (
        record.record_ref,
        ident.marketplace,
        ident.supplier_sku,
        asin_value,
        asin_status,
        ident.asin.provenance.source if ident.asin is not None else None,
        upc_value,
        upc_status,
        title_value,
        brand_value,
        category_value,
        weight_value,
        weight_status,
        height_value,
        width_value,
        length_value,
        cog,
        shipping_per_unit,
        selling_price_value,
        selling_price_status,
        price.selling_price_source.value,
        profit_value,
        profit_status,
        roi_value,
        roi_status,
        margin_value,
        margin_status,
        break_even_value,
        break_even_status,
        max_cog_profit_value,
        max_cog_profit_status,
        max_cog_roi_value,
        max_cog_roi_status,
        hazmat_flag.status.value if hazmat_flag is not None else None,
        _severity_value(hazmat_flag),
        bulky_flag.status.value if bulky_flag is not None else None,
        _severity_value(bulky_flag),
        decision_value,
        decision_reasons,
        len(record.issues),
        issues_text,
    ) + demand_cells_from_capture(record.market_evidence)


def append_literal_row(sheet: Worksheet, values: Sequence[Any]) -> None:
    """Write supplied strings as XLSX text, never formulas or error cells.

    Keep the text unchanged (no apostrophe prefix) and retain numeric/blank
    cell types. JUVAl exports calculated values, not executable formulas.
    """
    cells = []
    for value in values:
        cell = Cell(sheet, value=value)
        if isinstance(value, str):
            cell.data_type = "s"
        cells.append(cell)
    sheet.append(cells)


def export_excel(records: Sequence[SourcingRecord], path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "juval_sourcing_results"
    append_literal_row(sheet, HEADERS)
    for record in records:
        append_literal_row(sheet, _row_for_record(record))
    workbook.save(Path(path))
