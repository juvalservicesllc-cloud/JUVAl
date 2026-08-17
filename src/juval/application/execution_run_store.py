"""Port: persistence contract for ExecutionRun.

Defined in the Application Layer, not in domain/: ExecutionRun itself
must stay a plain, infrastructure-free dataclass (see
domain/execution_run.py — no sqlite3, no filesystem, no SQL). Concrete
implementations live in infrastructure/ (see
infrastructure/logging/sqlite_execution_run_store.py) and depend on
this contract; this contract never depends on them (ADR-001,
ARCHITECTURE.md §3 — dependency direction is Interfaces -> Application
-> Processing -> Domain, with Infrastructure implementing ports defined
inward).

Deliberately two methods only — save by execution_id, load by
execution_id. Not a generic Repository (list/delete/update/query are
not needed by any caller today and would be speculative — see
ADR-013).
"""

from __future__ import annotations

from typing import Optional, Protocol

from juval.domain.execution_run import ExecutionRun


class ExecutionRunStore(Protocol):
    def save_execution_run(self, run: ExecutionRun) -> None:
        """Persist `run`.

        Must raise if `run.execution_id` already exists in the store —
        an ExecutionRun is an audit record; silently overwriting one
        would destroy the trail this store exists to preserve (see
        ADR-013, "comportamiento ante execution_id duplicado").
        """
        ...

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]:
        """Return the ExecutionRun stored under `execution_id`, or None
        if it was never saved.

        Absence is represented as None rather than an exception,
        consistent with this codebase's existing convention for "not
        found" (see SourcingRecord.costs, FieldValue.not_found).
        """
        ...
