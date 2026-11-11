-- Rollback for 20261111000010_execution_run_acquisition.sql
--
-- Drops only the ADR-058 constraint and columns. Every run stays readable as
-- NOT_RECORDED. It DOES delete every stored acquisition document, and they
-- cannot be rebuilt from the remaining tables (ADR-058 forbids reconstructing
-- them from snapshots). Export them first if they must be kept. Verified only
-- against a disposable PostgreSQL cluster.
ALTER TABLE public.execution_runs DROP CONSTRAINT IF EXISTS execution_runs_acquisition_pair;
ALTER TABLE public.execution_runs
    DROP COLUMN IF EXISTS acquisition_execution,
    DROP COLUMN IF EXISTS acquisition_configuration;
