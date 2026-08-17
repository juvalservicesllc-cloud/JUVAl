-- Juval — execution_run_records (run-scoped record snapshots, ADR-019)
--
-- Persists a JSON-safe snapshot of each SourcingRecord a run produced,
-- alongside the ExecutionRun aggregate that
-- 20260817000000_execution_runs.sql already persists. Does NOT modify
-- that already-applied migration -- this is an additive companion
-- table only.
--
-- Identity is (execution_id, record_ref), never record_ref alone:
-- ADR-012 established record_ref is unique only within a single
-- execution, never globally -- this table's PRIMARY KEY mirrors that
-- exactly, so the same record_ref can legitimately exist under
-- different execution_id values without collision.
--
-- `snapshot` is JSONB (Postgres' native structured-JSON type) holding
-- exactly what application/record_snapshot.py::record_to_snapshot()
-- produces -- the same shape interfaces/api/models.py::RecordOut
-- already exposes over HTTP. No per-field column modeling (would be
-- 20+ columns for what is fundamentally one nested payload); no
-- pickle, no opaque blob -- valid, inspectable, queryable JSON.
--
-- `ordinal` preserves the original processing order for stable reads
-- regardless of storage-level row order.

create table if not exists execution_run_records (
    execution_id  text not null references execution_runs(execution_id),
    ordinal       integer not null,
    record_ref    text not null,
    snapshot      jsonb not null,
    primary key (execution_id, record_ref)
);

create index if not exists idx_execution_run_records_order
    on execution_run_records (execution_id, ordinal);

comment on table execution_run_records is
    'Run-scoped snapshot of one processed SourcingRecord (JSON-safe, '
    'ADR-019). Identity is (execution_id, record_ref) per ADR-012 -- '
    'never a global product catalog.';

-- Row Level Security: same fail-closed posture as execution_runs
-- (20260817000000_execution_runs.sql) -- enabled, no policy defined.
-- Juval has no authenticated end users today (Clerk still PENDING,
-- see CLAUDE.md and ADR-005/ADR-014); access until then goes through
-- the backend's direct Postgres connection only (service_role /
-- connection string), never the anon/public API key. Not a new
-- decision -- this simply extends ADR-017's existing RLS posture to
-- the new table.
alter table execution_run_records enable row level security;
