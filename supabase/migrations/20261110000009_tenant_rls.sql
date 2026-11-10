-- ADR-056 (2/2): tenant row-level security for the ADR-048 runtime role.
--
-- Run as postgres, after 20261005000007 (ADR-048) and 20261110000008. NOT
-- applied to any live database by this repository.
--
--   * The runtime role reads only its own membership row and cannot write
--     organizations or memberships (an operator action).
--   * The ADR-048 `USING (true)` policies on the six data tables are replaced
--     by policies that match only the organization bound to the current
--     transaction with set_config('juval.organization_id', ..., true). No
--     binding: no rows, no inserts. NULL-owned history never matches. Child
--     tables follow their parent run or batch explicitly.
--
-- This is defense in depth against a query that forgets its organization
-- filter. It does not protect against a compromised backend, which chooses
-- the binding itself.

DO $tenant_preconditions$
BEGIN
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'ADR-056 migration must run as postgres';
    END IF;
    IF to_regclass('public.organization_memberships') IS NULL THEN
        RAISE EXCEPTION 'ADR-056 RLS requires 20261110000008_tenant_ownership';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'juval_backend') THEN
        RAISE EXCEPTION 'ADR-056 requires the ADR-048 juval_backend role';
    END IF;
    -- RLS binds only a role that is neither superuser nor BYPASSRLS, and a
    -- membership could hand it either. Re-checked here because the role may
    -- have changed since 20261005000007 checked it.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'juval_backend'
                AND (rolsuper OR rolbypassrls OR rolinherit))
       OR EXISTS (SELECT 1 FROM pg_auth_members m
                   WHERE m.member = 'juval_backend'::regrole) THEN
        RAISE EXCEPTION 'juval_backend must not be superuser, BYPASSRLS, INHERIT or a member of another role';
    END IF;
    IF (SELECT count(*) FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename IN ('execution_runs', 'execution_run_records',
                             'execution_run_financial_records',
                             'execution_run_capture_diagnostics', 'batches', 'batch_files')
           AND policyname IN ('juval_backend_select', 'juval_backend_insert')) <> 12 THEN
        RAISE EXCEPTION 'ADR-056 requires exactly the ADR-048 policies on the data tables';
    END IF;
END
$tenant_preconditions$;

-- Tenancy tables: read-only for the runtime role --------------------------------

REVOKE ALL PRIVILEGES ON TABLE public.organizations, public.organization_memberships
FROM PUBLIC, anon, authenticated, authenticator, service_role, juval_backend;
GRANT SELECT ON TABLE public.organization_memberships TO juval_backend;

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations NO FORCE ROW LEVEL SECURITY;
ALTER TABLE public.organization_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_memberships NO FORCE ROW LEVEL SECURITY;
-- The runtime role sees only the membership of the identity it bound.
CREATE POLICY juval_backend_own_membership ON public.organization_memberships
    FOR SELECT TO juval_backend
    USING (issuer = current_setting('juval.issuer', true)
           AND subject = current_setting('juval.subject', true));

-- Tenant policies (replace ADR-048 USING (true)) ---------------------------------

DROP POLICY juval_backend_select ON public.execution_runs;
DROP POLICY juval_backend_insert ON public.execution_runs;
CREATE POLICY juval_tenant_select ON public.execution_runs FOR SELECT TO juval_backend
    USING (organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid);
CREATE POLICY juval_tenant_insert ON public.execution_runs FOR INSERT TO juval_backend
    WITH CHECK (organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid);

DROP POLICY juval_backend_select ON public.execution_run_records;
DROP POLICY juval_backend_insert ON public.execution_run_records;
CREATE POLICY juval_tenant_select ON public.execution_run_records FOR SELECT TO juval_backend
    USING (EXISTS (SELECT 1 FROM public.execution_runs r
                    WHERE r.execution_id = execution_run_records.execution_id
                      AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));
CREATE POLICY juval_tenant_insert ON public.execution_run_records FOR INSERT TO juval_backend
    WITH CHECK (EXISTS (SELECT 1 FROM public.execution_runs r
                         WHERE r.execution_id = execution_run_records.execution_id
                           AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));

DROP POLICY juval_backend_select ON public.execution_run_financial_records;
DROP POLICY juval_backend_insert ON public.execution_run_financial_records;
CREATE POLICY juval_tenant_select ON public.execution_run_financial_records FOR SELECT TO juval_backend
    USING (EXISTS (SELECT 1 FROM public.execution_runs r
                    WHERE r.execution_id = execution_run_financial_records.execution_id
                      AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));
CREATE POLICY juval_tenant_insert ON public.execution_run_financial_records FOR INSERT TO juval_backend
    WITH CHECK (EXISTS (SELECT 1 FROM public.execution_runs r
                         WHERE r.execution_id = execution_run_financial_records.execution_id
                           AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));

DROP POLICY juval_backend_select ON public.execution_run_capture_diagnostics;
DROP POLICY juval_backend_insert ON public.execution_run_capture_diagnostics;
CREATE POLICY juval_tenant_select ON public.execution_run_capture_diagnostics FOR SELECT TO juval_backend
    USING (EXISTS (SELECT 1 FROM public.execution_runs r
                    WHERE r.execution_id = execution_run_capture_diagnostics.execution_id
                      AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));
CREATE POLICY juval_tenant_insert ON public.execution_run_capture_diagnostics FOR INSERT TO juval_backend
    WITH CHECK (EXISTS (SELECT 1 FROM public.execution_runs r
                         WHERE r.execution_id = execution_run_capture_diagnostics.execution_id
                           AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));

DROP POLICY juval_backend_select ON public.batches;
DROP POLICY juval_backend_insert ON public.batches;
CREATE POLICY juval_tenant_select ON public.batches FOR SELECT TO juval_backend
    USING (organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid);
CREATE POLICY juval_tenant_insert ON public.batches FOR INSERT TO juval_backend
    WITH CHECK (organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid);

DROP POLICY juval_backend_select ON public.batch_files;
DROP POLICY juval_backend_insert ON public.batch_files;
CREATE POLICY juval_tenant_select ON public.batch_files FOR SELECT TO juval_backend
    USING (EXISTS (SELECT 1 FROM public.batches b
                    WHERE b.batch_id = batch_files.batch_id
                      AND b.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid));
-- A batch file may name only a run of the same organization (or none, for a
-- rejected file): a batch can never point at another organization's run.
CREATE POLICY juval_tenant_insert ON public.batch_files FOR INSERT TO juval_backend
    WITH CHECK (EXISTS (SELECT 1 FROM public.batches b
                         WHERE b.batch_id = batch_files.batch_id
                           AND b.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid)
                AND (batch_files.execution_id IS NULL
                     OR EXISTS (SELECT 1 FROM public.execution_runs r
                                 WHERE r.execution_id = batch_files.execution_id
                                   AND r.organization_id = NULLIF(current_setting('juval.organization_id', true), '')::uuid)));

-- Postconditions -----------------------------------------------------------------

DO $tenant_postconditions$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_policies
         WHERE schemaname = 'public'
           AND tablename IN ('execution_runs', 'execution_run_records',
                             'execution_run_financial_records',
                             'execution_run_capture_diagnostics', 'batches', 'batch_files',
                             'organizations', 'organization_memberships')
           AND (btrim(coalesce(qual, '')) = 'true' OR btrim(coalesce(with_check, '')) = 'true')
    ) THEN
        RAISE EXCEPTION 'a permissive USING (true) policy remains on a tenant table';
    END IF;
    -- RLS applies to juval_backend only while it does not own the table (the
    -- owner bypasses non-forced RLS). The owner stays postgres, for migrations
    -- and the operator tool; FORCE is therefore not used (same as ADR-048).
    IF (SELECT count(*) FROM pg_class
         WHERE relnamespace = 'public'::regnamespace
           AND relname IN ('execution_runs', 'execution_run_records',
                           'execution_run_financial_records',
                           'execution_run_capture_diagnostics', 'batches', 'batch_files',
                           'organizations', 'organization_memberships')
           AND relrowsecurity
           AND relowner <> 'juval_backend'::regrole) <> 8 THEN
        RAISE EXCEPTION 'every tenant table must have RLS and must not be owned by the runtime role';
    END IF;
END
$tenant_postconditions$;
