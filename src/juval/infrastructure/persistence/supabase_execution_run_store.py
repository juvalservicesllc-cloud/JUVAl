"""Postgres/Supabase-backed ExecutionRunStore -- production persistence
(ADR-017).

Implements the same port as `infrastructure/logging/sqlite_execution_run_store.py`
(`application/execution_run_store.py::ExecutionRunStore`) so `interfaces/api/main.py`
can switch between SQLite (local/dev, ADR-013) and this adapter
(production, ADR-017) without any change to `domain/`, `processing/`,
or `application/run_pipeline.py`.

STATUS -- see docs/architecture/SUPABASE.md "Estado": this module is
implemented and its SQL mirrors the accepted schema
(supabase/migrations/20260817000000_execution_runs.sql) exactly, but it
has NOT been integration-tested against a live Postgres/Supabase
instance -- none was available in this environment (no `supabase`/`psql`
reachable, no project credentials provided). Treat it as reviewed code,
not as verified as `SqliteExecutionRunStore` (which has 12 passing
integration tests against real SQLite files, ADR-013).

Uses `psycopg` (a focused PostgreSQL driver, not the full `supabase-py`
SDK) -- a Supabase database is a standard PostgreSQL database, and the
only two operations this port needs (INSERT, SELECT) don't need
Supabase's REST/Auth/Storage/Realtime layers. This keeps the dependency
footprint to one driver instead of a multi-package SDK (CLAUDE.md §20).
`psycopg` is declared as the optional `postgres` extra in pyproject.toml
-- not installed by default, so SQLite/local dev never needs it.
"""

from __future__ import annotations

from typing import Optional

import psycopg

from juval.domain.execution_run import ExecutionRun, ExecutionStatus

_INSERT = """
INSERT INTO execution_runs (
    execution_id, started_at, finished_at, status,
    input_filename, input_hash, application_version,
    records_total, records_processed,
    records_successful, records_with_errors, warnings
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

_SELECT = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs WHERE execution_id = %s
"""


class SupabaseExecutionRunStore:
    """Same contract as `SqliteExecutionRunStore` (ADR-013), backed by a
    Postgres connection string (`postgresql://...`) -- Supabase exposes
    exactly this as its "connection string" / "connection pooling"
    setting, no Supabase-specific SDK needed.

    Does NOT create the schema (unlike `SqliteExecutionRunStore`, which
    runs `CREATE TABLE IF NOT EXISTS` on every construction) -- schema
    changes to a shared production database go through versioned
    migrations only (supabase/migrations/), never an implicit
    CREATE TABLE from application code. See ADR-017.
    """

    def __init__(self, connection_string: str) -> None:
        self._connection_string = connection_string

    def save_execution_run(self, run: ExecutionRun) -> None:
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

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        with psycopg.connect(self._connection_string) as conn:
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
