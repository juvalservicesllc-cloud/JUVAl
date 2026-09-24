"""Format v2 of the financial record. Synthetic fixtures only; every round-trip goes through JSON."""
import ast
import copy
import json
import pathlib
from decimal import Decimal

import pytest

from juval.application import financial_serialization_v2 as module
from juval.application.financial_serialization import (
    FinancialRecordDocument, FinancialSerializationError, deserialize_financial_record, serialize_financial_record,
)
from juval.application.financial_serialization_v2 import (
    CaptureProblem, FinancialRecordDocumentV2, ImplementationIdentity, SuppliedInputs, assess_reproducibility,
    current_dependency_matrix_digest, current_expressions_digest, deserialize_financial_record_v2,
    read_financial_record, serialize_financial_record_v2,
)
from juval.domain.financial_dependencies import FinancialResult as R, ResolutionBlocker
from juval.domain.financial_evidence import DeclaredSellingPrice
from juval.domain.provenance import SourceType

from .test_financial_calculation import PRICE, TP, TR, complete
from .test_financial_dependencies import INV, I, NF, T, fv, term
from .test_financial_serialization import DECLARED_PRICE, document

IDENTITY = ImplementationIdentity.current(application_version="0.9.0-test", code_revision="deadbeef" * 5)
PROBLEMS = (CaptureProblem("COG: effective_at not declared; the import time never substitutes for it"),
            CaptureProblem("SELLING_PRICE: declared without an amount column", subject="SELLING_PRICE", row=7,
                           column="fin_selling_price_currency", raw_value="usd"))


def v2(doc=None, *, inputs=None, problems=PROBLEMS, identity=IDENTITY):
    doc = doc or document()
    if inputs is None:
        inputs = SuppliedInputs(selling_price=PRICE, target_profit=TP, target_roi=TR)
    return FinancialRecordDocumentV2(doc, inputs, problems, identity)


def round_trip(doc):
    payload = serialize_financial_record_v2(doc)
    text = json.dumps(payload, sort_keys=True)
    back = deserialize_financial_record_v2(json.loads(text))
    assert back == doc
    assert json.dumps(serialize_financial_record_v2(back), sort_keys=True) == text
    return back, payload


def with_price(amount, **inputs):
    """A document whose declared price and resolver price input are the same supplied FieldValue."""
    price = DeclaredSellingPrice(amount, DECLARED_PRICE.context)
    resolver_inputs = {"selling_price": amount, "target_profit": TP, "target_roi": TR, **inputs}
    doc = document(price=price, inputs=resolver_inputs)
    supplied = SuppliedInputs(selling_price=amount, target_profit=resolver_inputs["target_profit"],
                              target_roi=resolver_inputs["target_roi"], weight=resolver_inputs.get("weight"))
    return v2(doc, inputs=supplied)


# -- Round-trip -------------------------------------------------------------------

def test_complete_v2_round_trip_keeps_v1_core_and_new_blocks():
    back, payload = round_trip(v2())
    assert (payload["format"], payload["version"]) == ("juval.adr047.financial-record", 2)
    assert back.document.calculations.for_result(R.PROFIT).value.value == Decimal("8.50")
    assert back.supplied_inputs.target_profit.unit == "USD"
    assert back.supplied_inputs.target_roi.unit == "ratio"
    assert back.capture_problems == PROBLEMS
    assert (back.capture_problems[1].row, back.capture_problems[1].column) == (7, "fin_selling_price_currency")
    assert back.implementation == IDENTITY


def test_partial_v2_round_trips_without_resolution_or_inputs():
    doc = document(resolve=False, price=None)
    round_trip(v2(doc, inputs=SuppliedInputs(), problems=()))


@pytest.mark.parametrize("amount,blocker", [
    (fv(None, status=NF), ResolutionBlocker.VALUE_NOT_FOUND),
    (fv("19,99", status=INV), ResolutionBlocker.VALUE_INVALID),
])
def test_unusable_supplied_price_is_kept_as_supplied(amount, blocker):
    back, payload = round_trip(with_price(amount))
    assert back.supplied_inputs.selling_price == amount
    assert back.supplied_inputs.selling_price.status is amount.status
    assert back.supplied_inputs.selling_price.raw_value == amount.raw_value     # "19,99" survives
    [dep] = [d for d in back.document.resolution.for_result(R.PROFIT).dependencies if d.dependency == "SELLING_PRICE"]
    assert dep.blocker is blocker and dep.operand is None                        # v1 core only had this


def test_incompatible_currency_and_unit_inputs_are_kept_verbatim():
    back, _ = round_trip(with_price(fv(Decimal("20.00"), "USD"), target_profit=fv(Decimal("3"), "EUR"),
                                    target_roi=fv(Decimal("30"), "%")))
    assert back.supplied_inputs.target_profit.unit == "EUR"
    assert back.supplied_inputs.target_roi.value == Decimal("30") and back.supplied_inputs.target_roi.unit == "%"
    blockers = {d.dependency: d.blocker for item in back.document.resolution.results for d in item.blockers}
    assert blockers == {"TARGET_PROFIT": ResolutionBlocker.CURRENCY_INCOMPATIBLE,
                        "TARGET_ROI": ResolutionBlocker.UNIT_INCOMPATIBLE}


def test_supplied_weight_is_kept_even_with_an_incompatible_unit():
    ev = complete(SHIPPING_PER_POUND=term(T.SHIPPING_PER_POUND, "0.50"))
    weight = fv(Decimal("2.000"), "kg")
    doc = document(ev, inputs={"selling_price": PRICE, "target_profit": TP, "target_roi": TR, "weight": weight})
    back, _ = round_trip(v2(doc, inputs=SuppliedInputs(PRICE, weight, TP, TR)))
    assert str(back.supplied_inputs.weight.value) == "2.000" and back.supplied_inputs.weight.unit == "kg"


def test_decimal_scale_provenance_and_blocked_or_unrequested_results_survive():
    doc = document(complete(COG=term(T.COG, "4.50", status=I)), requested=frozenset({R.PROFIT, R.ROI}))
    back, _ = round_trip(v2(doc))
    assert [c.result for c in back.document.calculations.calculations] == [R.PROFIT, R.ROI]
    assert back.document.calculations.for_result(R.PROFIT).value.status is I      # not promoted
    assert str(back.supplied_inputs.selling_price.value) == "20.00"
    assert back.supplied_inputs.target_profit.provenance.source_type is SourceType.SUPPLIER_FILE
    blocked, _ = round_trip(v2(document(complete(REFERRAL_FEE=None))))
    assert blocked.document.calculations.for_result(R.PROFIT).value.status is NF


# -- Coherence -------------------------------------------------------------------------

@pytest.mark.parametrize("inputs", [
    SuppliedInputs(selling_price=PRICE, target_profit=TP),                       # TR used but not recorded
    SuppliedInputs(selling_price=PRICE, target_profit=fv(Decimal("4"), "USD"), target_roi=TR),  # differs
    SuppliedInputs(target_profit=TP, target_roi=TR),                              # price declared but not recorded
    SuppliedInputs(selling_price=fv(Decimal("21.00"), "USD"), target_profit=TP, target_roi=TR),  # not the declared
])
def test_supplied_inputs_must_match_what_the_resolution_saw(inputs):
    with pytest.raises(ValueError):
        v2(inputs=inputs)


def test_duplicate_capture_problems_and_bad_identities_are_rejected():
    with pytest.raises(ValueError):
        v2(problems=(PROBLEMS[0], PROBLEMS[0]))
    for bad in (dict(expressions_digest="abc"), dict(code_revision=" "), dict(calculator=""),
                dict(derivation_methods=["x"])):
        with pytest.raises(ValueError):
            ImplementationIdentity(**{**vars(IDENTITY), **bad})
    for bad in (dict(text=" "), dict(row=0), dict(row=True), dict(column="")):
        with pytest.raises(ValueError):
            CaptureProblem(**{"text": "x", **bad})


def corrupt(mutate):
    payload = json.loads(json.dumps(serialize_financial_record_v2(v2())))
    mutate(payload)
    with pytest.raises(FinancialSerializationError):
        deserialize_financial_record_v2(payload)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(version=3), lambda p: p.update(version=1), lambda p: p.update(version="2"),
    lambda p: p.pop("implementation"), lambda p: p.update(extra=None),
    lambda p: p["supplied_inputs"].pop("weight"),
    lambda p: p["supplied_inputs"]["target_profit"].update(value={"decimal": "3.0e0"}),
    lambda p: p["supplied_inputs"]["target_profit"]["provenance"].update(retrieved_at="2026-03-01"),
    lambda p: p["supplied_inputs"]["target_profit"]["provenance"].update(source_type="AMAZON"),
    lambda p: p["supplied_inputs"]["target_profit"].update(value={"decimal": "9"}),   # inconsistent with resolution
    lambda p: p["capture_problems"].append(p["capture_problems"][0]),
    lambda p: p["capture_problems"][1].update(row="7"),
    lambda p: p["capture_problems"][1].update(raw_value={"decimal": "1"}),
    lambda p: p["implementation"].update(expressions_digest="not-a-digest"),
    lambda p: p["implementation"].update(derivation_methods="none"),
    lambda p: p["evidence"]["terms"][0]["amount"].update(value={"decimal": "NaN"}),
])
def test_corrupt_v2_payload_is_rejected(mutate):
    corrupt(mutate)


# -- v1 compatibility -------------------------------------------------------------------

def test_v1_is_read_as_v1_and_v2_as_v2_without_reinterpretation():
    v1_payload = json.loads(json.dumps(serialize_financial_record(document())))
    v2_payload = json.loads(json.dumps(serialize_financial_record_v2(v2())))
    assert type(read_financial_record(v1_payload)) is FinancialRecordDocument
    assert type(read_financial_record(v2_payload)) is FinancialRecordDocumentV2
    with pytest.raises(FinancialSerializationError, match="version 2"):
        deserialize_financial_record(v2_payload)                  # the v1 reader never accepts v2
    with pytest.raises(FinancialSerializationError, match="version 1"):
        deserialize_financial_record_v2(v1_payload)               # v1 is not upgraded
    for version in (0, 3, "1", None, True):
        with pytest.raises(FinancialSerializationError):
            read_financial_record({**v1_payload, "version": version})
    assert serialize_financial_record(document()) == v1_payload   # v1 output unchanged


def test_v2_core_is_byte_identical_to_v1():
    doc = document()
    core_v1 = {k: v for k, v in serialize_financial_record(doc).items() if k != "version"}
    core_v2 = {k: v for k, v in serialize_financial_record_v2(v2(doc)).items()
               if k not in ("version", "supplied_inputs", "capture_problems", "implementation")}
    assert core_v1 == core_v2


# -- Implementation identity and reproducibility -------------------------------------------

def test_identity_digests_are_of_the_real_tables_and_unknowns_stay_unknown():
    unknown = ImplementationIdentity.current()
    assert (unknown.application_version, unknown.code_revision, unknown.configuration) == (None, None, None)
    assert unknown.expressions_digest == current_expressions_digest() == IDENTITY.expressions_digest
    assert unknown.dependency_matrix_digest == current_dependency_matrix_digest()
    assert unknown.derivation_methods == ()
    back, payload = round_trip(v2(identity=unknown))
    assert payload["implementation"]["code_revision"] is None and back.implementation == unknown


def test_reproducibility_guarantees_are_assessed_separately_and_c_is_never_asserted():
    v1_assessment = assess_reproducibility(document())
    assert v1_assessment.state_recovery == ()
    assert "format v1 does not record the explicit inputs as supplied" in v1_assessment.input_reconstruction
    full = assess_reproducibility(v2())
    assert full.state_recovery == () and full.input_reconstruction == ()
    assert full.historical_reproduction == (
        "the code and runtime a document names cannot be verified from the document",)
    unknown = assess_reproducibility(v2(identity=ImplementationIdentity.current()))
    assert {"application_version is unknown", "code_revision is unknown"} <= set(unknown.historical_reproduction)
    stale = ImplementationIdentity(IDENTITY.calculator, "0" * 64, IDENTITY.dependency_matrix_digest,
                                   IDENTITY.application_version, IDENTITY.code_revision)
    assert "expression table differs from the current code" in assess_reproducibility(v2(identity=stale)).historical_reproduction
    no_calc = assess_reproducibility(v2(document(calculate=False)))
    assert "no calculation is recorded" in no_calc.historical_reproduction


# -- Purity -----------------------------------------------------------------------------

def test_v2_serialization_is_deterministic_pure_and_non_mutating():
    doc = v2()
    before = copy.deepcopy(doc)
    assert serialize_financial_record_v2(doc) == serialize_financial_record_v2(doc)
    assert doc == before
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "dataclasses", "typing", "juval.application.financial_calculation",
                       "juval.application.financial_serialization", "juval.domain.financial_dependencies",
                       "juval.domain.provenance"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"open", "sqlite3", "CostInputs", "FeeInputs", "compute_profitability"} & names
