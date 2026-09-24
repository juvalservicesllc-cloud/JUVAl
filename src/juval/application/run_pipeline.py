"""Application Layer: Excel Input -> ... -> Excel-ready results + ExecutionRun.

This is the only module in Fase 2 allowed to depend on both
`infrastructure/` (the Excel importer) and `processing/` (the pipeline) —
consistent with Fase 0 ARCHITECTURE.md §3: Interfaces -> Application ->
Processing Core, with Infrastructure implementing the I/O underneath.
Processing Core itself (`processing/pipeline.py`) never imports
`infrastructure/`.

All non-deterministic inputs (`now`, `execution_id`) are supplied by the
caller rather than generated inside this function, so that
`run_pipeline` is a pure function of its arguments — required for the
reproducibility property in requirement 12 (same input + same thresholds
+ same version => same output).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.execution_run import ExecutionRun, ExecutionStatus, hash_file
from juval.domain.financial_evidence import FinancialEvidenceSet
from juval.domain.issues import IssueLevel
from juval.domain.sourcing_record import SourcingRecord
from juval.infrastructure.excel.financial_capture import NativeFinancialCapture
from juval.infrastructure.excel.importer import ImportResult, import_file
from juval.processing.data_quality import DataQualityConfig
from juval.processing.pipeline import process_batch


def run_pipeline(
    input_path: Path,
    thresholds: Thresholds,
    *,
    fees: Optional[FeeInputs] = None,
    application_version: str,
    execution_id: str,
    now: datetime,
    quality_config: DataQualityConfig = DataQualityConfig(),
) -> tuple[ExecutionRun, tuple[SourcingRecord, ...]]:
    run, records, _ = _execute(
        input_path, thresholds, fees=fees, application_version=application_version,
        execution_id=execution_id, now=now, quality_config=quality_config,
    )
    return run, records


@dataclass(frozen=True)
class RecordFinancialEvidence:
    """Native financial evidence (ADR-047 §22 step 3) of one processed record.

    Transported next to the record, never inside it: it does not feed
    profitability, risk, score or BUY/REVIEW/PASS, and its `problems` are
    capture diagnostics, not legacy ProcessingIssues. `evidence` is None
    exactly when the row declared no complete scenario; the captured terms
    and the reasons stay available on `capture`.
    """

    execution_id: str
    record_ref: str
    capture: NativeFinancialCapture
    evidence: Optional[FinancialEvidenceSet]

    @property
    def problems(self) -> tuple[str, ...]:
        return self.capture.problems


@dataclass(frozen=True)
class PipelineRunWithFinancialEvidence:
    """run_pipeline's result plus native financial evidence, keyed by record_ref.

    `financial_evidence` follows `records` order and is empty when the input
    has no `fin_*` column: no evidence is fabricated for a record without a
    native capture, and nothing is rebuilt from CostInputs/FeeInputs.
    """

    run: ExecutionRun
    records: tuple[SourcingRecord, ...]
    financial_evidence: tuple[RecordFinancialEvidence, ...]

    def evidence_for(self, record_ref: str) -> Optional[RecordFinancialEvidence]:
        return next((item for item in self.financial_evidence if item.record_ref == record_ref), None)


def run_pipeline_with_financial_evidence(
    input_path: Path,
    thresholds: Thresholds,
    *,
    fees: Optional[FeeInputs] = None,
    application_version: str,
    execution_id: str,
    now: datetime,
    quality_config: DataQualityConfig = DataQualityConfig(),
) -> PipelineRunWithFinancialEvidence:
    """Same run and records as run_pipeline, plus each record's native evidence.

    Additive: run_pipeline's signature and tuple are unchanged, and both share
    one execution path, so run and records are identical by construction.
    """
    run, records, import_result = _execute(
        input_path, thresholds, fees=fees, application_version=application_version,
        execution_id=execution_id, now=now, quality_config=quality_config,
    )
    return PipelineRunWithFinancialEvidence(
        run, records, bind_financial_captures(import_result, records, execution_id=execution_id))


def bind_financial_captures(
    import_result: ImportResult, records: tuple[SourcingRecord, ...], *, execution_id: str
) -> tuple[RecordFinancialEvidence, ...]:
    """Bind each native capture to its record by record_ref, never by position.

    record_ref embeds the source row number, so a row the importer dropped
    cannot shift another row's capture, and duplicate ASIN/UPC values do not
    matter. Any mismatch between imported records, captures and processed
    records fails loudly instead of attaching evidence to the wrong record.
    """
    captures = import_result.financial_captures
    if not captures:
        return ()
    imported = [record.record_ref for record in import_result.records]
    captured = [capture.record_ref for capture in captures]
    processed = [record.record_ref for record in records]
    if len(set(captured)) != len(captured) or len(set(imported)) != len(imported):
        raise ValueError("record_ref must identify exactly one imported record and one capture")
    if captured != imported or processed != imported:
        raise ValueError("native financial captures do not correspond one-to-one to the processed records")
    by_ref = {capture.record_ref: capture for capture in captures}
    return tuple(
        RecordFinancialEvidence(
            execution_id=execution_id, record_ref=ref, capture=by_ref[ref],
            evidence=by_ref[ref].bind(execution_id) if by_ref[ref].scenario is not None else None,
        )
        for ref in processed
    )


def _execute(
    input_path: Path,
    thresholds: Thresholds,
    *,
    fees: Optional[FeeInputs],
    application_version: str,
    execution_id: str,
    now: datetime,
    quality_config: DataQualityConfig,
) -> tuple[ExecutionRun, tuple[SourcingRecord, ...], ImportResult]:
    input_path = Path(input_path)
    import_result = import_file(input_path, now=now)

    if import_result.fatal:
        run = ExecutionRun(
            execution_id=execution_id,
            started_at=now,
            finished_at=now,
            status=ExecutionStatus.FAILED,
            input_filename=input_path.name,
            input_hash=hash_file(input_path),
            application_version=application_version,
            records_total=0,
            records_processed=0,
            records_successful=0,
            records_with_errors=0,
            warnings=sum(1 for i in import_result.issues if i.level == IssueLevel.WARNING),
        )
        return run, (), import_result

    processed = process_batch(
        import_result.records, thresholds, fees=fees, quality_config=quality_config, now=now
    )

    records_with_errors = sum(1 for r in processed if r.has_record_errors)
    records_successful = len(processed) - records_with_errors
    warnings = sum(1 for r in processed for i in r.issues if i.level == IssueLevel.WARNING)
    warnings += sum(1 for i in import_result.issues if i.level == IssueLevel.WARNING)

    status = ExecutionStatus.SUCCESS if records_with_errors == 0 else ExecutionStatus.PARTIAL_SUCCESS
    if len(processed) == 0:
        status = ExecutionStatus.FAILED

    run = ExecutionRun(
        execution_id=execution_id,
        started_at=now,
        finished_at=now,
        status=status,
        input_filename=input_path.name,
        input_hash=hash_file(input_path),
        application_version=application_version,
        records_total=import_result.rows_scanned,
        records_processed=len(processed),
        records_successful=records_successful,
        records_with_errors=records_with_errors,
        warnings=warnings,
    )
    return run, processed, import_result
