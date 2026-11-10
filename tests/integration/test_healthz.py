"""GET /healthz: the one public route, and nothing else becomes public (SEC-01E)."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import juval
from juval.interfaces.api import auth, bff
from juval.interfaces.api.main import app

from .test_api_auth import AUDIENCE, ISSUER, keypair  # noqa: F401 (fixture)


@pytest.fixture
def oidc(monkeypatch, keypair):  # noqa: F811
    _, public_key = keypair
    for name in ("JUVAL_SESSION_STORE", "JUVAL_OIDC_CLIENT_ID", "JUVAL_BFF_REDIRECT_URI", "JUVAL_EXECUTION_STORE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    auth.uninstall(app)
    bff.reset_for_tests()
    auth.set_verifier(auth.TokenVerifier(issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: public_key))
    with TestClient(app) as client:
        yield client
    auth.reset_for_tests()
    bff.reset_for_tests()


def test_liveness_needs_no_credential_and_says_nothing_else(oidc):
    response = oidc.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert juval.__version__ not in response.text
    assert not {"set-cookie", "www-authenticate"} & set(response.headers)


def test_liveness_ignores_whatever_the_caller_sends(oidc):
    noisy = oidc.get("/healthz", params={"verbose": "1", "db": "check"},
                     headers={"Authorization": "Bearer garbage", "Cookie": "juval_session=forged"})
    assert (noisy.status_code, noisy.json()) == (200, {"status": "ok"})


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_only_get_is_public(oidc, method):
    assert getattr(oidc, method)("/healthz").status_code == 405


def test_liveness_is_not_in_the_api_schema():
    assert "/healthz" not in app.openapi()["paths"]


def _depends_on(dependant, target) -> bool:
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def test_the_public_exception_does_not_extend_to_any_other_route():
    """Every API route outside the BFF's own login surface requires an authenticated principal."""
    public = sorted(
        route.path for route in app.routes
        if isinstance(route, APIRoute)
        and not route.path.startswith("/api/v1/auth/")
        and not _depends_on(route.dependant, auth.current_principal)
    )
    assert public == ["/healthz"]


def test_a_data_route_next_to_it_still_refuses_without_a_credential(oidc):
    assert oidc.get("/api/v1/runs").status_code == 401
    assert oidc.get("/healthz/../api/v1/runs").status_code in (401, 404)
