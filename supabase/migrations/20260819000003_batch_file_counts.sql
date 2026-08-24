-- Per-file record/warning counts copied from each child ExecutionRun, so the
-- batch view reports file-level outcomes without re-reading every child run.
--
-- Additive and non-destructive: separate from 20260819000002_batches.sql on
-- purpose, because that migration may already have been applied (its
-- CREATE TABLE IF NOT EXISTS would then silently skip any edit to it).
--
-- DEFAULT 0 is correct for a rejected file: it never produced a run, so it
-- processed no rows. It is "never processed", not a measured zero.

ALTER TABLE batch_files ADD COLUMN IF NOT EXISTS records_total integer NOT NULL DEFAULT 0;
ALTER TABLE batch_files ADD COLUMN IF NOT EXISTS records_processed integer NOT NULL DEFAULT 0;
ALTER TABLE batch_files ADD COLUMN IF NOT EXISTS records_with_errors integer NOT NULL DEFAULT 0;
ALTER TABLE batch_files ADD COLUMN IF NOT EXISTS warning_count integer NOT NULL DEFAULT 0;
