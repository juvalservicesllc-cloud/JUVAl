"""Processing issue taxonomy, shared across import/validation/processing.

See docs/architecture/ARCHITECTURE.md §7 (Phase 0) for the original
definition; reused as-is for the sourcing pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IssueLevel(str, Enum):
    FATAL = "FATAL"
    RECORD_ERROR = "RECORD_ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class ProcessingIssue:
    level: IssueLevel
    code: str
    message: str
    field: Optional[str] = None
    record_ref: Optional[str] = None
