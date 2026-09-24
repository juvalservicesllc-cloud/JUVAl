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

from juval.domain.financial_evidence import FinancialTerm, TermNature


@dataclass(frozen=True)
class ColumnSpec:
    canonical: str
    target: str
    required: bool
    value_type: str  # "str" | "decimal" | "int" | "bool" | "asin" | "upc" | "datetime"
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


# -- Native financial evidence (ADR-047 §22 step 3) ------------------------
#
# Optional, additive columns that let a file *declare* financial evidence.
# They never feed CostInputs/FeeInputs, profitability or decisions; a file
# without any of them imports exactly as before. See
# docs/architecture/EXCEL_PROCESSING.md §9 for the column contract.

#: Row-level declaration of the FinancialScenario the row's evidence binds to.
FINANCIAL_SCENARIO_COLUMNS: dict[str, str] = {
    "fin_scenario_id": "scenario_id",
    "fin_scenario_version": "scenario_version",
    "fin_currency": "currency",
    "fin_sellable_unit": "sellable_unit_definition",
    "fin_policy_identity": "policy_identity",
    "fin_required_terms": "required_terms",
    "fin_context_requirements": "context_requirements",
}

#: Per-term column suffix -> value type. `currency` exists only for monetary
#: terms: a ratio never carries a currency (ADR-047 §10, §11).
FINANCIAL_TERM_SUFFIXES: dict[str, str] = {
    "amount": "decimal",
    "currency": "str",
    "applies": "bool",
    "applies_method": "str",
    "justification": "str",
    "effective_at": "datetime",
    "basis": "str",
    "allocation": "str",
    "source_basis": "str",
}


#: Native declared selling price (not a FinancialTerm, ADR-047 §9): kept apart
#: from the legacy `selling_price` column, which it never reads or changes.
FINANCIAL_PRICE_COLUMNS: dict[str, str] = {
    "fin_selling_price_amount": "decimal",
    "fin_selling_price_currency": "str",
    "fin_selling_price_effective_at": "datetime",
    "fin_selling_price_basis": "str",
    "fin_selling_price_method": "str",
}


#: Native per-record weight for the financial path (the per-pound shipping
#: operand). Never read from, or written to, the legacy `weight` column.
FINANCIAL_WEIGHT_COLUMNS: dict[str, str] = {
    "fin_weight_amount": "decimal",
    "fin_weight_unit": "str",
    "fin_weight_method": "str",
}


def financial_term_column(term: FinancialTerm, suffix: str) -> str:
    """Header of one native evidence column, e.g. fin_referral_fee_amount."""
    return f"fin_{term.value.lower()}_{suffix}"


def _financial_term_specs() -> tuple[ColumnSpec, ...]:
    specs = []
    for term in FinancialTerm:
        for suffix, value_type in FINANCIAL_TERM_SUFFIXES.items():
            if suffix == "currency" and term.nature is TermNature.DIMENSIONLESS_RATIO:
                continue
            specs.append(ColumnSpec(financial_term_column(term, suffix),
                                    f"financial_evidence[{term.value}].{suffix}", False, value_type))
    return tuple(specs)


FINANCIAL_EVIDENCE_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    *(ColumnSpec(header, f"financial_scenario.{target}", False, "str")
      for header, target in FINANCIAL_SCENARIO_COLUMNS.items()),
    *_financial_term_specs(),
    *(ColumnSpec(header, f"declared_selling_price.{header.removeprefix('fin_selling_price_')}", False, value_type)
      for header, value_type in FINANCIAL_PRICE_COLUMNS.items()),
    *(ColumnSpec(header, f"financial_weight.{header.removeprefix('fin_weight_')}", False, value_type)
      for header, value_type in FINANCIAL_WEIGHT_COLUMNS.items()),
)


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for spec in (*COLUMN_SPECS, *FINANCIAL_EVIDENCE_COLUMN_SPECS):
        index[spec.canonical] = spec.canonical
        for alias in spec.aliases:
            index[alias] = spec.canonical
    return index


ALIAS_TO_CANONICAL: dict[str, str] = _build_alias_index()
