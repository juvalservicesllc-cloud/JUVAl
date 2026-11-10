"""ADR-048 startup contract using simulated catalogs only; no PostgreSQL connection."""
from __future__ import annotations

import socket
import traceback

import pytest

from juval.infrastructure.persistence import postgres_session_store as postgres


COMMANDS = {
    "identity_sessions": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "identity_oauth_transactions": ("SELECT", "INSERT", "DELETE"),
}
FAKE_DSN = "host=/synthetic/readiness-socket dbname=synthetic"  # parseable: startup now checks TLS first


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class CatalogConnection:
    def __init__(self):
        self.role = ["juval_backend", "juval_backend", False, False, False, False, False, True, 170006, False]
        self.tables = [[table, True, False, False, True] for table in COMMANDS]
        self.policies = [
            [table, "juval_backend_" + command.lower(), "PERMISSIVE", ["juval_backend"], command,
             "true" if command != "INSERT" else None,
             "true" if command in ("INSERT", "UPDATE") else None]
            for table, commands in COMMANDS.items() for command in commands
        ]
        self.privileges = {}
        self.keys = {}
        self.missing_columns = set()
        self.schema_usage = True
        self.read_only = "on"
        self.queries = []
        self.events = []
        self.rollback_error = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.events.append("close")

    def rollback(self):
        self.events.append("rollback")
        if self.rollback_error:
            raise RuntimeError(FAKE_DSN)

    def execute(self, query, params=None):
        self.queries.append((query, params))
        self.events.append(query.split()[0])
        assert query.split()[0] in ("set", "show", "select"), "mutating readiness SQL"
        if query.startswith("set "):
            return Result([])
        if query == "show transaction_read_only":
            return Result([(self.read_only,)])
        if "from pg_roles r" in query:
            return Result([tuple(self.role)] if self.role else [])
        if "has_schema_privilege" in query:
            return Result([(self.schema_usage,)])
        if "from pg_class c" in query:
            return Result([tuple(row) for row in self.tables])
        if "from pg_policies" in query:
            return Result(self.policies)
        if "has_table_privilege" in query:
            table = params[0].split(".")[1]
            return Result([
                (privilege, self.privileges.get((table, privilege), privilege in COMMANDS[table]))
                for privilege in params[1]
            ])
        if "from pg_constraint c" in query:
            return Result([(self.keys.get(params[0], 1),)])
        if query.endswith(" limit 0"):
            if any("from " + table + " " in query for table in self.missing_columns):
                raise RuntimeError(FAKE_DSN)
            return Result([])
        raise AssertionError("unexpected catalog query")


@pytest.fixture
def catalog(monkeypatch):
    def forbidden_connection(*args, **kwargs):
        pytest.fail("network forbidden in readiness unit tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden_connection)
    monkeypatch.setattr(socket, "create_connection", forbidden_connection)
    conn = CatalogConnection()

    class Driver:
        @staticmethod
        def connect(dsn, **kwargs):
            assert dsn == FAKE_DSN
            assert kwargs == {"connect_timeout": 5, "autocommit": False}
            conn.events.append("connect")
            return conn

    monkeypatch.setattr(postgres, "_require_driver", lambda: Driver)
    return conn


def rejected(catalog):
    with pytest.raises(RuntimeError, match="readiness failed") as error:
        postgres.verify_session_database(FAKE_DSN)
    assert catalog.events[-2:] == ["rollback", "close"]
    return error.value


@pytest.mark.parametrize("version", [160000, 170006])
def test_non_owner_runtime_with_exact_policies_and_crud_passes(catalog, version):
    catalog.role[8] = version
    postgres.verify_session_database(FAKE_DSN)
    assert catalog.events[:4] == ["connect", "set", "set", "show"]
    assert catalog.events[-2:] == ["rollback", "close"]
    privilege_queries = [(query, params) for query, params in catalog.queries if "has_table_privilege" in query]
    assert len(privilege_queries) == 2
    assert all(("MAINTAIN" in params[1]) == (version >= 170000) for _, params in privilege_queries)
    assert len([query for query, _ in catalog.queries if query.endswith(" limit 0")]) == 2


@pytest.mark.parametrize("table", list(COMMANDS))
def test_missing_table_fails_closed(catalog, table):
    catalog.tables = [row for row in catalog.tables if row[0] != table]
    rejected(catalog)


@pytest.mark.parametrize("table_index", [0, 1])
@pytest.mark.parametrize("attribute,bad_value", [(1, False), (2, True), (3, True), (4, False)])
def test_rls_force_ownership_or_search_path_shadowing_fails_closed(catalog, table_index, attribute, bad_value):
    catalog.tables[table_index][attribute] = bad_value
    rejected(catalog)


@pytest.mark.parametrize("attribute,bad_value", [
    (0, "postgres"), (1, "postgres"), (2, True), (3, True), (4, True),
    (5, True), (6, True), (7, False), (9, True),
])
def test_unsafe_runtime_identity_attributes_or_membership_fails_closed(catalog, attribute, bad_value):
    catalog.role[attribute] = bad_value
    rejected(catalog)


def test_unobserved_role_fails_closed(catalog):
    catalog.role = None
    rejected(catalog)


def test_missing_schema_usage_fails_closed(catalog):
    catalog.schema_usage = False
    rejected(catalog)


def test_read_only_verification_is_required_before_catalog_queries(catalog):
    catalog.read_only = "off"
    rejected(catalog)
    assert len(catalog.queries) == 3


@pytest.mark.parametrize("policy_index", range(7))
def test_each_required_policy_is_required(catalog, policy_index):
    catalog.policies.pop(policy_index)
    rejected(catalog)


@pytest.mark.parametrize("attribute,bad_value", [
    (1, "another_name"), (2, "RESTRICTIVE"), (3, ["public"]),
    (3, ["juval_backend", "authenticated"]), (4, "ALL"),
    (5, "false"), (5, None), (6, "true"),
])
def test_incorrect_policy_configuration_fails_closed(catalog, attribute, bad_value):
    catalog.policies[0][attribute] = bad_value
    rejected(catalog)


@pytest.mark.parametrize("policy_index", [1, 2, 5])
def test_insert_and_update_check_predicate_is_required(catalog, policy_index):
    catalog.policies[policy_index][6] = None
    rejected(catalog)


def test_extra_policy_fails_closed(catalog):
    catalog.policies.append(["identity_sessions", "extra", "PERMISSIVE", ["public"], "ALL", "true", "true"])
    rejected(catalog)


@pytest.mark.parametrize("table,privilege", [(table, command) for table, commands in COMMANDS.items() for command in commands])
def test_missing_required_effective_crud_fails_closed(catalog, table, privilege):
    catalog.privileges[table, privilege] = False
    rejected(catalog)


@pytest.mark.parametrize("table,privilege", [
    (table, privilege) for table in COMMANDS for privilege in ("TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN")
] + [("identity_oauth_transactions", "UPDATE")])
def test_unexpected_effective_privilege_including_public_derived_fails_closed(catalog, table, privilege):
    # The driver reports the effective result, regardless of explicit ACL origin.
    catalog.privileges[table, privilege] = True
    rejected(catalog)


@pytest.mark.parametrize("table", list(COMMANDS))
@pytest.mark.parametrize("key_count", [0, 2])
def test_digest_primary_key_validation_is_preserved(catalog, table, key_count):
    catalog.keys["public." + table] = key_count
    rejected(catalog)


@pytest.mark.parametrize("table", list(COMMANDS))
def test_column_validation_is_preserved(catalog, table):
    catalog.missing_columns.add(table)
    rejected(catalog)


def test_rollback_failure_does_not_pass_or_expose_driver_diagnostics(catalog, capsys):
    catalog.rollback_error = True
    error = rejected(catalog)
    assert FAKE_DSN not in "".join(traceback.format_exception(error))
    assert capsys.readouterr() == ("", "")


def test_connection_failure_is_secret_safe(monkeypatch, capsys):
    class BrokenDriver:
        @staticmethod
        def connect(*args, **kwargs):
            raise RuntimeError("synthetic-password " + FAKE_DSN)

    monkeypatch.setattr(postgres, "_require_driver", lambda: BrokenDriver)
    with pytest.raises(RuntimeError, match="ADR-048") as error:
        postgres.verify_session_database(FAKE_DSN)
    rendered = "".join(traceback.format_exception(error.value))
    assert FAKE_DSN not in rendered
    assert "synthetic-password" not in rendered
    assert capsys.readouterr() == ("", "")


def test_bff_selects_postgres_adapters_after_compliant_readiness(catalog, monkeypatch):
    from juval.interfaces.api import auth as auth_module, bff

    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", FAKE_DSN)
    cipher = object()
    monkeypatch.setattr(bff.TokenCipher, "from_environment", lambda: cipher)
    auth_module.reset_for_tests()
    try:
        sessions, transactions = bff.build_stores()
        assert isinstance(sessions, postgres.PostgresSessionStore)
        assert isinstance(transactions, postgres.PostgresOAuthTransactionStore)
        assert sessions._dsn == transactions._dsn == FAKE_DSN
        assert sessions._cipher is transactions._cipher is cipher
        assert catalog.events[-2:] == ["rollback", "close"]
    finally:
        auth_module.reset_for_tests()
