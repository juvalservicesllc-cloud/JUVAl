"""Read-only access to a SQLite database written by SqliteExecutionRunStore.

Unlike SqliteExecutionRunStore, constructing this reader runs no DDL and never
creates a file: every query opens the database through SQLite's URI
`mode=ro`, so the engine itself refuses any write, and a missing path is
reported instead of created. Row decoding reuses the store's own queries.

A table that predates a feature (e.g. a database written before the financial
or diagnostics tables existed) is read as "nothing stored" — it cannot hold
rows, and creating it here would be a write.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Optional, Sequence

from juval.domain.execution_run import ExecutionRun

from .sqlite_execution_run_store import _SELECT, _SELECT_RECORDS, _row_to_run, _rows_by_ref


class ReadOnlySqliteRunReader:
    def __init__(self, db_path: Path) -> None:
        path = Path(db_path)
        if not path.is_file():
            raise FileNotFoundError(f"SQLite database not found: {path}")
        self._uri = path.resolve().as_uri() + "?mode=ro"

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._uri, uri=True)

    def _has_table(self, conn: sqlite3.Connection, table: str) -> bool:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        with closing(self._connect()) as conn:
            if not self._has_table(conn, "execution_runs"):
                return None
            row = conn.execute(_SELECT, (execution_id,)).fetchone()
        return _row_to_run(row) if row is not None else None

    def load_records(self, execution_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            if not self._has_table(conn, "execution_run_records"):
                return []
            rows = conn.execute(_SELECT_RECORDS, (execution_id,)).fetchall()
        return [json.loads(snapshot) for (snapshot,) in rows]

    def _payload_row(self, table: str, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]:
        with closing(self._connect()) as conn:
            if not self._has_table(conn, table):
                return None
            row = conn.execute(f"SELECT format, format_version, payload FROM {table} "
                               "WHERE execution_id = ? AND record_ref = ?", (execution_id, record_ref)).fetchone()
        return tuple(row) if row is not None else None

    def load_financial_record(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]:
        return self._payload_row("execution_run_financial_records", execution_id, record_ref)

    def load_capture_diagnostics(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]:
        return self._payload_row("execution_run_capture_diagnostics", execution_id, record_ref)

    def load_financial_rows(
        self, execution_id: str, record_refs: Optional[Sequence[str]] = None,
    ) -> tuple[dict[str, tuple[str, int, str]], dict[str, tuple[str, int, str]]]:
        with closing(self._connect()) as conn:
            return tuple(_rows_by_ref(conn, table, execution_id, record_refs) if self._has_table(conn, table) else {}
                         for table in ("execution_run_financial_records", "execution_run_capture_diagnostics"))
