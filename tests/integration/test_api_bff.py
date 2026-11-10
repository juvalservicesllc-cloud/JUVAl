"""BFF authentication (ADR-034): state, PKCE, session custody, CSRF, logout.

No network: the token endpoint is stubbed and the ID token is signed with a
locally generated RSA key, so signature verification is real while nothing
leaves the process. No production credential, no real issuer.
"""

from __future__ import annotations

import dataclasses
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

from .api_lab import LOOPBACK


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


def _callback_location(client, return_to):
    response = client.get("/api/v1/auth/login", params={"return_to": return_to}, follow_redirects=False)
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(response.headers["location"]).query)
    callback = client.get("/api/v1/auth/callback", params={"code": "c", "state": query["state"][0]},
                          follow_redirects=False)
    return callback.headers["location"]


@pytest.mark.parametrize("return_to", ["/\\evil.test.invalid", "/\t/evil.test.invalid", "/\n/evil.test.invalid",
                                       "\\\\evil.test.invalid", "https:/evil.test.invalid"])
def test_return_to_that_a_browser_could_read_as_another_host_is_rejected(configured, rsa_key, monkeypatch,
                                                                           return_to):
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        assert _callback_location(client, return_to) == "/dashboard"


def test_return_to_lands_on_the_app_origin_in_the_adr038_topology(configured, rsa_key, monkeypatch):
    """The callback is served by the API host; a bare path would land there."""
    bff.configure(config=dataclasses.replace(bff.current_config(),
                                             post_login_redirect="https://app.test.invalid/home"))
    _stub_token_endpoint(monkeypatch, rsa_key, nonce_from=_raw_nonce)
    with TestClient(app) as client:
        assert _callback_location(client, "/runs/abc?tab=records") == "https://app.test.invalid/runs/abc?tab=records"
        assert _callback_location(client, "https://evil.test.invalid/x") == "https://app.test.invalid/home"
        assert _callback_location(client, "//evil.test.invalid") == "https://app.test.invalid/home"


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


# The two 403 bodies are a client contract: frontend-next renews its CSRF token
# and retries exactly once on the CSRF detail, and never on the permission one
# (frontend-next/src/api/client.ts). Exact strings, not substrings.
CSRF_REJECTED = {"detail": "csrf token missing or invalid"}
PERMISSION_DENIED = {"detail": "insufficient permissions"}


def test_csrf_and_permission_403s_have_distinct_exact_bodies(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        response = client.post("/api/v1/batches", files={"files": ("a.csv", b"x")}, data={"thresholds": "{}", "fees": "{}"})
        assert (response.status_code, response.json()) == (403, CSRF_REJECTED)
    with TestClient(app) as client:
        session = _login(client, rsa_key, monkeypatch, roles=("viewer",))
        response = client.post(
            "/api/v1/batches",
            files={"files": ("a.csv", b"x")},
            data={"thresholds": "{}", "fees": "{}"},
            headers={bff.CSRF_HEADER: session["csrf_token"]},
        )
        assert (response.status_code, response.json()) == (403, PERMISSION_DENIED)


@pytest.mark.parametrize("path, files", [
    ("/api/v1/batches", {"files": ("a.csv", b"x")}),
    ("/api/v1/runs/preview", {"file": ("a.csv", b"x")}),
])
def test_a_csrf_rejected_post_never_reaches_its_handler(configured, rsa_key, monkeypatch, path, files):
    """Why a client retry after the CSRF 403 cannot duplicate a batch: the
    guard is a dependency, so the handler -- ids, storage, processing -- never ran."""
    from juval.interfaces.api import service as service_module

    reached = []
    monkeypatch.setattr(service_module, "new_execution_id", lambda: reached.append("id") or "never")
    monkeypatch.setattr(service_module, "storage_dir", lambda: reached.append("storage") or "/nonexistent")
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        response = client.post(path, files=files, data={"thresholds": "{}", "fees": "{}"}, headers={bff.CSRF_HEADER: "stale"})
    assert (response.status_code, response.json()) == (403, CSRF_REJECTED)
    assert reached == []


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


def test_a_revoked_session_cannot_be_reused(configured, rsa_key, monkeypatch):
    """Logout revokes server-side: replaying the captured cookie and CSRF token gets nothing."""
    with TestClient(app) as client:
        session = _login(client, rsa_key, monkeypatch, roles=("admin",))
        captured = client.cookies[bff.SESSION_COOKIE]
        assert client.post("/api/v1/auth/logout", headers={bff.CSRF_HEADER: session["csrf_token"]}).status_code == 200
        client.cookies.set(bff.SESSION_COOKIE, captured)
        client.cookies.set(bff.CSRF_COOKIE, session["csrf_token"])
        assert client.get("/api/v1/auth/session").json() == {"authenticated": False}
        assert client.get("/api/v1/runs").status_code == 401
        replay = client.post("/api/v1/runs", headers={bff.CSRF_HEADER: session["csrf_token"]},
                             files={"file": ("a.csv", b"x", "text/csv")})
        assert replay.status_code == 401


def test_a_new_login_revokes_the_session_the_browser_held(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("admin",))
        previous = client.cookies[bff.SESSION_COOKIE]
        session = _login(client, rsa_key, monkeypatch, roles=("viewer",))
        assert client.cookies[bff.SESSION_COOKIE] != previous
        assert session["roles"] == ["viewer"]
        assert bff.session_store().load(previous, datetime.now(timezone.utc)) is None
        client.cookies.set(bff.SESSION_COOKIE, previous)
        assert client.get("/api/v1/auth/session").json()["authenticated"] is False


class _UnavailableSessionStore(InMemorySessionStore):
    def load(self, session_id, now):
        raise RuntimeError("SYNTHETIC-DRIVER-DETAIL host=db.internal user=juval_backend")


def test_an_unavailable_session_store_fails_closed_without_details(configured, caplog):
    bff.configure(sessions=_UnavailableSessionStore())
    with TestClient(app) as client:
        client.cookies.set(bff.SESSION_COOKIE, "some-session-id")
        for method, path in (("get", "/api/v1/runs"), ("get", "/api/v1/auth/session"),
                             ("post", "/api/v1/auth/logout")):
            response = getattr(client, method)(path)
            assert (response.status_code, response.json()) == (503, {"detail": "session service unavailable"})
    assert "SYNTHETIC-DRIVER-DETAIL" not in caplog.text and "db.internal" not in caplog.text


# --- disabled mode -----------------------------------------------------


def test_bff_routes_report_disabled_in_the_loopback_lab(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "disabled")
    monkeypatch.setenv(auth_module.LAB_CONFIRM_ENV, auth_module.LAB_CONFIRM_VALUE)
    monkeypatch.delenv("JUVAL_CORS_ORIGINS", raising=False)
    auth_module.reset_for_tests()
    auth_module.set_session_resolver(None)
    bff.reset_for_tests()
    try:
        with TestClient(app, **LOOPBACK) as client:
            response = client.get("/api/v1/auth/login", follow_redirects=False)
            assert response.status_code == 404
            assert response.json() == {"detail": "authentication is not enabled"}
    finally:
        auth_module.reset_for_tests()
        bff.reset_for_tests()


def test_startup_fails_closed_when_auth_mode_is_unset(monkeypatch):
    """The BFF no longer has an "unset" shape to report: the process stops."""
    monkeypatch.delenv("JUVAL_AUTH_MODE", raising=False)
    auth_module.reset_for_tests()
    bff.reset_for_tests()
    try:
        with pytest.raises(RuntimeError, match="JUVAL_AUTH_MODE must be set"):
            with TestClient(app):
                pass  # pragma: no cover - startup must raise before this runs
    finally:
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
    monkeypatch.delenv("JUVAL_RUNTIME_DB_URL", raising=False)
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)

    with pytest.raises(RuntimeError, match="JUVAL_RUNTIME_DB_URL"):
        with TestClient(app):
            pass  # pragma: no cover - startup must raise before this runs


def test_startup_fails_closed_without_an_encryption_key(unconfigured):
    monkeypatch = unconfigured
    _oidc_browser_env(monkeypatch)
    monkeypatch.setenv("JUVAL_SESSION_STORE", "postgres")
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", "postgresql://unused/db")
    monkeypatch.delenv("JUVAL_SESSION_ENCRYPTION_KEYS", raising=False)

    with pytest.raises(RuntimeError, match="cannot start"):
        with TestClient(app):
            pass  # pragma: no cover


def test_startup_fails_closed_on_a_half_configured_browser_flow(unconfigured):
    """client_id without redirect_uri is a configuration error, not a default."""
    monkeypatch = unconfigured
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    # Complete token validation (ADR-055 checks it first), so the failure under
    # test is the browser flow's own missing redirect URI.
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", AUDIENCE)
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
    monkeypatch.delenv("JUVAL_RUNTIME_DB_URL", raising=False)
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


@pytest.mark.parametrize("failure", ["rejected", "unreachable"])
def test_session_projection_uses_state_after_refresh(configured, rsa_key, monkeypatch, failure):
    _stub_token_endpoint(monkeypatch, rsa_key)

    def fail_refresh(*args):
        if failure == "rejected":
            raise bff._RefreshRejected("provider refusal")
        raise OSError("provider unavailable")

    monkeypatch.setattr(bff, "_refresh_tokens", fail_refresh)
    # The clock jumps ~60 min to reach the token's expiry; isolate refresh from
    # the 30-min idle timeout, which has its own tests.
    bff.configure(config=bff.current_config(), sessions=InMemorySessionStore(idle_timeout=timedelta(hours=2)))
    with TestClient(app) as client:
        _, query = _begin_login(client)
        client.get("/api/v1/auth/callback", params={"code": "c", "state": query["state"][0]},
                   follow_redirects=False)
        session_id = client.cookies[bff.SESSION_COOKIE]
        near_expiry = bff._now() + timedelta(seconds=3590)
        monkeypatch.setattr(bff, "_now", lambda: near_expiry)
        response = client.get("/api/v1/auth/session")
        assert response.status_code == 200
        if failure == "rejected":
            assert response.json()["authenticated"] is False
            assert set(response.json()) == {"authenticated"}
            assert bff.session_store().load(session_id, bff._now()) is None
            assert bff.SESSION_COOKIE not in client.cookies
            assert bff.CSRF_COOKIE not in client.cookies
        else:
            assert response.json()["authenticated"] is True
            assert bff.session_store().load(session_id, bff._now()) is not None


def test_rotation_persistence_failure_eventually_requires_and_allows_relogin(configured, rsa_key, monkeypatch):
    """Provider rotation and DB write are not atomic; exercise the documented recovery."""
    bff.configure(config=bff.current_config(), sessions=InMemorySessionStore(idle_timeout=timedelta(hours=2)))  # see above
    with TestClient(app) as client:
        assert _login(client, rsa_key, monkeypatch)['authenticated'] is True
        old_session = client.cookies[bff.SESSION_COOKIE]
        near_expiry = bff._now() + timedelta(seconds=3590)
        monkeypatch.setattr(bff, '_now', lambda: near_expiry)
        used = set()
        def rotating_provider(config, token):
            if token in used:
                raise bff._RefreshRejected('synthetic consumed token')
            used.add(token)
            # A verifiable access token, so the write -- not verification -- fails.
            return {'access_token': _id_token(rsa_key, nonce='unused'), 'refresh_token': 'synthetic-rotated',
                    'expires_in': 3600}
        monkeypatch.setattr(bff, '_refresh_tokens', rotating_provider)
        store = bff.session_store()
        real_replace = store.replace_tokens
        def failed_write(*args, **kwargs):
            raise RuntimeError('synthetic persistence outage')
        monkeypatch.setattr(store, 'replace_tokens', failed_write)
        assert client.get('/api/v1/auth/session').json()['authenticated'] is True
        assert store.load(old_session, near_expiry).refresh_generation == 0
        monkeypatch.setattr(store, 'replace_tokens', real_replace)
        assert client.get('/api/v1/auth/session').json() == {'authenticated': False}
        assert store.load(old_session, near_expiry) is None
        assert bff.SESSION_COOKIE not in client.cookies
        assert _login(client, rsa_key, monkeypatch)['authenticated'] is True
        assert client.cookies[bff.SESSION_COOKIE] != old_session
        assert store.load(old_session, near_expiry) is None


# --- SEC-01E: inactivity and role freshness (controlled clock, no sleeps) -----


def _advance(monkeypatch, delta):
    later = bff._now() + delta
    monkeypatch.setattr(bff, "_now", lambda: later)
    return later


def test_a_session_idle_for_30_minutes_is_over(configured, rsa_key, monkeypatch):
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        _advance(monkeypatch, timedelta(minutes=29))
        assert client.get("/api/v1/auth/session").json()["authenticated"] is True   # activity
        _advance(monkeypatch, timedelta(minutes=30, seconds=1))
        assert client.get("/api/v1/runs").status_code == 401
        assert client.get("/api/v1/auth/session").json() == {"authenticated": False}


def test_browser_declared_activity_does_not_count(configured, rsa_key, monkeypatch):
    """Only requests the server resolves are activity; headers or cookies cannot fake it."""
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch)
        _advance(monkeypatch, timedelta(minutes=31))
        response = client.get("/api/v1/runs", headers={"X-Last-Activity": "now", "X-Requested-With": "x"})
        assert response.status_code == 401


def _long_idle(rsa_key):
    """Reach the access token's expiry (1 h) without tripping the idle timeout."""
    bff.configure(config=bff.current_config(), sessions=InMemorySessionStore(idle_timeout=timedelta(hours=2)))


def test_roles_are_re_derived_from_the_refreshed_verified_token(configured, rsa_key, monkeypatch):
    _long_idle(rsa_key)
    with TestClient(app) as client:
        assert _login(client, rsa_key, monkeypatch, roles=("admin",))["roles"] == ["admin"]
        monkeypatch.setattr(bff, "_refresh_tokens", lambda config, token: {
            "access_token": _id_token(rsa_key, nonce="unused", roles=("viewer",)),
            "refresh_token": "rotated", "expires_in": 3600})
        _advance(monkeypatch, timedelta(minutes=59))
        session = client.get("/api/v1/auth/session").json()
        assert session["roles"] == ["viewer"] and "runs:create" not in session["permissions"]
        assert client.post("/api/v1/runs", headers={bff.CSRF_HEADER: session["csrf_token"]},
                           files={"file": ("a.csv", b"x", "text/csv")}).status_code == 403


def test_without_a_refresh_token_the_session_ends_with_its_access_token(configured, rsa_key, monkeypatch):
    _long_idle(rsa_key)
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("admin",))
        session_id = client.cookies[bff.SESSION_COOKIE]
        stored = bff.session_store()._items[digest(session_id)]
        stored.record = dataclasses.replace(stored.record, refresh_token=None)
        _advance(monkeypatch, timedelta(minutes=61))
        assert client.get("/api/v1/runs").status_code == 401
        assert bff.session_store().load(session_id, bff._now()) is None     # revoked


def test_after_expiry_an_unreachable_idp_is_a_503_never_stale_roles(configured, rsa_key, monkeypatch):
    _long_idle(rsa_key)
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("admin",))
        session_id = client.cookies[bff.SESSION_COOKIE]

        def down(config, token):
            raise OSError("synthetic outage")

        monkeypatch.setattr(bff, "_refresh_tokens", down)
        _advance(monkeypatch, timedelta(minutes=61))
        response = client.get("/api/v1/runs")
        assert (response.status_code, response.json()) == (503, {"detail": "identity provider temporarily unavailable"})
        assert bff.session_store().load(session_id, bff._now()) is not None   # kept for a retry


@pytest.mark.parametrize("token", ["not-a-jwt", "subject-mismatch"])
def test_an_unverifiable_or_foreign_refreshed_token_never_grants_roles(configured, rsa_key, monkeypatch, token):
    _long_idle(rsa_key)
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("viewer",))
        session_id = client.cookies[bff.SESSION_COOKIE]
        issued = "not-a-jwt" if token == "not-a-jwt" else _id_token(rsa_key, nonce="x", sub="someone-else",
                                                                     roles=("admin",))
        monkeypatch.setattr(bff, "_refresh_tokens", lambda config, t: {"access_token": issued, "expires_in": 3600})
        _advance(monkeypatch, timedelta(minutes=61))
        assert client.get("/api/v1/runs").status_code in (401, 503)
        record = bff.session_store().load(session_id, bff._now())
        assert record is None or record.roles == ("viewer",)
        if token == "subject-mismatch":
            assert record is None                                             # revoked


@pytest.mark.parametrize("value", ["0", "481", "thirty", "-5"])
def test_an_invalid_idle_timeout_stops_store_selection(monkeypatch, value):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "memory")
    monkeypatch.setenv("JUVAL_SESSION_STORE_MEMORY_CONFIRM", "yes-single-process-development-only")
    monkeypatch.setenv(bff.IDLE_TIMEOUT_ENV, value)
    with pytest.raises(RuntimeError, match=bff.IDLE_TIMEOUT_ENV):
        bff.build_stores()


def test_the_idle_timeout_is_configured_on_the_server(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_SESSION_STORE", "memory")
    monkeypatch.setenv("JUVAL_SESSION_STORE_MEMORY_CONFIRM", "yes-single-process-development-only")
    monkeypatch.setenv(bff.IDLE_TIMEOUT_ENV, "45")
    sessions, _ = bff.build_stores()
    assert sessions._idle_timeout == timedelta(minutes=45)
    monkeypatch.delenv(bff.IDLE_TIMEOUT_ENV)
    assert bff.build_stores()[0]._idle_timeout == timedelta(minutes=30)
