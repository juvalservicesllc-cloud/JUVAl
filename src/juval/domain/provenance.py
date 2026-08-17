"""Provenance and verification-state primitives.

Every sensitive data point in Juval (ASIN, weight, HazMat, price, demand,
risk flags, calculated financials, ...) is wrapped in a `FieldValue`, never
stored as a bare value. This is what makes it possible to answer "where did
this come from?" for any number the Decision Engine or the AI Analyst uses.

See docs/architecture/DATA_PROVENANCE.md for the normative description.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Iterable, Optional, TypeVar

T = TypeVar("T")


class VerificationStatus(str, Enum):
    """Mutually exclusive outcome of trying to establish a field's value.

    A single field can be in exactly one of these states at a time — this is
    enforced structurally (one enum, not independent booleans) precisely so
    that VERIFIED and INFERRED can never be confused, and NOT_FOUND can never
    silently carry a value.
    """

    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"


class SourceType(str, Enum):
    """Where a data point came from. Orthogonal to VerificationStatus:
    SourceType says *where we looked*, VerificationStatus says *what we got*.

    Example: source_type=OFFICIAL_API + verification_status=NOT_FOUND means
    "we queried an authorized API and it had no match" — more informative
    than source_type=NOT_FOUND, which means no source was even attempted.
    """

    USER_INPUT = "USER_INPUT"
    SUPPLIER_FILE = "SUPPLIER_FILE"
    OFFICIAL_API = "OFFICIAL_API"
    AUTHORIZED_EXTERNAL_SOURCE = "AUTHORIZED_EXTERNAL_SOURCE"
    DATABASE = "DATABASE"
    CALCULATED = "CALCULATED"
    INFERRED = "INFERRED"
    AI_ANALYSIS = "AI_ANALYSIS"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class Provenance:
    """Answers "where did this value come from?" for a single FieldValue."""

    source: str
    source_type: SourceType
    verification_status: VerificationStatus
    retrieved_at: datetime
    method: str
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    source_reference: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("Provenance.source must not be empty")
        if not self.method:
            raise ValueError("Provenance.method must not be empty")
        if self.retrieved_at.tzinfo is None:
            raise ValueError(
                "Provenance.retrieved_at must be timezone-aware "
                "(freshness/reproducibility checks require an unambiguous instant)"
            )
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Provenance.confidence must be within [0, 1], got {self.confidence}")


@dataclass(frozen=True)
class FieldValue(Generic[T]):
    """A single data point, always carrying its provenance.

    Invariants (enforced in __post_init__, not left to caller discipline):
      * status == NOT_FOUND  => value is None
      * status in (VERIFIED, INFERRED) => value is not None
      * status == INVALID    => raw_value is preserved for diagnosis
    """

    value: Optional[T]
    provenance: Provenance
    unit: Optional[str] = None
    raw_value: Optional[Any] = None

    def __post_init__(self) -> None:
        status = self.provenance.verification_status
        if status == VerificationStatus.NOT_FOUND and self.value is not None:
            raise ValueError("A NOT_FOUND FieldValue must not carry a value")
        if status in (VerificationStatus.VERIFIED, VerificationStatus.INFERRED) and self.value is None:
            raise ValueError(f"A {status.value} FieldValue must carry a non-None value")
        if status == VerificationStatus.INVALID and self.raw_value is None:
            raise ValueError("An INVALID FieldValue must preserve raw_value for diagnosis")

    @property
    def is_usable(self) -> bool:
        """True if this value can be used in calculations/decisions as-is."""
        return self.provenance.verification_status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.INFERRED,
        )

    @property
    def status(self) -> VerificationStatus:
        return self.provenance.verification_status

    # -- Convenience constructors -------------------------------------

    @classmethod
    def verified(
        cls,
        value: T,
        *,
        source: str,
        method: str,
        retrieved_at: datetime,
        source_type: SourceType = SourceType.USER_INPUT,
        unit: Optional[str] = None,
        confidence: Optional[float] = None,
        evidence: Optional[str] = None,
        source_reference: Optional[str] = None,
    ) -> "FieldValue[T]":
        return cls(
            value=value,
            unit=unit,
            provenance=Provenance(
                source=source,
                source_type=source_type,
                verification_status=VerificationStatus.VERIFIED,
                retrieved_at=retrieved_at,
                method=method,
                confidence=confidence,
                evidence=evidence,
                source_reference=source_reference,
            ),
        )

    @classmethod
    def inferred(
        cls,
        value: T,
        *,
        source: str,
        method: str,
        retrieved_at: datetime,
        source_type: SourceType = SourceType.INFERRED,
        unit: Optional[str] = None,
        confidence: Optional[float] = None,
        evidence: Optional[str] = None,
        source_reference: Optional[str] = None,
    ) -> "FieldValue[T]":
        return cls(
            value=value,
            unit=unit,
            provenance=Provenance(
                source=source,
                source_type=source_type,
                verification_status=VerificationStatus.INFERRED,
                retrieved_at=retrieved_at,
                method=method,
                confidence=confidence,
                evidence=evidence,
                source_reference=source_reference,
            ),
        )

    @classmethod
    def not_found(
        cls,
        *,
        source: str,
        method: str,
        retrieved_at: datetime,
        source_type: SourceType = SourceType.NOT_FOUND,
        evidence: Optional[str] = None,
        source_reference: Optional[str] = None,
    ) -> "FieldValue[T]":
        return cls(
            value=None,
            provenance=Provenance(
                source=source,
                source_type=source_type,
                verification_status=VerificationStatus.NOT_FOUND,
                retrieved_at=retrieved_at,
                method=method,
                evidence=evidence,
                source_reference=source_reference,
            ),
        )

    @classmethod
    def invalid(
        cls,
        raw_value: Any,
        *,
        source: str,
        method: str,
        retrieved_at: datetime,
        source_type: SourceType,
        evidence: Optional[str] = None,
        source_reference: Optional[str] = None,
    ) -> "FieldValue[T]":
        return cls(
            value=None,
            raw_value=raw_value,
            provenance=Provenance(
                source=source,
                source_type=source_type,
                verification_status=VerificationStatus.INVALID,
                retrieved_at=retrieved_at,
                method=method,
                evidence=evidence,
                source_reference=source_reference,
            ),
        )


def combine_verification_status(statuses: Iterable[VerificationStatus]) -> VerificationStatus:
    """Propagation rule for CALCULATED fields (profit, ROI, margin, score, ...).

    A calculated value can never be more certain than its weakest input:
      * if any input is NOT_FOUND or INVALID, the calculation cannot be
        trusted as a real number -> result is NOT_FOUND (never a silently
        computed value that ignores the gap).
      * else if any input is INFERRED, the result is INFERRED.
      * else (all inputs VERIFIED) the result is VERIFIED.
    """

    statuses = list(statuses)
    if not statuses:
        raise ValueError("combine_verification_status requires at least one status")
    if any(s in (VerificationStatus.NOT_FOUND, VerificationStatus.INVALID) for s in statuses):
        return VerificationStatus.NOT_FOUND
    if any(s == VerificationStatus.INFERRED for s in statuses):
        return VerificationStatus.INFERRED
    return VerificationStatus.VERIFIED
