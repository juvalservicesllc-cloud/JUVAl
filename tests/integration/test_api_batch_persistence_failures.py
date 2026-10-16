"""Characterization of POST /api/v1/batches when *persistence* fails (ADR-025 open item).

These tests pin today's behavior -- they do not endorse it. ADR-050 (Propuesta)
analyses it; if that ADR is approved, the assertions marked CURRENT change with
the contract. Temporary SQLite only, synthetic workbooks only.
"""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api import main as api
from juval.interfaces.api.main import app

from .test_api_batch_financial import post_batch, rows_of, workbook
from .test_api_financial_flow import DIAG, DOC, NATIVE, ROWS, count, env  # noqa: F401 (fixture)
from .test_cli_native_financial import row

client = TestClient(app, raise_server_exceptions=False)


def failing_save(monkeypatch, fail_on):
    """Make SqliteExecutionRunStore.save_execution_run raise for the given child ids."""
    original = SqliteExecutionRunStore.save_execution_run

    def save(self, run, *args, **kwargs):
        if fail_on(run.execution_id):
            raise sqlite3.OperationalError("simulated database failure")
        return original(self, run, *args, **kwargs)
    monkeypatch.setattr(SqliteExecutionRunStore, "save_execution_run", save)


def files(env):
    return workbook(env, "a.xlsx", *ROWS), workbook(env, "b.xlsx", row("B"))


def test_all_files_succeed_and_the_batch_links_every_child(env):
    body = post_batch(*files(env), **NATIVE).json()
    children = [f["execution_id"] for f in body["files"]]
    assert body["status"] == "SUCCESS" and body["persisted"] is True
    assert rows_of(env, "execution_runs") == sorted(children)
    assert all(client.get(f"/api/v1/runs/{c}/batch").json()["batch_id"] == body["batch_id"] for c in children)


def test_a_rejected_file_is_stored_as_a_batch_outcome_without_a_run(env):
    body = post_batch(("notes.txt", b"plain text"), workbook(env, "a.xlsx", row("A")), persist="true").json()
    rejected, good = body["files"]
    assert rejected["status"] == "REJECTED" and rejected["execution_id"] is None
    assert client.get(f"/api/v1/batches/{body['batch_id']}").json()["files"][0]["status"] == "REJECTED"
    assert rows_of(env, "execution_runs") == [good["execution_id"]]


def test_current_second_file_failure_leaves_an_unlinked_first_child(env, monkeypatch):
    """CURRENT: generic 500; child 1 stays stored with its documents, child 2
    stores nothing, no batch row -- so child 1 belongs to no batch and the
    client was never told its execution_id."""
    failing_save(monkeypatch, lambda execution_id: execution_id == "api-run-2")
    response = post_batch(*files(env), **NATIVE)
    assert response.status_code == 500 and response.json() == {"detail": "internal server error"}
    assert "api-run-1" not in response.text
    assert rows_of(env, "execution_runs") == ["api-run-1"]
    assert set(rows_of(env, DOC)) == set(rows_of(env, DIAG)) == {"api-run-1"}        # no orphan documents
    assert rows_of(env, "batches", "batch_id") == []
    assert client.get("/api/v1/runs/api-run-1/batch").status_code == 404           # reads as "submitted alone"


def test_current_retry_after_a_partial_failure_duplicates_the_stored_child(env, monkeypatch):
    """CURRENT: there is no idempotency key; the retry creates new runs, so the
    first file is now stored twice under different execution_ids."""
    request = files(env)                                    # the same bytes are re-sent, as a real retry does
    original = SqliteExecutionRunStore.save_execution_run
    failing_save(monkeypatch, lambda execution_id: execution_id == "api-run-2")
    assert post_batch(*request, **NATIVE).status_code == 500
    monkeypatch.setattr(SqliteExecutionRunStore, "save_execution_run", original)    # the database recovers
    monkeypatch.setattr(api.service, "new_execution_id", iter(f"retry-{n}" for n in range(10)).__next__)
    retry = post_batch(*request, **NATIVE)
    assert retry.status_code == 200
    with sqlite3.connect(env / "api.db") as conn:
        by_hash = conn.execute("SELECT input_hash, COUNT(*) FROM execution_runs GROUP BY input_hash "
                               "ORDER BY COUNT(*) DESC").fetchall()
    assert by_hash[0][1] == 2                                                        # a.xlsx stored twice
    assert rows_of(env, "batches", "batch_id") == ["retry-0"]


def test_current_global_database_failure_stores_nothing(env, monkeypatch):
    """CURRENT: a database that fails for every write is a generic 500 and
    nothing is stored; the response does not say a retry is safe."""
    failing_save(monkeypatch, lambda execution_id: True)
    response = post_batch(*files(env), **NATIVE)
    assert response.status_code == 500 and response.json() == {"detail": "internal server error"}
    assert rows_of(env, "execution_runs") == [] and count(env, DOC) == count(env, DIAG) == 0
    assert rows_of(env, "batches", "batch_id") == []


def test_current_export_failure_after_a_saved_child_is_also_a_500(env, monkeypatch):
    """CURRENT: the per-child XLSX export runs after that child was saved; if
    it fails the child stays stored and unlinked, as with a save failure."""
    def failing_export(records, path):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(api, "export_excel", failing_export)
    response = post_batch(*files(env), persist="true")
    assert response.status_code == 500
    assert rows_of(env, "execution_runs") == ["api-run-1"] and rows_of(env, "batches", "batch_id") == []
