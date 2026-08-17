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

from datetime import datetime
from pathlib import Path
from typing import Optional

from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.execution_run import ExecutionRun, ExecutionStatus, hash_file
from juval.domain.issues import IssueLevel
from juval.domain.sourcing_record import SourcingRecord
from juval.infrastructure.excel.importer import import_excel
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
    input_path = Path(input_path)
    import_result = import_excel(input_path, now=now)

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
        return run, ()

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
    return run, processed
