"""tools/tenancy_admin.py against a disposable SQLite store (ADR-056)."""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import tenancy_admin  # noqa: E402

from juval.application.tenancy import LAB_ORGANIZATION_ID  # noqa: E402
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore  # noqa: E402

ISS = "https://idp.example"


def organization(db, capsys, name):
    assert tenancy_admin.main(["--sqlite", str(db), "create-organization", "--name", name, "--created-by", "ops"]) == 0
    return re.search(r"create-organization ([0-9a-f-]{36})", capsys.readouterr().out).group(1)


def member(db, *extra):
    return tenancy_admin.main(["--sqlite", str(db), "add-member", "--issuer", ISS, "--created-by", "ops", *extra])


def test_create_add_and_remove_with_an_audit_trail(tmp_path, capsys):
    db = tmp_path / "runs.db"
    org = organization(db, capsys, "Customer A")
    assert member(db, "--organization", org, "--subject", "user-1") == 0
    assert "add-member subject=user-1" in capsys.readouterr().out
    store = SqliteExecutionRunStore(db)
    assert store.organization_ids_for(ISS, "user-1") == [org]
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT created_by FROM organizations").fetchall() == [("ops",)]
        assert conn.execute("SELECT created_by FROM organization_memberships").fetchall() == [("ops",)]
    assert tenancy_admin.main(["--sqlite", str(db), "remove-member", "--issuer", ISS, "--subject", "user-1",
                               "--created-by", "ops"]) == 0
    assert f"organization={org} by=ops" in capsys.readouterr().out
    assert store.organization_ids_for(ISS, "user-1") == []
    with pytest.raises(SystemExit, match="nothing changed"):
        tenancy_admin.main(["--sqlite", str(db), "remove-member", "--issuer", ISS, "--subject", "user-1",
                            "--created-by", "ops"])


def test_duplicates_and_operator_errors_are_refused(tmp_path, capsys):
    db = tmp_path / "runs.db"
    first = organization(db, capsys, "Customer A")
    second = organization(db, capsys, "Customer B")
    with pytest.raises(sqlite3.IntegrityError):  # same name, other case and padding
        organization(db, capsys, "  customer a ")
    with pytest.raises(SystemExit, match="lab"):
        member(db, "--organization", LAB_ORGANIZATION_ID, "--subject", "s")
    with pytest.raises(sqlite3.IntegrityError):  # foreign key: no such organization
        member(db, "--organization", "12345678-1234-4123-8123-123456789abc", "--subject", "s")
    with pytest.raises(ValueError):
        member(db, "--organization", "not-a-uuid", "--subject", "s")
    member(db, "--organization", first, "--subject", "s")
    with pytest.raises(sqlite3.IntegrityError):  # OD-6: one organization per identity
        member(db, "--organization", second, "--subject", "s")
    with pytest.raises(sqlite3.IntegrityError):  # and no duplicate of the same membership
        member(db, "--organization", first, "--subject", "s")


@pytest.mark.parametrize("issuer, subject", [
    ("http://idp.example", "user-1"),                    # not https
    ("urn:juval:local-lab", "user-1"),                   # the lab's issuer
    ("https://user:pass@idp.example", "user-1"),         # credentials in the URL
    (ISS, "person@example.com"),                         # an email, not the sub
    (ISS, " user-1"),                                    # padded
    (ISS, "  "),
])
def test_identities_the_api_cannot_verify_are_refused(tmp_path, capsys, issuer, subject):
    db = tmp_path / "runs.db"
    org = organization(db, capsys, "Customer A")
    with pytest.raises(SystemExit):
        tenancy_admin.main(["--sqlite", str(db), "add-member", "--organization", org, "--issuer", issuer,
                            "--subject", subject, "--created-by", "ops"])
    assert SqliteExecutionRunStore(db).organization_ids_for(issuer, subject) == []


def test_postgres_dsn_comes_only_from_the_environment(monkeypatch):
    monkeypatch.delenv("SYNTHETIC_ADMIN_DSN", raising=False)
    with pytest.raises(SystemExit, match="SYNTHETIC_ADMIN_DSN is not set"):
        tenancy_admin.main(["--postgres-dsn-env", "SYNTHETIC_ADMIN_DSN", "create-organization", "--name", "A",
                            "--created-by", "ops"])


# --- revoke-sessions (SEC-01E) -------------------------------------------------
# The SQL itself runs against PostgreSQL in test_session_store_contract.py
# (tools/session_store_lab.py); here: arguments, target and audit line.


@pytest.fixture
def revoked(monkeypatch):
    from juval.infrastructure.persistence import postgres_session_store

    calls = []
    monkeypatch.setattr(postgres_session_store, "revoke_sessions",
                        lambda dsn, now, subject=None: calls.append((dsn, subject)) or 3)
    monkeypatch.setenv("SYNTHETIC_ADMIN_DSN", "host=/synthetic/socket dbname=juval")
    return calls


def test_revoke_sessions_of_one_subject_or_all(revoked, capsys):
    base = ["--postgres-dsn-env", "SYNTHETIC_ADMIN_DSN", "revoke-sessions", "--created-by", "ops"]
    assert tenancy_admin.main(base + ["--subject", "fa-user-1"]) == 0
    assert "revoke-sessions subject=fa-user-1 revoked=3 by=ops" in capsys.readouterr().out
    assert tenancy_admin.main(base + ["--all"]) == 0
    assert "revoke-sessions all revoked=3 by=ops" in capsys.readouterr().out
    assert revoked == [("host=/synthetic/socket dbname=juval", "fa-user-1"),
                       ("host=/synthetic/socket dbname=juval", None)]


@pytest.mark.parametrize("extra", [[], ["--subject", "a", "--all"], ["--subject", "person@example.com"],
                                   ["--subject", " padded"]])
def test_revoke_sessions_refuses_ambiguous_or_wrong_targets(revoked, extra):
    with pytest.raises(SystemExit):
        tenancy_admin.main(["--postgres-dsn-env", "SYNTHETIC_ADMIN_DSN", "revoke-sessions",
                            "--created-by", "ops", *extra])
    assert revoked == []


def test_revoke_sessions_needs_postgres(tmp_path, revoked):
    with pytest.raises(SystemExit, match="PostgreSQL"):
        tenancy_admin.main(["--sqlite", str(tmp_path / "x.db"), "revoke-sessions", "--all", "--created-by", "ops"])
