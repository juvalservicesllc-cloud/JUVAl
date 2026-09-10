"""One contract, both adapters.

The same tests run against `InMemorySessionStore` and, when a database is
configured, against `PostgresSessionStore`. That is the point: ADR-036 allows
in-memory only for tests and local development, so a test that passes there
must mean something about production. Parametrising the fixture is how the two
adapters are prevented from drifting.

The PostgreSQL half requires the explicit test-only `JUVAL_TEST_SESSION_DB_URL`.
Runtime DSNs are never used. Each test owns a randomly named schema, with no
public-schema fallback, and removes only that schema in a finally block.
Use a disposable database; this suite does not authorize production migrations.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from juval.application.session_store import (
    OAuthTransaction,
    Session,
    digest,
)
from juval.infrastructure.crypto.token_cipher import TokenCipher, _Key
from juval.infrastructure.sessions.in_memory_session_store import (
    InMemoryOAuthTransactionStore,
    InMemorySessionStore,
)

DB_URL = os.environ.get("JUVAL_TEST_SESSION_DB_URL")

MIGRATION = "supabase/migrations/20260909000004_identity_sessions.sql"


def _now():
    return datetime.now(timezone.utc)


def _cipher():
    return TokenCipher(_Key("test-key", os.urandom(32)))


@pytest.fixture()
def session_db_dsn():
    if not DB_URL:
        pytest.skip("JUVAL_TEST_SESSION_DB_URL not set -- disposable session database required")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    schema = "juval_session_test_" + secrets.token_hex(12)
    with psycopg.connect(DB_URL) as conn:
        conn.execute(sql.SQL("create schema {}").format(sql.Identifier(schema)))
    try:
        # No public fallback: a missing test table must fail, never hit runtime.
        yield make_conninfo(DB_URL, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(DB_URL) as conn:
            conn.execute(sql.SQL("drop schema {} cascade").format(sql.Identifier(schema)))


@pytest.fixture(params=["memory", "postgres"])
def stores(request):
    if request.param == "memory":
        yield InMemorySessionStore(), InMemoryOAuthTransactionStore()
        return

    dsn = request.getfixturevalue("session_db_dsn")
    import psycopg
    from juval.infrastructure.persistence.postgres_session_store import (
        PostgresOAuthTransactionStore,
        PostgresSessionStore,
    )

    ddl = Path(MIGRATION).read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(ddl)

    cipher = _cipher()
    yield PostgresSessionStore(dsn, cipher), PostgresOAuthTransactionStore(dsn, cipher)


def _session(session_id=None, ttl=timedelta(hours=8), **overrides):
    now = _now()
    kwargs = dict(
        session_id=session_id or secrets.token_urlsafe(32),
        subject="user-1",
        roles=("operator",),
        csrf_token=secrets.token_urlsafe(32),
        created_at=now,
        expires_at=now + ttl,
        access_token="access-token-value",
        refresh_token="refresh-token-value",
        access_token_expires_at=now + timedelta(minutes=30),
    )
    kwargs.update(overrides)
    return Session(**kwargs)


def _transaction(transaction_id=None, ttl=timedelta(minutes=10)):
    now = _now()
    return OAuthTransaction(
        transaction_id=transaction_id or secrets.token_urlsafe(32),
        state=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),
        nonce=secrets.token_urlsafe(32),
        redirect_uri="https://api.test.invalid/api/v1/auth/callback",
        created_at=now,
        expires_at=now + ttl,
        return_to="/dashboard",
    )


# --- sessions ----------------------------------------------------------


def test_save_then_load(stores):
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    record = sessions.load(session.session_id, _now())
    assert record is not None
    assert record.subject == "user-1"
    assert record.roles == ("operator",)
    assert record.access_token == "access-token-value"
    assert record.refresh_token == "refresh-token-value"


def test_record_stores_digests_not_raw_identifiers(stores):
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    record = sessions.load(session.session_id, _now())
    assert record.session_digest == digest(session.session_id)
    assert record.csrf_digest == digest(session.csrf_token)
    # the record type has no field that is a bearer credential on its own
    assert not hasattr(record, "session_id")
    assert not hasattr(record, "csrf_token")


def test_unknown_session_is_none(stores):
    sessions, _ = stores
    assert sessions.load("never-issued", _now()) is None


def test_expired_session_is_none(stores):
    sessions, _ = stores
    session = _session(ttl=timedelta(seconds=-1))
    sessions.save(session)
    assert sessions.load(session.session_id, _now()) is None


def test_revoked_session_is_none(stores):
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    sessions.revoke(session.session_id, _now())
    assert sessions.load(session.session_id, _now()) is None


def test_revoke_is_idempotent(stores):
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    sessions.revoke(session.session_id, _now())
    sessions.revoke(session.session_id, _now())  # must not raise


def test_purge_expired_removes_only_dead_rows(stores):
    sessions, _ = stores
    live, dead = _session(), _session(ttl=timedelta(seconds=-1))
    sessions.save(live)
    sessions.save(dead)
    removed = sessions.purge_expired(_now())
    assert removed >= 1
    assert sessions.load(live.session_id, _now()) is not None


# --- refresh generation -------------------------------------------------


def test_replace_tokens_succeeds_on_the_expected_generation(stores):
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    assert sessions.replace_tokens(
        session.session_id, 0, "new-access", "new-refresh", None, _now()
    ) is True
    record = sessions.load(session.session_id, _now())
    assert record.access_token == "new-access"
    assert record.refresh_token == "new-refresh"
    assert record.refresh_generation == 1


def test_concurrent_replace_loses_and_does_not_clobber(stores):
    """The second writer using a stale generation must be rejected."""
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    assert sessions.replace_tokens(session.session_id, 0, "winner", "winner-r", None, _now())
    assert not sessions.replace_tokens(session.session_id, 0, "loser", "loser-r", None, _now())
    record = sessions.load(session.session_id, _now())
    assert record.access_token == "winner"


def test_replace_tokens_on_revoked_session_fails(stores):
    sessions, _ = stores
    session = _session()
    sessions.save(session)
    sessions.revoke(session.session_id, _now())
    assert not sessions.replace_tokens(session.session_id, 0, "a", "b", None, _now())


# --- oauth transactions -------------------------------------------------


def test_transaction_round_trip_returns_digests_and_the_verifier(stores):
    _, transactions = stores
    transaction = _transaction()
    transactions.start(transaction)
    record = transactions.consume(transaction.transaction_id, _now())
    assert record is not None
    assert record.state_digest == digest(transaction.state)
    assert record.nonce_digest == digest(transaction.nonce)
    assert record.code_verifier == transaction.code_verifier  # needed in plaintext
    assert record.redirect_uri == transaction.redirect_uri
    assert record.return_to == "/dashboard"


def test_transaction_is_single_use(stores):
    _, transactions = stores
    transaction = _transaction()
    transactions.start(transaction)
    assert transactions.consume(transaction.transaction_id, _now()) is not None
    assert transactions.consume(transaction.transaction_id, _now()) is None


def test_expired_transaction_is_none(stores):
    _, transactions = stores
    transaction = _transaction(ttl=timedelta(seconds=-1))
    transactions.start(transaction)
    assert transactions.consume(transaction.transaction_id, _now()) is None


def test_unknown_transaction_is_none(stores):
    _, transactions = stores
    assert transactions.consume("never-started", _now()) is None


def test_transaction_purge(stores):
    _, transactions = stores
    transactions.start(_transaction(ttl=timedelta(seconds=-1)))
    assert transactions.purge_expired(_now()) >= 1


# --- cross-instance semantics -------------------------------------------


def test_a_second_process_sees_the_same_session(stores):
    """Two store objects = two backend instances sharing one backend.

    For the in-memory adapter this is expected to be false, and the test says
    so explicitly rather than skipping: the difference between the adapters is
    exactly what ADR-036 is about.
    """
    sessions, _ = stores
    session = _session()
    sessions.save(session)

    if isinstance(sessions, InMemorySessionStore):
        other = InMemorySessionStore()
        assert other.load(session.session_id, _now()) is None  # documented limitation
        return

    from juval.infrastructure.persistence.postgres_session_store import PostgresSessionStore

    other = PostgresSessionStore(sessions._dsn, sessions._cipher)
    assert other.load(session.session_id, _now()) is not None


def test_login_on_one_instance_and_callback_on_another(stores):
    """The failure ADR-036 exists to prevent."""
    _, transactions = stores
    transaction = _transaction()
    transactions.start(transaction)

    if isinstance(transactions, InMemoryOAuthTransactionStore):
        other = InMemoryOAuthTransactionStore()
        assert other.consume(transaction.transaction_id, _now()) is None  # documented
        return

    from juval.infrastructure.persistence.postgres_session_store import (
        PostgresOAuthTransactionStore,
    )

    other = PostgresOAuthTransactionStore(transactions._dsn, transactions._cipher)
    assert other.consume(transaction.transaction_id, _now()) is not None


# --- ciphertext at rest (durable adapter only) --------------------------


def test_tokens_are_not_stored_in_plaintext(stores):
    sessions, _ = stores
    if isinstance(sessions, InMemorySessionStore):
        pytest.skip("in-memory holds objects, not rows; encryption is a storage concern")
    psycopg = pytest.importorskip("psycopg")
    session = _session()
    sessions.save(session)
    with psycopg.connect(sessions._dsn) as conn:
        row = conn.execute(
            "select access_token_ciphertext, refresh_token_ciphertext, crypto_key_id "
            "from identity_sessions where session_digest = %s",
            (digest(session.session_id),),
        ).fetchone()
    access_ct, refresh_ct, key_id = row
    assert "access-token-value" not in access_ct
    assert "refresh-token-value" not in refresh_ct
    assert access_ct.startswith("v1.")
    assert key_id == "test-key"


def test_a_row_encrypted_under_another_key_is_unusable(stores):
    sessions, _ = stores
    if isinstance(sessions, InMemorySessionStore):
        pytest.skip("encryption is a storage concern")
    from juval.infrastructure.persistence.postgres_session_store import PostgresSessionStore

    session = _session()
    sessions.save(session)
    stranger = PostgresSessionStore(sessions._dsn, _cipher())  # different key material
    assert stranger.load(session.session_id, _now()) is None  # fail closed, not raise


def test_migration_and_rollback_are_repeatable_and_isolated(session_db_dsn):
    import psycopg

    up = Path(MIGRATION).read_text(encoding="utf-8")
    down = Path(MIGRATION.replace(".sql", ".down.sql")).read_text(encoding="utf-8")
    with psycopg.connect(session_db_dsn) as conn:
        conn.execute("create table sentinel (value integer)")
        conn.execute("insert into sentinel values (42)")
        for _ in range(2):
            conn.execute(up)
        rows = conn.execute(
            "select relname, relrowsecurity, relforcerowsecurity, "
            "pg_get_userbyid(relowner) = current_user from pg_class "
            "where relnamespace = current_schema()::regnamespace "
            "and relname in ('identity_sessions', 'identity_oauth_transactions')"
        ).fetchall()
        assert len(rows) == 2
        assert all(rls and not force and owner for _, rls, force, owner in rows)
        for _ in range(2):
            conn.execute(down)
        assert conn.execute("select to_regclass('identity_sessions')").fetchone() == (None,)
        assert conn.execute("select to_regclass('identity_oauth_transactions')").fetchone() == (None,)
        assert conn.execute("select value from sentinel").fetchone() == (42,)
        conn.execute(up)
        assert conn.execute("select count(*) from identity_sessions").fetchone() == (0,)
