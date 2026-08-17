"""Structural tests only for SupabaseExecutionRunStore (ADR-017).

No live Postgres/Supabase instance is available in this environment
(no `supabase`/`psql` reachable, no project credentials). These tests
verify the class can be imported and constructed, and that it exposes
the ExecutionRunStore port's shape -- they do NOT verify actual
persistence behavior against a real database, unlike
tests/integration/test_execution_run_store.py (12 tests against real
SQLite files, ADR-013). See docs/architecture/SUPABASE.md "Estado".
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

    save_params = list(inspect.signature(store.save_execution_run).parameters)
    load_params = list(inspect.signature(store.load_execution_run).parameters)
    assert save_params == ["run"]
    assert load_params == ["execution_id"]
