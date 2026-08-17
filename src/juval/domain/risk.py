"""Risk model for a sourcing candidate.

Each risk type is tracked independently with its own status, verification
state, severity and evidence — a single "is this risky?" boolean would
throw away exactly the trail the project requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from .provenance import VerificationStatus


class RiskType(str, Enum):
    HAZMAT = "HAZMAT"
    OVERSIZE = "OVERSIZE"
    BULKY = "BULKY"
    MELTABLE = "MELTABLE"
    FRAGILE = "FRAGILE"
    IP_COMPLAINTS = "IP_COMPLAINTS"
    VARIATION = "VARIATION"
    SET_OR_BUNDLE = "SET_OR_BUNDLE"
    GENERIC = "GENERIC"
    RESTRICTED = "RESTRICTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    NO_BUY_BOX = "NO_BUY_BOX"
    NO_FBA_FEES = "NO_FBA_FEES"
    ASIN_NOT_FOUND = "ASIN_NOT_FOUND"


class RiskStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_SEVERITY_RANK = {
    Severity.NONE: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True)
class RiskFlag:
    risk_type: RiskType
    status: RiskStatus
    verification_status: VerificationStatus
    severity: Severity
    source: str
    timestamp: datetime
    evidence: Optional[str] = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("RiskFlag.timestamp must be timezone-aware")
        if not self.source:
            raise ValueError("RiskFlag.source must not be empty")
        if self.status == RiskStatus.ABSENT and self.severity != Severity.NONE:
            raise ValueError("An ABSENT RiskFlag must have severity NONE")
        if self.status == RiskStatus.UNKNOWN and self.verification_status not in (
            VerificationStatus.NOT_FOUND,
            VerificationStatus.INVALID,
        ):
            raise ValueError(
                "An UNKNOWN RiskFlag must carry verification_status NOT_FOUND or INVALID "
                "(an unknown risk is never VERIFIED or INFERRED)"
            )


@dataclass(frozen=True)
class RiskProfile:
    flags: tuple[RiskFlag, ...] = ()

    def flag_for(self, risk_type: RiskType) -> Optional[RiskFlag]:
        for flag in self.flags:
            if flag.risk_type == risk_type:
                return flag
        return None

    @property
    def highest_severity(self) -> Severity:
        present = [f.severity for f in self.flags if f.status == RiskStatus.PRESENT]
        if not present:
            return Severity.NONE
        return max(present, key=lambda s: _SEVERITY_RANK[s])

    @property
    def has_unknown_risk(self) -> bool:
        """True if any tracked risk type could not be determined. The
        Decision Engine must treat this conservatively — an unresolved risk
        is never treated as ABSENT."""

        return any(f.status == RiskStatus.UNKNOWN for f in self.flags)
