"""Read-only financial report CLI. Synthetic data, temporary SQLite only."""
import ast
import hashlib
import json
import pathlib
import sqlite3
from dataclasses import replace

import pytest

import juval.application.financial_calculation as calculation
from juval.application.financial_calculation import calculate_financial_results
from juval.application.financial_persistence import save_run_with_financial_records
from juval.application.financial_serialization import FinancialRecordDocument
from juval.application.financial_serialization_v2 import deserialize_financial_record_v2
from juval.domain.financial_dependencies import FinancialResult
from juval.domain.financial_evidence import FinancialTerm as T
from juval.infrastructure.logging.sqlite_read_only import ReadOnlySqliteRunReader
from juval.interfaces.cli import financial_report as report_cli
from juval.interfaces.cli import main as cli

from .test_cli_native_financial import FINANCIAL, cli_run, fixed_now, refs, row  # noqa: F401 (fixture)
from .test_native_financial_capture import BASE, declared, xlsx

DIAG_TABLE, DOC_TABLE = "execution_run_capture_diagnostics", "execution_run_financial_records"


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def report(tmp_path, execution_id="run-A", db="runs.db", capsys=None, extra=()):
    path = tmp_path / db
    if capsys:
        capsys.readouterr()                                           # drop output of earlier CLI runs
    before = digest(path) if path.exists() else None
    code = report_cli.main(["--persist-db", str(path), "--execution-id", execution_id, *extra])
    after = digest(path) if path.exists() else None
    assert before == after                                            # not one byte changed
    out = capsys.readouterr() if capsys else None
    return code, out


def populated(tmp_path):
    rows = [row("FULL"),
            row("PARTIAL", **declared(T.COG, "4.50", source_basis="carton")),
            {**BASE, "supplier_sku": "NO_SCENARIO", **declared(T.COG, "4.50")},
            row("DROPPED", marketplace="")]
    code, _, store = cli_run(tmp_path, rows, "--native-financial-evidence", "--financial-target-profit", "3",
                             "--financial-target-profit-currency", "USD")
    assert code == 0
    return store


def section(out, ref):
    lines = out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"record {ref} "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("record ")), len(lines))
    return "\n".join(lines[start:end])


# -- Content -------------------------------------------------------------------------

def test_report_shows_every_state_explicitly(tmp_path, capsys):
    store = populated(tmp_path)
    code, out = report(tmp_path, capsys=capsys)
    assert code == 0, out.err
    full, partial, no_scenario = refs(store)
    assert out.out.splitlines()[0] == "execution_id=run-A status=SUCCESS records=3"
    assert "DROPPED" not in out.out
    text = section(out.out, full)
    assert "  financial document: v2" in text
    assert "    PROFIT: 9.30 USD VERIFIED" in text                                   # calculated
    assert "    ROI: " in text and "ratio VERIFIED (inexact)" in text
    assert "    MAX_COG_TARGET_ROI: BLOCKED NOT_FOUND - DEPENDENCIES_UNRESOLVED: TARGET_ROI=STRUCTURALLY_ABSENT" in text
    assert "  capture diagnostics: 0" in text                                        # stored and empty
    text = section(out.out, partial)
    assert "  capture diagnostics: 1" in text
    assert ("    [SOURCE_BASIS_INVALID] COG row=3 column=fin_cog_source_basis raw='carton': "
            "source_basis must be one of ['pack', 'sellable_unit'], got 'carton'") in text
    text = section(out.out, no_scenario)
    assert "  financial document: none" in text and "BLOCKED" not in text           # not six blocked results
    assert "    [SCENARIO_UNDECLARED] scenario row=4: not declared:" in text


def test_v1_documents_unrequested_results_inferred_values_and_missing_sets(tmp_path, capsys):
    store = populated(tmp_path)
    # A v1 document (as written before 4L) for another run, computing only PROFIT.
    core = deserialize_financial_record_v2(json.loads(store.load_financial_record("run-A", refs(store)[0])[2])).document
    old_run = replace(store.load_execution_run("run-A"), execution_id="run-OLD")
    evidence = replace(core.evidence, execution_id="run-OLD")
    resolution = replace(core.resolution, execution_id="run-OLD")
    calculated_at = core.calculations.calculations[0].value.provenance.retrieved_at
    calcs = calculate_financial_results(resolution, calculated_at=calculated_at,
                                        requested=frozenset({FinancialResult.PROFIT}))
    v1 = FinancialRecordDocument(evidence, core.selling_price, resolution, calcs)
    snapshot = store.load_records("run-A")[0]
    save_run_with_financial_records(store, old_run, [snapshot], [v1])               # v1 doc, no diagnostics set
    code, out = report(tmp_path, "run-OLD", capsys=capsys)
    assert code == 0
    text = section(out.out, snapshot["record_ref"])
    assert "  financial document: v1" in text
    assert "    PROFIT: 9.30 USD VERIFIED" in text
    assert "    not requested: ROI, MARGIN, BREAK_EVEN_PRICE, MAX_COG_TARGET_PROFIT, MAX_COG_TARGET_ROI" in text
    assert "  capture diagnostics: not stored" in text                              # absent, not empty


def test_inferred_results_are_reported_as_inferred(tmp_path, capsys):
    cli_run(tmp_path, [row("A", **declared(T.COG, "4.50", applies_method="supplier estimate"))], *FINANCIAL)
    code, out = report(tmp_path, capsys=capsys)
    assert code == 0 and "    PROFIT: 9.30 USD INFERRED" in out.out and "PROFIT: 9.30 USD VERIFIED" not in out.out


def test_duplicate_asins_and_runs_stay_separate(tmp_path, capsys):
    cli_run(tmp_path, [row("A", **declared(T.COG, "1.00")), row("B", **declared(T.COG, "2.00"))], *FINANCIAL)
    cli_run(tmp_path, [row("A", **declared(T.COG, "7.00"))], *FINANCIAL, execution_id="run-B")
    code, out = report(tmp_path, capsys=capsys)
    assert code == 0 and out.out.count("\nrecord ") == 2
    assert "PROFIT: 12.80 USD" in out.out and "PROFIT: 11.80 USD" in out.out and "PROFIT: 6.80" not in out.out
    code, out = report(tmp_path, "run-B", capsys=capsys)
    assert code == 0 and out.out.count("\nrecord ") == 1 and "PROFIT: 6.80 USD" in out.out


def test_run_without_records(tmp_path, capsys):
    code, _, store = cli_run(tmp_path, [row("A")])          # legacy CLI persists the run only
    assert code == 0 and store.load_records("run-A") == []
    code, out = report(tmp_path, capsys=capsys)
    assert code == 0 and out.out.strip() == "execution_id=run-A status=SUCCESS records=0"


# -- Integrity -------------------------------------------------------------------------

def tamper(path, sql, *params):
    with sqlite3.connect(path) as conn:
        conn.execute(sql, params)


def test_v2_and_diagnostics_set_disagreement_is_reported_not_resolved(tmp_path, capsys):
    store = populated(tmp_path)
    ref = refs(store)[1]
    payload = json.loads(store.load_capture_diagnostics("run-A", ref)[2])
    payload["diagnostics"][0]["raw_value"] = "pallet"
    tamper(tmp_path / "runs.db", f"UPDATE {DIAG_TABLE} SET payload = ? WHERE record_ref = ?",
           json.dumps(payload, sort_keys=True), ref)
    code, out = report(tmp_path, capsys=capsys)
    assert code == 5
    assert "  integrity: INCONSISTENT - v2 document holds 1 capture problems" in section(out.out, ref)
    assert "error: integrity:" in out.err


@pytest.mark.parametrize("table,payload", [(DOC_TABLE, "not json"), (DIAG_TABLE, "{}"),
                                           (DOC_TABLE, None), (DIAG_TABLE, None)])
def test_corrupt_or_unknown_payloads_abort_without_a_report(tmp_path, capsys, table, payload):
    store = populated(tmp_path)
    ref = refs(store)[0]
    if payload is None:  # unknown version
        text = getattr(store, "load_financial_record" if table == DOC_TABLE else "load_capture_diagnostics")("run-A", ref)[2]
        payload = text.replace(f'"version": {2 if table == DOC_TABLE else 1}', '"version": 9')
    tamper(tmp_path / "runs.db", f"UPDATE {table} SET payload = ? WHERE record_ref = ?", payload, ref)
    code, out = report(tmp_path, capsys=capsys)
    assert code == 5 and out.out == "" and "error: integrity:" in out.err


def test_identity_mismatch_aborts(tmp_path, capsys):
    store = populated(tmp_path)
    first, second = refs(store)[:2]
    other = store.load_financial_record("run-A", second)[2]
    tamper(tmp_path / "runs.db", f"UPDATE {DOC_TABLE} SET payload = ? WHERE record_ref = ?", other, first)
    code, out = report(tmp_path, capsys=capsys)
    assert code == 5 and "stored under" in out.err and out.out == ""


def test_missing_database_is_not_created(tmp_path, capsys):
    code, out = report(tmp_path, db="absent.db", capsys=capsys)
    assert code == 2 and not (tmp_path / "absent.db").exists() and "not found" in out.err


def test_invalid_database(tmp_path, capsys):
    (tmp_path / "runs.db").write_bytes(b"this is not sqlite at all " * 40)
    code, out = report(tmp_path, capsys=capsys)
    assert code == 6 and "not a readable SQLite database" in out.err


def test_unknown_execution(tmp_path, capsys):
    populated(tmp_path)
    code, out = report(tmp_path, "run-NOPE", capsys=capsys)
    assert code == 4 and "run-NOPE" in out.err


# -- Read-only guarantees ---------------------------------------------------------------

def test_reader_cannot_write_and_runs_no_ddl(tmp_path, capsys):
    populated(tmp_path)
    reader = ReadOnlySqliteRunReader(tmp_path / "runs.db")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        with reader._connect() as conn:
            conn.execute("CREATE TABLE should_not_exist (x)")
    code, _ = report(tmp_path, capsys=capsys)
    assert code == 0
    with sqlite3.connect(tmp_path / "runs.db") as conn:
        tables = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "should_not_exist" not in tables


def test_database_predating_the_financial_tables_is_read_without_creating_them(tmp_path, capsys):
    populated(tmp_path)
    with sqlite3.connect(tmp_path / "runs.db") as conn:
        conn.execute(f"DROP TABLE {DIAG_TABLE}")
        conn.execute(f"DROP TABLE {DOC_TABLE}")
    code, out = report(tmp_path, capsys=capsys)
    assert code == 0
    assert out.out.count("financial document: none") == 3 and out.out.count("capture diagnostics: not stored") == 3
    with sqlite3.connect(tmp_path / "runs.db") as conn:
        tables = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert DIAG_TABLE not in tables and DOC_TABLE not in tables


def test_report_is_deterministic_and_does_not_recalculate(tmp_path, capsys, monkeypatch):
    """Default report only; --check-recalculation is the explicit opt-in, tested below."""
    populated(tmp_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("the report must not recalculate")

    monkeypatch.setattr(calculation, "calculate_financial_results", forbidden)
    first = report(tmp_path, capsys=capsys)[1].out
    second = report(tmp_path, capsys=capsys)[1].out
    assert first == second and first


def test_modules_are_read_only_and_local():
    for path in (report_cli.__file__, ReadOnlySqliteRunReader.__module__.replace(".", "/")):
        source = pathlib.Path(path if path.endswith(".py") else f"src/{path}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        assert not {"SqliteExecutionRunStore", "run_pipeline", "calculate_financial_results",
                    "import_file", "requests"} & names
        assert "supabase" not in source.lower() and "INSERT" not in source and "CREATE" not in source


def test_legacy_cli_still_runs_without_the_report(tmp_path):
    path = xlsx(tmp_path, row("A"), name="in.xlsx")
    assert cli.main([str(path), str(tmp_path / "out.xlsx"), "--target-profit", "5", "--target-roi", "0.3",
                     "--max-risk-severity", "LOW", "--referral-fee", "3", "--referral-fee-rate", "0.15"]) == 0


# -- Opt-in recalculation check (--check-recalculation) -----------------------------------

CHECK = ("--check-recalculation",)
MATCH = "    recalculation: MATCHES the current code (not a historical reproduction)"


def rewrite_document(path, ref, mutate):
    with sqlite3.connect(path) as conn:
        (text,) = conn.execute(f"SELECT payload FROM {DOC_TABLE} WHERE record_ref = ?", (ref,)).fetchone()
        payload = json.loads(text)
        mutate(payload)
        conn.execute(f"UPDATE {DOC_TABLE} SET payload = ? WHERE record_ref = ?",
                     (json.dumps(payload, sort_keys=True), ref))


def without_recalculation_lines(text):
    return "\n".join(line for line in text.splitlines() if not line.startswith("    recalculation: "))


def test_v2_documents_that_the_current_code_reproduces_are_reported_as_matching(tmp_path, capsys):
    store = populated(tmp_path)
    full, partial, no_scenario = refs(store)
    code, out = report(tmp_path, capsys=capsys, extra=CHECK)
    assert code == 0, out.err
    text = section(out.out, full)
    assert MATCH in text and "    PROFIT: 9.30 USD VERIFIED" in text                  # stored values still shown
    lines = text.splitlines()
    assert lines.index(MATCH) < lines.index("  capture diagnostics: 0")                 # under the document
    assert "recalculation:" not in section(out.out, no_scenario)                      # no document, nothing to check
    assert out.out.count("    recalculation: ") == sum(
        1 for ref in (full, partial, no_scenario) if store.load_financial_record("run-A", ref) is not None)


def test_default_output_is_unchanged_by_the_opt_in(tmp_path, capsys):
    populated(tmp_path)
    plain = report(tmp_path, capsys=capsys)[1].out
    checked = report(tmp_path, capsys=capsys, extra=CHECK)[1].out
    assert "recalculation:" not in plain and "recalculation:" in checked
    assert without_recalculation_lines(checked) == plain.rstrip("\n")


def test_a_stored_value_the_current_code_does_not_produce_is_reported_not_corrected(tmp_path, capsys):
    store = populated(tmp_path)
    ref = refs(store)[0]

    def mutate(payload):
        profit = next(c for c in payload["calculations"]["calculations"] if c["result"] == "PROFIT")
        profit["value"]["value"] = {"decimal": "9.31"}
    rewrite_document(tmp_path / "runs.db", ref, mutate)
    stored = store.load_financial_record("run-A", ref)
    code, out = report(tmp_path, capsys=capsys, extra=CHECK)
    assert code == 0
    text = section(out.out, ref)
    assert "    recalculation: DIFFERS from the current code in PROFIT" in text
    assert "    PROFIT: 9.31 USD VERIFIED" in text                                       # the stored value, as stored
    assert store.load_financial_record("run-A", ref) == stored                          # not repaired


def test_a_document_from_a_different_implementation_is_not_compared(tmp_path, capsys):
    store = populated(tmp_path)
    ref = refs(store)[0]
    rewrite_document(tmp_path / "runs.db", ref,
                     lambda payload: payload["implementation"].update(expressions_digest="0" * 64))
    code, out = report(tmp_path, capsys=capsys, extra=CHECK)
    assert code == 0
    assert ("    recalculation: NOT CHECKED - expression table differs from the current code"
            in section(out.out, ref))


def test_a_v2_document_without_calculations_is_not_compared(tmp_path, capsys):
    store = populated(tmp_path)
    ref = refs(store)[0]
    rewrite_document(tmp_path / "runs.db", ref, lambda payload: payload.update(calculations=None))
    code, out = report(tmp_path, capsys=capsys, extra=CHECK)
    assert code == 0
    text = section(out.out, ref)
    assert "    calculations: not stored" in text
    assert "    recalculation: NOT CHECKED - no calculation is recorded" in text


def test_v1_documents_are_reported_as_not_checkable(tmp_path, capsys):
    store = populated(tmp_path)
    core = deserialize_financial_record_v2(json.loads(store.load_financial_record("run-A", refs(store)[0])[2])).document
    old_run = replace(store.load_execution_run("run-A"), execution_id="run-OLD")
    v1 = FinancialRecordDocument(replace(core.evidence, execution_id="run-OLD"), core.selling_price,
                                 replace(core.resolution, execution_id="run-OLD"),
                                 replace(core.calculations, execution_id="run-OLD"))
    snapshot = store.load_records("run-A")[0]
    save_run_with_financial_records(store, old_run, [snapshot], [v1])
    code, out = report(tmp_path, "run-OLD", capsys=capsys, extra=CHECK)
    assert code == 0
    text = section(out.out, snapshot["record_ref"])
    assert "  financial document: v1" in text
    assert "    recalculation: NOT CHECKED - format v1 does not record the explicit inputs as supplied" in text


def test_recalculation_check_is_deterministic_and_never_writes(tmp_path, capsys):
    populated(tmp_path)
    first = report(tmp_path, capsys=capsys, extra=CHECK)[1].out                          # report() asserts the
    second = report(tmp_path, capsys=capsys, extra=CHECK)[1].out                         # db bytes are unchanged
    assert first == second and MATCH in first
