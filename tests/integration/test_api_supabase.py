"""End-to-end integration: FastAPI -> composition root -> Supabase/PostgreSQL.

Covers the one path nothing else did. `test_supabase_execution_run_store.py`
exercises the Store directly; `test_api.py` exercises the API but only against
SQLite. Neither proves that a real HTTP request to the real application, going
through the real composition root, actually lands in Supabase and can be read
back out through the API.

Runs only when JUVAL_SUPABASE_DB_URL points at a live project (ADR-017). No
mocks, no SQLite, no fakes. Every row this test creates is removed in a
`finally`, scoped to its own execution_id.

Guard against a false pass: the SQLite connection variable is deliberately
unset and the composition root's concrete type is asserted, so this test
cannot accidentally go green against SQLite -- which would be worse than no
test at all, since it would claim Supabase coverage that does not exist.

The DSN is read from the environment only; it is never printed, logged,
hardcoded or asserted against.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

psycopg = pytest.importorskip("psycopg")

from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore
from juval.interfaces.api.main import _execution_run_store, app

DB_URL = os.environ.get("JUVAL_SUPABASE_DB_URL")

pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="JUVAL_SUPABASE_DB_URL not set -- no live Supabase project to test against",
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"

_THRESHOLDS = json.dumps(
    {
        "target_profit": "5",
        "target_roi": "0.3",
        "minimum_estimated_monthly_sales": 0,
        "maximum_risk_severity": "LOW",
    }
)
_FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})


@pytest.fixture
def supabase_client(tmp_path, monkeypatch):
    """A TestClient whose composition root can only resolve to Supabase."""
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")
    # Removed on purpose: if the selector were ever ignored, SQLite would have
    # nowhere to write and the test would fail loudly instead of passing for
    # the wrong reason.
    monkeypatch.delenv("JUVAL_EXECUTION_DB_PATH", raising=False)
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    return TestClient(app)


def _delete_run(execution_id: str) -> None:
    """Remove a run and its records. Child rows first -- the FK has no cascade."""
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("delete from execution_run_records where execution_id = %s", (execution_id,))
            cur.execute("delete from execution_runs where execution_id = %s", (execution_id,))
        conn.commit()


def _row_count(table: str, execution_id: str) -> int:
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"select count(*) from {table} where execution_id = %s", (execution_id,))
            return cur.fetchone()[0]


def _upload(client, *, persist="true"):
    return client.post(
        "/api/v1/runs",
        files={
            "file": (
                "sample.xlsx",
                FIXTURE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"thresholds": _THRESHOLDS, "fees": _FEES, "persist": persist},
    )


def test_composition_root_resolves_to_supabase(supabase_client):
    """The precondition every other test here depends on."""
    assert isinstance(_execution_run_store(), SupabaseExecutionRunStore)


def test_api_persists_and_reads_back_through_supabase(supabase_client):
    """POST -> Supabase -> GET summary -> GET records, all over real HTTP."""
    response = _upload(supabase_client)
    assert response.status_code == 200
    body = response.json()
    execution_id = body["execution_id"]

    try:
        assert body["persisted"] is True
        assert body["records"], "the fixture must produce at least one record"
        expected_records = len(body["records"])

        # The row is really in PostgreSQL -- independent confirmation, not a
        # substitute for the application operation above.
        assert _row_count("execution_runs", execution_id) == 1
        assert _row_count("execution_run_records", execution_id) == expected_records

        summary = supabase_client.get(f"/api/v1/runs/{execution_id}")
        assert summary.status_code == 200
        summary_body = summary.json()
        assert summary_body["execution_id"] == execution_id
        assert summary_body["status"] == body["status"]
        assert summary_body["records_total"] == body["records_total"]
        assert summary_body["input_hash"] == body["input_hash"]

        records = supabase_client.get(f"/api/v1/runs/{execution_id}/records")
        assert records.status_code == 200
        records_body = records.json()
        assert records_body["execution_id"] == execution_id
        assert len(records_body["records"]) == expected_records

        listing = supabase_client.get("/api/v1/runs")
        assert listing.status_code == 200
        assert execution_id in [item["execution_id"] for item in listing.json()["items"]]
    finally:
        _delete_run(execution_id)

    assert _row_count("execution_runs", execution_id) == 0
    assert _row_count("execution_run_records", execution_id) == 0


def test_api_does_not_persist_to_supabase_without_persist_flag(supabase_client):
    """persist is opt-in (ADR-013 Option B) -- unchanged by the Supabase path."""
    response = _upload(supabase_client, persist="false")
    assert response.status_code == 200
    body = response.json()
    execution_id = body["execution_id"]

    try:
        assert body["persisted"] is False
        assert _row_count("execution_runs", execution_id) == 0
    finally:
        _delete_run(execution_id)  # no-op unless something unexpectedly persisted


def test_supabase_mode_without_dsn_fails_fast(monkeypatch):
    """A selected mode missing its connection variable must not degrade."""
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)
    with pytest.raises(RuntimeError, match="JUVAL_SUPABASE_DB_URL"):
        _execution_run_store()
