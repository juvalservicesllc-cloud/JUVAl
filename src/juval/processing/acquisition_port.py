"""Port for authorized external acquisition (ADR-057, ADR-058).

Defined inward, implemented in infrastructure/enrichment/ (CLAUDE.md §13).
Pure types only: no I/O, and nothing in processing/ calls a connector or reads
what one returns -- the application layer orchestrates acquisition after the
pipeline, so BUY/REVIEW/PASS never depend on it (ADR-052 §20.3, ADR-058 I6).

Each consulted item ends with exactly one `ItemOutcome`, by the precedence of
ADR-058 §6, computed here from what the item produced so no adapter can choose
it: FAILED, else WITH_EVIDENCE, else REJECTED, else NO_EVIDENCE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol, Sequence

from juval.domain.acquisition import ConfiguredSource, FailureCategory, ItemOutcome
from juval.domain.provenance import FieldValue, VerificationStatus
from juval.domain.sourcing_record import SourcingRecord


@dataclass(frozen=True)
class AcquisitionItem:
    """One record to consult, by the identifier the operation's contract needs."""

    record_ref: str
    identifier: str

    def __post_init__(self) -> None:
        if not self.record_ref or not self.identifier:
            raise ValueError("an acquisition item needs a record_ref and an identifier")


@dataclass(frozen=True)
class AcquiredValue:
    field: str
    value: FieldValue[Any]

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("an acquired value needs a field name")


@dataclass(frozen=True)
class ItemResult:
    record_ref: str
    outcome: ItemOutcome
    failure: Optional[FailureCategory] = None
    values: tuple[AcquiredValue, ...] = ()
    observation_contract_rejected: int = 0

    def __post_init__(self) -> None:
        fields = [v.field for v in self.values]
        if len(set(fields)) != len(fields):
            raise ValueError(f"{self.record_ref}: a field was acquired twice for one item")
        if self.observation_contract_rejected < 0:
            raise ValueError("observation_contract_rejected must be >= 0")
        if (self.outcome is ItemOutcome.FAILED) != (self.failure is not None):
            raise ValueError(f"{self.record_ref}: a failure category is set exactly when the item FAILED")
        if self.outcome is ItemOutcome.FAILED:
            if self.values or self.observation_contract_rejected:
                raise ValueError(f"{self.record_ref}: a failed item carries no values (never NOT_FOUND)")
        elif self.outcome is not _precedence(self.values, self.observation_contract_rejected):
            raise ValueError(f"{self.record_ref}: outcome {self.outcome.value} breaks the ADR-058 §6 precedence")

    @classmethod
    def failed(cls, record_ref: str, failure: FailureCategory) -> "ItemResult":
        return cls(record_ref, ItemOutcome.FAILED, failure)

    @classmethod
    def from_values(cls, record_ref: str, values: Sequence[AcquiredValue],
                    observation_contract_rejected: int = 0) -> "ItemResult":
        values = tuple(values)
        return cls(record_ref, _precedence(values, observation_contract_rejected), None, values,
                   observation_contract_rejected)


def _precedence(values: Sequence[AcquiredValue], observation_contract_rejected: int) -> ItemOutcome:
    statuses = {v.value.provenance.verification_status for v in values}
    if statuses & {VerificationStatus.VERIFIED, VerificationStatus.INFERRED}:
        return ItemOutcome.WITH_EVIDENCE
    if VerificationStatus.INVALID in statuses or observation_contract_rejected:
        return ItemOutcome.REJECTED
    if VerificationStatus.NOT_FOUND in statuses:
        return ItemOutcome.NO_EVIDENCE
    raise ValueError("an item that did not fail must leave at least one value (NOT_FOUND when there is no evidence)")


@dataclass(frozen=True)
class SourceAcquisitionResult:
    source_id: str
    requests_sent: int
    retries: int
    first_request_at: Optional[datetime]
    last_request_at: Optional[datetime]
    items: tuple[ItemResult, ...]


class AuthorizedConnector(Protocol):
    """One authorized provider operation (ADR-057), enabled explicitly."""

    @property
    def source(self) -> ConfiguredSource: ...

    def identifier_for(self, record: SourcingRecord) -> Optional[str]:
        """The identifier this operation consults for `record`, or None if the
        record is not eligible according to the operation's contract."""
        ...

    def acquire(self, items: Sequence[AcquisitionItem]) -> SourceAcquisitionResult:
        """Consult the provider for `items`: exactly one ItemResult per item.
        Operational failures are results (FAILED), never exceptions or NOT_FOUND."""
        ...
