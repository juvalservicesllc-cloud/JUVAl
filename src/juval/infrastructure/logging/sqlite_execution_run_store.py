"""SQLite-backed ExecutionRunStore — local, single-user persistence for
ExecutionRun audit records.

Implements application/execution_run_store.py::ExecutionRunStore. See
ADR-013 (Estado: Aceptada) for scope, alternatives considered, and what
this decision deliberately does NOT resolve (thresholds/sources_used
capture, multi-user/remote access, wiring into run_pipeline).

Schema: one table, `execution_runs`, `execution_id` as PRIMARY KEY.
`CREATE TABLE IF NOT EXISTS` is run on every store construction — this
is intentionally the entire "migration strategy" for this phase (a
single table, no prior versions to migrate from). Any future structural
change to ExecutionRun (e.g. adding thresholds/sources_used) will need
an explicit migration strategy at that time; this module does not
provide one.

Timestamps are stored as ISO 8601 strings (`datetime.isoformat()` /
`datetime.fromisoformat()`), which round-trip timezone-aware datetimes
exactly. `status` is stored as its enum `.value` string. `finished_at`
is stored as SQL NULL when the domain object's `finished_at` is None
(status == RUNNING).

Concurrency: not designed for multi-writer use. Each operation opens and
closes its own short-lived connection with SQLite's default settings
(no WAL, no custom timeout) — sufficient for a single local user running
sequential pipeline executions; not a decision for multi-user/remote
access, which is out of scope (see ADR-013).
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional

from juval.domain.execution_run import ExecutionRun, ExecutionStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_runs (
    execution_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    input_filename TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    application_version TEXT NOT NULL,
    records_total INTEGER NOT NULL,
    records_processed INTEGER NOT NULL,
    records_successful INTEGER NOT NULL,
    records_with_errors INTEGER NOT NULL,
    warnings INTEGER NOT NULL
)
"""

_INSERT = """
INSERT INTO execution_runs (
    execution_id, started_at, finished_at, status,
    input_filename, input_hash, application_version,
    records_total, records_processed,
    records_successful, records_with_errors, warnings
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs WHERE execution_id = ?
"""


class SqliteExecutionRunStore:
    """Single-user, local SQLite persistence for ExecutionRun.

    `execution_id` (not `record_ref`) is the primary key — the two are
    distinct concepts: `record_ref` identifies a row within one import
    (ADR-012), `execution_id` identifies one pipeline run (this store).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        with closing(sqlite3.connect(self._db_path)) as conn:
            with conn:
                conn.execute(_SCHEMA)

    def save_execution_run(self, run: ExecutionRun) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            with conn:
                conn.execute(
                    _INSERT,
                    (
                        run.execution_id,
                        run.started_at.isoformat(),
                        run.finished_at.isoformat() if run.finished_at is not None else None,
                        run.status.value,
                        run.input_filename,
                        run.input_hash,
                        run.application_version,
                        run.records_total,
                        run.records_processed,
                        run.records_successful,
                        run.records_with_errors,
                        run.warnings,
                    ),
                )

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(_SELECT, (execution_id,)).fetchone()

        if row is None:
            return None

        (
            row_execution_id,
            started_at,
            finished_at,
            status,
            input_filename,
            input_hash,
            application_version,
            records_total,
            records_processed,
            records_successful,
            records_with_errors,
            warnings,
        ) = row

        return ExecutionRun(
            execution_id=row_execution_id,
            started_at=datetime.fromisoformat(started_at),
            finished_at=datetime.fromisoformat(finished_at) if finished_at is not None else None,
            status=ExecutionStatus(status),
            input_filename=input_filename,
            input_hash=input_hash,
            application_version=application_version,
            records_total=records_total,
            records_processed=records_processed,
            records_successful=records_successful,
            records_with_errors=records_with_errors,
            warnings=warnings,
        )
