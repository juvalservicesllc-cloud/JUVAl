"""Loopback lab helpers for API tests (ADR-055).

The API has no default authentication mode. A test that exercises routes
without identity opts in explicitly with the `auth_lab` fixture
(`tests/integration/conftest.py`) and builds its client with `LOOPBACK`, so the
requests look like what the lab accepts: a direct connection from 127.0.0.1 to
127.0.0.1 with a loopback Host. Nothing here is enabled globally.
"""

from __future__ import annotations

from juval.interfaces.api import auth

#: TestClient keyword arguments for a direct loopback request.
LOOPBACK = {"base_url": "http://127.0.0.1", "client": ("127.0.0.1", 50000)}


def install_lab(app, monkeypatch) -> None:
    """Bind `app` to the confirmed loopback lab, as a lab startup would."""
    monkeypatch.setenv("JUVAL_AUTH_MODE", "disabled")
    monkeypatch.setenv(auth.LAB_CONFIRM_ENV, auth.LAB_CONFIRM_VALUE)
    auth.install(app, auth.resolve_settings())
