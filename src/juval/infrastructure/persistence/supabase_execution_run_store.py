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
default, so SQLite/local dev never needs it. The driver is therefore
imported lazily (`_require_driver`, called from `_connect`): importing
this module, and constructing the store, must work without it -- only
opening a connection genuinely requires it.

Atomicity (ADR-019): `save_execution_run` writes the `execution_runs`
row and every `execution_run_records` row over the same connection,
inside one transaction (`with self._connect() as conn:` --
psycopg commits on clean exit, rolls back on any exception) -- a run is
never left half-saved.

`snapshot` is stored as `JSONB` (Postgres' native type for exactly this
kind of structured JSON payload) -- psycopg adapts a Python dict to
JSONB automatically via `psycopg.types.json.Json`.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence


from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.application.record_snapshot_store import RecordSnapshotPage, RecordSnapshotQuery
from juval.application.run_analytics import brand_distribution, issue_types, numeric_summary, price_spread

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

_SELECT_RECORD = """
SELECT snapshot FROM execution_run_records
WHERE execution_id = %s AND record_ref = %s
"""

_BATCH_FILE_COLUMNS = (
    "ordinal, filename, content_type, size_bytes, status, execution_id, warnings, errors, "
    "records_total, records_processed, records_with_errors, warning_count"
)

_SORT_EXPRESSIONS = {
    "record_ref": "record_ref",
    "sku": "snapshot->>'supplier_sku'",
    "asin": "snapshot->'asin'->>'value'",
    "title": "snapshot->'title'->>'value'",
    "price": "NULLIF(snapshot->'selling_price'->>'value', '')::numeric",
    "cog": "NULLIF(snapshot->>'cog', '')::numeric",
    "decision": "snapshot->>'decision'",
    "profit": "NULLIF(snapshot->'profit'->>'value', '')::numeric",
    "roi": "NULLIF(snapshot->'roi'->>'value', '')::numeric",
    "margin": "NULLIF(snapshot->'margin'->>'value', '')::numeric",
    "hazmat": "snapshot->>'hazmat_status'",
    "bulky": "snapshot->>'bulky_status'",
}


def _require_driver():
    """Import the optional PostgreSQL driver, or say exactly how to install it.

    `psycopg` is the `postgres` extra (ADR-017), not a base dependency: the
    default store is SQLite (ADR-013). Importing this module -- and therefore
    `interfaces/api/main.py`, which imports it only to *choose* between the two
    stores -- must never require the driver. Only opening a connection does.
    """
    try:
        import psycopg
        from psycopg.types.json import Json
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "SupabaseExecutionRunStore needs the optional PostgreSQL driver. "
            "Install it with: pip install -e \".[postgres]\""
        ) from exc
    return psycopg, Json


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

    def _connect(self):
        psycopg, _ = _require_driver()
        return psycopg.connect(self._connection_string)

    def save_execution_run(self, run: ExecutionRun, records: Sequence[Mapping[str, Any]] = ()) -> None:
        _, Json = _require_driver()
        with self._connect() as conn:
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
        with self._connect() as conn:
            row = conn.execute(_SELECT, (execution_id,)).fetchone()
        return _row_to_run(row) if row is not None else None

    def list_execution_runs(self, limit: int = 20) -> list[ExecutionRun]:
        with self._connect() as conn:
            rows = conn.execute(_SELECT_LIST, (limit,)).fetchall()
        return [_row_to_run(row) for row in rows]

    def load_records(self, execution_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(_SELECT_RECORDS, (execution_id,)).fetchall()
        return [snapshot for (snapshot,) in rows]

    def load_record(self, execution_id: str, record_ref: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(_SELECT_RECORD, (execution_id, record_ref)).fetchone()
        return row[0] if row is not None else None

    def save_batch(self, batch: Batch) -> None:
        _, Json = _require_driver()
        with self._connect() as conn:
            conn.execute("INSERT INTO batches (batch_id, created_at, status) VALUES (%s, %s, %s)", (batch.batch_id, batch.created_at, batch.status.value))
            for file in batch.files:
                conn.execute(
                    f"INSERT INTO batch_files (batch_id, {_BATCH_FILE_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (batch.batch_id, file.ordinal, file.filename, file.content_type, file.size_bytes, file.status.value, file.execution_id, Json(list(file.warnings)), Json(list(file.errors)), file.records_total, file.records_processed, file.records_with_errors, file.warning_count),
                )

    def load_batch(self, batch_id: str) -> Optional[Batch]:
        with self._connect() as conn:
            row = conn.execute("SELECT batch_id, created_at, status FROM batches WHERE batch_id = %s", (batch_id,)).fetchone()
            if row is None:
                return None
            files = conn.execute(f"SELECT {_BATCH_FILE_COLUMNS} FROM batch_files WHERE batch_id = %s ORDER BY ordinal", (batch_id,)).fetchall()
        batch_files = tuple(
            BatchFile(ordinal, filename, content_type, size_bytes, BatchFileStatus(status), execution_id, tuple(warnings), tuple(errors), records_total, records_processed, records_with_errors, warning_count)
            for ordinal, filename, content_type, size_bytes, status, execution_id, warnings, errors, records_total, records_processed, records_with_errors, warning_count in files
        )
        return Batch(batch_id=row[0], created_at=row[1], status=BatchStatus(row[2]), files=batch_files)

    def load_batch_for_run(self, execution_id: str) -> Optional[Batch]:
        """The batch a child run belongs to, or None when it ran on its own."""
        with self._connect() as conn:
            row = conn.execute("SELECT batch_id FROM batch_files WHERE execution_id = %s LIMIT 1", (execution_id,)).fetchone()
        return self.load_batch(row[0]) if row is not None else None

    def list_records(self, execution_id: str, query: RecordSnapshotQuery) -> RecordSnapshotPage:
        clauses = ["execution_id = %s"]
        params: list[Any] = [execution_id]
        if query.decision is not None:
            clauses.append("snapshot->>'decision' = %s")
            params.append(query.decision)
        if query.search:
            clauses.append("(record_ref ILIKE %s OR snapshot->>'supplier_sku' ILIKE %s OR snapshot->'title'->>'value' ILIKE %s OR snapshot->'brand'->>'value' ILIKE %s OR snapshot->'asin'->>'value' ILIKE %s)")
            params.extend([f"%{query.search}%"] * 5)
        for field, minimum in (("roi", query.min_roi), ("profit", query.min_profit), ("margin", query.min_margin)):
            if minimum is not None:
                statuses = ("VERIFIED",) if query.confidence == "VERIFIED_ONLY" else ("VERIFIED", "INFERRED")
                placeholders = ",".join("%s" for _ in statuses)
                clauses.append(f"snapshot->'{field}'->>'status' IN ({placeholders}) AND (snapshot->'{field}'->>'value')::numeric >= %s")
                params.extend([*statuses, minimum])
        if query.hazmat is not None:
            clauses.append("snapshot->>'hazmat_status' = %s")
            params.append(query.hazmat)
        if query.bulky is not None:
            clauses.append("snapshot->>'bulky_status' = %s")
            params.append(query.bulky)
        if query.provenance_field is not None and query.provenance_status is not None:
            clauses.append(f"snapshot->'{query.provenance_field}'->>'status' = %s")
            params.append(query.provenance_status)
        where = " AND ".join(clauses)
        expression = _SORT_EXPRESSIONS[query.sort]
        order = query.direction.upper()
        sql = f"SELECT snapshot FROM execution_run_records WHERE {where} ORDER BY {expression} {order} NULLS LAST, ordinal ASC LIMIT %s OFFSET %s"
        count_sql = f"SELECT COUNT(*) FROM execution_run_records WHERE {where}"
        with self._connect() as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(sql, [*params, query.limit, query.offset]).fetchall()
        return RecordSnapshotPage(items=[snapshot for (snapshot,) in rows], total=total)

    def get_run_analytics(self, execution_id: str) -> dict[str, Any]:
        fields = ("asin", "weight", "selling_price", "profit", "roi", "margin")
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM execution_run_records WHERE execution_id=%s", (execution_id,)).fetchone()[0]
            def grouped(expression):
                return {str(k) if k is not None else "UNKNOWN": n for k, n in conn.execute(f"SELECT {expression}, COUNT(*) FROM execution_run_records WHERE execution_id=%s GROUP BY {expression}", (execution_id,))}
            decisions = grouped("snapshot->>'decision'")
            risks = {name: {"status": grouped(f"snapshot->>'{name}_status'"), "severity": grouped(f"snapshot->>'{name}_severity'")} for name in ("hazmat", "bulky")}
            provenance = {field: grouped(f"snapshot->'{field}'->>'status'") for field in fields}
            quality = conn.execute("SELECT COALESCE(SUM(CASE WHEN (snapshot->>'issue_count')::int>0 THEN 1 ELSE 0 END),0), COALESCE(SUM((snapshot->>'issue_count')::int),0) FROM execution_run_records WHERE execution_id=%s", (execution_id,)).fetchone()
            profitability = {
                field: numeric_summary(raw for (raw,) in conn.execute(f"SELECT snapshot->'{field}'->>'value' FROM execution_run_records WHERE execution_id=%s AND snapshot->'{field}'->>'status'='VERIFIED'", (execution_id,)).fetchall())
                for field in ("profit", "roi", "margin")
            }
            brands = brand_distribution(conn.execute("SELECT snapshot->'brand'->>'value', COUNT(*) FROM execution_run_records WHERE execution_id=%s GROUP BY 1", (execution_id,)).fetchall())
            # CROSS JOIN LATERAL drops rows whose snapshot has no
            # `issue_codes` (written before that field existed) instead of
            # inventing a code for them.
            codes = issue_types(conn.execute("SELECT code, COUNT(*) FROM execution_run_records r CROSS JOIN LATERAL jsonb_array_elements_text(r.snapshot->'issue_codes') AS code WHERE r.execution_id=%s GROUP BY 1", (execution_id,)).fetchall())
            spread = price_spread(conn.execute("SELECT record_ref, snapshot->'title'->>'value', snapshot->'selling_price'->>'value', snapshot->>'cog' FROM execution_run_records WHERE execution_id=%s AND snapshot->'selling_price'->>'status'='VERIFIED' AND snapshot->>'cog' IS NOT NULL", (execution_id,)).fetchall())
        return {"records": {"total_records": total}, "decisions": decisions, "risks": risks, "provenance": provenance, "data_quality": {"records_with_issues": quality[0], "total_issue_count": quality[1]}, "profitability": profitability, "brands": brands, "issue_types": codes, "price_spread": spread}
