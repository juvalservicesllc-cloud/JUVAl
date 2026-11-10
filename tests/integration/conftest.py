from __future__ import annotations

import pytest

from juval.interfaces.api import auth

from .api_lab import install_lab


@pytest.fixture
def auth_lab(request, monkeypatch):
    """Opt-in only: run this test against the confirmed loopback lab (ADR-055).

    A test that also asks for `enable_auth` asked for OIDC; the lab then binds
    nothing, whatever order pytest sets the two fixtures up in.
    """
    from juval.interfaces.api.main import app

    if "enable_auth" in request.fixturenames:
        yield
        return
    install_lab(app, monkeypatch)
    yield
    auth.uninstall(app)
