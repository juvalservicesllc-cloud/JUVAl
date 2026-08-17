"""Postgres/Supabase-backed ExecutionRunStore -- production persistence
(ADR-017), extended (ADR-019) with run-scoped record snapshots.

Implements the same ports as `infrastructure/logging/sqlite_execution_run_store.py`
(`application/execution_run_store.py::ExecutionRunStore` and
`application/record_snapshot_store.py::RecordSnapshotStore`) so
`interfaces/api/main.py` can switch between SQLite (local/dev,
ADR-013/ADR-019) and this adapter (production, ADR-017/ADR-019)
without any change to `domain/`, `processing/`, or
`application/run_pipeline.py`.

STATUS -- see docs/architecture/SUPABASE.md "Estado": the ExecutionRun
half of this module is verified against a live Supabase project (real
INSERT/SELECT/cleanup integration test). The record-snapshot half
(ADR-019) mirrors the same schema/query pattern and is covered by
structural tests only, same caveat as the rest of this module before
its own integration test existed -- see docs/architecture/SUPABASE.md.

Uses `psycopg` (a focused PostgreSQL driver, not the full `supabase-py`
SDK) -- a Supabase database is a standard PostgreSQL database, and the
operations this port needs (INSERT, SELECT) don't need Supabase's
REST/Auth/Storage/Realtime layers. `psycopg` is declared as the
optional `postgres` extra in pyproject.toml -- not installed by
default, so SQLite/local dev never needs it.

Atomicity (ADR-019): `save_execution_run` writes the `execution_runs`
row and every `execution_run_records` row over the same connection,
inside one transaction (`with psycopg.connect(...) as conn:` --
psycopg commits on clean exit, rolls back on any exception) -- a run is
never left half-saved.

`snapshot` is stored as `JSONB` (Postgres' native type for exactly this
kind of structured JSON payload) -- psycopg adapts a Python dict to
JSONB automatically via `psycopg.types.json.Json`.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

import psycopg
from psycopg.types.json import Json

from juval.domain.execution_run import ExecutionRun, ExecutionStatus

_INSERT = """
INSERT INTO execution_runs (
    execution_id, started_at, finished_at, status,
    input_filename, input_hash, application_version,
    records_total, records_processed,
    records_successful, records_with_errors, warnings
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_RECORD = """
INSERT INTO execution_run_records (execution_id, ordinal, record_ref, snapshot)
VALUES (%s, %s, %s, %s)
"""

_SELECT = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs WHERE execution_id = %s
"""

_SELECT_LIST = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs ORDER BY started_at DESC LIMIT %s
"""

_SELECT_RECORDS = """
SELECT snapshot FROM execution_run_records
WHERE execution_id = %s ORDER BY ordinal ASC
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
        started_at=started_at,
        finished_at=finished_at,
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


class SupabaseExecutionRunStore:
    """Same contract as `SqliteExecutionRunStore` (ADR-013/ADR-019),
    backed by a Postgres connection string (`postgresql://...`) -- Supabase
    exposes exactly this as its "connection string" / "connection pooling"
    setting, no Supabase-specific SDK needed.

    Does NOT create the schema (unlike `SqliteExecutionRunStore`, which
    runs `CREATE TABLE IF NOT EXISTS` on every construction) -- schema
    changes to a shared production database go through versioned
    migrations only (supabase/migrations/), never an implicit
    CREATE TABLE from application code. See ADR-017.
    """

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    def save_execution_run(self, run: ExecutionRun, records: Sequence[Mapping[str, Any]] = ()) -> None:
        with psycopg.connect(self._connection_string) as conn:
            conn.execute(
                _INSERT,
                (
                    run.execution_id,
                    run.started_at,
                    run.finished_at,
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
                    (run.execution_id, ordinal, record["record_ref"], Json(dict(record))),
                )

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        with psycopg.connect(self._connection_string) as conn:
            row = conn.execute(_SELECT, (execution_id,)).fetchone()
        return _row_to_run(row) if row is not None else None

    def list_execution_runs(self, limit: int = 20) -> list[ExecutionRun]:
        with psycopg.connect(self._connection_string) as conn:
            rows = conn.execute(_SELECT_LIST, (limit,)).fetchall()
        return [_row_to_run(row) for row in rows]

    def load_records(self, execution_id: str) -> list[dict[str, Any]]:
        with psycopg.connect(self._connection_string) as conn:
            rows = conn.execute(_SELECT_RECORDS, (execution_id,)).fetchall()
        return [snapshot for (snapshot,) in rows]
