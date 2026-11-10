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

Native financial records and capture diagnostics (ADR-047 §22 step 6,
migration 20260925000005_execution_run_financial_records.sql): same
contract as the SQLite store. `save_execution_run(..., financial_records=...,
capture_diagnostics=...)` writes them in the run's own transaction, and the
rows are built by the SQLite store's own helpers, so both backends store the
identical canonical TEXT (not JSONB, which would not keep the text
byte-identical). `load_financial_record` / `load_capture_diagnostics` return
the raw `(format, format_version, payload)` row or None, and raise
FinancialStorageUnavailable when the migration was not applied; parsing and
integrity checks stay in application/financial_persistence.py.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence


from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.application.batch_store import RunWrite
from juval.application.financial_persistence import FinancialStorageUnavailable
from juval.application.record_snapshot_store import RecordSnapshotPage, RecordSnapshotQuery
from juval.application.tenancy import OutOfScopeError, Ownership, TenantScope, canonical_organization_id
from juval.application.review_classification import PENDING_DEMAND_VERIFICATION
from juval.application.run_analytics import brand_distribution, decision_counts_by_run, issue_types, numeric_summary, price_spread
from juval.infrastructure.logging.sqlite_execution_run_store import _diagnostics_row, _financial_row, _owner_values

_INSERT = """
INSERT INTO execution_runs (
    execution_id, started_at, finished_at, status,
    input_filename, input_hash, application_version,
    records_total, records_processed,
    records_successful, records_with_errors, warnings
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

# ADR-056: an owned run names its organization and creator. Unowned writes
# (unscoped tools only) keep the column list above, so they still work on a
# database that predates migration 20261110000008.
_INSERT_OWNED = _INSERT.replace(
    "warnings\n) VALUES (", "warnings,\n    organization_id, created_by_issuer, created_by_subject\n) VALUES (%s, %s, %s, ")

_INSERT_RECORD = """
INSERT INTO execution_run_records (execution_id, ordinal, record_ref, snapshot)
VALUES (%s, %s, %s, %s)
"""

_INSERT_FINANCIAL = """
INSERT INTO execution_run_financial_records (execution_id, record_ref, format, format_version, payload)
VALUES (%s, %s, %s, %s, %s)
"""

_INSERT_DIAGNOSTICS = """
INSERT INTO execution_run_capture_diagnostics (execution_id, record_ref, format, format_version, payload)
VALUES (%s, %s, %s, %s, %s)
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

# ADR-056 scoped forms (the RLS of migration 20261110000008 applies the same
# filter again in the database; NULL-owned history never matches either).
_SELECT_OWNED = _SELECT.rstrip() + " AND organization_id = %s\n"
_SELECT_LIST_OWNED = """
SELECT execution_id, started_at, finished_at, status,
       input_filename, input_hash, application_version,
       records_total, records_processed,
       records_successful, records_with_errors, warnings
FROM execution_runs WHERE organization_id = %s ORDER BY started_at DESC LIMIT %s
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


def _write_run(conn, run: ExecutionRun, records: Sequence[Mapping[str, Any]],
               financial_records: Sequence[Mapping[str, Any]],
               capture_diagnostics: Sequence[Mapping[str, Any]],
               owner: Optional[Ownership] = None) -> None:
    """The run's inserts on `conn`, inside the caller's transaction."""
    _, Json = _require_driver()
    owned = owner is not None
    conn.execute(
        _INSERT_OWNED if owned else _INSERT,
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
            *(_owner_values(owner) if owned else ()),
        ),
    )
    for ordinal, record in enumerate(records):
        conn.execute(
            _INSERT_RECORD,
            (run.execution_id, ordinal, record["record_ref"], Json(dict(record))),
        )
    for payload in financial_records:
        conn.execute(_INSERT_FINANCIAL, _financial_row(run.execution_id, payload))
    for payload in capture_diagnostics:
        conn.execute(_INSERT_DIAGNOSTICS, _diagnostics_row(run.execution_id, payload))


def _write_batch(conn, batch: Batch, owner: Optional[Ownership] = None) -> None:
    """The batch's inserts on `conn`, inside the caller's transaction."""
    _, Json = _require_driver()
    if owner is None:  # unscoped tools: pre-ADR-056 column list
        conn.execute("INSERT INTO batches (batch_id, created_at, status) VALUES (%s, %s, %s)",
                     (batch.batch_id, batch.created_at, batch.status.value))
    else:
        conn.execute(
            "INSERT INTO batches (batch_id, created_at, status, organization_id, created_by_issuer, created_by_subject) "
            "VALUES (%s, %s, %s, %s, %s, %s)", (batch.batch_id, batch.created_at, batch.status.value, *_owner_values(owner)))
    for file in batch.files:
        conn.execute(
            f"INSERT INTO batch_files (batch_id, {_BATCH_FILE_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (batch.batch_id, file.ordinal, file.filename, file.content_type, file.size_bytes, file.status.value, file.execution_id, Json(list(file.warnings)), Json(list(file.errors)), file.records_total, file.records_processed, file.records_with_errors, file.warning_count),
        )


# SQL mirror of application/review_classification.py (tests hold them equal).
# JSONB equality: the stored codes array is exactly ["DEMAND_UNKNOWN"]; a
# snapshot without `decision_reason_codes` never matches.
_PENDING_DEMAND_SQL = "(snapshot->>'decision' = 'REVIEW' AND snapshot->'decision_reason_codes' = '[\"DEMAND_UNKNOWN\"]'::jsonb)"
_REVIEW_NOT_CLASSIFIABLE_SQL = "(snapshot->>'decision' = 'REVIEW' AND NOT (snapshot ? 'decision_reason_codes'))"


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
        self._scope: Optional[TenantScope] = None

    def _connect(self):
        """A connection; a scoped store also binds its organization for RLS.

        `set_config(..., true)` is transaction-local: it lasts for exactly the
        `with` block that uses this connection and cannot leak to another
        request through a pooled session. Without it, the tenant policies of
        migration 20261110000008 return no rows and accept no inserts.
        """
        psycopg, _ = _require_driver()
        conn = psycopg.connect(self._connection_string)
        if self._scope is not None:
            try:
                conn.execute("SELECT set_config('juval.organization_id', %s, true)", (self._scope.organization_id,))
            except BaseException:
                conn.close()
                raise
        return conn

    # --- ADR-056 tenant scope ------------------------------------------------

    def scoped(self, scope: TenantScope) -> "SupabaseExecutionRunStore":
        """Same contract as `SqliteExecutionRunStore.scoped`, plus RLS binding."""
        if not isinstance(scope, TenantScope):
            raise TypeError("scoped() requires a TenantScope")
        view = copy.copy(self)
        view._scope = scope
        return view

    def _owner_for_write(self, owner: Optional[Ownership]) -> Optional[Ownership]:
        if self._scope is not None and (owner is None or owner.organization_id != self._scope.organization_id):
            raise OutOfScopeError("a scoped store writes only its own organization's resources")
        return owner

    def _require_runs_in_scope(self, conn, execution_ids: Sequence[str]) -> None:
        """Application-level twin of the RLS policy, so a missing policy is not silent."""
        if self._scope is None or not execution_ids:
            return
        owned = conn.execute(
            "SELECT COUNT(DISTINCT execution_id) FROM execution_runs WHERE organization_id = %s AND execution_id = ANY(%s)",
            (self._scope.organization_id, list(execution_ids))).fetchone()[0]
        if owned != len(set(execution_ids)):
            raise OutOfScopeError("child read outside the store's organization")

    def organization_ids_for(self, issuer: str, subject: str) -> list[str]:
        """The organizations this identity belongs to (at most one, OD-6).

        The runtime role may only read its own membership row: the policy
        compares against these transaction-local settings (migration
        20261110000008).
        """
        with self._connect() as conn:
            conn.execute("SELECT set_config('juval.issuer', %s, true), set_config('juval.subject', %s, true)",
                         (issuer, subject))
            rows = conn.execute(
                "SELECT organization_id::text FROM organization_memberships WHERE issuer = %s AND subject = %s",
                (issuer, subject)).fetchall()
        return [row[0] for row in rows]

    def create_organization(self, organization_id: str, name: str, created_by: str, created_at: datetime) -> None:
        """Operator action with an administrative DSN; the runtime role cannot write here."""
        canonical_organization_id(organization_id)
        if not name.strip() or not created_by:
            raise ValueError("organization requires a name and created_by")
        with self._connect() as conn:
            conn.execute("INSERT INTO organizations (organization_id, name, created_at, created_by) VALUES (%s, %s, %s, %s)",
                         (organization_id, name, created_at, created_by))

    def remove_membership(self, issuer: str, subject: str) -> Optional[str]:
        """Operator action (offboarding): the organization the identity left, or
        None if it had no membership. Access ends on the identity's next request."""
        with self._connect() as conn:
            row = conn.execute("DELETE FROM organization_memberships WHERE issuer = %s AND subject = %s "
                               "RETURNING organization_id::text", (issuer, subject)).fetchone()
        return row[0] if row is not None else None

    def add_membership(self, organization_id: str, issuer: str, subject: str, created_by: str,
                       created_at: datetime) -> None:
        """Operator action; a second organization for one identity is refused (OD-6)."""
        canonical_organization_id(organization_id)
        if not issuer or not subject or not created_by:
            raise ValueError("membership requires issuer, subject and created_by")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO organization_memberships (issuer, subject, organization_id, created_at, created_by) "
                "VALUES (%s, %s, %s, %s, %s)", (issuer, subject, organization_id, created_at, created_by))

    def save_execution_run(
        self,
        run: ExecutionRun,
        records: Sequence[Mapping[str, Any]] = (),
        *,
        financial_records: Sequence[Mapping[str, Any]] = (),
        capture_diagnostics: Sequence[Mapping[str, Any]] = (),
        owner: Optional[Ownership] = None,
    ) -> None:
        """Run, record snapshots and (optionally) native financial payloads and
        capture diagnostics, all in one transaction: any failure, including a
        financial or diagnostics one, rolls back everything."""
        owner = self._owner_for_write(owner)
        with self._connect() as conn:
            _write_run(conn, run, records, financial_records, capture_diagnostics, owner)

    def save_batch_with_runs(self, batch: Batch, runs: Sequence[RunWrite], owner: Optional[Ownership] = None) -> None:
        """Every child run (records, financial documents, diagnostics) and the
        batch in ONE transaction: any failure rolls back all of it (ADR-050).
        The batch and every child share one owner."""
        owner = self._owner_for_write(owner)
        with self._connect() as conn:
            for item in runs:
                _write_run(conn, item.run, item.records, item.financial_records, item.capture_diagnostics, owner)
            _write_batch(conn, batch, owner)

    def _payload_row(self, table: str, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]:
        psycopg, _ = _require_driver()
        try:
            with self._connect() as conn:
                self._require_runs_in_scope(conn, (execution_id,))
                row = conn.execute(f"SELECT format, format_version, payload FROM {table} "
                                   "WHERE execution_id = %s AND record_ref = %s", (execution_id, record_ref)).fetchone()
        except psycopg.errors.UndefinedTable as error:
            # Migration 20260925000005 not applied: an error, never "no document".
            raise FinancialStorageUnavailable(f"table {table} does not exist") from error
        return tuple(row) if row is not None else None

    def load_financial_rows(
        self, execution_id: str, record_refs: Optional[Sequence[str]] = None,
    ) -> tuple[dict[str, tuple[str, int, str]], dict[str, tuple[str, int, str]]]:
        """Financial and diagnostics rows of many records of one run, keyed by
        record_ref, over one connection (two queries). None = the whole run."""
        psycopg, _ = _require_driver()
        if record_refs is not None and not record_refs:
            return {}, {}
        found = []
        try:
            with self._connect() as conn:
                self._require_runs_in_scope(conn, (execution_id,))
                for table in ("execution_run_financial_records", "execution_run_capture_diagnostics"):
                    sql = f"SELECT record_ref, format, format_version, payload FROM {table} WHERE execution_id = %s"
                    params: list[Any] = [execution_id]
                    if record_refs is not None:
                        sql += " AND record_ref = ANY(%s)"
                        params.append(list(record_refs))
                    found.append({ref: (fmt, version, payload) for ref, fmt, version, payload in conn.execute(sql, params)})
        except psycopg.errors.UndefinedTable as error:
            raise FinancialStorageUnavailable("financial tables do not exist") from error
        return found[0], found[1]

    def load_financial_record(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]:
        """(format, format_version, payload JSON text) of one run's record, or None
        when that record has no financial document. Parsing is the caller's job."""
        return self._payload_row("execution_run_financial_records", execution_id, record_ref)

    def load_capture_diagnostics(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]:
        """(format, format_version, payload JSON text) of one record's stored
        diagnostics, or None when none were stored for it."""
        return self._payload_row("execution_run_capture_diagnostics", execution_id, record_ref)

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        """The run, or None -- also when it belongs to another organization."""
        with self._connect() as conn:
            if self._scope is None:
                row = conn.execute(_SELECT, (execution_id,)).fetchone()
            else:
                row = conn.execute(_SELECT_OWNED, (execution_id, self._scope.organization_id)).fetchone()
        return _row_to_run(row) if row is not None else None

    def list_execution_runs(self, limit: int = 20) -> list[ExecutionRun]:
        with self._connect() as conn:
            if self._scope is None:
                rows = conn.execute(_SELECT_LIST, (limit,)).fetchall()
            else:
                rows = conn.execute(_SELECT_LIST_OWNED, (self._scope.organization_id, limit)).fetchall()
        return [_row_to_run(row) for row in rows]

    def load_records(self, execution_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._require_runs_in_scope(conn, (execution_id,))
            rows = conn.execute(_SELECT_RECORDS, (execution_id,)).fetchall()
        return [snapshot for (snapshot,) in rows]

    def load_record(self, execution_id: str, record_ref: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            self._require_runs_in_scope(conn, (execution_id,))
            row = conn.execute(_SELECT_RECORD, (execution_id, record_ref)).fetchone()
        return row[0] if row is not None else None

    def save_batch(self, batch: Batch, owner: Optional[Ownership] = None) -> None:
        owner = self._owner_for_write(owner)
        with self._connect() as conn:
            _write_batch(conn, batch, owner)

    def load_batch(self, batch_id: str) -> Optional[Batch]:
        """The batch, or None -- also when it belongs to another organization."""
        with self._connect() as conn:
            if self._scope is None:
                row = conn.execute("SELECT batch_id, created_at, status FROM batches WHERE batch_id = %s", (batch_id,)).fetchone()
            else:
                row = conn.execute("SELECT batch_id, created_at, status FROM batches WHERE batch_id = %s AND organization_id = %s",
                                   (batch_id, self._scope.organization_id)).fetchone()
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
            self._require_runs_in_scope(conn, (execution_id,))
            row = conn.execute("SELECT batch_id FROM batch_files WHERE execution_id = %s LIMIT 1", (execution_id,)).fetchone()
        return self.load_batch(row[0]) if row is not None else None  # load_batch re-applies the scope

    def list_records(self, execution_id: str, query: RecordSnapshotQuery) -> RecordSnapshotPage:
        clauses = ["execution_id = %s"]
        params: list[Any] = [execution_id]
        if query.decision is not None:
            clauses.append("snapshot->>'decision' = %s")
            params.append(query.decision)
        if query.search:
            clauses.append("(record_ref ILIKE %s OR snapshot->>'supplier_sku' ILIKE %s OR snapshot->'title'->>'value' ILIKE %s OR snapshot->'brand'->>'value' ILIKE %s OR snapshot->'asin'->>'value' ILIKE %s)")
            params.extend([f"%{query.search}%"] * 5)
        if query.brand is not None:
            clauses.append("snapshot->'brand'->>'value' = %s")
            params.append(query.brand)
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
        if query.review_classification == PENDING_DEMAND_VERIFICATION:
            clauses.append(_PENDING_DEMAND_SQL)
        where = " AND ".join(clauses)
        expression = _SORT_EXPRESSIONS[query.sort]
        order = query.direction.upper()
        sql = f"SELECT snapshot FROM execution_run_records WHERE {where} ORDER BY {expression} {order} NULLS LAST, ordinal ASC LIMIT %s OFFSET %s"
        count_sql = f"SELECT COUNT(*) FROM execution_run_records WHERE {where}"
        with self._connect() as conn:
            self._require_runs_in_scope(conn, (execution_id,))
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(sql, [*params, query.limit, query.offset]).fetchall()
        return RecordSnapshotPage(items=[snapshot for (snapshot,) in rows], total=total)

    def decision_counts(self, execution_ids: Sequence[str]) -> dict[str, dict[str, int]]:
        if not execution_ids:
            return {}
        with self._connect() as conn:
            self._require_runs_in_scope(conn, execution_ids)
            rows = conn.execute("SELECT execution_id, snapshot->>'decision', COUNT(*) FROM execution_run_records WHERE execution_id = ANY(%s) GROUP BY 1, 2", (list(execution_ids),)).fetchall()
        return decision_counts_by_run(rows)

    def get_run_analytics(self, execution_id: str) -> dict[str, Any]:
        fields = ("asin", "weight", "selling_price", "profit", "roi", "margin")
        with self._connect() as conn:
            self._require_runs_in_scope(conn, (execution_id,))
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
            classification = conn.execute(f"SELECT COUNT(*) FILTER (WHERE {_PENDING_DEMAND_SQL}), COUNT(*) FILTER (WHERE {_REVIEW_NOT_CLASSIFIABLE_SQL}) FROM execution_run_records WHERE execution_id=%s", (execution_id,)).fetchone()
        return {"records": {"total_records": total}, "decisions": decisions, "risks": risks, "provenance": provenance, "data_quality": {"records_with_issues": quality[0], "total_issue_count": quality[1]}, "profitability": profitability, "brands": brands, "issue_types": codes, "price_spread": spread,
                "review_classification": {"pending_demand_verification": classification[0], "review_not_classifiable": classification[1]}}
