"""Tests for tools/compliance_check.py (RF-01, RF-05, RF-03/RF-04 posture).

The checker is itself a compliance control, so it needs the same treatment as
any other: proof that it *detects failure*, not just that it prints PASS on a
healthy repository. A scanner that cannot fail is not a scanner.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("compliance_check", REPO_ROOT / "tools" / "compliance_check.py")
compliance_check = importlib.util.module_from_spec(_spec)
sys.modules["compliance_check"] = compliance_check
_spec.loader.exec_module(compliance_check)

FAIL = compliance_check.FAIL
WARN = compliance_check.WARN
PASS = compliance_check.PASS


def statuses(findings, check):
    return [f.status for f in findings if f.check == check]


# --- the real repository ----------------------------------------------


def test_repository_has_no_committed_secrets():
    """The whole point: no secret-shaped string anywhere in the tree."""
    findings = compliance_check.scan_for_secrets()
    failures = [f for f in findings if f.status == FAIL]
    assert not failures, "secret scan found candidate secrets: " + "; ".join(f.message for f in failures)


def test_incident_response_plan_is_structurally_complete():
    findings = compliance_check.check_incident_response_plan()
    failures = [f for f in findings if f.status == FAIL]
    assert not failures, "; ".join(f.message for f in failures)


def test_incident_response_plan_still_reports_historical_placeholder():
    """A historical placeholder marker does not prove roles are unassigned.

    The check remains conservative; current assignments are recorded in §2/§12.
    """
    findings = compliance_check.check_incident_response_plan()
    assert WARN in statuses(findings, "irp.placeholders")


def test_static_auth_source_markers_are_present():
    findings = compliance_check.check_auth_posture()
    assert statuses(findings, "auth.endpoints") == [PASS]
    assert statuses(findings, "auth.algorithms") == [PASS]


def test_run_all_exits_clean_on_the_current_repository():
    findings = compliance_check.run_all()
    assert not [f for f in findings if f.status == FAIL]


# --- the checker detects failure --------------------------------------


def test_overdue_review_is_detected():
    """RF-05's six-month cadence must fail once the due date passes."""
    far_future = dt.date(2099, 1, 1)
    findings = compliance_check.check_incident_response_plan(today=far_future)
    assert FAIL in statuses(findings, "irp.review_due")


def test_missing_plan_is_detected(monkeypatch, tmp_path):
    monkeypatch.setattr(compliance_check, "IRP_PATH", tmp_path / "nope.md")
    findings = compliance_check.check_incident_response_plan()
    assert findings[0].status == FAIL


def test_plan_without_amazon_address_is_detected(monkeypatch, tmp_path):
    stub = tmp_path / "plan.md"
    stub.write_text("| Next review due | `2099-01-01` |\n24-hour\n", encoding="utf-8")
    monkeypatch.setattr(compliance_check, "IRP_PATH", stub)
    findings = compliance_check.check_incident_response_plan()
    assert FAIL in statuses(findings, "irp.amazon_address")
    assert FAIL in statuses(findings, "irp.sections")


# Planted fixtures are assembled at runtime, never written as complete
# literals. That way this very file stays clean, the scanner needs no
# self-exclusion, and `test_repository_has_no_committed_secrets` remains a
# genuine assertion about the whole tree rather than one with a hole in it.
def _fake_aws_key() -> str:
    return "AKIA" + "IOSFODNN7EXAMPLE"


def _fake_private_key_header() -> str:
    return "-----BEGIN RSA " + "PRIVATE KEY-----"


def _fake_github_token() -> str:
    return "ghp_" + "a" * 36


def _fake_prod_dsn() -> str:
    return "postgresql://realuser:" + "h9Xk2mQvT4" + "@prod-db.internal:5432/juval"


@pytest.mark.parametrize(
    "factory",
    [_fake_aws_key, _fake_private_key_header, _fake_github_token, _fake_prod_dsn],
    ids=["aws_key", "private_key", "github_token", "production_dsn"],
)
def test_secret_scan_detects_planted_secrets(tmp_path, factory):
    (tmp_path / "leak.py").write_text(f"value = '{factory()}'\n", encoding="utf-8")
    findings = compliance_check.scan_for_secrets(root=tmp_path)
    assert [f for f in findings if f.status == FAIL], f"scanner missed {factory.__name__}"


def test_secret_scan_never_prints_the_matched_value(tmp_path):
    """Evidence artifacts must not themselves leak the secret they found."""
    secret = _fake_aws_key()
    (tmp_path / "leak.py").write_text(f"key = '{secret}'\n", encoding="utf-8")
    findings = compliance_check.scan_for_secrets(root=tmp_path)
    assert all(secret not in f.message for f in findings)


def test_secret_scan_ignores_obvious_placeholder_dsns(tmp_path):
    """Test fixtures must not create permanent false positives."""
    (tmp_path / "t.py").write_text(
        "DSN = 'postgresql://user:pass@localhost:5432/postgres'\n", encoding="utf-8"
    )
    findings = compliance_check.scan_for_secrets(root=tmp_path)
    assert not [f for f in findings if f.status == FAIL]


def test_secret_scan_skips_virtualenvs(tmp_path):
    vendored = tmp_path / ".venv" / "lib"
    vendored.mkdir(parents=True)
    (vendored / "x.py").write_text(f"k = '{_fake_aws_key()}'\n", encoding="utf-8")
    findings = compliance_check.scan_for_secrets(root=tmp_path)
    assert not [f for f in findings if f.status == FAIL]


def test_dependency_finding_names_the_affected_package():
    """A dependency FAIL must be actionable where it happens.

    The environment that fails is usually CI, not the machine reading the
    message, so "run pip-audit yourself for detail" can be unreproducible --
    the finding has to carry the package, version, advisory and fix.
    """
    report = json.dumps(
        {
            "dependencies": [
                {"name": "urllib3", "version": "2.0.1",
                 "vulns": [{"id": "GHSA-v845-jxx5-vc9f", "fix_versions": ["2.0.7"]}]},
                {"name": "openpyxl", "version": "3.1.5", "vulns": []},
            ]
        }
    )
    message = compliance_check._vulnerable_packages(report)
    assert "urllib3==2.0.1" in message
    assert "GHSA-v845-jxx5-vc9f" in message
    assert "fixed in 2.0.7" in message
    # A clean dependency is not named -- only the affected one.
    assert "openpyxl" not in message


def test_dependency_finding_says_so_when_no_fix_exists():
    report = json.dumps(
        {"dependencies": [{"name": "foo", "version": "1.0",
                           "vulns": [{"id": "PYSEC-2026-1", "fix_versions": []}]}]}
    )
    assert "no fixed version published" in compliance_check._vulnerable_packages(report)


def test_dependency_finding_degrades_instead_of_crashing_on_bad_output():
    # pip-audit failing in a way that produces no JSON must not take the whole
    # compliance run down -- the control still has to report a usable FAIL.
    assert "could not parse" in compliance_check._vulnerable_packages("<not json>")


def test_dependency_finding_reports_each_advisory_once():
    # pip-audit returns the same advisory from several feeds; listing it twice
    # makes a one-vulnerability finding read like two.
    report = json.dumps(
        {"dependencies": [{"name": "setuptools", "version": "79.0.1", "vulns": [
            {"id": "PYSEC-2026-3447", "fix_versions": ["83.0.0"]},
            {"id": "PYSEC-2026-3447", "fix_versions": ["83.0.0"]},
        ]}]}
    )
    assert compliance_check._vulnerable_packages(report) == "setuptools==79.0.1 (PYSEC-2026-3447; fixed in 83.0.0)"


@pytest.mark.parametrize("suffix", [".mjs", ".cjs", ".mts", ".cts"])
def test_secret_scan_covers_javascript_and_typescript_module_files(tmp_path, suffix):
    secret = _fake_aws_key()
    (tmp_path / ("module" + suffix)).write_text("export const key = '" + secret + "';")
    findings = compliance_check.scan_for_secrets(root=tmp_path)
    failures = [finding for finding in findings if finding.status == FAIL]
    assert failures
    assert all(secret not in finding.message for finding in findings)


@pytest.mark.parametrize("returncode, stdout", [
    (0, ""), (1, "connection failed"), (0, "null"), (0, "[]"),
    (0, '{"dependencies": []}'),
    (0, '{"dependencies": [{"name": "demo", "version": "1"}]}'),
    (1, '{"dependencies": [{"name": "demo", "version": "1", "vulns": []}]}'),
])
def test_audit_execution_failure_is_inconclusive_not_a_vulnerability(monkeypatch, returncode, stdout):
    from subprocess import CompletedProcess
    monkeypatch.setattr(compliance_check.subprocess, "run", lambda *a, **kw: CompletedProcess([], returncode, stdout, "private diagnostic"))
    findings = compliance_check.check_dependency_vulnerabilities()
    assert statuses(findings, "deps.audit") == [FAIL]
    assert "inconclusive" in findings[0].message
    assert "reported known vulnerabilities" not in findings[0].message
    assert "private diagnostic" not in findings[0].message


@pytest.mark.parametrize("vulnerable", [False, True])
def test_audit_preserves_findings_and_reports_skipped_coverage(monkeypatch, vulnerable):
    from subprocess import CompletedProcess
    report = json.dumps({"dependencies": [
        {"name": "demo", "version": "1", "vulns": [{"id": "TEST-1", "fix_versions": ["2"]}] if vulnerable else []},
        {"name": "local-project", "skip_reason": "private diagnostic"},
    ]})
    monkeypatch.setattr(compliance_check.subprocess, "run", lambda *a, **kw: CompletedProcess([], int(vulnerable), report, ""))
    findings = compliance_check.check_dependency_vulnerabilities()
    assert statuses(findings, "deps.audit") == [FAIL if vulnerable else PASS, WARN]
    assert "PARTIAL" in findings[-1].message
    assert all("private diagnostic" not in finding.message for finding in findings)
    if vulnerable:
        assert "TEST-1" in findings[0].message


def test_secret_scan_cannot_pass_after_an_unreadable_file(monkeypatch, tmp_path):
    target = tmp_path / "unreadable.py"
    target.write_text("ordinary content")
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == target:
            raise PermissionError("private diagnostic")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    findings = compliance_check.scan_for_secrets(tmp_path)
    assert statuses(findings, "secret_scan") == [FAIL]
    assert "scan incomplete" in findings[0].message
    assert "private diagnostic" not in findings[0].message


def test_audit_cannot_pass_when_every_dependency_is_skipped(monkeypatch):
    from subprocess import CompletedProcess
    report = json.dumps({"dependencies": [{"name": "local-project", "skip_reason": "not auditable"}]})
    monkeypatch.setattr(compliance_check.subprocess, "run", lambda *a, **kw: CompletedProcess([], 0, report, ""))
    assert statuses(compliance_check.check_dependency_vulnerabilities(), "deps.audit") == [WARN]
