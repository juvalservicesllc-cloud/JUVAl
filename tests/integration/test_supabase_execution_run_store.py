"""Real integration test for SupabaseExecutionRunStore (ADR-017) — runs
only when JUVAL_SUPABASE_DB_URL points at a live Postgres/Supabase
instance. Connects for real (psycopg), no mocks/SQLite/fakes. The test
row is deleted via a DELETE scoped to its own execution_id in a
finally block -- SupabaseExecutionRunStore intentionally exposes no
delete method (schema changes are migrations-only, ADR-017), so
cleanup of a row this same test created is the one place a direct,
narrowly-scoped SQL statement is justified.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

psycopg = pytest.importorskip("psycopg")

from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

DB_URL = os.environ.get("JUVAL_SUPABASE_DB_URL")

pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="JUVAL_SUPABASE_DB_URL not set -- no live Supabase project to test against",
)


def test_save_then_load_round_trip_against_real_supabase():
    execution_id = f"juval-integration-test-{uuid.uuid4()}"
    original = ExecutionRun(
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
        with psycopg.connect(DB_URL) as conn:
            conn.execute(
                "DELETE FROM execution_runs WHERE execution_id = %s",
                (execution_id,),
            )

    assert store.load_execution_run(execution_id) is None
