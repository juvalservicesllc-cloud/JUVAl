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
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.application.record_snapshot_store import RecordSnapshotPage, RecordSnapshotQuery
from juval.application.run_analytics import brand_distribution, issue_types, numeric_summary, price_spread

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

_BATCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
)
"""

_BATCH_FILES_SCHEMA = """
CREATE TABLE IF NOT EXISTS batch_files (
    batch_id TEXT NOT NULL REFERENCES batches(batch_id),
    ordinal INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    status TEXT NOT NULL,
    execution_id TEXT,
    warnings TEXT NOT NULL,
    errors TEXT NOT NULL,
    records_total INTEGER NOT NULL DEFAULT 0,
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_with_errors INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (batch_id, ordinal)
)
"""

# `execution_id` is the join Run Detail needs to answer "was this run part of
# a batch"; without it that lookup is a full scan of batch_files.
_BATCH_FILES_RUN_INDEX = """
CREATE INDEX IF NOT EXISTS idx_batch_files_execution
    ON batch_files (execution_id)
"""

_BATCH_FILE_COLUMNS = (
    "ordinal, filename, content_type, size_bytes, status, execution_id, warnings, errors, "
    "records_total, records_processed, records_with_errors, warning_count"
)

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

_SELECT_RECORD = """
SELECT snapshot FROM execution_run_records
WHERE execution_id = ? AND record_ref = ?
"""

_SELECT_BATCH = "SELECT batch_id, created_at, status FROM batches WHERE batch_id = ?"
_SELECT_BATCH_ID_FOR_RUN = "SELECT batch_id FROM batch_files WHERE execution_id = ? LIMIT 1"
_SELECT_BATCH_FILES = f"SELECT {_BATCH_FILE_COLUMNS} FROM batch_files WHERE batch_id = ? ORDER BY ordinal"

_SORT_EXPRESSIONS = {
    "record_ref": "record_ref",
    "sku": "json_extract(snapshot, '$.supplier_sku')",
    "asin": "json_extract(snapshot, '$.asin.value')",
    "title": "json_extract(snapshot, '$.title.value')",
    "price": "CAST(json_extract(snapshot, '$.selling_price.value') AS REAL)",
    "cog": "CAST(json_extract(snapshot, '$.cog') AS REAL)",
    "decision": "json_extract(snapshot, '$.decision')",
    "profit": "CAST(json_extract(snapshot, '$.profit.value') AS REAL)",
    "roi": "CAST(json_extract(snapshot, '$.roi.value') AS REAL)",
    "margin": "CAST(json_extract(snapshot, '$.margin.value') AS REAL)",
    "hazmat": "json_extract(snapshot, '$.hazmat_status')",
    "bulky": "json_extract(snapshot, '$.bulky_status')",
}


# `CREATE TABLE IF NOT EXISTS` silently does nothing for a table that already
# exists, so a database created before these columns were added would keep the
# old shape and fail on the next INSERT. Adding them explicitly is the whole
# migration story for this local, single-user store (same scope as ADR-013):
# additive columns with a default, never a rewrite or a drop.
_BATCH_FILE_COUNT_COLUMNS = (
    ("records_total", "INTEGER NOT NULL DEFAULT 0"),
    ("records_processed", "INTEGER NOT NULL DEFAULT 0"),
    ("records_with_errors", "INTEGER NOT NULL DEFAULT 0"),
    ("warning_count", "INTEGER NOT NULL DEFAULT 0"),
)


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: tuple[tuple[str, str], ...]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


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
                conn.execute(_BATCH_SCHEMA)
                conn.execute(_BATCH_FILES_SCHEMA)
                conn.execute(_BATCH_FILES_RUN_INDEX)
                _add_missing_columns(conn, "batch_files", _BATCH_FILE_COUNT_COLUMNS)

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

    def load_record(self, execution_id: str, record_ref: str) -> Optional[dict[str, Any]]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(_SELECT_RECORD, (execution_id, record_ref)).fetchone()
        return json.loads(row[0]) if row is not None else None

    def save_batch(self, batch: Batch) -> None:
        with closing(sqlite3.connect(self._db_path)) as conn:
            with conn:
                conn.execute("INSERT INTO batches (batch_id, created_at, status) VALUES (?, ?, ?)", (batch.batch_id, batch.created_at.isoformat(), batch.status.value))
                for file in batch.files:
                    conn.execute(
                        f"INSERT INTO batch_files (batch_id, {_BATCH_FILE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (batch.batch_id, file.ordinal, file.filename, file.content_type, file.size_bytes, file.status.value, file.execution_id, json.dumps(list(file.warnings)), json.dumps(list(file.errors)), file.records_total, file.records_processed, file.records_with_errors, file.warning_count),
                    )

    def load_batch(self, batch_id: str) -> Optional[Batch]:
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(_SELECT_BATCH, (batch_id,)).fetchone()
            if row is None:
                return None
            files = conn.execute(_SELECT_BATCH_FILES, (batch_id,)).fetchall()
        batch_files = tuple(
            BatchFile(ordinal, filename, content_type, size_bytes, BatchFileStatus(status), execution_id, tuple(json.loads(warnings)), tuple(json.loads(errors)), records_total, records_processed, records_with_errors, warning_count)
            for ordinal, filename, content_type, size_bytes, status, execution_id, warnings, errors, records_total, records_processed, records_with_errors, warning_count in files
        )
        return Batch(batch_id=row[0], created_at=datetime.fromisoformat(row[1]), status=BatchStatus(row[2]), files=batch_files)

    def load_batch_for_run(self, execution_id: str) -> Optional[Batch]:
        """The batch a child run belongs to, or None when it ran on its own."""
        with closing(sqlite3.connect(self._db_path)) as conn:
            row = conn.execute(_SELECT_BATCH_ID_FOR_RUN, (execution_id,)).fetchone()
        return self.load_batch(row[0]) if row is not None else None

    def list_records(self, execution_id: str, query: RecordSnapshotQuery) -> RecordSnapshotPage:
        """Query JSON snapshots in SQLite; never load a whole run for a page."""
        clauses = ["execution_id = ?"]
        params: list[Any] = [execution_id]
        if query.decision is not None:
            clauses.append("json_extract(snapshot, '$.decision') = ?")
            params.append(query.decision)
        if query.search:
            clauses.append("(record_ref LIKE ? OR json_extract(snapshot, '$.supplier_sku') LIKE ? OR json_extract(snapshot, '$.title.value') LIKE ? OR json_extract(snapshot, '$.brand.value') LIKE ? OR json_extract(snapshot, '$.asin.value') LIKE ?)")
            params.extend([f"%{query.search}%"] * 5)
        for field, minimum in (("roi", query.min_roi), ("profit", query.min_profit), ("margin", query.min_margin)):
            if minimum is not None:
                statuses = ("VERIFIED",) if query.confidence == "VERIFIED_ONLY" else ("VERIFIED", "INFERRED")
                placeholders = ",".join("?" for _ in statuses)
                clauses.append(f"json_extract(snapshot, '$.{field}.status') IN ({placeholders}) AND CAST(json_extract(snapshot, '$.{field}.value') AS REAL) >= ?")
                params.extend([*statuses, float(minimum)])
        if query.hazmat is not None:
            clauses.append("json_extract(snapshot, '$.hazmat_status') = ?")
            params.append(query.hazmat)
        if query.bulky is not None:
            clauses.append("json_extract(snapshot, '$.bulky_status') = ?")
            params.append(query.bulky)
        if query.provenance_field is not None and query.provenance_status is not None:
            clauses.append(f"json_extract(snapshot, '$.{query.provenance_field}.status') = ?")
            params.append(query.provenance_status)
        where = " AND ".join(clauses)
        expression = _SORT_EXPRESSIONS[query.sort]
        order = query.direction.upper()
        sql = f"SELECT snapshot FROM execution_run_records WHERE {where} ORDER BY {expression} {order}, ordinal ASC LIMIT ? OFFSET ?"
        count_sql = f"SELECT COUNT(*) FROM execution_run_records WHERE {where}"
        with closing(sqlite3.connect(self._db_path)) as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(sql, [*params, query.limit, query.offset]).fetchall()
        return RecordSnapshotPage(items=[json.loads(snapshot) for (snapshot,) in rows], total=total)

    def get_run_analytics(self, execution_id: str) -> dict[str, Any]:
        """Use SQL grouping; only numeric value/status pairs leave SQLite."""
        fields = ("asin", "weight", "selling_price", "profit", "roi", "margin")
        with closing(sqlite3.connect(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM execution_run_records WHERE execution_id=?", (execution_id,)).fetchone()[0]
            def grouped(expression):
                return {str(k) if k is not None else "UNKNOWN": n for k, n in conn.execute(f"SELECT {expression}, COUNT(*) FROM execution_run_records WHERE execution_id=? GROUP BY {expression}", (execution_id,))}
            decisions = grouped("json_extract(snapshot, '$.decision')")
            risks = {name: {"status": grouped(f"json_extract(snapshot, '$.{name}_status')"), "severity": grouped(f"json_extract(snapshot, '$.{name}_severity')")} for name in ("hazmat", "bulky")}
            provenance = {field: grouped(f"json_extract(snapshot, '$.{field}.status')") for field in fields}
            quality = conn.execute("SELECT COALESCE(SUM(CASE WHEN CAST(json_extract(snapshot, '$.issue_count') AS INTEGER)>0 THEN 1 ELSE 0 END),0), COALESCE(SUM(CAST(json_extract(snapshot, '$.issue_count') AS INTEGER)),0) FROM execution_run_records WHERE execution_id=?", (execution_id,)).fetchone()
            profitability = {
                field: numeric_summary(raw for (raw,) in conn.execute(f"SELECT json_extract(snapshot, '$.{field}.value') FROM execution_run_records WHERE execution_id=? AND json_extract(snapshot, '$.{field}.status')='VERIFIED'", (execution_id,)))
                for field in ("profit", "roi", "margin")
            }
            brands = brand_distribution(conn.execute("SELECT json_extract(snapshot, '$.brand.value'), COUNT(*) FROM execution_run_records WHERE execution_id=? GROUP BY 1", (execution_id,)).fetchall())
            # json_each yields nothing for a snapshot without `issue_codes`
            # (written before that field existed) -- a legacy record simply
            # does not contribute, it is never guessed at.
            codes = issue_types(conn.execute("SELECT code.value, COUNT(*) FROM execution_run_records r, json_each(r.snapshot, '$.issue_codes') code WHERE r.execution_id=? GROUP BY 1", (execution_id,)).fetchall())
            spread = price_spread(conn.execute("SELECT record_ref, json_extract(snapshot, '$.title.value'), json_extract(snapshot, '$.selling_price.value'), json_extract(snapshot, '$.cog') FROM execution_run_records WHERE execution_id=? AND json_extract(snapshot, '$.selling_price.status')='VERIFIED' AND json_extract(snapshot, '$.cog') IS NOT NULL", (execution_id,)).fetchall())
        return {"records": {"total_records": total}, "decisions": decisions, "risks": risks, "provenance": provenance, "data_quality": {"records_with_issues": quality[0], "total_issue_count": quality[1]}, "profitability": profitability, "brands": brands, "issue_types": codes, "price_spread": spread}
