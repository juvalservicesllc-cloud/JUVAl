"""Synthetic fixtures only: no supplier, fee schedule, price or commercial calibration."""
import ast
import copy
import pathlib
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from juval.domain import financial_dependencies as module
from juval.domain.financial_dependencies import (
    DEPENDENCY_MATRIX, ExplicitInput, FinancialResult, ResolutionBlocker, resolve_financial_dependencies,
)
from juval.domain.financial_evidence import (
    Applicability, EffectiveContext, FinancialEvidenceSet, FinancialScenario, FinancialTerm,
    FinancialTermEvidence,
)
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus

T = FinancialTerm
R = FinancialResult
NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)
CONTEXT = EffectiveContext(effective_at=NOW - timedelta(days=30), basis_definition="synthetic per-unit basis")
V, I, NF, INV = (VerificationStatus.VERIFIED, VerificationStatus.INFERRED,
                 VerificationStatus.NOT_FOUND, VerificationStatus.INVALID)


def fv(value, unit=None, status=V):
    common = dict(source="synthetic.xlsx", method="direct_read", retrieved_at=NOW,
                  source_type=SourceType.SUPPLIER_FILE, source_reference="row=2")
    if status is NF:
        return FieldValue.not_found(**common)
    if status is INV:
        return FieldValue.invalid(value, **common)
    return (FieldValue.verified if status is V else FieldValue.inferred)(value, unit=unit, **common)


def term(kind, amount="1.00", *, applies=True, applies_status=V, unit="USD", status=V, **extra):
    if kind is T.REFERRAL_FEE_RATE and unit == "USD":
        unit = "ratio"
    if kind is T.SHIPPING_PER_POUND and unit == "USD":
        unit = "USD/lb"
    value = None if amount is None else fv(Decimal(amount) if status in (V, I) else amount, unit, status)
    applicability = Applicability(fv(applies if applies_status in (V, I) else "?", status=applies_status),
                                  "synthetic declaration")
    return FinancialTermEvidence(kind, applicability, CONTEXT, value, **extra)


def evidence(*terms, required=(T.COG, T.REFERRAL_FEE, T.FULFILLMENT_FEE, T.REFERRAL_FEE_RATE),
             context_requirements=()):
    scenario = FinancialScenario("s", "v1", "USD", "one sellable unit", "synthetic-policy@v1",
                                 frozenset(required), context_requirements)
    return FinancialEvidenceSet(scenario, "run-1", "row_2:SKU", terms)


FULL = (term(T.COG, "4.50"), term(T.REFERRAL_FEE, "3.00"), term(T.FULFILLMENT_FEE, "3.20"),
        term(T.REFERRAL_FEE_RATE, "0.15"))
PRICE = fv(Decimal("19.99"), "USD")
TP, TR = fv(Decimal("3.00"), "USD"), fv(Decimal("0.30"), "ratio")


def resolve(ev, **inputs):
    inputs.setdefault("selling_price", PRICE)
    inputs.setdefault("target_profit", TP)
    inputs.setdefault("target_roi", TR)
    return resolve_financial_dependencies(ev, **inputs)


def dep(resolution, result, name):
    return next(d for d in resolution.for_result(result).dependencies if d.dependency == name)


# -- Matrix is ADR-047 §16 -------------------------------------------------

def test_matrix_matches_adr_047_section_16():
    names = lambda r: {t for t in DEPENDENCY_MATRIX[r][0]}
    assert set(DEPENDENCY_MATRIX) == set(FinancialResult)
    assert names(R.PROFIT) == names(R.ROI) == names(R.MARGIN) == set(T) - {T.REFERRAL_FEE_RATE}
    assert names(R.BREAK_EVEN_PRICE) == set(T) - {T.REFERRAL_FEE}
    assert names(R.MAX_COG_TARGET_PROFIT) == names(R.MAX_COG_TARGET_ROI) == set(T) - {T.COG, T.REFERRAL_FEE_RATE}
    assert DEPENDENCY_MATRIX[R.BREAK_EVEN_PRICE][1] == ()  # P is not a break-even operand
    assert DEPENDENCY_MATRIX[R.MAX_COG_TARGET_PROFIT][1] == (ExplicitInput.SELLING_PRICE, ExplicitInput.TARGET_PROFIT)
    assert DEPENDENCY_MATRIX[R.MAX_COG_TARGET_ROI][1] == (ExplicitInput.SELLING_PRICE, ExplicitInput.TARGET_ROI)


# -- Complete and partial ----------------------------------------------------

def test_complete_supplier_evidence_resolves_every_result_as_verified():
    resolution = resolve(evidence(*FULL))
    assert (resolution.execution_id, resolution.record_reference) == ("run-1", "row_2:SKU")
    for item in resolution.results:
        assert item.dependencies_resolved and item.dependency_status is V
        assert item.scenario.scenario_id == "s"
    profit = resolution.for_result(R.PROFIT)
    assert [d.dependency for d in profit.dependencies] == ["COG", "REFERRAL_FEE", "FULFILLMENT_FEE", "SELLING_PRICE"]
    cog = dep(resolution, R.PROFIT, "COG")
    assert cog.operand is FULL[0].amount  # original object: value, unit and provenance untouched
    assert cog.operand.provenance.source_type is SourceType.SUPPLIER_FILE
    assert resolution.for_result(R.ROI).math_preconditions == ("C = COG + C0 > 0",)


def test_partial_evidence_blocks_only_the_results_that_need_the_gap():
    resolution = resolve(evidence(term(T.COG, "4.50"), term(T.FULFILLMENT_FEE, "3.20"),
                                  term(T.REFERRAL_FEE_RATE, "0.15")))
    assert resolution.for_result(R.BREAK_EVEN_PRICE).dependencies_resolved  # R is not needed
    for result in (R.PROFIT, R.ROI, R.MARGIN, R.MAX_COG_TARGET_PROFIT, R.MAX_COG_TARGET_ROI):
        [blocked] = resolution.for_result(result).blockers
        assert (blocked.dependency, blocked.blocker) == ("REFERRAL_FEE", ResolutionBlocker.STRUCTURALLY_ABSENT)
        assert resolution.for_result(result).dependency_status is None


def test_max_cog_does_not_depend_on_cog_and_profit_does_not_depend_on_the_rate():
    ev = evidence(term(T.REFERRAL_FEE, "3.00"), term(T.FULFILLMENT_FEE, "3.20"),
                  required=(T.REFERRAL_FEE, T.FULFILLMENT_FEE))
    resolution = resolve(ev)
    assert resolution.for_result(R.MAX_COG_TARGET_PROFIT).dependencies_resolved
    # Neither COG nor the rate is required or represented: outside this scenario's universe.
    profit_deps = {d.dependency for d in resolution.for_result(R.PROFIT).dependencies}
    assert resolution.for_result(R.PROFIT).dependencies_resolved
    assert not {"COG", "REFERRAL_FEE_RATE"} & profit_deps


def test_break_even_is_resolvable_without_price_while_profit_is_blocked():
    resolution = resolve(evidence(*FULL), selling_price=None)
    assert resolution.for_result(R.BREAK_EVEN_PRICE).dependencies_resolved
    blocked = resolution.for_result(R.PROFIT).blockers
    assert [(b.dependency, b.blocker) for b in blocked] == [("SELLING_PRICE", ResolutionBlocker.STRUCTURALLY_ABSENT)]


# -- States ------------------------------------------------------------------

@pytest.mark.parametrize("status,blocker", [(NF, ResolutionBlocker.VALUE_NOT_FOUND),
                                            (INV, ResolutionBlocker.VALUE_INVALID)])
def test_not_found_and_invalid_amounts_block_and_are_never_zero(status, blocker):
    resolution = resolve(evidence(term(T.COG, "x", status=status), *FULL[1:]))
    cog = dep(resolution, R.PROFIT, "COG")
    assert cog.blocker is blocker and cog.operand is None
    assert resolution.for_result(R.MAX_COG_TARGET_PROFIT).dependencies_resolved  # COG not needed there


def test_amount_absent_under_resolved_applicability_blocks_as_structural_absence():
    cog = dep(resolve(evidence(term(T.COG, None), *FULL[1:])), R.PROFIT, "COG")
    assert cog.blocker is ResolutionBlocker.STRUCTURALLY_ABSENT and cog.detail == "applies but no amount is represented"


def test_inferred_operand_is_usable_and_keeps_the_result_inferred():
    resolution = resolve(evidence(term(T.COG, "4.50", status=I), *FULL[1:]))
    assert dep(resolution, R.PROFIT, "COG").operand.status is I
    assert resolution.for_result(R.PROFIT).dependency_status is I
    assert resolution.for_result(R.MAX_COG_TARGET_PROFIT).dependency_status is V  # COG not a dependency


def test_explicit_zero_is_an_operand_not_an_exclusion():
    fee = dep(resolve(evidence(*FULL[:2], term(T.FULFILLMENT_FEE, "0"), FULL[3])), R.PROFIT, "FULFILLMENT_FEE")
    assert fee.operand.value == Decimal("0") and not fee.excluded and fee.blocker is None


def test_accredited_exclusion_has_no_operand_and_keeps_its_dependency():
    resolution = resolve(evidence(*FULL[:2], term(T.FULFILLMENT_FEE, None, applies=False), FULL[3]))
    fee = dep(resolution, R.PROFIT, "FULFILLMENT_FEE")
    assert fee.excluded and fee.operand is None and fee.applicability.status is V
    assert resolution.for_result(R.PROFIT).dependency_status is V


def test_inferred_exclusion_keeps_dependent_results_inferred():
    resolution = resolve(evidence(*FULL[:2], term(T.FULFILLMENT_FEE, None, applies=False, applies_status=I),
                                  FULL[3]))
    assert dep(resolution, R.PROFIT, "FULFILLMENT_FEE").excluded
    for result in resolution.results:
        assert result.dependency_status is I


@pytest.mark.parametrize("applies_status", [NF, INV])
def test_unresolved_applicability_blocks_even_with_a_usable_amount(applies_status):
    fee = dep(resolve(evidence(*FULL[:2], term(T.FULFILLMENT_FEE, "3.20", applies_status=applies_status),
                               FULL[3])), R.PROFIT, "FULFILLMENT_FEE")
    assert fee.blocker is ResolutionBlocker.APPLICABILITY_UNRESOLVED and fee.operand is None


def test_represented_optional_term_is_a_dependency_and_absent_optional_one_is_not():
    resolution = resolve(evidence(*FULL, term(T.PREP, "0.40", applies_status=NF)))
    prep = dep(resolution, R.PROFIT, "PREP")
    assert prep.blocker is ResolutionBlocker.APPLICABILITY_UNRESOLVED
    assert "VAT" not in {d.dependency for d in resolution.for_result(R.PROFIT).dependencies}


# -- Currency, units, context, allocation ------------------------------------

@pytest.mark.parametrize("price,blocker", [
    (fv(Decimal("19.99")), ResolutionBlocker.CURRENCY_UNDECLARED),
    (fv(Decimal("19.99"), "EUR"), ResolutionBlocker.CURRENCY_INCOMPATIBLE),
    (fv(None, status=NF), ResolutionBlocker.VALUE_NOT_FOUND),
    (fv("abc", status=INV), ResolutionBlocker.VALUE_INVALID),
    (fv(Decimal("NaN"), "USD"), ResolutionBlocker.VALUE_INVALID),
    (fv(Decimal("Infinity"), "USD"), ResolutionBlocker.VALUE_INVALID),
])
def test_price_needs_a_finite_value_in_the_scenario_currency(price, blocker):
    assert dep(resolve(evidence(*FULL), selling_price=price), R.PROFIT, "SELLING_PRICE").blocker is blocker


def test_mismatched_term_currency_cannot_even_enter_the_set():
    with pytest.raises(ValueError, match="incompatible with scenario currency"):
        evidence(term(T.COG, "4.50", unit="EUR"))


def test_per_pound_rate_needs_weight_in_pounds():
    ev = evidence(*FULL, term(T.SHIPPING_PER_POUND, "0.50"))
    missing = dep(resolve(ev), R.PROFIT, "WEIGHT")
    assert missing.blocker is ResolutionBlocker.STRUCTURALLY_ABSENT
    kilograms = dep(resolve(ev, weight=fv(Decimal("2"), "kg")), R.PROFIT, "WEIGHT")
    assert kilograms.blocker is ResolutionBlocker.UNIT_INCOMPATIBLE
    pounds = resolve(ev, weight=fv(Decimal("2"), "lb"))
    assert pounds.for_result(R.PROFIT).dependencies_resolved
    assert dep(pounds, R.PROFIT, "WEIGHT").operand.unit == "lb"


def test_ratio_target_keeps_ratio_unit_and_rate_stays_a_ratio():
    resolution = resolve(evidence(*FULL), target_roi=fv(Decimal("30"), "%"))
    assert dep(resolution, R.MAX_COG_TARGET_ROI, "TARGET_ROI").blocker is ResolutionBlocker.UNIT_INCOMPATIBLE
    assert dep(resolution, R.BREAK_EVEN_PRICE, "REFERRAL_FEE_RATE").operand.unit == "ratio"
    assert dep(resolution, R.MAX_COG_TARGET_PROFIT, "TARGET_PROFIT").operand is TP


def test_out_of_range_rate_is_invalid_and_blocks_break_even():
    rate = dep(resolve(evidence(*FULL[:3], term(T.REFERRAL_FEE_RATE, "1.5", status=INV))),
               R.BREAK_EVEN_PRICE, "REFERRAL_FEE_RATE")
    assert rate.blocker is ResolutionBlocker.VALUE_INVALID
    with pytest.raises(ValueError):
        term(T.REFERRAL_FEE_RATE, "1.5")  # never usable


def test_allocation_required_and_absent_is_a_contract_error_while_explicit_allocation_resolves():
    with pytest.raises(ValueError, match="allocation_method"):
        term(T.STORAGE, "0.20")
    storage = term(T.STORAGE, "0.20", allocation_method="monthly storage split over units stored")
    assert dep(resolve(evidence(*FULL, storage)), R.PROFIT, "STORAGE").operand is storage.amount
    assert term(T.COG, "4.50").allocation_method is None  # COG per sellable unit needs none


def test_unresolved_context_requirement_blocks_every_result():
    resolution = resolve(evidence(*FULL, context_requirements=("fee schedule window",)))
    for item in resolution.results:
        [blocked] = item.blockers
        assert blocked.blocker is ResolutionBlocker.CONTEXT_REQUIREMENT_UNRESOLVED


# -- Purity and scope ----------------------------------------------------------

def test_supplier_verified_is_not_promoted_or_relabelled():
    operand = dep(resolve(evidence(*FULL)), R.PROFIT, "COG").operand
    assert operand.provenance.source_type is SourceType.SUPPLIER_FILE
    assert operand.provenance.source_type is not SourceType.OFFICIAL_API


def test_resolution_is_deterministic_and_does_not_mutate_the_set():
    ev = evidence(*FULL)
    before = copy.deepcopy(ev)
    assert resolve(ev) == resolve(ev)
    assert ev == before
    with pytest.raises(FrozenInstanceError):
        resolve(ev).results = ()


def test_bare_values_are_contract_errors_not_ordinary_absence():
    with pytest.raises(ValueError):
        resolve_financial_dependencies(evidence(*FULL), selling_price=Decimal("19.99"))
    with pytest.raises(ValueError):
        resolve_financial_dependencies("not a set")


def test_resolver_depends_only_on_domain_evidence_contracts():
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported == {"__future__", "dataclasses", "decimal", "enum", "typing",
                        "financial_evidence", "provenance", "units"}
    assert not {"CostInputs", "FeeInputs", "ProfitabilityResult", "PriceObservation"} & set(vars(module))
