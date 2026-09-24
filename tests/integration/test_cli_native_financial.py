"""CLI opt-in native financial flow (ADR-047) against temporary SQLite. Synthetic files only."""
import ast
import pathlib
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest

from juval.application import native_financial_documents as documents_module
from juval.application.financial_calculation import CalculationBlocker as CB
from juval.application.financial_persistence import load_financial_record as load_any
from juval.application.financial_serialization import FinancialRecordDocument
from juval.application.financial_serialization_v2 import FinancialRecordDocumentV2
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.financial_dependencies import FinancialResult as R, ResolutionBlocker
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.provenance import SourceType, VerificationStatus
from juval.domain.risk import Severity
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.cli import main as cli

from .test_native_financial_calculation import AMOUNTS, every_term_declared
from .test_native_financial_capture import BASE, declared, xlsx

NOW = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
ARGS = ["--target-profit", "5", "--target-roi", "0.3", "--max-risk-severity", "LOW",
        "--referral-fee", "3", "--referral-fee-rate", "0.15", "--fulfillment-fee", "2"]
FINANCIAL = ["--native-financial-evidence", "--financial-target-profit", "3",
             "--financial-target-profit-currency", "USD", "--financial-target-roi", "0.30"]
TABLE = "execution_run_financial_records"


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(cli, "datetime", _FixedDatetime)


def row(sku, **overrides):
    data = {**every_term_declared(**AMOUNTS), "supplier_sku": sku}
    data.update(overrides)
    return data


def cli_run(tmp_path, rows, *extra, db="runs.db", execution_id="run-A", name="in.xlsx"):
    path = xlsx(tmp_path, *rows, name=f"{execution_id}/{name}")
    code = cli.main([str(path), str(tmp_path / f"{execution_id}-out.xlsx"), *ARGS, "--execution-id", execution_id,
                     "--persist-db", str(tmp_path / db), *extra])
    return code, path, SqliteExecutionRunStore(tmp_path / db)


def load_financial_record(store, execution_id, record_ref):
    """The CLI writes v2: return its financial core, or None when there is no document."""
    document = load_any(store, execution_id, record_ref)
    if document is None:
        return None
    assert type(document) is FinancialRecordDocumentV2
    return document.document


def count(db, table=TABLE):
    with sqlite3.connect(db) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def refs(store, execution_id="run-A"):
    return [snapshot["record_ref"] for snapshot in store.load_records(execution_id)]


# -- Activation ------------------------------------------------------------------

def test_legacy_cli_is_the_default_and_persists_no_financial_documents(tmp_path):
    code, _, store = cli_run(tmp_path, [row("A")])
    assert code == 0
    assert store.load_execution_run("run-A") is not None
    assert store.load_records("run-A") == []                   # legacy CLI persists the run only
    assert count(tmp_path / "runs.db") == 0


@pytest.mark.parametrize("argv", [
    ["--native-financial-evidence"],                                          # no --persist-db
    ["--financial-target-roi", "0.3"],                                        # target without opt-in
    ["--native-financial-evidence", "--persist-db", "x.db", "--financial-target-profit", "3"],  # no currency
])
def test_flag_combinations_are_validated(tmp_path, argv):
    path = xlsx(tmp_path, row("A"))
    with pytest.raises(SystemExit) as exit_info:
        cli.main([str(path), str(tmp_path / "out.xlsx"), *ARGS, *argv])
    assert exit_info.value.code == 2


# -- Native flow -------------------------------------------------------------------

def test_native_flow_persists_run_snapshots_and_documents_together(tmp_path, capsys):
    code, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    assert code == 0
    [ref] = refs(store)
    document = load_financial_record(store, "run-A", ref)
    assert document.evidence.execution_id == "run-A" and document.evidence.record_reference == ref
    calcs = document.calculations
    assert calcs.for_result(R.PROFIT).value.value == Decimal("9.30")
    assert calcs.for_result(R.MAX_COG_TARGET_PROFIT).value.value == Decimal("10.80")  # 20.00 - 6.20 - 0 - 3
    target = next(d for d in document.resolution.for_result(R.MAX_COG_TARGET_PROFIT).dependencies
                  if d.dependency == "TARGET_PROFIT")
    assert target.operand.provenance.source_type is SourceType.USER_INPUT and target.operand.unit == "USD"
    assert calcs.decimal_precision == 28
    out = capsys.readouterr().out
    assert "financial: captures=1 documents=1 without_scenario=0 capture_problems=0" in out


def test_without_financial_targets_max_cog_stays_blocked(tmp_path):
    code, _, store = cli_run(tmp_path, [row("A")], "--native-financial-evidence")
    assert code == 0
    document = load_financial_record(store, "run-A", refs(store)[0])
    for result in (R.MAX_COG_TARGET_PROFIT, R.MAX_COG_TARGET_ROI):
        item = document.calculations.for_result(result)
        assert item.blocker is CB.DEPENDENCIES_UNRESOLVED and item.value.status is VerificationStatus.NOT_FOUND
    assert document.calculations.for_result(R.PROFIT).value.value == Decimal("9.30")


def test_target_currency_is_never_adapted(tmp_path):
    code, _, store = cli_run(tmp_path, [row("A")], "--native-financial-evidence", "--financial-target-profit", "3",
                             "--financial-target-profit-currency", "EUR")
    document = load_financial_record(store, "run-A", refs(store)[0])
    [blocked] = document.resolution.for_result(R.MAX_COG_TARGET_PROFIT).blockers
    assert blocked.blocker is ResolutionBlocker.CURRENCY_INCOMPATIBLE


def test_partial_and_blocked_evidence_is_kept_per_record(tmp_path, capsys):
    rows = [
        row("FULL"),
        row("PRICE_NO_FEES", **declared(T.REFERRAL_FEE, "")),                                  # R NOT_FOUND
        {k: v for k, v in row("FEES_NO_PRICE").items() if not k.startswith("fin_selling_price_")},
        row("INVALID", **declared(T.COG, "abc")),
        row("UNRESOLVED", **declared(T.FULFILLMENT_FEE, "3.20", applies="")),
        row("ZERO", **declared(T.FULFILLMENT_FEE, "0")),
        row("DROPPED", marketplace=""),                                                         # importer drops
        {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")},                     # no document
    ]
    code, _, store = cli_run(tmp_path, rows, *FINANCIAL)
    assert code == 0
    stored = refs(store)
    assert not any("DROPPED" in ref for ref in stored)
    docs = {ref.split(":")[1]: load_financial_record(store, "run-A", ref) for ref in stored}
    assert docs["NO_SCENARIO"] is None                                  # no FinancialEvidenceSet fabricated
    assert docs["FULL"].calculations.for_result(R.PROFIT).value.value == Decimal("9.30")

    def profit_blocker(sku):
        return {(b.dependency, b.blocker) for b in docs[sku].resolution.for_result(R.PROFIT).blockers}

    assert profit_blocker("PRICE_NO_FEES") == {("REFERRAL_FEE", ResolutionBlocker.VALUE_NOT_FOUND)}
    assert profit_blocker("FEES_NO_PRICE") == {("SELLING_PRICE", ResolutionBlocker.STRUCTURALLY_ABSENT)}
    assert docs["FEES_NO_PRICE"].calculations.for_result(R.BREAK_EVEN_PRICE).value.status is VerificationStatus.VERIFIED
    assert profit_blocker("INVALID") == {("COG", ResolutionBlocker.VALUE_INVALID)}
    assert profit_blocker("UNRESOLVED") == {("FULFILLMENT_FEE", ResolutionBlocker.APPLICABILITY_UNRESOLVED)}
    assert docs["ZERO"].calculations.for_result(R.PROFIT).value.value == Decimal("12.50")  # zero is an operand
    assert docs["FULL"].evidence.evidence_for(T.VAT).applicability.excludes              # exclusion kept
    assert "NO_SCENARIO: scenario: not declared" in capsys.readouterr().out


def test_duplicate_asin_records_and_runs_stay_isolated(tmp_path):
    cli_run(tmp_path, [row("A", **declared(T.COG, "1.00")), row("B", **declared(T.COG, "2.00"))], *FINANCIAL)
    cli_run(tmp_path, [row("A", **declared(T.COG, "7.00"))], *FINANCIAL, execution_id="run-B")
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    a_refs, b_refs = refs(store, "run-A"), refs(store, "run-B")
    cogs = [str(load_financial_record(store, "run-A", ref).evidence.evidence_for(T.COG).amount.value) for ref in a_refs]
    assert cogs == ["1.00", "2.00"]
    assert a_refs[0] == b_refs[0]
    assert str(load_financial_record(store, "run-B", b_refs[0]).evidence.evidence_for(T.COG).amount.value) == "7.00"


# -- Failures ------------------------------------------------------------------------

def test_financial_failure_rolls_back_the_whole_run(tmp_path, monkeypatch, capsys):
    real = cli.build_financial_documents

    def with_foreign_document(outcome, **kwargs):
        docs = real(outcome, **kwargs)
        evidence = docs[0].document.evidence
        foreign = evidence.__class__(evidence.scenario, "run-OTHER", evidence.record_reference, evidence.terms)
        return (FinancialRecordDocument(foreign),)

    monkeypatch.setattr(cli, "build_financial_documents", with_foreign_document)
    code, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    assert code == 3 and "nothing was persisted" in capsys.readouterr().err
    assert store.load_execution_run("run-A") is None and store.load_records("run-A") == []
    assert count(tmp_path / "runs.db") == 0


def test_storage_failure_leaves_no_partial_writes(tmp_path, capsys):
    assert cli_run(tmp_path, [row("A")], *FINANCIAL)[0] == 0
    before = (count(tmp_path / "runs.db"), count(tmp_path / "runs.db", "execution_run_records"))
    code, _, _ = cli_run(tmp_path, [row("A"), row("B")], *FINANCIAL, name="again.xlsx")  # same execution_id
    assert code == 3 and "nothing was persisted" in capsys.readouterr().err
    assert (count(tmp_path / "runs.db"), count(tmp_path / "runs.db", "execution_run_records")) == before


# -- Legacy parity --------------------------------------------------------------------

def sheet(path):
    return list(openpyxl.load_workbook(path).active.iter_rows(values_only=True))


def test_native_flow_changes_no_commercial_result(tmp_path):
    rows = [row("A"), row("B", hazmat="yes"), row("C", cost=""), row("D", marketplace="")]
    assert cli_run(tmp_path, rows, db="legacy.db", execution_id="run-L")[0] == 0
    assert cli_run(tmp_path, rows, *FINANCIAL, db="native.db", execution_id="run-L", name="in2.xlsx")[0] == 0
    legacy_store = SqliteExecutionRunStore(tmp_path / "legacy.db")
    native_store = SqliteExecutionRunStore(tmp_path / "native.db")
    legacy_run, native_run = legacy_store.load_execution_run("run-L"), native_store.load_execution_run("run-L")
    assert native_run.status == legacy_run.status
    assert {**vars(native_run), "input_filename": None, "input_hash": None} == \
        {**vars(legacy_run), "input_filename": None, "input_hash": None}
    # Snapshots persisted by the native flow equal the legacy pipeline's own records.
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))
    thresholds = Thresholds(target_profit=Decimal("5"), target_roi=Decimal("0.3"), minimum_estimated_monthly_sales=0,
                            maximum_risk_severity=Severity.LOW)
    _, records = run_pipeline(tmp_path / "run-L" / "in2.xlsx", thresholds, fees=fees, application_version=cli.juval.__version__,
                              execution_id="run-L", now=NOW)
    assert native_store.load_records("run-L") == [record_to_snapshot(record) for record in records]


def test_output_workbook_is_identical_with_and_without_the_flag(tmp_path):
    path = xlsx(tmp_path, row("A"), row("B", hazmat="yes"))
    out_legacy, out_native = tmp_path / "legacy.xlsx", tmp_path / "native.xlsx"
    assert cli.main([str(path), str(out_legacy), *ARGS, "--execution-id", "run-X"]) == 0
    assert cli.main([str(path), str(out_native), *ARGS, "--execution-id", "run-X",
                     "--persist-db", str(tmp_path / "n.db"), *FINANCIAL]) == 0
    assert sheet(out_legacy) == sheet(out_native)


# -- Determinism and scope ---------------------------------------------------------------

def test_same_input_yields_the_same_stored_payload(tmp_path):
    path = xlsx(tmp_path, row("A"))
    for db in ("one.db", "two.db"):
        assert cli.main([str(path), str(tmp_path / "out.xlsx"), *ARGS, "--execution-id", "run-A",
                         "--persist-db", str(tmp_path / db), *FINANCIAL]) == 0
    one = SqliteExecutionRunStore(tmp_path / "one.db")
    two = SqliteExecutionRunStore(tmp_path / "two.db")
    ref = refs(one)[0]
    assert one.load_financial_record("run-A", ref) == two.load_financial_record("run-A", ref)


def test_new_module_has_no_legacy_operands_network_or_supabase():
    tree = ast.parse(pathlib.Path(documents_module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "datetime", "typing", "juval.application.financial_calculation",
                       "juval.application.financial_serialization", "juval.application.financial_serialization_v2",
                       "juval.application.native_financial_resolution", "juval.application.run_pipeline",
                       "juval.domain.provenance"}
    cli_text = pathlib.Path(cli.__file__).read_text(encoding="utf-8").lower()
    assert "supabase" not in cli_text and "interfaces.api" not in cli_text
