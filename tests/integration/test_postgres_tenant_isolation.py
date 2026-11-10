"""ADR-056 tenant RLS against a private disposable PostgreSQL only.

Applies the real migrations (baseline, ADR-048, ADR-056) and then connects as
the runtime role `juval_backend`. Raw SQL checks the database policies on
their own, without the application's WHERE clauses; the store checks then
exercise the same path the API uses. Never a runtime or Supabase DSN.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import sql
from psycopg.conninfo import make_conninfo

from juval.application.tenancy import OutOfScopeError, Ownership, TenantScope
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.application.batch_store import RunWrite
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

from .test_postgres_financial_persistence import cluster  # noqa: F401 (fixture)
from .test_postgres_runtime_role_security import ACCESS_MIGRATION, BASELINE, MIGRATIONS, _apply, _ensure_test_roles

pytestmark = pytest.mark.skipif(
    not os.environ.get("JUVAL_POSTGRES_BIN"),
    reason="JUVAL_POSTGRES_BIN required: disposable PostgreSQL only",
)

TENANT_MIGRATIONS = ("20261110000008_tenant_ownership", "20261110000009_tenant_rls")
ISSUER = "https://idp.synthetic.example"
ORG_A = "aaaaaaaa-0000-4000-8000-00000000000a"
ORG_B = "bbbbbbbb-0000-4000-8000-00000000000b"
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)
DATA_TABLES = ("execution_runs", "execution_run_records", "execution_run_financial_records",
               "execution_run_capture_diagnostics", "batches", "batch_files")
LEGACY_RUN = "legacy-run-before-adr056"
FORMATS = {"execution_run_financial_records": "juval.adr047.financial-record",
           "execution_run_capture_diagnostics": "juval.adr047.capture-diagnostics"}


def run(execution_id: str) -> ExecutionRun:
    return ExecutionRun(
        execution_id=execution_id, started_at=NOW, finished_at=NOW, status=ExecutionStatus.SUCCESS,
        input_filename="synthetic.xlsx", input_hash="0" * 64, application_version="test",
        records_total=1, records_processed=1, records_successful=1, records_with_errors=0, warnings=0,
    )


def snapshot(ref: str = "row-1") -> dict:
    return {"record_ref": ref, "decision": "BUY", "issue_count": 0}


@pytest.fixture
def tenant_database(cluster):  # noqa: F811
    """ADR-048 database with one pre-ADR-056 run, then the ADR-056 migration."""
    _ensure_test_roles(cluster)
    dbname = "adr056_" + secrets.token_hex(6)
    with psycopg.connect(cluster, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER postgres").format(sql.Identifier(dbname)))
    admin_dsn = make_conninfo(cluster, dbname=dbname, user="postgres")
    try:
        with psycopg.connect(admin_dsn) as conn:
            for migration in BASELINE:
                _apply(conn, migration)
            _apply(conn, ACCESS_MIGRATION)
        SupabaseExecutionRunStore(admin_dsn).save_execution_run(run(LEGACY_RUN), [snapshot()])  # history
        with psycopg.connect(admin_dsn) as conn:
            for migration in TENANT_MIGRATIONS:
                _apply(conn, migration)
        admin = SupabaseExecutionRunStore(admin_dsn)
        admin.create_organization(ORG_A, "Synthetic A", "test-operator", NOW)
        admin.create_organization(ORG_B, "Synthetic B", "test-operator", NOW)
        admin.add_membership(ORG_A, ISSUER, "user-a1", "test-operator", NOW)
        admin.add_membership(ORG_B, ISSUER, "user-b", "test-operator", NOW)
        yield admin_dsn
    finally:
        with psycopg.connect(cluster, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))


@pytest.fixture
def runtime(tenant_database):
    return make_conninfo(tenant_database, user="juval_backend")


@pytest.fixture
def a_data(runtime):
    """Run, record and batch of organization A, written through the scoped store."""
    owner = Ownership(ORG_A, ISSUER, "user-a1")
    store = SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A))
    store.save_execution_run(run("run-a"), [snapshot()], owner=owner)
    batch = Batch(batch_id="batch-a", created_at=NOW, status=BatchStatus.SUCCESS,
                  files=(BatchFile(0, "a.xlsx", None, 1, BatchFileStatus.SUCCESS, "run-a-child"),))
    store.save_batch_with_runs(batch, [RunWrite(run("run-a-child"), [snapshot()])], owner)
    return store


def count_as_runtime(dsn, table, organization=None):
    with psycopg.connect(dsn) as conn:
        if organization is not None:
            conn.execute("SELECT set_config('juval.organization_id', %s, true)", (organization,))
        return conn.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))).fetchone()[0]


# --- migration shape -------------------------------------------------------


def test_no_permissive_policy_remains_and_tenancy_tables_are_read_only(tenant_database):
    with psycopg.connect(tenant_database) as conn:
        for table in DATA_TABLES:
            policies = conn.execute(
                "SELECT policyname, cmd, roles, qual, with_check FROM pg_policies "
                "WHERE schemaname='public' AND tablename=%s", (table,)).fetchall()
            assert {(name, cmd, tuple(roles)) for name, cmd, roles, _q, _w in policies} == {
                ("juval_tenant_select", "SELECT", ("juval_backend",)),
                ("juval_tenant_insert", "INSERT", ("juval_backend",)),
            }, table
            for _name, _cmd, _roles, qual, check in policies:
                assert "juval.organization_id" in (qual or check), table
        for table, allowed in (("organizations", set()), ("organization_memberships", {"SELECT"})):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                granted = conn.execute("SELECT has_table_privilege('juval_backend', %s, %s)",
                                       (f"public.{table}", privilege)).fetchone()[0]
                assert granted == (privilege in allowed), (table, privilege)
                for role in ("anon", "authenticated", "authenticator", "service_role"):
                    assert not conn.execute("SELECT has_table_privilege(%s, %s, %s)",
                                            (role, f"public.{table}", privilege)).fetchone()[0]


# --- the database policy on its own (raw SQL, no application filter) -------------


def test_rls_shows_each_organization_only_its_rows(runtime, a_data):
    with psycopg.connect(runtime) as conn:  # the owner's own child rows are accepted
        conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_A,))
        for table in ("execution_run_financial_records", "execution_run_capture_diagnostics"):
            conn.execute(sql.SQL("INSERT INTO public.{} (execution_id, record_ref, format, format_version, payload) "
                                 "VALUES ('run-a', 'row-1', %s, 1, '{{}}')").format(sql.Identifier(table)),
                         (FORMATS[table],))
    for table in DATA_TABLES:
        assert count_as_runtime(runtime, table) == 0, table               # no binding: nothing
        assert count_as_runtime(runtime, table, ORG_B) == 0, table        # other organization: nothing
        assert count_as_runtime(runtime, table, ORG_A) > 0, table         # own organization


def test_rls_refuses_writes_into_another_organization(runtime, a_data):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(runtime) as conn:
            conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_B,))
            conn.execute("INSERT INTO execution_run_records (execution_id, ordinal, record_ref, snapshot) "
                         "VALUES ('run-a', 9, 'smuggled', '{}'::jsonb)")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_B))._connect().execute(
            "INSERT INTO execution_runs (execution_id, started_at, status, input_filename, input_hash, "
            "application_version, records_total, records_processed, records_successful, records_with_errors, "
            "warnings, organization_id, created_by_issuer, created_by_subject) VALUES "
            "('forged', now(), 'SUCCESS', 'x', 'x', 'x', 0, 0, 0, 0, 0, %s, 'i', 's')", (ORG_A,))


def test_the_runtime_role_cannot_write_unowned_rows(runtime):
    with pytest.raises(psycopg.Error):
        SupabaseExecutionRunStore(runtime).save_execution_run(run("unowned"))


def test_history_is_quarantined(runtime, tenant_database, a_data):
    with psycopg.connect(tenant_database) as conn:
        assert conn.execute("SELECT organization_id FROM execution_runs WHERE execution_id=%s",
                            (LEGACY_RUN,)).fetchone() == (None,)
    for organization in (ORG_A, ORG_B):
        assert SupabaseExecutionRunStore(runtime).scoped(TenantScope(organization)).load_execution_run(LEGACY_RUN) is None
    assert LEGACY_RUN not in [r.execution_id for r in SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_A)).list_execution_runs()]


def test_membership_lookup_sees_only_the_bound_identity(runtime):
    store = SupabaseExecutionRunStore(runtime)
    assert store.organization_ids_for(ISSUER, "user-a1") == [ORG_A]
    assert store.organization_ids_for(ISSUER, "user-b") == [ORG_B]
    assert store.organization_ids_for("https://other.example", "user-a1") == []
    assert count_as_runtime(runtime, "organization_memberships") == 0     # no identity bound: no row
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        store.add_membership(ORG_B, ISSUER, "user-a1-elsewhere", "attacker", NOW)


# --- the store the API uses ------------------------------------------------------


def test_scoped_store_isolates_runs_batches_and_children(runtime, a_data):
    store_a = a_data
    store_b = SupabaseExecutionRunStore(runtime).scoped(TenantScope(ORG_B))
    assert store_a.load_execution_run("run-a") is not None
    assert {r.execution_id for r in store_a.list_execution_runs()} == {"run-a", "run-a-child"}
    assert store_a.load_batch("batch-a") is not None
    assert store_b.load_execution_run("run-a") is None
    assert store_b.list_execution_runs() == []
    assert store_b.load_batch("batch-a") is None
    for read in (lambda: store_b.load_records("run-a"), lambda: store_b.load_record("run-a", "row-1"),
                 lambda: store_b.decision_counts(["run-a"]), lambda: store_b.get_run_analytics("run-a"),
                 lambda: store_b.load_batch_for_run("run-a-child")):
        with pytest.raises(OutOfScopeError):
            read()


# --- rollback ---------------------------------------------------------------------


def test_rollback_restores_the_adr048_policies(tenant_database):
    with psycopg.connect(tenant_database) as conn:
        for migration in reversed(TENANT_MIGRATIONS):
            conn.execute((MIGRATIONS / f"{migration}.down.sql").read_text(encoding="utf-8"))
    with psycopg.connect(tenant_database) as conn:
        names = {row[0] for row in conn.execute(
            "SELECT DISTINCT policyname FROM pg_policies WHERE schemaname='public' AND tablename = ANY(%s)",
            (list(DATA_TABLES),))}
        assert names == {"juval_backend_select", "juval_backend_insert"}
        assert conn.execute("SELECT to_regclass('public.organizations')").fetchone() == (None,)


# --- audit 2026-11-10 ------------------------------------------------------------


def test_the_context_ends_with_its_transaction_on_a_reused_connection(runtime, a_data):
    """Pooled or reused connections never carry an organization into the next transaction."""
    with psycopg.connect(runtime) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_A,))
            assert conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0] == 2
        with conn.transaction():
            assert conn.execute("SELECT current_setting('juval.organization_id', true)").fetchone()[0] in (None, "")
            assert conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0] == 0
        with conn.transaction():
            conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_B,))
            assert conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0] == 0


_FORGED_RUN = ("INSERT INTO execution_runs (execution_id, started_at, status, input_filename, input_hash, "
               "application_version, records_total, records_processed, records_successful, records_with_errors, "
               "warnings, organization_id, created_by_issuer, created_by_subject) VALUES "
               "(%s, now(), 'SUCCESS', 'x', 'x', 'x', 0, 0, 0, 0, 0, %s, 'i', 's')")


def test_writes_need_a_context_and_a_real_organization(runtime):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):     # owned row, no context
        with psycopg.connect(runtime) as conn:
            conn.execute(_FORGED_RUN, ("no-context", ORG_A))
    ghost = "99999999-9999-4999-8999-999999999999"
    with psycopg.connect(runtime) as conn:                          # unknown organization: nothing visible
        conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ghost,))
        assert conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0] == 0
    with pytest.raises(psycopg.errors.ForeignKeyViolation):        # and nothing can be written for it
        with psycopg.connect(runtime) as conn:
            conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ghost,))
            conn.execute(_FORGED_RUN, ("ghost-run", ghost))


def test_a_batch_cannot_point_at_another_organizations_run(runtime, a_data):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with psycopg.connect(runtime) as conn:
            conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_B,))
            conn.execute("INSERT INTO batches (batch_id, created_at, status, organization_id, created_by_issuer, "
                         "created_by_subject) VALUES ('batch-b', now(), 'SUCCESS', %s, 'i', 's')", (ORG_B,))
            conn.execute("INSERT INTO batch_files (batch_id, ordinal, filename, size_bytes, status, execution_id, "
                         "warnings, errors) VALUES ('batch-b', 0, 'x', 1, 'SUCCESS', 'run-a', '[]', '[]')")


def test_the_runtime_role_cannot_update_or_delete_ownership(runtime, a_data):
    for statement in ("UPDATE execution_runs SET organization_id = %s", "DELETE FROM execution_runs WHERE organization_id = %s",
                      "UPDATE organization_memberships SET organization_id = %s"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(runtime) as conn:
                conn.execute("SELECT set_config('juval.organization_id', %s, true)", (ORG_A,))
                conn.execute(statement, (ORG_B,))


def test_the_table_owner_bypasses_rls_so_the_admin_dsn_is_privileged(tenant_database, a_data):
    """Documented, not a defect: the owner (postgres) is the migration and
    operator identity and is not subject to non-forced RLS (ADR-048 shape)."""
    with psycopg.connect(tenant_database) as conn:
        assert conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0] == 3   # A's two and the legacy run


def test_the_rls_migration_refuses_a_runtime_role_that_could_bypass_it(cluster):  # noqa: F811
    _ensure_test_roles(cluster)
    dbname = "adr056_role_" + secrets.token_hex(6)
    with psycopg.connect(cluster, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER postgres").format(sql.Identifier(dbname)))
    admin_dsn = make_conninfo(cluster, dbname=dbname, user="postgres")
    try:
        with psycopg.connect(admin_dsn) as conn:
            for migration in (*BASELINE, ACCESS_MIGRATION, TENANT_MIGRATIONS[0]):
                _apply(conn, migration)
        with psycopg.connect(cluster, autocommit=True) as conn:
            conn.execute("ALTER ROLE juval_backend BYPASSRLS")
        with pytest.raises(psycopg.errors.RaiseException, match="BYPASSRLS"):
            with psycopg.connect(admin_dsn) as conn:
                _apply(conn, TENANT_MIGRATIONS[1])
    finally:
        with psycopg.connect(cluster, autocommit=True) as conn:
            conn.execute("ALTER ROLE juval_backend NOBYPASSRLS")
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))


def test_offboarding_is_an_admin_action_that_takes_effect_at_once(runtime, tenant_database):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        SupabaseExecutionRunStore(runtime).remove_membership(ISSUER, "user-b")
    assert SupabaseExecutionRunStore(tenant_database).remove_membership(ISSUER, "user-b") == ORG_B
    assert SupabaseExecutionRunStore(runtime).organization_ids_for(ISSUER, "user-b") == []
    assert SupabaseExecutionRunStore(tenant_database).remove_membership(ISSUER, "user-b") is None
