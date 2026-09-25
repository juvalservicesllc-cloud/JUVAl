-- Juval — native financial records and capture diagnostics (ADR-047 §21, §22 step 6)
--
-- Additive companion tables of execution_run_records
-- (20260817000001_execution_run_records.sql). Nothing existing is altered,
-- rewritten or backfilled: a run saved before this migration, or saved
-- without the native financial flow, simply has no rows here, and absence
-- is read as "no document stored", never as evidence.
--
-- Mirrors the SQLite tables of the same names
-- (infrastructure/logging/sqlite_execution_run_store.py) column for column.
--
--   execution_run_financial_records
--       at most one versioned financial document per (execution_id, record_ref):
--       format 'juval.adr047.financial-record', v1 or v2
--       (application/financial_serialization*.py).
--   execution_run_capture_diagnostics
--       at most one capture-diagnostics set per (execution_id, record_ref):
--       format 'juval.adr047.capture-diagnostics' v1
--       (application/capture_diagnostics.py). Independent of the financial
--       table: a record without a scenario has diagnostics but no document.
--
-- Identity is (execution_id, record_ref) per ADR-012, with a composite
-- FOREIGN KEY to execution_run_records, so a document can only exist for a
-- record snapshot of the same run. Rows discarded by the importer have no
-- record_ref and therefore no row here; no surrogate identity is invented.
--
-- `payload` is TEXT, not JSONB, on purpose: it holds the exact canonical
-- serialization (json.dumps(..., sort_keys=True)) that the application reads
-- back and validates. JSONB would re-order keys and normalize the text, so
-- the stored document would no longer be byte-identical to what was written.
-- `format` / `format_version` duplicate the payload's own identity so a
-- reader can refuse a row whose columns and payload disagree.
--
-- NOT YET APPLIED to any live Supabase project. Verified only against a
-- disposable PostgreSQL cluster (tests/integration/test_postgres_financial_persistence.py).

create table if not exists execution_run_financial_records (
    execution_id    text    not null,
    record_ref      text    not null,
    format          text    not null check (format = 'juval.adr047.financial-record'),
    format_version  integer not null check (format_version >= 1),
    payload         text    not null,
    primary key (execution_id, record_ref),
    foreign key (execution_id, record_ref)
        references execution_run_records (execution_id, record_ref)
);

comment on table execution_run_financial_records is
    'ADR-047 native financial record document of one run-scoped record. '
    'payload is the exact canonical JSON text written by the application.';

create table if not exists execution_run_capture_diagnostics (
    execution_id    text    not null,
    record_ref      text    not null,
    format          text    not null check (format = 'juval.adr047.capture-diagnostics'),
    format_version  integer not null check (format_version >= 1),
    payload         text    not null,
    primary key (execution_id, record_ref),
    foreign key (execution_id, record_ref)
        references execution_run_records (execution_id, record_ref)
);

comment on table execution_run_capture_diagnostics is
    'ADR-047 capture diagnostics of one run-scoped record, independent of any '
    'financial document. payload is the exact canonical JSON text.';

-- Row Level Security: the same fail-closed posture as execution_runs and
-- execution_run_records -- enabled, no policy. The anon/authenticated API
-- keys read nothing; the backend reaches these rows through its direct
-- PostgreSQL connection as the owning role, exactly like the run itself.
-- Financial rows are therefore never more exposed than the run they belong to.
alter table execution_run_financial_records enable row level security;
alter table execution_run_capture_diagnostics enable row level security;
