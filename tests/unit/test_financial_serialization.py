"""Synthetic fixtures only. Every round-trip goes through json.dumps/json.loads."""
import ast
import copy
import json
import pathlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest

from juval.application import financial_serialization as module
from juval.application.financial_calculation import CalculationBlocker as CB, calculate_financial_results
from juval.application.financial_serialization import (
    FORMAT, VERSION, FinancialRecordDocument, FinancialSerializationError,
    deserialize_financial_record, serialize_financial_record,
)
from juval.domain.financial_dependencies import FinancialResult as R, ResolutionBlocker, resolve_financial_dependencies
from juval.domain.financial_evidence import DeclaredSellingPrice, EffectiveContext, FinancialDependency, FinancialTermEvidence
from juval.domain.provenance import FieldValue, SourceType

from .test_financial_calculation import DECLARED, PRICE, SHIPPING, TP, TR, complete
from .test_financial_dependencies import CONTEXT, INV, I, NF, NOW, T, V, evidence, fv, term

DECLARED_PRICE = DeclaredSellingPrice(PRICE, EffectiveContext(
    effective_at=datetime(2026, 2, 1, tzinfo=timezone(timedelta(hours=-5))), basis_definition="synthetic MAP"))


def document(ev=None, *, price=DECLARED_PRICE, inputs=None, requested=None, resolve=True, calculate=True):
    ev = ev or complete()
    inputs = {"selling_price": PRICE, "target_profit": TP, "target_roi": TR} if inputs is None else inputs
    resolution = resolve_financial_dependencies(ev, **inputs) if resolve else None
    calcs = (calculate_financial_results(resolution, calculated_at=NOW, requested=requested)
             if resolve and calculate else None)
    return FinancialRecordDocument(ev, price, resolution, calcs)


def round_trip(doc):
    payload = serialize_financial_record(doc)
    text = json.dumps(payload, sort_keys=True)
    back = deserialize_financial_record(json.loads(text))
    assert back == doc                                              # semantic equality of every field
    assert serialize_financial_record(back) == payload              # serialize -> deserialize -> serialize
    assert json.dumps(serialize_financial_record(back), sort_keys=True) == text  # byte-identical canonical JSON
    return back, payload


def payload_of(doc=None):
    return json.loads(json.dumps(serialize_financial_record(doc or document())))


# -- Identity and coverage ---------------------------------------------------

def test_payload_declares_format_and_version_separately_from_scenario_identity():
    payload = payload_of()
    assert (payload["format"], payload["version"]) == (FORMAT, VERSION) == ("juval.adr047.financial-record", 1)
    scenario = payload["evidence"]["scenario"]
    assert (scenario["scenario_version"], scenario["policy_identity"]) == ("v1", "synthetic-policy@v1")
    assert (payload["evidence"]["execution_id"], payload["evidence"]["record_reference"]) == ("run-1", "row_2:SKU")
    assert (payload["calculations"]["decimal_precision"], payload["calculations"]["decimal_rounding"]) == (
        28, "ROUND_HALF_EVEN")


@pytest.mark.parametrize("doc", [
    pytest.param(lambda: document(resolve=False, price=None), id="scenario+evidence only"),
    pytest.param(lambda: document(), id="complete evidence, price, resolution, calculations"),
    pytest.param(lambda: document(complete(REFERRAL_FEE=None)), id="partial evidence, blocked results"),
    pytest.param(lambda: document(complete(COG=term(T.COG, "4.50", status=I))), id="inferred operand"),
    pytest.param(lambda: document(complete(COG=term(T.COG, "x", status=NF))), id="NOT_FOUND term"),
    pytest.param(lambda: document(complete(COG=term(T.COG, "x", status=INV))), id="INVALID term"),
    pytest.param(lambda: document(complete(FULFILLMENT_FEE=term(T.FULFILLMENT_FEE, "3.20", applies_status=NF))),
                 id="unresolved applicability"),
    pytest.param(lambda: document(complete(OTHER_SELLING_FEES=term(T.OTHER_SELLING_FEES, None, applies=False,
                                                                   applies_status=I))), id="inferred exclusion"),
    pytest.param(lambda: document(inputs={"selling_price": fv(Decimal("20.00"), "EUR")}), id="currency mismatch"),
    pytest.param(lambda: document(complete(SHIPPING_PER_POUND=term(T.SHIPPING_PER_POUND, "0.50")),
                                  inputs={"selling_price": PRICE, "weight": fv(Decimal("2"), "kg")}), id="unit mismatch"),
    pytest.param(lambda: document(evidence(*complete().terms, required=tuple(T),
                                           context_requirements=("fee window",))), id="context requirement"),
    pytest.param(lambda: document(inputs={"selling_price": fv(Decimal("0"), "USD"), "target_roi": fv(Decimal("-1"), "ratio")}),
                 id="failed math preconditions"),
    pytest.param(lambda: document(requested=frozenset({R.PROFIT})), id="unrequested results absent"),
    pytest.param(lambda: document(evidence(*DECLARED.values(), required=(T.COG,))), id="undeclared formula terms"),
])
def test_round_trip_through_json_preserves_every_field(doc):
    round_trip(doc())


# -- Specific preservation -------------------------------------------------------

def test_blocked_unrequested_and_failed_results_keep_their_meaning():
    back, _ = round_trip(document(complete(REFERRAL_FEE=None), requested=frozenset({R.PROFIT, R.BREAK_EVEN_PRICE})))
    assert [c.result for c in back.calculations.calculations] == [R.PROFIT, R.BREAK_EVEN_PRICE]
    profit = back.calculations.for_result(R.PROFIT)
    assert profit.blocker is CB.DEPENDENCIES_UNRESOLVED and profit.value.status is NF and profit.value.value is None
    assert profit.value.provenance.evidence == "DEPENDENCIES_UNRESOLVED: REFERRAL_FEE=STRUCTURALLY_ABSENT"
    [blocked] = profit.resolution.blockers
    assert (blocked.dependency, blocked.blocker, blocked.detail) == (
        "REFERRAL_FEE", ResolutionBlocker.STRUCTURALLY_ABSENT, "required by the scenario but not represented")
    failed, _ = round_trip(document(inputs={"selling_price": fv(Decimal("0"), "USD")}))
    margin = failed.calculations.for_result(R.MARGIN)
    assert margin.blocker is CB.MATH_PRECONDITION_FAILED
    assert (margin.preconditions[0].expression, margin.preconditions[0].satisfied) == ("P > 0", False)


def test_calculated_value_expression_exactness_and_provenance_survive():
    back, _ = round_trip(document())
    roi = back.calculations.for_result(R.ROI)
    assert roi.exact is False and roi.expression == "profit / (COG + C0)"
    assert roi.value.value == Decimal("8.50") / Decimal("5.30") and roi.value.unit == "ratio"
    assert roi.value.provenance.source_type is SourceType.CALCULATED
    cog = next(d for d in back.resolution.for_result(R.PROFIT).dependencies if d.dependency == "COG")
    assert cog.operand.provenance.source_type is SourceType.SUPPLIER_FILE  # not replaced by CALCULATED
    assert cog.operand.status is V


def test_decimal_scale_sign_and_long_values_are_exact():
    for text in ("0", "0.0", "0.00", "0.10", "8.50", "1234567890.123456789012345678901234567", "1E+2"):
        ev = complete(COG=term(T.COG, text))
        back, payload = round_trip(document(ev, resolve=False, price=None))
        assert str(back.evidence.evidence_for(T.COG).amount.value) == text
    negative = document(inputs={"selling_price": fv(Decimal("0.00"), "USD")})
    back, _ = round_trip(negative)
    assert str(back.calculations.for_result(R.PROFIT).value.value) == "-11.50"


def test_reconstruction_ignores_the_callers_decimal_context():
    payload = payload_of(document(complete(COG=term(T.COG, "1234567890.123456789012345678901234567")),
                                  resolve=False, price=None))
    with localcontext() as ctx:
        ctx.prec = 3
        back = deserialize_financial_record(payload)
    assert str(back.evidence.evidence_for(T.COG).amount.value) == "1234567890.123456789012345678901234567"


def test_timestamps_keep_their_offsets_and_context():
    back, payload = round_trip(document())
    assert payload["selling_price"]["context"]["effective_at"] == "2026-02-01T00:00:00-05:00"
    assert back.selling_price.context.effective_at.utcoffset() == timedelta(hours=-5)
    shipping = back.evidence.evidence_for(T.SHIPPING_PER_UNIT)
    assert shipping.allocation_method == SHIPPING.allocation_method and shipping.context == CONTEXT


def test_exclusion_is_never_a_zero_after_round_trip():
    back, payload = round_trip(document())
    other = back.evidence.evidence_for(T.OTHER_SELLING_FEES)
    assert other.applicability.excludes and other.amount is None
    [serialized] = [t for t in payload["evidence"]["terms"] if t["term"] == "OTHER_SELLING_FEES"]
    assert serialized["amount"] is None


def test_term_dependencies_are_restored_as_references_to_the_evidence():
    back, _ = round_trip(document())
    for item in back.resolution.results:
        for dep in item.dependencies:
            if dep.evidence is not None:
                assert dep.evidence is back.evidence.evidence_for(dep.term)
                assert dep.operand is None or dep.operand is dep.evidence.amount
    assert back.calculations.for_result(R.PROFIT).resolution is back.resolution.for_result(R.PROFIT)


def test_declared_dependencies_links_survive():
    derived = FinancialTermEvidence(
        T.REFERRAL_FEE, term(T.REFERRAL_FEE).applicability, CONTEXT,
        FieldValue.verified(Decimal("3.00"), unit="USD", source="synthetic", method="m", retrieved_at=NOW,
                            source_type=SourceType.CALCULATED),
        depends_on=(FinancialDependency("fixture:rate", "rate used", T.REFERRAL_FEE_RATE),
                    FinancialDependency("fixture:price", "price used")))
    back, _ = round_trip(document(evidence(derived, DECLARED[T.REFERRAL_FEE_RATE], required=(T.COG,)),
                                  resolve=False, price=None))
    assert back.evidence.evidence_for(T.REFERRAL_FEE).depends_on == derived.depends_on


# -- Rejection ------------------------------------------------------------------

def corrupt(mutate):
    payload = payload_of()
    mutate(payload)
    with pytest.raises(FinancialSerializationError):
        deserialize_financial_record(payload)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(version=2), lambda p: p.update(version="1"), lambda p: p.update(version=1.0),
    lambda p: p.update(version=True), lambda p: p.update(format="juval.other"),
])
def test_unknown_format_or_version_is_rejected(mutate):
    corrupt(mutate)


def first_term(p):
    return p["evidence"]["terms"][0]


@pytest.mark.parametrize("mutate", [
    lambda p: p.pop("calculations"),                                              # missing key
    lambda p: p.update(extra=1),                                                   # unknown key
    lambda p: first_term(p).update(term="SHIPPING_COST"),                         # invalid enum
    lambda p: first_term(p)["amount"]["provenance"].update(verification_status="MAYBE"),
    lambda p: first_term(p)["amount"]["provenance"].update(source_type="AMAZON"),
    lambda p: first_term(p)["amount"].update(value={"decimal": "4.5000000001e0"}),  # non-canonical
    lambda p: first_term(p)["amount"].update(value={"decimal": "NaN"}),
    lambda p: first_term(p)["amount"].update(value={"decimal": "abc"}),
    lambda p: first_term(p)["amount"].update(value={"float": 4.5}),
    lambda p: first_term(p)["amount"].update(value=4.5),
    lambda p: first_term(p)["amount"]["provenance"].update(retrieved_at="2026-03-01T00:00:00"),  # naive
    lambda p: first_term(p)["amount"]["provenance"].update(retrieved_at="yesterday"),
    lambda p: first_term(p)["context"].update(effective_at="2026-02-01"),
    lambda p: first_term(p)["amount"].update(value=None),                      # VERIFIED without value
    lambda p: p["evidence"]["scenario"].update(currency="usd"),
    lambda p: p["evidence"]["scenario"].update(required_terms=["COG", "COG"]),
    lambda p: p.update(resolution=None),                                      # calculations without resolution
    lambda p: p["resolution"].update(record_reference="row_9"),               # foreign record
    lambda p: p["resolution"]["results"][0]["dependencies"][0].update(evidence_ref="VAT"),
    lambda p: p["resolution"]["results"][0]["dependencies"][0]["operand"].update(
        value={"decimal": "9.99"}),                                            # operand diverges from evidence
    lambda p: p["calculations"]["calculations"][0].update(blocker="DEPENDENCIES_UNRESOLVED"),
    lambda p: p["calculations"]["calculations"][0].update(exact=None),
    lambda p: p["calculations"].update(decimal_precision=0),
    lambda p: p["calculations"]["calculations"].append(p["calculations"]["calculations"][0]),
])
def test_corrupt_or_incoherent_payload_is_rejected(mutate):
    corrupt(mutate)


def test_non_objects_are_rejected():
    for payload in (None, [], "text", 1):
        with pytest.raises(FinancialSerializationError):
            deserialize_financial_record(payload)


def test_serializer_rejects_incoherent_documents():
    doc = document()
    with pytest.raises(FinancialSerializationError):
        serialize_financial_record(FinancialRecordDocument(doc.evidence, calculations=doc.calculations))
    other = document(evidence(*complete().terms, required=tuple(T), context_requirements=("x",)))
    with pytest.raises(FinancialSerializationError):
        serialize_financial_record(FinancialRecordDocument(doc.evidence, None, other.resolution))


# -- Purity -------------------------------------------------------------------------

def test_serialization_is_deterministic_and_does_not_mutate():
    doc = document()
    before = copy.deepcopy(doc)
    assert serialize_financial_record(doc) == serialize_financial_record(doc)
    assert doc == before


def test_module_does_no_io_persistence_or_legacy_access():
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "dataclasses", "datetime", "decimal", "enum", "typing",
                       "juval.application.financial_calculation", "juval.domain.financial_dependencies",
                       "juval.domain.financial_evidence", "juval.domain.provenance"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"open", "pickle", "CostInputs", "FeeInputs", "compute_profitability"} & names
