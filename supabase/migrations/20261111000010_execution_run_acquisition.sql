-- ADR-058: acquisition sources and results recorded per ExecutionRun.
--
-- Run as postgres, after 20261110000009_tenant_rls.sql. NOT applied to any
-- live database by this repository: applying it to Supabase is an explicit
-- owner action.
--
--   * Two nullable text columns on execution_runs (PD-5): the canonical JSON
--     documents juval.adr058.acquisition-configuration and
--     juval.adr058.acquisition-execution, written by the run's own INSERT.
--   * Both NULL means NOT_RECORDED: every existing row stays that way and
--     nothing here backfills it. One NULL is refused by the CHECK (P3).
--   * No new table, grant or policy. Table-level privileges (ADR-048) cover the
--     new columns, the ADR-056 tenant policies filter them with their row, and
--     juval_backend still has no UPDATE: the documents cannot be changed after
--     the INSERT (P2).
--
-- ADD COLUMN without a default and a CHECK that existing NULL rows satisfy do
-- not rewrite the table.

DO $adr058_preconditions$
BEGIN
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'ADR-058 migration must run as postgres';
    END IF;
    IF to_regclass('public.execution_runs') IS NULL THEN
        RAISE EXCEPTION 'ADR-058 requires the execution_runs table';
    END IF;
END
$adr058_preconditions$;

ALTER TABLE public.execution_runs
    ADD COLUMN acquisition_configuration text,
    ADD COLUMN acquisition_execution text;

ALTER TABLE public.execution_runs
    ADD CONSTRAINT execution_runs_acquisition_pair
    CHECK ((acquisition_configuration IS NULL) = (acquisition_execution IS NULL));

COMMENT ON COLUMN public.execution_runs.acquisition_configuration IS
    'ADR-058 juval.adr058.acquisition-configuration v1, canonical JSON text. NULL with acquisition_execution = NOT_RECORDED.';
COMMENT ON COLUMN public.execution_runs.acquisition_execution IS
    'ADR-058 juval.adr058.acquisition-execution v1, canonical JSON text, written by the same INSERT as the run.';
