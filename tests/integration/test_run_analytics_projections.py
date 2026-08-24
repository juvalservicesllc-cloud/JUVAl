"""Internal analytics projections: brand mix, issue types and sourcing spread.

These are aggregated by the persistence layer over canonical snapshot fields --
no fixture data, no ranking model, and no value invented for a record that did
not record one.
"""

from datetime import datetime, timezone

from juval.application.run_analytics import brand_distribution, issue_types, numeric_summary, price_spread
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _run() -> ExecutionRun:
    return ExecutionRun("run-analytics", NOW, NOW, ExecutionStatus.SUCCESS, "in.xlsx", "hash", "0.1", 4, 4, 4, 0, 0)


def _snapshot(ref, *, brand, price, price_status, cog, codes):
    return {
        "record_ref": ref,
        "brand": {"value": brand, "status": "VERIFIED" if brand else "NOT_FOUND"},
        "title": {"value": f"Item {ref}", "status": "VERIFIED"},
        "selling_price": {"value": price, "status": price_status},
        "cog": cog,
        "profit": {"value": None, "status": None},
        "roi": {"value": None, "status": None},
        "margin": {"value": None, "status": None},
        "decision": "BUY",
        "hazmat_status": "ABSENT",
        "bulky_status": "ABSENT",
        "issue_count": len(codes),
        "issues": [f"[WARNING] {code}: message" for code in codes],
        "issue_codes": list(codes),
    }


def _store(tmp_path, snapshots):
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.save_execution_run(_run(), snapshots)
    return store


def test_brand_distribution_keeps_unrecorded_brands_separate(tmp_path):
    store = _store(tmp_path, [
        _snapshot("r1", brand="Acme", price="20", price_status="VERIFIED", cog="10", codes=()),
        _snapshot("r2", brand="Acme", price="20", price_status="VERIFIED", cog="10", codes=()),
        _snapshot("r3", brand="Globex", price="20", price_status="VERIFIED", cog="10", codes=()),
        _snapshot("r4", brand=None, price="20", price_status="VERIFIED", cog="10", codes=()),
    ])
    brands = store.get_run_analytics("run-analytics")["brands"]
    assert brands["items"] == [{"label": "Acme", "count": 2}, {"label": "Globex", "count": 1}]
    assert brands["distinct"] == 2
    assert brands["not_recorded"] == 1


def test_issue_types_group_by_canonical_code(tmp_path):
    store = _store(tmp_path, [
        _snapshot("r1", brand="Acme", price="20", price_status="VERIFIED", cog="10", codes=("MISSING_UNIT", "INVALID_NUMBER")),
        _snapshot("r2", brand="Acme", price="20", price_status="VERIFIED", cog="10", codes=("MISSING_UNIT",)),
    ])
    assert store.get_run_analytics("run-analytics")["issue_types"] == [
        {"code": "MISSING_UNIT", "count": 2},
        {"code": "INVALID_NUMBER", "count": 1},
    ]


def test_legacy_snapshot_without_issue_codes_contributes_nothing(tmp_path):
    """Historical snapshots predate `issue_codes`; they are never back-filled."""
    legacy = _snapshot("r1", brand="Acme", price="20", price_status="VERIFIED", cog="10", codes=("MISSING_UNIT",))
    del legacy["issue_codes"]
    store = _store(tmp_path, [legacy])
    assert store.get_run_analytics("run-analytics")["issue_types"] == []


def test_price_spread_excludes_unverified_prices_and_missing_cog(tmp_path):
    store = _store(tmp_path, [
        _snapshot("r1", brand="Acme", price="20", price_status="VERIFIED", cog="10", codes=()),
        _snapshot("r2", brand="Acme", price="30", price_status="VERIFIED", cog="24", codes=()),
        _snapshot("r3", brand="Acme", price="99", price_status="INFERRED", cog="10", codes=()),
        _snapshot("r4", brand="Acme", price="50", price_status="VERIFIED", cog=None, codes=()),
    ])
    spread = store.get_run_analytics("run-analytics")["price_spread"]
    assert spread["count"] == 2
    assert [entry["record_ref"] for entry in spread["largest"]] == ["r1", "r2"]
    assert spread["largest"][0]["amount"] == "10"
    assert spread["largest"][0]["percent"] == "0.5"
    assert spread["average_amount"] == "8"
    assert spread["at_or_below_cog"] == 0


def test_price_spread_flags_records_priced_at_or_below_cost(tmp_path):
    store = _store(tmp_path, [
        _snapshot("r1", brand="Acme", price="10", price_status="VERIFIED", cog="12", codes=()),
        _snapshot("r2", brand="Acme", price="10", price_status="VERIFIED", cog="10", codes=()),
    ])
    spread = store.get_run_analytics("run-analytics")["price_spread"]
    assert spread["at_or_below_cog"] == 2
    assert spread["largest"][0]["record_ref"] == "r2"


def test_empty_projections_report_none_not_zero(tmp_path):
    store = _store(tmp_path, [_snapshot("r1", brand=None, price=None, price_status=None, cog=None, codes=())])
    analytics = store.get_run_analytics("run-analytics")
    assert analytics["price_spread"] == {"count": 0, "average_amount": None, "at_or_below_cog": 0, "largest": []}
    assert analytics["issue_types"] == []
    assert analytics["brands"]["not_recorded"] == 1


def test_pure_helpers_skip_unusable_values_instead_of_zeroing_them():
    assert numeric_summary(["1", None, "not-a-number", "3"]) == {
        "count": 2, "sum": "4", "average": "2", "minimum": "1", "maximum": "3",
    }
    assert numeric_summary([])["average"] is None
    assert price_spread([("r1", "T", None, "5")])["count"] == 0
    assert price_spread([("r1", "T", "0", "0")])["largest"][0]["percent"] is None
    assert brand_distribution([])["items"] == []
    assert issue_types([(None, 3)]) == []


def test_batch_file_count_columns_are_added_to_a_preexisting_database(tmp_path):
    """A database created before the per-file counts existed must gain them.

    `CREATE TABLE IF NOT EXISTS` does nothing for an existing table, so without
    an explicit column migration the next batch INSERT fails.
    """
    import sqlite3

    from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus

    db = tmp_path / "legacy.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE batches (batch_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE batch_files (batch_id TEXT NOT NULL, ordinal INTEGER NOT NULL, filename TEXT NOT NULL,"
            " content_type TEXT, size_bytes INTEGER NOT NULL, status TEXT NOT NULL, execution_id TEXT,"
            " warnings TEXT NOT NULL, errors TEXT NOT NULL, PRIMARY KEY (batch_id, ordinal))"
        )

    store = SqliteExecutionRunStore(db)
    store.save_execution_run(_run(), [])
    store.save_batch(Batch(
        batch_id="batch-legacy", created_at=NOW, status=BatchStatus.SUCCESS,
        files=(BatchFile(0, "a.xlsx", None, 10, BatchFileStatus.SUCCESS, "run-analytics", records_total=5, records_processed=5),),
    ))

    loaded = store.load_batch("batch-legacy")
    assert loaded.files[0].records_total == 5
    assert store.load_batch_for_run("run-analytics").batch_id == "batch-legacy"
