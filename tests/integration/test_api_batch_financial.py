"""POST /api/v1/batches with native financial evidence (ADR-047 step 7, ADR-025).

Temporary SQLite only, synthetic workbooks only. Each child's documents are
compared with what the application functions build from that file alone, so
the batch path is shown to add no financial logic and to share nothing
between files.
"""
from __future__ import annotations

import json
import sqlite3
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import juval
from juval.application.financial_persistence import load_financial_record
from juval.application.financial_recalculation import check_recalculation
from juval.application.financial_serialization_v2 import serialize_financial_record_v2
from juval.application.native_financial_documents import build_financial_documents, declared_financial_target
from juval.application.run_pipeline import run_pipeline_with_financial_evidence
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.risk import Severity
from juval.infrastructure.logging import sqlite_execution_run_store as sqlite_module
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app

from .test_api_financial_flow import DIAG, DOC, FEES, NATIVE, NOW, ROWS, THRESHOLDS, count, env, financial  # noqa: F401
from .test_cli_native_financial import row
from .test_native_financial_capture import declared, xlsx

client = TestClient(app, raise_server_exceptions=False)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def post_batch(*files, **data):
    body = {"thresholds": THRESHOLDS, "fees": FEES, **data}
    return client.post("/api/v1/batches", data=body,
                       files=[("files", (name, content, XLSX)) for name, content in files])


def workbook(env, name, *rows):
    return name, xlsx(env, *rows, name=f"src/{name}").read_bytes()


def expected_documents(env, name, content, execution_id):
    """What the application functions alone build from this one file."""
    path = env / "expected" / execution_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    outcome = run_pipeline_with_financial_evidence(
        path, Thresholds(Decimal("5"), Decimal("0.3"), 0, Severity.LOW),
        fees=FeeInputs(Decimal("3"), Decimal("0.15"), Decimal("2")),
        application_version=juval.__version__, execution_id=execution_id, now=NOW)
    targets = dict(
        target_profit=declared_financial_target(Decimal("3"), "USD", source="juval-api",
                                                method="request field financial_target_profit", retrieved_at=NOW),
        target_roi=declared_financial_target(Decimal("0.30"), "ratio", source="juval-api",
                                             method="request field financial_target_roi", retrieved_at=NOW))
    return {d.document.evidence.record_reference: serialize_financial_record_v2(d)
            for d in build_financial_documents(outcome, calculated_at=NOW,
                                               application_version=outcome.run.application_version, **targets)}


def stored_documents(execution_id):
    return {e["record_ref"]: e["financial_document"]["payload"]
            for e in financial(execution_id)["records"] if e["financial_document"]}


def rows_of(env, table, column="execution_id"):
    with sqlite3.connect(env / "api.db") as conn:
        return [value for (value,) in conn.execute(f"SELECT {column} FROM {table} ORDER BY {column}")]


def without_ids(body):
    body = json.loads(json.dumps(body))
    body.pop("batch_id")
    for item in body["files"]:
        item.pop("execution_id")
    return body


# -- Opt-in absent: the previous behavior --------------------------------------------

def test_a_batch_without_the_opt_in_is_unchanged_and_stores_no_financial_rows(env):
    files = (workbook(env, "a.xlsx", *ROWS), workbook(env, "b.xlsx", row("B")))
    plain = post_batch(*files, persist="true")
    assert plain.status_code == 200, plain.text
    assert count(env, DOC) == count(env, DIAG) == 0
    for item in plain.json()["files"]:
        entries = financial(item["execution_id"])["records"]
        assert entries and all(e["financial_document"] is None and e["capture_diagnostics"] is None
                               for e in entries)
    native = post_batch(*files, **NATIVE)
    assert native.status_code == 200, native.text
    assert without_ids(native.json()) == without_ids(plain.json())       # same response shape and content
    for before, after in zip(plain.json()["files"], native.json()["files"]):
        old = client.get(f"/api/v1/runs/{before['execution_id']}/records", params={"limit": 50}).json()["records"]
        new = client.get(f"/api/v1/runs/{after['execution_id']}/records", params={"limit": 50}).json()["records"]
        assert [{k: v for k, v in r.items() if k != "execution_id"} for r in new] == \
               [{k: v for k, v in r.items() if k != "execution_id"} for r in old]   # records/decisions unchanged


# -- Opt-in: one child, one transaction, one set of documents -------------------------

def test_each_child_stores_exactly_the_documents_its_own_file_produces(env):
    files = (workbook(env, "a.xlsx", *ROWS), workbook(env, "b.xlsx", row("B", **declared(T.COG, "7.00"))))
    response = post_batch(*files, **NATIVE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["persisted"] is True and body["status"] == "SUCCESS"
    children = [item["execution_id"] for item in body["files"]]
    assert len(set(children)) == 2 and body["batch_id"] not in children
    for (name, content), execution_id in zip(files, children):
        expected = expected_documents(env, name, content, execution_id)
        assert expected and stored_documents(execution_id) == expected
    assert rows_of(env, DOC) == sorted([children[0]] * 3 + [children[1]])    # 3 scenarios in a, 1 in b
    assert rows_of(env, DIAG) == sorted([children[0]] * 4 + [children[1]])   # one set per captured record


def test_children_do_not_share_documents_or_record_identities(env):
    files = (workbook(env, "a.xlsx", row("SAME", **declared(T.COG, "1.00"))),
             workbook(env, "b.xlsx", row("SAME", **declared(T.COG, "7.00"))))
    first, second = (item["execution_id"] for item in post_batch(*files, **NATIVE).json()["files"])
    a, b = stored_documents(first), stored_documents(second)
    assert a.keys() == b.keys()                                            # same record_ref, different runs
    [ref] = a
    cog = {run: json.dumps(docs[ref]["evidence"]) for run, docs in ((first, a), (second, b))}
    assert '"1.00"' in cog[first] and '"7.00"' not in cog[first]
    assert '"7.00"' in cog[second] and '"1.00"' not in cog[second]
    assert a[ref]["evidence"]["execution_id"] == first and b[ref]["evidence"]["execution_id"] == second
    assert client.get(f"/api/v1/runs/{first}/batch").json()["batch_id"] == \
           client.get(f"/api/v1/runs/{second}/batch").json()["batch_id"]


def test_absent_and_invalid_evidence_keep_their_states_in_a_batch(env):
    files = (workbook(env, "a.xlsx", *ROWS), workbook(env, "bad.xlsx", row("BAD", **declared(T.COG, "abc"))))
    first, second = (item["execution_id"] for item in post_batch(*files, **NATIVE).json()["files"])
    entries = {e["record_ref"]: e for e in financial(first)["records"]}
    full, partial, no_scenario, inferred = sorted(entries)
    assert entries[no_scenario]["financial_document"] is None                  # no scenario: no document
    assert entries[no_scenario]["capture_diagnostics"]["payload"]["diagnostics"]
    assert '"INFERRED"' in json.dumps(entries[inferred])
    [bad] = financial(second)["records"]
    text = json.dumps(bad["financial_document"]["payload"]["evidence"])
    assert '"INVALID"' in text and '"abc"' in text                             # kept with its raw value
    blocked = {c["result"]: c for c in bad["financial_document"]["payload"]["calculations"]["calculations"]
               if c["blocker"]}
    assert blocked["PROFIT"]["value"]["value"] is None                         # blocked, never zero


def test_rejected_and_unreadable_files_do_not_affect_their_siblings(env):
    files = (("notes.txt", b"not a workbook"), ("broken.xlsx", b"this is not a zip archive"),
             workbook(env, "good.xlsx", row("G")))
    response = post_batch(*files, **NATIVE)
    assert response.status_code == 200, response.text
    rejected, failed, good = response.json()["files"]
    assert response.json()["status"] == "PARTIAL_SUCCESS"
    assert rejected["status"] == "REJECTED" and rejected["execution_id"] is None
    assert failed["status"] == "FAILED" and good["status"] == "SUCCESS"
    assert financial(failed["execution_id"])["records"] == []                  # run stored, nothing financial
    assert stored_documents(good["execution_id"]) == expected_documents(env, *files[2], good["execution_id"])
    assert rows_of(env, DOC) == [good["execution_id"]]


def test_documents_stored_by_a_batch_recalculate_under_the_current_code(env):
    body = post_batch(workbook(env, "a.xlsx", *ROWS), workbook(env, "b.xlsx", row("B")), **NATIVE).json()
    store = SqliteExecutionRunStore(env / "api.db")
    for item in body["files"]:
        for ref in stored_documents(item["execution_id"]):
            assert check_recalculation(load_financial_record(store, item["execution_id"], ref)).matches


# -- Options and failures ----------------------------------------------------------------

@pytest.mark.parametrize("data, detail", [
    ({"native_financial_evidence": "true"}, "native_financial_evidence requires persist=true"),
    ({"persist": "true", "financial_target_roi": "0.3"}, "financial_target_* fields require native_financial_evidence=true"),
    ({**NATIVE, "financial_target_profit_currency": ""}, "go together"),
    ({**NATIVE, "financial_target_roi": "NaN"}, None),
])
def test_invalid_financial_options_are_422_and_process_nothing(env, data, detail):
    data = {k: v for k, v in data.items() if v != ""}
    response = post_batch(workbook(env, "a.xlsx", *ROWS), **data)
    assert response.status_code == 422
    if detail:
        assert detail in response.json()["detail"]
    assert not (env / "api.db").exists() or (rows_of(env, "execution_runs") == [] and count(env, DOC) == 0)
    assert not (env / "runs").exists() or not any((env / "runs").rglob("*.xlsx"))


def test_a_failing_financial_write_keeps_the_existing_batch_failure_semantics(env, monkeypatch):
    """ADR-025 leaves per-file isolation of *persistence* failures undecided, so the
    opt-in keeps today's semantics: the failing child persists nothing (its own
    transaction rolls back), earlier children stay, the request is a generic 500
    and no batch row is written."""
    original = sqlite_module._diagnostics_row

    def fail_second_child(execution_id, payload):
        if execution_id == "api-run-2":
            raise sqlite3.IntegrityError("simulated failure after the run and snapshot inserts")
        return original(execution_id, payload)
    monkeypatch.setattr(sqlite_module, "_diagnostics_row", fail_second_child)
    response = post_batch(workbook(env, "a.xlsx", row("A")), workbook(env, "b.xlsx", row("B")), **NATIVE)
    assert response.status_code == 500 and response.json() == {"detail": "internal server error"}
    assert rows_of(env, "execution_runs") == ["api-run-1"]
    assert rows_of(env, DOC) == rows_of(env, DIAG) == ["api-run-1"]
    assert rows_of(env, "execution_run_records") == ["api-run-1"]
    assert rows_of(env, "batches", "batch_id") == []
