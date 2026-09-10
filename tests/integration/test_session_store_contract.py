"""One contract, both adapters.

The same tests run against `InMemorySessionStore` and, when a database is
configured, against `PostgresSessionStore`. That is the point: ADR-036 allows
in-memory only for tests and local development, so a test that passes there
must mean something about production. Parametrising the fixture is how the two
adapters are prevented from drifting.

The PostgreSQL half is skipped unless `JUVAL_SESSION_DB_URL` (or
`JUVAL_SUPABASE_DB_URL`) points at a database -- the same convention
`test_supabase_execution_run_store.py` already uses. It never touches a
production project: the schema is created and dropped per run.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

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

DB_URL = os.environ.get("JUVAL_SESSION_DB_URL") or os.environ.get("JUVAL_SUPABASE_DB_URL")

MIGRATION = "supabase/migrations/20260909000004_identity_sessions.sql"


def _now():
    return datetime.now(timezone.utc)


def _cipher():
    return TokenCipher(_Key("test-key", os.urandom(32)))


@pytest.fixture(params=["memory", "postgres"])
def stores(request):
    if request.param == "memory":
        yield InMemorySessionStore(), InMemoryOAuthTransactionStore()
        return

    if not DB_URL:
        pytest.skip("JUVAL_SESSION_DB_URL not set -- no database to test the durable adapter")
    psycopg = pytest.importorskip("psycopg")
    from juval.infrastructure.persistence.postgres_session_store import (
        PostgresOAuthTransactionStore,
        PostgresSessionStore,
    )

    with open(MIGRATION, encoding="utf-8") as handle:
        ddl = handle.read()
    with psycopg.connect(DB_URL) as conn:
        conn.execute("drop table if exists identity_sessions cascade")
        conn.execute("drop table if exists identity_oauth_transactions cascade")
        conn.execute(ddl)

    cipher = _cipher()
    yield PostgresSessionStore(DB_URL, cipher), PostgresOAuthTransactionStore(DB_URL, cipher)

    with psycopg.connect(DB_URL) as conn:
        conn.execute("drop table if exists identity_sessions cascade")
        conn.execute("drop table if exists identity_oauth_transactions cascade")


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

    other = PostgresSessionStore(DB_URL, sessions._cipher)
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

    other = PostgresOAuthTransactionStore(DB_URL, transactions._cipher)
    assert other.consume(transaction.transaction_id, _now()) is not None


# --- ciphertext at rest (durable adapter only) --------------------------


def test_tokens_are_not_stored_in_plaintext(stores):
    sessions, _ = stores
    if isinstance(sessions, InMemorySessionStore):
        pytest.skip("in-memory holds objects, not rows; encryption is a storage concern")
    psycopg = pytest.importorskip("psycopg")
    session = _session()
    sessions.save(session)
    with psycopg.connect(DB_URL) as conn:
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
    stranger = PostgresSessionStore(DB_URL, _cipher())  # different key material
    assert stranger.load(session.session_id, _now()) is None  # fail closed, not raise
