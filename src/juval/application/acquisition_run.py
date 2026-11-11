"""Run the pipeline, consult authorized sources and persist it all at once (ADR-058).

`run_and_persist_with_acquisition` is the only way connectors are invoked, and
it always persists: a `persist=false` run cannot consult an external source
(PD-7). `run_pipeline` itself is unchanged and never calls a connector.

Order and boundaries:

1. The configuration is fixed before any request (ADR-058 §5.1).
2. The existing pipeline runs exactly as without acquisition. Decisions,
   DecisionInputs and Product never see acquired values (ADR-052 §20.3, I6).
3. Each connector is consulted for the records its contract finds eligible.
   A FAILED run consults nothing (`RUN_FAILED_BEFORE_ACQUISITION`).
4. Acquired values are attached to their record snapshot as the
   `acquired_evidence` document; value counts are derived from those
   snapshots, never declared by an adapter (ADR-058 §7).
5. Run, snapshots and both documents are written by one store call, in one
   transaction (P1). An exception at any step persists nothing (P8): the
   registry describes persisted runs only and is not an attempt log.

`ExecutionRun.status` keeps its meaning: SUCCESS is processing success, not
acquisition success; acquisition failures are only counted (PD-8 pending).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from juval.application.acquisition_documents import (
    ACQUIRED_EVIDENCE_KEY,
    acquired_evidence_document,
    derive_value_counts,
)
from juval.application.execution_run_store import ExecutionRunStore
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.application.tenancy import Ownership
from juval.domain.acquisition import (
    AcquisitionConfiguration,
    AcquisitionExecution,
    AcquisitionRecord,
    FailureCategory,
    ItemCounts,
    ItemOutcome,
    NotConsultedReason,
    SourceExecution,
    ValueCounts,
)
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.sourcing_record import SourcingRecord
from juval.processing.acquisition_port import AcquisitionItem, AuthorizedConnector, SourceAcquisitionResult
from juval.processing.data_quality import DataQualityConfig


class ConnectorResultError(ValueError):
    """A connector answered for records it was not asked about, or skipped one."""


@dataclass(frozen=True)
class AcquiredRun:
    run: ExecutionRun
    records: tuple[SourcingRecord, ...]
    snapshots: tuple[dict[str, Any], ...]
    acquisition: AcquisitionRecord


def run_and_persist_with_acquisition(
    input_path: Path,
    thresholds: Thresholds,
    *,
    connectors: Sequence[AuthorizedConnector],
    store: ExecutionRunStore,
    application_version: str,
    execution_id: str,
    now: datetime,
    owner: Optional[Ownership] = None,
    fees: Optional[FeeInputs] = None,
    quality_config: DataQualityConfig = DataQualityConfig(),
) -> AcquiredRun:
    configuration = AcquisitionConfiguration(now, tuple(connector.source for connector in connectors))
    run, records = run_pipeline(
        input_path, thresholds, fees=fees, application_version=application_version,
        execution_id=execution_id, now=now, quality_config=quality_config)

    results: dict[str, SourceAcquisitionResult] = {}
    reasons: dict[str, NotConsultedReason] = {}
    for connector in connectors:
        source_id = connector.source.source_id
        if run.status is ExecutionStatus.FAILED:
            reasons[source_id] = NotConsultedReason.RUN_FAILED_BEFORE_ACQUISITION
            continue
        items = [AcquisitionItem(record.record_ref, identifier) for record in records
                 if (identifier := connector.identifier_for(record)) is not None]
        if not items:
            reasons[source_id] = NotConsultedReason.NO_ELIGIBLE_RECORDS
            continue
        results[source_id] = _checked_result(connector.acquire(items), source_id, items)

    acquired: dict[str, list[tuple[str, str, Any]]] = {}
    for source_id, result in sorted(results.items()):
        for item in result.items:
            acquired.setdefault(item.record_ref, []).extend(
                (source_id, value.field, value.value) for value in item.values)
    snapshots = tuple(_snapshot(record, acquired.get(record.record_ref, ())) for record in records)
    derived = derive_value_counts(snapshots)
    execution = AcquisitionExecution(tuple(
        _source_execution(source.source_id, results.get(source.source_id), reasons.get(source.source_id),
                          derived.get(source.source_id, ValueCounts(0, 0, 0)))
        for source in configuration.sources))
    acquisition = AcquisitionRecord(configuration, execution)
    store.save_execution_run(run, snapshots, owner=owner, acquisition=acquisition)
    return AcquiredRun(run, records, snapshots, acquisition)


def _checked_result(result: SourceAcquisitionResult, source_id: str,
                    items: Sequence[AcquisitionItem]) -> SourceAcquisitionResult:
    if result.source_id != source_id:
        raise ConnectorResultError(f"connector of {source_id} answered as {result.source_id}")
    if [item.record_ref for item in result.items] != [item.record_ref for item in items]:
        raise ConnectorResultError(f"{source_id} must return exactly one result per requested item, in order")
    return result


def _snapshot(record: SourcingRecord, values: Sequence[tuple[str, str, Any]]) -> dict[str, Any]:
    snapshot = record_to_snapshot(record)
    if values:
        snapshot[ACQUIRED_EVIDENCE_KEY] = acquired_evidence_document(values)
    return snapshot


def _source_execution(source_id: str, result: Optional[SourceAcquisitionResult],
                      reason: Optional[NotConsultedReason], values: ValueCounts) -> SourceExecution:
    if result is None:
        return SourceExecution(source_id, None, None, 0, 0, ItemCounts.empty(), values, 0, reason)
    outcomes = [item.outcome for item in result.items]
    failed = {category: 0 for category in FailureCategory}
    for item in result.items:
        if item.failure is not None:
            failed[item.failure] += 1
    return SourceExecution(
        source_id=source_id,
        first_request_at=result.first_request_at,
        last_request_at=result.last_request_at,
        requests_sent=result.requests_sent,
        retries=result.retries,
        items=ItemCounts(
            requested=len(result.items),
            with_evidence=outcomes.count(ItemOutcome.WITH_EVIDENCE),
            no_evidence=outcomes.count(ItemOutcome.NO_EVIDENCE),
            rejected=outcomes.count(ItemOutcome.REJECTED),
            failed=failed,
        ),
        values=values,
        observation_contract_rejected=sum(item.observation_contract_rejected for item in result.items),
        not_consulted_reason=reason,
    )
