"""Authentication/authorization tests for the Juval API (RF-03 backend, RF-04).

These are the negative security tests Amazon finding RF-04 requires as
evidence: it is not enough that an authorized caller succeeds, it must be
proven that an unauthorized one is refused *server-side*, including a caller
that bypasses the frontend entirely and calls the API directly.

Signatures are verified against a real RSA key pair generated per test run, so
these exercise genuine cryptographic verification -- not a stubbed-out
validator. No secret, password or real token appears anywhere in this file.
"""

from __future__ import annotations

import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from juval.interfaces.api import auth
from juval.interfaces.api.main import app

ISSUER = "https://juval-test.example.com/oauth2/default"
AUDIENCE = "juval-api"

# Endpoint -> (method, permission it requires)
PROTECTED_READ_ENDPOINTS = [
    "/api/v1/runs",
    "/api/v1/runs/some-id",
    "/api/v1/runs/some-id/records",
]


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def enable_auth(keypair):
    """Install a verifier bound to the test key pair, then restore the default."""
    _, public_key = keypair

    def resolve(token: str):
        return public_key

    auth.set_verifier(
        auth.TokenVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            key_resolver=resolve,
            roles_claim="roles",
        )
    )
    yield
    auth.reset_for_tests()


def make_token(
    keypair,
    *,
    roles=("operator",),
    issuer=ISSUER,
    audience=AUDIENCE,
    subject="00u-test-subject",
    expires_in_seconds=300,
    algorithm="RS256",
    omit_claims=(),
):
    private_key, _ = keypair
    now = dt.datetime.now(tz=dt.timezone.utc)
    claims = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=expires_in_seconds)).timestamp()),
        "roles": list(roles),
    }
    for claim in omit_claims:
        claims.pop(claim, None)

    if algorithm == "none":
        return jwt.encode(claims, key=None, algorithm=None)

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm=algorithm)


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


client = TestClient(app, raise_server_exceptions=False)


# --- auth disabled (default) -----------------------------------------


def test_auth_disabled_by_default_allows_unauthenticated_read():
    """Existing local-development behavior is preserved when auth is off."""
    auth.reset_for_tests()
    response = client.get("/api/v1/runs")
    # 500 = no execution store configured; the point is it is NOT 401/403.
    assert response.status_code not in (401, 403)


# --- authentication (401) --------------------------------------------


@pytest.mark.parametrize("path", PROTECTED_READ_ENDPOINTS)
def test_missing_token_is_rejected(enable_auth, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", PROTECTED_READ_ENDPOINTS)
def test_direct_api_call_bypassing_frontend_is_rejected(enable_auth, path):
    """A caller ignoring the PWA entirely still cannot read anything."""
    response = client.get(path, headers={"Origin": "https://attacker.example"})
    assert response.status_code == 401


def test_malformed_authorization_header_is_rejected(enable_auth, keypair):
    token = make_token(keypair)
    for header in ({"Authorization": token}, {"Authorization": f"Basic {token}"}, {"Authorization": "Bearer "}):
        assert client.get("/api/v1/runs", headers=header).status_code == 401


def test_garbage_token_is_rejected(enable_auth):
    assert client.get("/api/v1/runs", headers=bearer("not.a.jwt")).status_code == 401


def test_expired_token_is_rejected(enable_auth, keypair):
    token = make_token(keypair, expires_in_seconds=-60)
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 401


def test_wrong_issuer_is_rejected(enable_auth, keypair):
    token = make_token(keypair, issuer="https://evil.example.com")
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 401


def test_wrong_audience_is_rejected(enable_auth, keypair):
    token = make_token(keypair, audience="some-other-api")
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 401


def test_token_signed_by_a_different_key_is_rejected(enable_auth):
    """A validly-shaped token signed by an attacker's key must not be accepted."""
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = make_token((attacker_key, attacker_key.public_key()))
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 401


def test_unsigned_alg_none_token_is_rejected(enable_auth, keypair):
    """Classic JWT forgery: alg=none must never be honored."""
    token = make_token(keypair, algorithm="none")
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 401


@pytest.mark.parametrize("claim", ["sub", "exp", "iss", "aud", "iat"])
def test_token_missing_a_required_claim_is_rejected(enable_auth, keypair, claim):
    token = make_token(keypair, omit_claims=(claim,))
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 401


# --- authorization (403) ---------------------------------------------


def test_valid_token_with_no_roles_claim_gets_no_permissions(enable_auth, keypair):
    token = make_token(keypair, roles=())
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 403


def test_valid_token_with_unknown_role_gets_no_permissions(enable_auth, keypair):
    """An unrecognized role grants nothing -- it never falls back to full access."""
    token = make_token(keypair, roles=("some-unmapped-okta-group",))
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code == 403


def test_viewer_cannot_create_a_run(enable_auth, keypair):
    """Least privilege: read access does not imply the right to start work."""
    token = make_token(keypair, roles=("viewer",))
    response = client.post(
        "/api/v1/runs",
        headers=bearer(token),
        files={"file": ("x.xlsx", b"not-a-real-workbook", "application/vnd.ms-excel")},
        data={"thresholds": "{}", "fees": "{}"},
    )
    assert response.status_code == 403


def test_viewer_cannot_download_an_export(enable_auth, keypair):
    token = make_token(keypair, roles=("viewer",))
    response = client.get("/api/v1/runs/some-id/download", headers=bearer(token))
    assert response.status_code == 403


def test_viewer_may_read(enable_auth, keypair):
    token = make_token(keypair, roles=("viewer",))
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code not in (401, 403)


def test_operator_may_read_and_export(enable_auth, keypair):
    token = make_token(keypair, roles=("operator",))
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code not in (401, 403)
    # 404 (unknown id) proves authorization passed and the handler ran.
    assert client.get("/api/v1/runs/some-id/download", headers=bearer(token)).status_code == 404


def test_admin_has_every_permission(enable_auth, keypair):
    token = make_token(keypair, roles=("admin",))
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code not in (401, 403)
    assert client.get("/api/v1/runs/some-id/download", headers=bearer(token)).status_code == 404


def test_roles_claim_accepts_space_separated_string(enable_auth, keypair):
    """Some IdPs emit roles as a string rather than an array."""
    private_key, _ = keypair
    now = dt.datetime.now(tz=dt.timezone.utc)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token = jwt.encode(
        {
            "sub": "00u-test-subject",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + dt.timedelta(seconds=300)).timestamp()),
            "roles": "viewer operator",
        },
        pem,
        algorithm="RS256",
    )
    assert client.get("/api/v1/runs", headers=bearer(token)).status_code not in (401, 403)


# --- configuration fail-closed ---------------------------------------


def test_oidc_mode_without_issuer_fails_fast(monkeypatch):
    """Misconfiguration must crash, never silently serve unauthenticated."""
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.delenv("JUVAL_OIDC_ISSUER", raising=False)
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", AUDIENCE)
    auth.reset_for_tests()
    with pytest.raises(RuntimeError, match="JUVAL_OIDC_ISSUER"):
        auth.build_verifier()
    auth.reset_for_tests()


def test_oidc_mode_without_audience_fails_fast(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    monkeypatch.delenv("JUVAL_OIDC_AUDIENCE", raising=False)
    auth.reset_for_tests()
    with pytest.raises(RuntimeError, match="JUVAL_OIDC_AUDIENCE"):
        auth.build_verifier()
    auth.reset_for_tests()


def test_unrecognized_auth_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("JUVAL_AUTH_MODE", "off")
    with pytest.raises(RuntimeError, match="JUVAL_AUTH_MODE"):
        auth.auth_mode()


def test_permissions_are_least_privilege():
    """The role table itself must not silently grant more than intended."""
    assert auth.ROLE_PERMISSIONS["viewer"] == frozenset({auth.RUNS_READ})
    assert auth.RUNS_CREATE not in auth.ROLE_PERMISSIONS["viewer"]
    assert auth.RUNS_EXPORT not in auth.ROLE_PERMISSIONS["viewer"]
    assert auth.ROLE_PERMISSIONS["admin"] == auth.ALL_PERMISSIONS
