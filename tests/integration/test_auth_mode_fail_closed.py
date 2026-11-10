"""ADR-055: authentication mode selection fails closed.

Negative tests for every way the API used to (or could) serve a caller without
identity: no mode, a bad mode, an unconfirmed or hosted lab, remote or proxied
lab requests, incomplete OIDC, OIDC without a usable verifier, and a mode that
changes while the instance runs. Route coverage is taken from the application
itself, so a new data route is covered without editing this file.

No real credential appears here: the key pair is generated per run and the
"secret" strings are synthetic markers used to prove they are never echoed.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from juval.interfaces.api import auth, bff
from juval.interfaces.api.main import app

from .api_lab import LOOPBACK
from .test_api_auth import AUDIENCE, ISSUER, bearer, keypair, make_token  # noqa: F401 (fixture)

DATA_ROUTES = sorted(
    (method, re.sub(r"\{[^}]+\}", "x", route.path))
    for route in app.routes
    if getattr(route, "path", "").startswith("/api/v1/") and not route.path.startswith("/api/v1/auth")
    for method in route.methods
)
DOC_PATHS = ("/openapi.json", "/docs", "/redoc")
REMOTE = {"base_url": "http://127.0.0.1", "client": ("203.0.113.7", 40000)}
SECRET_MARKER = "synthetic-marker-7f3a9c"


def call(client, method, path, **kwargs):
    return client.request(method, path, **kwargs)


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Each test starts from an unstarted instance with no verifier override."""
    for name in ("JUVAL_AUTH_MODE", auth.LAB_CONFIRM_ENV, "JUVAL_CORS_ORIGINS", "JUVAL_SESSION_STORE",
                 "JUVAL_OIDC_CLIENT_ID", "JUVAL_BFF_REDIRECT_URI", "JUVAL_EXECUTION_STORE", "JUVAL_EXECUTION_DB_PATH"):
        monkeypatch.delenv(name, raising=False)
    auth.uninstall(app)
    auth.reset_for_tests()
    bff.reset_for_tests()
    yield
    auth.uninstall(app)
    auth.reset_for_tests()
    bff.reset_for_tests()


def lab_env(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "disabled")
    monkeypatch.setenv(auth.LAB_CONFIRM_ENV, auth.LAB_CONFIRM_VALUE)


@pytest.fixture
def oidc(monkeypatch, keypair):  # noqa: F811
    """OIDC started through the real lifespan with a verifier for the test key pair."""
    _, public_key = keypair
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    auth.set_verifier(auth.TokenVerifier(issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: public_key))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def startup_error(**client_kwargs) -> str:
    with pytest.raises(RuntimeError) as excinfo:
        with TestClient(app, **client_kwargs):
            pass  # pragma: no cover - startup must raise before this runs
    assert getattr(app.state, "juval_auth", None) is None  # nothing left bound
    return str(excinfo.value)


def test_every_data_route_is_covered():
    assert len(DATA_ROUTES) == 14


# --- missing and invalid mode ---------------------------------------------


def test_missing_mode_stops_startup():
    assert "JUVAL_AUTH_MODE must be set" in startup_error()


@pytest.mark.parametrize("value", ["", "   "])
def test_empty_mode_stops_startup(monkeypatch, value):
    monkeypatch.setenv("JUVAL_AUTH_MODE", value)
    assert "JUVAL_AUTH_MODE must be set" in startup_error()


@pytest.mark.parametrize("value", ["off", "none", "OIDC", "Disabled", "true", SECRET_MARKER])
def test_unknown_mode_stops_startup_without_echoing_the_value(monkeypatch, value):
    monkeypatch.setenv("JUVAL_AUTH_MODE", value)
    message = startup_error()
    assert "unrecognized value" in message
    assert SECRET_MARKER not in message


def test_an_unstarted_instance_grants_nothing():
    client = TestClient(app, raise_server_exceptions=False, **LOOPBACK)
    for method, path in DATA_ROUTES:
        assert call(client, method, path).status_code == 503, (method, path)


# --- the lab needs explicit, local-only confirmation -------------------------


@pytest.mark.parametrize("confirm", [None, "", "true", "yes", "1", SECRET_MARKER])
def test_disabled_without_the_exact_confirmation_stops_startup(monkeypatch, confirm):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "disabled")
    if confirm is not None:
        monkeypatch.setenv(auth.LAB_CONFIRM_ENV, confirm)
    message = startup_error()
    assert auth.LAB_CONFIRM_ENV in message
    assert SECRET_MARKER not in message


@pytest.mark.parametrize("variable", ["RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "VERCEL", "VERCEL_ENV"])
def test_disabled_on_a_hosting_platform_stops_startup(monkeypatch, variable):
    lab_env(monkeypatch)
    monkeypatch.setenv(variable, SECRET_MARKER)
    message = startup_error()
    assert "hosting platform" in message
    assert SECRET_MARKER not in message


@pytest.mark.parametrize("origins", ["https://app.example.com", "http://127.0.0.1:18772,https://juval.example",
                                     "http://10.0.0.5:18772", "null"])
def test_disabled_with_a_public_cors_origin_stops_startup(monkeypatch, origins):
    lab_env(monkeypatch)
    monkeypatch.setenv("JUVAL_CORS_ORIGINS", origins)
    assert "non-loopback origin" in startup_error()


def test_disabled_accepts_loopback_cors_origins(monkeypatch):
    lab_env(monkeypatch)
    monkeypatch.setenv("JUVAL_CORS_ORIGINS", "http://127.0.0.1:18772,http://localhost:5173,http://[::1]:8080")
    with TestClient(app, **LOOPBACK):
        assert app.state.juval_auth.mode == "disabled"


# --- the lab serves direct loopback requests only ------------------------------


@pytest.fixture
def lab(monkeypatch):
    lab_env(monkeypatch)
    with TestClient(app, raise_server_exceptions=False, **LOOPBACK) as client:
        yield client


def test_lab_serves_a_direct_loopback_request(lab):
    # No execution store is configured, so 500; the point is it is not refused.
    assert lab.get("/api/v1/runs").status_code not in (401, 403, 503)


def _scope(client, server, host):
    """The ASGI scope uvicorn builds; TestClient cannot express an IPv6 base_url."""
    from starlette.requests import Request

    return Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"host", host.encode())],
                    "client": client, "server": server, "query_string": b""})


@pytest.mark.parametrize("client,server,host,allowed", [
    (("::1", 1), ("::1", 18771), "[::1]:18771", True),
    (("::ffff:127.0.0.1", 1), ("127.0.0.1", 18771), "127.0.0.1:18771", True),
    (("127.0.0.2", 1), ("127.0.0.1", 18771), "localhost:18771", True),
    (("2001:db8::5", 1), ("::1", 18771), "[::1]:18771", False),
    (("::1", 1), ("2001:db8::1", 18771), "[::1]:18771", False),
    (None, ("127.0.0.1", 18771), "127.0.0.1", False),
    (("testclient", 50000), ("testserver", 80), "testserver", False),
])
def test_lab_loopback_rule_on_raw_scopes(client, server, host, allowed):
    assert auth.lab_request_allowed(_scope(client, server, host)) is allowed


@pytest.mark.parametrize("method,path", DATA_ROUTES)
def test_lab_refuses_a_remote_client_on_every_data_route(lab, method, path):
    response = call(TestClient(app, raise_server_exceptions=False, **REMOTE), method, path)
    assert response.status_code == 403
    assert response.json() == {"detail": "unauthenticated lab mode accepts direct loopback requests only"}


def test_lab_refuses_a_connection_to_a_non_loopback_local_address(lab):
    # A server bound to 0.0.0.0 reached through its LAN address.
    client = TestClient(app, raise_server_exceptions=False, base_url="http://192.168.1.20", client=("127.0.0.1", 40000))
    assert client.get("/api/v1/runs", headers={"host": "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize("header", ["Forwarded", "Via", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto",
                                    "X-Real-IP", "CF-Connecting-IP", "CF-Ray", "True-Client-IP"])
def test_lab_refuses_a_proxied_or_tunnelled_request(lab, header):
    assert lab.get("/api/v1/runs", headers={header: "198.51.100.4"}).status_code == 403


@pytest.mark.parametrize("host", ["juval.example.com", "attacker.example:18771", "192.168.1.20", "0.0.0.0",
                                  "evil.example@127.0.0.1", "127.0.0.1.evil.example", "localhost.evil.example"])
def test_lab_refuses_a_non_loopback_host_header(lab, host):
    """A tunnel keeps the public Host; DNS rebinding sends the attacker's name."""
    assert lab.get("/api/v1/runs", headers={"host": host}).status_code == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://192.168.1.20:18772",
                                    "http://evil.example@127.0.0.1:18772", "file://", "http://127.0.0.1.evil.example"])
def test_lab_refuses_a_cross_site_origin(lab, origin):
    assert lab.get("/api/v1/runs", headers={"origin": origin}).status_code == 403


def test_lab_accepts_a_loopback_browser_origin(lab):
    assert lab.get("/api/v1/runs", headers={"origin": "http://127.0.0.1:18772"}).status_code not in (401, 403)


def test_lab_refusal_logs_no_request_values(lab, caplog):
    with caplog.at_level("DEBUG"):
        lab.get("/api/v1/runs", headers={"X-Forwarded-For": SECRET_MARKER, "host": f"{SECRET_MARKER}.example"})
    assert SECRET_MARKER not in "\n".join(record.getMessage() for record in caplog.records)


# --- OIDC fails closed ---------------------------------------------------------


@pytest.mark.parametrize("missing", ["JUVAL_OIDC_ISSUER", "JUVAL_OIDC_AUDIENCE"])
def test_incomplete_oidc_stops_startup(monkeypatch, missing):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", f"https://{SECRET_MARKER}.example")
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", SECRET_MARKER)
    monkeypatch.delenv(missing)
    message = startup_error()
    assert missing in message
    assert SECRET_MARKER not in message


@pytest.mark.parametrize("method,path", DATA_ROUTES)
def test_oidc_without_a_token_refuses_every_data_route(oidc, method, path):
    assert call(oidc, method, path).status_code == 401


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c", ""])
def test_oidc_with_an_invalid_token_refuses(oidc, token):
    response = oidc.get("/api/v1/runs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_oidc_is_never_bypassed_by_the_lab_shape(oidc):
    """A direct loopback request with no token is still refused under OIDC."""
    client = TestClient(app, raise_server_exceptions=False, **LOOPBACK)
    assert client.get("/api/v1/runs").status_code == 401


def test_oidc_cannot_be_constructed_without_a_verifier():
    with pytest.raises(ValueError):
        auth.AuthSettings(mode="oidc", verifier=None)
    with pytest.raises(ValueError):
        auth.AuthSettings(mode="disabled", verifier=auth.TokenVerifier(ISSUER, AUDIENCE, lambda token: None))
    with pytest.raises(ValueError):
        auth.AuthSettings(mode="anonymous")


def test_clearing_the_verifier_override_builds_one_from_the_environment(monkeypatch):
    """set_verifier(None) used to mean "anonymous"; now it means "use the env"."""

    class FailingJwks:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            raise ConnectionError("JWKS unreachable")

    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(auth.jwt, "PyJWKClient", FailingJwks)
    auth.set_verifier(None)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert app.state.juval_auth.verifier is not None
        assert client.get("/api/v1/runs").status_code == 401
        # An internal verifier failure (JWKS down) is a 401, never access.
        assert client.get("/api/v1/runs", headers=bearer("a.b.c")).status_code == 401


def test_a_failing_session_resolver_never_grants_access(oidc, monkeypatch):
    def broken(request):
        raise RuntimeError("session store unavailable")

    monkeypatch.setattr(auth, "_session_resolver", broken)
    assert oidc.get("/api/v1/runs").status_code == 500


def test_an_unavailable_membership_store_is_a_503_without_details(oidc, keypair, monkeypatch, caplog):  # noqa: F811
    from juval.interfaces.api import main

    class Unavailable:
        def organization_ids_for(self, issuer, subject):
            raise RuntimeError("SYNTHETIC-DRIVER-DETAIL host=db.internal")

    monkeypatch.setattr(main, "_execution_run_store", lambda: Unavailable())
    response = oidc.get("/api/v1/runs", headers=bearer(make_token(keypair, roles=("viewer",))))
    assert (response.status_code, response.json()) == (
        503, {"detail": "organization membership is temporarily unavailable"})
    assert "SYNTHETIC-DRIVER-DETAIL" not in caplog.text


def test_a_remote_execution_store_without_tls_stops_startup(monkeypatch, keypair):  # noqa: F811
    _, public_key = keypair
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_EXECUTION_STORE", "supabase")
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", "postgresql://db.example.com/postgres")
    auth.set_verifier(auth.TokenVerifier(issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: public_key))
    assert "without TLS" in startup_error()


def test_valid_token_still_works(oidc, keypair):  # noqa: F811
    token = make_token(keypair, roles=("viewer",))
    assert oidc.get("/api/v1/runs", headers=bearer(token)).status_code not in (401, 403)
    assert oidc.get("/api/v1/runs/x/download", headers=bearer(token)).status_code == 403


# --- the mode is fixed for the life of the instance -----------------------------


def test_lab_instance_ignores_a_later_switch_to_oidc(lab, monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    assert app.state.juval_auth.mode == "disabled"
    assert lab.get("/api/v1/runs").status_code not in (401, 403, 503)


def test_oidc_instance_ignores_a_later_switch_to_the_lab(oidc, monkeypatch):
    lab_env(monkeypatch)
    monkeypatch.setenv("JUVAL_OIDC_ROLES_CLAIM", "groups")
    client = TestClient(app, raise_server_exceptions=False, **LOOPBACK)
    assert client.get("/api/v1/runs").status_code == 401
    assert app.state.juval_auth.verifier.roles_claim == "roles"


def test_a_running_instance_cannot_be_rebound(lab):
    with pytest.raises(RuntimeError, match="already installed"):
        auth.install(app, auth.AuthSettings(mode="disabled"))
    assert app.state.juval_auth.mode == "disabled"


def test_settings_are_immutable(lab):
    with pytest.raises(Exception):
        app.state.juval_auth.mode = "oidc"


def test_two_instances_keep_their_own_settings(monkeypatch, keypair):  # noqa: F811
    """Each instance binds only itself, at startup and at shutdown (ADR-055)."""
    from fastapi import FastAPI

    from juval.interfaces.api.main import _lifespan

    _, public_key = keypair
    lab_env(monkeypatch)
    with TestClient(app, **LOOPBACK):
        lab_settings = app.state.juval_auth
        monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
        auth.set_verifier(auth.TokenVerifier(issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: public_key))
        other = FastAPI(lifespan=_lifespan)
        with TestClient(other):
            assert other.state.juval_auth.mode == "oidc"
            assert app.state.juval_auth is lab_settings
        assert getattr(other.state, "juval_auth", None) is None
        assert app.state.juval_auth is lab_settings  # the other shutdown left it bound
    assert getattr(app.state, "juval_auth", None) is None


def test_shutdown_unbinds_the_instance(monkeypatch):
    lab_env(monkeypatch)
    with TestClient(app, **LOOPBACK):
        pass
    assert getattr(app.state, "juval_auth", None) is None


# --- generated API documentation ----------------------------------------------


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_are_hidden_under_oidc(oidc, path):
    assert oidc.get(path).status_code == 404


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_are_hidden_before_startup(path):
    assert TestClient(app, **LOOPBACK).get(path).status_code == 404


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_are_served_to_the_loopback_lab_only(lab, path):
    assert lab.get(path).status_code == 200
    assert TestClient(app, **REMOTE).get(path).status_code == 404
