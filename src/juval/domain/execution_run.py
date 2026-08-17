"""ExecutionRun — audit/reproducibility record for one pipeline run.

This dataclass itself stays infrastructure-free (no sqlite3, no SQL, no
filesystem) — persisting it across runs is implemented behind the
`ExecutionRunStore` port (application/execution_run_store.py) by
`infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore`
(local SQLite, ADR-013, `Estado: Aceptada`). `run_pipeline()` does not
invoke the store automatically (Opción B, ADR-013) — the caller decides
explicitly when to persist a run.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ExecutionRun:
    execution_id: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: ExecutionStatus
    input_filename: str
    input_hash: str
    application_version: str
    records_total: int
    records_processed: int
    records_successful: int
    records_with_errors: int
    warnings: int

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("ExecutionRun.execution_id must not be empty")
        if self.started_at.tzinfo is None:
            raise ValueError("ExecutionRun.started_at must be timezone-aware")
        if self.finished_at is not None:
            if self.finished_at.tzinfo is None:
                raise ValueError("ExecutionRun.finished_at must be timezone-aware")
            if self.finished_at < self.started_at:
                raise ValueError("ExecutionRun.finished_at must not precede started_at")
        for name in ("records_total", "records_processed", "records_successful", "records_with_errors", "warnings"):
            if getattr(self, name) < 0:
                raise ValueError(f"ExecutionRun.{name} must not be negative")
        if self.records_processed > self.records_total:
            raise ValueError("ExecutionRun.records_processed must not exceed records_total")
        if self.records_successful + self.records_with_errors > self.records_processed:
            raise ValueError(
                "ExecutionRun.records_successful + records_with_errors must not exceed records_processed"
            )
        if self.status == ExecutionStatus.RUNNING and self.finished_at is not None:
            raise ValueError("ExecutionRun.status=RUNNING must not carry a finished_at")
        if self.status != ExecutionStatus.RUNNING and self.finished_at is None:
            raise ValueError(f"ExecutionRun.status={self.status.value} requires a finished_at")


def hash_file(path: Path) -> str:
    """SHA-256 of the file's raw bytes — used as ExecutionRun.input_hash so
    two runs can be compared to confirm they used the literal same input,
    not just a file with the same name."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
