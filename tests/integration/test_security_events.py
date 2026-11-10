"""Structured security events (SEC-01E): emitted where it matters, never sensitive."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from juval.interfaces.api import auth, bff, main, security_events
from juval.interfaces.api.main import app

from .test_api_auth import AUDIENCE, ISSUER, bearer, keypair, make_token  # noqa: F401 (fixture)


def events(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "juval.security"]


@pytest.fixture
def oidc(monkeypatch, keypair):  # noqa: F811
    _, public_key = keypair
    for name in ("JUVAL_SESSION_STORE", "JUVAL_OIDC_CLIENT_ID", "JUVAL_BFF_REDIRECT_URI", "JUVAL_EXECUTION_STORE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JUVAL_AUTH_MODE", "oidc")
    auth.uninstall(app)
    bff.reset_for_tests()
    auth.set_verifier(auth.TokenVerifier(issuer=ISSUER, audience=AUDIENCE, key_resolver=lambda token: public_key))
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    auth.reset_for_tests()
    bff.reset_for_tests()


def test_one_json_object_per_line_with_a_closed_vocabulary(caplog):
    with caplog.at_level(logging.INFO, logger="juval.security"):
        security_events.emit("access.denied", kind="rbac", permission="runs:create")
    assert events(caplog) == [{"event": "access.denied", "kind": "rbac", "permission": "runs:create"}]
    with pytest.raises(ValueError):
        security_events.emit("something.else")
    with pytest.raises(ValueError):
        security_events.emit("access.denied", subject="fa-user-1")      # raw subjects are not a field


def test_the_subject_fingerprint_is_stable_and_not_the_subject():
    fp = security_events.subject_fingerprint("fa-user-1")
    assert fp == security_events.subject_fingerprint("fa-user-1") and len(fp) == 12
    assert "fa-user-1" not in fp and fp != security_events.subject_fingerprint("fa-user-2")


def test_rejected_tokens_and_rbac_denials_are_events_without_identifiers(oidc, keypair, caplog):  # noqa: F811
    token = make_token(keypair, subject="fa-user-secret-sub", roles=("viewer",))
    with caplog.at_level(logging.INFO):
        oidc.get("/api/v1/runs", headers=bearer("a.b.c"))
        oidc.post("/api/v1/runs", headers=bearer(token), files={"file": ("a.csv", b"x", "text/csv")})
    seen = events(caplog)
    assert {"event": "auth.token_rejected", "reason": "DecodeError"} in seen
    denied = [e for e in seen if e["event"] == "access.denied"]
    assert denied == [{"event": "access.denied", "kind": "rbac", "permission": "runs:create",
                       "subject_fp": security_events.subject_fingerprint("fa-user-secret-sub")}]
    assert "fa-user-secret-sub" not in caplog.text and token not in caplog.text


def test_tenant_denial_and_membership_outage_are_events(oidc, keypair, monkeypatch, caplog):  # noqa: F811
    token = bearer(make_token(keypair, subject="fa-user-x", roles=("viewer",)))

    class NoMembership:
        def organization_ids_for(self, issuer, subject):
            return []

    class Down:
        def organization_ids_for(self, issuer, subject):
            raise RuntimeError("SYNTHETIC-DRIVER-DETAIL")

    with caplog.at_level(logging.INFO):
        monkeypatch.setattr(main, "_execution_run_store", lambda: NoMembership())
        assert oidc.get("/api/v1/runs", headers=token).status_code == 403
        monkeypatch.setattr(main, "_execution_run_store", lambda: Down())
        assert oidc.get("/api/v1/runs", headers=token).status_code == 503
    kinds = [(e["event"], e.get("kind"), e.get("reason")) for e in events(caplog)]
    assert ("access.denied", "tenant", "no_membership") in kinds
    assert ("membership.store_unavailable", None, None) in kinds
    assert "SYNTHETIC-DRIVER-DETAIL" not in caplog.text and "fa-user-x" not in caplog.text


def test_a_failed_startup_names_only_its_stage(monkeypatch, caplog):
    monkeypatch.delenv("JUVAL_AUTH_MODE", raising=False)
    auth.uninstall(app)
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        with TestClient(app):
            pass  # pragma: no cover
    assert {"event": "startup.failed", "stage": "authentication"} in events(caplog)
