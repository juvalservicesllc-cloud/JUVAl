-- ADR-048: direct PostgreSQL runtime access boundary.
--
-- Provision juval_backend operationally before applying this migration. Never
-- place its password in SQL or migration history. This migration must run as
-- postgres, the current migration/object creator. It intentionally fails
-- closed if unexpected global table/sequence defaults or pre-existing target
-- policies are found.

DO $migration_preconditions$
DECLARE
    runtime_role record;
    restricted_roles text[] := ARRAY[
        'anon', 'authenticated', 'authenticator', 'service_role', 'PUBLIC'
    ];
    role_name text;
BEGIN
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'ADR-048 migration must run as postgres';
    END IF;

    SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication,
           rolbypassrls, rolinherit, rolcanlogin
      INTO runtime_role
      FROM pg_roles
     WHERE rolname = 'juval_backend';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'ADR-048 requires pre-provisioned juval_backend';
    END IF;
    IF runtime_role.rolsuper OR runtime_role.rolcreatedb
       OR runtime_role.rolcreaterole OR runtime_role.rolreplication
       OR runtime_role.rolbypassrls OR runtime_role.rolinherit
       OR NOT runtime_role.rolcanlogin THEN
        RAISE EXCEPTION 'juval_backend role attributes violate ADR-048';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members m
          JOIN pg_roles r ON r.oid = m.member OR r.oid = m.roleid
         WHERE r.rolname = 'juval_backend'
    ) THEN
        RAISE EXCEPTION 'juval_backend must have no role memberships';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relname = ANY (ARRAY[
               'execution_runs', 'execution_run_records',
               'execution_run_financial_records',
               'execution_run_capture_diagnostics', 'batches', 'batch_files',
               'identity_sessions', 'identity_oauth_transactions'
           ])
           AND c.relowner = 'juval_backend'::regrole
    ) THEN
        RAISE EXCEPTION 'juval_backend must not own internal tables';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_namespace n
         WHERE n.nspname = 'public'
           AND n.nspowner = 'juval_backend'::regrole
    ) THEN
        RAISE EXCEPTION 'juval_backend must not own the public schema';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_policies p
         WHERE p.schemaname = 'public'
           AND p.tablename = ANY (ARRAY[
               'execution_runs', 'execution_run_records',
               'execution_run_financial_records',
               'execution_run_capture_diagnostics', 'batches', 'batch_files',
               'identity_sessions', 'identity_oauth_transactions'
           ])
    ) THEN
        RAISE EXCEPTION 'unexpected existing policies on ADR-048 target tables';
    END IF;

    FOREACH role_name IN ARRAY ARRAY[
        'anon', 'authenticated', 'authenticator', 'service_role'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            RAISE EXCEPTION 'ADR-048 requires role % to exist', role_name;
        END IF;
    END LOOP;

    -- Schema-specific revokes cannot cancel global default ACL grants.
    -- Refuse to proceed if a global TABLES or SEQUENCES grant would reappear
    -- for any principal denied by this boundary.
    IF EXISTS (
        SELECT 1
          FROM pg_default_acl d
          CROSS JOIN LATERAL aclexplode(d.defaclacl) a
         WHERE d.defaclrole = 'postgres'::regrole
           AND d.defaclnamespace = 0
           AND d.defaclobjtype IN ('r', 'S')
           AND (
               a.grantee = 0
               OR a.grantee IN (
                   SELECT oid FROM pg_roles
                    WHERE rolname = ANY (restricted_roles || ARRAY['juval_backend'])
               )
           )
    ) THEN
        RAISE EXCEPTION 'unapproved global table/sequence default ACL for postgres';
    END IF;
END
$migration_preconditions$;

-- Objects created by postgres in public do not inherit table/sequence access.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, authenticator,
        service_role, juval_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated, authenticator,
        service_role, juval_backend;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated,
        authenticator, service_role, juval_backend;

-- PostgreSQL grants EXECUTE on new functions to PUBLIC globally by default.
-- This owner-scoped global revoke is required because a schema revoke cannot
-- cancel a global default. It does not alter defaults for other owners.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated,
        authenticator, service_role, juval_backend;

-- Existing internal tables: remove all direct table rights from public/API
-- principals, service_role, authenticator, and reset the runtime before
-- applying the exact per-table allowlist below. Ownership is untouched.
REVOKE ALL PRIVILEGES ON TABLE
    public.execution_runs,
    public.execution_run_records,
    public.execution_run_financial_records,
    public.execution_run_capture_diagnostics,
    public.batches,
    public.batch_files,
    public.identity_sessions,
    public.identity_oauth_transactions
FROM PUBLIC, anon, authenticated, authenticator, service_role, juval_backend;

GRANT SELECT, INSERT ON TABLE public.execution_runs TO juval_backend;
GRANT SELECT, INSERT ON TABLE public.execution_run_records TO juval_backend;
GRANT SELECT, INSERT ON TABLE public.execution_run_financial_records TO juval_backend;
GRANT SELECT, INSERT ON TABLE public.execution_run_capture_diagnostics TO juval_backend;
GRANT SELECT, INSERT ON TABLE public.batches TO juval_backend;
GRANT SELECT, INSERT ON TABLE public.batch_files TO juval_backend;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.identity_sessions TO juval_backend;
GRANT SELECT, INSERT, DELETE ON TABLE public.identity_oauth_transactions TO juval_backend;

-- RLS remains enabled and not forced. Policies are operation-specific and
-- authorize only the direct PostgreSQL runtime role.
ALTER TABLE public.execution_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_runs NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.execution_runs
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_runs
    FOR INSERT TO juval_backend WITH CHECK (true);

ALTER TABLE public.execution_run_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_run_records NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.execution_run_records
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_run_records
    FOR INSERT TO juval_backend WITH CHECK (true);

ALTER TABLE public.execution_run_financial_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_run_financial_records NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.execution_run_financial_records
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_run_financial_records
    FOR INSERT TO juval_backend WITH CHECK (true);

ALTER TABLE public.execution_run_capture_diagnostics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.execution_run_capture_diagnostics NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.execution_run_capture_diagnostics
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.execution_run_capture_diagnostics
    FOR INSERT TO juval_backend WITH CHECK (true);

ALTER TABLE public.batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batches NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.batches
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.batches
    FOR INSERT TO juval_backend WITH CHECK (true);

ALTER TABLE public.batch_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batch_files NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.batch_files
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.batch_files
    FOR INSERT TO juval_backend WITH CHECK (true);

ALTER TABLE public.identity_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.identity_sessions NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.identity_sessions
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.identity_sessions
    FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_update ON public.identity_sessions
    FOR UPDATE TO juval_backend USING (true) WITH CHECK (true);
CREATE POLICY juval_backend_delete ON public.identity_sessions
    FOR DELETE TO juval_backend USING (true);

ALTER TABLE public.identity_oauth_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.identity_oauth_transactions NO FORCE ROW LEVEL SECURITY;
CREATE POLICY juval_backend_select ON public.identity_oauth_transactions
    FOR SELECT TO juval_backend USING (true);
CREATE POLICY juval_backend_insert ON public.identity_oauth_transactions
    FOR INSERT TO juval_backend WITH CHECK (true);
CREATE POLICY juval_backend_delete ON public.identity_oauth_transactions
    FOR DELETE TO juval_backend USING (true);

-- Verify effective privileges as well as direct ACLs. A membership inherited
-- from another role must not silently defeat the intended denials.
DO $migration_postconditions$
DECLARE
    target record;
    privilege_name text;
    denied_role text;
    target_name text;
    server_version integer := current_setting('server_version_num')::integer;
    allowed_privileges text[];
    table_names text[] := ARRAY[
        'execution_runs', 'execution_run_records',
        'execution_run_financial_records', 'execution_run_capture_diagnostics',
        'batches', 'batch_files', 'identity_sessions', 'identity_oauth_transactions'
    ];
    table_privileges text[] := ARRAY[
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'
    ];
BEGIN
    -- MAINTAIN exists only on PostgreSQL 17+. Do not ask older servers to
    -- parse it; on 17+, verify effective privileges for every named role.
    IF server_version >= 170000 THEN
        table_privileges := array_append(table_privileges, 'MAINTAIN');
    END IF;

    FOR target IN
        SELECT * FROM (VALUES
            ('execution_runs', ARRAY['SELECT','INSERT']::text[]),
            ('execution_run_records', ARRAY['SELECT','INSERT']::text[]),
            ('execution_run_financial_records', ARRAY['SELECT','INSERT']::text[]),
            ('execution_run_capture_diagnostics', ARRAY['SELECT','INSERT']::text[]),
            ('batches', ARRAY['SELECT','INSERT']::text[]),
            ('batch_files', ARRAY['SELECT','INSERT']::text[]),
            ('identity_sessions', ARRAY['SELECT','INSERT','UPDATE','DELETE']::text[]),
            ('identity_oauth_transactions', ARRAY['SELECT','INSERT','DELETE']::text[])
        ) AS expected(table_name, privileges)
    LOOP
        target_name := format('public.%I', target.table_name);
        FOR privilege_name IN SELECT unnest(table_privileges) LOOP
            IF has_table_privilege('juval_backend', target_name, privilege_name)
               IS DISTINCT FROM (privilege_name = ANY (target.privileges)) THEN
                RAISE EXCEPTION 'effective runtime privilege mismatch for %.%', target.table_name, privilege_name;
            END IF;
            FOREACH denied_role IN ARRAY ARRAY[
                'anon', 'authenticated', 'authenticator', 'service_role'
            ] LOOP
                IF has_table_privilege(denied_role, target_name, privilege_name) THEN
                    RAISE EXCEPTION 'denied role % has effective %.% privilege', denied_role, target.table_name, privilege_name;
                END IF;
            END LOOP;
        END LOOP;
    END LOOP;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
          CROSS JOIN LATERAL aclexplode(c.relacl) a
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relname = ANY (table_names)
           AND a.grantee = 0
    ) THEN
        RAISE EXCEPTION 'PUBLIC has a direct ACL on an internal table';
    END IF;

    -- PUBLIC is a pseudo-role, so its effective table privilege is represented
    -- by direct PUBLIC ACL entries. Denied-role checks above include inherited
    -- PUBLIC grants through has_table_privilege().
    IF server_version >= 170000 AND EXISTS (
        SELECT 1
          FROM pg_class c
          CROSS JOIN LATERAL aclexplode(c.relacl) a
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relname = ANY (table_names)
           AND a.grantee = 0
           AND a.privilege_type = 'MAINTAIN'
    ) THEN
        RAISE EXCEPTION 'PUBLIC has effective MAINTAIN on an internal table';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_class c
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relname = ANY (table_names)
           AND (NOT c.relrowsecurity OR c.relforcerowsecurity)
    ) THEN
        RAISE EXCEPTION 'internal table RLS state differs from ADR-048';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class c
         WHERE c.relnamespace = 'public'::regnamespace
           AND c.relname = ANY (table_names)
           AND c.relowner = 'juval_backend'::regrole
    ) THEN
        RAISE EXCEPTION 'juval_backend owns an internal table';
    END IF;
END
$migration_postconditions$;
