"""Decision Score — a 0-100 deterministic summary, separate from the
BUY/REVIEW/PASS decision itself.

Deliberately not AI-computed (requirement 13): every component is a
FieldValue[Decimal] in [0, 100] supplied by the caller (typically produced
by small, separately testable scoring functions per component —
profitability, demand, competition, price stability, risk, operational
complexity), and combined here with configurable weights. Using FieldValue
(rather than a plain Decimal plus a side-channel status) makes it
structurally impossible for a component's value and its verification
status to drift apart.

v1 scope: if any component is missing or unusable, the overall score is
NOT_FOUND rather than guessed from a partial set — silently reweighting
around a gap is a policy decision (see docs/architecture/DECISION_ENGINE.md,
"pending decisions") that has not been made yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from juval.domain.provenance import FieldValue, SourceType, VerificationStatus, combine_verification_status

_SOURCE = "decision_score"
_COMPONENT_NAMES = (
    "profitability",
    "demand",
    "competition",
    "price_stability",
    "risk",
    "operational_complexity",
)


@dataclass(frozen=True)
class ScoreWeights:
    profitability: Decimal
    demand: Decimal
    competition: Decimal
    price_stability: Decimal
    risk: Decimal
    operational_complexity: Decimal

    def __post_init__(self) -> None:
        for name in _COMPONENT_NAMES:
            value = getattr(self, name)
            if not (Decimal("0") <= value <= Decimal("1")):
                raise ValueError(f"ScoreWeights.{name} must be within [0, 1], got {value}")
        total = sum(getattr(self, name) for name in _COMPONENT_NAMES)
        if abs(total - Decimal("1")) > Decimal("0.0001"):
            raise ValueError(f"ScoreWeights must sum to 1, got {total}")


@dataclass(frozen=True)
class ScoreComponents:
    """Each field is a 0-100 subscore with its own provenance, or None if
    it was never computed for this candidate."""

    profitability: Optional[FieldValue[Decimal]] = None
    demand: Optional[FieldValue[Decimal]] = None
    competition: Optional[FieldValue[Decimal]] = None
    price_stability: Optional[FieldValue[Decimal]] = None
    risk: Optional[FieldValue[Decimal]] = None
    operational_complexity: Optional[FieldValue[Decimal]] = None

    def __post_init__(self) -> None:
        for name in _COMPONENT_NAMES:
            fv = getattr(self, name)
            if fv is not None and fv.value is not None and not (Decimal("0") <= fv.value <= Decimal("100")):
                raise ValueError(f"ScoreComponents.{name} must be within [0, 100], got {fv.value}")

    def missing_or_unusable(self) -> tuple[str, ...]:
        return tuple(
            name for name in _COMPONENT_NAMES if (fv := getattr(self, name)) is None or not fv.is_usable
        )


@dataclass(frozen=True)
class DecisionScoreResult:
    score: FieldValue[Decimal]
    components: ScoreComponents


def compute_decision_score(components: ScoreComponents, weights: ScoreWeights, *, now: datetime) -> DecisionScoreResult:
    missing = components.missing_or_unusable()
    if missing:
        return DecisionScoreResult(
            score=FieldValue.not_found(
                source=_SOURCE,
                method="weighted_sum",
                retrieved_at=now,
                evidence=f"components not usable: {', '.join(missing)}",
            ),
            components=components,
        )

    statuses = [getattr(components, name).status for name in _COMPONENT_NAMES]
    result_status = combine_verification_status(statuses)

    total = sum(getattr(components, name).value * getattr(weights, name) for name in _COMPONENT_NAMES)

    if result_status == VerificationStatus.VERIFIED:
        score = FieldValue.verified(
            total, source=_SOURCE, method="weighted_sum", retrieved_at=now, source_type=SourceType.CALCULATED
        )
    else:
        score = FieldValue.inferred(
            total, source=_SOURCE, method="weighted_sum", retrieved_at=now, source_type=SourceType.CALCULATED
        )

    return DecisionScoreResult(score=score, components=components)
