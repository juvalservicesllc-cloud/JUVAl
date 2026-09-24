"""Build one FinancialRecordDocument per record with native evidence (ADR-047).

Glue over existing pieces only: the pipeline's transported evidence, the
dependency resolver (via the native adapter) and the accredited calculator.
Inputs are the record's native evidence and declared price plus explicit
caller FieldValues; nothing comes from the legacy price, CostInputs,
FeeInputs, weight columns or defaults. A record whose row declared no
complete scenario has no FinancialEvidenceSet and therefore no document —
its capture problems are reported by the caller, since format v1 has no
place for them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from juval.application.financial_calculation import calculate_financial_results
from juval.application.financial_serialization import FinancialRecordDocument
from juval.application.native_financial_resolution import resolve_record_financial_dependencies
from juval.application.run_pipeline import PipelineRunWithFinancialEvidence
from juval.domain.provenance import FieldValue


def build_financial_documents(
    result: PipelineRunWithFinancialEvidence,
    *,
    calculated_at: datetime,
    target_profit: Optional[FieldValue] = None,
    target_roi: Optional[FieldValue] = None,
) -> tuple[FinancialRecordDocument, ...]:
    """Documents in record order, only for records whose evidence could be bound."""
    documents = []
    for item in result.financial_evidence:
        if item.evidence is None:
            continue
        resolution = resolve_record_financial_dependencies(item, target_profit=target_profit, target_roi=target_roi)
        documents.append(FinancialRecordDocument(
            item.evidence, item.capture.selling_price, resolution,
            calculate_financial_results(resolution, calculated_at=calculated_at)))
    return tuple(documents)
