"""Synthetic fixtures only: no supplier, fee schedule, price or commercial calibration."""
import ast
import copy
import pathlib
from decimal import Decimal, getcontext, localcontext

import pytest

from juval.application import financial_calculation as module
from juval.application.financial_calculation import (
    EXPRESSIONS, CalculationBlocker as B, calculate_financial_results,
)
from juval.domain.costs import CostInputs, FeeInputs
from juval.domain.financial_dependencies import DEPENDENCY_MATRIX, FinancialResult, resolve_financial_dependencies
from juval.domain.financial_evidence import FinancialTerm
from juval.domain.provenance import SourceType
from juval.processing.profitability import compute_profitability

from .test_financial_dependencies import INV, I, NF, NOW, T, V, evidence, fv, term

R = FinancialResult
PRICE, TP, TR = fv(Decimal("20.00"), "USD"), fv(Decimal("3"), "USD"), fv(Decimal("0.30"), "ratio")
SHIPPING = term(T.SHIPPING_PER_UNIT, "0.80", allocation_method="carton freight split per unit")
DECLARED = {T.COG: term(T.COG, "4.50"), T.REFERRAL_FEE: term(T.REFERRAL_FEE, "3.00"),
            T.FULFILLMENT_FEE: term(T.FULFILLMENT_FEE, "3.20"), T.REFERRAL_FEE_RATE: term(T.REFERRAL_FEE_RATE, "0.15"),
            T.SHIPPING_PER_UNIT: SHIPPING}


def complete(**overrides):
    """Every term declared: the given amounts, all others explicitly excluded."""
    items = {t: term(t, None, applies=False) for t in T}
    items.update(DECLARED)
    items.update(overrides)
    return evidence(*(item for item in items.values() if item is not None), required=tuple(T))


def calc(ev=None, **inputs):
    inputs = {"selling_price": PRICE, "target_profit": TP, "target_roi": TR, **inputs}
    return calculate_financial_results(resolve_financial_dependencies(ev or complete(), **inputs), calculated_at=NOW)


def value(result, which):
    return result.for_result(which).value.value


# -- Every result, exact existing expressions ---------------------------------

def test_all_six_results_are_calculated_with_the_existing_expressions():
    result = calc()
    assert value(result, R.PROFIT) == Decimal("8.50")                     # 20 - 6.20 - 5.30
    assert value(result, R.ROI) == Decimal("8.50") / Decimal("5.30")
    assert value(result, R.MARGIN) == Decimal("0.425")
    assert value(result, R.BREAK_EVEN_PRICE) == Decimal("10")             # (5.30 + 3.20) / 0.85
    assert value(result, R.MAX_COG_TARGET_PROFIT) == Decimal("10.00")     # 13.80 - 0.80 - 3
    assert value(result, R.MAX_COG_TARGET_ROI) == (Decimal("13.80") - Decimal("0.80") * Decimal("1.30")) / Decimal("1.30")
    for item in result.calculations:
        assert item.blocker is None and item.expression == EXPRESSIONS[item.result]


def test_values_match_the_legacy_engine_for_equivalent_operands():
    legacy = compute_profitability(
        selling_price=PRICE, costs=CostInputs(cog=Decimal("4.50"), shipping_per_unit=Decimal("0.80")),
        fees=FeeInputs(referral_fee=Decimal("3.00"), referral_fee_rate=Decimal("0.15"),
                       fulfillment_fee=Decimal("3.20")),
        target_profit=Decimal("3"), target_roi=Decimal("0.30"), now=NOW)
    result = calc()
    assert value(result, R.PROFIT) == legacy.profit.value
    assert value(result, R.ROI) == legacy.roi.value
    assert value(result, R.MARGIN) == legacy.margin.value
    assert value(result, R.BREAK_EVEN_PRICE) == legacy.break_even_price.value
    assert value(result, R.MAX_COG_TARGET_PROFIT) == legacy.max_cog_target_profit.value
    assert value(result, R.MAX_COG_TARGET_ROI) == legacy.max_cog_target_roi.value


def test_units_currency_and_calculated_provenance():
    result = calc()
    for which in (R.PROFIT, R.BREAK_EVEN_PRICE, R.MAX_COG_TARGET_PROFIT, R.MAX_COG_TARGET_ROI):
        assert result.for_result(which).value.unit == "USD"
    for which in (R.ROI, R.MARGIN):
        assert result.for_result(which).value.unit == "ratio"
    profit = result.for_result(R.PROFIT).value
    assert profit.provenance.source_type is SourceType.CALCULATED   # a calculation, not an observation
    assert profit.provenance.retrieved_at == NOW
    assert profit.provenance.source_reference == "scenario=s@v1"
    assert "P - (R + F + O)" in profit.provenance.method
    cog = next(d for d in result.for_result(R.PROFIT).resolution.dependencies if d.dependency == "COG")
    assert cog.operand is DECLARED[T.COG].amount and cog.operand.provenance.source_type is SourceType.SUPPLIER_FILE


def test_preconditions_are_exactly_the_resolver_ones():
    result = calc()
    for item in result.calculations:
        assert tuple(c.expression for c in item.preconditions) == DEPENDENCY_MATRIX[item.result][2]
        assert all(c.satisfied for c in item.preconditions)
    assert result.for_result(R.ROI).preconditions[0].operand == Decimal("5.30")


# -- Precision --------------------------------------------------------------

def test_decimal_precision_is_pinned_and_rounding_is_reported():
    result = calc()
    assert result.for_result(R.PROFIT).exact and result.for_result(R.MARGIN).exact
    assert result.for_result(R.ROI).exact is False  # 8.50 / 5.30 does not terminate
    with localcontext() as ctx:
        ctx.prec = 5
        assert calc() == result                       # caller's context cannot change results
    assert getcontext().prec == 28


# -- Blocking ------------------------------------------------------------------

@pytest.mark.parametrize("override,blocked", [
    ({T.REFERRAL_FEE: None}, {R.PROFIT, R.ROI, R.MARGIN, R.MAX_COG_TARGET_PROFIT, R.MAX_COG_TARGET_ROI}),
    ({T.COG: term(T.COG, "x", status=NF)}, {R.PROFIT, R.ROI, R.MARGIN, R.BREAK_EVEN_PRICE}),
    ({T.COG: term(T.COG, "x", status=INV)}, {R.PROFIT, R.ROI, R.MARGIN, R.BREAK_EVEN_PRICE}),
    ({T.FULFILLMENT_FEE: term(T.FULFILLMENT_FEE, "3.20", applies_status=NF)}, set(R)),
    ({T.REFERRAL_FEE_RATE: term(T.REFERRAL_FEE_RATE, "x", status=INV)}, {R.BREAK_EVEN_PRICE}),
])
def test_each_result_is_blocked_only_by_its_own_dependencies(override, blocked):
    result = calc(complete(**{t.name: v for t, v in override.items()}))
    for item in result.calculations:
        assert (item.blocker is not None) == (item.result in blocked), item.result
        if item.result in blocked:
            assert item.value.status is NF and item.value.value is None and item.blocker is B.DEPENDENCIES_UNRESOLVED


def test_absent_required_term_blocks_and_undeclared_formula_term_is_not_zero():
    # Required but absent -> the resolver already blocks.
    assert calc(complete(REFERRAL_FEE=None)).for_result(R.PROFIT).blocker is B.DEPENDENCIES_UNRESOLVED
    # Neither required nor represented: not a resolver dependency, yet no accredited neutral exists.
    sparse = evidence(*DECLARED.values(), required=(T.COG,))
    item = calc(sparse).for_result(R.PROFIT)
    assert item.blocker is B.FORMULA_TERM_UNDECLARED and item.value.status is NF and item.value.value is None
    assert T.VAT in item.undeclared_terms and T.OTHER_SELLING_FEES in item.undeclared_terms


def test_price_is_not_needed_for_break_even():
    result = calc(selling_price=None)
    assert result.for_result(R.BREAK_EVEN_PRICE).value.value == Decimal("10")
    assert result.for_result(R.PROFIT).blocker is B.DEPENDENCIES_UNRESOLVED


def test_cog_is_not_needed_for_max_cog():
    result = calc(complete(COG=term(T.COG, "x", status=NF)))
    assert value(result, R.MAX_COG_TARGET_PROFIT) == Decimal("10.00")
    assert result.for_result(R.PROFIT).blocker is B.DEPENDENCIES_UNRESOLVED


def test_referral_fee_and_rate_are_never_derived_from_each_other():
    no_rate = calc(complete(REFERRAL_FEE_RATE=None))
    assert no_rate.for_result(R.BREAK_EVEN_PRICE).blocker is B.DEPENDENCIES_UNRESOLVED
    assert value(no_rate, R.PROFIT) == Decimal("8.50")        # profit uses R, not r
    no_fee = calc(complete(REFERRAL_FEE=None))
    assert no_fee.for_result(R.PROFIT).blocker is B.DEPENDENCIES_UNRESOLVED
    assert value(no_fee, R.BREAK_EVEN_PRICE) == Decimal("10")  # break-even uses r, not R


# -- Mathematical preconditions -------------------------------------------------

def test_roi_with_zero_total_cost_is_blocked_not_zero():
    result = calc(complete(COG=term(T.COG, "0"), SHIPPING_PER_UNIT=term(T.SHIPPING_PER_UNIT, None, applies=False)))
    roi = result.for_result(R.ROI)
    assert roi.blocker is B.MATH_PRECONDITION_FAILED and roi.value.status is NF
    assert (roi.preconditions[0].operand, roi.preconditions[0].satisfied) == (Decimal("0"), False)
    assert value(result, R.PROFIT) == Decimal("13.80")  # explicit zero COG is an operand


def test_margin_with_zero_price_is_blocked():
    result = calc(selling_price=fv(Decimal("0"), "USD"))
    assert result.for_result(R.MARGIN).blocker is B.MATH_PRECONDITION_FAILED
    assert value(result, R.PROFIT) == Decimal("-11.50")  # a negative profit is a valid result


def test_break_even_denominator_cannot_reach_zero_through_evidence():
    # r = 1 is outside the ratio domain: it can only be INVALID evidence, which blocks upstream.
    with pytest.raises(ValueError):
        term(T.REFERRAL_FEE_RATE, "1")
    item = calc(complete(REFERRAL_FEE_RATE=term(T.REFERRAL_FEE_RATE, "1", status=INV))).for_result(R.BREAK_EVEN_PRICE)
    assert item.blocker is B.DEPENDENCIES_UNRESOLVED


@pytest.mark.parametrize("target", ["-1", "-1.5"])
def test_max_cog_roi_with_zero_or_negative_denominator_is_blocked(target):
    item = calc(target_roi=fv(Decimal(target), "ratio")).for_result(R.MAX_COG_TARGET_ROI)
    assert item.blocker is B.MATH_PRECONDITION_FAILED and item.value.status is NF and item.value.value is None
    assert item.preconditions[0].operand == Decimal("1") + Decimal(target)


# -- States, exclusions, currency, units, context ---------------------------------

def test_inferred_dependency_makes_the_result_inferred_never_verified():
    result = calc(complete(COG=term(T.COG, "4.50", status=I)))
    assert result.for_result(R.PROFIT).value.status is I
    assert result.for_result(R.MAX_COG_TARGET_PROFIT).value.status is V  # COG not a dependency
    inferred_exclusion = calc(complete(OTHER_SELLING_FEES=term(T.OTHER_SELLING_FEES, None, applies=False,
                                                              applies_status=I)))
    assert all(item.value.status is I for item in inferred_exclusion.calculations)


def test_exclusion_is_neutral_and_stays_a_recorded_dependency():
    item = calc().for_result(R.PROFIT)
    other = next(d for d in item.resolution.dependencies if d.dependency == "OTHER_SELLING_FEES")
    assert other.excluded and other.operand is None and other.applicability.status is V


def test_explicit_zero_fee_is_an_operand():
    result = calc(complete(FULFILLMENT_FEE=term(T.FULFILLMENT_FEE, "0")))
    fee = next(d for d in result.for_result(R.PROFIT).resolution.dependencies if d.dependency == "FULFILLMENT_FEE")
    assert fee.operand.value == Decimal("0") and not fee.excluded
    assert value(result, R.PROFIT) == Decimal("11.70")


@pytest.mark.parametrize("inputs", [
    {"selling_price": fv(Decimal("20.00"), "EUR")}, {"selling_price": fv(Decimal("20.00"))},
    {"target_profit": fv(Decimal("3"), "EUR")},
])
def test_incompatible_or_undeclared_currency_blocks(inputs):
    result = calc(**inputs)
    assert any(item.blocker is B.DEPENDENCIES_UNRESOLVED for item in result.calculations)
    assert result.for_result(R.BREAK_EVEN_PRICE).value.status is V


def test_per_pound_rate_uses_weight_in_pounds_only():
    per_lb = term(T.SHIPPING_PER_POUND, "0.50")
    kg = calc(complete(SHIPPING_PER_POUND=per_lb), weight=fv(Decimal("2"), "kg"))
    assert kg.for_result(R.PROFIT).blocker is B.DEPENDENCIES_UNRESOLVED
    lb = calc(complete(SHIPPING_PER_POUND=per_lb), weight=fv(Decimal("2"), "lb"))
    assert value(lb, R.PROFIT) == Decimal("7.50")  # 0.50 USD/lb * 2 lb added to C0


def test_ratio_target_in_percent_is_not_converted():
    item = calc(target_roi=fv(Decimal("30"), "%")).for_result(R.MAX_COG_TARGET_ROI)
    assert item.blocker is B.DEPENDENCIES_UNRESOLVED


def test_unresolved_context_requirement_blocks_every_result():
    ev = complete()
    constrained = evidence(*ev.terms, required=tuple(T), context_requirements=("fee schedule window",))
    assert all(item.blocker is B.DEPENDENCIES_UNRESOLVED for item in calc(constrained).calculations)


# -- Purity -----------------------------------------------------------------------

def test_calculation_is_deterministic_and_mutates_nothing():
    ev = complete()
    before = copy.deepcopy(ev)
    assert calc(ev) == calc(ev)
    assert ev == before
    with pytest.raises(ValueError):
        calculate_financial_results("not a resolution", calculated_at=NOW)


def test_module_has_no_legacy_operands_persistence_or_mutable_globals():
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not {m for m in modules if m and any(k in m for k in ("costs", "persistence", "interfaces", "logging",
                                                                    "record_snapshot", "decision", "importer"))}
    assert not {"CostInputs", "FeeInputs", "compute_profitability", "ProfitabilityResult"} & set(vars(module))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            assert target.id.isupper() or target.id.startswith("_"), target.id


def test_blocked_result_is_a_calculated_not_found_with_its_diagnostic():
    item = calc(complete(REFERRAL_FEE=None)).for_result(R.PROFIT)
    assert item.value.status is NF and item.value.provenance.source_type is SourceType.CALCULATED
    assert item.value.provenance.evidence == "DEPENDENCIES_UNRESOLVED: REFERRAL_FEE=STRUCTURALLY_ABSENT"
    roi = calc(complete(COG=term(T.COG, "0"), SHIPPING_PER_UNIT=term(T.SHIPPING_PER_UNIT, None, applies=False)))
    assert roi.for_result(R.ROI).value.provenance.evidence == \
        "MATH_PRECONDITION_FAILED: C = COG + C0 > 0 is false (0)"


def test_unrequested_results_are_absent_not_failed():
    result = calculate_financial_results(
        resolve_financial_dependencies(complete(), selling_price=PRICE),
        calculated_at=NOW, requested=frozenset({R.PROFIT, R.BREAK_EVEN_PRICE}))
    assert [item.result for item in result.calculations] == [R.PROFIT, R.BREAK_EVEN_PRICE]
    with pytest.raises(ValueError):
        calculate_financial_results(resolve_financial_dependencies(complete()), calculated_at=NOW,
                                    requested={R.PROFIT})


def test_allocation_and_context_stay_reachable_from_the_result():
    item = calc().for_result(R.PROFIT)
    shipping = next(d for d in item.resolution.dependencies if d.dependency == "SHIPPING_PER_UNIT")
    assert shipping.evidence is SHIPPING
    assert shipping.evidence.allocation_method == "carton freight split per unit"
    assert shipping.evidence.context.basis_definition == "synthetic per-unit basis"
