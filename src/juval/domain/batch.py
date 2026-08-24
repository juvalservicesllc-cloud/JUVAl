"""Run grouping for a multi-file submission.

`ExecutionRun` remains one deterministic input unit. A Batch only groups the
independent child runs and their file outcomes; it never becomes a product or
record identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional


class BatchStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class BatchFileStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class BatchFile:
    ordinal: int
    filename: str
    content_type: Optional[str]
    size_bytes: int
    status: BatchFileStatus
    execution_id: Optional[str]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    # Row/record outcome copied from this file's own child ExecutionRun, so the
    # batch view can report per-file counts without re-reading every child run.
    # A REJECTED file never produced a run, so its counts stay 0 -- that is an
    # accurate "never processed", not a measured zero.
    records_total: int = 0
    records_processed: int = 0
    records_with_errors: int = 0
    warning_count: int = 0


@dataclass(frozen=True)
class Batch:
    batch_id: str
    created_at: datetime
    status: BatchStatus
    files: tuple[BatchFile, ...]

    @property
    def succeeded_files(self) -> int:
        return sum(file.status in {BatchFileStatus.SUCCESS, BatchFileStatus.PARTIAL_SUCCESS} for file in self.files)

    @property
    def failed_files(self) -> int:
        return sum(file.status in {BatchFileStatus.FAILED, BatchFileStatus.REJECTED} for file in self.files)

    @property
    def records_total(self) -> int:
        return sum(file.records_total for file in self.files)

    @property
    def records_processed(self) -> int:
        return sum(file.records_processed for file in self.files)

    @property
    def records_with_errors(self) -> int:
        return sum(file.records_with_errors for file in self.files)

    @property
    def warning_count(self) -> int:
        return sum(file.warning_count for file in self.files)


def aggregate_batch_status(files: tuple[BatchFile, ...]) -> BatchStatus:
    if not files or all(file.status in {BatchFileStatus.FAILED, BatchFileStatus.REJECTED} for file in files):
        return BatchStatus.FAILED
    if any(file.status != BatchFileStatus.SUCCESS for file in files):
        return BatchStatus.PARTIAL_SUCCESS
    return BatchStatus.SUCCESS
