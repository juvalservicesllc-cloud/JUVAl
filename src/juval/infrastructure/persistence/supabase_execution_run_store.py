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
from decimal import Decimal, InvalidOperation

import psycopg
from psycopg.types.json import Json

from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.application.record_snapshot_store import RecordSnapshotPage, RecordSnapshotQuery

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

_SORT_EXPRESSIONS = {
    "record_ref": "record_ref",
    "sku": "snapshot->>'supplier_sku'",
    "decision": "snapshot->>'decision'",
    "profit": "NULLIF(snapshot->'profit'->>'value', '')::numeric",
    "roi": "NULLIF(snapshot->'roi'->>'value', '')::numeric",
    "margin": "NULLIF(snapshot->'margin'->>'value', '')::numeric",
}


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

    def list_records(self, execution_id: str, query: RecordSnapshotQuery) -> RecordSnapshotPage:
        clauses = ["execution_id = %s"]
        params: list[Any] = [execution_id]
        if query.decision is not None:
            clauses.append("snapshot->>'decision' = %s")
            params.append(query.decision)
        if query.search:
            clauses.append("(record_ref ILIKE %s OR snapshot->>'supplier_sku' ILIKE %s OR snapshot->'title'->>'value' ILIKE %s OR snapshot->'brand'->>'value' ILIKE %s OR snapshot->'asin'->>'value' ILIKE %s)")
            params.extend([f"%{query.search}%"] * 5)
        where = " AND ".join(clauses)
        expression = _SORT_EXPRESSIONS[query.sort]
        order = query.direction.upper()
        sql = f"SELECT snapshot FROM execution_run_records WHERE {where} ORDER BY {expression} {order} NULLS LAST, ordinal ASC LIMIT %s OFFSET %s"
        count_sql = f"SELECT COUNT(*) FROM execution_run_records WHERE {where}"
        with psycopg.connect(self._connection_string) as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(sql, [*params, query.limit, query.offset]).fetchall()
        return RecordSnapshotPage(items=[snapshot for (snapshot,) in rows], total=total)

    def get_run_analytics(self, execution_id: str) -> dict[str, Any]:
        fields = ("asin", "weight", "selling_price", "profit", "roi", "margin")
        with psycopg.connect(self._connection_string) as conn:
            total = conn.execute("SELECT COUNT(*) FROM execution_run_records WHERE execution_id=%s", (execution_id,)).fetchone()[0]
            def grouped(expression):
                return {str(k) if k is not None else "UNKNOWN": n for k, n in conn.execute(f"SELECT {expression}, COUNT(*) FROM execution_run_records WHERE execution_id=%s GROUP BY {expression}", (execution_id,))}
            decisions = grouped("snapshot->>'decision'")
            risks = {name: {"status": grouped(f"snapshot->>'{name}_status'"), "severity": grouped(f"snapshot->>'{name}_severity'")} for name in ("hazmat", "bulky")}
            provenance = {field: grouped(f"snapshot->'{field}'->>'status'") for field in fields}
            quality = conn.execute("SELECT COALESCE(SUM(CASE WHEN (snapshot->>'issue_count')::int>0 THEN 1 ELSE 0 END),0), COALESCE(SUM((snapshot->>'issue_count')::int),0) FROM execution_run_records WHERE execution_id=%s", (execution_id,)).fetchone()
            profitability = {}
            for field in ("profit", "roi", "margin"):
                rows = conn.execute(f"SELECT snapshot->'{field}'->>'value' FROM execution_run_records WHERE execution_id=%s AND snapshot->'{field}'->>'status'='VERIFIED'", (execution_id,)).fetchall()
                values = []
                for (raw,) in rows:
                    try: values.append(Decimal(raw))
                    except (InvalidOperation, TypeError): pass
                profitability[field] = {"count": len(values), "sum": str(sum(values)) if values else None, "average": str(sum(values) / len(values)) if values else None, "minimum": str(min(values)) if values else None, "maximum": str(max(values)) if values else None}
        return {"records": {"total_records": total}, "decisions": decisions, "risks": risks, "provenance": provenance, "data_quality": {"records_with_issues": quality[0], "total_issue_count": quality[1]}, "profitability": profitability}
