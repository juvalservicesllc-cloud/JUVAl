"""The synthetic IdP enforces what a real provider must (SEC-01F)."""

from __future__ import annotations

import base64
import hashlib
import sys
import urllib.parse
from pathlib import Path

import jwt
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from oidc_lab import LabUser, SyntheticIdP  # noqa: E402

VERIFIER = "v" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")


@pytest.fixture
def idp():
    provider = SyntheticIdP(client_id="c", client_secret="s", redirect_uri="http://localhost:1/cb",
                            post_logout_redirect_uri="http://localhost:2/",
                            users={"alice": LabUser("alice", "Alice", ["operator"])})
    yield provider
    provider._server.server_close()


def request(**overrides):
    return {"client_id": "c", "redirect_uri": "http://localhost:1/cb", "response_type": "code", "state": "st",
            "nonce": "n", "code_challenge": CHALLENGE, "code_challenge_method": "S256", **overrides}


def code_for(idp, **overrides):
    location = idp.issue_code(request(**overrides), "alice")
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(location).query))["code"]


def exchange(idp, code, **overrides):
    return idp.token({"grant_type": "authorization_code", "client_id": "c", "client_secret": "s", "code": code,
                      "redirect_uri": "http://localhost:1/cb", "code_verifier": VERIFIER, **overrides})


@pytest.mark.parametrize("change", [{"redirect_uri": "http://evil/cb"}, {"client_id": "x"},
                                    {"code_challenge_method": "plain"}, {"code_challenge": ""},
                                    {"state": ""}, {"response_type": "token"}])
def test_bad_authorization_requests_are_refused(idp, change):
    assert idp.authorize_error(request(**change))


def test_code_exchange_needs_pkce_secret_and_is_single_use(idp):
    assert exchange(idp, code_for(idp), code_verifier="w" * 64)[0] == 400
    assert exchange(idp, code_for(idp), client_secret="wrong")[0] == 401
    code = code_for(idp)
    status, tokens = exchange(idp, code)
    assert status == 200 and {"access_token", "id_token", "refresh_token"} <= set(tokens)
    claims = jwt.decode(tokens["id_token"], options={"verify_signature": False})
    assert claims["nonce"] == "n" and claims["aud"] == "c" and claims["iss"] == idp.issuer
    assert exchange(idp, code)[0] == 400                      # replay


def test_refresh_rotates_and_reflects_role_changes_and_deactivation(idp):
    _, tokens = exchange(idp, code_for(idp))
    idp.set_roles("alice", ["viewer"])
    refresh = {"grant_type": "refresh_token", "client_id": "c", "client_secret": "s"}
    status, renewed = idp.token({**refresh, "refresh_token": tokens["refresh_token"]})
    assert status == 200 and jwt.decode(renewed["access_token"], options={"verify_signature": False})["roles"] == ["viewer"]
    assert idp.token({**refresh, "refresh_token": tokens["refresh_token"]})[0] == 400   # rotated
    idp.disable("alice")
    assert idp.token({**refresh, "refresh_token": renewed["refresh_token"]})[0] == 400
    with pytest.raises(PermissionError):
        code_for(idp)


def test_the_provider_listens_on_loopback_only(idp):
    assert idp._server.server_address[0] == "127.0.0.1"
