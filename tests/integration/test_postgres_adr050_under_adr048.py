"""ADR-050 atomic batch persistence under the ADR-048 runtime role `juval_backend`.

Reuses the ADR-048 disposable fixture (full baseline + 20261005000007 applied
as `postgres`, Unix socket only, no DSN from the environment) and drives the
real POST /api/v1/batches as `juval_backend`: all six tables in one
transaction, a failure at any of the six INSERTs commits nothing, the unit-1
atomicity scenarios hold, and UPDATE/DELETE/TRUNCATE/ALTER are denied.
Synthetic data only. Sessions are covered by test_postgres_runtime_role_security.py.
"""
from __future__ import annotations

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import sql  # noqa: E402
from psycopg.conninfo import make_conninfo  # noqa: E402

from juval.infrastructure.persistence import supabase_execution_run_store as pg_module  # noqa: E402
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore  # noqa: E402

from .test_postgres_runtime_role_security import cluster, secured_database  # noqa: E402,F401 (fixtures)

SIX = ("execution_runs", "execution_run_records", "execution_run_financial_records",
       "execution_run_capture_diagnostics", "batches", "batch_files")


def _counts(admin):
    with psycopg.connect(admin) as conn:
        return {t: conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(t))).fetchone()[0] for t in SIX}


def _client(tmp_path, monkeypatch, dsn):
    from fastapi.testclient import TestClient
    from juval.interfaces.api import service
    from juval.interfaces.api.main import app
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", dsn)                    # ADR-048 runtime credential
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.setattr(service, "new_execution_id", iter(f"b48-{n}" for n in range(100)).__next__)
    return TestClient(app, raise_server_exceptions=False)


def _post(client, tmp_path):
    from .test_api_batch_financial import XLSX
    from .test_api_financial_flow import FEES, NATIVE, ROWS, THRESHOLDS
    from .test_cli_native_financial import row
    from .test_native_financial_capture import xlsx
    files = [("files", ("a.xlsx", xlsx(tmp_path, *ROWS, name="a.xlsx").read_bytes(), XLSX)),
             ("files", ("b.xlsx", xlsx(tmp_path, row("B"), name="b.xlsx").read_bytes(), XLSX))]
    return client.post("/api/v1/batches", data={"thresholds": THRESHOLDS, "fees": FEES, **NATIVE}, files=files)


def test_batch_and_reads_as_juval_backend(secured_database, tmp_path, monkeypatch):
    backend = make_conninfo(secured_database, user="juval_backend")
    client = _client(tmp_path, monkeypatch, backend)
    response = _post(client, tmp_path)
    assert response.status_code == 200, response.text
    assert all(n > 0 for n in _counts(secured_database).values())
    body = response.json(); run = body["files"][0]["execution_id"]
    for path in (f"/api/v1/batches/{body['batch_id']}", f"/api/v1/runs/{run}", f"/api/v1/runs/{run}/records",
                 f"/api/v1/runs/{run}/analytics", f"/api/v1/runs/{run}/financial"):
        assert client.get(path).status_code == 200, path


@pytest.mark.parametrize("table", SIX)
def test_failure_at_any_of_the_six_inserts_commits_nothing(secured_database, table, tmp_path, monkeypatch):
    with psycopg.connect(secured_database) as conn:
        conn.execute(sql.SQL("REVOKE INSERT ON {} FROM juval_backend").format(sql.Identifier(table)))
    response = _post(_client(tmp_path, monkeypatch, make_conninfo(secured_database, user="juval_backend")), tmp_path)
    assert response.status_code == 500
    assert _counts(secured_database) == dict.fromkeys(SIX, 0)


def _scenarios():
    from .test_batch_atomic_persistence import SCENARIOS
    return SCENARIOS


@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s.__name__)
def test_atomic_scenarios_as_juval_backend(scenario, secured_database, tmp_path, monkeypatch):
    from .test_batch_atomic_persistence import run_scenario

    def rows(table):
        column = "batch_id" if table.startswith("batch") else "execution_id"
        with psycopg.connect(secured_database) as conn:
            return [r[0] for r in conn.execute(sql.SQL("SELECT {} FROM {}").format(sql.Identifier(column), sql.Identifier(table)))]
    run_scenario(scenario, SupabaseExecutionRunStore(make_conninfo(secured_database, user="juval_backend")),
                 rows, pg_module, tmp_path, monkeypatch)


@pytest.mark.parametrize("table", SIX)
def test_juval_backend_cannot_update_delete_truncate(secured_database, table, tmp_path, monkeypatch):
    backend = make_conninfo(secured_database, user="juval_backend")
    assert _post(_client(tmp_path, monkeypatch, backend), tmp_path).status_code == 200
    before = _counts(secured_database)
    column = "batch_id" if table.startswith("batch") else "execution_id"
    with psycopg.connect(backend, autocommit=True) as conn:
        for statement in (f"UPDATE {table} SET {column} = {column}", f"DELETE FROM {table}", f"TRUNCATE {table}",
                          f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
    assert _counts(secured_database) == before
