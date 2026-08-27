"""Exercise the JUVAl backend's OIDC + RBAC enforcement against a real issuer.

`tools/verify_oidc.py` proves the *issuer* is well-formed. This proves the
*backend* accepts a genuine token and enforces least privilege on it -- the
RF-04 runtime evidence that unit tests with a synthetic key pair cannot give,
because they never touch the real JWKS or the real `iss`/`aud` path.

How it gets a real token without a browser flow or a real user: FusionAuth's
`POST /api/jwt/vend` signs arbitrary claims with the tenant's signing key --
the same key published in the JWKS the backend reads. So a token minted here
verifies exactly as a login-issued one would.

It then calls a **running** backend (`JUVAL_AUTH_MODE=oidc`, pointed at the
same issuer) and asserts the status-code matrix:

    role / token         GET /api/v1/runs      GET .../download
    admin                not 401/403           not 401/403
    operator             not 401/403           not 401/403
    viewer               not 401/403           403
    no roles             403                   403
    wrong audience       401                   401
    wrong issuer         401                   401
    expired              401                   401

Secret hygiene (same rules as verify_oidc.py): API key from
`JUVAL_IDP_API_KEY`, never an argument; no token value is ever printed, only
its role label and the resulting status code.

Usage:
    JUVAL_IDP_API_KEY=... python tools/verify_rbac.py \
        --issuer http://127.0.0.1:9011 \
        --audience <application id> \
        --backend http://127.0.0.1:8000

Exit code is non-zero if any row of the matrix does not hold.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

TIMEOUT = 15


def _api(url: str, api_key: str, body: dict) -> dict:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    request.add_header("Authorization", api_key)
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def vend(issuer: str, api_key: str, base: str, *, audience: str, roles: list[str],
         sub: str = "verify-rbac", ttl: int = 120, key_id: Optional[str] = None) -> str:
    claims = {"iss": issuer, "aud": audience, "sub": sub, "roles": roles}
    body: dict = {"claims": claims, "timeToLiveInSeconds": ttl}
    if key_id:
        body["keyId"] = key_id
    result = _api(f"{base.rstrip('/')}/api/jwt/vend", api_key, body)
    token = result.get("token")
    if not token:
        raise RuntimeError("jwt/vend returned no token")
    return token


def call(backend: str, path: str, token: str) -> int:
    request = urllib.request.Request(f"{backend.rstrip('/')}{path}", method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  backend unreachable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return -1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--audience", required=True, help="the JUVAl application id (OAuth client id)")
    parser.add_argument("--backend", default=os.environ.get("JUVAL_BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--base", default=os.environ.get("JUVAL_IDP_BASE"),
                        help="FusionAuth API base if it differs from --issuer (e.g. local while issuer is public)")
    parser.add_argument("--key-id", default=os.environ.get("JUVAL_IDP_SIGNING_KEY_ID"),
                        help="tenant access-token signing key id, if jwt/vend's default is not the published one")
    args = parser.parse_args()

    api_key = os.environ.get("JUVAL_IDP_API_KEY")
    if not api_key:
        print("JUVAL_IDP_API_KEY is not set.", file=sys.stderr)
        return 2

    base = args.base or args.issuer
    runs, download = "/api/v1/runs", "/api/v1/runs/verify-rbac-none/download"

    def token(**kw) -> str:
        return vend(args.issuer, api_key, base, audience=args.audience, key_id=args.key_id, **kw)

    try:
        cases = [
            ("admin",          token(roles=["admin"]),                        (runs, "not-4xx"), (download, "not-4xx")),
            ("operator",       token(roles=["operator"]),                     (runs, "not-4xx"), (download, "not-4xx")),
            ("viewer",         token(roles=["viewer"]),                       (runs, "not-4xx"), (download, "403")),
            ("no-roles",       token(roles=[]),                               (runs, "403"),     (download, "403")),
            ("wrong-audience", vend(args.issuer, api_key, base, audience="not-the-juval-app", roles=["admin"], key_id=args.key_id), (runs, "401"), None),
            ("wrong-issuer",   vend("https://evil.example.com", api_key, base, audience=args.audience, roles=["admin"], key_id=args.key_id), (runs, "401"), None),
            ("expired",        token(roles=["admin"], ttl=1), (runs, "401"), None),
        ]
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, TimeoutError) as exc:
        print(f"could not mint tokens via jwt/vend: {exc}", file=sys.stderr)
        return 1

    time.sleep(2)  # let the ttl=1 token actually expire

    failed = False

    def check(label: str, path: str, expectation: str) -> None:
        nonlocal failed
        status = call(args.backend, path, tok)
        if expectation == "not-4xx":
            ok = status not in (401, 403) and status > 0
        else:
            ok = status == int(expectation)
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed = True
        print(f"  {mark}  {label:<14} {path:<40} -> {status} (want {expectation})")

    for label, tok, first, second in cases:
        check(label, *first)
        if second:
            check(label, *second)

    print()
    if failed:
        print("RBAC MATRIX FAILED. No token value was printed.")
        return 1
    print("RBAC matrix holds. OIDC + least-privilege enforcement verified against the real issuer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
