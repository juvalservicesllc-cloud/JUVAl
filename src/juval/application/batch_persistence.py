"""Atomic persistence of a whole batch (ADR-050 unit 1; ADR-025 grouping).

`save_batch_with_runs` stores, in one store transaction, every child
ExecutionRun with its record snapshots, financial documents and capture
diagnostics, and the Batch with its ordered file outcomes. Any failure leaves
nothing of the call stored: there are no compensating deletes.

Before anything is written it checks that the batch and its children describe
the same executions: every file that names an execution_id has exactly one
child run, every child run is named by exactly one file, and a REJECTED file
names none. Documents and diagnostics are validated and serialized by
financial_persistence.financial_payloads, the same rules as a single run.

Not wired to any endpoint yet: POST /api/v1/batches still saves child by child.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from juval.application.batch_store import AtomicBatchStore, RunWrite
from juval.application.capture_diagnostics import RecordCaptureDiagnostics
from juval.application.financial_persistence import AnyFinancialRecord, financial_payloads
from juval.domain.batch import Batch, BatchFileStatus
from juval.domain.execution_run import ExecutionRun


class BatchIntegrityError(ValueError):
    """The batch and its child runs do not describe the same executions."""


@dataclass(frozen=True)
class BatchChild:
    """One processed file's run with what is stored for it."""

    run: ExecutionRun
    snapshots: Sequence[Mapping[str, Any]] = ()
    documents: Sequence[AnyFinancialRecord] = ()
    capture_diagnostics: Sequence[RecordCaptureDiagnostics] = ()


def save_batch_with_runs(store: AtomicBatchStore, batch: Batch, children: Sequence[BatchChild]) -> None:
    child_ids = Counter(child.run.execution_id for child in children)
    named = Counter(file.execution_id for file in batch.files if file.execution_id is not None)
    for file in batch.files:
        if file.status is BatchFileStatus.REJECTED and file.execution_id is not None:
            raise BatchIntegrityError(f"rejected file {file.ordinal} names an execution")
    repeated = sorted({i for i, n in child_ids.items() if n > 1} | {i for i, n in named.items() if n > 1})
    if repeated:
        raise BatchIntegrityError(f"executions appear more than once: {repeated}")
    if set(child_ids) != set(named):
        raise BatchIntegrityError(
            f"children without a batch file: {sorted(set(child_ids) - set(named))}; "
            f"batch files without a child: {sorted(set(named) - set(child_ids))}")
    writes = []
    for child in children:  # raises FinancialRecordIntegrityError, naming the execution, before any write
        payloads, diagnostics = financial_payloads(child.run, child.snapshots, child.documents,
                                                   child.capture_diagnostics)
        writes.append(RunWrite(child.run, child.snapshots, payloads, diagnostics))
    store.save_batch_with_runs(batch, writes)
