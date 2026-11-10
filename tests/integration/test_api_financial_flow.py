"""POST /api/v1/runs with native financial evidence -> persistence -> GET (ADR-047).

Temporary SQLite only, synthetic workbooks only. The documents the API
persists are compared with the ones the application functions build directly
from the same file, so the API is shown to add no financial logic of its own.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import juval

from juval.application.financial_serialization_v2 import serialize_financial_record_v2
from juval.application.native_financial_documents import build_financial_documents, declared_financial_target
from juval.application.run_pipeline import run_pipeline_with_financial_evidence
from juval.domain.decision import Thresholds
from juval.domain.costs import FeeInputs
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.risk import Severity
from juval.infrastructure.logging import sqlite_execution_run_store as sqlite_module
from juval.interfaces.api import main as api
from juval.interfaces.api import service
from juval.interfaces.api.main import app
from .api_lab import LOOPBACK, add_member

from .test_api_auth import ISSUER, bearer, enable_auth, keypair, make_token  # noqa: F401 (fixtures)
from .test_cli_native_financial import row
from .test_native_financial_capture import BASE, declared, xlsx

NOW = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
THRESHOLDS = json.dumps({"target_profit": "5", "target_roi": "0.3", "minimum_estimated_monthly_sales": 0,
                         "maximum_risk_severity": "LOW"})
FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})
NATIVE = {"persist": "true", "native_financial_evidence": "true", "financial_target_profit": "3",
          "financial_target_profit_currency": "USD", "financial_target_roi": "0.30"}
ROWS = [row("FULL"),
        row("PARTIAL", **declared(T.COG, "4.50", source_basis="carton")),
        {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")},
        row("INFERRED", **declared(T.COG, "4.50", applies_method="supplier estimate")),
        row("DROPPED", marketplace="")]
DOC, DIAG = "execution_run_financial_records", "execution_run_capture_diagnostics"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path / "runs"))
    monkeypatch.delenv("JUVAL_EXECUTION_STORE", raising=False)
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.setattr(service, "now_utc", lambda: NOW)
    ids = iter(f"api-run-{n}" for n in range(100))
    monkeypatch.setattr(service, "new_execution_id", lambda: next(ids))
    return tmp_path


client = TestClient(app, raise_server_exceptions=False, **LOOPBACK)
pytestmark = pytest.mark.usefixtures("auth_lab")  # ADR-055: explicit loopback lab


def post(path, **data):
    body = {"thresholds": THRESHOLDS, "fees": FEES, **data}
    with open(path, "rb") as handle:
        return client.post("/api/v1/runs", data=body,
                           files={"file": (path.name, handle.read(), "application/octet-stream")})


def count(env, table):
    with sqlite3.connect(env / "api.db") as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def financial(execution_id, **params):
    response = client.get(f"/api/v1/runs/{execution_id}/financial", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# -- Write path ---------------------------------------------------------------------

def test_post_persists_the_documents_the_application_builds(env):
    path = xlsx(env, *ROWS)
    response = post(path, **NATIVE)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["persisted"] is True
    assert body["financial"] == {"captures": 4, "documents": 3, "without_scenario": 1,
                                 "capture_diagnostics_sets": 4, "capture_problems": 2}
    # The same file through the application functions alone, with the same targets.
    outcome = run_pipeline_with_financial_evidence(
        path, Thresholds(Decimal("5"), Decimal("0.3"), 0, Severity.LOW),
        fees=FeeInputs(Decimal("3"), Decimal("0.15"), Decimal("2")),
        application_version=juval.__version__, execution_id=body["execution_id"], now=NOW)
    targets = dict(target_profit=declared_financial_target(Decimal("3"), "USD", source="juval-api",
                                                           method="request field financial_target_profit",
                                                           retrieved_at=NOW),
                   target_roi=declared_financial_target(Decimal("0.30"), "ratio", source="juval-api",
                                                        method="request field financial_target_roi",
                                                        retrieved_at=NOW))
    expected = {d.document.evidence.record_reference: serialize_financial_record_v2(d)
                for d in build_financial_documents(outcome, calculated_at=NOW,
                                                   application_version=outcome.run.application_version, **targets)}
    stored = {e["record_ref"]: e["financial_document"] for e in financial(body["execution_id"])["records"]}
    assert {ref: doc["payload"] for ref, doc in stored.items() if doc} == expected
    assert all(doc["version"] == 2 for doc in stored.values() if doc)


def test_states_blocked_results_and_provenance_survive_the_round_trip(env):
    body = post(xlsx(env, *ROWS), **NATIVE).json()
    entries = {e["record_ref"]: e for e in financial(body["execution_id"])["records"]}
    full, partial, no_scenario, inferred = sorted(entries)
    text = {ref: json.dumps(entry) for ref, entry in entries.items()}
    assert '"USER_INPUT"' in text[full] and '"juval-api"' in text[full]                  # targets: operator input
    assert '"SUPPLIER_FILE"' in text[full] and "AMAZON" not in text[full]               # supplier stays supplier
    assert '"INFERRED"' in text[inferred]
    partial_terms = [t["term"] for t in entries[partial]["financial_document"]["payload"]["evidence"]["terms"]]
    assert "COG" not in partial_terms and "COG" in json.dumps(entries[partial]["capture_diagnostics"])  # absent, not 0
    calculations = entries[partial]["financial_document"]["payload"]["calculations"]["calculations"]
    blocked = [c for c in calculations if c["blocker"]]
    assert blocked and all(c["value"]["value"] is None for c in blocked)                 # blocked, never zero
    assert entries[no_scenario]["financial_document"] is None
    assert entries[no_scenario]["capture_diagnostics"]["payload"]["diagnostics"]         # why: undeclared scenario
    assert entries[full]["capture_diagnostics"]["payload"]["diagnostics"] == []          # stored and empty


def test_invalid_declared_amount_stays_invalid_with_its_raw_value(env):
    body = post(xlsx(env, row("BAD", **declared(T.COG, "abc"))), **NATIVE).json()
    [entry] = financial(body["execution_id"])["records"]
    payload = entry["financial_document"]["payload"]
    text = json.dumps(payload["evidence"])
    assert '"INVALID"' in text and '"abc"' in text                                       # kept for diagnosis
    blocked = {c["result"]: c for c in payload["calculations"]["calculations"] if c["blocker"]}
    assert "PROFIT" in blocked and blocked["PROFIT"]["value"]["value"] is None


def test_financial_flow_changes_no_record_or_decision(env):
    path = xlsx(env, *ROWS)
    plain = post(path, persist="true").json()
    native = post(path, **NATIVE).json()
    assert native["records"] == plain["records"]
    assert plain["financial"] is None


def test_existing_clients_are_unchanged_and_store_no_financial_rows(env):
    body = post(xlsx(env, *ROWS), persist="true").json()
    assert body["persisted"] is True and body["financial"] is None
    assert count(env, DOC) == count(env, DIAG) == 0
    entries = financial(body["execution_id"])["records"]
    assert entries and all(e["financial_document"] is None and e["capture_diagnostics"] is None for e in entries)
    assert post(xlsx(env, *ROWS)).json()["persisted"] is False                          # no persist, as before


@pytest.mark.parametrize("data, detail", [
    ({"native_financial_evidence": "true"}, "native_financial_evidence requires persist=true"),
    ({"persist": "true", "financial_target_roi": "0.3"}, "financial_target_* fields require native_financial_evidence=true"),
    ({**NATIVE, "financial_target_profit_currency": ""}, "go together"),
    ({**NATIVE, "financial_target_roi": "NaN"}, None),
    ({**NATIVE, "financial_target_profit": "Infinity"}, None),
])
def test_invalid_financial_options_are_422_and_persist_nothing(env, data, detail):
    data = {k: v for k, v in data.items() if v != ""}
    response = post(xlsx(env, *ROWS), **data)
    assert response.status_code == 422
    if detail:
        assert detail in response.json()["detail"]
    assert not (env / "api.db").exists() or count(env, DOC) == 0


def test_a_failing_financial_write_persists_nothing(env, monkeypatch):
    def fail(execution_id, payload):
        raise sqlite3.IntegrityError("simulated failure after the run and snapshot inserts")
    monkeypatch.setattr(sqlite_module, "_diagnostics_row", fail)
    response = post(xlsx(env, *ROWS), **NATIVE)
    assert response.status_code == 500 and response.json() == {"detail": "internal server error"}
    assert client.get("/api/v1/runs/api-run-0").status_code == 404
    with sqlite3.connect(env / "api.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM execution_run_records").fetchone()[0] == 0
    assert count(env, DOC) == count(env, DIAG) == 0


# -- Read path -----------------------------------------------------------------------

def test_runs_are_isolated_and_pages_are_stable(env):
    a = post(xlsx(env, *ROWS), **NATIVE).json()["execution_id"]
    b = post(xlsx(env, row("FULL", **declared(T.COG, "7.00")), name="b.xlsx"), **NATIVE).json()["execution_id"]
    whole = financial(a)["records"]
    assert [e["record_ref"] for e in whole] == sorted(e["record_ref"] for e in whole)
    assert financial(a, limit=2, offset=1)["records"] == whole[1:3]
    assert financial(a, limit=2, offset=1)["records"] == whole[1:3]                      # same page twice
    [other] = financial(b)["records"]
    assert other["record_ref"] == whole[0]["record_ref"]                                 # same record_ref
    assert '"7.00"' in json.dumps(other) and '"7.00"' not in json.dumps(whole[0])


def test_a_page_costs_the_same_connections_whatever_its_size(env, monkeypatch):
    execution_id = post(xlsx(env, *ROWS), **NATIVE).json()["execution_id"]
    real = sqlite3.connect
    calls = []

    def counting(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)
    monkeypatch.setattr(sqlite_module.sqlite3, "connect", counting)
    per_page = []
    for limit in (1, 4):
        calls.clear()
        assert len(financial(execution_id, limit=limit)["records"]) == limit
        per_page.append(len(calls))
    assert per_page[0] == per_page[1] <= 4                        # constant: store init, run, page, one batch read


# -- Access ----------------------------------------------------------------------------

def test_post_requires_runs_create_and_get_requires_runs_read(env, enable_auth, keypair):
    path = xlsx(env, *ROWS)
    assert post(path, **NATIVE).status_code == 401
    add_member(env / "api.db", ISSUER)  # ADR-056: one organization for this test identity
    viewer = bearer(make_token(keypair, roles=("viewer",)))
    with open(path, "rb") as handle:
        refused = client.post("/api/v1/runs", headers=viewer, data={"thresholds": THRESHOLDS, "fees": FEES, **NATIVE},
                              files={"file": (path.name, handle.read(), "application/octet-stream")})
    assert refused.status_code == 403
    assert not (env / "api.db").exists() or count(env, DOC) == 0
    operator = bearer(make_token(keypair, roles=("operator",)))
    with open(path, "rb") as handle:
        created = client.post("/api/v1/runs", headers=operator, data={"thresholds": THRESHOLDS, "fees": FEES, **NATIVE},
                              files={"file": (path.name, handle.read(), "application/octet-stream")})
    assert created.status_code == 200, created.text
    url = f"/api/v1/runs/{created.json()['execution_id']}/financial"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=bearer(make_token(keypair, roles=()))).status_code == 403
    assert client.get(url, headers=viewer).status_code == 200
