"""Native declared price + accredited fees through import, pipeline and resolver. Synthetic only."""
import ast
import pathlib
from decimal import Decimal

from juval.application import native_financial_resolution as adapter_module
from juval.application.native_financial_resolution import resolve_record_financial_dependencies
from juval.domain.financial_dependencies import FinancialResult, ResolutionBlocker
from juval.domain.financial_fees import FeeEvidenceState, accredited_fee_evidence
from juval.domain.financial_evidence import FinancialTerm
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus
from juval.infrastructure.excel.column_mapping import FINANCIAL_PRICE_COLUMNS
from juval.infrastructure.excel.financial_capture import BLANK_CELL_EVIDENCE
from juval.infrastructure.excel.importer import import_csv, import_excel

from .test_native_financial_capture import BASE, EFFECTIVE, FULL, NOW, capture_of, declared, xlsx
from .test_pipeline_financial_evidence import legacy, run

PRICE = {"fin_selling_price_amount": "24.99", "fin_selling_price_currency": "USD",
         "fin_selling_price_effective_at": EFFECTIVE, "fin_selling_price_basis": "supplier MAP per sellable unit"}
NATIVE = {**FULL, **declared(FinancialTerm.FULFILLMENT_FEE, "3.20"), **PRICE,
          "fin_required_terms": "COG;REFERRAL_FEE;FULFILLMENT_FEE;REFERRAL_FEE_RATE"}
TP = FieldValue.verified(Decimal("3"), unit="USD", source="synthetic config", method="explicit",
                         retrieved_at=NOW, source_type=SourceType.USER_INPUT)


def price_of(tmp_path, row):
    return capture_of(tmp_path, row).selling_price


# -- Native declared price ---------------------------------------------------

def test_legacy_file_has_no_native_price_or_captures(tmp_path):
    assert import_excel(xlsx(tmp_path, BASE), now=NOW).financial_captures == ()


def test_complete_native_price_is_separate_from_the_legacy_price(tmp_path):
    result = import_excel(xlsx(tmp_path, NATIVE), now=NOW)
    [record], [capture] = result.records, result.financial_captures
    price = capture.selling_price
    assert (price.amount.value, price.amount.unit, price.amount.status) == (
        Decimal("24.99"), "USD", VerificationStatus.VERIFIED)
    assert price.amount.provenance.source_type is SourceType.SUPPLIER_FILE
    assert price.amount.provenance.source_reference == "row=2;column=fin_selling_price_amount"
    assert price.context.basis_definition == "supplier MAP per sellable unit"
    assert record.product.price.selling_price_used.value == Decimal("19.99")  # legacy untouched
    assert record.product.price.selling_price_used.unit is None               # and not promoted
    assert not any(i.code == "UNKNOWN_COLUMN" for i in result.issues)


def test_price_without_currency_is_not_captured_nor_borrowed_from_the_scenario(tmp_path):
    capture = capture_of(tmp_path, {**NATIVE, "fin_selling_price_currency": ""})
    assert capture.selling_price is None
    assert any(p.startswith("SELLING_PRICE:") and "currency" in p for p in capture.problems)


def test_price_with_incompatible_unit_or_malformed_currency_is_rejected(tmp_path):
    for currency in ("USD/lb", "ratio", "usd", "$"):
        capture = capture_of(tmp_path, {**NATIVE, "fin_selling_price_currency": currency})
        assert capture.selling_price is None and any(p.startswith("SELLING_PRICE:") for p in capture.problems)


def test_price_without_effective_context_or_amount_column_is_not_captured(tmp_path):
    for row in ({**NATIVE, "fin_selling_price_effective_at": ""},
                {**NATIVE, "fin_selling_price_basis": ""},
                {**NATIVE, "fin_selling_price_effective_at": "2026-02-01T00:00:00"}):
        assert price_of(tmp_path, row) is None
    row = {key: value for key, value in NATIVE.items() if key != "fin_selling_price_amount"}
    capture = capture_of(tmp_path, row)
    assert capture.selling_price is None and "SELLING_PRICE: declared without an amount column" in capture.problems


def test_price_states_blank_invalid_and_inferred(tmp_path):
    blank = price_of(tmp_path, {**NATIVE, "fin_selling_price_amount": ""}).amount
    assert blank.status is VerificationStatus.NOT_FOUND and blank.provenance.evidence == BLANK_CELL_EVIDENCE
    assert blank.provenance.source_type is SourceType.SUPPLIER_FILE
    for raw in ("abc", "NaN", "Infinity", "-1"):
        invalid = price_of(tmp_path, {**NATIVE, "fin_selling_price_amount": raw}).amount
        assert invalid.status is VerificationStatus.INVALID and invalid.raw_value == raw
    inferred = price_of(tmp_path, {**NATIVE, "fin_selling_price_method": "supplier MAP minus promo"}).amount
    assert inferred.status is VerificationStatus.INFERRED
    assert inferred.provenance.method == "supplier MAP minus promo"


def test_zero_price_is_a_declared_zero(tmp_path):
    zero = price_of(tmp_path, {**NATIVE, "fin_selling_price_amount": "0"}).amount
    assert zero.value == Decimal("0") and zero.status is VerificationStatus.VERIFIED


def test_price_only_row_keeps_price_without_a_scenario(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **PRICE})
    assert capture.scenario is None and capture.selling_price.amount.value == Decimal("24.99")


def test_csv_and_xlsx_capture_the_same_price(tmp_path):
    headers = list(NATIVE)
    path = tmp_path / "synthetic.csv"
    path.write_text(",".join(headers) + "\n" + ",".join(NATIVE[h] for h in headers) + "\n",
                    encoding="utf-8", newline="")
    from_csv = import_csv(path, now=NOW).financial_captures[0].selling_price
    from_xlsx = import_excel(xlsx(tmp_path, NATIVE), now=NOW).financial_captures[0].selling_price
    assert (from_csv.amount.value, from_csv.amount.unit, from_csv.context) == (
        from_xlsx.amount.value, from_xlsx.amount.unit, from_xlsx.context)
    assert set(FINANCIAL_PRICE_COLUMNS) >= {"fin_selling_price_amount", "fin_selling_price_currency"}


# -- Resolver integration -------------------------------------------------------

def test_native_price_unblocks_price_results_without_legacy_fallback(tmp_path):
    item = run(xlsx(tmp_path, NATIVE)).financial_evidence[0]
    resolution = resolve_record_financial_dependencies(item, target_profit=TP)
    for result in (FinancialResult.PROFIT, FinancialResult.MARGIN, FinancialResult.MAX_COG_TARGET_PROFIT):
        assert resolution.for_result(result).dependencies_resolved
    price_dep = next(d for d in resolution.for_result(FinancialResult.PROFIT).dependencies
                     if d.dependency == "SELLING_PRICE")
    assert price_dep.operand is item.capture.selling_price.amount
    # Target ROI not supplied: only that result is blocked.
    [blocked] = resolution.for_result(FinancialResult.MAX_COG_TARGET_ROI).blockers
    assert (blocked.dependency, blocked.blocker) == ("TARGET_ROI", ResolutionBlocker.STRUCTURALLY_ABSENT)


def test_without_native_price_the_legacy_price_is_never_used(tmp_path):
    row = {key: value for key, value in NATIVE.items() if not key.startswith("fin_selling_price_")}
    item = run(xlsx(tmp_path, row)).financial_evidence[0]
    resolution = resolve_record_financial_dependencies(item)
    [blocked] = resolution.for_result(FinancialResult.PROFIT).blockers
    assert (blocked.dependency, blocked.blocker) == ("SELLING_PRICE", ResolutionBlocker.STRUCTURALLY_ABSENT)


def test_incompatible_native_price_currency_is_reported_not_converted(tmp_path):
    item = run(xlsx(tmp_path, {**NATIVE, "fin_selling_price_currency": "EUR"})).financial_evidence[0]
    [blocked] = resolve_record_financial_dependencies(item).for_result(FinancialResult.PROFIT).blockers
    assert blocked.blocker is ResolutionBlocker.CURRENCY_INCOMPATIBLE


def test_record_without_scenario_resolves_to_none(tmp_path):
    item = run(xlsx(tmp_path, {**BASE, **PRICE})).financial_evidence[0]
    assert item.evidence is None and resolve_record_financial_dependencies(item) is None


def test_native_fees_are_accredited_per_record_and_never_from_feeinputs(tmp_path):
    rows = [NATIVE, {**NATIVE, "supplier_sku": "SKU-2", **declared(FinancialTerm.FULFILLMENT_FEE, "", applies="no")}]
    result = run(xlsx(tmp_path, *rows))
    first, second = (accredited_fee_evidence(item.evidence) for item in result.financial_evidence)
    assert first[1].state is FeeEvidenceState.DECLARED and second[1].state is FeeEvidenceState.EXCLUDED
    assert first[2].state is FeeEvidenceState.STRUCTURALLY_ABSENT  # OTHER_SELLING_FEES never defaulted to 0
    assert all(record.fees is None for record in result.records)


def test_native_price_and_fees_change_no_legacy_result(tmp_path):
    base_run, base_records = legacy(xlsx(tmp_path, BASE, name="legacy/in.xlsx"))
    native = run(xlsx(tmp_path, {**NATIVE, "fin_selling_price_amount": "99.00"}, name="native/in.xlsx"))
    [a], [b] = base_records, native.records
    assert (a.product.price, a.costs, a.fees, a.profitability, a.decision, a.risk, a.score, a.issues) == \
        (b.product.price, b.costs, b.fees, b.profitability, b.decision, b.risk, b.score, b.issues)


def test_adapter_is_pure_and_touches_no_persistence_api_or_profitability(tmp_path):
    path = xlsx(tmp_path, NATIVE)
    item = run(path).financial_evidence[0]
    assert resolve_record_financial_dependencies(item, target_profit=TP) == \
        resolve_record_financial_dependencies(run(path).financial_evidence[0], target_profit=TP)
    tree = ast.parse(pathlib.Path(adapter_module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "typing", "juval.application.run_pipeline",
                       "juval.domain.financial_dependencies", "juval.domain.provenance"}
    assert [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))] == []
