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


class _TokenVerifier:
    """Stands in for the API verifier: accepts only the synthetic tokens these
    tests mint ("<subject>|<role>,<role>"), rejects everything else."""

    def verify(self, token):
        from fastapi import HTTPException

        subject, sep, roles = token.partition("|")
        if not sep or not subject:
            raise HTTPException(status_code=401, detail="invalid or expired token")
        return auth_module.Principal(subject=subject, roles=tuple(r for r in roles.split(",") if r),
                                     permissions=frozenset(), issuer="https://idp.test.invalid")


VERIFIER = _TokenVerifier()


def refresh(session_id, record):
    return bff.refresh_if_needed(session_id, record, VERIFIER)


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
    assert refresh(session_id, record) is None
    assert called["n"] == 0


def test_refresh_when_the_access_token_is_near_expiry(wired, monkeypatch):
    monkeypatch.setattr(
        bff,
        "_refresh_tokens",
        lambda config, token: {
            "access_token": "user-1|viewer",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        },
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=30))
    updated = refresh(session_id, record)
    assert updated is not None
    assert updated.access_token == "user-1|viewer"
    assert updated.refresh_token == "new-refresh"
    assert updated.refresh_generation == 1
    assert updated.roles == ("viewer",)   # re-derived from the verified token (SEC-01E)


def test_session_id_does_not_rotate_on_refresh(wired, monkeypatch):
    """Rotating it would log out every other in-flight request from the tab."""
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "user-1|operator", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=10))
    refresh(session_id, record)
    assert wired.load(session_id, _now()) is not None


def test_refresh_token_is_kept_when_the_idp_does_not_return_a_new_one(wired, monkeypatch):
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "user-1|operator", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=10))
    updated = refresh(session_id, record)
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
    assert refresh(session_id, wired.load(session_id, _now())) is None


# --- failure modes ------------------------------------------------------


def test_rejected_refresh_revokes_the_session(wired, monkeypatch):
    def reject(config, token):
        raise bff._RefreshRejected("HTTP 400")

    monkeypatch.setattr(bff, "_refresh_tokens", reject)
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    assert refresh(session_id, record) is None
    assert wired.load(session_id, _now()) is None  # revoked, not merely unrefreshed


def test_unreachable_idp_keeps_the_session(wired, monkeypatch):
    def boom(config, token):
        raise OSError("connection refused")

    monkeypatch.setattr(bff, "_refresh_tokens", boom)
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    assert refresh(session_id, record) is None
    assert wired.load(session_id, _now()) is not None  # still usable for RBAC


def test_persistence_failure_leaves_the_session_untouched(wired, monkeypatch):
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "user-1|operator", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))

    def failing_replace(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(wired, "replace_tokens", failing_replace)
    assert refresh(session_id, record) is None
    assert wired.load(session_id, _now()).access_token == "old-access"


def test_concurrent_refresh_loser_reads_the_winners_tokens(wired, monkeypatch):
    monkeypatch.setattr(
        bff, "_refresh_tokens", lambda c, t: {"access_token": "user-1|operator", "expires_in": 3600}
    )
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    # A concurrent request wins first, bumping the generation.
    assert wired.replace_tokens(session_id, 0, "winner-access", "winner-refresh", None, _now())
    # This caller still holds the stale generation-0 record.
    result = refresh(session_id, record)
    assert result is not None
    assert result.access_token == "winner-access"  # did not clobber
    assert result.refresh_generation == 1


# --- store selection: fail closed ---------------------------------------


def test_memory_store_is_used_when_auth_is_disabled(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "disabled")
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
    monkeypatch.delenv("JUVAL_RUNTIME_DB_URL", raising=False)
    monkeypatch.setenv("JUVAL_SESSION_DB_URL", "postgresql://user:password@localhost/db")
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", "postgresql://postgres:postgres@localhost/db")
    auth_module.reset_for_tests()
    with pytest.raises(RuntimeError, match="JUVAL_RUNTIME_DB_URL"):
        bff.build_stores()


def test_postgres_without_an_encryption_key_fails_closed(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", "postgresql://user:pass@localhost/db")
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
    monkeypatch.delenv("JUVAL_RUNTIME_DB_URL", raising=False)
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
    monkeypatch.delenv("JUVAL_RUNTIME_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)
    auth_module.reset_for_tests()

    with pytest.raises(RuntimeError, match="JUVAL_RUNTIME_DB_URL"):
        bff.build_stores()



def test_postgres_readiness_failure_aborts_selection_without_exposing_dsn(monkeypatch):
    from juval.infrastructure.persistence import postgres_session_store as postgres

    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setattr(bff.TokenCipher, "from_environment", lambda: object())
    auth_module.reset_for_tests()

    class BrokenDriver:
        @staticmethod
        def connect(*args, **kwargs):
            assert kwargs["connect_timeout"] == 5
            raise RuntimeError("sensitive-driver-diagnostic")

    monkeypatch.setattr(postgres, "_require_driver", lambda: BrokenDriver)
    with pytest.raises(RuntimeError, match="readiness failed") as error:
        bff.build_stores()
    import traceback
    rendered = "".join(traceback.format_exception(error.value))
    assert "sensitive-driver-diagnostic" not in rendered
    assert "postgresql://" not in rendered


def test_overlapping_refresh_calls_contact_provider_once(wired, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    calls = []
    def rotating_provider(config, token):
        calls.append(token)
        entered.set()
        assert release.wait(5)
        return {'access_token': 'user-1|operator', 'refresh_token': 'rotated', 'expires_in': 3600}
    monkeypatch.setattr(bff, '_refresh_tokens', rotating_provider)
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(refresh, session_id, record)
        try:
            assert entered.wait(5)
            assert pool.submit(refresh, session_id, record).result(timeout=5) is None
        finally:
            release.set()
        assert first.result(timeout=5).refresh_generation == 1
    assert calls == ['old-refresh']
    # Even after release a stale request must not replay the consumed token.
    assert refresh(session_id, record).refresh_generation == 1
    assert calls == ['old-refresh']


# --- B-1: concurrent requests on an expired access token (SEC-01G) -------


def _race(wired, monkeypatch, provider, *, sessions=1, callers=4, settle=None, ids_out=None):
    """Run `callers` concurrent `_fresh_session` calls per expired session.

    The provider is entered only by a refresher; it blocks until every caller
    has reached the refresh guard, so the others contend while the refresh is
    in flight. `settle` lets the test release the provider. Returns, per
    session, each caller's outcome: a record, None (401) or the HTTP status.
    """
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock

    from fastapi import HTTPException

    total = sessions * callers
    entered, count, lock = Event(), [0], Lock()
    original = wired.refresh_guard

    def spy(session_id, **kwargs):
        with lock:
            count[0] += 1
            if count[0] == total:
                entered.set()
        return original(session_id, **kwargs)

    monkeypatch.setattr(wired, "refresh_guard", spy)
    calls = []

    def gated(config, token):
        calls.append(token)
        assert entered.wait(5), "callers never reached the guard"
        if settle is not None:
            settle()
        return provider(config, token)

    monkeypatch.setattr(bff, "_refresh_tokens", gated)
    ids = []
    for n in range(sessions):
        session_id, _ = _session(wired, access_ttl=timedelta(seconds=-1))
        if n:
            wired.replace_tokens(session_id, 0, "a", f"refresh-{n}", _now() - timedelta(seconds=1), _now())
        ids.append(session_id)
    if ids_out is not None:
        ids_out.extend(ids)

    def call(session_id):
        snapshot = wired.load(session_id, _now())       # what the request loaded: expired
        try:
            return bff._fresh_session(session_id, snapshot, VERIFIER)
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = {s: [pool.submit(call, s) for _ in range(callers)] for s in ids}
        results = {s: [f.result(timeout=15) for f in fs] for s, fs in futures.items()}
    return ids, results, calls


def test_concurrent_requests_on_an_expired_token_all_get_the_refreshed_session(wired, monkeypatch):
    ids, results, calls = _race(wired, monkeypatch, lambda c, t: {
        "access_token": "user-1|operator", "refresh_token": "rotated", "expires_in": 3600})
    outcomes = results[ids[0]]
    assert all(not isinstance(o, int) and o is not None for o in outcomes), outcomes   # no spurious 503
    assert {o.refresh_generation for o in outcomes} == {1}
    assert calls == ["old-refresh"]                                                # one provider call


def test_disabled_account_ends_every_concurrent_request_as_signed_out(wired, monkeypatch):
    def reject(config, token):
        raise bff._RefreshRejected("HTTP 400")

    ids, results, calls = _race(wired, monkeypatch, reject)
    assert results[ids[0]] == [None] * 4          # 401 for all, never a 503 that hides it
    assert calls == ["old-refresh"]
    assert wired.load(ids[0], _now()) is None


def test_session_revoked_during_the_refresh_is_not_resurrected_for_waiters(wired, monkeypatch):
    known = []

    def revoke_then_rotate(config, token):
        wired.revoke(known[0], _now())           # operator revoke-sessions while refreshing
        return {"access_token": "user-1|operator", "refresh_token": "rotated", "expires_in": 3600}

    ids, results, calls = _race(wired, monkeypatch, revoke_then_rotate, ids_out=known)
    assert results[ids[0]] == [None] * 4
    assert calls == ["old-refresh"]


def test_a_real_provider_outage_stays_503_and_waiters_do_not_retry(wired, monkeypatch):
    def unreachable(config, token):
        raise OSError("connection refused")

    ids, results, calls = _race(wired, monkeypatch, unreachable)
    assert results[ids[0]] == [503] * 4           # the outage is not turned into success
    assert calls == ["old-refresh"]               # waiters never replay the refresh token
    assert wired.load(ids[0], _now()) is not None  # kept for a later retry (ADR-036)


def test_the_wait_is_bounded_and_ends_in_503(wired, monkeypatch):
    from threading import Event

    monkeypatch.setattr(bff, "_REFRESH_WAIT", timedelta(milliseconds=200))
    waiters_done = Event()
    finished = []

    def slow(config, token):
        return {"access_token": "user-1|operator", "refresh_token": "rotated", "expires_in": 3600}

    def hold_until_waiters_gave_up():
        # The refresher is still busy when the waiters' bounded wait ends.
        assert waiters_done.wait(10)

    original_fresh = bff._fresh_session

    def tracked(session_id, snapshot, verifier):
        try:
            return original_fresh(session_id, snapshot, verifier)
        finally:
            finished.append(1)
            if len(finished) == 3:
                waiters_done.set()

    monkeypatch.setattr(bff, "_fresh_session", tracked)
    ids, results, calls = _race(wired, monkeypatch, slow, settle=hold_until_waiters_gave_up)
    outcomes = results[ids[0]]
    assert sorted(o if isinstance(o, int) else 200 for o in outcomes) == [200, 503, 503, 503]
    assert calls == ["old-refresh"]


def test_concurrent_refreshes_of_different_sessions_stay_isolated(wired, monkeypatch):
    def per_session(config, token):
        return {"access_token": "user-1|operator", "refresh_token": f"{token}-rotated", "expires_in": 3600}

    ids, results, calls = _race(wired, monkeypatch, per_session, sessions=2, callers=2)
    assert sorted(calls) == ["old-refresh", "refresh-1"]          # one call per session, own token
    for session_id in ids:
        assert all(not isinstance(o, int) and o is not None for o in results[session_id])
        assert wired.load(session_id, _now()).refresh_generation >= 1
    assert wired.load(ids[0], _now()).refresh_token == "old-refresh-rotated"
    assert wired.load(ids[1], _now()).refresh_token == "refresh-1-rotated"


def test_logout_during_refresh_cannot_resurrect_session(wired, monkeypatch):
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    def provider(config, token):
        wired.revoke(session_id, _now())
        return {'access_token': 'user-1|operator', 'refresh_token': 'rotated', 'expires_in': 3600}
    monkeypatch.setattr(bff, '_refresh_tokens', provider)
    assert refresh(session_id, record) is None
    assert wired.load(session_id, _now()) is None


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
def test_provider_http_outage_does_not_revoke_session(wired, monkeypatch, status):
    import urllib.error
    def unavailable(*args, **kwargs):
        raise urllib.error.HTTPError('https://idp.test.invalid/token', status,
                                     'unavailable', {}, None)
    monkeypatch.setattr(bff.urllib.request, 'urlopen', unavailable)
    session_id, record = _session(wired, access_ttl=timedelta(seconds=5))
    assert refresh(session_id, record) is None
    assert wired.load(session_id, _now()) is not None
