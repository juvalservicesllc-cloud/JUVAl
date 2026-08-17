"""Processing Core orchestrator: Data Quality -> Profitability -> Risk -> Decision.

`process_record` is the `process_record(record, thresholds)` orchestrator
requested by the Fase 2 brief. It calls the existing engines only —
`profitability.py` for the financial math and `decision_engine.py` for the
classification — and never redefines a formula or a rule inline. Risk
evaluation itself (turning raw signals into `RiskFlag`s) happens upstream,
at import time in this phase (see infrastructure/excel/importer.py); here
"Risk evaluation" means feeding the risk profile that is already on the
record into the Decision Engine, and leaving room for a later phase to add
risk-specific rules of its own without touching this orchestration.

This module has no I/O and does not import anything from
`infrastructure/` — it is Processing Core, called by the Application Layer
(`application/run_pipeline.py`), never the other way around.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Optional, Sequence

from juval.domain.costs import FeeInputs
from juval.domain.decision import DecisionInputs, Thresholds
from juval.domain.issues import IssueLevel, ProcessingIssue
from juval.domain.provenance import FieldValue
from juval.domain.sourcing_record import SourcingRecord

from .data_quality import (
    DataQualityConfig,
    validate_competition_consistency,
    validate_dimensions,
    validate_financial_consistency,
    validate_identification,
    validate_price,
)
from .decision_engine import evaluate_decision
from .profitability import compute_profitability

_SOURCE = "processing_pipeline"


def process_record(
    record: SourcingRecord,
    thresholds: Thresholds,
    *,
    fees: Optional[FeeInputs] = None,
    quality_config: DataQualityConfig = DataQualityConfig(),
    now: datetime,
) -> SourcingRecord:
    """Runs the full per-record pipeline and returns a new SourcingRecord.

    1. Data Quality  -- audits identification/dimensions/price/competition
    2. Profitability -- only if both costs and a selling price are usable
    3. Risk          -- reads `record.risk` as-is (built upstream)
    4. Decision       -- BUY/REVIEW/PASS via the existing Decision Engine
    5. Issues aggregation -- everything above is appended to record.issues
    """

    issues: list[ProcessingIssue] = list(record.issues)

    # 1. Data Quality
    issues.extend(validate_identification(record.product.identification, record_ref=record.record_ref))
    issues.extend(validate_dimensions(record.product.dimensions, config=quality_config, record_ref=record.record_ref))
    issues.extend(validate_price(record.product.price, record_ref=record.record_ref))
    issues.extend(validate_competition_consistency(record.product.competition, record_ref=record.record_ref))

    # 2. Profitability (existing engine only — no formulas duplicated here)
    selling_price = record.product.price.selling_price_used
    effective_fees = fees if fees is not None else record.fees
    profitability = None

    if record.costs is None:
        pass  # already carries a MISSING_REQUIRED_FIELD/INVALID_NUMBER/NEGATIVE_COST issue from import
    elif selling_price is None:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.WARNING, code="MISSING_SELLING_PRICE",
                message="No selling price available; profitability cannot be calculated.",
                record_ref=record.record_ref,
            )
        )
    elif effective_fees is None:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.WARNING, code="MISSING_FEES",
                message="No FeeInputs provided; profitability cannot be calculated.",
                record_ref=record.record_ref,
            )
        )
    else:
        profitability = compute_profitability(
            selling_price=selling_price,
            costs=record.costs,
            fees=effective_fees,
            target_profit=thresholds.target_profit,
            target_roi=thresholds.target_roi,
            now=now,
        )
        issues.extend(validate_financial_consistency(profitability, record_ref=record.record_ref))

    # 3. Risk (already attached upstream; read as-is)
    risk_profile = record.risk

    # 4. Decision (existing engine only)
    if profitability is not None:
        profit_fv, roi_fv = profitability.profit, profitability.roi
    else:
        reason = "profitability could not be calculated for this record"
        profit_fv = FieldValue.not_found(source=_SOURCE, method="process_record", retrieved_at=now, evidence=reason)
        roi_fv = FieldValue.not_found(source=_SOURCE, method="process_record", retrieved_at=now, evidence=reason)

    decision_inputs = DecisionInputs(
        profit=profit_fv,
        roi=roi_fv,
        estimated_monthly_sales=record.product.demand.estimated_monthly_sales,
        risk_profile=risk_profile,
    )
    decision = evaluate_decision(decision_inputs, thresholds, now=now)

    # 5. Issues aggregation
    return replace(record, profitability=profitability, decision=decision, issues=tuple(issues))


def process_batch(
    records: Sequence[SourcingRecord],
    thresholds: Thresholds,
    *,
    fees: Optional[FeeInputs] = None,
    quality_config: DataQualityConfig = DataQualityConfig(),
    now: datetime,
) -> tuple[SourcingRecord, ...]:
    return tuple(
        process_record(record, thresholds, fees=fees, quality_config=quality_config, now=now) for record in records
    )
