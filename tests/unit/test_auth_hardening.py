"""Hardening properties of `interfaces/api/auth.py` that were previously implicit.

Each of these was a library default or an absent header before this phase. They
are asserted here so a dependency bump or a refactor cannot change
token-verification behaviour without a failing test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from juval.interfaces.api import auth as auth_module

ISSUER = "https://idp.test.invalid"
AUDIENCE = "juval-test-client"


@pytest.fixture()
def key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture()
def verifier(key):
    return auth_module.TokenVerifier(
        issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: key.public_key()
    )


def _token(key, **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-1",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "roles": ["viewer"],
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


# --- clock skew --------------------------------------------------------


def test_leeway_is_explicit_and_small():
    assert auth_module._CLOCK_SKEW_LEEWAY_SECONDS == 60


def test_token_expired_within_the_leeway_is_accepted(verifier, key):
    just_expired = datetime.now(timezone.utc) - timedelta(seconds=10)
    principal = verifier.verify(_token(key, exp=int(just_expired.timestamp())))
    assert principal.subject == "user-1"


def test_token_expired_beyond_the_leeway_is_rejected(verifier, key):
    long_expired = datetime.now(timezone.utc) - timedelta(seconds=600)
    with pytest.raises(HTTPException) as exc:
        verifier.verify(_token(key, exp=int(long_expired.timestamp())))
    assert exc.value.status_code == 401


def test_token_issued_slightly_in_the_future_is_accepted(verifier, key):
    soon = datetime.now(timezone.utc) + timedelta(seconds=10)
    assert verifier.verify(_token(key, iat=int(soon.timestamp()))).subject == "user-1"


# --- JWKS cache --------------------------------------------------------


def test_jwks_cache_parameters_are_pinned():
    assert auth_module._JWKS_CACHE_LIFESPAN_SECONDS == 300
    assert auth_module._JWKS_MAX_CACHED_KEYS == 16
    assert auth_module._JWKS_HTTP_TIMEOUT_SECONDS == 10


def test_build_verifier_configures_the_jwks_client_explicitly(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, uri, **kwargs):
            captured["uri"] = uri
            captured.update(kwargs)

        def get_signing_key_from_jwt(self, token):  # pragma: no cover - not called
            raise AssertionError

    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    monkeypatch.setenv("JUVAL_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("JUVAL_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setattr(jwt, "PyJWKClient", FakeClient)
    auth_module.reset_for_tests()

    assert auth_module.build_verifier() is not None
    assert captured["uri"] == f"{ISSUER}/.well-known/jwks.json"
    assert captured["cache_jwk_set"] is True
    assert captured["lifespan"] == auth_module._JWKS_CACHE_LIFESPAN_SECONDS
    assert captured["max_cached_keys"] == auth_module._JWKS_MAX_CACHED_KEYS
    assert captured["timeout"] == auth_module._JWKS_HTTP_TIMEOUT_SECONDS
    auth_module.reset_for_tests()


def test_key_rotation_uses_the_resolver_for_every_verification(key):
    """A rotated key must be picked up by resolving per token, not once."""
    calls = {"n": 0}
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = [other.public_key(), key.public_key()]

    def rotating(token):
        calls["n"] += 1
        return keys[min(calls["n"] - 1, len(keys) - 1)]

    verifier = auth_module.TokenVerifier(
        issuer=ISSUER, audience=AUDIENCE, key_resolver=rotating
    )
    token = _token(key)
    with pytest.raises(HTTPException):
        verifier.verify(token)          # stale key -> rejected
    assert verifier.verify(token).subject == "user-1"  # rotated key -> accepted
    assert calls["n"] == 2


# --- RFC 6750 challenge ------------------------------------------------


def test_invalid_token_carries_a_www_authenticate_challenge(verifier, key):
    with pytest.raises(HTTPException) as exc:
        verifier.verify(_token(key, iss="https://evil.test.invalid"))
    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'


def test_challenge_does_not_disclose_why_the_token_failed(verifier, key):
    with pytest.raises(HTTPException) as exc:
        verifier.verify(_token(key, aud="another-client"))
    assert exc.value.detail == "invalid or expired token"
    assert "aud" not in exc.value.headers["WWW-Authenticate"]


# --- algorithm pinning is still absolute -------------------------------


def test_unsigned_token_is_rejected(verifier):
    unsigned = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": "u"}, key=None, algorithm="none")
    with pytest.raises(HTTPException):
        verifier.verify(unsigned)


def test_only_rs256_is_accepted():
    assert auth_module._ALLOWED_ALGORITHMS == ["RS256"]
