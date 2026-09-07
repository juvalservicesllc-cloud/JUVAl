"""Deterministic, mocked-FusionAuth tests for tools/diagnose_api_key_401.py.

No live FusionAuth call is made anywhere in this file. `urllib.request.urlopen`
is replaced with a scripted fake that records every request and returns canned
statuses, so each test asserts exactly which endpoints were called, with what
method and body -- and, critically, that the supplied key value never reaches
stdout.

The behaviour under test is the authentication/authorization discriminator
described in `docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` §39.2: a
single empty-body 401 is ambiguous, and only a non-401 on a granted endpoint
resolves it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

SECRET = "super-secret-api-key-value-do-not-print"
APP_ID = "84f077a0-b2b0-4655-8168-082b2233d029"


def _load():
    spec = importlib.util.spec_from_file_location(
        "diagnose_api_key_401", REPO_ROOT / "tools" / "diagnose_api_key_401.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["diagnose_api_key_401"] = module
    spec.loader.exec_module(module)
    return module


diag = _load()


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def read(self) -> bytes:
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class Recorder:
    """Returns a status per request path, recording every call."""

    def __init__(self, by_path: dict[str, int], default: int = 401) -> None:
        self.by_path = by_path
        self.default = default
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request, timeout: Optional[int] = None):
        path = request.full_url.split("9011", 1)[-1]
        self.calls.append(
            {
                "path": path,
                "method": request.get_method(),
                "authorization": request.get_header("Authorization"),
                "tenant": request.get_header("X-fusionauth-tenantid"),
                "body": json.loads(request.data.decode()) if request.data else None,
            }
        )
        status = next(
            (s for p, s in self.by_path.items() if path.startswith(p)), self.default
        )
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "", {}, None)
        return FakeResponse(status)


@pytest.fixture
def patched(monkeypatch):
    def _install(by_path: dict[str, int], default: int = 401) -> Recorder:
        recorder = Recorder(by_path, default)
        monkeypatch.setattr(urllib.request, "urlopen", recorder)
        monkeypatch.setenv("JUVAL_IDP_API_KEY", SECRET)
        return recorder

    return _install


# --- probe construction ---------------------------------------------------


def test_probe_set_covers_the_six_granted_endpoints():
    labels = [p.label for p in diag.build_probes(APP_ID, skip_login=False) if p.granted]
    assert len(labels) == 6
    for fragment in (
        "/api/application/",
        "/api/user/action",
        "POST /api/user (",
        "/api/user/registration",
        "/api/user/two-factor",
        "/api/login",
    ):
        assert any(fragment in label for label in labels), fragment


def test_probe_set_includes_a_not_granted_control():
    controls = [p for p in diag.build_probes(APP_ID, skip_login=False) if not p.granted]
    assert len(controls) == 1
    assert "/api/tenant" in controls[0].path


def test_skip_login_removes_only_the_login_probe():
    with_login = diag.build_probes(APP_ID, skip_login=False)
    without = diag.build_probes(APP_ID, skip_login=True)
    assert len(with_login) - len(without) == 1
    assert not any("/api/login" in p.path for p in without)


def test_mutating_probes_target_random_absent_uuids():
    """Two runs must not reuse a target id, so no probe can hit real state."""
    first = {p.path for p in diag.build_probes(APP_ID, skip_login=False)}
    second = {p.path for p in diag.build_probes(APP_ID, skip_login=False)}
    assert first != second


def test_post_bodies_are_deliberately_invalid():
    """Empty bodies fail FusionAuth validation, so nothing can be created."""
    for probe in diag.build_probes(APP_ID, skip_login=True):
        if probe.method == "POST":
            assert probe.body == {}


# --- classification -------------------------------------------------------


def _results(statuses: dict[str, int]) -> list:
    out = []
    for probe in diag.build_probes(APP_ID, skip_login=False):
        status = next((s for k, s in statuses.items() if k in probe.label), 401)
        out.append(diag.Result(probe, status))
    return out


def test_all_granted_401_yields_no_authentication_evidence_not_a_cause():
    """401 everywhere is an absence of evidence, never a proof of a bad key."""
    verdict, explanation = diag.classify(_results({}))
    assert verdict == "NO_AUTHENTICATION_EVIDENCE_OBTAINED"
    assert "no evidence" in explanation
    assert "(c) the key is stored correctly" in explanation


def test_one_non_401_grant_proves_authentication_works():
    verdict, explanation = diag.classify(_results({"/api/application/": 200}))
    assert verdict == "AUTHENTICATION_CONFIRMED_OK"
    assert "H10" in explanation and "ELIMINATED" in explanation


def test_a_400_also_proves_authentication_works():
    """400 means FusionAuth parsed the body -- it got past authn and authz."""
    verdict, _ = diag.classify(_results({"POST /api/user (": 400}))
    assert verdict == "AUTHENTICATION_CONFIRMED_OK"


def test_control_endpoint_status_does_not_affect_the_verdict():
    """A 401 on the not-granted control is expected and must not count."""
    verdict, _ = diag.classify(_results({"NOT granted": 401}))
    assert verdict == "NO_AUTHENTICATION_EVIDENCE_OBTAINED"


def test_unreachable_server_is_inconclusive_not_a_verdict():
    results = [diag.Result(p, None, error="refused") for p in diag.build_probes(APP_ID, skip_login=False)]
    verdict, _ = diag.classify(results)
    assert verdict == "INCONCLUSIVE"


# --- request shape --------------------------------------------------------


def test_key_is_sent_raw_without_bearer_prefix(patched):
    recorder = patched({})
    diag.main(["--application-id", APP_ID])
    authed = [c for c in recorder.calls if c["authorization"] == SECRET]
    assert authed, "the key must be sent verbatim in Authorization"
    assert not any(
        (c["authorization"] or "").startswith("Bearer") for c in recorder.calls
    )


def test_baseline_controls_run_without_and_with_an_invalid_key(patched):
    recorder = patched({})
    diag.main(["--application-id", APP_ID])
    assert any(c["authorization"] is None for c in recorder.calls)
    assert any(c["authorization"] == diag.INVALID_KEY_CONTROL for c in recorder.calls)


def test_invalid_key_control_is_not_derived_from_the_real_key():
    assert SECRET not in diag.INVALID_KEY_CONTROL
    assert diag.INVALID_KEY_CONTROL == "0" * 32


# --- secret hygiene -------------------------------------------------------


def test_secret_never_appears_in_output(patched, capsys):
    patched({"/api/application/": 200})
    diag.main(["--application-id", APP_ID])
    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert SECRET not in captured.err


def test_no_length_or_fingerprint_of_the_secret_is_printed(patched, capsys):
    patched({})
    diag.main(["--application-id", APP_ID])
    out = capsys.readouterr().out
    assert str(len(SECRET)) not in out
    assert SECRET[:8] not in out
    assert SECRET[-8:] not in out


def test_missing_key_exits_2_and_does_not_probe(patched, monkeypatch):
    recorder = patched({})
    monkeypatch.delenv("JUVAL_IDP_API_KEY", raising=False)
    assert diag.main(["--application-id", APP_ID]) == 2
    assert recorder.calls == []


def test_key_is_not_accepted_as_a_command_line_argument():
    """Arguments are visible in `ps`; the key must come from the environment."""
    with pytest.raises(SystemExit):
        diag.main(["--application-id", APP_ID, "--api-key", SECRET])


# --- credential transport faults ------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("cleankey123", []),
        ("cleankey123 ", ["surrounding whitespace"]),
        (" cleankey123", ["surrounding whitespace"]),
        ("cleankey123\r", ["surrounding whitespace", "carriage return"]),
        ("cleankey123\n", ["surrounding whitespace", "newline"]),
        ("clean key123", ["embedded whitespace"]),
        ("cleankey123–", ["non-ASCII"]),
    ],
)
def test_transport_faults_names_each_class(value, expected):
    faults = " | ".join(diag.transport_faults(value))
    for fragment in expected:
        assert fragment in faults, f"{fragment} not detected in {value!r}"
    if not expected:
        assert faults == ""


def test_transport_fault_report_never_reveals_the_value(patched, capsys):
    patched({})
    import os

    os.environ["JUVAL_IDP_API_KEY"] = SECRET + " "
    try:
        diag.main(["--application-id", APP_ID])
    finally:
        os.environ["JUVAL_IDP_API_KEY"] = SECRET
    out = capsys.readouterr().out
    assert "surrounding whitespace" in out
    assert SECRET not in out
    assert str(len(SECRET)) not in out


def test_sanitising_a_whitespace_damaged_key_is_reported_as_root_cause(monkeypatch, capsys):
    """A valid key wrapped in whitespace must be diagnosed, not blamed on FusionAuth."""
    calls: list[str] = []

    def urlopen(request, timeout=None):
        auth = request.get_header("Authorization")
        calls.append(auth)
        if auth == SECRET:  # the sanitised retry
            return FakeResponse(200)
        raise urllib.error.HTTPError(request.full_url, 401, "", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("JUVAL_IDP_API_KEY", SECRET + "\r")

    assert diag.main(["--application-id", APP_ID]) == 0
    out = capsys.readouterr().out
    assert "ROOT CAUSE FOUND" in out
    assert "carriage return" in out
    assert "No FusionAuth or database change is required" in out
    assert SECRET not in out


# --- diagnostic profile ---------------------------------------------------


def test_diagnostic_profile_has_exactly_one_grant_and_one_control():
    probes = diag.build_diagnostic_probes()
    granted = [p for p in probes if p.granted]
    controls = [p for p in probes if not p.granted]
    assert len(granted) == 1 and granted[0].path == "/api/application"
    assert len(controls) == 1 and controls[0].path == "/api/tenant"


def test_diagnostic_profile_is_entirely_read_only():
    """A single-grant diagnostic key must not be able to change anything."""
    for probe in diag.build_diagnostic_probes():
        assert probe.method == "GET"
        assert probe.body is None


def test_diagnostic_profile_selected_by_flag(patched):
    recorder = patched({})
    diag.main(["--application-id", APP_ID, "--profile", "diagnostic"])
    paths = {c["path"] for c in recorder.calls}
    assert paths <= {"/api/application", "/api/tenant"}
    assert all(c["method"] == "GET" for c in recorder.calls)


def test_diagnostic_200_is_authentication_confirmed(patched, capsys):
    patched({"/api/application": 200})
    diag.main(["--application-id", APP_ID, "--profile", "diagnostic"])
    out = capsys.readouterr().out
    assert "AUTHENTICATION_CONFIRMED_OK" in out
    assert SECRET not in out


# --- tenant header --------------------------------------------------------


def test_tenant_header_sent_on_every_probe_when_requested(patched):
    tenant = "5fcaaf07-8832-491a-a6e7-35d348a591b6"
    recorder = patched({})
    diag.main(["--application-id", APP_ID, "--profile", "diagnostic", "--tenant-id", tenant])
    assert recorder.calls
    for call in recorder.calls:
        assert call.get("tenant") == tenant


def test_tenant_header_absent_by_default(patched):
    recorder = patched({})
    diag.main(["--application-id", APP_ID, "--profile", "diagnostic"])
    assert all(c.get("tenant") is None for c in recorder.calls)


# --- bootstrap profile ----------------------------------------------------


def test_bootstrap_profile_probes_only_bootstrap_grants():
    probes = diag.build_bootstrap_probes(APP_ID)
    granted = [p.path for p in probes if p.granted]
    assert any(p == "/api/tenant" for p in granted)
    assert any(p == "/api/application" for p in granted)
    assert any(p.startswith("/api/application/84f0") for p in granted)
    assert any(p == "/api/jwt/vend" for p in granted)
    # None of the IV3-only user endpoints may appear as a *grant*.
    assert not any("/api/user" in p for p in granted)


def test_bootstrap_profile_control_is_a_user_endpoint():
    controls = [p for p in diag.build_bootstrap_probes(APP_ID) if not p.granted]
    assert len(controls) == 1
    assert "/api/user/action" in controls[0].path


def test_bootstrap_profile_is_read_only_except_an_invalid_jwt_vend():
    for probe in diag.build_bootstrap_probes(APP_ID):
        if probe.method == "POST":
            assert probe.path == "/api/jwt/vend"
            assert probe.body == {}, "must fail validation and mint nothing"


def test_bootstrap_profile_selected_by_flag(patched):
    recorder = patched({})
    diag.main(["--application-id", APP_ID, "--profile", "bootstrap"])
    paths = {c["path"] for c in recorder.calls}
    assert "/api/tenant" in paths
    assert "/api/jwt/vend" in paths
    assert not any(p.startswith("/api/login") for p in paths)


def test_default_profile_is_iv3(patched):
    recorder = patched({})
    diag.main(["--application-id", APP_ID])
    paths = {c["path"] for c in recorder.calls}
    assert "/api/user" in paths
    assert "/api/jwt/vend" not in paths


def test_bootstrap_tenant_200_proves_authentication(patched, capsys):
    """The §39.2 sanity row: a 200 here means the key value authenticates."""
    patched({"/api/tenant": 200})
    diag.main(["--application-id", APP_ID, "--profile", "bootstrap"])
    out = capsys.readouterr().out
    assert "AUTHENTICATION_CONFIRMED_OK" in out
    assert SECRET not in out


def test_clean_key_that_still_401s_is_not_blamed_on_transport(patched, capsys):
    patched({})
    diag.main(["--application-id", APP_ID])
    out = capsys.readouterr().out
    assert "credential transport check" not in out
    assert "NO_AUTHENTICATION_EVIDENCE_OBTAINED" in out
