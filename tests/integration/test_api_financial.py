"""Read-only ADR-047 financial API over a temporary SQLite store. Synthetic data only.

The database is written by the real CLI native financial flow (v2 documents and
diagnostics) plus a v1 document and a legacy run, then read over HTTP.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from juval.application.financial_calculation import calculate_financial_results
from juval.application.financial_persistence import (
    FinancialStorageUnavailable, load_financial_record, save_run_with_financial_records,
)
from juval.application.financial_serialization import FinancialRecordDocument
from juval.domain.financial_dependencies import FinancialResult
from juval.domain.financial_evidence import FinancialTerm as T
from juval.interfaces.api import main as api
from juval.interfaces.api.main import app
from .api_lab import LOOPBACK

from .test_api_auth import bearer, enable_auth, keypair, make_token  # noqa: F401 (fixtures)
from .test_cli_native_financial import FINANCIAL, cli_run, fixed_now, refs, row  # noqa: F401 (fixture)
from .test_native_financial_capture import BASE, declared

DOC, DIAG = "execution_run_financial_records", "execution_run_capture_diagnostics"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """run-A: CLI v2 flow; run-B: same record_ref, other COG; run-L: legacy CLI
    (run only); run-H: historical run with a snapshot and no financial rows;
    run-OLD: a v1 document without a diagnostics set."""
    rows = [row("FULL"),
            row("PARTIAL", **declared(T.COG, "4.50", source_basis="carton")),
            {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")},
            row("INFERRED", **declared(T.COG, "4.50", applies_method="supplier estimate")),
            row("DROPPED", marketplace="")]
    assert cli_run(tmp_path, rows, *FINANCIAL)[0] == 0
    assert cli_run(tmp_path, [row("FULL", **declared(T.COG, "7.00"))], *FINANCIAL, execution_id="run-B")[0] == 0
    store = cli_run(tmp_path, [row("FULL")], execution_id="run-L")[2]               # legacy CLI: run only
    assert store.load_records("run-L") == []
    ref = refs(store)[0]
    snapshot = store.load_record("run-A", ref)
    store.save_execution_run(replace(store.load_execution_run("run-A"), execution_id="run-H"), [snapshot])
    core = load_financial_record(store, "run-A", ref).document
    evidence, resolution = replace(core.evidence, execution_id="run-OLD"), replace(core.resolution, execution_id="run-OLD")
    calculated_at = core.calculations.calculations[0].value.provenance.retrieved_at
    v1 = FinancialRecordDocument(evidence, core.selling_price, resolution, calculate_financial_results(
        resolution, calculated_at=calculated_at, requested=frozenset({FinancialResult.PROFIT})))
    save_run_with_financial_records(store, replace(store.load_execution_run("run-A"), execution_id="run-OLD"),
                                    [snapshot], [v1])
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.delenv("JUVAL_EXECUTION_STORE", raising=False)
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    return tmp_path / "runs.db", store


client = TestClient(app, raise_server_exceptions=False, **LOOPBACK)
pytestmark = pytest.mark.usefixtures("auth_lab")  # ADR-055: explicit loopback lab


def stored(store, table_loader, execution_id, ref):
    row_ = table_loader(execution_id, ref)
    return None if row_ is None else {"format": row_[0], "version": row_[1], "payload": json.loads(row_[2])}


def by_ref(body):
    return {entry["record_ref"]: entry for entry in body["records"]}


# -- Content ---------------------------------------------------------------------

def test_run_financial_returns_every_stored_payload_unchanged(db):
    _, store = db
    response = client.get("/api/v1/runs/run-A/financial")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_id"] == "run-A" and body["pagination"]["total"] == 4       # DROPPED has no record
    entries = by_ref(body)
    assert set(entries) == set(refs(store))
    for ref, entry in entries.items():
        assert entry["financial_document"] == stored(store, store.load_financial_record, "run-A", ref)
        assert entry["capture_diagnostics"] == stored(store, store.load_capture_diagnostics, "run-A", ref)
        assert entry["inconsistencies"] == []
    full, partial, no_scenario, inferred = refs(store)
    assert entries[full]["financial_document"]["format"] == "juval.adr047.financial-record"
    assert entries[full]["financial_document"]["version"] == 2
    assert entries[full]["capture_diagnostics"]["payload"]["diagnostics"] == []         # stored and empty
    assert entries[partial]["capture_diagnostics"]["payload"]["diagnostics"][0]["code"] == "SOURCE_BASIS_INVALID"
    assert entries[no_scenario]["financial_document"] is None                            # absent, not zero
    assert entries[no_scenario]["capture_diagnostics"]["payload"]["diagnostics"]


def test_states_and_provenance_travel_unchanged(db):
    _, store = db
    entries = by_ref(client.get("/api/v1/runs/run-A/financial").json())
    full, partial, _, inferred = refs(store)
    text = json.dumps(entries[inferred]["financial_document"])
    assert '"INFERRED"' in text                                                         # never promoted
    calculations = entries[partial]["financial_document"]["payload"]["calculations"]["calculations"]
    blocked = [c for c in calculations if c["blocker"] == "DEPENDENCIES_UNRESOLVED"]
    assert blocked and all(c["value"]["value"] is None for c in blocked)                 # invalid COG: never zero
    assert all("NOT_FOUND" in json.dumps(c["value"]) for c in blocked)
    source_types = set()

    def walk(node):
        if isinstance(node, dict):
            if "source_type" in node:
                source_types.add(node["source_type"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(entries[full]["financial_document"]["payload"])
    assert source_types and not any("AMAZON" in s for s in source_types)                 # supplier stays supplier


def test_record_financial_matches_the_run_entry(db):
    _, store = db
    entries = by_ref(client.get("/api/v1/runs/run-A/financial").json())
    for ref in refs(store):
        response = client.get(f"/api/v1/runs/run-A/records/{ref}/financial")
        assert response.status_code == 200 and response.json() == entries[ref]


def test_v1_document_is_served_as_v1_without_a_diagnostics_set(db):
    body = client.get("/api/v1/runs/run-OLD/financial").json()
    [entry] = body["records"]
    assert entry["financial_document"]["version"] == 1
    assert entry["financial_document"]["payload"]["version"] == 1
    assert entry["capture_diagnostics"] is None                                          # not stored, not empty


def test_historical_runs_have_no_financial_payloads(db):
    body = client.get("/api/v1/runs/run-H/financial").json()
    assert body["pagination"]["total"] == 1
    assert body["records"][0]["financial_document"] is None
    assert body["records"][0]["capture_diagnostics"] is None
    ref = body["records"][0]["record_ref"]
    assert client.get(f"/api/v1/runs/run-H/records/{ref}/financial").json() == body["records"][0]
    legacy = client.get("/api/v1/runs/run-L/financial")                                # run without snapshots
    assert legacy.status_code == 200 and legacy.json()["records"] == []


def test_runs_are_isolated_under_the_same_record_ref(db):
    _, store = db
    ref = refs(store)[0]
    assert ref == refs(store, "run-B")[0]
    a = client.get(f"/api/v1/runs/run-A/records/{ref}/financial").json()
    b = client.get(f"/api/v1/runs/run-B/records/{ref}/financial").json()
    assert a["execution_id"] == "run-A" and b["execution_id"] == "run-B"
    assert '"7.00"' in json.dumps(b) and '"7.00"' not in json.dumps(a)


def test_pagination_follows_the_records_endpoint(db):
    full = client.get("/api/v1/runs/run-A/financial").json()["records"]
    page = client.get("/api/v1/runs/run-A/financial", params={"limit": 2, "offset": 1}).json()
    assert page["records"] == full[1:3]
    assert page["pagination"] == {"limit": 2, "offset": 1, "total": 4, "has_more": True}
    assert client.get("/api/v1/runs/run-A/financial", params={"limit": 101}).status_code == 422


# -- Absence and errors -----------------------------------------------------------

def test_unknown_run_and_record_are_404(db):
    _, store = db
    ref = refs(store)[0]
    unknown_run = client.get("/api/v1/runs/run-Z/financial")
    assert unknown_run.status_code == 404 and unknown_run.json()["detail"] == "unknown execution_id"
    for path in (f"/api/v1/runs/run-Z/records/{ref}/financial", "/api/v1/runs/run-A/records/row_99/financial"):
        response = client.get(path)
        assert response.status_code == 404 and response.json()["detail"] == "unknown record for execution"


def tamper(path, sql, *params):
    with sqlite3.connect(path) as conn:
        conn.execute(sql, params)


@pytest.mark.parametrize("statement", [
    f"UPDATE {DOC} SET payload = 'not json {{' WHERE record_ref = ?",
    f"UPDATE {DOC} SET format_version = 1 WHERE record_ref = ?",
    f"UPDATE {DIAG} SET payload = replace(payload, '\"run-A\"', '\"run-B\"') WHERE record_ref = ?",
])
def test_invalid_stored_data_is_a_500_that_leaks_nothing(db, statement):
    path, store = db
    ref = refs(store)[0]
    tamper(path, statement, ref)
    for url in ("/api/v1/runs/run-A/financial", f"/api/v1/runs/run-A/records/{ref}/financial"):
        response = client.get(url)
        assert response.status_code == 500
        assert response.json() == {"detail": "stored financial data failed validation"}


def test_missing_financial_tables_are_a_503_not_an_empty_answer(db, monkeypatch):
    _, store = db

    class Unmigrated:
        def __getattr__(self, name):
            return getattr(store, name)

        def load_financial_rows(self, *_):
            raise FinancialStorageUnavailable("financial tables do not exist")

    monkeypatch.setattr(api, "_execution_run_store", Unmigrated)
    for url in ("/api/v1/runs/run-A/financial", f"/api/v1/runs/run-A/records/{refs(store)[0]}/financial"):
        response = client.get(url)
        assert response.status_code == 503
        assert response.json() == {"detail": "financial persistence is not available on this deployment"}


def test_unconfigured_store_is_a_500(db, monkeypatch):
    monkeypatch.delenv("JUVAL_EXECUTION_DB_PATH")
    assert client.get("/api/v1/runs/run-A/financial").status_code == 500


# -- Read-only ---------------------------------------------------------------------

def test_endpoints_never_write(db):
    path, store = db
    ref = refs(store)[0]
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    client.get("/api/v1/runs/run-A/financial")
    client.get(f"/api/v1/runs/run-A/records/{ref}/financial")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    for method in ("post", "put", "patch", "delete"):
        for url in ("/api/v1/runs/run-A/financial", f"/api/v1/runs/run-A/records/{ref}/financial"):
            assert getattr(client, method)(url).status_code == 405


# -- Authorization (the existing runs:read contract) ---------------------------------

@pytest.mark.parametrize("path", ["/api/v1/runs/run-A/financial", "/api/v1/runs/run-A/records/x/financial"])
def test_requires_authentication_and_runs_read(db, enable_auth, keypair, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers=bearer("not-a-jwt")).status_code == 401
    assert client.get(path, headers=bearer(make_token(keypair, roles=()))).status_code == 403
    assert client.get(path, headers=bearer(make_token(keypair, roles=("unknown-role",)))).status_code == 403
    viewer = client.get(path, headers=bearer(make_token(keypair, roles=("viewer",))))
    assert viewer.status_code in (200, 404)                                             # authorized; x is unknown


def test_openapi_documents_both_routes_as_get_only():
    schema = app.openapi()
    for path, model in (("/api/v1/runs/{execution_id}/financial", "RunFinancialResponse"),
                        ("/api/v1/runs/{execution_id}/records/{record_ref}/financial", "RecordFinancialOut")):
        assert set(schema["paths"][path]) == {"get"}
        assert schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == \
            {"$ref": f"#/components/schemas/{model}"}
    assert set(schema["components"]["schemas"]["StoredPayloadOut"]["properties"]) == {"format", "version", "payload"}
