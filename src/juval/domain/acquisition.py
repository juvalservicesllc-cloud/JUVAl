"""ADR-058: what a run configured, consulted and obtained from external sources.

Two value objects per run, kept apart on purpose (ADR-058 §4):

* `AcquisitionConfiguration` -- the authorized sources enabled when the run
  started, each with the contract it was built from (ADR-057 D3.2).
* `AcquisitionExecution` -- per source, the aggregate outcome of the run:
  requests, retries, one result per consulted item and the counts of persisted
  values derived from provenance (ADR-058 §6-§7).

Only external acquisition is in scope (ADR-058 §2): `OFFICIAL_API` and
`AUTHORIZED_EXTERNAL_SOURCE`. The input file is already identified by
`ExecutionRun.input_hash`. A run without these objects is NOT_RECORDED; an
empty `sources` tuple means "recorded, no external source configured".

No I/O, no serialization (application/acquisition_documents.py) and nothing
here reaches `processing/` or the Decision Engine (ADR-058 I6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional

from juval.domain.provenance import SourceType

#: Source types that represent external acquisition (ADR-058 §2).
EXTERNAL_SOURCE_TYPES = frozenset({SourceType.OFFICIAL_API, SourceType.AUTHORIZED_EXTERNAL_SOURCE})

# `<provider>/<operation>`: the "/" keeps it disjoint from any input filename
# (`Path.name` never contains one), so provenance attribution is unambiguous.
_SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
# Mirror of processing/data_quality.py::_PLACEHOLDER_SOURCES (a test holds them
# equal): "n/a" is a valid-looking id but a placeholder source (ADR-058 P10).
PLACEHOLDER_SOURCES = frozenset({"unknown", "n/a", "na", "todo", "tbd", "?"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_source_id(source_id: str) -> str:
    if not isinstance(source_id, str) or not _SOURCE_ID.match(source_id):
        raise ValueError(f"source_id must look like '<provider>/<operation>' in lowercase, got {source_id!r}")
    if source_id in PLACEHOLDER_SOURCES:
        raise ValueError(f"source_id {source_id!r} is a placeholder source")
    return source_id


def _aware(value: Optional[datetime], name: str) -> None:
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None
                              or value.tzinfo.utcoffset(value) is None):
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _count(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be an integer >= 0, got {value!r}")


class FailureCategory(str, Enum):
    """Operational failures (DATA_SOURCES.md §1b). None of them is NOT_FOUND."""

    THROTTLED = "THROTTLED"
    SOURCE_FAILURE = "SOURCE_FAILURE"
    AUTH_OR_CONFIGURATION = "AUTH_OR_CONFIGURATION"
    SCHEMA_FAILURE = "SCHEMA_FAILURE"


class NotConsultedReason(str, Enum):
    """Closed v1 enum (ADR-058 §5.2); a new reason needs the ADR of its policy."""

    RUN_FAILED_BEFORE_ACQUISITION = "RUN_FAILED_BEFORE_ACQUISITION"
    NO_ELIGIBLE_RECORDS = "NO_ELIGIBLE_RECORDS"


class EnabledBy(str, Enum):
    ENV_FLAG = "ENV_FLAG"


class ItemOutcome(str, Enum):
    """Exactly one per consulted item, by the precedence of ADR-058 §6."""

    FAILED = "FAILED"
    WITH_EVIDENCE = "WITH_EVIDENCE"
    REJECTED = "REJECTED"
    NO_EVIDENCE = "NO_EVIDENCE"


@dataclass(frozen=True)
class ConfiguredSource:
    source_id: str
    source_type: SourceType
    contract_id: str
    contract_sha256: str
    enabled_by: EnabledBy = EnabledBy.ENV_FLAG

    def __post_init__(self) -> None:
        validate_source_id(self.source_id)
        if self.source_type not in EXTERNAL_SOURCE_TYPES:
            raise ValueError(f"{self.source_id}: source_type must be external, got {self.source_type!r}")
        if not isinstance(self.contract_id, str) or not self.contract_id.strip():
            raise ValueError(f"{self.source_id}: contract_id must not be empty")
        if not isinstance(self.contract_sha256, str) or not _SHA256.match(self.contract_sha256):
            raise ValueError(f"{self.source_id}: contract_sha256 must be 64 lowercase hex characters")
        if not isinstance(self.enabled_by, EnabledBy):
            raise ValueError(f"{self.source_id}: enabled_by must be an EnabledBy")


@dataclass(frozen=True)
class AcquisitionConfiguration:
    """Fixed when the run starts, before its first request (ADR-058 §5.1)."""

    captured_at: datetime
    sources: tuple[ConfiguredSource, ...]

    def __post_init__(self) -> None:
        _aware(self.captured_at, "AcquisitionConfiguration.captured_at")
        if not isinstance(self.sources, tuple) or not all(isinstance(s, ConfiguredSource) for s in self.sources):
            raise ValueError("AcquisitionConfiguration.sources must be a tuple of ConfiguredSource")
        ids = [s.source_id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError("a source appears more than once in the configuration (one contract per run, P9)")

    def source(self, source_id: str) -> Optional[ConfiguredSource]:
        return next((s for s in self.sources if s.source_id == source_id), None)


@dataclass(frozen=True)
class ItemCounts:
    """Consulted items by result. `failed` always carries every category."""

    requested: int
    with_evidence: int
    no_evidence: int
    rejected: int
    failed: Mapping[FailureCategory, int]

    def __post_init__(self) -> None:
        for name in ("requested", "with_evidence", "no_evidence", "rejected"):
            _count(getattr(self, name), f"items.{name}")
        if set(self.failed) != set(FailureCategory):
            raise ValueError("items.failed must have exactly one count per FailureCategory")
        for category, value in self.failed.items():
            _count(value, f"items.failed.{category.value}")
        object.__setattr__(self, "failed", MappingProxyType({c: self.failed[c] for c in FailureCategory}))
        total = self.with_evidence + self.no_evidence + self.rejected + sum(self.failed.values())
        if total != self.requested:  # I2
            raise ValueError(f"items.requested ({self.requested}) must equal the sum of its outcomes ({total})")

    @property
    def failed_total(self) -> int:
        return sum(self.failed.values())

    @classmethod
    def empty(cls) -> "ItemCounts":
        return cls(0, 0, 0, 0, {c: 0 for c in FailureCategory})


@dataclass(frozen=True)
class ValueCounts:
    """Persisted values attributed to the source, derived from provenance (ADR-058 §7)."""

    used: int
    not_found: int
    invalid: int

    def __post_init__(self) -> None:
        for name in ("used", "not_found", "invalid"):
            _count(getattr(self, name), f"values.{name}")


@dataclass(frozen=True)
class SourceExecution:
    source_id: str
    first_request_at: Optional[datetime]
    last_request_at: Optional[datetime]
    requests_sent: int
    retries: int
    items: ItemCounts
    values: ValueCounts
    observation_contract_rejected: int
    not_consulted_reason: Optional[NotConsultedReason]

    def __post_init__(self) -> None:
        validate_source_id(self.source_id)
        _count(self.requests_sent, "requests_sent")
        _count(self.retries, "retries")
        _count(self.observation_contract_rejected, "observation_contract_rejected")
        _aware(self.first_request_at, "first_request_at")
        _aware(self.last_request_at, "last_request_at")
        consulted = self.items.requested > 0
        # I3
        if (self.requests_sent >= 1) != consulted:
            raise ValueError(f"{self.source_id}: requests_sent >= 1 exactly when items were requested")
        if (self.not_consulted_reason is not None) == consulted:
            raise ValueError(f"{self.source_id}: not_consulted_reason is set exactly when nothing was requested")
        if self.retries and not consulted:
            raise ValueError(f"{self.source_id}: retries without any request")
        if (self.first_request_at is None) != (not consulted) or (self.last_request_at is None) != (not consulted):
            raise ValueError(f"{self.source_id}: request instants are present exactly when it was consulted")
        if consulted and self.last_request_at < self.first_request_at:
            raise ValueError(f"{self.source_id}: last_request_at precedes first_request_at")
        # I4
        if (self.items.with_evidence > 0) != (self.values.used > 0):
            raise ValueError(f"{self.source_id}: items with evidence exist exactly when values were used")
        if self.items.no_evidence > 0 and self.values.not_found == 0:
            raise ValueError(f"{self.source_id}: an item without evidence must leave a NOT_FOUND value")
        if not consulted and (self.values.used or self.values.not_found or self.values.invalid
                              or self.observation_contract_rejected):
            raise ValueError(f"{self.source_id}: values attributed to a source that was not consulted")

    @property
    def consulted(self) -> bool:
        return self.items.requested > 0


@dataclass(frozen=True)
class AcquisitionExecution:
    sources: tuple[SourceExecution, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sources, tuple) or not all(isinstance(s, SourceExecution) for s in self.sources):
            raise ValueError("AcquisitionExecution.sources must be a tuple of SourceExecution")
        ids = [s.source_id for s in self.sources]
        if len(set(ids)) != len(ids):
            raise ValueError("a source appears more than once in the execution document")


@dataclass(frozen=True)
class AcquisitionRecord:
    """Both documents of one run: RECORDED. Absence of this object is NOT_RECORDED."""

    configuration: AcquisitionConfiguration
    execution: AcquisitionExecution

    def __post_init__(self) -> None:
        configured = [s.source_id for s in self.configuration.sources]
        executed = [s.source_id for s in self.execution.sources]
        if sorted(configured) != sorted(executed):  # I1
            raise ValueError("the execution document must have exactly one entry per configured source")
