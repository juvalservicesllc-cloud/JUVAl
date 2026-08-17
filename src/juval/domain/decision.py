"""Decision Engine data types: the BUY / REVIEW / PASS classification.

Only data structures live here — the actual rule evaluation is in
`juval.processing.decision_engine` (Processing Core), consistent with the
domain layer staying free of orchestration logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from .provenance import FieldValue
from .risk import RiskProfile, Severity


class Decision(str, Enum):
    BUY = "BUY"
    REVIEW = "REVIEW"
    PASS = "PASS"


@dataclass(frozen=True)
class Thresholds:
    """Configurable decision thresholds — supplied by the caller (config
    file, UI setting), never hardcoded in the engine. There is deliberately
    no exported default instance: every caller must state its own
    commercial thresholds explicitly.
    """

    target_profit: Decimal
    target_roi: Decimal
    minimum_estimated_monthly_sales: int
    maximum_risk_severity: Severity
    allow_restricted: bool = False
    allow_approval_required: bool = False
    allow_unknown_risk: bool = False

    def __post_init__(self) -> None:
        if self.minimum_estimated_monthly_sales < 0:
            raise ValueError("minimum_estimated_monthly_sales must not be negative")


@dataclass(frozen=True)
class DecisionInputs:
    """Everything the Decision Engine reads. All values here must already
    be computed upstream (Profitability Engine, Risk Engine, Demand data)
    — the Decision Engine never computes a financial value itself, it only
    classifies based on values it is handed."""

    profit: FieldValue[Decimal]
    roi: FieldValue[Decimal]
    estimated_monthly_sales: Optional[FieldValue[int]]
    risk_profile: RiskProfile


@dataclass(frozen=True)
class DecisionReason:
    code: str
    message: str


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reasons: tuple[DecisionReason, ...]
    evaluated_at: datetime

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None:
            raise ValueError("DecisionResult.evaluated_at must be timezone-aware")
        if self.decision != Decision.BUY and not self.reasons:
            raise ValueError("REVIEW and PASS decisions must carry at least one reason")
