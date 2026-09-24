"""Structured capture diagnostics and native per-record weight (ADR-047). Synthetic data, temporary SQLite."""
import ast
import pathlib
from decimal import Decimal

import openpyxl
import pytest

from juval.application.financial_persistence import load_financial_record
from juval.application.financial_serialization_v2 import FinancialRecordDocumentV2
from juval.domain.financial_dependencies import FinancialResult as R, ResolutionBlocker
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.provenance import SourceType, VerificationStatus as VS
from juval.infrastructure.excel import financial_capture
from juval.infrastructure.excel.financial_capture import BLANK_CELL_EVIDENCE, CaptureCode
from juval.infrastructure.excel.importer import import_excel
from juval.interfaces.cli import main as cli

from .test_cli_native_financial import ARGS, FINANCIAL, cli_run, fixed_now, refs, row  # noqa: F401 (fixture)
from .test_native_financial_capture import NOW, declared, xlsx

LB = {"fin_weight_amount": "2", "fin_weight_unit": "lb"}
PER_POUND = declared(T.SHIPPING_PER_POUND, "0.50")          # 0.50 USD/lb, applies


def captures(tmp_path, *rows):
    return import_excel(xlsx(tmp_path, *rows), now=NOW)


def only_capture(tmp_path, data):
    [capture] = captures(tmp_path, data).financial_captures
    return capture


def v2(store, index=0):
    document = load_financial_record(store, "run-A", refs(store)[index])
    assert type(document) is FinancialRecordDocumentV2
    return document


def profit_blockers(document):
    return {(b.dependency, b.blocker) for b in document.document.resolution.for_result(R.PROFIT).blockers}


# -- Structured diagnostics ------------------------------------------------------

def test_diagnostic_is_structured_at_source_and_keeps_the_legacy_text(tmp_path):
    capture = only_capture(tmp_path, row("A", **declared(T.COG, "4.50", effective_at="tomorrow")))
    [diagnostic] = capture.diagnostics
    assert (diagnostic.subject, diagnostic.code, diagnostic.row) == ("COG", CaptureCode.EFFECTIVE_AT_INVALID, 2)
    assert (diagnostic.column, diagnostic.raw_value) == ("fin_cog_effective_at", "tomorrow")
    assert capture.problems == (diagnostic.text,) == ("COG: effective_at 'tomorrow' is not an ISO 8601 instant",)


def test_rows_columns_and_raw_values_are_the_real_ones(tmp_path):
    result = captures(tmp_path, row("A"), row("B", **declared(T.COG, "4.50", source_basis="carton")))
    first, second = result.financial_captures
    assert first.diagnostics == ()
    [diagnostic] = second.diagnostics
    assert (diagnostic.code, diagnostic.row, diagnostic.column, diagnostic.raw_value) == (
        CaptureCode.SOURCE_BASIS_INVALID, 3, "fin_cog_source_basis", "carton")


@pytest.mark.parametrize("data,code", [
    ({"fin_currency": ""}, CaptureCode.SCENARIO_UNDECLARED),
    (declared(T.STORAGE, "0.20"), CaptureCode.CONTRACT_REJECTED),       # domain: allocated term needs a method
    ({**declared(T.COG, "4.50"), "fin_cog_applies": None}, None),        # blank applicability -> no diagnostic
])
def test_no_structure_is_invented_when_no_single_cell_caused_it(tmp_path, data, code):
    capture = only_capture(tmp_path, row("A", **data))
    if code is None:
        assert capture.diagnostics == ()
        return
    [diagnostic] = [d for d in capture.diagnostics if d.code is code]
    assert (diagnostic.column, diagnostic.raw_value) == (None, None)
    assert diagnostic.row == 2


def test_diagnostics_follow_record_ref_with_duplicate_asins_and_dropped_rows(tmp_path):
    result = captures(tmp_path,
                      row("A", **declared(T.COG, "4.50", source_basis="x")),
                      row("DROP", marketplace=""),                       # importer drops row 3
                      row("C", **declared(T.COG, "4.50", source_basis="y")))  # same ASIN as A
    assert [c.record_ref for c in result.financial_captures] == ["row_2:A", "row_4:C"]
    assert [(d.row, d.raw_value) for c in result.financial_captures for d in c.diagnostics] == [(2, "x"), (4, "y")]


def test_record_without_scenario_keeps_diagnostics_on_its_capture_only(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A", fin_currency="")], *FINANCIAL)
    assert load_financial_record(store, "run-A", refs(store)[0]) is None      # no scenario, no document


# -- Native weight ------------------------------------------------------------------

def test_valid_weight_in_pounds_is_captured_with_provenance(tmp_path):
    weight = only_capture(tmp_path, row("A", **LB)).weight
    assert (weight.value, weight.unit, weight.status) == (Decimal("2"), "lb", VS.VERIFIED)
    assert weight.provenance.source_type is SourceType.SUPPLIER_FILE
    assert weight.provenance.source_reference == "row=2;column=fin_weight_amount"


@pytest.mark.parametrize("cells,status,value,raw", [
    ({"fin_weight_amount": "0", "fin_weight_unit": "lb"}, VS.VERIFIED, Decimal("0"), None),
    ({"fin_weight_amount": "", "fin_weight_unit": "lb"}, VS.NOT_FOUND, None, None),
    ({"fin_weight_amount": "heavy", "fin_weight_unit": "lb"}, VS.INVALID, None, "heavy"),
    ({"fin_weight_amount": "-1", "fin_weight_unit": "lb"}, VS.INVALID, None, "-1"),
    ({"fin_weight_amount": "NaN", "fin_weight_unit": "lb"}, VS.INVALID, None, "NaN"),
])
def test_weight_states_are_kept_and_never_zeroed(tmp_path, cells, status, value, raw):
    weight = only_capture(tmp_path, row("A", **cells)).weight
    assert (weight.status, weight.value, weight.raw_value) == (status, value, raw)
    if status is VS.NOT_FOUND:
        assert weight.provenance.evidence == BLANK_CELL_EVIDENCE


def test_weight_units_are_never_assumed_or_converted(tmp_path):
    assert only_capture(tmp_path, row("A", fin_weight_amount="0.9", fin_weight_unit="kg")).weight.unit == "kg"
    undeclared = only_capture(tmp_path, row("A", fin_weight_amount="2", fin_weight_unit=""))
    assert undeclared.weight.unit is None
    assert [d.code for d in undeclared.diagnostics] == [CaptureCode.UNIT_UNDECLARED]


def test_inferred_weight_stays_inferred(tmp_path):
    weight = only_capture(tmp_path, row("A", **LB, fin_weight_method="supplier carton average")).weight
    assert weight.status is VS.INFERRED and weight.provenance.method == "supplier carton average"


def test_weight_absent_is_none_and_legacy_weight_is_never_read(tmp_path):
    capture = only_capture(tmp_path, row("A", weight="2", weight_unit="lb"))
    assert capture.weight is None


# -- SHIPPING_PER_POUND through the CLI -------------------------------------------------

def test_per_pound_shipping_is_calculated_with_usable_rate_and_weight(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A", **PER_POUND, **LB)], *FINANCIAL)
    document = v2(store)
    assert document.document.calculations.for_result(R.PROFIT).value.value == Decimal("8.30")  # 9.30 - 0.50*2
    weight_dep = next(d for d in document.document.resolution.for_result(R.PROFIT).dependencies
                      if d.dependency == "WEIGHT")
    assert weight_dep.operand == document.supplied_inputs.weight


@pytest.mark.parametrize("cells,blocker", [
    ({}, ResolutionBlocker.STRUCTURALLY_ABSENT),
    ({"weight": "2", "weight_unit": "lb"}, ResolutionBlocker.STRUCTURALLY_ABSENT),       # legacy weight ignored
    ({"fin_weight_amount": "0.9", "fin_weight_unit": "kg"}, ResolutionBlocker.UNIT_INCOMPATIBLE),  # no kg->lb
    ({"fin_weight_amount": "2", "fin_weight_unit": ""}, ResolutionBlocker.UNIT_INCOMPATIBLE),
    ({"fin_weight_amount": "", "fin_weight_unit": "lb"}, ResolutionBlocker.VALUE_NOT_FOUND),
    ({"fin_weight_amount": "heavy", "fin_weight_unit": "lb"}, ResolutionBlocker.VALUE_INVALID),
])
def test_per_pound_shipping_stays_blocked_without_usable_weight(tmp_path, cells, blocker):
    _, _, store = cli_run(tmp_path, [row("A", **PER_POUND, **cells)], *FINANCIAL)
    document = v2(store)
    assert profit_blockers(document) == {("WEIGHT", blocker)}
    assert document.document.calculations.for_result(R.PROFIT).value.status is VS.NOT_FOUND
    assert document.document.calculations.for_result(R.MAX_COG_TARGET_ROI).value.status is VS.NOT_FOUND


def test_excluded_per_pound_shipping_needs_no_weight(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)       # every_term_declared excludes it
    document = v2(store)
    assert "WEIGHT" not in {d.dependency for item in document.document.resolution.results for d in item.dependencies}
    assert document.supplied_inputs.weight is None
    assert document.document.calculations.for_result(R.PROFIT).value.value == Decimal("9.30")


# -- v2 persistence ------------------------------------------------------------------------

@pytest.mark.parametrize("cells", [
    LB, {"fin_weight_amount": "0.900", "fin_weight_unit": "kg"},
    {"fin_weight_amount": "", "fin_weight_unit": "lb"}, {"fin_weight_amount": "heavy", "fin_weight_unit": "lb"},
])
def test_v2_keeps_the_supplied_weight_and_diagnostics_through_sqlite(tmp_path, cells):
    data = row("A", **PER_POUND, **cells, **declared(T.PREP, "0.40", source_basis="carton"))
    _, _, store = cli_run(tmp_path, [data], *FINANCIAL)
    document = v2(store)
    weight = document.supplied_inputs.weight
    assert weight.provenance.source_reference == "row=2;column=fin_weight_amount"
    if cells["fin_weight_amount"] == "heavy":
        assert (weight.status, weight.raw_value) == (VS.INVALID, "heavy")
    elif cells["fin_weight_amount"] == "":
        assert weight.status is VS.NOT_FOUND
    else:
        assert str(weight.value) == cells["fin_weight_amount"] and weight.unit == cells["fin_weight_unit"]
    [problem] = document.capture_problems
    assert (problem.subject, problem.row, problem.column, problem.raw_value) == (
        "PREP", 2, "fin_prep_source_basis", "carton")


# -- Commercial parity --------------------------------------------------------------------

def sheet(path):
    return list(openpyxl.load_workbook(path).active.iter_rows(values_only=True))


def test_native_weight_and_diagnostics_change_no_commercial_result(tmp_path):
    rows = [row("A", **PER_POUND, **LB, weight="3", weight_unit="lb"), row("B", hazmat="yes", fin_weight_amount="x")]
    path = xlsx(tmp_path, *rows, name="native/in.xlsx")
    plain = xlsx(tmp_path, *[{k: v for k, v in r.items() if not k.startswith("fin_")} for r in rows],
                 name="legacy/in.xlsx")
    assert cli.main([str(plain), str(tmp_path / "legacy.xlsx"), *ARGS, "--execution-id", "run-A",
                     "--persist-db", str(tmp_path / "legacy.db")]) == 0
    assert cli.main([str(path), str(tmp_path / "native.xlsx"), *ARGS, "--execution-id", "run-A",
                     "--persist-db", str(tmp_path / "native.db"), *FINANCIAL]) == 0
    assert sheet(tmp_path / "legacy.xlsx") == sheet(tmp_path / "native.xlsx")


def test_capturer_has_no_network_or_legacy_operands():
    tree = ast.parse(pathlib.Path(financial_capture.__file__).read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"CostInputs", "FeeInputs", "requests", "urlopen", "PriceObservation"} & names
