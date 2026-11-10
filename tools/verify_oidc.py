"""Verify a live OIDC provider against JUVAl's backend expectations.

Produces the RF-03 runtime evidence that no amount of code review can: that a
real issuer publishes a usable discovery document and JWKS, that its signing
algorithm is one `interfaces/api/auth.py` will accept, and that the tenant
password policy actually carries Amazon's values.

Deliberately read-only and secret-free:

* no token, no client secret and no API key is ever printed -- a token is
  summarised by its claim *names* and validity, never its value;
* an API key, when needed to read tenant policy, is taken from the environment
  (`JUVAL_IDP_API_KEY`) and never accepted as an argument, so it cannot land in
  shell history;
* nothing is written to the provider. This tool evidences, it does not
  configure.

Usage:
    python tools/verify_oidc.py --issuer https://idp.example.com
    python tools/verify_oidc.py --issuer ... --tenant-policy   # needs JUVAL_IDP_API_KEY
    python tools/verify_oidc.py --issuer ... --audience <client id> --token-env TEST_TOKEN
        # verifies a test user's token with the API's own verifier and prints
        # the exact iss/sub for `tenancy_admin.py add-member`

Exit code is non-zero when a checked control fails, so it can gate CI.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Optional

TIMEOUT = 10

# Mirrors interfaces/api/auth.py::_ALLOWED_ALGORITHMS. RS256 only: accepting
# "none" or a symmetric algorithm would allow JWT algorithm-confusion forgery.
ACCEPTED_ALGORITHMS = {"RS256"}

# Amazon's human-account baseline (SP_API_REGISTRATION_REMEDIATION.md).
AMAZON_PASSWORD_BASELINE = {
    "minLength": (">=", 12),
    "requireMixedCase": ("==", True),
    "requireNumber": ("==", True),
    "requireNonAlpha": ("==", True),
}


def _get(url: str, api_key: Optional[str] = None) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if api_key:
        request.add_header("Authorization", api_key)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - operator-supplied issuer
        return json.loads(response.read().decode("utf-8"))


class Report:
    """Collects PASS/FAIL lines and decides the exit code."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []
        self.failed = False

    def record(self, ok: Optional[bool], control: str, detail: str) -> None:
        status = "PASS" if ok else ("NOT_VERIFIED" if ok is None else "FAIL")
        if ok is False:
            self.failed = True
        self.rows.append((status, control, detail))

    def render(self) -> str:
        width = max((len(control) for _, control, _ in self.rows), default=0)
        lines = [f"{status:<13} {control:<{width}}  {detail}" for status, control, detail in self.rows]
        return "\n".join(lines)


def check_discovery(report: Report, issuer: str) -> Optional[dict]:
    url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    try:
        document = _get(url)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        report.record(False, "OIDC discovery", f"{url} unreachable or not JSON: {type(exc).__name__}")
        return None
    report.record(True, "OIDC discovery", url)

    # The issuer the provider claims must equal the one the backend will pin,
    # or every token fails the `iss` check at runtime with a bare 401.
    claimed = str(document.get("issuer", ""))
    report.record(
        claimed.rstrip("/") == issuer.rstrip("/"),
        "issuer matches",
        f"document issuer={claimed!r} expected={issuer!r}",
    )
    return document


def check_jwks(report: Report, document: Optional[dict], uri: str) -> None:
    # The backend never reads discovery: it fetches `JUVAL_OIDC_JWKS_URI` or
    # the conventional path. If the provider publishes its keys elsewhere,
    # every token fails at runtime with a bare 401.
    published = (document or {}).get("jwks_uri")
    report.record(
        published == uri if published else None,
        "backend JWKS URI matches discovery",
        f"backend={uri!r} discovery={published!r}",
    )
    try:
        jwks = _get(uri)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        report.record(False, "JWKS reachable", f"{uri}: {type(exc).__name__}")
        return
    keys = jwks.get("keys") or []
    report.record(bool(keys), "JWKS reachable", f"{uri} ({len(keys)} key(s))")

    algorithms = {key.get("alg") for key in keys if key.get("alg")}
    usable = algorithms & ACCEPTED_ALGORITHMS
    report.record(
        bool(usable),
        "signing algorithm",
        f"published={sorted(a for a in algorithms if a)} accepted={sorted(ACCEPTED_ALGORITHMS)}",
    )
    # A key with no `kid` cannot be selected by PyJWKClient when more than one
    # key is published, which surfaces later as an intermittent 401.
    report.record(
        all(key.get("kid") for key in keys) if keys else None,
        "every key has a kid",
        f"{sum(1 for key in keys if key.get('kid'))}/{len(keys)}",
    )


def check_tenant_policy(report: Report, issuer: str) -> None:
    api_key = os.environ.get("JUVAL_IDP_API_KEY")
    if not api_key:
        report.record(None, "tenant password policy", "JUVAL_IDP_API_KEY not set; policy not read")
        return
    try:
        tenants = _get(f"{issuer.rstrip('/')}/api/tenant", api_key=api_key)
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        report.record(False, "tenant password policy", f"unreadable: {type(exc).__name__}")
        return

    for tenant in tenants.get("tenants", []):
        name = tenant.get("name", "?")
        rules = tenant.get("passwordValidationRules", {}) or {}
        for field, (operator, expected) in AMAZON_PASSWORD_BASELINE.items():
            actual = rules.get(field)
            ok = actual is not None and (actual >= expected if operator == ">=" else actual == expected)
            report.record(ok, f"[{name}] {field}", f"actual={actual!r} required {operator} {expected!r}")

        history = (rules.get("rememberPreviousPasswords") or {})
        report.record(
            bool(history.get("enabled")) and int(history.get("count") or 0) >= 10,
            f"[{name}] password history >=10",
            f"enabled={history.get('enabled')} count={history.get('count')}",
        )
        minimum_age = (tenant.get("minimumPasswordAge") or {})
        report.record(
            bool(minimum_age.get("enabled")) and int(minimum_age.get("seconds") or 0) >= 86400,
            f"[{name}] minimum password age >=1d",
            f"enabled={minimum_age.get('enabled')} seconds={minimum_age.get('seconds')}",
        )
        maximum_age = (tenant.get("maximumPasswordAge") or {})
        report.record(
            bool(maximum_age.get("enabled")) and 0 < int(maximum_age.get("days") or 0) <= 365,
            f"[{name}] maximum password age <=365d",
            f"enabled={maximum_age.get('enabled')} days={maximum_age.get('days')}",
        )
        lockout = (tenant.get("failedAuthenticationConfiguration") or {})
        attempts = lockout.get("tooManyAttempts")
        report.record(
            attempts is not None and 0 < int(attempts) <= 10,
            f"[{name}] lockout <=10 attempts",
            f"tooManyAttempts={attempts}",
        )
        # Control 6 is PARTIALLY_SATISFIED by design (ADR-021). Report it as
        # NOT_VERIFIED rather than letting a green run imply Amazon's full
        # "any part of the user's name" requirement is met.
        report.record(
            None,
            f"[{name}] control 6 name exclusion",
            "B - PARTIALLY_SATISFIED (ADR-021): login-Id rejection only, not first/last name",
        )


def check_token(report: Report, issuer: str, audience: str, jwks_uri: str, roles_claim: str, token: str) -> None:
    """Verify one real token with the API's own verifier (`auth.jwks_verifier`).

    Signature, RS256, issuer, audience, expiry and required claims are checked
    by the same code that will run in production. The token is never printed;
    `iss` and `sub` are, because they are what a membership is keyed by.
    """
    from fastapi import HTTPException

    from juval.interfaces.api import auth

    try:
        principal = auth.jwks_verifier(issuer, audience, jwks_uri, roles_claim).verify(token)
    except HTTPException:
        report.record(False, "token verifies", "rejected by the API verifier (signature, RS256, iss, aud, exp or claims)")
        return
    report.record(True, "token verifies", "signature, RS256, iss, aud, exp and required claims")
    report.record(
        bool(principal.permissions),
        "roles claim maps to JUVAl permissions",
        f"claim={roles_claim!r} roles={list(principal.roles)} permissions={sorted(principal.permissions)}",
    )
    # Not a pass/fail: the line an operator copies into `tenancy_admin.py add-member`.
    report.record(True, "membership identity", f"--issuer {principal.issuer!r} --subject {principal.subject!r}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issuer", required=True, help="OIDC issuer URL, e.g. https://idp.example.com")
    parser.add_argument("--jwks-uri", help="the backend's JUVAL_OIDC_JWKS_URI, if set (default: <issuer>/.well-known/jwks.json)")
    parser.add_argument("--audience", help="the backend's JUVAL_OIDC_AUDIENCE; required with --token-env")
    parser.add_argument("--roles-claim", default="roles", help="the backend's JUVAL_OIDC_ROLES_CLAIM")
    parser.add_argument("--token-env", help="NAME of an environment variable holding a test user's token (never the token itself)")
    parser.add_argument("--tenant-policy", action="store_true", help="also read tenant password policy (needs JUVAL_IDP_API_KEY)")
    args = parser.parse_args(argv)
    if args.token_env and not args.audience:
        parser.error("--token-env requires --audience")

    from juval.interfaces.api.auth import default_jwks_uri

    jwks_uri = args.jwks_uri or default_jwks_uri(args.issuer)
    report = Report()
    document = check_discovery(report, args.issuer)
    check_jwks(report, document, jwks_uri)
    if args.token_env:
        token = os.environ.get(args.token_env)
        if token:
            check_token(report, args.issuer, args.audience, jwks_uri, args.roles_claim, token)
        else:
            report.record(False, "token verifies", f"environment variable {args.token_env} is not set")
    if args.tenant_policy:
        check_tenant_policy(report, args.issuer)

    print(report.render())
    print()
    print("NOT_VERIFIED is not a pass. No token, key or secret is printed by this tool.")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
