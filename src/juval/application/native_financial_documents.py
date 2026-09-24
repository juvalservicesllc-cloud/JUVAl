"""Build one format-v2 financial document per record with native evidence (ADR-047).

Glue over existing pieces only: the pipeline's transported evidence, the
dependency resolver (via the native adapter) and the accredited calculator.
Inputs are the record's native evidence and declared price plus explicit
caller FieldValues; nothing comes from the legacy price, CostInputs,
FeeInputs, weight columns or defaults. A record whose row declared no
complete scenario has no FinancialEvidenceSet and therefore no document —
its capture problems are reported by the caller only.

The v2 blocks carry only what this flow really has: the inputs it hands to
the resolver (the declared price, the declared `fin_weight_*` weight, the
caller's targets), the capturer's diagnostics as emitted at the source
(subject, row, and the failing column/raw value when known; format v2 has
no field for the diagnostic code, which stays on the capture), and the
implementation identity with whatever version or revision the caller
actually knows (None otherwise).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from juval.application.financial_calculation import calculate_financial_results
from juval.application.financial_serialization import FinancialRecordDocument
from juval.application.financial_serialization_v2 import (
    CaptureProblem,
    FinancialRecordDocumentV2,
    ImplementationIdentity,
    SuppliedInputs,
)
from juval.application.native_financial_resolution import resolve_record_financial_dependencies
from juval.application.run_pipeline import PipelineRunWithFinancialEvidence
from juval.domain.provenance import FieldValue


def build_financial_documents(
    result: PipelineRunWithFinancialEvidence,
    *,
    calculated_at: datetime,
    target_profit: Optional[FieldValue] = None,
    target_roi: Optional[FieldValue] = None,
    application_version: Optional[str] = None,
    code_revision: Optional[str] = None,
) -> tuple[FinancialRecordDocumentV2, ...]:
    """Documents in record order, only for records whose evidence could be bound."""
    identity = ImplementationIdentity.current(application_version=application_version, code_revision=code_revision)
    documents = []
    for item in result.financial_evidence:
        if item.evidence is None:
            continue
        price = item.capture.selling_price
        supplied = SuppliedInputs(selling_price=price.amount if price is not None else None,
                                  weight=item.capture.weight, target_profit=target_profit, target_roi=target_roi)
        resolution = resolve_record_financial_dependencies(
            item, weight=supplied.weight, target_profit=target_profit, target_roi=target_roi)
        core = FinancialRecordDocument(item.evidence, price, resolution,
                                       calculate_financial_results(resolution, calculated_at=calculated_at))
        problems = tuple(CaptureProblem(d.text, subject=d.subject, row=d.row, column=d.column, raw_value=d.raw_value)
                         for d in item.capture.diagnostics)
        documents.append(FinancialRecordDocumentV2(core, supplied, problems, identity))
    return tuple(documents)
