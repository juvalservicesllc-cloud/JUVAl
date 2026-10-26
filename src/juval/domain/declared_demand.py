"""Declared demand captured from an input file (ADR-052, amendment to ADR-046).

A capture is *evidence*, never an input to the Decision Engine: it lives on
`SourcingRecord.market_evidence`, outside `Product`, and nothing in
`processing/` reads it. A usable value is INFERRED by construction
(`DemandObservation`, ADR-046 §9); anything the file did not declare well
enough is kept as a diagnostic with its raw cell, never repaired.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .market_evidence import DemandMetric, DemandObservation


@dataclass(frozen=True)
class DemandDiagnostic:
    """Why a declared demand cell did not become a usable observation."""

    code: str
    message: str
    row: int
    column: Optional[str] = None      # original header of the failing cell, when known
    raw_value: Optional[str] = None   # the cell as received, text form

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("DemandDiagnostic requires a code and a message")


@dataclass(frozen=True)
class DeclaredObservation:
    """One `DemandObservation` plus how its window was declared (ADR-052 §3.8)."""

    observation_id: str
    observation: DemandObservation
    window_source: str                 # "EXPLICIT" | "DECLARED_MONTH"
    declared_month: Optional[str] = None
    declared_timezone: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ValueError("observation_id must not be empty")
        if self.window_source not in ("EXPLICIT", "DECLARED_MONTH"):
            raise ValueError("window_source must be EXPLICIT or DECLARED_MONTH")
        if self.window_source == "DECLARED_MONTH" and not (self.declared_month and self.declared_timezone):
            raise ValueError("a declared-month window requires the declared month and timezone")
        if self.observation.metric != DemandMetric.ESTIMATED_SALES:
            raise ValueError("ADR-052 ingests ESTIMATED_SALES only")


@dataclass(frozen=True)
class DeclaredDemandCapture:
    """Everything one record's file row declared about demand.

    `captured_at` is the effective import instant every value's `retrieved_at`
    carries (ADR-052 §20.9). At most one observation per record in v1.
    """

    captured_at: datetime
    observations: tuple[DeclaredObservation, ...] = ()
    diagnostics: tuple[DemandDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        if len(self.observations) > 1:
            raise ValueError("ADR-052 v1 captures at most one demand observation per record")
