"""Explicit, documented column mapping for the sourcing Excel format.

This is the single source of truth for "which Excel header maps to which
domain field" — the importer and exporter both read this table rather than
hardcoding header names inline. See docs/architecture/EXCEL_PROCESSING.md
for the human-readable version of this same table.

Column order in the sheet is NEVER assumed: headers are resolved by name
(after normalization) to a column index, then that index is used to read
every data row. Reordering columns in the source file does not break
anything; renaming a header to something unrecognized does (it becomes an
"unknown column" warning, or a "missing required column" fatal error if
that header was required).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSpec:
    canonical: str
    target: str
    required: bool
    value_type: str  # "str" | "decimal" | "int" | "bool" | "asin" | "upc"
    aliases: tuple[str, ...] = ()


COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("supplier_sku", "product.identification.supplier_sku", False, "str", aliases=("sku",)),
    ColumnSpec("marketplace", "product.identification.marketplace", True, "str"),
    ColumnSpec("asin", "product.identification.asin", True, "asin"),
    ColumnSpec("upc", "product.identification.upc", False, "upc"),
    ColumnSpec("title", "product.info.title", False, "str", aliases=("product_title",)),
    ColumnSpec("brand", "product.info.brand", False, "str"),
    ColumnSpec("category", "product.info.category", False, "str"),
    ColumnSpec("weight", "product.dimensions.weight", False, "decimal", aliases=("weight_lb",)),
    ColumnSpec("weight_unit", "product.dimensions.weight (unit)", False, "str"),
    ColumnSpec("height", "product.dimensions.height", False, "decimal"),
    ColumnSpec("width", "product.dimensions.width", False, "decimal"),
    ColumnSpec("length", "product.dimensions.length", False, "decimal"),
    ColumnSpec("dimension_unit", "product.dimensions.{height,width,length} (unit)", False, "str"),
    ColumnSpec("cost", "costs.cog", True, "decimal", aliases=("cog",)),
    ColumnSpec("shipping_per_unit", "costs.shipping_per_unit", False, "decimal"),
    ColumnSpec(
        "selling_price",
        "product.price.selling_price_used (+ current_buy_box, selling_price_source=CURRENT_BUY_BOX)",
        False,
        "decimal",
        aliases=("price", "buy_box"),
    ),
    ColumnSpec("hazmat", "risk[HAZMAT]", False, "bool"),
    ColumnSpec("bulky", "risk[BULKY]", False, "bool"),
)


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for spec in COLUMN_SPECS:
        index[spec.canonical] = spec.canonical
        for alias in spec.aliases:
            index[alias] = spec.canonical
    return index


ALIAS_TO_CANONICAL: dict[str, str] = _build_alias_index()
