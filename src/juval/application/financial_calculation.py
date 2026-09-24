"""Accredited financial calculation (ADR-047 §7, §16, §17; §22 step 5).

Takes a FinancialDependencyResolution and computes each §16 result whose
dependencies are resolved, every formula term is accounted for, and whose
mathematical preconditions hold. Blocked results carry the reason; nothing
falls back to CostInputs/FeeInputs, the legacy price or a default.

Arithmetic reuses the pure Decimal functions of processing/profitability.py
unchanged, so the expressions are exactly the existing ones:

  proceeds = P - (R + F + O)          C0 = sum of non-COG costs (+ rate * weight)
  C        = COG + C0
  PROFIT                = compute_profit(proceeds, C)
  ROI                   = compute_roi(profit, C)                    if C > 0
  MARGIN                = compute_margin(profit, P)                 if P > 0
  BREAK_EVEN_PRICE      = compute_break_even_price(C, F, O, r)      if 1 - r > 0
  MAX_COG_TARGET_PROFIT = compute_max_cog_for_target_profit(proceeds, C0, tp)
  MAX_COG_TARGET_ROI    = compute_max_cog_for_target_roi(proceeds, C0, tr) if 1 + tr > 0

A formula term contributes its operand, or the neutral element *only* when
its resolved exclusion says so (ADR-047 §7). A term outside the scenario's
declared universe is not a dependency for resolution (§8), but it has no
accredited neutral either, so it blocks the calculation instead of silently
counting as zero (§13).

Decimal policy: no rounding is introduced. Operations run in an explicit copy
of Python's default context (the one the legacy engine uses) and each result
records whether the Inexact signal was raised, so a rounded quotient is
visible instead of silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, Inexact, localcontext
from enum import Enum
from typing import Callable, Optional

from juval.domain.financial_dependencies import (
    DEPENDENCY_MATRIX,
    ExplicitInput,
    FinancialDependencyResolution,
    FinancialResult,
    ResultResolution,
)
from juval.domain.financial_evidence import RATIO_UNIT, FinancialTerm
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus
from juval.processing.profitability import (
    compute_break_even_price,
    compute_margin,
    compute_max_cog_for_target_profit,
    compute_max_cog_for_target_roi,
    compute_profit,
    compute_roi,
)

SOURCE = "adr047_financial_calculator"

#: Python's default decimal precision/rounding, pinned so a caller's global
#: context cannot silently change results. It is the legacy engine's effective
#: policy, not a new one; a fresh Context is built per call (no shared state).
DECIMAL_PRECISION = 28
DECIMAL_ROUNDING = ROUND_HALF_EVEN

_C0 = (
    FinancialTerm.VAT, FinancialTerm.INBOUND_SHIPPING, FinancialTerm.SHIPPING_PER_UNIT,
    FinancialTerm.SHIPPING_PER_POUND, FinancialTerm.PREP, FinancialTerm.LABELING,
    FinancialTerm.FRAGILE_PREP, FinancialTerm.STORAGE, FinancialTerm.INBOUND_PLACEMENT,
    FinancialTerm.TAXES, FinancialTerm.OTHER_COSTS,
)

EXPRESSIONS: dict[FinancialResult, str] = {
    FinancialResult.PROFIT: "P - (R + F + O) - (COG + C0)",
    FinancialResult.ROI: "profit / (COG + C0)",
    FinancialResult.MARGIN: "profit / P",
    FinancialResult.BREAK_EVEN_PRICE: "(COG + C0 + F + O) / (1 - r)",
    FinancialResult.MAX_COG_TARGET_PROFIT: "P - (R + F + O) - C0 - tp",
    FinancialResult.MAX_COG_TARGET_ROI: "(P - (R + F + O) - C0 * (1 + tr)) / (1 + tr)",
}


class CalculationBlocker(str, Enum):
    """Why a result was not calculated. A diagnostic, not a VerificationStatus."""

    DEPENDENCIES_UNRESOLVED = "DEPENDENCIES_UNRESOLVED"
    FORMULA_TERM_UNDECLARED = "FORMULA_TERM_UNDECLARED"
    MATH_PRECONDITION_FAILED = "MATH_PRECONDITION_FAILED"


@dataclass(frozen=True)
class PreconditionCheck:
    expression: str   # exactly the resolver's math_preconditions text
    operand: Decimal  # the evaluated left-hand side
    satisfied: bool


@dataclass(frozen=True)
class FinancialCalculation:
    """One result: a CALCULATED FieldValue, VERIFIED/INFERRED when computed or
    NOT_FOUND with the blocker as evidence when not (ADR-047 §14, §17: that
    NOT_FOUND describes the failed calculation, not a lookup).

    `resolution` keeps every original operand, applicability assertion,
    exclusion and FinancialTermEvidence. `exact` is False when the Decimal
    context had to round.
    """

    result: FinancialResult
    expression: str
    resolution: ResultResolution
    value: Optional[FieldValue] = None
    preconditions: tuple[PreconditionCheck, ...] = ()
    blocker: Optional[CalculationBlocker] = None
    undeclared_terms: tuple[FinancialTerm, ...] = ()
    exact: Optional[bool] = None


@dataclass(frozen=True)
class FinancialCalculationSet:
    """Results of one record. The decimal policy the calculation ran under is
    recorded with them so a serialized set says how its quotients were rounded."""

    execution_id: str
    record_reference: str
    calculations: tuple[FinancialCalculation, ...]
    decimal_precision: int = DECIMAL_PRECISION
    decimal_rounding: str = DECIMAL_ROUNDING

    def for_result(self, result: FinancialResult) -> FinancialCalculation:
        return next(item for item in self.calculations if item.result == result)


def calculate_financial_results(
    resolution: FinancialDependencyResolution,
    *,
    calculated_at: datetime,
    requested: Optional[frozenset[FinancialResult]] = None,
) -> FinancialCalculationSet:
    """Calculate the requested §16 results (all by default).

    A result not requested is structurally absent from the set, not a failed
    calculation. `calculated_at` is the calculation instant recorded as
    retrieved_at, never an observation time.
    """
    if not isinstance(resolution, FinancialDependencyResolution):
        raise ValueError("Explicit FinancialDependencyResolution required")
    if requested is not None and (not isinstance(requested, frozenset)
                                  or not all(isinstance(r, FinancialResult) for r in requested)):
        raise ValueError("requested must be a frozenset of FinancialResult")
    return FinancialCalculationSet(
        resolution.execution_id, resolution.record_reference,
        tuple(_calculate(item, calculated_at) for item in resolution.results
              if requested is None or item.result in requested),
    )


def _calculate(item: ResultResolution, calculated_at: datetime) -> FinancialCalculation:
    expression = EXPRESSIONS[item.result]
    provenance = dict(source=SOURCE, method=f"ADR-047 §16: {expression}", retrieved_at=calculated_at,
                      source_type=SourceType.CALCULATED,
                      source_reference=f"scenario={item.scenario.scenario_id}@{item.scenario.scenario_version}")

    def blocked(blocker: CalculationBlocker, detail: str, **extra) -> FinancialCalculation:
        value = FieldValue.not_found(evidence=f"{blocker.value}: {detail}", **provenance)
        return FinancialCalculation(item.result, expression, item, value=value, blocker=blocker, **extra)

    if not item.dependencies_resolved:
        return blocked(CalculationBlocker.DEPENDENCIES_UNRESOLVED,
                       ", ".join(f"{dep.dependency}={dep.blocker.value}" for dep in item.blockers))
    by_name = {dep.dependency: dep for dep in item.dependencies}
    undeclared = tuple(term for term in DEPENDENCY_MATRIX[item.result][0] if term.value not in by_name)
    if undeclared:
        return blocked(CalculationBlocker.FORMULA_TERM_UNDECLARED,
                       "no accredited operand or exclusion for " + ", ".join(t.value for t in undeclared),
                       undeclared_terms=undeclared)

    with localcontext(Context(prec=DECIMAL_PRECISION, rounding=DECIMAL_ROUNDING, flags=[])) as context:
        ops = _Operands(by_name)
        checks, compute = _PLANS[item.result](ops)
        if not all(check.satisfied for check in checks):
            return blocked(CalculationBlocker.MATH_PRECONDITION_FAILED,
                           ", ".join(f"{c.expression} is false ({c.operand})" for c in checks if not c.satisfied),
                           preconditions=checks)
        value = compute()
        exact = not context.flags[Inexact]

    unit = RATIO_UNIT if item.result in (FinancialResult.ROI, FinancialResult.MARGIN) else item.scenario.currency
    build = FieldValue.verified if item.dependency_status is VerificationStatus.VERIFIED else FieldValue.inferred
    return FinancialCalculation(item.result, expression, item, value=build(value, unit=unit, **provenance),
                                preconditions=checks, exact=exact)


class _Operands:
    """Operand values of one resolved result; an excluded term is the neutral 0."""

    def __init__(self, by_name: dict) -> None:
        self._by_name = by_name

    def get(self, name: str) -> Decimal:
        dep = self._by_name[name]
        return Decimal("0") if dep.excluded else dep.operand.value

    def term(self, term: FinancialTerm) -> Decimal:
        if term is FinancialTerm.SHIPPING_PER_POUND and not self._by_name[term.value].excluded:
            return self.get(term.value) * self.get(ExplicitInput.WEIGHT.value)
        return self.get(term.value)

    @property
    def fees(self) -> Decimal:
        return (self.term(FinancialTerm.REFERRAL_FEE) + self.term(FinancialTerm.FULFILLMENT_FEE)
                + self.term(FinancialTerm.OTHER_SELLING_FEES))

    @property
    def price(self) -> Decimal:
        return self.get(ExplicitInput.SELLING_PRICE.value)

    @property
    def c0(self) -> Decimal:
        return sum((self.term(term) for term in _C0), Decimal("0"))

    @property
    def total_cost(self) -> Decimal:
        return self.term(FinancialTerm.COG) + self.c0


_Plan = Callable[[_Operands], tuple[tuple[PreconditionCheck, ...], Callable[[], Decimal]]]


def _check(expression: str, operand: Decimal) -> tuple[PreconditionCheck, ...]:
    return (PreconditionCheck(expression, operand, operand > 0),)


def _profit(ops: _Operands) -> Decimal:
    return compute_profit(ops.price - ops.fees, ops.total_cost)


def _plan_profit(ops):
    return (), lambda: _profit(ops)


def _plan_roi(ops):
    return _check("C = COG + C0 > 0", ops.total_cost), lambda: compute_roi(_profit(ops), ops.total_cost)


def _plan_margin(ops):
    return _check("P > 0", ops.price), lambda: compute_margin(_profit(ops), ops.price)


def _plan_break_even(ops):
    rate = ops.term(FinancialTerm.REFERRAL_FEE_RATE)
    return _check("1 - r > 0", Decimal("1") - rate), lambda: compute_break_even_price(
        total_cost=ops.total_cost, fulfillment_fee=ops.term(FinancialTerm.FULFILLMENT_FEE),
        other_selling_fees=ops.term(FinancialTerm.OTHER_SELLING_FEES), referral_fee_rate=rate)


def _plan_max_cog_profit(ops):
    return (), lambda: compute_max_cog_for_target_profit(
        seller_proceeds=ops.price - ops.fees, landed_cost_excl_cog=ops.c0,
        target_profit=ops.get(ExplicitInput.TARGET_PROFIT.value))


def _plan_max_cog_roi(ops):
    target = ops.get(ExplicitInput.TARGET_ROI.value)
    return _check("1 + tr > 0", Decimal("1") + target), lambda: compute_max_cog_for_target_roi(
        seller_proceeds=ops.price - ops.fees, landed_cost_excl_cog=ops.c0, target_roi=target)


_PLANS: dict[FinancialResult, _Plan] = {
    FinancialResult.PROFIT: _plan_profit,
    FinancialResult.ROI: _plan_roi,
    FinancialResult.MARGIN: _plan_margin,
    FinancialResult.BREAK_EVEN_PRICE: _plan_break_even,
    FinancialResult.MAX_COG_TARGET_PROFIT: _plan_max_cog_profit,
    FinancialResult.MAX_COG_TARGET_ROI: _plan_max_cog_roi,
}
