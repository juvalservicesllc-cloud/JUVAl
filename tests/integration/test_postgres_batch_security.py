"""Gate B1: real disposable PostgreSQL, Unix socket only, synthetic data.

Reuse the existing initdb/cleanup fixture; never read runtime DSNs or env files.
Each test owns a database. Roles are non-superusers with no inherited membership.
Schema-scoped default grants reproduce B0 ONLY inside that disposable database.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone

import pytest

psycopg = pytest.importorskip("psycopg")
from psycopg import sql
from psycopg.conninfo import make_conninfo

from juval.domain.batch import Batch, BatchFile, BatchFileStatus, BatchStatus
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore
from .test_postgres_financial_persistence import cluster, MIGRATIONS  # noqa: F401

pytestmark = pytest.mark.skipif(not os.environ.get("JUVAL_POSTGRES_BIN"), reason="JUVAL_POSTGRES_BIN required: disposable PostgreSQL only")
BASE = ("20260817000000_execution_runs", "20260817000001_execution_run_records",
        "20260925000005_execution_run_financial_records")
DEPLOY = ("20260819000002_batches", "20260819000003_batch_file_counts",
          "20260928000006_batch_table_security")
TABLES = ("batches", "batch_files")
ROLES = ("anon", "authenticated", "public_probe")


@pytest.fixture(scope="module")
def roles(cluster):
    with psycopg.connect(cluster) as conn:
        assert 160000 <= int(conn.execute("SHOW server_version_num").fetchone()[0]) < 170000
        assert conn.execute("SHOW listen_addresses").fetchone() == ("",)
        for role in ("batch_backend", *ROLES):
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT").format(sql.Identifier(role)))
    return cluster


def apply(conn, migration):
    """Apply real SQL and record it ONLY in the disposable database's synthetic ledger."""
    text = (MIGRATIONS / f"{migration}.sql").read_text()
    conn.execute(text)
    version, name = migration.split("_", 1)
    conn.execute("INSERT INTO supabase_migrations.schema_migrations VALUES (%s,%s,%s)", (version, [text], name))


@pytest.fixture
def database(roles):
    name = "batch_b1_" + secrets.token_hex(6)
    with psycopg.connect(roles, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER batch_backend").format(sql.Identifier(name)))
    dsn = make_conninfo(roles, dbname=name, user="batch_backend")
    with psycopg.connect(dsn) as conn:
        conn.execute("CREATE SCHEMA supabase_migrations")
        conn.execute("CREATE TABLE supabase_migrations.schema_migrations (version text PRIMARY KEY, statements text[], name text)")
        conn.execute("GRANT USAGE ON SCHEMA public TO PUBLIC")
        # Reproduce inherited grants, including PUBLIC, without changing global defaults.
        conn.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO PUBLIC, anon, authenticated")
        for migration in BASE:
            apply(conn, migration)
    yield dsn
    with psycopg.connect(roles, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def fingerprint(conn):
    """Untargeted tables and default privileges must remain byte-for-byte equivalent."""
    return (
        conn.execute("SELECT relname,relowner,relacl::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND relname LIKE 'execution_%' ORDER BY relname").fetchall(),
        conn.execute("SELECT attrelid,attname,atttypid,attnotnull FROM pg_attribute WHERE attrelid IN (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace AND relname LIKE 'execution_%') AND attnum>0 ORDER BY attrelid,attnum").fetchall(),
        conn.execute("SELECT conrelid,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid IN (SELECT oid FROM pg_class WHERE relnamespace='public'::regnamespace AND relname LIKE 'execution_%') ORDER BY conrelid,conname").fetchall(),
        conn.execute("SELECT defaclrole,defaclnamespace,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY oid").fetchall(),
    )


@pytest.fixture
def secured(database):
    with psycopg.connect(database) as conn:
        before = fingerprint(conn)
        for migration in DEPLOY[:2]:
            apply(conn, migration)
        # Prove the fixture actually reproduces the insecure grants before 000006.
        for table in TABLES:
            assert conn.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE oid=%s::regclass", (table,)).fetchone() == (False,False,"batch_backend")
            for role in ROLES:
                for privilege in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER"):
                    assert conn.execute("SELECT has_table_privilege(%s,%s,%s)", (role,table,privilege)).fetchone()[0]
        apply(conn, DEPLOY[-1])
        assert fingerprint(conn) == before
    return database


def seed(dsn):
    now = datetime(2026, 9, 28, tzinfo=timezone.utc)
    run = ExecutionRun(execution_id="run-b1", started_at=now, finished_at=now,
        status=ExecutionStatus.SUCCESS, input_filename="synthetic.xlsx", input_hash="0" * 64,
        application_version="test", records_total=0, records_processed=0,
        records_successful=0, records_with_errors=0, warnings=0)
    batch = Batch("batch-b1", now, BatchStatus.SUCCESS,
        (BatchFile(0, "synthetic.xlsx", None, 1, BatchFileStatus.SUCCESS, run.execution_id),))
    store = SupabaseExecutionRunStore(dsn)
    store.save_execution_run(run)
    store.save_batch(batch)
    assert store.load_batch(batch.batch_id) == batch
    assert store.load_batch_for_run(run.execution_id) == batch
    return batch


def test_original_migrations_unchanged():
    for name, digest in zip(DEPLOY[:2], (
        "f61d267590bd54ac9d1adf6bb8e1c150ef4aa7e83240bbb056647846a21cf040",
        "cde3dc047125f497a7684d05100971bd47332615ce46d9efaf66b428bdf51704",
    )):
        assert hashlib.sha256((MIGRATIONS / f"{name}.sql").read_bytes()).hexdigest() == digest


def test_schema_security_and_backend_roundtrip(secured):
    seed(secured)
    with psycopg.connect(secured) as conn:
        assert conn.execute("SELECT current_user,rolsuper,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user").fetchone() == ("batch_backend",False,False,False)
        expected = {
            "batches": [("batch_id","text","NO",None),("created_at","timestamptz","NO",None),("status","text","NO",None)],
            "batch_files": [("batch_id","text","NO",None),("ordinal","int4","NO",None),("filename","text","NO",None),("content_type","text","YES",None),("size_bytes","int8","NO",None),("status","text","NO",None),("execution_id","text","YES",None),("warnings","jsonb","NO","'[]'::jsonb"),("errors","jsonb","NO","'[]'::jsonb")]
                + [(n,"int4","NO","0") for n in ("records_total","records_processed","records_with_errors","warning_count")],
        }
        for table in TABLES:
            assert conn.execute("SELECT column_name,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,)).fetchall() == expected[table]
            assert conn.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE oid=%s::regclass", (table,)).fetchone() == (True,False,"batch_backend")
            assert conn.execute("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=%s", (table,)).fetchone() == (0,)
            assert conn.execute("SELECT count(*) FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE c.oid=%s::regclass AND a.grantee=0", (table,)).fetchone() == (0,)
            for role in ROLES:
                for privilege in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER"):
                    assert not conn.execute("SELECT has_table_privilege(%s,%s,%s)", (role,table,privilege)).fetchone()[0]
            for privilege in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER"):
                assert conn.execute("SELECT has_table_privilege(current_user,%s,%s)", (table,privilege)).fetchone()[0]
        constraints = conn.execute("SELECT conrelid::regclass::text,contype,pg_get_constraintdef(oid),convalidated FROM pg_constraint WHERE conrelid IN ('batches'::regclass,'batch_files'::regclass) ORDER BY conname").fetchall()
        assert len(constraints) == 6 and all(r[3] for r in constraints)
        definitions = {r[2] for r in constraints}
        assert 'PRIMARY KEY (batch_id)' in definitions
        assert 'PRIMARY KEY (batch_id, ordinal)' in definitions
        assert 'FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE' in definitions
        assert 'FOREIGN KEY (execution_id) REFERENCES execution_runs(execution_id)' in definitions
        checks = [r[2] for r in constraints if r[1] == 'c']
        assert len(checks) == 2 and all('PARTIAL_SUCCESS' in c and 'FAILED' in c and 'SUCCESS' in c for c in checks)
        assert sum('REJECTED' in c for c in checks) == 1
        assert conn.execute("SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND indexname='idx_batch_files_execution'").fetchone() == ('CREATE INDEX idx_batch_files_execution ON public.batch_files USING btree (execution_id)',)


def test_backend_owner_can_update_delete_and_truncate(secured):
    seed(secured)  # Real backend adapter INSERT/SELECT round-trip, as non-superuser owner.
    with psycopg.connect(secured) as conn:
        for table in TABLES:
            assert conn.execute(f"UPDATE {table} SET status='PARTIAL_SUCCESS'").rowcount == 1
            assert conn.execute(f"SELECT status FROM {table}").fetchall() == [("PARTIAL_SUCCESS",)]
        assert conn.execute("DELETE FROM batch_files").rowcount == 1
        assert conn.execute("DELETE FROM batches").rowcount == 1
    with psycopg.connect(secured) as conn:
        conn.execute("INSERT INTO batches VALUES ('truncate-b1',now(),'SUCCESS')")
        conn.execute("INSERT INTO batch_files (batch_id,ordinal,filename,size_bytes,status) VALUES ('truncate-b1',0,'synthetic.xlsx',1,'REJECTED')")
        conn.execute("TRUNCATE batches,batch_files")
        for table in TABLES:
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


@pytest.mark.parametrize("role", ROLES)
def test_effective_role_operations_are_denied_by_privileges(secured, role):
    seed(secured)
    # Direct login as the actual non-owner: no mock, no superuser RLS bypass.
    with psycopg.connect(make_conninfo(secured, user=role), autocommit=True) as conn:
        assert conn.execute("SELECT current_user").fetchone() == (role,)
        assert conn.execute("SELECT rolsuper,rolbypassrls,rolinherit FROM pg_roles WHERE rolname=current_user").fetchone() == (False,False,False)
        assert conn.execute("SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)").fetchone() == (0,)
        for table in TABLES:
            insert = ("INSERT INTO batches VALUES ('denied',now(),'SUCCESS')" if table == "batches" else
                      "INSERT INTO batch_files (batch_id,ordinal,filename,size_bytes,status) VALUES ('batch-b1',1,'synthetic.xlsx',1,'REJECTED')")
            for statement in (f"SELECT * FROM {table}", insert, f"UPDATE {table} SET status='FAILED'", f"DELETE FROM {table}", f"TRUNCATE {table}"):
                with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
                    conn.execute(statement)
                assert 'permission denied for table' in str(error.value)


@pytest.mark.parametrize("role", ("anon", "authenticated"))
def test_rls_is_independent_defense_when_dml_privileges_are_temporarily_granted(secured, role):
    seed(secured)
    # Test-only grants, committed in a disposable DB so a real role connection sees them.
    with psycopg.connect(secured) as conn:
        conn.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON batches,batch_files TO {}").format(sql.Identifier(role)))
    with psycopg.connect(make_conninfo(secured, user=role), autocommit=True) as conn:
        for table in TABLES:
            assert conn.execute(f"SELECT * FROM {table}").fetchall() == []
            assert conn.execute(f"UPDATE {table} SET status='FAILED'").rowcount == 0
            assert conn.execute(f"DELETE FROM {table}").rowcount == 0
            insert = ("INSERT INTO batches VALUES ('denied',now(),'SUCCESS')" if table == "batches" else
                      "INSERT INTO batch_files (batch_id,ordinal,filename,size_bytes,status) VALUES ('batch-b1',1,'synthetic.xlsx',1,'REJECTED')")
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
                conn.execute(insert)
            assert 'row-level security policy' in str(error.value)
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as error:
                conn.execute(f"TRUNCATE {table}")
            assert 'permission denied for table' in str(error.value)
    with psycopg.connect(secured) as conn:
        for table in TABLES:
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (1,)
        # Reapplying security restores grants; no history entry is invented for the test.
        conn.execute((MIGRATIONS / f"{DEPLOY[-1]}.sql").read_text())
        for table in TABLES:
            for privilege in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE"):
                assert not conn.execute("SELECT has_table_privilege(%s,%s,%s)", (role,table,privilege)).fetchone()[0]


@pytest.mark.parametrize("role", ROLES)
def test_truncate_grant_bypasses_rls_so_revocation_is_necessary(secured, role):
    seed(secured)
    with psycopg.connect(secured) as conn:
        grantee = sql.SQL("PUBLIC") if role == "public_probe" else sql.Identifier(role)
        conn.execute(sql.SQL("GRANT TRUNCATE ON batches,batch_files TO {}").format(grantee))
    with psycopg.connect(make_conninfo(secured, user=role)) as conn:
        # RLS stays enabled with zero policies. A TRUNCATE grant still permits deletion.
        assert conn.execute("SELECT bool_and(relrowsecurity),bool_or(relforcerowsecurity) FROM pg_class WHERE oid IN ('batches'::regclass,'batch_files'::regclass)").fetchone() == (True,False)
        assert conn.execute("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename IN ('batches','batch_files')").fetchone() == (0,)
        conn.execute("TRUNCATE batches,batch_files")
        # Roll back this destructive probe inside the disposable database.
        conn.rollback()
    with psycopg.connect(secured) as conn:
        for table in TABLES:
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (1,)
        conn.execute((MIGRATIONS / f"{DEPLOY[-1]}.sql").read_text())
        for table in TABLES:
            assert not conn.execute("SELECT has_table_privilege(%s,%s,'TRUNCATE')", (role,table)).fetchone()[0]


@pytest.mark.parametrize("fail", (False, True))
def test_deployment_transaction_is_all_or_nothing(database, fail):
    with psycopg.connect(database) as observer:
        before = fingerprint(observer)
    try:
        with psycopg.connect(database) as conn:
            for migration in DEPLOY:
                apply(conn, migration)
            # Verification runs BEFORE leaving this transaction (and hence before COMMIT).
            assert fingerprint(conn) == before
            for table in TABLES:
                assert conn.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) FROM pg_class WHERE oid=%s::regclass", (table,)).fetchone() == (True,False,"batch_backend")
                assert conn.execute("SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename=%s", (table,)).fetchone() == (0,)
                for role in ROLES:
                    for privilege in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE"):
                        assert not conn.execute("SELECT has_table_privilege(%s,%s,%s)", (role,table,privilege)).fetchone()[0]
            with psycopg.connect(database) as observer:
                assert observer.execute("SELECT to_regclass('public.batches'),to_regclass('public.batch_files')").fetchone() == (None,None)
                assert observer.execute("SELECT count(*) FROM supabase_migrations.schema_migrations").fetchone() == (3,)
            if fail:
                conn.execute("SELECT 1/0")
    except psycopg.errors.DivisionByZero:
        assert fail
    with psycopg.connect(database) as conn:
        assert fingerprint(conn) == before
        versions = conn.execute("SELECT version FROM supabase_migrations.schema_migrations ORDER BY version").fetchall()
        assert versions == sorted((m.split('_',1)[0],) for m in BASE + (() if fail else DEPLOY))
        for table in TABLES:
            assert (conn.execute("SELECT to_regclass(%s)",(f"public.{table}",)).fetchone()[0] is None) == fail
        for version, statements, name in conn.execute("SELECT version,statements,name FROM supabase_migrations.schema_migrations"):
            assert statements == [(MIGRATIONS / f"{version}_{name}.sql").read_text()]
