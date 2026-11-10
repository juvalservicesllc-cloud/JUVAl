"""OIDC readiness against a synthetic loopback IdP (SEC-01E).

The IdP is an in-process HTTP server on 127.0.0.1 serving a discovery
document and a JWKS built from locally generated keys. Tokens are signed
locally. This exercises the real PyJWKClient path the API uses
(`auth.jwks_verifier`) -- key rotation, an unreachable JWKS -- and the
`tools/verify_oidc.py` checks, with no real issuer and no credential.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from juval.interfaces.api import auth

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import verify_oidc  # noqa: E402

AUDIENCE = "juval-client"


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(key, kid):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    return {**jwk, "kid": kid, "alg": "RS256", "use": "sig"}


class _Idp:
    """Mutable discovery + JWKS; `published` is what the JWKS endpoint returns now."""

    def __init__(self):
        self.published = {}
        self.jwks_requests = 0
        self.discovery_jwks_uri = None
        self.claimed_issuer = None
        self.down = False
        idp = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if idp.down:
                    self.send_error(503)
                    return
                if self.path == "/.well-known/openid-configuration":
                    body = {"issuer": idp.claimed_issuer or idp.issuer, "jwks_uri": idp.discovery_jwks_uri or f"{idp.issuer}/.well-known/jwks.json"}
                elif self.path == "/.well-known/jwks.json":
                    idp.jwks_requests += 1
                    body = {"keys": [_jwk(key, kid) for kid, key in idp.published.items()]}
                else:
                    self.send_error(404)
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.issuer = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.jwks_uri = f"{self.issuer}/.well-known/jwks.json"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def token(self, key, kid, **overrides):
        now = datetime.now(timezone.utc)
        claims = {"iss": self.issuer, "aud": AUDIENCE, "sub": "fa-user-1", "iat": int(now.timestamp()),
                  "exp": int((now + timedelta(minutes=5)).timestamp()), "roles": ["viewer"], **overrides}
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture()
def idp():
    server = _Idp()
    yield server
    server.server.shutdown()
    server.server.server_close()


# --- the API's verifier against a live (loopback) JWKS ----------------------


@pytest.fixture()
def clock(monkeypatch):
    """Monotonic time under test control (PyJWT's JWKS cache and cooldown use it)."""
    now = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    return now


def test_a_rotated_in_key_is_accepted_after_the_bounded_cooldown(idp, clock):
    old, new = _key(), _key()
    idp.published = {"k1": old}
    verifier = auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri)
    assert verifier.verify(idp.token(old, "k1")).subject == "fa-user-1"
    idp.published = {"k1": old, "k2": new}
    # Within the pinned cooldown an unknown kid does not trigger a refetch:
    # fail closed (401) for at most _JWKS_REFRESH_COOLDOWN_SECONDS.
    with pytest.raises(HTTPException):
        verifier.verify(idp.token(new, "k2"))
    clock[0] += auth._JWKS_REFRESH_COOLDOWN_SECONDS + 1
    assert verifier.verify(idp.token(new, "k2")).subject == "fa-user-1"


def test_a_retired_key_stops_verifying_within_the_cache_lifespan(idp, clock):
    old, new = _key(), _key()
    idp.published = {"k1": old, "k2": new}
    verifier = auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri)
    old_token = idp.token(old, "k1")
    assert verifier.verify(old_token).subject == "fa-user-1"
    idp.published = {"k2": new}                     # the IdP retires (revokes) k1
    clock[0] += auth._JWKS_CACHE_LIFESPAN_SECONDS + 1
    with pytest.raises(HTTPException):
        verifier.verify(old_token)
    assert verifier.verify(idp.token(new, "k2")).issuer == idp.issuer


def test_the_key_set_cache_expires_after_its_lifespan(idp, clock):
    key = _key()
    idp.published = {"k1": key}
    verifier = auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri)
    token = idp.token(key, "k1")
    verifier.verify(token)
    verifier.verify(token)
    assert idp.jwks_requests == 1                       # served from the set cache
    clock[0] += auth._JWKS_CACHE_LIFESPAN_SECONDS - 1
    verifier.verify(token)
    assert idp.jwks_requests == 1
    clock[0] += 2
    verifier.verify(token)
    assert idp.jwks_requests == 2                       # re-fetched once the lifespan passed


def test_a_jwks_outage_fails_closed_after_the_cache_and_recovers_without_a_restart(idp, clock):
    key = _key()
    idp.published = {"k1": key}
    verifier = auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri)
    token = idp.token(key, "k1")
    verifier.verify(token)
    idp.down = True
    verifier.verify(token)                              # cached keys still serve during the lifespan
    clock[0] += auth._JWKS_CACHE_LIFESPAN_SECONDS + 1
    for _ in range(3):                                  # expired cache + outage: no stale keys, 401
        with pytest.raises(HTTPException) as refused:
            verifier.verify(token)
        assert refused.value.status_code == 401
    idp.down = False
    assert verifier.verify(token).subject == "fa-user-1"   # next request after recovery


def test_an_unknown_kid_is_rejected_and_the_jwks_fetches_are_bounded(idp):
    idp.published = {"k1": _key()}
    verifier = auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri)
    stranger = _key()
    for _ in range(5):
        with pytest.raises(HTTPException) as refused:
            verifier.verify(idp.token(stranger, "attacker-kid"))
        assert refused.value.status_code == 401
    assert idp.jwks_requests <= 6   # one refresh per miss at most; a key is never invented


def test_an_unreachable_jwks_is_a_401_never_access(idp):
    key = _key()
    idp.published = {"k1": key}
    token = idp.token(key, "k1")
    verifier = auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri)
    idp.server.shutdown()
    idp.server.server_close()
    with pytest.raises(HTTPException) as refused:
        verifier.verify(token)
    assert refused.value.status_code == 401


@pytest.mark.parametrize("change", [
    {"aud": "another-client"},
    {"iss": "https://other-issuer.example"},
    {"exp": 1},
])
def test_claims_the_backend_does_not_pin_are_refused(idp, change):
    key = _key()
    idp.published = {"k1": key}
    with pytest.raises(HTTPException):
        auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri).verify(idp.token(key, "k1", **change))


def test_an_hs256_token_using_the_public_key_as_secret_is_refused(idp):
    key = _key()
    idp.published = {"k1": key}
    forged = jwt.encode({"iss": idp.issuer, "aud": AUDIENCE, "sub": "x", "iat": 1, "exp": 4102444800},
                        "public-key-material-used-as-an-hmac-secret", algorithm="HS256", headers={"kid": "k1"})
    with pytest.raises(HTTPException):
        auth.jwks_verifier(idp.issuer, AUDIENCE, idp.jwks_uri).verify(forged)


# --- tools/verify_oidc.py ---------------------------------------------------


def _run(capsys, *argv):
    code = verify_oidc.main(list(argv))
    return code, capsys.readouterr().out


def test_tool_verifies_a_token_with_the_api_verifier_and_prints_the_membership_identity(idp, capsys, monkeypatch):
    key = _key()
    idp.published = {"k1": key}
    token = idp.token(key, "k1")
    monkeypatch.setenv("SYNTHETIC_TEST_TOKEN", token)
    code, out = _run(capsys, "--issuer", idp.issuer, "--audience", AUDIENCE, "--token-env", "SYNTHETIC_TEST_TOKEN")
    assert code == 0, out
    assert f"--issuer '{idp.issuer}' --subject 'fa-user-1'" in out
    assert "runs:read" in out
    assert token not in out and token.split(".")[2] not in out


def test_tool_fails_a_token_for_another_audience(idp, capsys, monkeypatch):
    key = _key()
    idp.published = {"k1": key}
    monkeypatch.setenv("SYNTHETIC_TEST_TOKEN", idp.token(key, "k1", aud="another-client"))
    code, out = _run(capsys, "--issuer", idp.issuer, "--audience", AUDIENCE, "--token-env", "SYNTHETIC_TEST_TOKEN")
    assert code == 1 and "FAIL" in out and "token verifies" in out


def test_tool_fails_a_token_without_juval_roles(idp, capsys, monkeypatch):
    key = _key()
    idp.published = {"k1": key}
    monkeypatch.setenv("SYNTHETIC_TEST_TOKEN", idp.token(key, "k1", roles=["fusionauth-only"]))
    code, out = _run(capsys, "--issuer", idp.issuer, "--audience", AUDIENCE, "--token-env", "SYNTHETIC_TEST_TOKEN")
    assert code == 1 and "roles claim maps to JUVAl permissions" in out


def test_tool_fails_when_the_backend_would_fetch_keys_from_another_uri(idp, capsys):
    idp.published = {"k1": _key()}
    idp.discovery_jwks_uri = f"{idp.issuer}/oauth2/jwks"
    code, out = _run(capsys, "--issuer", idp.issuer)
    assert code == 1
    assert "FAIL" in out and "backend JWKS URI matches discovery" in out


def test_tool_fails_on_an_issuer_mismatch_and_a_missing_token_variable(idp, capsys, monkeypatch):
    idp.published = {"k1": _key()}
    idp.claimed_issuer = "https://another-issuer.example"
    monkeypatch.delenv("SYNTHETIC_TEST_TOKEN", raising=False)
    code, out = _run(capsys, "--issuer", idp.issuer, "--audience", AUDIENCE, "--token-env", "SYNTHETIC_TEST_TOKEN")
    assert code == 1
    assert [line for line in out.splitlines() if line.startswith("FAIL") and "issuer matches" in line]
    assert "SYNTHETIC_TEST_TOKEN is not set" in out


def test_tool_requires_an_audience_to_check_a_token(capsys):
    with pytest.raises(SystemExit):
        verify_oidc.main(["--issuer", "https://idp.example", "--token-env", "X"])
