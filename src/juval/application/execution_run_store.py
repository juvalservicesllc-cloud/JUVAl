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

Originally deliberately two methods only — save by execution_id, load
by execution_id; a Repository-style list was explicitly rejected as
speculative ("not needed by any caller today", ADR-013). ADR-019
(2026-08-17) revisits exactly that: a real caller now exists
(`GET /api/v1/runs`), so `list_execution_runs` was added. Still not a
generic Repository — no delete/update/query-by-arbitrary-field, only
what that one caller needs.

Record-level persistence (the individual `SourcingRecord`s a run
produced) is a deliberately separate concern, not folded into this
Protocol — see `record_snapshot_store.py::RecordSnapshotStore` and
ADR-019 for why. `save_execution_run` grew an optional `records`
parameter instead: writing an ExecutionRun and its records must be
atomic (never one persisted without the other), and the only way to
guarantee that without a Unit-of-Work framework is to have the
concrete adapter -- which already owns the one connection/transaction
that matters -- do both writes together.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence

from juval.domain.execution_run import ExecutionRun


class ExecutionRunStore(Protocol):
    def save_execution_run(self, run: ExecutionRun, records: Sequence[Mapping[str, Any]] = ()) -> None:
        """Persist `run`, and -- atomically, same transaction -- `records`
        if given (ADR-019). Each item of `records` is a JSON-safe snapshot
        dict shaped like `record_snapshot.py::record_to_snapshot()` output;
        never a domain SourcingRecord (this port stays free of any need to
        re-import domain internals beyond ExecutionRun).

        Must raise if `run.execution_id` already exists in the store —
        an ExecutionRun is an audit record; silently overwriting one
        would destroy the trail this store exists to preserve (see
        ADR-013, "comportamiento ante execution_id duplicado"). A
        duplicate must leave neither the run nor any of its records
        persisted (atomic failure, not a partial write).
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

    def list_execution_runs(self, limit: int = 20) -> list[ExecutionRun]:
        """Most recently started runs first, capped at `limit` (ADR-019)
        -- callers must never receive an unbounded scan of history."""
        ...
