"""Refresh rotation (ADR-036 Part E) and fail-closed store selection.

No network: the IdP call is replaced. No database: the in-memory adapter obeys
the same contract, which is why it is a legitimate substrate for these tests.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import pytest

from juval.application.session_store import Session
from juval.infrastructure.sessions.in_memory_session_store import InMemorySessionStore
from juval.interfaces.api import auth as auth_module
from juval.interfaces.api import bff


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture()
def wired(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    auth_module.reset_for_tests()
    bff.reset_for_tests()
    sessions = InMemorySessionStore()
    bff.configure(
        config=bff.BffConfig(
            issuer="https://idp.test.invalid",
            client_id="client",
            client_secret="secret",
            redirect_uri="https://api.test.invalid/api/v1/auth/callback",
            post_login_redirect="/",
            post_logout_redirect="/",
            authorization_endpoint="https://idp.test.invalid/oauth2/authorize",
            token_endpoint="https://idp.test.invalid/oauth2/token",
            end_session_endpoint="https://idp.test.invalid/oauth2/logout",
        ),
        sessions=sessions,
    )
    yield sessions
    auth_module.reset_for_tests()
    bff.reset_for_tests()


def _session(sessions, *, access_ttl):
    session_id = secrets.token_urlsafe(32)
    sessions.save(
        Session(
            session_id=session_id,
            subject="user-1",
            roles=("operator",),
            csrf_token=secrets.token_urlsafe(32),
            created_at=_now(),
            expires_at=_now() + timedelta(hours=8),
            access_token="old-access",
            refresh_token="old-refresh",
            access_token_expires_at=_now() + access_ttl,
        )
    )
    return session_id, sessions.load(session_id, _now())


# --- when refresh happens ----------------------------------------------


def test_no_refresh_while_the_access_token_is_fresh(wired, monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(bff, "_refresh_tokens", lambda *a: called.__setitem__("n", called["n"] + 1))
    session_id, record = _session(wired, access_ttl=timedelta(hours=1))
    assert bff.refresh_if_needed(session_id, record) is None
    assert called["n"] == 0


def test_refresh_when_the_access_token_is_near_expiry(wired, monkeypatch):
    monkeypatch.setattr(
        bff,
        "_refresh_tokens",
        lambda config, token: {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        },
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=30))
    updated = bff.refresh_if_needed(session_id, record)
    assert updated is not None
    assert updated.access_token == "new-access"
    assert updated.refresh_token == "new-refresh"
    assert updated.refresh_generation == 1


def test_session_id_does_not_rotate_on_refresh(wired, monkeypatch):
    """Rotating it would log out every other in-flight request from the tab."""
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "a", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=10))
    bff.refresh_if_needed(session_id, record)
    assert wired.load(session_id, _now()) is not None


def test_refresh_token_is_kept_when_the_idp_does_not_return_a_new_one(wired, monkeypatch):
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "a2", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=10))
    updated = bff.refresh_if_needed(session_id, record)
    assert updated.refresh_token == "old-refresh"


def test_session_without_a_refresh_token_is_left_alone(wired, monkeypatch):
    monkeypatch.setattr(bff, "_refresh_tokens", lambda c, t: pytest.fail("must not be called"))
    session_id = secrets.token_urlsafe(32)
    wired.save(
        Session(
            session_id=session_id,
            subject="s",
            roles=(),
            csrf_token="c",
            created_at=_now(),
            expires_at=_now() + timedelta(hours=1),
            access_token="a",
            refresh_token=None,
            access_token_expires_at=_now() + timedelta(seconds=5),
        )
    )
    assert bff.refresh_if_needed(session_id, wired.load(session_id, _now())) is None


# --- failure modes ------------------------------------------------------


def test_rejected_refresh_revokes_the_session(wired, monkeypatch):
    def reject(config, token):
        raise bff._RefreshRejected("HTTP 400")

    monkeypatch.setattr(bff, "_refresh_tokens", reject)
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    assert bff.refresh_if_needed(session_id, record) is None
    assert wired.load(session_id, _now()) is None  # revoked, not merely unrefreshed


def test_unreachable_idp_keeps_the_session(wired, monkeypatch):
    def boom(config, token):
        raise OSError("connection refused")

    monkeypatch.setattr(bff, "_refresh_tokens", boom)
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    assert bff.refresh_if_needed(session_id, record) is None
    assert wired.load(session_id, _now()) is not None  # still usable for RBAC


def test_persistence_failure_leaves_the_session_untouched(wired, monkeypatch):
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "n", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))

    def failing_replace(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(wired, "replace_tokens", failing_replace)
    assert bff.refresh_if_needed(session_id, record) is None
    assert wired.load(session_id, _now()).access_token == "old-access"


def test_concurrent_refresh_loser_reads_the_winners_tokens(wired, monkeypatch):
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "mine", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    # A concurrent request wins first, bumping the generation.
    assert wired.replace_tokens(session_id, 0, "winner-access", "winner-refresh", None, _now())
    # This caller still holds the stale generation-0 record.
    result = bff.refresh_if_needed(session_id, record)
    assert result is not None
    assert result.access_token == "winner-access"  # did not clobber
    assert result.refresh_generation == 1


# --- store selection: fail closed ---------------------------------------


def test_memory_store_is_used_when_auth_is_disabled(monkeypatch):
    monkeypatch.delenv("JUVAL_AUTH_MODE", raising=False)
    auth_module.reset_for_tests()
    sessions, transactions = bff.build_stores()
    assert isinstance(sessions, InMemorySessionStore)


def test_memory_store_is_refused_under_oidc_without_the_opt_in(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "memory")
    monkeypatch.delenv("JUVAL_SESSION_STORE_MEMORY_CONFIRM", raising=False)
    auth_module.reset_for_tests()
    with pytest.raises(RuntimeError, match="forbidden in production"):
        bff.build_stores()


def test_memory_store_allowed_under_oidc_with_the_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "memory")
    monkeypatch.setenv("JUVAL_SESSION_STORE_MEMORY_CONFIRM", bff._MEMORY_OPT_IN)
    auth_module.reset_for_tests()
    sessions, _ = bff.build_stores()
    assert isinstance(sessions, InMemorySessionStore)


def test_postgres_without_a_dsn_fails_closed(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.delenv("JUVAL_SESSION_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)
    auth_module.reset_for_tests()
    with pytest.raises(RuntimeError, match="JUVAL_SESSION_DB_URL"):
        bff.build_stores()


def test_postgres_without_an_encryption_key_fails_closed(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.setenv("JUVAL_SESSION_DB_URL", "postgresql://unused/db")
    monkeypatch.delenv("JUVAL_SESSION_ENCRYPTION_KEYS", raising=False)
    auth_module.reset_for_tests()
    with pytest.raises(RuntimeError, match="cannot start"):
        bff.build_stores()


def test_unknown_store_backend_fails_closed(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "redis")
    auth_module.reset_for_tests()
    with pytest.raises(RuntimeError, match="unrecognized value"):
        bff.build_stores()


# --- one initialisation point (recovery-phase regression) ---------------


def test_accessors_initialise_instead_of_serving_the_placeholder(monkeypatch):
    """The exact defect the recovery audit found.

    Before the fix, `session_store()` (and therefore the session resolver and
    the CSRF guard) returned the module-global placeholder in any process that
    had not yet served `/login`, even when `build_stores()` would have selected
    PostgreSQL. Fail-closed, but the durable store was never reached.
    """
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", "https://idp.test.invalid")
    monkeypatch.setenv("JUVAL_OIDC_CLIENT_ID", "client")
    monkeypatch.setenv("JUVAL_BFF_REDIRECT_URI", "https://api.test.invalid/api/v1/auth/callback")
    auth_module.reset_for_tests()
    bff.reset_for_tests()
    placeholder = bff._sessions
    selected = InMemorySessionStore()
    monkeypatch.setattr(bff, "build_stores", lambda: (selected, bff._transactions))
    try:
        assert bff.session_store() is selected
        assert bff.session_store() is not placeholder
        assert bff.transaction_store() is not None
        assert bff._configured is True
    finally:
        auth_module.reset_for_tests()
        bff.reset_for_tests()


def test_ensure_configured_is_idempotent_and_never_overwrites_a_test_double(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    auth_module.reset_for_tests()
    bff.reset_for_tests()
    installed = InMemorySessionStore()
    bff.configure(config=None, sessions=installed)

    def must_not_run():  # pragma: no cover - asserted by not being called
        raise AssertionError("ensure_configured re-selected an already-configured process")

    monkeypatch.setattr(bff, "build_stores", must_not_run)
    try:
        bff.ensure_configured()
        assert bff.session_store() is installed
    finally:
        auth_module.reset_for_tests()
        bff.reset_for_tests()


def test_bearer_only_deployment_needs_no_session_store(monkeypatch):
    """No BFF variable set: sessions cannot exist, so no DSN is demanded."""
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    for name in bff._BFF_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("JUVAL_SESSION_STORE", raising=False)
    monkeypatch.delenv("JUVAL_SESSION_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)
    auth_module.reset_for_tests()

    sessions, transactions = bff.build_stores()
    assert isinstance(sessions, InMemorySessionStore)
    assert bff.build_config() is None  # so /login answers 404 and never writes


def test_an_explicitly_named_store_is_checked_even_when_bearer_only(monkeypatch):
    """Naming the backend opts into the check; it is not skipped as unused."""
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    for name in bff._BFF_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.delenv("JUVAL_SESSION_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)
    auth_module.reset_for_tests()

    with pytest.raises(RuntimeError, match="JUVAL_SESSION_DB_URL"):
        bff.build_stores()
