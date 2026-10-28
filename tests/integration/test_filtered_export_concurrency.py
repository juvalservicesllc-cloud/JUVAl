"""Regression tests for the filtered-export race (diagnosed 2026-10-28).

`GET /api/v1/runs/{id}/records/export` used to save every export to one fixed
file per run and stream it with FileResponse after the handler returned, so a
second export of the same run could overwrite the file while the first was
being sent: the first caller silently received the other request's filters or
a broken transfer. Each export must be built and delivered independently.
"""

from __future__ import annotations

import asyncio
import io
import json
import threading
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.interfaces.api import main
from juval.interfaces.api.main import app

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_THRESHOLDS = json.dumps({"target_profit": "5", "target_roi": "0.3", "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "LOW"})
_FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "execution_runs.db"))
    monkeypatch.delenv("JUVAL_EXECUTION_STORE", raising=False)
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    return TestClient(app)


@pytest.fixture
def run_id(client):
    response = client.post(
        "/api/v1/runs",
        files={"file": ("sample.xlsx", FIXTURE.read_bytes(), XLSX)},
        data={"thresholds": _THRESHOLDS, "fees": _FEES, "persist": "true"},
    )
    assert response.status_code == 200
    return response.json()["execution_id"]


def _signature(body: bytes):
    """What an export says it contains: its record order and the query it claims to answer."""
    workbook = openpyxl.load_workbook(io.BytesIO(body), read_only=True)
    try:
        refs = tuple(row[0] for row in list(workbook["catalog_export"].iter_rows(values_only=True))[1:])
        meta = {row[0]: row[1] for row in workbook["query_metadata"].iter_rows(values_only=True)}
    finally:
        workbook.close()
    return refs, json.loads(meta["filters"])["decision"], meta["sort"], meta["direction"]


def _records(client, run_id, params):
    """The record order GET /records gives for the same query: the export must match it."""
    records = client.get(f"/api/v1/runs/{run_id}/records", params={**params, "limit": 100}).json()["records"]
    return tuple(record["record_ref"] for record in records)


async def _build(run_id, **query):
    """Call the endpoint directly so the response exists before anything is sent."""
    params = dict(search=None, brand=None, decision=None, sort="record_ref", direction="asc", min_roi=None,
                  min_profit=None, min_margin=None, confidence="VERIFIED_ONLY", hazmat=None, bulky=None,
                  provenance_field=None, provenance_status=None, review_classification=None, _principal=None)
    return await main.export_filtered_records(run_id, **{**params, **query})


async def _send(response):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await response({"type": "http", "method": "GET", "headers": [], "extensions": {}}, receive, send)
    headers = {k.decode().lower(): v.decode() for k, v in messages[0]["headers"]}
    return headers, b"".join(m.get("body", b"") for m in messages[1:])


async def _build_both_then_send(run_id, first, second):
    built = [await _build(run_id, **first), await _build(run_id, **second)]
    return [await _send(response) for response in built]


@pytest.mark.parametrize(
    "first, second",
    [
        ({"decision": "REVIEW"}, {"decision": "PASS"}),
        ({"sort": "roi", "direction": "asc"}, {"sort": "roi", "direction": "desc"}),
    ],
    ids=["different-filters", "different-sort"],
)
def test_an_export_keeps_its_own_query_when_another_is_built_before_it_is_sent(client, run_id, first, second):
    results = asyncio.run(_build_both_then_send(run_id, first, second))

    for query, (headers, body) in zip((first, second), results):
        refs, decision, sort, direction = _signature(body)
        assert refs == _records(client, run_id, query)
        assert decision == query.get("decision")
        assert (sort, direction) == (query.get("sort", "record_ref"), query.get("direction", "asc"))
        assert int(headers["content-length"]) == len(body)
    assert results[0][1] != results[1][1]


def test_concurrent_exports_of_one_run_never_mix(client, run_id):
    queries = [{"decision": "REVIEW"}, {"decision": "PASS"}, {"sort": "roi", "direction": "desc"}, {}]
    expected = {i: _signature(client.get(f"/api/v1/runs/{run_id}/records/export", params=q).content) for i, q in enumerate(queries)}
    failures = []

    def export(i, barrier):
        barrier.wait()
        try:
            response = client.get(f"/api/v1/runs/{run_id}/records/export", params=queries[i])
            if response.status_code != 200 or int(response.headers["content-length"]) != len(response.content):
                failures.append((i, "transfer"))
            elif _signature(response.content) != expected[i]:
                failures.append((i, "content of another request"))
        except Exception as exc:  # a broken transfer or workbook is a failure of this request, not of the thread
            failures.append((i, type(exc).__name__))

    for _ in range(15):
        barrier = threading.Barrier(len(queries))
        threads = [threading.Thread(target=export, args=(i, barrier)) for i in range(len(queries))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert failures == []


def test_export_leaves_no_shared_file_in_the_run_directory(client, run_id, tmp_path):
    client.get(f"/api/v1/runs/{run_id}/records/export", params={"decision": "REVIEW"})
    client.get(f"/api/v1/runs/{run_id}/records/export", params={"decision": "PASS"})

    run_dir = tmp_path / "juval_runs" / run_id
    assert sorted(p.name for p in run_dir.iterdir()) == ["output.xlsx"]


def test_export_http_contract_is_unchanged(client, run_id):
    response = client.get(f"/api/v1/runs/{run_id}/records/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX
    assert response.headers["content-disposition"] == f'attachment; filename="{run_id}-filtered.xlsx"'
    assert int(response.headers["content-length"]) == len(response.content)
    assert client.get("/api/v1/runs/unknown-run/records/export").status_code == 404
    assert client.get(f"/api/v1/runs/{run_id}/records/export", params={"decision": "MAYBE"}).status_code == 422


def test_run_download_is_unchanged(client, run_id, tmp_path):
    response = client.get(f"/api/v1/runs/{run_id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX
    assert response.headers["content-disposition"] == f'attachment; filename="{run_id}.xlsx"'
    assert response.headers["accept-ranges"] == "bytes"
    assert response.content == (tmp_path / "juval_runs" / run_id / "output.xlsx").read_bytes()
