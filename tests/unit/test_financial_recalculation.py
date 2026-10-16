"""Recalculation check of stored financial records (ADR-047 §19). Synthetic fixtures only;
stored documents go through real JSON before being checked."""
import ast
import copy
import json
import pathlib
from decimal import Decimal

import pytest

from juval.application import financial_recalculation as module
from juval.application.financial_recalculation import RecalculationCheck, check_recalculation
from juval.application.financial_serialization_v2 import (
    ImplementationIdentity, assess_reproducibility, deserialize_financial_record_v2, serialize_financial_record_v2,
)
from juval.domain.financial_dependencies import FinancialResult as R
from juval.domain.provenance import VerificationStatus as VS

from .test_financial_calculation import complete
from .test_financial_dependencies import INV, I, NF, T, fv, term
from .test_financial_serialization import document
from .test_financial_serialization_v2 import IDENTITY, v2, with_price


def stored(doc):
    """What a reader gets back from persistence: the canonical JSON text, deserialized."""
    return deserialize_financial_record_v2(json.loads(json.dumps(serialize_financial_record_v2(doc), sort_keys=True)))


def tampered(mutate, doc=None):
    payload = json.loads(json.dumps(serialize_financial_record_v2(doc or v2())))
    mutate(payload)
    return deserialize_financial_record_v2(payload)


def calc_payload(payload, result):
    return next(c for c in payload["calculations"]["calculations"] if c["result"] == result.value)


# -- Reproduced under the current code ---------------------------------------------

def test_stored_complete_record_is_recalculated_exactly():
    check = check_recalculation(stored(v2()))
    assert check == RecalculationCheck((), ())
    assert check.matches


@pytest.mark.parametrize("amount", [fv(None, status=NF), fv("twenty", status=INV), fv(Decimal("20.00"), "EUR")],
                         ids=["NOT_FOUND", "INVALID", "wrong-currency"])
def test_blocked_results_are_recalculated_as_blocked(amount):
    doc = stored(with_price(amount))
    profit = doc.document.calculations.for_result(R.PROFIT)
    assert profit.value.status is VS.NOT_FOUND and profit.blocker is not None   # nothing became a value
    assert check_recalculation(doc).matches


def test_inferred_evidence_is_recalculated_as_inferred():
    doc = stored(v2(document(complete(**{T.COG: term(T.COG, "4.50", status=I)}))))
    assert doc.document.calculations.for_result(R.PROFIT).value.status is VS.INFERRED
    assert check_recalculation(doc).matches


def test_unrequested_results_stay_absent_from_the_recalculation():
    doc = stored(v2(document(requested=frozenset({R.PROFIT, R.ROI}))))
    assert {c.result for c in doc.document.calculations.calculations} == {R.PROFIT, R.ROI}
    assert check_recalculation(doc).matches


def test_a_match_is_not_historical_reproduction():
    doc = stored(v2())
    assert check_recalculation(doc).matches
    assert assess_reproducibility(doc).historical_reproduction == (
        "the code and runtime a document names cannot be verified from the document",)


# -- Differences are reported, never repaired --------------------------------------

def test_a_stored_value_the_code_does_not_produce_is_reported():
    def mutate(payload):
        calc_payload(payload, R.PROFIT)["value"]["value"] = {"decimal": "9.31"}
    check = check_recalculation(tampered(mutate))
    assert check.differing == ("PROFIT",) and not check.matches


def test_a_stored_resolution_the_code_does_not_produce_is_reported():
    def mutate(payload):
        payload["resolution"]["results"][0]["math_preconditions"] = ["edited"]
    check = check_recalculation(tampered(mutate))
    assert check.refused == () and "resolution" in check.differing


def test_stored_exactness_and_precondition_operands_are_compared():
    def mutate(payload):
        roi = calc_payload(payload, R.ROI)
        roi["exact"] = not roi["exact"]
        roi["preconditions"][0]["operand"] = {"decimal": "5.31"}
    assert check_recalculation(tampered(mutate)).differing == ("ROI",)


# -- Refused, never approximated --------------------------------------------------

def test_v1_cannot_be_recalculated():
    check = check_recalculation(document())
    assert check.refused == ("format v1 does not record the explicit inputs as supplied",)
    assert not check.matches


def test_a_record_without_calculation_is_refused():
    assert check_recalculation(stored(v2(document(calculate=False)))).refused == ("no calculation is recorded",)
    assert "no calculation is recorded" in check_recalculation(
        stored(v2(document(requested=frozenset())))).refused


def test_a_different_implementation_table_is_refused():
    stale = ImplementationIdentity(IDENTITY.calculator, "0" * 64, "1" * 64, IDENTITY.application_version,
                                   IDENTITY.code_revision)
    assert check_recalculation(stored(v2(identity=stale))).refused == (
        "expression table differs from the current code", "dependency matrix differs from the current code")


def test_a_different_decimal_policy_is_refused():
    def mutate(payload):
        payload["calculations"]["decimal_precision"] = 30
    assert check_recalculation(tampered(mutate)).refused == ("decimal policy differs from the current calculator",)


def test_calculations_from_different_instants_are_refused():
    def mutate(payload):
        calc_payload(payload, R.ROI)["value"]["provenance"]["retrieved_at"] = "2026-03-02T00:00:00+00:00"
    assert check_recalculation(tampered(mutate)).refused == ("calculations do not share one calculation instant",)


def test_anything_but_a_financial_document_is_rejected():
    with pytest.raises(ValueError):
        check_recalculation(serialize_financial_record_v2(v2()))


# -- Purity -------------------------------------------------------------------------

def test_check_is_pure_and_reuses_the_existing_resolver_and_calculator():
    doc = stored(v2())
    before = copy.deepcopy(doc)
    assert check_recalculation(doc) == check_recalculation(doc)
    assert doc == before
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules == {"__future__", "dataclasses", "typing", "juval.application.financial_calculation",
                       "juval.application.financial_serialization", "juval.application.financial_serialization_v2",
                       "juval.domain.financial_dependencies"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"open", "sqlite3", "CostInputs", "FeeInputs", "compute_profit", "compute_roi"} & names
