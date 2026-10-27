"""ADR-048 access-boundary checks against private disposable PostgreSQL only."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import sql
from psycopg.conninfo import make_conninfo

from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore
from .test_postgres_financial_persistence import cluster

pytestmark = pytest.mark.skipif(
    not os.environ.get("JUVAL_POSTGRES_BIN"),
    reason="JUVAL_POSTGRES_BIN required: disposable PostgreSQL only",
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "supabase" / "migrations"
BASELINE = (
    "20260817000000_execution_runs",
    "20260817000001_execution_run_records",
    "20260819000002_batches",
    "20260819000003_batch_file_counts",
    "20260909000004_identity_sessions",
    "20260925000005_execution_run_financial_records",
    "20260928000006_batch_table_security",
)
ACCESS_MIGRATION = "20261005000007_database_access_boundary"
TABLES = (
    "execution_runs",
    "execution_run_records",
    "execution_run_financial_records",
    "execution_run_capture_diagnostics",
    "batches",
    "batch_files",
    "identity_sessions",
    "identity_oauth_transactions",
)
DENIED_ROLES = ("anon", "authenticated", "authenticator", "service_role")
PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
EXPECTED = {
    "execution_runs": {"SELECT", "INSERT"},
    "execution_run_records": {"SELECT", "INSERT"},
    "execution_run_financial_records": {"SELECT", "INSERT"},
    "execution_run_capture_diagnostics": {"SELECT", "INSERT"},
    "batches": {"SELECT", "INSERT"},
    "batch_files": {"SELECT", "INSERT"},
    "identity_sessions": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "identity_oauth_transactions": {"SELECT", "INSERT", "DELETE"},
}
EXPECTED_POLICIES = {
    "execution_runs": {"SELECT", "INSERT"},
    "execution_run_records": {"SELECT", "INSERT"},
    "execution_run_financial_records": {"SELECT", "INSERT"},
    "execution_run_capture_diagnostics": {"SELECT", "INSERT"},
    "batches": {"SELECT", "INSERT"},
    "batch_files": {"SELECT", "INSERT"},
    "identity_sessions": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "identity_oauth_transactions": {"SELECT", "INSERT", "DELETE"},
}


def _ensure_test_roles(cluster_dsn: str) -> None:
    with psycopg.connect(cluster_dsn) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'postgres'").fetchone():
            conn.execute("CREATE ROLE postgres LOGIN SUPERUSER")
        else:
            assert conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname='postgres'").fetchone() == (True,)
        for name in ("juval_backend", *DENIED_ROLES, "public_probe"):
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)).fetchone()
            if not exists:
                conn.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS"
                    ).format(sql.Identifier(name))
                )
            attrs = conn.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                "rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname = %s",
                (name,),
            ).fetchone()
            assert attrs == (False, False, False, False, False, False, True)


def _apply(conn, migration: str) -> None:
    conn.execute((MIGRATIONS / f"{migration}.sql").read_text(encoding="utf-8"))


@pytest.fixture
def secured_database(cluster):
    _ensure_test_roles(cluster)
    dbname = "adr048_" + secrets.token_hex(6)
    with psycopg.connect(cluster, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER postgres").format(sql.Identifier(dbname)))
    admin_dsn = make_conninfo(cluster, dbname=dbname, user="postgres")
    try:
        with psycopg.connect(admin_dsn) as conn:
            for migration in BASELINE:
                _apply(conn, migration)
            conn.execute("CREATE TABLE public.adr048_outside_scope_probe (id integer PRIMARY KEY)")
            _apply(conn, ACCESS_MIGRATION)
        yield admin_dsn
    finally:
        with psycopg.connect(cluster, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))


def _effective(conn, role: str, table: str, privilege: str) -> bool:
    return conn.execute(
        "SELECT has_table_privilege(%s, %s, %s)", (role, f"public.{table}", privilege)
    ).fetchone()[0]


def test_migration_enforces_exact_role_acl_rls_policies_and_ownership(secured_database):
    with psycopg.connect(secured_database) as conn:
        version = int(conn.execute("SHOW server_version_num").fetchone()[0])
        # MAINTAIN_LOCAL_PG16 = NOT_APPLICABLE. Only PG17+ validates this
        # privilege; public_probe observes privileges granted to PUBLIC.
        checked_privileges = PRIVILEGES + (("MAINTAIN",) if version >= 170000 else ())

        attrs = conn.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
            "rolbypassrls, rolinherit, rolcanlogin FROM pg_roles WHERE rolname='juval_backend'"
        ).fetchone()
        assert attrs == (False, False, False, False, False, False, True)
        assert conn.execute(
            "SELECT count(*) FROM pg_auth_members m "
            "JOIN pg_roles r ON r.oid=m.member OR r.oid=m.roleid "
            "WHERE r.rolname='juval_backend'"
        ).fetchone() == (0,)

        for table in TABLES:
            assert conn.execute(
                "SELECT relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner) "
                "FROM pg_class WHERE oid=%s::regclass", (f"public.{table}",)
            ).fetchone() == (True, False, "postgres")
            observed = conn.execute(
                "SELECT policyname, cmd, roles FROM pg_policies "
                "WHERE schemaname='public' AND tablename=%s ORDER BY cmd", (table,)
            ).fetchall()
            assert {(cmd, tuple(roles)) for _name, cmd, roles in observed} == {
                (cmd, ("juval_backend",)) for cmd in EXPECTED_POLICIES[table]
            }

            for privilege in checked_privileges:
                assert _effective(conn, "juval_backend", table, privilege) == (
                    privilege in EXPECTED[table]
                ), (table, privilege)
                for role in DENIED_ROLES:
                    assert not _effective(conn, role, table, privilege), (role, table, privilege)
                assert not _effective(conn, "public_probe", table, privilege), (table, privilege)

            acl_roles = conn.execute(
                "SELECT DISTINCT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE r.rolname END "
                "FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a "
                "LEFT JOIN pg_roles r ON r.oid=a.grantee "
                "WHERE c.oid=%s::regclass", (f"public.{table}",)
            ).fetchall()
            assert not (set(x[0] for x in acl_roles) & {*DENIED_ROLES, "PUBLIC"})

        assert conn.execute(
            "SELECT count(*) FROM pg_class WHERE relowner='juval_backend'::regrole "
            "AND relnamespace='public'::regnamespace"
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT nspowner='juval_backend'::regrole FROM pg_namespace WHERE nspname='public'"
        ).fetchone() == (False,)


def test_identity_readiness_accepts_adr048_runtime_and_rejects_admin(secured_database):
    """Use the existing disposable fixture; never a runtime or Supabase DSN."""
    from juval.infrastructure.persistence.postgres_session_store import verify_session_database

    verify_session_database(make_conninfo(secured_database, user="juval_backend"))
    with pytest.raises(RuntimeError, match="readiness failed"):
        verify_session_database(secured_database)


def test_runtime_positive_operations_and_denied_unneeded_crud(secured_database):
    runtime_dsn = make_conninfo(secured_database, user="juval_backend")
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    run = ExecutionRun(
        execution_id="adr048-run",
        started_at=now,
        finished_at=now,
        status=ExecutionStatus.SUCCESS,
        input_filename="synthetic.xlsx",
        input_hash="0" * 64,
        application_version="test",
        records_total=1,
        records_processed=1,
        records_successful=1,
        records_with_errors=0,
        warnings=0,
    )
    store = SupabaseExecutionRunStore(runtime_dsn)
    store.save_execution_run(run, records=[{"record_ref": "r1", "synthetic": True}])
    assert store.load_execution_run(run.execution_id) == run
    assert store.load_records(run.execution_id) == [{"record_ref": "r1", "synthetic": True}]

    batch = Batch(
        "adr048-batch", now, BatchStatus.SUCCESS,
        (BatchFile(0, "synthetic.xlsx", None, 1, BatchFileStatus.SUCCESS, run.execution_id),),
    )
    store.save_batch(batch)
    assert store.load_batch(batch.batch_id) == batch
    assert store.load_batch_for_run(run.execution_id) == batch

    with psycopg.connect(runtime_dsn) as conn:
        conn.execute(
            "INSERT INTO execution_run_financial_records VALUES "
            "(%s,%s,'juval.adr047.financial-record',1,'{}')",
            (run.execution_id, "r1"),
        )
        conn.execute(
            "INSERT INTO execution_run_capture_diagnostics VALUES "
            "(%s,%s,'juval.adr047.capture-diagnostics',1,'{}')",
            (run.execution_id, "r1"),
        )
        assert conn.execute(
            "SELECT payload FROM execution_run_financial_records WHERE execution_id=%s",
            (run.execution_id,),
        ).fetchone() == ("{}",)
        assert conn.execute(
            "SELECT payload FROM execution_run_capture_diagnostics WHERE execution_id=%s",
            (run.execution_id,),
        ).fetchone() == ("{}",)

        conn.execute(
            "INSERT INTO identity_sessions "
            "(session_digest,subject,roles,csrf_digest,created_at,last_seen_at,expires_at) "
            "VALUES ('session-hash','subject','{}','csrf-hash',%s,%s,%s)",
            (now, now, now),
        )
        assert conn.execute(
            "SELECT subject FROM identity_sessions WHERE session_digest='session-hash'"
        ).fetchone() == ("subject",)
        conn.execute(
            "UPDATE identity_sessions SET last_seen_at=%s WHERE session_digest='session-hash'", (now,)
        )
        conn.execute(
            "DELETE FROM identity_sessions WHERE session_digest='session-hash'"
        )

        conn.execute(
            "INSERT INTO identity_oauth_transactions "
            "(transaction_digest,state_digest,nonce_digest,code_verifier_ciphertext,redirect_uri,created_at,expires_at) "
            "VALUES ('txn-hash','state-hash','nonce-hash','ciphertext','https://example.invalid/cb',%s,%s)",
            (now, now),
        )
        assert conn.execute(
            "DELETE FROM identity_oauth_transactions WHERE transaction_digest='txn-hash' "
            "RETURNING state_digest"
        ).fetchone() == ("state-hash",)

    # Commands outside the evidenced CRUD matrix fail at the ACL layer.
    update_columns = {
        "execution_runs": "execution_id",
        "execution_run_records": "record_ref",
        "execution_run_financial_records": "record_ref",
        "execution_run_capture_diagnostics": "record_ref",
        "batches": "status",
        "batch_files": "status",
        "identity_sessions": "subject",
        "identity_oauth_transactions": "state_digest",
    }
    with psycopg.connect(runtime_dsn, autocommit=True) as conn:
        for table in TABLES:
            if "UPDATE" not in EXPECTED[table]:
                column = sql.Identifier(update_columns[table])
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(sql.SQL("UPDATE public.{} SET {} = {} WHERE false").format(
                        sql.Identifier(table), column, column,
                    ))
            if "DELETE" not in EXPECTED[table]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(sql.SQL("DELETE FROM public.{} WHERE false").format(sql.Identifier(table)))
            if "TRUNCATE" not in EXPECTED[table]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(sql.SQL("TRUNCATE public.{}").format(sql.Identifier(table)))


@pytest.mark.parametrize("role", (*DENIED_ROLES, "public_probe"))
def test_denied_roles_cannot_select_or_insert_internal_tables(secured_database, role):
    dsn = make_conninfo(secured_database, user=role)
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert conn.execute("SELECT current_user").fetchone() == (role,)
        for table in TABLES:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SELECT * FROM public.{} LIMIT 0").format(sql.Identifier(table)))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("INSERT INTO public.{} DEFAULT VALUES").format(sql.Identifier(table)))


def test_defaults_protect_future_public_objects_and_leave_existing_sentinel_unchanged(secured_database):
    with psycopg.connect(secured_database) as conn:
        conn.execute("CREATE TABLE public.adr048_future_table (id integer)")
        conn.execute("CREATE SEQUENCE public.adr048_future_sequence")
        conn.execute("CREATE FUNCTION public.adr048_future_function() RETURNS integer LANGUAGE sql AS 'SELECT 1'")
        for table in ("adr048_future_table",):
            for role in (*DENIED_ROLES, "juval_backend", "public_probe"):
                for privilege in PRIVILEGES:
                    assert not _effective(conn, role, table, privilege)
        for role in (*DENIED_ROLES, "juval_backend", "public_probe"):
            assert not conn.execute(
                "SELECT has_sequence_privilege(%s, 'public.adr048_future_sequence', 'USAGE')", (role,)
            ).fetchone()[0]
            assert not conn.execute(
                "SELECT has_function_privilege(%s, 'public.adr048_future_function()', 'EXECUTE')", (role,)
            ).fetchone()[0]

        assert conn.execute(
            "SELECT relowner::regrole::text, relacl::text FROM pg_class "
            "WHERE oid='public.adr048_outside_scope_probe'::regclass"
        ).fetchone() == ("postgres", None)


def test_migration_fails_closed_on_global_table_default_grant(cluster):
    _ensure_test_roles(cluster)
    dbname = "adr048_failclosed_" + secrets.token_hex(6)
    with psycopg.connect(cluster, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER postgres").format(sql.Identifier(dbname)))
    admin_dsn = make_conninfo(cluster, dbname=dbname, user="postgres")
    try:
        with psycopg.connect(admin_dsn) as conn:
            for migration in BASELINE:
                _apply(conn, migration)
            conn.execute("ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO anon")
        with psycopg.connect(admin_dsn) as conn:
            with pytest.raises(psycopg.errors.RaiseException, match="unapproved global table/sequence default ACL"):
                _apply(conn, ACCESS_MIGRATION)
        with psycopg.connect(admin_dsn) as conn:
            assert conn.execute("SELECT count(*) FROM pg_policies WHERE schemaname='public'").fetchone() == (0,)
            assert conn.execute("SELECT to_regclass('public.adr048_future_table')").fetchone() == (None,)
    finally:
        with psycopg.connect(cluster, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))
