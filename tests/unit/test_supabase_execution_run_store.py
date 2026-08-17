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
