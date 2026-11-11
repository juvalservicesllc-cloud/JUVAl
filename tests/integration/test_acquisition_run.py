"""ADR-058 end to end on SQLite: pipeline + synthetic connector + atomic persistence.

Synthetic fixtures and transport doubles only (tests/unit/acquisition_synthetic.py).
"""

from __future__ import annotations

import json
import socket
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

import juval
from juval.application import acquisition_run as acquisition_run_module
from juval.application.acquisition_documents import ACQUIRED_EVIDENCE_KEY, AcquisitionIntegrityError
from juval.application.acquisition_run import ConnectorResultError, run_and_persist_with_acquisition
from juval.application.batch_persistence import BatchChild, save_batch_with_runs
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.application.tenancy import OutOfScopeError, Ownership, TenantScope
from juval.domain.acquisition import FailureCategory, NotConsultedReason, ValueCounts
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.execution_run import ExecutionStatus
from juval.domain.risk import Severity
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

from tests.unit.acquisition_synthetic import (
    SOURCE,
    ScriptedTransport,
    connector,
    found,
    no_match,
    ok,
    status,
)

NOW = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"
THRESHOLDS = Thresholds(target_profit=Decimal("5"), target_roi=Decimal("0.3"),
                        minimum_estimated_monthly_sales=0, maximum_risk_severity=Severity.LOW)
FEES = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))
ORG = "aaaaaaaa-0000-4000-8000-00000000000a"
OTHER_ORG = "bbbbbbbb-0000-4000-8000-00000000000b"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def store(tmp_path):
    return SqliteExecutionRunStore(tmp_path / "runs.sqlite")


def eligible_asins() -> list[str]:
    _, records = run_pipeline(FIXTURE, THRESHOLDS, fees=FEES, application_version="t", execution_id="probe", now=NOW)
    asins = [r.product.identification.asin.value for r in records
             if r.product.identification.asin is not None and r.product.identification.asin.is_usable]
    assert asins, "the synthetic fixture must have at least one usable ASIN"
    return asins


def run_with(store, *connectors, execution_id="acq-1", path=FIXTURE, owner=None):
    return run_and_persist_with_acquisition(
        path, THRESHOLDS, connectors=connectors, store=store, fees=FEES,
        application_version=juval.__version__, execution_id=execution_id, now=NOW, owner=owner)


def decisions(records):
    return [(r.record_ref, r.decision.decision if r.decision else None,
             tuple(x.code for x in r.decision.reasons) if r.decision else ()) for r in records]


def raw_columns(store_path: Path, execution_id: str):
    with sqlite3.connect(store_path) as conn:
        return conn.execute("SELECT acquisition_configuration, acquisition_execution FROM execution_runs "
                            "WHERE execution_id = ?", (execution_id,)).fetchone()


# --- happy path ---------------------------------------------------------------------


def test_acquired_run_is_persisted_atomically_and_derived_from_provenance(store, tmp_path):
    asins = eligible_asins()
    transport = ScriptedTransport(ok(*[found(a, weight_lb=2) for a in asins[:-1]], no_match(asins[-1])))
    result = run_with(store, connector(transport))

    loaded = store.load_acquisition("acq-1")
    assert loaded == result.acquisition
    entry = loaded.execution.sources[0]
    assert entry.source_id == SOURCE.source_id and entry.not_consulted_reason is None
    assert entry.items.requested == len(asins) and entry.requests_sent == 1 and entry.retries == 0
    assert entry.items.with_evidence == len(asins) - 1 and entry.items.no_evidence == 1
    assert entry.values == ValueCounts(used=2 * (len(asins) - 1), not_found=1, invalid=0)
    assert loaded.configuration.captured_at == NOW
    assert loaded.configuration.sources == (SOURCE,)

    snapshots = store.load_records("acq-1")
    with_evidence = [s for s in snapshots if ACQUIRED_EVIDENCE_KEY in s]
    assert len(with_evidence) == len(asins)
    value = with_evidence[0][ACQUIRED_EVIDENCE_KEY]["values"][0]["value"]
    assert value["provenance"]["source"] == SOURCE.source_id
    assert value["provenance"]["source_type"] == "AUTHORIZED_EXTERNAL_SOURCE"
    assert value["status"] in ("INFERRED", "NOT_FOUND")       # synthetic data is never VERIFIED
    assert all(s.get("decision") for s in snapshots)


def test_decisions_and_existing_snapshot_fields_are_identical_with_or_without_connectors(store):
    asins = eligible_asins()
    _, plain = run_pipeline(FIXTURE, THRESHOLDS, fees=FEES, application_version=juval.__version__,
                            execution_id="acq-1", now=NOW)
    acquired = run_with(store, connector(ScriptedTransport(ok(*[found(a) for a in asins]))))
    assert decisions(acquired.records) == decisions(plain)          # BUY/REVIEW/PASS untouched
    assert acquired.records == plain                                 # no domain field changed
    for snapshot, record in zip(acquired.snapshots, plain):
        without = {k: v for k, v in snapshot.items() if k != ACQUIRED_EVIDENCE_KEY}
        assert without == record_to_snapshot(record)


def test_operational_failures_are_counted_and_never_become_not_found(store):
    asins = eligible_asins()
    transport = ScriptedTransport(status(503), status(503), status(503))
    result = run_with(store, connector(transport))
    entry = result.acquisition.execution.sources[0]
    assert entry.items.failed[FailureCategory.SOURCE_FAILURE] == len(asins)
    assert entry.retries == 2 and entry.values == ValueCounts(0, 0, 0)
    assert all(ACQUIRED_EVIDENCE_KEY not in s for s in store.load_records("acq-1"))
    plain_status = run_pipeline(FIXTURE, THRESHOLDS, fees=FEES, application_version=juval.__version__,
                                execution_id="x", now=NOW)[0].status
    assert store.load_execution_run("acq-1").status is plain_status   # PD-8 pending: status keeps its meaning


def test_429_then_success_records_the_retry(store):
    asins = eligible_asins()
    sleeps: list = []
    transport = ScriptedTransport(status(429, {"Retry-After": "2"}), ok(*[found(a) for a in asins]))
    entry = run_with(store, connector(transport, sleeps=sleeps)).acquisition.execution.sources[0]
    assert entry.retries == 1 and entry.requests_sent == 1 and sleeps == [2.0]
    assert entry.items.with_evidence == len(asins)


@pytest.mark.parametrize("answer, category", [
    (status(401), FailureCategory.AUTH_OR_CONFIGURATION),
    (status(403), FailureCategory.AUTH_OR_CONFIGURATION),
    (ok({"id": "nope", "status": "FOUND", "title": "x"}), FailureCategory.SCHEMA_FAILURE),
])
def test_auth_and_schema_failures_end_to_end(store, answer, category):
    entry = run_with(store, connector(ScriptedTransport(answer))).acquisition.execution.sources[0]
    assert entry.items.failed[category] == entry.items.requested > 0
    assert store.load_acquisition("acq-1") is not None


# --- not consulted --------------------------------------------------------------------


def test_failed_run_consults_nothing(store, tmp_path):
    bad = tmp_path / "empty.csv"
    bad.write_text("", encoding="utf-8")
    transport = ScriptedTransport()
    result = run_with(store, connector(transport), path=bad)
    assert result.run.status is ExecutionStatus.FAILED and transport.sent == []
    entry = store.load_acquisition("acq-1").execution.sources[0]
    assert entry.not_consulted_reason is NotConsultedReason.RUN_FAILED_BEFORE_ACQUISITION


def test_no_eligible_records(store, tmp_path, monkeypatch):
    transport = ScriptedTransport()
    probe = connector(transport)
    monkeypatch.setattr(probe, "identifier_for", lambda record: None)
    entry = run_with(store, probe).acquisition.execution.sources[0]
    assert entry.not_consulted_reason is NotConsultedReason.NO_ELIGIBLE_RECORDS and transport.sent == []


def test_run_without_connectors_is_recorded_with_no_sources(store):
    result = run_with(store)
    assert result.acquisition.configuration.sources == ()
    assert store.load_acquisition("acq-1") == result.acquisition


# --- NOT_RECORDED, history and compatibility -----------------------------------------------


def test_runs_saved_without_acquisition_are_not_recorded(store):
    run, records = run_pipeline(FIXTURE, THRESHOLDS, fees=FEES, application_version="t", execution_id="legacy", now=NOW)
    store.save_execution_run(run, [record_to_snapshot(r) for r in records])
    assert store.load_acquisition("legacy") is None
    assert store.load_execution_run("legacy") == run
    with pytest.raises(LookupError):
        store.load_acquisition("does-not-exist")


def test_a_database_created_before_adr058_is_migrated_in_place(tmp_path):
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as conn:  # pre-ADR-058 shape with one historical run
        conn.execute("CREATE TABLE execution_runs (execution_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, "
                     "finished_at TEXT, status TEXT NOT NULL, input_filename TEXT NOT NULL, input_hash TEXT NOT NULL, "
                     "application_version TEXT NOT NULL, records_total INTEGER NOT NULL, records_processed INTEGER "
                     "NOT NULL, records_successful INTEGER NOT NULL, records_with_errors INTEGER NOT NULL, "
                     "warnings INTEGER NOT NULL)")
        conn.execute("INSERT INTO execution_runs VALUES ('old', ?, ?, 'SUCCESS', 'f.xlsx', ?, '0', 0, 0, 0, 0, 0)",
                     (NOW.isoformat(), NOW.isoformat(), "0" * 64))
    store = SqliteExecutionRunStore(path)
    assert store.load_acquisition("old") is None                   # history stays NOT_RECORDED
    assert store.load_execution_run("old").execution_id == "old"
    run_with(store, execution_id="new")
    assert store.load_acquisition("new") is not None


def test_check_constraint_refuses_one_null_column(store, tmp_path):  # P3 in the database
    run_with(store)
    with sqlite3.connect(tmp_path / "runs.sqlite") as conn:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute("INSERT INTO execution_runs (execution_id, started_at, status, input_filename, input_hash, "
                         "application_version, records_total, records_processed, records_successful, "
                         "records_with_errors, warnings, acquisition_configuration) "
                         "VALUES ('x', ?, 'SUCCESS', 'f', 'h', 'v', 0, 0, 0, 0, 0, '{}')", (NOW.isoformat(),))


def test_listing_does_not_read_the_documents(store):
    run_with(store)
    assert [r.execution_id for r in store.list_execution_runs()] == ["acq-1"]  # P5: unchanged shape


# --- atomicity and rollback (P1, P8) -------------------------------------------------------


def test_a_failing_store_write_persists_nothing(store, tmp_path, monkeypatch):
    asins = eligible_asins()
    original = store.save_execution_run

    def broken(run, records=(), **kwargs):
        records = list(records)
        records.append({"record_ref": records[0]["record_ref"]})  # duplicate key -> IntegrityError mid-transaction
        return original(run, records, **kwargs)

    monkeypatch.setattr(store, "save_execution_run", broken)
    with pytest.raises(sqlite3.IntegrityError):
        run_with(store, connector(ScriptedTransport(ok(*[found(a) for a in asins]))))
    assert store.load_execution_run("acq-1") is None
    assert raw_columns(tmp_path / "runs.sqlite", "acq-1") is None


def test_an_inconsistent_record_is_refused_before_writing(store, tmp_path):
    result = run_with(store)
    rogue = dict(result.snapshots[0])
    rogue[ACQUIRED_EVIDENCE_KEY] = {"values": [{"value": {"value": "x", "status": "INFERRED", "provenance": {
        "source": "synthetic-test/rogue", "source_type": "OFFICIAL_API", "verification_status": "INFERRED"}}}]}
    run2 = result.run.__class__(**{**result.run.__dict__, "execution_id": "acq-2"})
    with pytest.raises(AcquisitionIntegrityError, match="unconfigured"):   # P6
        store.save_execution_run(run2, [rogue, *result.snapshots[1:]], acquisition=result.acquisition)
    assert store.load_execution_run("acq-2") is None


def test_an_exception_during_acquisition_persists_nothing(store, monkeypatch):
    probe = connector(ScriptedTransport())
    monkeypatch.setattr(probe, "acquire", lambda items: (_ for _ in ()).throw(RuntimeError("process killed")))
    with pytest.raises(RuntimeError):
        run_with(store, probe)
    assert store.load_execution_run("acq-1") is None   # aborted before the INSERT: no registry (P8)


def test_a_connector_answering_for_other_records_is_refused(store, monkeypatch):
    probe = connector(ScriptedTransport())
    real = probe.acquire
    monkeypatch.setattr(probe, "acquire", lambda items: real(items[:0]))
    with pytest.raises(ConnectorResultError):
        run_with(store, probe)
    assert store.load_execution_run("acq-1") is None


# --- PD-7: no connector without persistence -----------------------------------------------


def test_run_pipeline_has_no_connector_path():
    """run_pipeline (used by persist=false) cannot take or reach a connector."""
    import inspect
    import juval.application.run_pipeline as rp
    assert "connectors" not in inspect.signature(rp.run_pipeline).parameters
    assert "acquisition" not in Path(rp.__file__).read_text(encoding="utf-8")
    assert acquisition_run_module.run_pipeline is rp.run_pipeline   # the acquisition path reuses it unchanged


def test_the_api_process_endpoint_has_no_connector_path():
    """persist=false (and today persist=true too) never reaches a connector."""
    main = Path(juval.__file__).parent / "interfaces" / "api" / "main.py"
    text = main.read_text(encoding="utf-8")
    assert "run_and_persist_with_acquisition" not in text and "acquisition_port" not in text


# --- organization isolation and batches ------------------------------------------------------


def test_documents_follow_the_run_owner_scope(store):
    owner = Ownership(ORG, "https://idp.synthetic.example", "user-a")
    scoped = store.scoped(TenantScope(ORG))
    run_with(scoped, owner=owner)
    assert scoped.load_acquisition("acq-1") is not None
    with pytest.raises(OutOfScopeError):
        store.scoped(TenantScope(OTHER_ORG)).load_acquisition("acq-1")


def test_batch_children_carry_their_documents_in_the_single_transaction(store, tmp_path):
    first = run_with(SqliteExecutionRunStore(tmp_path / "scratch.sqlite"), execution_id="child-1")
    second = run_with(SqliteExecutionRunStore(tmp_path / "scratch.sqlite"), execution_id="child-2")
    batch = Batch(batch_id="b-1", created_at=NOW, status=BatchStatus.SUCCESS, files=(
        BatchFile(0, "a.xlsx", None, 1, BatchFileStatus.SUCCESS, "child-1"),
        BatchFile(1, "b.xlsx", None, 1, BatchFileStatus.SUCCESS, "child-2")))
    save_batch_with_runs(store, batch, [BatchChild(first.run, first.snapshots, acquisition=first.acquisition),
                                        BatchChild(second.run, second.snapshots)])
    assert store.load_acquisition("child-1") == first.acquisition
    assert store.load_acquisition("child-2") is None


def test_stored_documents_are_canonical_text(store, tmp_path):
    run_with(store)
    config_text, execution_text = raw_columns(tmp_path / "runs.sqlite", "acq-1")
    assert config_text == json.dumps(json.loads(config_text), sort_keys=True, separators=(",", ":"))
    assert json.loads(execution_text)["format"] == "juval.adr058.acquisition-execution"
