"""Per-result financial dependency resolution (ADR-047 §16, §17).

Pure resolution of which evidence each existing financial result depends on,
which of it is usable and why the rest blocks the result. Nothing is computed:
no profit, ROI, margin, break-even or max-COG value, no sum of costs, and no
change to ProfitabilityResult, CostInputs/FeeInputs or any decision.

The matrix is ADR-047 §16, verbatim. With P price, R referral fee, F
fulfillment, O other selling fees, r referral rate, C0 costs other than COG,
tp/tr the profit/ROI targets:

  PROFIT, ROI, MARGIN     P, R, F, O, COG, C0
  BREAK_EVEN_PRICE        COG, C0, F, O, r          (not P, not R)
  MAX_COG_TARGET_PROFIT   P, R, F, O, C0, tp        (not COG)
  MAX_COG_TARGET_ROI      P, R, F, O, C0, tr        (not COG)

Scope of a term: a formula term is a dependency when the scenario requires it
or the evidence set represents it. A required term with no representation
blocks (ADR-047 §8: absence never excludes); a term the scenario neither
requires nor represents is outside that scenario's declared universe.

Resolution outcomes are reported as ResolutionBlocker reasons, never as new
VerificationStatus members. Mathematical-domain preconditions (C > 0, P > 0,
1 + tr > 0) need the calculation itself and are listed, not evaluated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from .financial_evidence import (
    RATIO_UNIT,
    FinancialEvidenceSet,
    FinancialScenario,
    FinancialTerm,
    FinancialTermEvidence,
)
from .provenance import FieldValue, VerificationStatus, combine_verification_status
from .units import CANONICAL_WEIGHT_UNIT


class FinancialResult(str, Enum):
    """The existing results of ADR-047 §16; no result is added by analogy."""

    PROFIT = "PROFIT"
    ROI = "ROI"
    MARGIN = "MARGIN"
    BREAK_EVEN_PRICE = "BREAK_EVEN_PRICE"
    MAX_COG_TARGET_PROFIT = "MAX_COG_TARGET_PROFIT"
    MAX_COG_TARGET_ROI = "MAX_COG_TARGET_ROI"


class ExplicitInput(str, Enum):
    """Dependencies that are not FinancialTerms (ADR-047 §9, §10, §16)."""

    SELLING_PRICE = "SELLING_PRICE"
    WEIGHT = "WEIGHT"  # only through SHIPPING_PER_POUND
    TARGET_PROFIT = "TARGET_PROFIT"
    TARGET_ROI = "TARGET_ROI"


class ResolutionBlocker(str, Enum):
    """Why a dependency is not usable. A diagnostic, not a VerificationStatus."""

    STRUCTURALLY_ABSENT = "STRUCTURALLY_ABSENT"
    APPLICABILITY_UNRESOLVED = "APPLICABILITY_UNRESOLVED"
    VALUE_NOT_FOUND = "VALUE_NOT_FOUND"
    VALUE_INVALID = "VALUE_INVALID"
    CURRENCY_UNDECLARED = "CURRENCY_UNDECLARED"
    CURRENCY_INCOMPATIBLE = "CURRENCY_INCOMPATIBLE"
    UNIT_INCOMPATIBLE = "UNIT_INCOMPATIBLE"
    CONTEXT_REQUIREMENT_UNRESOLVED = "CONTEXT_REQUIREMENT_UNRESOLVED"


_C0 = (
    FinancialTerm.VAT, FinancialTerm.INBOUND_SHIPPING, FinancialTerm.SHIPPING_PER_UNIT,
    FinancialTerm.SHIPPING_PER_POUND, FinancialTerm.PREP, FinancialTerm.LABELING,
    FinancialTerm.FRAGILE_PREP, FinancialTerm.STORAGE, FinancialTerm.INBOUND_PLACEMENT,
    FinancialTerm.TAXES, FinancialTerm.OTHER_COSTS,
)
_FO = (FinancialTerm.FULFILLMENT_FEE, FinancialTerm.OTHER_SELLING_FEES)
_PROFIT_TERMS = (FinancialTerm.COG, *_C0, FinancialTerm.REFERRAL_FEE, *_FO)

#: ADR-047 §16: result -> (formula terms, explicit inputs, math preconditions).
DEPENDENCY_MATRIX: dict[FinancialResult, tuple[tuple[FinancialTerm, ...], tuple[ExplicitInput, ...], tuple[str, ...]]] = {
    FinancialResult.PROFIT: (_PROFIT_TERMS, (ExplicitInput.SELLING_PRICE,), ()),
    FinancialResult.ROI: (_PROFIT_TERMS, (ExplicitInput.SELLING_PRICE,), ("C = COG + C0 > 0",)),
    FinancialResult.MARGIN: (_PROFIT_TERMS, (ExplicitInput.SELLING_PRICE,), ("P > 0",)),
    FinancialResult.BREAK_EVEN_PRICE: (
        (FinancialTerm.COG, *_C0, *_FO, FinancialTerm.REFERRAL_FEE_RATE), (), ("1 - r > 0",)),
    FinancialResult.MAX_COG_TARGET_PROFIT: (
        (*_C0, FinancialTerm.REFERRAL_FEE, *_FO), (ExplicitInput.SELLING_PRICE, ExplicitInput.TARGET_PROFIT), ()),
    FinancialResult.MAX_COG_TARGET_ROI: (
        (*_C0, FinancialTerm.REFERRAL_FEE, *_FO), (ExplicitInput.SELLING_PRICE, ExplicitInput.TARGET_ROI),
        ("1 + tr > 0",)),
}


@dataclass(frozen=True)
class DependencyResolution:
    """One dependency of one result, with the original evidence objects.

    `operand` is the untouched usable FieldValue (value, unit, status and
    provenance as captured); `applicability` is the assertion a term's
    inclusion or exclusion depends on. An accredited exclusion has no operand,
    `excluded=True` and keeps its applicability status (INFERRED stays INFERRED).
    `evidence` links the term's whole FinancialTermEvidence (context,
    allocation, depends_on) so no part of it is lost by resolution.
    """

    dependency: str
    term: Optional[FinancialTerm]
    operand: Optional[FieldValue] = None
    applicability: Optional[FieldValue] = None
    excluded: bool = False
    blocker: Optional[ResolutionBlocker] = None
    detail: Optional[str] = None
    evidence: Optional[FinancialTermEvidence] = None

    @property
    def statuses(self) -> tuple[VerificationStatus, ...]:
        return tuple(fv.status for fv in (self.applicability, self.operand) if fv is not None)


@dataclass(frozen=True)
class ResultResolution:
    result: FinancialResult
    scenario: FinancialScenario
    dependencies: tuple[DependencyResolution, ...]
    math_preconditions: tuple[str, ...]

    @property
    def blockers(self) -> tuple[DependencyResolution, ...]:
        return tuple(dep for dep in self.dependencies if dep.blocker is not None)

    @property
    def dependencies_resolved(self) -> bool:
        """Every evidence precondition holds. Not "calculable": math preconditions remain."""
        return not self.blockers

    @property
    def dependency_status(self) -> Optional[VerificationStatus]:
        """Weakest-link status of the resolved dependencies (ADR-047 §17); None while blocked."""
        if not self.dependencies_resolved:
            return None
        return combine_verification_status(s for dep in self.dependencies for s in dep.statuses)


@dataclass(frozen=True)
class FinancialDependencyResolution:
    execution_id: str
    record_reference: str
    results: tuple[ResultResolution, ...]

    def for_result(self, result: FinancialResult) -> ResultResolution:
        return next(item for item in self.results if item.result == result)


def resolve_financial_dependencies(
    evidence: FinancialEvidenceSet,
    *,
    selling_price: Optional[FieldValue] = None,
    weight: Optional[FieldValue] = None,
    target_profit: Optional[FieldValue] = None,
    target_roi: Optional[FieldValue] = None,
) -> FinancialDependencyResolution:
    """Resolve every §16 result's dependencies against one evidence set.

    Explicit inputs are FieldValues supplied by the caller; None is structural
    absence. Only contract errors raise: ordinary missing evidence is reported.
    """
    if not isinstance(evidence, FinancialEvidenceSet):
        raise ValueError("Explicit FinancialEvidenceSet required")
    explicit = {ExplicitInput.SELLING_PRICE: selling_price, ExplicitInput.WEIGHT: weight,
                ExplicitInput.TARGET_PROFIT: target_profit, ExplicitInput.TARGET_ROI: target_roi}
    for name, value in explicit.items():
        if value is not None and not isinstance(value, FieldValue):
            raise ValueError(f"{name.value} must be a FieldValue or None, never a bare value")
    scenario = evidence.scenario
    context = tuple(
        DependencyResolution(f"CONTEXT_REQUIREMENT:{requirement}", None,
                             blocker=ResolutionBlocker.CONTEXT_REQUIREMENT_UNRESOLVED,
                             detail="no approved method resolves scenario context requirements (ADR-047 §28)")
        for requirement in scenario.context_requirements
    )
    results = []
    for result, (terms, inputs, math) in DEPENDENCY_MATRIX.items():
        dependencies = list(context)
        for term in terms:
            if term in scenario.required_terms or evidence.evidence_for(term) is not None:
                dependencies.extend(_resolve_term(term, evidence, explicit[ExplicitInput.WEIGHT]))
        for name in inputs:
            dependencies.append(_resolve_explicit(name, explicit[name], scenario.currency))
        results.append(ResultResolution(result, scenario, tuple(dependencies), math))
    return FinancialDependencyResolution(evidence.execution_id, evidence.record_reference, tuple(results))


def _resolve_term(term: FinancialTerm, evidence: FinancialEvidenceSet,
                  weight: Optional[FieldValue]) -> tuple[DependencyResolution, ...]:
    item = evidence.evidence_for(term)
    if item is None:
        return (DependencyResolution(term.value, term, blocker=ResolutionBlocker.STRUCTURALLY_ABSENT,
                                     detail="required by the scenario but not represented"),)
    applies = item.applicability.applies
    if not item.applicability.is_resolved:
        return (DependencyResolution(term.value, term, applicability=applies,
                                     blocker=ResolutionBlocker.APPLICABILITY_UNRESOLVED,
                                     detail=f"applicability is {applies.status.value}", evidence=item),)
    if item.applicability.excludes:
        return (DependencyResolution(term.value, term, applicability=applies, excluded=True, evidence=item),)
    amount = item.amount
    if amount is None:
        resolved = DependencyResolution(term.value, term, applicability=applies,
                                        blocker=ResolutionBlocker.STRUCTURALLY_ABSENT,
                                        detail="applies but no amount is represented", evidence=item)
    elif not amount.is_usable:
        blocker = (ResolutionBlocker.VALUE_INVALID if amount.status is VerificationStatus.INVALID
                   else ResolutionBlocker.VALUE_NOT_FOUND)
        resolved = DependencyResolution(term.value, term, operand=None, applicability=applies,
                                        blocker=blocker, detail=f"amount is {amount.status.value}", evidence=item)
    else:
        resolved = DependencyResolution(term.value, term, operand=amount, applicability=applies, evidence=item)
    if term is not FinancialTerm.SHIPPING_PER_POUND or resolved.blocker is not None:
        return (resolved,)
    # A per-pound rate is only an operand together with the effective weight.
    return (resolved, _resolve_weight(weight))


def _resolve_weight(weight: Optional[FieldValue]) -> DependencyResolution:
    name = ExplicitInput.WEIGHT.value
    blocked = _unusable(name, weight)
    if blocked is not None:
        return blocked
    if weight.unit != CANONICAL_WEIGHT_UNIT:
        return DependencyResolution(name, None, blocker=ResolutionBlocker.UNIT_INCOMPATIBLE,
                                    detail=f"weight unit {weight.unit!r} is not {CANONICAL_WEIGHT_UNIT!r}; not converted")
    return DependencyResolution(name, None, operand=weight)


def _resolve_explicit(name: ExplicitInput, value: Optional[FieldValue], currency: str) -> DependencyResolution:
    blocked = _unusable(name.value, value)
    if blocked is not None:
        return blocked
    if name is ExplicitInput.TARGET_ROI:
        if value.unit != RATIO_UNIT:
            return DependencyResolution(name.value, None, blocker=ResolutionBlocker.UNIT_INCOMPATIBLE,
                                        detail=f"target ROI must keep unit {RATIO_UNIT!r}, got {value.unit!r}")
        return DependencyResolution(name.value, None, operand=value)
    if value.unit is None:
        return DependencyResolution(name.value, None, blocker=ResolutionBlocker.CURRENCY_UNDECLARED,
                                    detail="no currency declared; none is inferred")
    if value.unit != currency:
        return DependencyResolution(name.value, None, blocker=ResolutionBlocker.CURRENCY_INCOMPATIBLE,
                                    detail=f"{value.unit!r} is not scenario currency {currency!r}; not converted")
    return DependencyResolution(name.value, None, operand=value)


def _unusable(name: str, value: Optional[FieldValue]) -> Optional[DependencyResolution]:
    if value is None:
        return DependencyResolution(name, None, blocker=ResolutionBlocker.STRUCTURALLY_ABSENT,
                                    detail="not supplied")
    if value.status is VerificationStatus.INVALID:
        return DependencyResolution(name, None, blocker=ResolutionBlocker.VALUE_INVALID, detail="INVALID")
    if not value.is_usable:
        return DependencyResolution(name, None, blocker=ResolutionBlocker.VALUE_NOT_FOUND,
                                    detail=value.status.value)
    if not isinstance(value.value, Decimal) or not value.value.is_finite():
        return DependencyResolution(name, None, blocker=ResolutionBlocker.VALUE_INVALID,
                                    detail="a usable operand must be a finite Decimal")
    return None
