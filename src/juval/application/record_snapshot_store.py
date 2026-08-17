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

from typing import Any, Protocol


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
