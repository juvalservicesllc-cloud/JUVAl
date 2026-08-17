"""Unit tests for the ExecutionRunStore composition root
(interfaces/api/main.py::_execution_run_store), ADR-017's "selection by
environment variable" mechanism. Deterministic -- no network, no real
credentials. JUVAL_EXECUTION_STORE, when set, is the sole source of
truth; it must never be inferred from which connection variable happens
to be present.
"""

from __future__ import annotations

import pytest

from juval.interfaces.api.main import _execution_run_store
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("JUVAL_EXECUTION_STORE", "JUVAL_EXECUTION_DB_PATH", "JUVAL_SUPABASE_DB_URL"):
        monkeypatch.delenv(name, raising=False)


def test_sqlite_selected_with_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "sqlite")
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))

    store = _execution_run_store()

    assert isinstance(store, SqliteExecutionRunStore)


def test_sqlite_selected_without_db_path_fails_explicitly(monkeypatch):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "sqlite")

    with pytest.raises(RuntimeError, match="JUVAL_EXECUTION_DB_PATH"):
        _execution_run_store()


def test_supabase_selected_with_db_url(monkeypatch):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", "postgresql://user:pass@localhost:5432/postgres")

    store = _execution_run_store()

    assert isinstance(store, SupabaseExecutionRunStore)


def test_supabase_selected_without_db_url_fails_explicitly(monkeypatch):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")

    with pytest.raises(RuntimeError, match="JUVAL_SUPABASE_DB_URL"):
        _execution_run_store()


def test_invalid_store_value_fails_explicitly(monkeypatch):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "mongodb")

    with pytest.raises(RuntimeError, match="mongodb"):
        _execution_run_store()


def test_legacy_behavior_when_selector_unset_and_db_path_present(monkeypatch, tmp_path):
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))

    store = _execution_run_store()

    assert isinstance(store, SqliteExecutionRunStore)


def test_legacy_behavior_when_nothing_is_set_returns_none():
    assert _execution_run_store() is None


def test_explicit_selector_wins_supabase_when_both_connection_vars_present(monkeypatch, tmp_path):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", "postgresql://user:pass@localhost:5432/postgres")

    store = _execution_run_store()

    assert isinstance(store, SupabaseExecutionRunStore)


def test_explicit_selector_wins_sqlite_when_both_connection_vars_present(monkeypatch, tmp_path):
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "sqlite")
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", "postgresql://user:pass@localhost:5432/postgres")

    store = _execution_run_store()

    assert isinstance(store, SqliteExecutionRunStore)
