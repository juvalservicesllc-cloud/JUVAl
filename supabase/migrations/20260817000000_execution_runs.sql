-- Juval — execution_runs (Supabase/PostgreSQL persistence, ADR-017)
--
-- Mirrors exactly the same fields as domain/execution_run.py::ExecutionRun
-- and the SQLite schema already accepted in ADR-013
-- (infrastructure/logging/sqlite_execution_run_store.py). No column here
-- was invented for this migration -- every column maps to a field that
-- already exists on ExecutionRun. No SourcingRecord/business data is
-- persisted here (out of ADR-013's scope, unchanged).
--
-- NOT YET APPLIED to any live Supabase project. This file documents the
-- schema Juval would create there; running it requires the Supabase CLI
-- (`supabase db push` / `supabase migration up`) or the SQL editor of an
-- actual Supabase project, neither of which is available in this
-- environment (see docs/architecture/SUPABASE.md "Estado").

create table if not exists execution_runs (
    execution_id           text primary key,
    started_at             timestamptz not null,
    finished_at            timestamptz,
    status                 text not null,
    input_filename         text not null,
    input_hash             text not null,
    application_version    text not null,
    records_total          integer not null,
    records_processed      integer not null,
    records_successful     integer not null,
    records_with_errors    integer not null,
    warnings                integer not null
);

comment on table execution_runs is
    'Audit record for one Juval pipeline run (domain.execution_run.ExecutionRun). '
    'Mirrors the SQLite schema of ADR-013 exactly -- see ADR-017.';

-- Row Level Security: enabled, no policy defined yet. Per ADR-017, Juval
-- has no authenticated end users today (Clerk is still PENDING, see
-- CLAUDE.md §14 and ADR-005/ADR-014) -- there is no user identity to
-- write a meaningful per-row policy against yet. Enabling RLS with zero
-- policies means the table is inaccessible via the anon/public API key
-- by default (fail-closed), which is the correct posture until an
-- authenticated caller model exists. Access until then is expected to go
-- through the service_role key from the backend only (never exposed to
-- the frontend, see docs/architecture/SUPABASE.md §"Secrets").
alter table execution_runs enable row level security;
