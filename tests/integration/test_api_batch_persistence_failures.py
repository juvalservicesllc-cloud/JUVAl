"""POST /api/v1/batches persists atomically through save_batch_with_runs (ADR-050 D1-D4).

Every file is processed first; then the batch, every child run, its records,
financial documents and diagnostics are written in one transaction; XLSX
exports run only after that commit. A failed write is still the existing
generic 500 (D4 provisional) but now leaves no row at all.

The scenarios are functions of (env, rows, store_module, monkeypatch) so the
PostgreSQL suite runs the same ones against a disposable cluster. Failures are
injected into the store module's own write helpers, the ones the endpoint's
atomic path really calls. Synthetic workbooks only.
"""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from juval.domain.financial_evidence import FinancialTerm as T
from juval.infrastructure.logging import sqlite_execution_run_store as sqlite_module
from juval.interfaces.api import main as api
from juval.interfaces.api.main import EXPORT_FAILED_WARNING, app
from .api_lab import LOOPBACK

from .test_api_batch_financial import post_batch, workbook
from .test_api_financial_flow import NATIVE, ROWS, env  # noqa: F401 (fixture)
from .test_cli_native_financial import row
from .test_native_financial_capture import declared

client = TestClient(app, raise_server_exceptions=False, **LOOPBACK)
pytestmark = pytest.mark.usefixtures("auth_lab")  # ADR-055: explicit loopback lab
DOC, DIAG = "execution_run_financial_records", "execution_run_capture_diagnostics"
TABLES = ("execution_runs", "execution_run_records", DOC, DIAG, "batches", "batch_files")
GENERIC_500 = {"detail": "internal server error"}


def files(env):
    return workbook(env, "a.xlsx", *ROWS), workbook(env, "b.xlsx", row("B"))


def nothing_stored(rows):
    return all(rows(table) == [] for table in TABLES)


def fail_in(monkeypatch, store_module, helper, when):
    original = getattr(store_module, helper)

    def failing(*args):
        if when(*args):
            raise RuntimeError(f"simulated {helper} failure")
        return original(*args)
    monkeypatch.setattr(store_module, helper, failing)


def exported(execution_id):
    return client.get(f"/api/v1/runs/{execution_id}/download").status_code == 200


# -- Scenarios shared with the PostgreSQL suite ---------------------------------------------

def every_file_stored_and_linked_with_its_documents(env, rows, store_module, monkeypatch):
    body = post_batch(*files(env), **NATIVE).json()
    children = [f["execution_id"] for f in body["files"]]
    assert body["status"] == "SUCCESS" and body["persisted"] is True
    assert sorted(rows("execution_runs")) == sorted(children)
    assert sorted(rows(DOC)) == sorted([children[0]] * 3 + [children[1]])
    assert sorted(rows(DIAG)) == sorted([children[0]] * 4 + [children[1]])
    assert rows("batches") == [body["batch_id"]] and len(rows("batch_files")) == 2
    for execution_id in children:
        assert client.get(f"/api/v1/runs/{execution_id}/batch").json()["batch_id"] == body["batch_id"]
        assert exported(execution_id)


def a_batch_without_the_opt_in_stores_no_financial_rows(env, rows, store_module, monkeypatch):
    body = post_batch(*files(env), persist="true").json()
    assert body["status"] == "SUCCESS" and len(rows("execution_runs")) == 2
    assert rows(DOC) == [] and rows(DIAG) == []


def a_rejected_file_is_an_outcome_without_a_run(env, rows, store_module, monkeypatch):
    body = post_batch(("notes.txt", b"plain text"), workbook(env, "a.xlsx", row("A")), **NATIVE).json()
    rejected, good = body["files"]
    assert body["status"] == "PARTIAL_SUCCESS"
    assert rejected["status"] == "REJECTED" and rejected["execution_id"] is None
    assert rows("execution_runs") == [good["execution_id"]] and len(rows("batch_files")) == 2


def a_failing_second_child_write_stores_nothing_and_exports_nothing(env, rows, store_module, monkeypatch):
    fail_in(monkeypatch, store_module, "_write_run", lambda conn, run, *rest: run.execution_id == "api-run-2")
    response = post_batch(*files(env), **NATIVE)
    assert response.status_code == 500 and response.json() == GENERIC_500
    assert nothing_stored(rows)                                       # no unlinked first child any more
    assert not exported("api-run-1") and not exported("api-run-2")     # exports wait for the commit


def a_failing_financial_document_write_stores_nothing(env, rows, store_module, monkeypatch):
    fail_in(monkeypatch, store_module, "_financial_row", lambda execution_id, payload: execution_id == "api-run-2")
    response = post_batch(*files(env), **NATIVE)
    assert response.status_code == 500 and response.json() == GENERIC_500
    assert nothing_stored(rows)


def a_failing_batch_write_after_every_child_stores_nothing(env, rows, store_module, monkeypatch):
    fail_in(monkeypatch, store_module, "_write_batch", lambda conn, batch: True)
    response = post_batch(*files(env), **NATIVE)
    assert response.status_code == 500 and response.json() == GENERIC_500
    assert nothing_stored(rows)


def a_global_database_failure_stores_nothing(env, rows, store_module, monkeypatch):
    fail_in(monkeypatch, store_module, "_write_run", lambda *args: True)
    assert post_batch(*files(env), persist="true").status_code == 500
    assert nothing_stored(rows)


def a_retry_after_a_failure_stores_each_file_once(env, rows, store_module, monkeypatch):
    request = files(env)                                      # the same bytes are re-sent, as a real retry does
    original = store_module._write_batch
    fail_in(monkeypatch, store_module, "_write_batch", lambda conn, batch: True)
    assert post_batch(*request, **NATIVE).status_code == 500
    monkeypatch.setattr(store_module, "_write_batch", original)   # the database recovers
    retry = post_batch(*request, **NATIVE)
    assert retry.status_code == 200
    assert len(rows("execution_runs")) == 2 and rows("batches") == [retry.json()["batch_id"]]


def files_repeating_a_record_ref_keep_separate_documents(env, rows, store_module, monkeypatch):
    body = post_batch(workbook(env, "a.xlsx", row("SAME", **declared(T.COG, "1.00"))),
                      workbook(env, "b.xlsx", row("SAME", **declared(T.COG, "7.00"))), **NATIVE).json()
    first, second = (f["execution_id"] for f in body["files"])
    a, b = (client.get(f"/api/v1/runs/{run}/financial").json()["records"] for run in (first, second))
    assert [e["record_ref"] for e in a] == [e["record_ref"] for e in b]
    assert a[0]["financial_document"]["payload"]["evidence"]["execution_id"] == first
    assert b[0]["financial_document"]["payload"]["evidence"]["execution_id"] == second
    assert '"7.00"' not in str(a) and '"1.00"' not in str(b)


def exports_run_only_after_the_commit(env, rows, store_module, monkeypatch):
    seen = []
    original = api.export_excel

    def spy(records, path):
        seen.append(rows("batches"))                           # what is committed when the export starts
        return original(records, path)
    monkeypatch.setattr(api, "export_excel", spy)
    body = post_batch(*files(env), persist="true").json()
    assert seen == [[body["batch_id"]]] * 2


def a_failed_export_keeps_the_stored_batch_and_reports_a_warning(env, rows, store_module, monkeypatch):
    original = api.export_excel

    def fail_first(records, path):
        if "api-run-1" in str(path):
            raise OSError("simulated disk failure")
        return original(records, path)
    monkeypatch.setattr(api, "export_excel", fail_first)
    response = post_batch(*files(env), **NATIVE)
    assert response.status_code == 200                             # the data was committed; no misleading 500
    first, second = response.json()["files"]
    assert first["status"] == "SUCCESS" and EXPORT_FAILED_WARNING in first["warnings"]
    assert EXPORT_FAILED_WARNING not in second["warnings"]
    assert len(rows("execution_runs")) == 2 and rows("batches") == [response.json()["batch_id"]]
    assert not exported("api-run-1") and exported("api-run-2")
    stored = client.get(f"/api/v1/batches/{response.json()['batch_id']}").json()["files"][0]
    assert EXPORT_FAILED_WARNING not in stored["warnings"]         # the committed batch is not mutated


SCENARIOS = [every_file_stored_and_linked_with_its_documents,
             a_batch_without_the_opt_in_stores_no_financial_rows,
             a_rejected_file_is_an_outcome_without_a_run,
             a_failing_second_child_write_stores_nothing_and_exports_nothing,
             a_failing_financial_document_write_stores_nothing,
             a_failing_batch_write_after_every_child_stores_nothing,
             a_global_database_failure_stores_nothing,
             a_retry_after_a_failure_stores_each_file_once,
             files_repeating_a_record_ref_keep_separate_documents,
             exports_run_only_after_the_commit,
             a_failed_export_keeps_the_stored_batch_and_reports_a_warning]


# -- SQLite ---------------------------------------------------------------------------------

@pytest.fixture
def sqlite_rows(env):
    def rows(table):
        if not (env / "api.db").exists():
            return []
        column = "batch_id" if table.startswith("batch") else "execution_id"
        with sqlite3.connect(env / "api.db") as conn:
            return [value for (value,) in conn.execute(f"SELECT {column} FROM {table}")]
    return rows


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.__name__)
def test_sqlite(scenario, env, sqlite_rows, monkeypatch):
    scenario(env, sqlite_rows, sqlite_module, monkeypatch)


def test_the_endpoint_persists_through_save_batch_with_runs_only(env, monkeypatch):
    """The real atomic path is used: one save_batch_with_runs call per request,
    and neither a per-child save nor a separate batch save."""
    from juval.application.tenancy import LAB_ORGANIZATION_ID
    from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
    calls = []
    original = SqliteExecutionRunStore.save_batch_with_runs

    def spy(self, batch, runs, owner):
        assert owner.organization_id == LAB_ORGANIZATION_ID  # ADR-056: one owner for batch and children
        calls.append((batch.batch_id, [item.run.execution_id for item in runs]))
        return original(self, batch, runs, owner)

    def forbidden(*args, **kwargs):
        raise AssertionError("the batch endpoint must not save child by child")
    monkeypatch.setattr(SqliteExecutionRunStore, "save_batch_with_runs", spy)
    monkeypatch.setattr(SqliteExecutionRunStore, "save_execution_run", forbidden)
    monkeypatch.setattr(SqliteExecutionRunStore, "save_batch", forbidden)
    body = post_batch(("notes.txt", b"x"), *files(env), ("broken.xlsx", b"not a zip"), **NATIVE).json()
    assert body["persisted"] is True
    assert calls == [("api-run-0", ["api-run-1", "api-run-2", "api-run-3"])]   # REJECTED has no run; FAILED does
