"""Hand a record's native evidence to the dependency resolver (ADR-047 §16).

Pure and additive. The price given to the resolver is only the row's native
declared price (`fin_selling_price_*`); there is no fallback to the legacy
selling price, to FeeInputs or to any default. Weight and targets stay
explicit caller inputs.
"""

from __future__ import annotations

from typing import Optional

from juval.application.run_pipeline import RecordFinancialEvidence
from juval.domain.financial_dependencies import FinancialDependencyResolution, resolve_financial_dependencies
from juval.domain.provenance import FieldValue


def resolve_record_financial_dependencies(
    item: RecordFinancialEvidence,
    *,
    weight: Optional[FieldValue] = None,
    target_profit: Optional[FieldValue] = None,
    target_roi: Optional[FieldValue] = None,
) -> Optional[FinancialDependencyResolution]:
    """None when the record declared no complete scenario (nothing to resolve against)."""
    if not isinstance(item, RecordFinancialEvidence):
        raise ValueError("Explicit RecordFinancialEvidence required")
    if item.evidence is None:
        return None
    price = item.capture.selling_price
    return resolve_financial_dependencies(
        item.evidence, selling_price=price.amount if price is not None else None,
        weight=weight, target_profit=target_profit, target_roi=target_roi,
    )
