"""Capture diagnostics persisted per (execution_id, record_ref), independent of financial documents.
Synthetic data, temporary SQLite only."""
import ast
import json
import pathlib
import sqlite3

import openpyxl
import pytest

from juval.application import capture_diagnostics as module
from juval.application import native_financial_documents as documents_module
from juval.application.capture_diagnostics import (
    RecordCaptureDiagnostics, deserialize_capture_diagnostics, serialize_capture_diagnostics,
)
from juval.application.financial_persistence import (
    FinancialRecordIntegrityError, load_capture_diagnostics, load_financial_record,
)
from juval.application.financial_serialization import FinancialSerializationError
from juval.application.financial_serialization_v2 import FinancialRecordDocumentV2
from juval.domain.financial_evidence import FinancialTerm as T
from juval.infrastructure.excel.financial_capture import CaptureCode, CaptureDiagnostic
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.cli import main as cli

from .test_cli_native_financial import ARGS, FINANCIAL, cli_run, count, fixed_now, refs, row  # noqa: F401 (fixture)
from .test_native_financial_capture import BASE, declared, xlsx

TABLE = "execution_run_capture_diagnostics"
FULL_DIAG = CaptureDiagnostic("COG", CaptureCode.EFFECTIVE_AT_INVALID, "effective_at 'x' is not an ISO 8601 instant",
                              2, "fin_cog_effective_at", "x")
BARE_DIAG = CaptureDiagnostic("scenario", CaptureCode.SCENARIO_UNDECLARED, "not declared: fin_currency", 2)


def round_trip(item):
    text = json.dumps(serialize_capture_diagnostics(item), sort_keys=True)
    back = deserialize_capture_diagnostics(json.loads(text))
    assert back == item and json.dumps(serialize_capture_diagnostics(back), sort_keys=True) == text
    return back


def load(store, index=0, execution_id="run-A"):
    return load_capture_diagnostics(store, execution_id, refs(store, execution_id)[index])


# -- Contract ---------------------------------------------------------------------

def test_full_and_bare_diagnostics_round_trip_in_order_with_their_codes():
    back = round_trip(RecordCaptureDiagnostics("run-A", "row_2:A", (FULL_DIAG, BARE_DIAG)))
    assert back.diagnostics == (FULL_DIAG, BARE_DIAG)                     # order kept
    assert back.diagnostics[0].code is CaptureCode.EFFECTIVE_AT_INVALID
    assert (back.diagnostics[1].column, back.diagnostics[1].raw_value) == (None, None)
    assert round_trip(RecordCaptureDiagnostics("run-A", "row_2:A", ())).diagnostics == ()


def good_payload():
    return json.loads(json.dumps(serialize_capture_diagnostics(RecordCaptureDiagnostics("run-A", "row_2:A", (FULL_DIAG,)))))


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(version=2), lambda p: p.update(format="juval.adr047.financial-record"),
    lambda p: p.update(version="1"), lambda p: p.pop("record_ref"), lambda p: p.update(extra=1),
    lambda p: p["diagnostics"][0].update(code="SOMETHING_ELSE"),
    lambda p: p["diagnostics"][0].update(row=0), lambda p: p["diagnostics"][0].update(row="2"),
    lambda p: p["diagnostics"][0].update(message=""), lambda p: p["diagnostics"][0].update(column=3),
    lambda p: p["diagnostics"][0].pop("raw_value"), lambda p: p.update(diagnostics={}),
])
def test_corrupt_or_unknown_payloads_are_rejected(mutate):
    payload = good_payload()
    mutate(payload)
    with pytest.raises(FinancialSerializationError):
        deserialize_capture_diagnostics(payload)


# -- Through the CLI ----------------------------------------------------------------

def test_every_captured_record_gets_its_own_diagnostics_set(tmp_path):
    rows = [row("FULL"),                                                        # complete, no diagnostics
            row("PARTIAL", **declared(T.COG, "4.50", source_basis="carton")),  # scenario + diagnostic
            {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")},  # no scenario at all
            row("DROPPED", marketplace="")]                                   # importer drops it
    code, _, store = cli_run(tmp_path, rows, *FINANCIAL)
    assert code == 0
    stored = refs(store)
    assert [ref.split(":")[1] for ref in stored] == ["FULL", "PARTIAL", "NO_SCENARIO"]
    full, partial, no_scenario = (load_capture_diagnostics(store, "run-A", ref) for ref in stored)
    assert full.diagnostics == ()
    [diag] = partial.diagnostics
    assert (diag.code, diag.row, diag.column, diag.raw_value) == (
        CaptureCode.SOURCE_BASIS_INVALID, 3, "fin_cog_source_basis", "carton")
    [diag] = no_scenario.diagnostics
    assert (diag.subject, diag.code, diag.row, diag.column) == ("scenario", CaptureCode.SCENARIO_UNDECLARED, 4, None)
    # No financial document, and no fabricated scenario, for the record without one.
    assert load_financial_record(store, "run-A", stored[2]) is None
    assert type(load_financial_record(store, "run-A", stored[1])) is FinancialRecordDocumentV2
    assert count(tmp_path / "runs.db", TABLE) == 3                           # nothing for the dropped row


def test_v2_documents_and_the_diagnostics_store_agree(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A", **declared(T.PREP, "0.40", currency=""))], *FINANCIAL)
    [stored] = load(store).diagnostics
    [problem] = load_financial_record(store, "run-A", refs(store)[0]).capture_problems
    assert (problem.text, problem.subject, problem.row, problem.column, problem.raw_value) == (
        stored.text, stored.subject, stored.row, stored.column, stored.raw_value)
    assert stored.code is CaptureCode.CURRENCY_UNDECLARED                        # the code v2 cannot hold


def test_duplicate_asins_and_runs_stay_isolated(tmp_path):
    cli_run(tmp_path, [row("A", **declared(T.COG, "1", source_basis="x")),
                       row("B", **declared(T.COG, "1", source_basis="y"))], *FINANCIAL)
    cli_run(tmp_path, [row("A", **declared(T.COG, "1", source_basis="z"))], *FINANCIAL, execution_id="run-B")
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    assert [load(store, i).diagnostics[0].raw_value for i in (0, 1)] == ["x", "y"]
    assert load(store, 0, "run-B").diagnostics[0].raw_value == "z"
    assert load_capture_diagnostics(store, "run-C", refs(store)[0]) is None


def test_legacy_cli_stores_no_diagnostics(tmp_path):
    code, _, store = cli_run(tmp_path, [row("A", fin_currency="")])
    assert code == 0 and count(tmp_path / "runs.db", TABLE) == 0
    assert load_capture_diagnostics(store, "run-A", "row_2:A") is None


# -- Integrity and atomicity -------------------------------------------------------------

def tamper(tmp_path, sql, *params):
    with sqlite3.connect(tmp_path / "runs.db") as conn:
        conn.execute(sql, params)


def test_stored_corruption_version_and_identity_are_errors_not_absence(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A"), row("B")], *FINANCIAL)
    first, second = refs(store)
    text = store.load_capture_diagnostics("run-A", first)[2]
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = 'not json' WHERE record_ref = ?", first)
    with pytest.raises(FinancialSerializationError):
        load_capture_diagnostics(store, "run-A", first)
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ? WHERE record_ref = ?", text.replace('"version": 1', '"version": 9'), first)
    with pytest.raises(FinancialSerializationError, match="version 9"):
        load_capture_diagnostics(store, "run-A", first)
    other = store.load_capture_diagnostics("run-A", second)[2]
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ? WHERE record_ref = ?", other, first)
    with pytest.raises(FinancialRecordIntegrityError, match="stored under"):
        load_capture_diagnostics(store, "run-A", first)
    tamper(tmp_path, f"UPDATE {TABLE} SET payload = ?, format_version = 2 WHERE record_ref = ?", text, first)
    with pytest.raises(FinancialRecordIntegrityError):
        load_capture_diagnostics(store, "run-A", first)


@pytest.mark.parametrize("tamper_kind", ["other_run", "unknown_record", "duplicate"])
def test_invalid_diagnostics_sets_write_nothing(tmp_path, monkeypatch, tamper_kind, capsys):
    real = documents_module.RecordCaptureDiagnostics

    def build(execution_id, record_ref, diagnostics):
        if tamper_kind == "other_run":
            return real("run-OTHER", record_ref, diagnostics)
        if tamper_kind == "unknown_record":
            return real(execution_id, "row_99:GHOST", diagnostics)
        return real(execution_id, "row_2:A", diagnostics)                # both records claim row_2:A

    monkeypatch.setattr(documents_module, "RecordCaptureDiagnostics", build)
    code, _, store = cli_run(tmp_path, [row("A"), row("B")], *FINANCIAL)
    assert code == 3 and "nothing was persisted" in capsys.readouterr().err
    assert store.load_execution_run("run-A") is None and store.load_records("run-A") == []
    assert count(tmp_path / "runs.db") == 0 and count(tmp_path / "runs.db", TABLE) == 0


@pytest.mark.parametrize("failure", ["foreign_key", "primary_key", "other_run"])
def test_store_rolls_back_run_snapshots_documents_and_diagnostics_together(tmp_path, failure):
    _, _, source = cli_run(tmp_path, [row("A"), row("B")], *FINANCIAL, db="source.db")
    snapshots = source.load_records("run-A")
    run = source.load_execution_run("run-A")
    documents = [json.loads(source.load_financial_record("run-A", s["record_ref"])[2]) for s in snapshots]
    diagnostics = [json.loads(source.load_capture_diagnostics("run-A", s["record_ref"])[2]) for s in snapshots]
    if failure == "foreign_key":
        diagnostics.append({**diagnostics[0], "record_ref": "row_99:GHOST"})
    elif failure == "primary_key":
        diagnostics.append(diagnostics[0])
    else:
        diagnostics[1] = {**diagnostics[1], "execution_id": "run-Z"}
    target = SqliteExecutionRunStore(tmp_path / "target.db")
    with pytest.raises((sqlite3.IntegrityError, ValueError)):
        target.save_execution_run(run, snapshots, financial_records=documents, capture_diagnostics=diagnostics)
    assert target.load_execution_run("run-A") is None and target.load_records("run-A") == []
    assert count(tmp_path / "target.db", "execution_run_financial_records") == 0
    assert count(tmp_path / "target.db", TABLE) == 0


def test_diagnostics_table_is_added_to_a_pre_existing_database(tmp_path):
    db = tmp_path / "old.db"
    SqliteExecutionRunStore(db)
    with sqlite3.connect(db) as conn:
        conn.execute(f"DROP TABLE {TABLE}")                                    # a database from before 4N
    reopened = SqliteExecutionRunStore(db)
    assert reopened.load_capture_diagnostics("run-A", "row_2:A") is None


# -- Commercial parity and scope ------------------------------------------------------------

def sheet(path):
    return list(openpyxl.load_workbook(path).active.iter_rows(values_only=True))


def test_persisting_diagnostics_changes_no_commercial_result(tmp_path):
    rows = [row("A", **declared(T.COG, "4.50", source_basis="carton")), row("B", hazmat="yes", fin_currency="")]
    native = xlsx(tmp_path, *rows, name="native/in.xlsx")
    plain = xlsx(tmp_path, *[{k: v for k, v in r.items() if not k.startswith("fin_")} for r in rows],
                 name="legacy/in.xlsx")
    assert cli.main([str(plain), str(tmp_path / "legacy.xlsx"), *ARGS, "--execution-id", "run-A"]) == 0
    assert cli.main([str(native), str(tmp_path / "native.xlsx"), *ARGS, "--execution-id", "run-A",
                     "--persist-db", str(tmp_path / "n.db"), *FINANCIAL]) == 0
    assert sheet(tmp_path / "legacy.xlsx") == sheet(tmp_path / "native.xlsx")
    for snapshot in SqliteExecutionRunStore(tmp_path / "n.db").load_records("run-A"):
        assert "diagnostic" not in json.dumps(snapshot).lower()


def test_module_is_pure_with_no_network_supabase_or_api():
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "dataclasses", "typing", "juval.application.financial_serialization",
                       "juval.infrastructure.excel.financial_capture"}
