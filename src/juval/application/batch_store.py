"""Persistence port for auditable multi-file Batch groups."""

from __future__ import annotations

from typing import Any, Mapping, NamedTuple, Optional, Protocol, Sequence

from juval.domain.batch import Batch
from juval.domain.execution_run import ExecutionRun


class BatchStore(Protocol):
    def save_batch(self, batch: Batch) -> None:
        """Persist a batch and its ordered file outcomes atomically."""

    def load_batch(self, batch_id: str) -> Optional[Batch]:
        """Return a batch by its opaque grouping identity."""


class RunWrite(NamedTuple):
    """One child run as the store writes it: the same arguments as
    save_execution_run (snapshots and already-serialized payloads)."""

    run: ExecutionRun
    records: Sequence[Mapping[str, Any]] = ()
    financial_records: Sequence[Mapping[str, Any]] = ()
    capture_diagnostics: Sequence[Mapping[str, Any]] = ()


class AtomicBatchStore(Protocol):
    def save_batch_with_runs(self, batch: Batch, runs: Sequence[RunWrite]) -> None:
        """Persist every child run (with its records, financial documents and
        diagnostics) and the batch with its file outcomes in ONE transaction:
        any failure leaves nothing of this call stored (ADR-050)."""
