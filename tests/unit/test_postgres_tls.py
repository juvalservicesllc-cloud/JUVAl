"""TLS is required for remote PostgreSQL connection strings (SEC-01E)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from juval.infrastructure.persistence.postgres_tls import require_tls_for_remote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import tenancy_admin  # noqa: E402


@pytest.fixture(autouse=True)
def no_libpq_env(monkeypatch):
    for name in ("PGHOST", "PGSSLMODE"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("dsn", [
    "postgresql://db.example.supabase.co:5432/postgres",
    "postgresql://pooler.example.com:6543/postgres?sslmode=prefer",
    "postgresql://pooler.example.com/postgres?sslmode=disable",
    "postgresql://pooler.example.com/postgres?sslmode=allow",
    "host=localhost,db.example.com dbname=x",          # one remote host is enough
    "hostaddr=203.0.113.7 dbname=x",
    "postgresql://db.example.com/postgres?sslmode=require",     # encrypted, server not verified
    "postgresql://db.example.com/postgres?sslmode=verify-ca",   # CA checked, hostname not
])
def test_a_remote_dsn_without_tls_is_refused(dsn):
    with pytest.raises(RuntimeError, match="without TLS verify-full"):
        require_tls_for_remote(dsn, "JUVAL_RUNTIME_DB_URL")


@pytest.mark.parametrize("dsn", [
    "postgresql://db.example.com/postgres?sslmode=verify-full&sslrootcert=/etc/ca.pem",
    "postgresql://db.example.com/postgres?sslmode=verify-full",
    "host=/tmp/pg-socket dbname=x",                    # the disposable test clusters
    "postgresql://localhost/db",
    "postgresql://127.0.0.1:5432/db",
    "postgresql://[::1]/db",
    "dbname=x",                                         # libpq default: local socket
])
def test_tls_or_a_local_connection_is_accepted(dsn):
    require_tls_for_remote(dsn, "JUVAL_RUNTIME_DB_URL")


def test_pghost_counts_and_pgsslmode_does_not(monkeypatch):
    monkeypatch.setenv("PGHOST", "db.example.com")
    monkeypatch.setenv("PGSSLMODE", "verify-full")      # must be in the DSN itself
    with pytest.raises(RuntimeError, match="without TLS verify-full"):
        require_tls_for_remote("dbname=x", "JUVAL_RUNTIME_DB_URL")


def test_errors_never_echo_the_connection_string():
    secret = "synthetic-marker-never-echoed"
    for dsn in (f"not a dsn {secret}", f"host=db.example.com application_name={secret}"):
        with pytest.raises(RuntimeError) as refused:
            require_tls_for_remote(dsn, "JUVAL_RUNTIME_DB_URL")
        assert secret not in str(refused.value)
        assert refused.value.__cause__ is None
        assert refused.value.__context__ is None or refused.value.__suppress_context__


def test_operator_tool_refuses_a_remote_admin_dsn_without_tls(monkeypatch):
    monkeypatch.setenv("SYNTHETIC_ADMIN_DSN", "postgresql://db.example.com/postgres")
    with pytest.raises(SystemExit, match="without TLS verify-full"):
        tenancy_admin.main(["--postgres-dsn-env", "SYNTHETIC_ADMIN_DSN", "create-organization",
                            "--name", "A", "--created-by", "ops"])
