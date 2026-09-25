-- Rollback for 20260925000005_execution_run_financial_records.sql
--
-- Drops only the two ADR-047 tables. execution_runs, execution_run_records
-- and batches are untouched, so every run and record snapshot stays readable
-- as a legacy run (no financial document, no diagnostics set).
--
-- It DOES delete every stored financial document and diagnostics set, and
-- they cannot be rebuilt from the remaining tables. Export them first if they
-- must be kept. Verified only against a disposable PostgreSQL cluster.
drop table if exists execution_run_capture_diagnostics;
drop table if exists execution_run_financial_records;
