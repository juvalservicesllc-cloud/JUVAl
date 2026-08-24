"""Structural tests only for SupabaseExecutionRunStore (ADR-017/ADR-019).

No live Postgres/Supabase instance is required for these -- the real
integration test (tests/integration/test_supabase_execution_run_store.py)
covers actual persistence behavior against a live project, gated on
JUVAL_SUPABASE_DB_URL. These only verify the class can be imported and
constructed, and that it exposes the ExecutionRunStore/RecordSnapshotStore
port shapes -- see docs/architecture/SUPABASE.md "Estado".
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore


def test_constructs_without_connecting():
    # __init__ only stores the connection string -- no eager psycopg.connect()
    # (schema is migrations-only, not created implicitly, see ADR-017) -- so
    # this must not require a reachable database.
    store = SupabaseExecutionRunStore("postgresql://user:pass@localhost:5432/postgres")
    assert store._connection_string == "postgresql://user:pass@localhost:5432/postgres"


def test_implements_the_execution_run_store_port_shape():
    store = SupabaseExecutionRunStore("postgresql://localhost/postgres")
    assert callable(store.save_execution_run)
    assert callable(store.load_execution_run)
    assert callable(store.list_execution_runs)

    save_params = list(inspect.signature(store.save_execution_run).parameters)
    load_params = list(inspect.signature(store.load_execution_run).parameters)
    list_params = list(inspect.signature(store.list_execution_runs).parameters)
    assert save_params == ["run", "records"]
    assert load_params == ["execution_id"]
    assert list_params == ["limit"]


def test_implements_the_record_snapshot_store_port_shape():
    store = SupabaseExecutionRunStore("postgresql://localhost/postgres")
    assert callable(store.load_records)
    assert list(inspect.signature(store.load_records).parameters) == ["execution_id"]
    assert callable(store.load_record)
    assert list(inspect.signature(store.load_record).parameters) == ["execution_id", "record_ref"]


def test_implements_the_batch_store_port_shape():
    store = SupabaseExecutionRunStore("postgresql://localhost/postgres")
    assert callable(store.save_batch)
    assert callable(store.load_batch)
    assert list(inspect.signature(store.save_batch).parameters) == ["batch"]
    assert list(inspect.signature(store.load_batch).parameters) == ["batch_id"]


def test_imports_without_the_optional_postgres_driver():
    # psycopg is the `postgres` extra, not a base dependency (ADR-017): the
    # default store is SQLite (ADR-013). Importing this module -- and the API
    # that imports it only to *choose* a store -- must work without the driver.
    # A top-level `import psycopg` here broke CI collection for five test
    # modules, because CI installs `.[dev]` only. Run in a subprocess so the
    # already-imported psycopg in this process cannot mask the regression.
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_WITHOUT_PSYCOPG],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORTED_WITHOUT_PSYCOPG" in result.stdout
    # The driver is still genuinely required to talk to Postgres -- the import
    # is deferred, not made optional at the point of use.
    assert "CONNECT_REQUIRES_DRIVER" in result.stdout


_IMPORT_WITHOUT_PSYCOPG = """
import sys, importlib.abc


class _Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "psycopg" or name.startswith("psycopg."):
            raise ModuleNotFoundError("No module named '%s'" % name)
        return None


sys.meta_path.insert(0, _Blocked())
sys.path.insert(0, "src")

import juval.interfaces.api.main  # noqa: F401  -- selects a store, must not need the driver
from juval.infrastructure.persistence.supabase_execution_run_store import (
    SupabaseExecutionRunStore,
)

store = SupabaseExecutionRunStore("postgresql://localhost/postgres")
print("IMPORTED_WITHOUT_PSYCOPG")

try:
    store.load_execution_run("any")
except ModuleNotFoundError as exc:
    assert "postgres" in str(exc), exc
    print("CONNECT_REQUIRES_DRIVER")
"""
