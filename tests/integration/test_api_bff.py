"""BFF authentication (ADR-034): state, PKCE, session custody, CSRF, logout.

No network: the token endpoint is stubbed and the ID token is signed with a
locally generated RSA key, so signature verification is real while nothing
leaves the process. No production credential, no real issuer.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from juval.application.session_store import digest
from juval.infrastructure.sessions.in_memory_session_store import (
    InMemoryOAuthTransactionStore,
    InMemorySessionStore,
)
from juval.interfaces.api import auth as auth_module
from juval.interfaces.api import bff
from juval.interfaces.api.main import app


class RecordingTransactionStore(InMemoryOAuthTransactionStore):
    """Keeps the raw nonce so a test can mint a matching ID token.

    The production store only ever holds `digest(nonce)` -- that is the whole
    point of ADR-036 -- so a test that needs the plaintext has to capture it at
    creation time, exactly as the BFF itself does.
    """

    def __init__(self) -> None:
        super().__init__()
        self.raw_nonce_by_state_digest: dict[str, str] = {}

    def start(self, transaction):
        self.raw_nonce_by_state_digest[digest(transaction.state)] = transaction.nonce
        super().start(transaction)

ISSUER = "https://idp.test.invalid"
AUDIENCE = "juval-test-client"
REDIRECT_URI = "https://api.test.invalid/api/v1/auth/callback"


@pytest.fixture()
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def configured(rsa_key, monkeypatch):
    """Auth enabled, verifier bound to the local key, BFF configured."""
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_BFF_INSECURE_COOKIES", "yes-local-http-only")
    auth_module.reset_for_tests()
    auth_module.set_verifier(
        auth_module.TokenVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            key_resolver=lambda token: rsa_key.public_key(),
        )
    )
    auth_module.set_session_resolver(bff.principal_from_session)
    bff.reset_for_tests()
    bff.configure(
        sessions=InMemorySessionStore(),
        transactions=RecordingTransactionStore(),
        config=bff.BffConfig(
            issuer=ISSUER,
            client_id=AUDIENCE,
            client_secret="test-client-secret",
            redirect_uri=REDIRECT_URI,
            post_login_redirect="/dashboard",
            post_logout_redirect="/bye",
            authorization_endpoint=f"{ISSUER}/oauth2/authorize",
            token_endpoint=f"{ISSUER}/oauth2/token",
            end_session_endpoint=f"{ISSUER}/oauth2/logout",
        )
    )
    yield
    auth_module.reset_for_tests()
    auth_module.set_session_resolver(None)
    bff.reset_for_tests()


def _id_token(rsa_key, *, nonce, sub="user-1", roles=("operator",), **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "nonce": nonce,
        "roles": list(roles),
    }
    claims.update(overrides)
    return jwt.encode(claims, rsa_key, algorithm="RS256")


def _raw_nonce(record):
    """Recover the plaintext nonce the BFF generated, via the recording store."""
    return bff._transactions.raw_nonce_by_state_digest[record.state_digest]


def _stub_token_endpoint(monkeypatch, rsa_key, *, nonce_from=None, **token_overrides):
    """Replace the one network call with a local, signed response."""
    nonce_from = nonce_from or _raw_nonce

    def fake_exchange(config, code, transaction):
        return {
            "access_token": "opaque-access-token",
            "refresh_token": "opaque-refresh-token",
            "expires_in": 3600,
            "id_token": _id_token(rsa_key, nonce=nonce_from(transaction), **token_overrides),
        }

    monkeypatch.setattr(bff, "_exchange_code", fake_exchange)


def _begin_login(client):
    response = client.get("/api/v1/auth/login", follow_redirects=False)
    assert response.status_code == 302
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(response.headers["location"]).query)
    return response, query


# --- the authorization request ----------------------------------------


def test_login_redirects_with_pkce_s256_state_and_nonce(configured):
    with TestClient(app) as client:
        response, query = _begin_login(client)
        assert query["response_type"] == ["code"]
        assert query["code_challenge_method"] == ["S256"]
        assert query["redirect_uri"] == [REDIRECT_URI]
        assert query["client_id"] == [AUDIENCE]
        assert len(query["state"][0]) >= 32
        assert len(query["nonce"][0]) >= 32
        # the verifier is NOT in the redirect; only the challenge is
        assert "code_verifier" not in query


def test_login_sets_httponly_transaction_cookie_only(configured):
    with TestClient(app) as client:
        response, _ = _begin_login(client)
        cookie_header = response.headers["set-cookie"]
        assert bff.TRANSACTION_COOKIE in cookie_header
        assert "httponly" in cookie_header.lower()
        assert bff.SESSION_COOKIE not in cookie_header


def test_pkce_challenge_is_the_s256_of_a_server_held_verifier(configured):
    import base64
    import hashlib

    with TestClient(app) as client:
        _, query = _begin_login(client)
        txn_id = client.cookies[bff.TRANSACTION_COOKIE]
        record = bff._transactions.consume(txn_id, datetime.now(timezone.utc))
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(record.code_verifier.encode()).digest()
        ).decode().rstrip("=")
        assert query["code_challenge"] == [expected]


# --- the callback: happy path -----------------------------------------


def test_callback_creates_session_and_never_returns_tokens(configured, rsa_key, monkeypatch):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        _, query = _begin_login(client)
        response = client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": query["state"][0]},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

        body = json.dumps(dict(response.headers))
        assert "opaque-access-token" not in body
        assert "opaque-refresh-token" not in body

        session = client.get("/api/v1/auth/session").json()
        assert session["authenticated"] is True
        assert session["subject"] == "user-1"
        assert session["roles"] == ["operator"]
        assert "runs:create" in session["permissions"]
        # the projection must never grow a token field
        assert "access_token" not in session
        assert "refresh_token" not in session
        assert "id_token" not in session


def test_session_cookie_is_httponly_and_csrf_cookie_is_not(configured, rsa_key, monkeypatch):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        _, query = _begin_login(client)
        response = client.get(
            "/api/v1/auth/callback",
            params={"code": "c", "state": query["state"][0]},
            follow_redirects=False,
        )
        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(c for c in cookies if c.startswith(bff.SESSION_COOKIE))
        csrf_cookie = next(c for c in cookies if c.startswith(bff.CSRF_COOKIE))
        assert "httponly" in session_cookie.lower()
        assert "samesite=lax" in session_cookie.lower()
        assert "httponly" not in csrf_cookie.lower()  # the SPA must read it


# --- the callback: every negative case --------------------------------


def test_callback_rejects_missing_state(configured):
    with TestClient(app) as client:
        _begin_login(client)
        assert client.get("/api/v1/auth/callback", params={"code": "c"}).status_code == 400


def test_callback_rejects_wrong_state(configured):
    with TestClient(app) as client:
        _begin_login(client)
        response = client.get(
            "/api/v1/auth/callback", params={"code": "c", "state": "attacker-supplied"}
        )
        assert response.status_code == 400


def test_callback_rejects_missing_transaction_cookie(configured):
    with TestClient(app) as client:
        _, query = _begin_login(client)
        client.cookies.delete(bff.TRANSACTION_COOKIE)
        response = client.get(
            "/api/v1/auth/callback", params={"code": "c", "state": query["state"][0]}
        )
        assert response.status_code == 400


def test_callback_cannot_be_replayed(configured, rsa_key, monkeypatch):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        _, query = _begin_login(client)
        state = query["state"][0]
        txn = client.cookies[bff.TRANSACTION_COOKIE]
        first = client.get(
            "/api/v1/auth/callback", params={"code": "c", "state": state}, follow_redirects=False
        )
        assert first.status_code == 302
        client.cookies.set(bff.TRANSACTION_COOKIE, txn)
        replay = client.get("/api/v1/auth/callback", params={"code": "c", "state": state})
        assert replay.status_code == 400


def test_callback_rejects_id_token_with_wrong_nonce(configured, rsa_key, monkeypatch):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=lambda t: "not-the-nonce")
    with TestClient(app) as client:
        _, query = _begin_login(client)
        response = client.get(
            "/api/v1/auth/callback", params={"code": "c", "state": query["state"][0]}
        )
        assert response.status_code == 400


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://evil.test.invalid"},
        {"aud": "some-other-client"},
        {"exp": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())},
    ],
    ids=["wrong-issuer", "wrong-audience", "expired"],
)
def test_callback_rejects_bad_id_token_claims(configured, rsa_key, monkeypatch, overrides):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce, **overrides)
    with TestClient(app) as client:
        _, query = _begin_login(client)
        response = client.get(
            "/api/v1/auth/callback", params={"code": "c", "state": query["state"][0]}
        )
        assert response.status_code in (400, 401)


def test_callback_rejects_id_token_signed_with_another_key(configured, monkeypatch):
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _stub_token_endpoint(monkeypatch, attacker_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        _, query = _begin_login(client)
        response = client.get(
            "/api/v1/auth/callback", params={"code": "c", "state": query["state"][0]}
        )
        assert response.status_code in (400, 401)


def test_open_redirect_is_not_possible_via_return_to(configured, rsa_key, monkeypatch):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/login",
            params={"return_to": "https://evil.test.invalid/steal"},
            follow_redirects=False,
        )
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(response.headers["location"]).query)
        callback = client.get(
            "/api/v1/auth/callback",
            params={"code": "c", "state": query["state"][0]},
            follow_redirects=False,
        )
        assert callback.headers["location"] == "/dashboard"


def test_protocol_relative_return_to_is_rejected(configured, rsa_key, monkeypatch):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/login", params={"return_to": "//evil.test.invalid"}, follow_redirects=False
        )
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(response.headers["location"]).query)
        callback = client.get(
            "/api/v1/auth/callback",
            params={"code": "c", "state": query["state"][0]},
            follow_redirects=False,
        )
        assert callback.headers["location"] == "/dashboard"


# --- session, RBAC and CSRF -------------------------------------------


def _login(client, rsa_key, monkeypatch, roles=("operator",)):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce, roles=roles)
    _, query = _begin_login(client)
    client.get(
        "/api/v1/auth/callback",
        params={"code": "c", "state": query["state"][0]},
        follow_redirects=False,
    )
    return client.get("/api/v1/auth/session").json()


def test_session_endpoint_reports_unauthenticated_without_a_cookie(configured):
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/session").json() == {"authenticated": False}


def test_invalid_session_cookie_is_not_authenticated(configured):
    with TestClient(app) as client:
        client.cookies.set(bff.SESSION_COOKIE, "forged-session-id")
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_session_cookie_authenticates_a_protected_read(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("viewer",))
        # viewer holds runs:read; the store is unconfigured, so a 503 here means
        # authorization passed and the handler ran.
        response = client.get("/api/v1/runs")
        assert response.status_code != 401
        assert response.status_code != 403


def test_role_without_permission_is_403_not_401(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("viewer",))
        response = client.get("/api/v1/runs/some-run/download")
        assert response.status_code == 403


def test_unknown_role_grants_nothing(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        session = _login(client, rsa_key, monkeypatch, roles=("not-a-juval-role",))
        assert session["permissions"] == []
        assert client.get("/api/v1/runs").status_code == 403


def test_state_changing_request_without_csrf_header_is_rejected(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        response = client.post("/api/v1/runs", files={"file": ("a.xlsx", b"x")})
        assert response.status_code == 403
        assert "csrf" in response.json()["detail"].lower()


def test_state_changing_request_with_wrong_csrf_header_is_rejected(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        response = client.post(
            "/api/v1/runs",
            files={"file": ("a.xlsx", b"x")},
            headers={bff.CSRF_HEADER: "wrong-token"},
        )
        assert response.status_code == 403


def test_state_changing_request_with_correct_csrf_header_passes_the_guard(
    configured, rsa_key, monkeypatch
):
    with TestClient(app) as client:
        session = _login(client, rsa_key, monkeypatch)
        response = client.post(
            "/api/v1/runs",
            files={"file": ("a.xlsx", b"not-a-real-workbook")},
            headers={bff.CSRF_HEADER: session["csrf_token"]},
        )
        # Past auth and CSRF; the upload itself is rejected on its own merits.
        assert response.status_code not in (401, 403)


def test_logout_clears_the_session_and_offers_idp_logout(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        session = _login(client, rsa_key, monkeypatch)
        response = client.post("/api/v1/auth/logout", headers={bff.CSRF_HEADER: session["csrf_token"]})
        assert response.status_code == 200
        assert response.json()["logged_out"] is True
        assert response.json()["end_session_url"].startswith(f"{ISSUER}/oauth2/logout")
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_logout_requires_csrf(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        assert client.post("/api/v1/auth/logout").status_code == 403
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True


def test_expired_session_is_not_authenticated(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        session_id = client.cookies[bff.SESSION_COOKIE]
        stored = bff._sessions._items[digest(session_id)]
        import dataclasses

        stored.record = dataclasses.replace(
            stored.record, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False


# --- disabled mode -----------------------------------------------------


def test_bff_routes_report_disabled_when_auth_mode_is_unset(monkeypatch):
    monkeypatch.delenv("JUVAL_AUTH_MODE", raising=False)
    auth_module.reset_for_tests()
    auth_module.set_session_resolver(None)
    bff.reset_for_tests()
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/auth/login", follow_redirects=False).status_code == 404
    finally:
        auth_module.reset_for_tests()
        bff.reset_for_tests()


# --- startup validation and store wiring (ADR-036) ---------------------
#
# The recovery audit found that session consumers read a module-global store
# that `build_stores()` might never have populated: a worker that had not
# served /login answered cookie requests from the pre-initialisation
# placeholder. Fail-closed (a 401), but the durable, multi-instance session
# layer ADR-036 exists to provide was not actually in use. These tests pin the
# corrected contract: one initialisation point, reached by every consumer, and
# an invalid production configuration that stops startup instead of surfacing
# as an intermittent runtime fault.


@pytest.fixture()
def unconfigured(monkeypatch):
    """A process that has chosen nothing yet -- the shape the bug needed."""
    auth_module.reset_for_tests()
    auth_module.set_session_resolver(bff.principal_from_session)
    bff.reset_for_tests()
    yield monkeypatch
    auth_module.reset_for_tests()
    auth_module.set_session_resolver(None)
    bff.reset_for_tests()


def _oidc_browser_env(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("JUVAL_OIDC_CLIENT_ID", AUDIENCE)
    monkeypatch.setenv("JUVAL_BFF_REDIRECT_URI", REDIRECT_URI)


def test_startup_fails_closed_when_the_durable_store_is_unconfigured(unconfigured):
    """A missing DSN stops the process, rather than 500ing on some later request."""
    monkeypatch = unconfigured
    _oidc_browser_env(monkeypatch)
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.delenv("JUVAL_SESSION_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)

    with pytest.raises(RuntimeError, match="JUVAL_SESSION_DB_URL"):
        with TestClient(app):
            pass  # pragma: no cover - startup must raise before this runs


def test_startup_fails_closed_without_an_encryption_key(unconfigured):
    monkeypatch = unconfigured
    _oidc_browser_env(monkeypatch)
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.setenv("JUVAL_SESSION_DB_URL", "postgresql://unused/db")
    monkeypatch.delenv("JUVAL_SESSION_ENCRYPTION_KEYS", raising=False)

    with pytest.raises(RuntimeError, match="cannot start"):
        with TestClient(app):
            pass  # pragma: no cover


def test_startup_fails_closed_on_a_half_configured_browser_flow(unconfigured):
    """client_id without redirect_uri is a configuration error, not a default."""
    monkeypatch = unconfigured
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("JUVAL_OIDC_CLIENT_ID", AUDIENCE)
    monkeypatch.delenv("JUVAL_BFF_REDIRECT_URI", raising=False)
    monkeypatch.setenv("JUVAL_SESSION_STORE", "memory")
    monkeypatch.setenv("JUVAL_SESSION_STORE_MEMORY_CONFIRM", bff._MEMORY_OPT_IN)

    with pytest.raises(RuntimeError, match="JUVAL_BFF_REDIRECT_URI"):
        with TestClient(app):
            pass  # pragma: no cover


def test_startup_never_downgrades_a_configured_postgres_store_to_memory(unconfigured):
    """The silent degradation ADR-036 forbids: it must raise, not fall back."""
    monkeypatch = unconfigured
    _oidc_browser_env(monkeypatch)
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.delenv("JUVAL_SESSION_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)

    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass  # pragma: no cover
    # Nothing was installed as a consolation prize.
    assert bff._configured is False


def test_bearer_only_deployment_starts_and_disables_the_browser_routes(unconfigured):
    """OIDC without any BFF variable is a valid, honest shape: no session, 404.

    It must not demand a database for a capability it never asked for, and it
    must not pretend the login endpoint works.
    """
    monkeypatch = unconfigured
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", AUDIENCE)
    for name in bff._BFF_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("JUVAL_SESSION_STORE", raising=False)

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/login", follow_redirects=False)
        assert response.status_code == 404
        assert response.json()["detail"] == "browser authentication is not configured"


def test_every_session_consumer_uses_the_store_startup_selected(unconfigured, rsa_key):
    """One store, reached by login, callback, resolution, CSRF and logout.

    The spy is installed by `build_stores()` -- i.e. through the single
    initialisation point -- and nothing else is configured by hand, which is
    exactly the arrangement that used to leave consumers on the placeholder.
    """
    monkeypatch = unconfigured
    _oidc_browser_env(monkeypatch)
    monkeypatch.setenv("JUVAL_BFF_INSECURE_COOKIES", "yes-local-http-only")

    class SpySessionStore(InMemorySessionStore):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[str] = []

        def save(self, session):
            self.calls.append("save")
            return super().save(session)

        def load(self, session_id, now):
            self.calls.append("load")
            return super().load(session_id, now)

        def revoke(self, session_id, now):
            self.calls.append("revoke")
            return super().revoke(session_id, now)

    spy = SpySessionStore()
    transactions = RecordingTransactionStore()
    placeholder = bff._sessions
    monkeypatch.setattr(bff, "build_stores", lambda: (spy, transactions))
    auth_module.set_verifier(
        auth_module.TokenVerifier(
            issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: rsa_key.public_key()
        )
    )

    with TestClient(app) as client:
        assert bff.session_store() is spy
        _login(client, rsa_key, monkeypatch)
        assert "save" in spy.calls                      # callback wrote here

        assert client.get("/api/v1/auth/session").json()["authenticated"] is True
        assert client.get("/api/v1/runs").status_code not in (401, 403)  # resolver read here

        csrf = client.cookies[bff.CSRF_COOKIE]
        client.post("/api/v1/auth/logout", headers={bff.CSRF_HEADER: csrf})
        assert "revoke" in spy.calls                    # logout revoked here

    # The pre-initialisation placeholder never served anything.
    assert placeholder is not spy
    assert not placeholder._items
