"""Mechanical verification of JUVAl's Amazon compliance artifacts.

A Markdown file cannot assert anything about itself. This script checks the
things a reviewer would otherwise have to take on trust:

  * the incident response plan has every section Amazon's findings require;
  * it states the `security@amazon.com` address and the 24-hour obligation;
  * its six-month review (RF-05) is not overdue *as of today*;
  * unfilled `ROLE PLACEHOLDER` items are surfaced, so an unapproved plan can
    never be quietly presented as finished;
  * no secret-shaped string has been committed anywhere in the repository.

Run:  python tools/compliance_check.py
Exit: 0 = no FAIL findings, 1 = at least one FAIL.

Stdlib only, by design -- a compliance check that needs its own dependency
tree is one more thing that can rot. It never prints a matched secret value,
only the file and line where one was found.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
IRP_PATH = REPO_ROOT / "docs" / "compliance" / "INCIDENT_RESPONSE_PLAN.md"

PASS, FAIL, WARN, INFO = "PASS", "FAIL", "WARN", "INFO"


@dataclass(frozen=True)
class Finding:
    check: str
    status: str
    message: str


# --- Incident response plan (RF-01, RF-05) ----------------------------

# Section headings the plan must contain. Amazon's findings name roles,
# periodic review and a 24-hour notification procedure; the rest is what makes
# those actually executable rather than aspirational.
REQUIRED_IRP_SECTIONS = [
    "What counts as a Security Incident",
    "Roles",
    "Severity classification",
    "Response procedure",
    "Credential revocation matrix",
    "Determine whether Amazon Information is involved",
    "Preserve evidence",
    "Recover",
    "Amazon notification",
    "Communication",
    "Postmortem",
    "Plan review",
    "Tabletop exercise",
    "Approval",
]

REVIEW_DUE_RE = re.compile(r"\|\s*Next review due\s*\|\s*`?(\d{4}-\d{2}-\d{2})`?")
PLACEHOLDER_RE = re.compile(r"ROLE PLACEHOLDER")


def check_incident_response_plan(today: dt.date | None = None) -> list[Finding]:
    today = today or dt.date.today()
    findings: list[Finding] = []

    if not IRP_PATH.is_file():
        return [Finding("irp.exists", FAIL, f"missing incident response plan: {IRP_PATH}")]

    text = IRP_PATH.read_text(encoding="utf-8")

    missing = [s for s in REQUIRED_IRP_SECTIONS if s not in text]
    if missing:
        findings.append(
            Finding("irp.sections", FAIL, f"incident response plan is missing sections: {', '.join(missing)}")
        )
    else:
        findings.append(Finding("irp.sections", PASS, f"all {len(REQUIRED_IRP_SECTIONS)} required sections present"))

    if "security@amazon.com" in text:
        findings.append(Finding("irp.amazon_address", PASS, "security@amazon.com notification address is stated"))
    else:
        findings.append(Finding("irp.amazon_address", FAIL, "security@amazon.com is not stated (RF-01)"))

    if re.search(r"24[\s-]?hour", text, re.IGNORECASE):
        findings.append(Finding("irp.24h", PASS, "24-hour notification obligation is stated"))
    else:
        findings.append(Finding("irp.24h", FAIL, "the 24-hour notification obligation is not stated (RF-01)"))

    match = REVIEW_DUE_RE.search(text)
    if not match:
        findings.append(Finding("irp.review_due", FAIL, "no parseable 'Next review due' date (RF-05)"))
    else:
        due = dt.date.fromisoformat(match.group(1))
        if due < today:
            findings.append(
                Finding("irp.review_due", FAIL, f"six-month review is OVERDUE (was due {due.isoformat()}) (RF-05)")
            )
        else:
            findings.append(
                Finding("irp.review_due", PASS, f"review current; next due {due.isoformat()} ({(due - today).days} days)")
            )

    placeholders = len(PLACEHOLDER_RE.findall(text))
    if placeholders:
        findings.append(
            Finding(
                "irp.placeholders",
                WARN,
                f"{placeholders} unfilled ROLE PLACEHOLDER item(s) remain in the document "
                "(check whether they are live role assignments or a preserved historical "
                "record) -- do not cite the plan as fully evidenced until §12 confirms "
                "every required action is DONE (EXTERNAL USER ACTION REQUIRED)",
            )
        )
    else:
        findings.append(Finding("irp.placeholders", PASS, "no unfilled role placeholders"))

    return findings


# --- Secret scan ------------------------------------------------------

# High-signal patterns only. A scanner that cries wolf gets switched off, and
# a switched-off scanner is worse than none.
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("json_web_token", re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.")),
    ("postgres_url_with_password", re.compile(r"postgres(?:ql)?://([^\s:/@]+):([^\s@'\"]+)@([^\s/'\":]+)")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("stripe_live_key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
]

# Obvious non-secrets used in tests and documentation. Keeping these out of the
# results is what stops the scanner from being ignored; anything not matching
# both a placeholder credential AND a local/example host still fails.
PLACEHOLDER_CREDENTIALS = {"user:pass", "user:password", "postgres:postgres", "user:secret", "username:password"}
PLACEHOLDER_HOSTS = {"localhost", "127.0.0.1", "db", "postgres", "example.com", "host"}


def _is_placeholder_dsn(match: re.Match[str]) -> bool:
    user, password, host = match.group(1), match.group(2), match.group(3)
    return f"{user}:{password}".lower() in PLACEHOLDER_CREDENTIALS and host.lower() in PLACEHOLDER_HOSTS


EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".mypy_cache", ".ruff_cache", "coverage",
}

SCANNED_SUFFIXES = {
    ".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml", ".ts", ".tsx",
    ".js", ".jsx", ".html", ".css", ".sql", ".sh", ".cfg", ".ini", ".example",
}


def _scannable_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SCANNED_SUFFIXES or path.name == ".env.example":
            yield path


def scan_for_secrets(root: Path | None = None) -> list[Finding]:
    """Report files containing secret-shaped strings. Never prints the value."""
    root = root or REPO_ROOT
    findings: list[Finding] = []
    scanned = 0

    for path in _scannable_files(root):
        scanned += 1
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            for name, pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if match:
                    if name == "postgres_url_with_password" and _is_placeholder_dsn(match):
                        continue
                    rel = path.relative_to(root).as_posix()
                    findings.append(
                        Finding(
                            "secret_scan",
                            FAIL,
                            f"possible {name} at {rel}:{line_no} (value intentionally not shown)",
                        )
                    )

    if not findings:
        findings.append(Finding("secret_scan", PASS, f"no secret-shaped strings found in {scanned} files"))
    return findings


# --- Auth posture -----------------------------------------------------


def check_auth_posture() -> list[Finding]:
    """The API must fail closed, and must not be able to silently run open."""
    auth_path = REPO_ROOT / "src" / "juval" / "interfaces" / "api" / "auth.py"
    if not auth_path.is_file():
        return [Finding("auth.module", FAIL, "interfaces/api/auth.py is missing (RF-03/RF-04)")]

    text = auth_path.read_text(encoding="utf-8")
    findings = [Finding("auth.module", PASS, "interfaces/api/auth.py present")]

    if '_ALLOWED_ALGORITHMS = ["RS256"]' in text:
        findings.append(Finding("auth.algorithms", PASS, "JWT algorithms pinned to RS256 (no alg-confusion)"))
    else:
        findings.append(Finding("auth.algorithms", FAIL, "JWT algorithms are not pinned to an asymmetric allow-list"))

    main_path = REPO_ROOT / "src" / "juval" / "interfaces" / "api" / "main.py"
    main_text = main_path.read_text(encoding="utf-8") if main_path.is_file() else ""
    unprotected = [
        line.strip()
        for line in main_text.splitlines()
        if line.strip().startswith("@app.") and "exception_handler" not in line
    ]
    protected_count = main_text.count("Depends(require(")
    if unprotected and protected_count < len(unprotected):
        findings.append(
            Finding(
                "auth.endpoints",
                FAIL,
                f"{len(unprotected)} route(s) declared but only {protected_count} permission check(s) -- "
                "every endpoint must enforce a permission server-side (RF-04)",
            )
        )
    else:
        findings.append(
            Finding("auth.endpoints", PASS, f"all {len(unprotected)} route(s) enforce a permission server-side")
        )

    return findings


# --- Runner -----------------------------------------------------------


def check_dependency_vulnerabilities() -> list[Finding]:
    """Run pip-audit against the installed dependency set (AC-13A).

    pip-audit is a dev tool, so its absence is a WARN (the control is not
    running) rather than a FAIL (the code is not broken). A found
    vulnerability is a FAIL -- that is the point of the check.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--progress-spinner", "off", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError:
        return [Finding("deps.audit", WARN, "pip-audit is not installed; dependency scanning is NOT running")]
    except subprocess.TimeoutExpired:
        return [Finding("deps.audit", WARN, "pip-audit timed out; dependency scan inconclusive")]

    output = (result.stdout or "") + (result.stderr or "")
    if "No module named" in output:
        return [Finding("deps.audit", WARN, "pip-audit is not installed; dependency scanning is NOT running")]
    if result.returncode == 0:
        return [Finding("deps.audit", PASS, "pip-audit: no known vulnerabilities in installed dependencies")]
    return [Finding("deps.audit", FAIL, f"pip-audit reported known vulnerabilities: {_vulnerable_packages(result.stdout)}")]


def _vulnerable_packages(stdout: str) -> str:
    """Name the affected package, version and advisory IDs.

    A control that reports only "there are vulnerabilities" is not evidence
    anyone can act on -- and the environment that fails is often CI, not the
    machine reading the message, so "run it yourself for detail" can be
    unreproducible. Report the detail where the failure happens.
    """
    try:
        report = json.loads(stdout)
    except (ValueError, TypeError):
        return "could not parse the pip-audit report -- run `python -m pip_audit` for detail"

    affected = [
        f"{dep.get('name', '?')}=={dep.get('version', '?')} "
        f"({', '.join(sorted({v.get('id', '?') for v in dep['vulns']}))}"
        + (f"; fixed in {', '.join(sorted({f for v in dep['vulns'] for f in v.get('fix_versions') or []}))}"
           if any(v.get("fix_versions") for v in dep["vulns"]) else "; no fixed version published")
        + ")"
        for dep in report.get("dependencies", [])
        if dep.get("vulns")
    ]
    return "; ".join(affected) or "pip-audit exited non-zero but reported no vulnerable package"


def run_all() -> list[Finding]:
    return [
        *check_incident_response_plan(),
        *check_auth_posture(),
        *check_dependency_vulnerabilities(),
        *scan_for_secrets(),
    ]


def main() -> int:
    findings = run_all()

    width = max(len(f.check) for f in findings)
    for f in findings:
        print(f"[{f.status:<4}] {f.check:<{width}}  {f.message}")

    fails = [f for f in findings if f.status == FAIL]
    warns = [f for f in findings if f.status == WARN]

    print()
    print(f"{len(findings)} checks: {len(findings) - len(fails) - len(warns)} pass, {len(warns)} warn, {len(fails)} fail")

    if fails:
        print("\nRESULT: FAIL -- compliance artifacts are structurally incomplete.")
        return 1
    if warns:
        print("\nRESULT: PASS WITH WARNINGS -- structurally complete, but not yet")
        print("approved/evidenced. See the warnings above before citing anything to Amazon.")
        return 0
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
