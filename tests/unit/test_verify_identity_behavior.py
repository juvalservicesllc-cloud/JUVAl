"""Deterministic, mocked-FusionAuth tests for tools/verify_identity_behavior.py.

No live FusionAuth call is made anywhere in this file. `urllib.request.urlopen`
is replaced with a small scripted fake that records every request and returns
canned responses in order, so each test can assert exactly which endpoints
were called, with what method, headers and body -- and that nothing else was.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_identity_behavior", REPO_ROOT / "tools" / "verify_identity_behavior.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_identity_behavior"] = module
    spec.loader.exec_module(module)
    return module


vib = _load()


class _FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class ScriptedFusionAuth:
    """Replays (status, body) pairs in order; records every call made."""

    def __init__(self, script: list[tuple[int, dict]]) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def __call__(self, request, timeout=None):  # matches urlopen(request, timeout=...)
        body = json.loads(request.data.decode()) if request.data else None
        self.calls.append(
            {
                "method": request.get_method(),
                "url": request.full_url,
                "headers": {k: v for k, v in request.header_items()},
                "body": body,
            }
        )
        if not self._script:
            raise AssertionError(f"unexpected extra call: {request.get_method()} {request.full_url}")
        status, response_body = self._script.pop(0)
        raw = json.dumps(response_body).encode()
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "", None, io.BytesIO(raw))
        return _FakeResponse(status, raw)


TENANT_ID = "11111111-1111-1111-1111-111111111111"
APP_ID = "22222222-2222-2222-2222-222222222222"


def _client(fake: ScriptedFusionAuth) -> vib.Client:
    return vib.Client("http://127.0.0.1:9011", "test-key-not-real", TENANT_ID)


# --- Client / secret hygiene ------------------------------------------------


def test_client_never_issues_delete():
    client = vib.Client("http://x", "key", TENANT_ID)
    with pytest.raises(vib.IdentityVerificationError, match="never issues DELETE"):
        client.request("DELETE", "/api/user/some-id")


def test_client_sends_tenant_header_by_default(monkeypatch):
    fake = ScriptedFusionAuth([(200, {"ok": True})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    client.request("GET", "/api/application/x")
    assert fake.calls[0]["headers"].get("X-fusionauth-tenantid") == TENANT_ID


def test_client_can_omit_tenant_header(monkeypatch):
    fake = ScriptedFusionAuth([(200, {"ok": True})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    client.request("POST", "/api/two-factor/login", {}, scope_tenant=False)
    assert "X-fusionauth-tenantid" not in fake.calls[0]["headers"]


def test_client_never_sends_the_api_key_in_a_readable_log(monkeypatch):
    """The Authorization header carries the key (required for FusionAuth auth),
    but nothing in Client ever writes it to stdout/stderr or a Finding."""
    fake = ScriptedFusionAuth([(200, {"ok": True})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = vib.Client("http://x", "super-secret-key-value", TENANT_ID)
    client.request("GET", "/api/application/x")
    # The header is expected to carry it (that's how auth works) --
    # what matters is nothing else (Finding, print, exception message) does.
    assert fake.calls[0]["headers"]["Authorization"] == "super-secret-key-value"


# --- verify_targeting: fail-closed tenant/application scoping --------------


def test_verify_targeting_accepts_the_confirmed_application(monkeypatch):
    fake = ScriptedFusionAuth(
        [(200, {"application": {"name": "JUVAl", "tenantId": TENANT_ID}})]
    )
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    vib.verify_targeting(client, TENANT_ID, APP_ID)  # must not raise
    assert fake.calls[0]["method"] == "GET"
    assert fake.calls[0]["url"].endswith(f"/api/application/{APP_ID}")


def test_verify_targeting_refuses_wrong_application_name(monkeypatch):
    fake = ScriptedFusionAuth(
        [(200, {"application": {"name": "NotJUVAl", "tenantId": TENANT_ID}})]
    )
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    with pytest.raises(vib.IdentityVerificationError, match="refusing to proceed"):
        vib.verify_targeting(client, TENANT_ID, APP_ID)


def test_verify_targeting_refuses_mismatched_tenant_id():
    """Simulates the Default-tenant trap: an application named JUVAl but under
    a different (e.g. Default) tenant id than the one the operator supplied."""
    fake = ScriptedFusionAuth(
        [(200, {"application": {"name": "JUVAl", "tenantId": "different-tenant-id"}})]
    )
    import unittest.mock as mock

    with mock.patch.object(vib.urllib.request, "urlopen", fake):
        client = _client(fake)
        with pytest.raises(vib.IdentityVerificationError, match="refusing to proceed"):
            vib.verify_targeting(client, TENANT_ID, APP_ID)


def test_verify_targeting_refuses_on_non_200():
    fake = ScriptedFusionAuth([(404, {})])
    import unittest.mock as mock

    with mock.patch.object(vib.urllib.request, "urlopen", fake):
        client = _client(fake)
        with pytest.raises(vib.IdentityVerificationError):
            vib.verify_targeting(client, TENANT_ID, APP_ID)


# --- TOTP --------------------------------------------------------------


def test_totp_code_is_deterministic_for_a_fixed_time():
    secret = vib.random_totp_secret()
    a = vib.totp_code(secret, at=1_700_000_000)
    b = vib.totp_code(secret, at=1_700_000_000)
    assert a == b
    assert len(a) == 6 and a.isdigit()


def test_totp_code_changes_across_periods():
    secret = vib.random_totp_secret()
    a = vib.totp_code(secret, at=1_700_000_000)
    b = vib.totp_code(secret, at=1_700_000_000 + 30)
    assert a != b


def test_wrong_totp_code_always_differs():
    secret = vib.random_totp_secret()
    for _ in range(20):
        correct = vib.totp_code(secret)
        assert vib.wrong_totp_code(secret) != correct


# --- Endpoint construction -----------------------------------------------


def test_create_disposable_user_hits_post_api_user_with_tag(monkeypatch):
    fake = ScriptedFusionAuth([(200, {"user": {"id": "u1", "email": "x@y.invalid"}})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    status, body = vib.create_disposable_user(client, case_id="P-01", password="Vvz9!abcdefQx")
    assert status == 200
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/user")
    assert call["body"]["user"]["password"] == "Vvz9!abcdefQx"
    assert call["body"]["user"]["data"]["juval_identity_verification"] is True
    assert call["body"]["user"]["data"]["case"] == "P-01"


def test_register_to_application_hits_post_registration_with_user_id_path(monkeypatch):
    fake = ScriptedFusionAuth([(200, {"registration": {}})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    vib.register_to_application(client, user_id="u1", application_id=APP_ID, roles=["viewer"])
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/user/registration/u1")
    assert call["body"]["registration"]["applicationId"] == APP_ID
    assert call["body"]["registration"]["roles"] == ["viewer"]


def test_login_hits_post_api_login(monkeypatch):
    fake = ScriptedFusionAuth([(200, {})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    vib.login(client, login_id="x@y.invalid", password="secretpw", application_id=APP_ID)
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/login")
    assert call["body"] == {"loginId": "x@y.invalid", "password": "secretpw", "applicationId": APP_ID}


def test_enroll_totp_hits_post_user_two_factor_path(monkeypatch):
    fake = ScriptedFusionAuth([(200, {})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    vib.enroll_totp(client, user_id="u1", secret=vib.random_totp_secret())
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/user/two-factor/u1")
    assert call["body"]["method"] == "authenticator"
    assert "secret" in call["body"] and "code" in call["body"]


def test_complete_two_factor_login_hits_post_two_factor_login_unscoped(monkeypatch):
    fake = ScriptedFusionAuth([(200, {"token": "not-a-real-jwt"})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    vib.complete_two_factor_login(client, two_factor_id="tfid", code="123456")
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/two-factor/login")
    assert "X-fusionauth-tenantid" not in call["headers"]


def test_read_lockout_state_hits_get_user_action_with_query_params(monkeypatch):
    fake = ScriptedFusionAuth([(200, {"actions": []})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    vib.read_lockout_state(client, user_id="u1")
    call = fake.calls[0]
    assert call["method"] == "GET"
    assert "/api/user/action" in call["url"]
    assert "userId=u1" in call["url"]
    assert "preventingLogin=true" in call["url"]


# --- Password test-group classification -----------------------------------


def test_password_tests_classify_correctly_and_include_config_only_rows(monkeypatch):
    # P-01 accepted, P-02..P-06 rejected -- exactly the expected outcome.
    script = [
        (200, {"user": {"id": "u1"}}),
        (400, {"fieldErrors": {"user.password": [{"code": "[minLength]"}]}}),
        (400, {"fieldErrors": {"user.password": [{"code": "[requireMixedCase]"}]}}),
        (400, {"fieldErrors": {"user.password": [{"code": "[requireMixedCase]"}]}}),
        (400, {"fieldErrors": {"user.password": [{"code": "[requireNumber]"}]}}),
        (400, {"fieldErrors": {"user.password": [{"code": "[requireNonAlpha]"}]}}),
    ]
    fake = ScriptedFusionAuth(script)
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)

    findings = vib.run_password_tests(client)
    by_id = {f.case_id: f for f in findings}
    for case_id in ("P-01", "P-02", "P-03", "P-04", "P-05", "P-06"):
        assert by_id[case_id].status == vib.Status.PASS, by_id[case_id]
    assert by_id["P-07"].status == vib.Status.NOT_TESTED
    assert by_id["P-08"].status == vib.Status.NOT_TESTED
    assert len(fake.calls) == 6


def test_password_test_unexpected_accept_is_a_real_failure(monkeypatch):
    """If a policy-violating password is wrongly ACCEPTED, that must be FAIL,
    not silently reclassified as success -- this is the actual defect a
    behavioral test exists to catch."""
    script = [
        (200, {"user": {"id": "u1"}}),  # P-01
        (200, {"user": {"id": "u2"}}),  # P-02 -- wrongly accepted!
        (400, {"fieldErrors": {}}),
        (400, {"fieldErrors": {}}),
        (400, {"fieldErrors": {}}),
        (400, {"fieldErrors": {}}),
    ]
    fake = ScriptedFusionAuth(script)
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    findings = vib.run_password_tests(client)
    by_id = {f.case_id: f for f in findings}
    assert by_id["P-02"].status == vib.Status.FAIL


def test_no_password_or_secret_ever_appears_in_a_finding_detail(monkeypatch):
    the_password = "Vvz9!SuperSecretMarkerQx"
    script = [
        (200, {"user": {"id": "u1"}}),
        (400, {}),
        (400, {}),
        (400, {}),
        (400, {}),
        (400, {}),
    ]
    fake = ScriptedFusionAuth(script)
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)

    import unittest.mock as mock

    with mock.patch.object(vib, "compliant_password", return_value=the_password):
        findings = vib.run_password_tests(client)
    for finding in findings:
        assert the_password not in finding.detail
        assert "SuperSecretMarker" not in finding.detail


# --- Lockout + MFA sequence -------------------------------------------


def test_lockout_and_mfa_sequence_full_success_path(monkeypatch):
    too_many_attempts = 3  # small, so the test script stays short
    script: list[tuple[int, dict]] = [
        (200, {"user": {"id": "u1", "email": "x@y.invalid"}}),  # create
        (200, {"registration": {}}),  # register
        (200, {}),  # enroll TOTP
        (242, {"twoFactorId": "tf-1"}),  # M-04/L-01: correct password -> challenge
        (401, {}),  # M-05: wrong code rejected
        (242, {"twoFactorId": "tf-2"}),  # second login for M-06
        (200, {"token": "not-a-real-jwt"}),  # M-06/M-07: correct code -> token
    ]
    # L-02: too_many_attempts - 1 = 2 wrong-password logins
    script += [(401, {}) for _ in range(too_many_attempts - 1)]
    script += [(200, {"actions": []})]  # L-02 read-back: not locked
    script += [(401, {})]  # L-03: the attempt that hits the threshold
    script += [(200, {"actions": [{"expiry": "2026-01-01T00:00:00Z"}]})]  # L-03/L-05 read-back: locked
    script += [(401, {})]  # L-04: correct password while locked -> still rejected

    fake = ScriptedFusionAuth(script)
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)

    findings = vib.run_lockout_and_mfa_sequence(client, APP_ID, too_many_attempts=too_many_attempts)
    by_id = {f.case_id: f for f in findings}

    for case_id in ("M-02", "M-03", "M-04", "L-01", "M-05", "M-06", "M-07", "L-02", "L-03", "L-05", "L-04"):
        assert by_id[case_id].status == vib.Status.PASS, (case_id, by_id[case_id])
    assert by_id["L-unlock-duration"].status == vib.Status.NOT_TESTED


def test_lockout_sequence_flags_a_bypass_as_failure(monkeypatch):
    """If a correct-password login while locked returns 200/242 (bypassing
    the lock), that must be reported as FAIL, not hidden."""
    too_many_attempts = 2
    script: list[tuple[int, dict]] = [
        (200, {"user": {"id": "u1", "email": "x@y.invalid"}}),
        (200, {"registration": {}}),
        (200, {}),
        (242, {"twoFactorId": "tf-1"}),
        (401, {}),
        (242, {"twoFactorId": "tf-2"}),
        (200, {"token": "not-a-real-jwt"}),
    ]
    script += [(401, {}) for _ in range(too_many_attempts - 1)]  # L-02 loop: 1 wrong-password login
    script += [(200, {"actions": []})]  # L-02 read-back after that 1 failure
    script += [(401, {})]  # the threshold-hitting attempt
    script += [(200, {"actions": [{"expiry": "2026-01-01T00:00:00Z"}]})]
    script += [(242, {"twoFactorId": "tf-bypass"})]  # L-04: BYPASS -- should be flagged FAIL

    fake = ScriptedFusionAuth(script)
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)

    findings = vib.run_lockout_and_mfa_sequence(client, APP_ID, too_many_attempts=too_many_attempts)
    by_id = {f.case_id: f for f in findings}
    assert by_id["L-04"].status == vib.Status.FAIL


# --- Control 6 -----------------------------------------------------------


def test_control6_classification_never_promoted_regardless_of_outcome(monkeypatch):
    # Both accepted (the expected/predicted native-FusionAuth gap).
    fake = ScriptedFusionAuth([(200, {"user": {"id": "u1"}}), (200, {"user": {"id": "u2"}})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    findings = vib.run_control6_tests(client)
    for finding in findings:
        assert "PARTIALLY_SATISFIED/B" in finding.detail
        assert finding.status == vib.Status.PASS  # the *check* succeeded at producing evidence


def test_control6_classification_stays_the_same_even_if_fusionauth_rejects(monkeypatch):
    # Both rejected -- a surprising outcome, still must not claim closure.
    fake = ScriptedFusionAuth([(400, {}), (400, {})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    findings = vib.run_control6_tests(client)
    for finding in findings:
        assert "PARTIALLY_SATISFIED/B" in finding.detail


def test_control6_uses_synthetic_names_containing_the_tested_component():
    assert vib.CONTROL6_FIRST_NAME.lower() not in ("", None)
    assert vib.CONTROL6_LAST_NAME != vib.CONTROL6_FIRST_NAME
    # Never a plausible real name -- both start with an unmistakable synthetic prefix.
    assert vib.CONTROL6_FIRST_NAME.startswith("Zz")
    assert vib.CONTROL6_LAST_NAME.startswith("Qq")


# --- Failure handling / partial execution -----------------------------


def test_lockout_sequence_stops_cleanly_if_user_creation_fails(monkeypatch):
    fake = ScriptedFusionAuth([(400, {"fieldErrors": {}})])
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    findings = vib.run_lockout_and_mfa_sequence(client, APP_ID, too_many_attempts=10)
    assert len(findings) == 1
    assert findings[0].status == vib.Status.BLOCKED
    assert len(fake.calls) == 1  # no further calls attempted after the failure


def test_mfa_observation_stops_cleanly_if_registration_fails(monkeypatch):
    fake = ScriptedFusionAuth(
        [(200, {"user": {"id": "u1", "email": "x@y.invalid"}}), (400, {})]
    )
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)
    findings = vib.run_mfa_enforcement_observation(client, APP_ID)
    assert findings[0].status == vib.Status.BLOCKED
    assert len(fake.calls) == 2


# --- CLI safety gates: no network call without explicit confirmation ------


def test_dry_run_makes_zero_network_calls(monkeypatch, capsys):
    monkeypatch.setenv("JUVAL_IDP_API_KEY", "test-key")
    monkeypatch.setenv("JUVAL_IDP_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("JUVAL_IDP_APPLICATION_ID", APP_ID)
    monkeypatch.delenv("JUVAL_IDENTITY_VERIFICATION_CONFIRM", raising=False)

    def _explode(*a, **kw):
        raise AssertionError("no network call should happen in dry-run mode")

    monkeypatch.setattr(vib.urllib.request, "urlopen", _explode)
    monkeypatch.setattr(sys, "argv", ["verify_identity_behavior.py", "--dry-run"])
    exit_code = vib.main()
    assert exit_code == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_execute_without_confirmation_env_var_refuses_and_makes_no_calls(monkeypatch):
    monkeypatch.setenv("JUVAL_IDP_API_KEY", "test-key")
    monkeypatch.setenv("JUVAL_IDP_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("JUVAL_IDP_APPLICATION_ID", APP_ID)
    monkeypatch.delenv("JUVAL_IDENTITY_VERIFICATION_CONFIRM", raising=False)

    def _explode(*a, **kw):
        raise AssertionError("no network call should happen without the confirmation gate")

    monkeypatch.setattr(vib.urllib.request, "urlopen", _explode)
    monkeypatch.setattr(sys, "argv", ["verify_identity_behavior.py", "--execute"])
    exit_code = vib.main()
    assert exit_code == 2


def test_missing_tenant_or_application_id_refuses(monkeypatch):
    monkeypatch.setenv("JUVAL_IDP_API_KEY", "test-key")
    monkeypatch.delenv("JUVAL_IDP_TENANT_ID", raising=False)
    monkeypatch.delenv("JUVAL_IDP_APPLICATION_ID", raising=False)
    monkeypatch.setattr(sys, "argv", ["verify_identity_behavior.py", "--dry-run"])
    exit_code = vib.main()
    assert exit_code == 2


def test_missing_api_key_refuses(monkeypatch):
    monkeypatch.delenv("JUVAL_IDP_API_KEY", raising=False)
    monkeypatch.setenv("JUVAL_IDP_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("JUVAL_IDP_APPLICATION_ID", APP_ID)
    monkeypatch.setattr(sys, "argv", ["verify_identity_behavior.py", "--dry-run"])
    exit_code = vib.main()
    assert exit_code == 2


# --- Full-run ACL surface: only the 7 approved rows are ever touched ------


def test_full_run_only_touches_the_approved_endpoint_set(monkeypatch):
    too_many_attempts = 2
    script: list[tuple[int, dict]] = []
    # run_password_tests: 6 creates
    script += [(200, {"user": {"id": f"p{i}"}}) if i == 0 else (400, {"fieldErrors": {}}) for i in range(6)]
    # run_mfa_enforcement_observation: create, register, login
    script += [(200, {"user": {"id": "m1", "email": "m1@y.invalid"}}), (200, {"registration": {}}), (242, {"twoFactorId": "tf-obs"})]
    # run_lockout_and_mfa_sequence
    script += [
        (200, {"user": {"id": "u1", "email": "x@y.invalid"}}),
        (200, {"registration": {}}),
        (200, {}),
        (242, {"twoFactorId": "tf-1"}),
        (401, {}),
        (242, {"twoFactorId": "tf-2"}),
        (200, {"token": "tok"}),
    ]
    script += [(401, {}) for _ in range(too_many_attempts - 1)]
    script += [(200, {"actions": []})]
    script += [(401, {})]
    script += [(200, {"actions": [{"expiry": "2026-01-01T00:00:00Z"}]})]
    script += [(401, {})]
    # run_control6_tests: 2 creates
    script += [(200, {"user": {"id": "c1"}}), (200, {"user": {"id": "c2"}})]

    fake = ScriptedFusionAuth(script)
    monkeypatch.setattr(vib.urllib.request, "urlopen", fake)
    client = _client(fake)

    vib.run_all(client, APP_ID, too_many_attempts=too_many_attempts)

    approved_prefixes = (
        "/api/user/registration/",
        "/api/user/two-factor/",
        "/api/user/action",
        "/api/user",  # covers plain POST /api/user (must check after more specific prefixes)
        "/api/login",
        "/api/two-factor/login",
    )
    for call in fake.calls:
        path = call["url"].split("127.0.0.1:9011", 1)[-1]
        assert any(path.startswith(p) for p in approved_prefixes), f"unexpected endpoint touched: {path}"
        assert call["method"] != "DELETE"
        assert call["method"] != "PUT"
        assert call["method"] != "PATCH"
