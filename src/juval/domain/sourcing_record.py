"""SourcingRecord — the aggregate root for one sourcing candidate.

This is composition, not a second implementation: every field here is an
instance of a type already defined elsewhere (Product, CostInputs,
FeeInputs, RiskProfile, ProfitabilityResult, DecisionScoreResult,
DecisionResult). SourcingRecord does not redefine, copy, or duplicate any
of their fields — it only holds references to them and tracks the issues
accumulated while building/processing this row. See ADR-011.

`profitability` and `score` are typed as `Any` rather than imported from
`juval.processing` on purpose: the domain layer must not depend on the
Processing Core (dependency direction is Interfaces -> Application ->
Processing -> Domain, never the reverse — see Fase 0 ARCHITECTURE.md §3).
At runtime they hold `juval.processing.profitability.ProfitabilityResult`
and `juval.processing.decision_score.DecisionScoreResult` respectively.

Immutable, like the rest of the domain: processing steps (Data Quality,
Profitability, Decision) each produce a *new* SourcingRecord via the
`.with_*()` helpers rather than mutating in place, so a partially-processed
record is never silently visible to two different callers at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Optional

from .costs import CostInputs, FeeInputs
from .decision import DecisionResult
from .issues import IssueLevel, ProcessingIssue
from .product import Product
from .risk import RiskProfile


@dataclass(frozen=True)
class SourcingRecord:
    """One row/product processed by Juval.

    `costs` is Optional, not a required CostInputs: if the source data did
    not provide a usable COG, we do not fabricate a CostInputs(cog=0) —
    the absence itself is the honest representation (see
    infrastructure/excel/importer.py and CostInputs' own docstring).
    """

    record_ref: str
    product: Product
    costs: Optional[CostInputs] = None
    fees: Optional[FeeInputs] = None
    risk: RiskProfile = field(default_factory=RiskProfile)
    profitability: Optional[Any] = None
    score: Optional[Any] = None
    decision: Optional[DecisionResult] = None
    issues: tuple[ProcessingIssue, ...] = ()

    def __post_init__(self) -> None:
        if not self.record_ref:
            raise ValueError("SourcingRecord.record_ref must not be empty")

    def with_issues(self, *new_issues: ProcessingIssue) -> "SourcingRecord":
        return replace(self, issues=self.issues + tuple(new_issues))

    def with_costs(self, costs: Optional[CostInputs]) -> "SourcingRecord":
        return replace(self, costs=costs)

    def with_fees(self, fees: Optional[FeeInputs]) -> "SourcingRecord":
        return replace(self, fees=fees)

    def with_risk(self, risk: RiskProfile) -> "SourcingRecord":
        return replace(self, risk=risk)

    def with_profitability(self, profitability: Any) -> "SourcingRecord":
        return replace(self, profitability=profitability)

    def with_score(self, score: Any) -> "SourcingRecord":
        return replace(self, score=score)

    def with_decision(self, decision: DecisionResult) -> "SourcingRecord":
        return replace(self, decision=decision)

    @property
    def has_fatal_issues(self) -> bool:
        return any(i.level == IssueLevel.FATAL for i in self.issues)

    @property
    def has_record_errors(self) -> bool:
        return any(i.level == IssueLevel.RECORD_ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.level == IssueLevel.WARNING for i in self.issues)
