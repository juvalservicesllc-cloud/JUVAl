"""Native XLSX -> pipeline -> resolver -> accredited calculation. Synthetic only."""
from decimal import Decimal

from juval.application.financial_calculation import CalculationBlocker, calculate_financial_results
from juval.application.native_financial_resolution import resolve_record_financial_dependencies
from juval.domain.financial_dependencies import FinancialResult as R
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.provenance import SourceType, VerificationStatus

from .test_native_financial_capture import BASE, NOW, SCENARIO, declared, xlsx
from .test_native_price_and_fees import PRICE, TP
from .test_pipeline_financial_evidence import legacy, run

AMOUNTS = {T.COG: "4.50", T.REFERRAL_FEE: "3.00", T.FULFILLMENT_FEE: "3.20"}


def every_term_declared(**amounts):
    row = {**BASE, **SCENARIO, **PRICE, "fin_selling_price_amount": "20.00",
           "fin_required_terms": ";".join(t.value for t in T)}
    for term in T:
        if term is T.REFERRAL_FEE_RATE:
            row.update(declared(term, "0.15", currency=None))
        elif term in amounts:
            row.update(declared(term, amounts[term]))
        else:
            row.update(declared(term, None, currency=None, applies="no"))
    return row


def calculate(path, **inputs):
    item = run(path).financial_evidence[0]
    return calculate_financial_results(resolve_record_financial_dependencies(item, **inputs), calculated_at=NOW)


def test_declared_supplier_evidence_calculates_and_legacy_results_are_unchanged(tmp_path):
    path = xlsx(tmp_path, every_term_declared(**AMOUNTS), name="native/in.xlsx")
    result = calculate(path, target_profit=TP)
    profit = result.for_result(R.PROFIT).value
    assert profit.value == Decimal("9.30")                 # 20.00 - 6.20 - 4.50
    assert profit.unit == "USD" and profit.status is VerificationStatus.VERIFIED
    assert profit.provenance.source_type is SourceType.CALCULATED
    assert result.for_result(R.BREAK_EVEN_PRICE).value.value == Decimal("7.70") / Decimal("0.85")
    assert result.for_result(R.MAX_COG_TARGET_ROI).blocker is CalculationBlocker.DEPENDENCIES_UNRESOLVED
    # Legacy engine and decision are untouched by the native calculation.
    [native_record] = run(path).records
    _, [legacy_record] = legacy(xlsx(tmp_path, BASE, name="legacy/in.xlsx"))
    assert (native_record.profitability, native_record.decision) == (legacy_record.profitability, legacy_record.decision)


def test_scenario_that_omits_formula_terms_does_not_calculate(tmp_path):
    row = {**BASE, **SCENARIO, **PRICE, **declared(T.COG, "4.50"), **declared(T.REFERRAL_FEE, "3.00"),
           **declared(T.REFERRAL_FEE_RATE, "0.15", currency=None), "fin_required_terms": "COG"}
    item = calculate(xlsx(tmp_path, row)).for_result(R.PROFIT)
    assert item.blocker is CalculationBlocker.FORMULA_TERM_UNDECLARED
    assert item.value.status is VerificationStatus.NOT_FOUND and item.value.value is None


def test_native_record_round_trips_through_versioned_json(tmp_path):
    import json

    from juval.application.financial_serialization import (
        FinancialRecordDocument, deserialize_financial_record, serialize_financial_record,
    )

    path = xlsx(tmp_path, every_term_declared(**AMOUNTS))
    item = run(path).financial_evidence[0]
    resolution = resolve_record_financial_dependencies(item, target_profit=TP)
    document = FinancialRecordDocument(item.evidence, item.capture.selling_price, resolution,
                                       calculate_financial_results(resolution, calculated_at=NOW))
    text = json.dumps(serialize_financial_record(document), sort_keys=True)
    back = deserialize_financial_record(json.loads(text))
    assert back == document
    assert back.calculations.for_result(R.PROFIT).value.value == Decimal("9.30")
    assert back.selling_price.amount.provenance.source_reference == "row=2;column=fin_selling_price_amount"
    assert json.dumps(serialize_financial_record(back), sort_keys=True) == text
