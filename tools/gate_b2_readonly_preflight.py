"""Single-attempt, transaction-read-only Gate B2 catalog reconciliation.

This program never applies migrations or tests exploitability. Supply its DSN
only in JUVAL_SUPABASE_DB_URL from the dedicated credential loader; it never
prints connection details or database exception text.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from gate_b2_evidence import (
    build_evidence_document,
    compact_summary,
    reconcile_observations,
    write_evidence_artifact,
)

ROOT = Path(__file__).resolve().parents[1]

TARGET_RELATIONS = (
    "execution_runs",
    "execution_run_records",
    "execution_run_financial_records",
    "execution_run_capture_diagnostics",
    "batches",
    "batch_files",
    "identity_sessions",
    "identity_oauth_transactions",
)
LEDGER_VERSIONS = (
    "20260817000000",
    "20260817000001",
    "20260819000002",
    "20260819000003",
    "20260909000004",
    "20260925000005",
    "20260928000006",
    "20261005000007",
)
ROLES = (
    "juval_backend",
    "postgres",
    "supabase_admin",
    "anon",
    "authenticated",
    "authenticator",
    "service_role",
)
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _fetchall(conn: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        names = [column.name for column in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def _fetchone(conn: Any, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = _fetchall(conn, query, params)
    if not rows:
        raise RuntimeError("expected one catalog result")
    return rows[0]


def _relation_reconciliation(conn: Any, relation: str, role_names: set[str], pg_major: int) -> dict[str, Any]:
    meta = _fetchall(
        conn,
        """SELECT c.oid, c.relname, c.relkind, owner.rolname AS owner,
                  c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced,
                  c.relacl::text AS declared_acl
           FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           JOIN pg_roles owner ON owner.oid = c.relowner
           WHERE n.nspname = 'public' AND c.relname = %s
             AND c.relkind IN ('r', 'p', 'v', 'm', 'f')""",
        (relation,),
    )
    if not meta:
        return {
            "name": relation,
            "state": "ABSENT",
        }
    item = meta[0]
    oid = item.pop("oid")
    item.update(name=relation, state="PRESENT")
    item["columns"] = _fetchall(
        conn,
        """SELECT a.attname AS name, format_type(a.atttypid, a.atttypmod) AS type,
                  a.attnotnull AS not_null
           FROM pg_attribute a
           WHERE a.attrelid = %s AND a.attnum > 0 AND NOT a.attisdropped
           ORDER BY a.attnum""",
        (oid,),
    )
    item["constraints"] = _fetchall(
        conn,
        """SELECT conname AS name, contype AS type, convalidated AS validated,
                  pg_get_constraintdef(oid, true) AS definition
           FROM pg_constraint WHERE conrelid = %s ORDER BY conname""",
        (oid,),
    )
    item["declared_acl_entries"] = _fetchall(
        conn,
        """SELECT CASE WHEN x.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee,
                  grantor.rolname AS grantor, x.privilege_type, x.is_grantable
           FROM pg_class c
           CROSS JOIN LATERAL aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) x
           LEFT JOIN pg_roles grantee ON grantee.oid = x.grantee
           JOIN pg_roles grantor ON grantor.oid = x.grantor
           WHERE c.oid = %s ORDER BY grantee, x.privilege_type, grantor""",
        (oid,),
    )
    item["effective_table_privileges"] = {}
    for role in sorted(role_names):
        checks = TABLE_PRIVILEGES + (("MAINTAIN",) if pg_major >= 17 else ())
        item["effective_table_privileges"][role] = {
            privilege: _fetchone(
                conn,
                "SELECT has_table_privilege(%s, %s, %s) AS allowed",
                (role, oid, privilege),
            )["allowed"]
            for privilege in checks
        }
    item["policies"] = _fetchall(
        conn,
        """SELECT policyname, permissive, roles, cmd, qual, with_check
           FROM pg_policies WHERE schemaname = 'public' AND tablename = %s
           ORDER BY policyname""",
        (relation,),
    )
    return item


def build_report(conn: Any) -> dict[str, Any]:
    identity = _fetchone(
        conn,
        """SELECT current_database() AS database, current_user AS current_user,
                  session_user AS session_user, current_setting('server_version_num')::int AS server_version_num,
                  current_setting('transaction_read_only') AS transaction_read_only,
                  pg_is_in_recovery() AS in_recovery""",
    )
    pg_major = identity["server_version_num"] // 10000
    role_rows = _fetchall(
        conn,
        """SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication,
                  rolbypassrls, rolinherit, rolcanlogin
           FROM pg_roles WHERE rolname = ANY(%s) ORDER BY rolname""",
        (list(ROLES),),
    )
    role_names = {row["rolname"] for row in role_rows}
    memberships = _fetchall(
        conn,
        """SELECT parent.rolname AS granted_role, member.rolname AS member,
                  grantor.rolname AS grantor, m.admin_option
           FROM pg_auth_members m
           JOIN pg_roles parent ON parent.oid = m.roleid
           JOIN pg_roles member ON member.oid = m.member
           JOIN pg_roles grantor ON grantor.oid = m.grantor
           WHERE parent.rolname = ANY(%s) OR member.rolname = ANY(%s)
           ORDER BY granted_role, member""",
        (list(ROLES), list(ROLES)),
    )

    ledger_exists = _fetchone(
        conn, "SELECT to_regclass('supabase_migrations.schema_migrations') IS NOT NULL AS present"
    )["present"]
    ledger: dict[str, Any] = {"state": "ABSENT", "versions": []}
    if ledger_exists:
        ledger["state"] = "PRESENT"
        ledger_columns = {
            row["column_name"]
            for row in _fetchall(
                conn,
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema = 'supabase_migrations'
                     AND table_name = 'schema_migrations'""",
            )
        }
        if "version" in ledger_columns:
            rows = _fetchall(
                conn,
                """SELECT version::text AS version
                   FROM supabase_migrations.schema_migrations
                   WHERE version::text = ANY(%s) ORDER BY version::text""",
                (list(LEDGER_VERSIONS),),
            )
            present = {row["version"] for row in rows}
            ledger["versions"] = [
                {"version": version, "state": "PRESENT" if version in present else "ABSENT"}
                for version in LEDGER_VERSIONS
            ]
            ledger["version_column"] = "PRESENT"
        else:
            ledger["version_column"] = "ABSENT"
            ledger["versions"] = [{"version": version, "state": "UNDETERMINED"} for version in LEDGER_VERSIONS]

    relations = [_relation_reconciliation(conn, name, role_names, pg_major) for name in TARGET_RELATIONS]
    public_schema = _fetchall(
        conn,
        """SELECT n.nspname AS name, owner.rolname AS owner, n.nspacl::text AS declared_acl
           FROM pg_namespace n JOIN pg_roles owner ON owner.oid = n.nspowner
           WHERE n.nspname = 'public'""",
    )
    schema_acl: list[dict[str, Any]] = []
    if public_schema:
        schema_acl = _fetchall(
            conn,
            """SELECT CASE WHEN x.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee,
                      grantor.rolname AS grantor, x.privilege_type, x.is_grantable
               FROM pg_namespace n
               CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl, acldefault('n', n.nspowner))) x
               LEFT JOIN pg_roles grantee ON grantee.oid = x.grantee
               JOIN pg_roles grantor ON grantor.oid = x.grantor
               WHERE n.nspname = 'public' ORDER BY grantee, x.privilege_type""",
        )
        for schema in public_schema:
            schema["effective_privileges"] = {
                role: {
                    privilege: _fetchone(
                        conn,
                        "SELECT has_schema_privilege(%s, 'public', %s) AS allowed",
                        (role, privilege),
                    )["allowed"]
                    for privilege in ("USAGE", "CREATE")
                }
                for role in sorted(role_names)
            }

    defaults = _fetchall(
        conn,
        """SELECT creator.rolname AS owner,
                  CASE WHEN d.defaclnamespace = 0 THEN NULL ELSE n.nspname END AS schema,
                  d.defaclobjtype AS object_type,
                  CASE WHEN x.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END AS grantee,
                  grantor.rolname AS grantor, x.privilege_type, x.is_grantable
           FROM pg_default_acl d
           JOIN pg_roles creator ON creator.oid = d.defaclrole
           LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
           CROSS JOIN LATERAL aclexplode(d.defaclacl) x
           LEFT JOIN pg_roles grantee ON grantee.oid = x.grantee
           JOIN pg_roles grantor ON grantor.oid = x.grantor
           ORDER BY owner, schema NULLS FIRST, object_type, grantee, privilege_type""",
    )
    return {
        "mode": "CATALOG_PRIVILEGE_RECONCILIATION_ONLY",
        "exploitability_tested": False,
        "database_identity": identity,
        "migration_ledger": ledger,
        "relations": relations,
        "public_schema": public_schema,
        "public_schema_declared_acl_entries": schema_acl,
        "roles": role_rows,
        "relevant_memberships": memberships,
        "default_privileges_by_owner": defaults,
        "maintain": {
            "postgres_major": pg_major,
            "effective_checks_applicable": pg_major >= 17,
            "role_present": "juval_backend" in role_names,
        },
        "data_api_assessed_or_changed": False,
        "supavisor_custom_role_test_performed": False,
    }


def main() -> int:
    report: dict[str, Any] = {
        "attempt_count": 0,
        "connection_established": False,
        "read_only_setup_complete": False,
        "read_only_verified": False,
        "transaction_read_only": None,
        "observations_complete": False,
        "rollback_attempted": False,
        "rollback_succeeded": False,
        "connection_close_attempted": False,
        "connection_close_succeeded": False,
        "connection_closed": False,
        "artifact_status": "NOT_FINALIZED",
    }
    dsn = os.environ.get("JUVAL_SUPABASE_DB_URL")
    if not dsn:
        report["error_class"] = "MissingCredential"
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 2

    conn = None
    catalog = None
    classification = None
    try:
        import psycopg

        report["attempt_count"] = 1
        conn = psycopg.connect(dsn, autocommit=False, connect_timeout=15)
        report["connection_established"] = True
        if conn.autocommit:
            raise RuntimeError("autocommit must be disabled")
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            report["read_only_setup_complete"] = True
            cur.execute("SHOW transaction_read_only")
            report["transaction_read_only"] = cur.fetchone()[0].lower()
            report["read_only_verified"] = report["transaction_read_only"] == "on"
        if not report["read_only_verified"]:
            raise RuntimeError("read-only transaction was not verified")
        catalog = build_report(conn)
        report["observations_complete"] = True
        classification = reconcile_observations(catalog)
    except Exception as exc:
        # Only exception classes are retained; driver text can contain conninfo.
        report["error_class"] = type(exc).__name__
    finally:
        if conn is not None:
            report["rollback_attempted"] = True
            try:
                conn.rollback()
                report["rollback_succeeded"] = True
            except Exception as exc:
                report["rollback_error_class"] = type(exc).__name__
            report["connection_close_attempted"] = True
            try:
                conn.close()
                report["connection_close_succeeded"] = True
                report["connection_closed"] = bool(conn.closed)
            except Exception as exc:
                report["close_error_class"] = type(exc).__name__

    valid_lifecycle = (
        report["attempt_count"] == 1
        and report["transaction_read_only"] == "on"
        and all(report[key] is True for key in (
            "connection_established",
            "read_only_setup_complete",
            "read_only_verified",
            "observations_complete",
            "rollback_attempted",
            "rollback_succeeded",
            "connection_close_attempted",
            "connection_close_succeeded",
            "connection_closed",
        ))
        and not any(key.endswith("error_class") for key in report)
    )
    if valid_lifecycle and catalog is not None and classification is not None:
        try:
            document = build_evidence_document(catalog, report)
            document["CLASSIFICATION"] = classification
            artifact = write_evidence_artifact(document, repository_root=ROOT)
            summary = compact_summary(document, artifact)
            print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
            return 0
        except Exception as exc:
            report["artifact_error_class"] = type(exc).__name__
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
