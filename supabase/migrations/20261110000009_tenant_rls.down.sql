-- Rollback for 20261110000009_tenant_rls.sql (run as postgres).
--
-- Restores the ADR-048 runtime policies, which do NOT isolate tenants: after
-- this rollback every authenticated reader of the API can again reach every
-- run of every organization (SEC-01D finding). Roll back only with the backend
-- offline. Ownership data is kept (see the 20261110000008 rollback).
-- Verified only against a disposable PostgreSQL cluster.

DROP POLICY juval_tenant_select ON public.execution_runs;
DROP POLICY juval_tenant_insert ON public.execution_runs;
DROP POLICY juval_tenant_select ON public.execution_run_records;
DROP POLICY juval_tenant_insert ON public.execution_run_records;
DROP POLICY juval_tenant_select ON public.execution_run_financial_records;
DROP POLICY juval_tenant_insert ON public.execution_run_financial_records;
DROP POLICY juval_tenant_select ON public.execution_run_capture_diagnostics;
DROP POLICY juval_tenant_insert ON public.execution_run_capture_diagnostics;
DROP POLICY juval_tenant_select ON public.batches;
DROP POLICY juval_tenant_insert ON public.batches;
DROP POLICY juval_tenant_select ON public.batch_files;
DROP POLICY juval_tenant_insert ON public.batch_files;

CREATE POLICY juval_backend_select ON public.execution_runs FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_runs FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_select ON public.execution_run_records FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_run_records FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_select ON public.execution_run_financial_records FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_run_financial_records FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_select ON public.execution_run_capture_diagnostics FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_run_capture_diagnostics FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_select ON public.batches FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.batches FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_select ON public.batch_files FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.batch_files FOR INSERT TO juval_backend WITH CHECK (true);

DROP POLICY juval_backend_own_membership ON public.organization_memberships;
REVOKE ALL PRIVILEGES ON TABLE public.organizations, public.organization_memberships FROM juval_backend;
