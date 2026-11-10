"""Loopback lab helpers for API tests (ADR-055).

The API has no default authentication mode. A test that exercises routes
without identity opts in explicitly with the `auth_lab` fixture
(`tests/integration/conftest.py`) and builds its client with `LOOPBACK`, so the
requests look like what the lab accepts: a direct connection from 127.0.0.1 to
127.0.0.1 with a loopback Host. Nothing here is enabled globally.
"""

from __future__ import annotations

from juval.interfaces.api import auth

#: TestClient keyword arguments for a direct loopback request.
LOOPBACK = {"base_url": "http://127.0.0.1", "client": ("127.0.0.1", 50000)}


def install_lab(app, monkeypatch) -> None:
    """Bind `app` to the confirmed loopback lab, as a lab startup would."""
    monkeypatch.setenv("JUVAL_AUTH_MODE", "disabled")
    monkeypatch.setenv(auth.LAB_CONFIRM_ENV, auth.LAB_CONFIRM_VALUE)
    auth.install(app, auth.resolve_settings())


# ADR-056: the lab acts for a fixed synthetic organization. A test that writes
# a run straight into the store and then reads it through the lab API gives it
# this owner explicitly; a run saved without one is quarantined, as in
# production.
from juval.application.tenancy import LAB_ORGANIZATION_ID, Ownership  # noqa: E402

LAB_OWNER = Ownership(LAB_ORGANIZATION_ID, "urn:juval:local-lab", "local-lab-unauthenticated")


def lab_run_dir(storage_root, execution_id):
    """Where the lab API keeps a run's files under JUVAL_RUN_STORAGE_DIR."""
    return storage_root / "juval_runs" / LAB_ORGANIZATION_ID / execution_id


def assign_to_lab(db_path, *execution_ids):
    """Give CLI-written (unowned) runs to the lab organization, as an explicit
    test act: nothing in the product assigns history automatically (OD-3)."""
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        for execution_id in execution_ids:
            assert conn.execute(
                "UPDATE execution_runs SET organization_id=?, created_by_issuer=?, created_by_subject=? "
                "WHERE execution_id=? AND organization_id IS NULL",
                (LAB_OWNER.organization_id, LAB_OWNER.created_by_issuer, LAB_OWNER.created_by_subject, execution_id),
            ).rowcount == 1, execution_id


#: A synthetic customer organization for OIDC tests that need a member.
TEST_ORGANIZATION_ID = "7e570000-0000-4000-8000-000000000001"


def add_member(db_path, issuer, subject="00u-test-subject"):
    """Make `subject` a member of the test organization in the SQLite store at
    `db_path` (ADR-056: an OIDC identity without a membership gets no data)."""
    import sqlite3
    from datetime import datetime, timezone

    from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

    store = SqliteExecutionRunStore(db_path)
    now = datetime(2026, 11, 10, tzinfo=timezone.utc)
    try:
        store.create_organization(TEST_ORGANIZATION_ID, "Synthetic test organization", "test-fixture", now)
    except sqlite3.IntegrityError:
        pass  # another member was added to it earlier in this test
    store.add_membership(TEST_ORGANIZATION_ID, issuer, subject, "test-fixture", now)
