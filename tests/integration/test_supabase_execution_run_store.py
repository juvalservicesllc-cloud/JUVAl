"""Real integration test for SupabaseExecutionRunStore (ADR-017/ADR-019)
— runs only when JUVAL_SUPABASE_DB_URL points at a live Postgres/Supabase
instance. Connects for real (psycopg), no mocks/SQLite/fakes. Every test
row is deleted via a DELETE scoped to its own execution_id in a finally
block -- SupabaseExecutionRunStore intentionally exposes no delete
method (schema changes are migrations-only, ADR-017), so cleanup of a
row this same test created is the one place a direct, narrowly-scoped
SQL statement is justified.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

psycopg = pytest.importorskip("psycopg")

from juval.application.record_snapshot import record_to_snapshot
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.product import Identification, Product
from juval.domain.provenance import FieldValue
from juval.domain.sourcing_record import SourcingRecord
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

DB_URL = os.environ.get("JUVAL_SUPABASE_DB_URL")

pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="JUVAL_SUPABASE_DB_URL not set -- no live Supabase project to test against",
)


def _run(execution_id: str, **overrides) -> ExecutionRun:
    defaults = dict(
        execution_id=execution_id,
        started_at=datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 8, 17, 12, 5, tzinfo=timezone.utc),
        status=ExecutionStatus.SUCCESS,
        input_filename="juval-integration-test.xlsx",
        input_hash="deadbeef",
        application_version="test",
        records_total=3,
        records_processed=3,
        records_successful=3,
        records_with_errors=0,
        warnings=0,
    )
    defaults.update(overrides)
    return ExecutionRun(**defaults)


def _cleanup(execution_id: str) -> None:
    with psycopg.connect(DB_URL) as conn:
        conn.execute("DELETE FROM execution_run_records WHERE execution_id = %s", (execution_id,))
        conn.execute("DELETE FROM execution_runs WHERE execution_id = %s", (execution_id,))


def test_save_then_load_round_trip_against_real_supabase():
    execution_id = f"juval-integration-test-{uuid.uuid4()}"
    original = _run(execution_id)
    store = SupabaseExecutionRunStore(DB_URL)

    try:
        store.save_execution_run(original)
        loaded = store.load_execution_run(execution_id)

        assert loaded == original
        assert loaded.execution_id == execution_id
        assert loaded.status == ExecutionStatus.SUCCESS
        assert loaded.started_at == original.started_at
        assert loaded.finished_at == original.finished_at
    finally:
        _cleanup(execution_id)

    assert store.load_execution_run(execution_id) is None


def test_records_save_load_and_provenance_round_trip_against_real_supabase():
    execution_id = f"juval-integration-test-{uuid.uuid4()}"
    asin = FieldValue.not_found(source="s", method="m", retrieved_at=datetime(2026, 8, 17, tzinfo=timezone.utc))
    product = Product(identification=Identification(asin=asin, marketplace="US", supplier_sku="row_1"))
    record = SourcingRecord(record_ref="row_1", product=product)
    snapshot = record_to_snapshot(record)
    store = SupabaseExecutionRunStore(DB_URL)

    try:
        store.save_execution_run(_run(execution_id, records_total=1, records_processed=1, records_successful=1), [snapshot])
        loaded_run = store.load_execution_run(execution_id)
        loaded_records = store.load_records(execution_id)

        assert loaded_run is not None
        assert loaded_records == [snapshot]
        assert loaded_records[0]["asin"] == {"value": None, "status": "NOT_FOUND"}
    finally:
        _cleanup(execution_id)

    assert store.load_records(execution_id) == []


def test_list_execution_runs_against_real_supabase():
    execution_id = f"juval-integration-test-{uuid.uuid4()}"
    store = SupabaseExecutionRunStore(DB_URL)

    try:
        store.save_execution_run(_run(execution_id))
        runs = store.list_execution_runs(limit=50)

        assert any(r.execution_id == execution_id for r in runs)
    finally:
        _cleanup(execution_id)
