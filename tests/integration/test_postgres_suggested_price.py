"""Supplier suggested price (ADR-053) through the PostgreSQL store, on a disposable cluster.

The run-audit migrations already store the snapshot as JSONB, so no migration is
added: this proves the document round-trips there exactly as through SQLite,
including a historical snapshot without the key. Never a runtime DSN.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("psycopg")

from juval.application.record_snapshot import record_to_snapshot  # noqa: E402
from juval.application.suggested_price_evidence import suggested_price_state  # noqa: E402
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore  # noqa: E402
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore  # noqa: E402

from .test_postgres_financial_persistence import cluster, prior_dsn  # noqa: E402,F401 (fixtures)
from .test_record_snapshot_pagination import run, snapshot  # noqa: E402
from .test_supplier_suggested_price import BASE, PRICE, records, write_csv  # noqa: E402

pytestmark = pytest.mark.skipif(not os.environ.get("JUVAL_POSTGRES_BIN"),
                                reason="JUVAL_POSTGRES_BIN not set -- no disposable PostgreSQL cluster")


def test_the_document_round_trips_through_postgres_exactly_as_through_sqlite(tmp_path, prior_dsn):
    rows = [{**BASE, **PRICE, "supplier_suggested_price": "1234567890.123456789012345678"},
            {**BASE, "asin": "B000000002", "supplier_suggested_price": " $5 ", "supplier_suggested_price_currency": "usd"},
            {**BASE, "asin": "B000000003", "supplier_suggested_price": "", "supplier_suggested_price_currency": "EUR"}]
    snapshots = [record_to_snapshot(r) for r in records(write_csv(tmp_path, rows))]
    postgres, sqlite = SupabaseExecutionRunStore(prior_dsn), SqliteExecutionRunStore(tmp_path / "runs.db")
    for store in (postgres, sqlite):
        store.save_execution_run(run(), snapshots)
    for original in snapshots:
        stored = postgres.load_record("run-page", original["record_ref"])
        assert stored["supplier_suggested_price"] == original["supplier_suggested_price"]
        assert stored["supplier_suggested_price"] == sqlite.load_record("run-page", original["record_ref"])["supplier_suggested_price"]
    assert postgres.load_record("run-page", snapshots[0]["record_ref"])["supplier_suggested_price"]["amount"]["value"] \
        == "1234567890.123456789012345678"


def test_a_historical_snapshot_stays_not_captured_in_postgres(prior_dsn):
    store = SupabaseExecutionRunStore(prior_dsn)
    store.save_execution_run(run(), [snapshot(0)])
    stored = store.load_record("run-page", "row_00")
    assert "supplier_suggested_price" not in stored and suggested_price_state(stored) == "NOT_CAPTURED"
