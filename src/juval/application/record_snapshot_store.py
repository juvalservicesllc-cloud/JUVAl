"""Port: read access to persisted record snapshots for one execution.

Deliberately separate from ExecutionRunStore (ADR-019) -- reading the
records of a run is an independent concern from persisting the run
itself, with no atomicity requirement of its own. Writing stays on
ExecutionRunStore.save_execution_run(run, records=...) instead, because
that write must share one transaction with the ExecutionRun write; see
that Protocol's docstring and ADR-019 for why.

One method only, justified by the one real caller
(GET /api/v1/runs/{execution_id}/records) -- not a generic Repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Protocol


RecordSort = Literal["record_ref", "sku", "asin", "title", "price", "cog", "decision", "profit", "roi", "margin", "hazmat", "bulky"]
SortDirection = Literal["asc", "desc"]
ConfidenceMode = Literal["VERIFIED_ONLY", "INCLUDE_INFERRED"]
ProvenanceField = Literal["asin", "selling_price", "profit", "roi", "margin"]


@dataclass(frozen=True)
class RecordSnapshotQuery:
    """Persistence-level query for immutable snapshots of one run.

    Offset pagination is intentional: a persisted execution run is immutable,
    so ordinal order cannot drift while an operator pages through it.  It also
    matches the existing `(execution_id, ordinal)` index in both stores.
    """

    limit: int
    offset: int = 0
    search: str | None = None
    decision: str | None = None
    sort: RecordSort = "record_ref"
    direction: SortDirection = "asc"
    min_roi: Decimal | None = None
    min_profit: Decimal | None = None
    min_margin: Decimal | None = None
    confidence: ConfidenceMode = "VERIFIED_ONLY"
    hazmat: str | None = None
    bulky: str | None = None
    provenance_field: ProvenanceField | None = None
    provenance_status: str | None = None


@dataclass(frozen=True)
class RecordSnapshotPage:
    items: list[dict[str, Any]]
    total: int


class RecordSnapshotStore(Protocol):
    def load_records(self, execution_id: str) -> list[dict[str, Any]]:
        """Snapshots for `execution_id`, in original processing order.

        Returns [] both when the run has no persisted records and when
        `execution_id` itself is unknown to this store -- distinguishing
        those two is the caller's job via ExecutionRunStore.load_execution_run,
        not this port's (same "absence is not an exception" convention
        as ExecutionRunStore.load_execution_run).
        """
        ...

    def load_record(self, execution_id: str, record_ref: str) -> dict[str, Any] | None:
        """Return one immutable snapshot by its run-scoped composite identity.

        ``None`` means the record is absent from that execution. The caller
        checks run existence separately so the API can keep both cases as
        honest, non-enumerating 404 responses.
        """
        ...

    def list_records(self, execution_id: str, query: RecordSnapshotQuery) -> RecordSnapshotPage:
        """Return one backend-paginated snapshot page and its exact total.

        The query is deliberately run-scoped and bounded by the API before it
        reaches an adapter; it is not a generic product repository.
        """
        ...

    def get_run_analytics(self, execution_id: str) -> dict[str, Any]:
        """Aggregate canonical snapshot fields for one immutable execution."""
        ...
