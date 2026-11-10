"""docs/architecture/BFF_FRONTEND_CONTRACT.md matches the backend (SEC-01F).

The contract is what Codex builds frontend-next against, so drift is a bug:
every error `detail` the API can return to a browser must be documented, and
the documented precedence of refusals must hold.
"""

from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from juval.interfaces.api import bff
from juval.interfaces.api.main import app

from .test_api_bff import _login, configured, rsa_key  # noqa: F401 (fixtures)
from .test_resource_isolation import api, as_user, db  # noqa: F401 (fixtures)
from .test_api_auth import keypair  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (ROOT / "docs" / "architecture" / "BFF_FRONTEND_CONTRACT.md").read_text(encoding="utf-8")
API = ROOT / "src" / "juval" / "interfaces" / "api"

#: Not reachable by the browser client the contract describes: bearer-header
#: parsing, the loopback lab, and per-field input validation (422/413, shown
#: verbatim by the existing UI).
NOT_BROWSER_FACING = {"malformed Authorization header", "unauthenticated lab mode accepts direct loopback requests only"}


def _emitted_details() -> set[str]:
    details = set()
    for name in ("main.py", "auth.py", "bff.py"):
        source = (API / name).read_text(encoding="utf-8")
        for status, detail in re.findall(r'status_code=(\d{3}),\s*detail="([^"{]+)"', source):
            if status not in ("413", "422"):
                details.add(detail)
        details.update(re.findall(r'(?<!status_code=\d{3}, )detail="([^"{]+)"', source))
        details.update(re.findall(r'run_in_scope\("([^"]+)"\)', source))
        details.update(re.findall(r'not_found="([^"]+)"', source))
    validation = set()
    for name in ("main.py",):
        source = (API / name).read_text(encoding="utf-8")
        validation.update(re.findall(r'status_code=(?:413|422),\s*detail="([^"{]+)"', source))
        validation.update(re.findall(r'status_code=(?:413|422),\s*\n\s*detail="([^"{]+)"', source))
    return details - validation - NOT_BROWSER_FACING


def test_every_error_detail_the_browser_can_receive_is_in_the_contract():
    details = _emitted_details()
    assert len(details) >= 20                       # the scan itself still finds the routes
    text = " ".join(CONTRACT.split())               # Markdown line wrapping is not a difference
    missing = sorted(d for d in details if d not in text)
    assert missing == []


def test_a_viewer_without_organization_is_refused_by_rbac_first(api, as_user):  # noqa: F811
    response = api.post("/api/v1/runs", headers=as_user("user-none", "viewer"),
                        files={"file": ("a.csv", b"x", "text/csv")})
    assert (response.status_code, response.json()) == (403, {"detail": "insufficient permissions"})


def test_csrf_is_checked_before_the_organization(configured, rsa_key, monkeypatch):  # noqa: F811
    with TestClient(app) as client:
        _login(client, rsa_key, monkeypatch, roles=("operator",))
        response = client.post("/api/v1/runs", files={"file": ("a.csv", b"x", "text/csv")})
        assert (response.status_code, response.json()) == (403, {"detail": "csrf token missing or invalid"})


def test_session_and_logout_shapes_are_as_documented(configured, rsa_key, monkeypatch):  # noqa: F811
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/session").json() == {"authenticated": False}
        view = _login(client, rsa_key, monkeypatch, roles=("operator",))
        assert set(view) == {"authenticated", "subject", "roles", "permissions", "expires_at", "csrf_token"}
        assert view["permissions"] == ["runs:create", "runs:export", "runs:read"]
        out = client.post("/api/v1/auth/logout", headers={bff.CSRF_HEADER: view["csrf_token"]}).json()
        assert set(out) == {"logged_out", "end_session_url"} and out["logged_out"] is True


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_the_full_local_integration_environment_passes_its_security_smoke(monkeypatch):
    """Real backend process + disposable PostgreSQL (RLS, sessions) + synthetic OIDC."""
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import integration_lab

    try:
        integration_lab._postgres_binaries()
    except SystemExit:
        pytest.skip("PostgreSQL server binaries not available (set JUVAL_POSTGRES_BIN)")
    assert integration_lab.main(["--check", "--api-port", str(_free_port()), "--idp-port", str(_free_port()),
                                 "--web-port", str(_free_port())]) == 0
