"""SQLite-backed ExecutionRunStore — local, single-user persistence for
ExecutionRun audit records and (ADR-019) their run-scoped record
snapshots.

Implements application/execution_run_store.py::ExecutionRunStore and
application/record_snapshot_store.py::RecordSnapshotStore. See ADR-013
(Estado: Aceptada) for the original ExecutionRun-only scope, and
ADR-019 (Estado: Aceptada) for record snapshots + listing.

Schema: two tables. `execution_runs`, `execution_id` as PRIMARY KEY
(ADR-013, unchanged). `execution_run_records` (ADR-019),
`(execution_id, record_ref)` as PRIMARY KEY — matches ADR-012's "unique
only within one execution", never a global product identity — with a
FOREIGN KEY to `execution_runs(execution_id)` so a record snapshot can
never exist for a run that was never saved. `CREATE TABLE IF NOT
EXISTS` is run on every store construction — intentionally the entire
"migration strategy" for this phase (same as ADR-013).

`snapshot` is stored as a JSON TEXT column — the exact dict
`application/record_snapshot.py::record_to_snapshot()` produces,
serialized with `json.dumps`/deserialized with `json.loads`. Never
`repr()`, never pickle.

Timestamps are stored as ISO 8601 strings (`datetime.isoformat()` /
`datetime.fromisoformat()`), which round-trip timezone-aware datetimes
exactly. `status` is stored as its enum `.value` string. `finished_at`
is stored as SQL NULL when the domain object's `finished_at` is None
(status == RUNNING).

Atomicity (ADR-019): `save_execution_run` writes the `execution_runs`
row and every `execution_run_records` row inside the same `with conn:`
block -- sqlite3's context manager commits once at the end or rolls
back everything on any exception, so a run is never left half-saved.

Concurrency: not designed for multi-writer use. Each operation opens and
closes its own short-lived connection with SQLite's default settings
(no WAL, no custom timeout) — sufficient for a single local user running
sequential pipeline executions; not a decision for multi-user/remote
access, which is out of scope (see ADR-013).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

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

_RECORDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_run_records (
    execution_id TEXT NOT NULL REFERENCES execution_runs(execution_id),
    ordinal INTEGER NOT NULL,
    record_ref TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    PRIMARY KEY (execution_id, record_ref)
)
"""

_RECORDS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_execution_run_records_order
    ON execution_run_records (execution_id, ordinal)
"""

_INSERT = """
INSERT INTO execution_runs (
    execution_id, started_at, finished_at, status,
    input_filename, input_hash, application_version,
    records_total, records_processed,
    records_successful, records_with_errors, warnings
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_RECORD = """
INSERT INTO execution_run_records (execution_id, ordinal, record_ref, snapshot)
VALUES (?, ?, ?, ?)
"""

_SELECT = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs WHERE execution_id = ?
"""

_SELECT_LIST = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs ORDER BY started_at DESC LIMIT ?
"""

_SELECT_RECORDS = """
SELECT snapshot FROM execution_run_records
WHERE execution_id = ? ORDER BY ordinal ASC
"""


def _row_to_run(row: tuple) -> ExecutionRun:
    (
        execution_id,
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
        execution_id=execution_id,
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


class SqliteExecutionRunStore:
    """Single-user, local SQLite persistence for ExecutionRun and
    (ADR-019) its record snapshots.

    `execution_id` (not `record_ref`) is the primary key of
    `execution_runs` — the two are distinct concepts: `record_ref`
    identifies a row within one import (ADR-012), `execution_id`
    identifies one pipeline run (this store).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        with closing(sqlite3.connect(self._db_path)) as conn:
            with conn:
                conn.execute(_SCHEMA)
                conn.execute(_RECORDS_SCHEMA)
                conn.execute(_RECORDS_INDEX)

    def save_execution_run(self, run: ExecutionRun, records: Sequence[Mapping[str, Any]] = ()) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
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
                for ordinal, record in enumerate(records):
                    conn.execute(
                        _INSERT_RECORD,
                        (run.execution_id, ordinal, record["record_ref"], json.dumps(record)),
                    )

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(_SELECT, (execution_id,)).fetchone()
        return _row_to_run(row) if row is not None else None

    def list_execution_runs(self, limit: int = 20) -> list[ExecutionRun]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(_SELECT_LIST, (limit,)).fetchall()
        return [_row_to_run(row) for row in rows]

    def load_records(self, execution_id: str) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            rows = conn.execute(_SELECT_RECORDS, (execution_id,)).fetchall()
        return [json.loads(snapshot) for (snapshot,) in rows]
