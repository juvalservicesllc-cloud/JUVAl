"""Discriminate *authentication* from *authorization* for a FusionAuth API key.

An empty-body `HTTP 401` from FusionAuth is ambiguous. It is returned both when
the presented API key is not recognised at all (authentication failure) and when
the key is recognised but lacks the endpoint permission (authorization failure).
The response is byte-identical in both cases -- same status, same
`content-length: 0`, same headers -- so a single 401 proves nothing about which
layer rejected the request.

`docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` §39.2 resolved that
ambiguity for the bootstrap key with one extra row in its probe table:

    Sanity check: GET /api/tenant with the same key, same moment -> 200

That row is what licensed §39's conclusion ("no permission for this endpoint").
Without it, the identical evidence would equally have supported "the key value
is wrong". The IV3 investigation (§41-§43) has **no** such row: every endpoint
probed so far returned 401, so its root cause is still undetermined.

This tool supplies the missing row systematically. It probes every endpoint the
key is *supposed* to be granted, shaping each request so that a key which both
authenticates and is authorized produces a **non-401** status:

    GET  /api/application/{id}          -> 200   (read-only)
    GET  /api/user/action?userId=<uuid> -> 200/404 (read-only, random uuid)
    POST /api/user                      -> 400   (empty body, fails validation)
    POST /api/user/registration         -> 400   (empty body, fails validation)
    POST /api/user/two-factor/<uuid>    -> 400/404 (empty body, random uuid)
    POST /api/login                     -> 404   (random non-existent loginId)

Every request body is deliberately invalid, or targets a randomly generated
UUID that cannot exist. FusionAuth validates before acting, so **no probe can
create, modify or delete identity state**. `/api/login` is the only probe with
any side effect at all (a failed-login audit record against a login id that
matches no user, locking nothing); use `--skip-login` to omit it.

Three controls run alongside the grants:

    no `Authorization` header      -> must be 401 (baseline)
    deliberately invalid key       -> must be 401 (baseline)
    GET /api/tenant (NOT granted)  -> must be 401 (proves scoping is enforced)

Interpretation:

* **any** granted endpoint returns non-401 -> the key value is valid, so
  authentication works and every remaining 401 is an authorization result.
* **all** granted endpoints return 401, while the ACL is independently proven
  persisted (UI + Audit Log + `authentication_keys.permissions` all agree) ->
  six independent, separately-stored grants would all have to be unenforced
  simultaneously. A single invalid credential explains the same evidence with
  one fault instead of six.

The tool reports that distinction and stops. It does not assert a root cause
beyond what the status codes support, and it never treats a 401 as evidence
about a password, lockout or MFA policy -- a request that never authenticated
tested no policy at all.

Secret hygiene: the key is read from `JUVAL_IDP_API_KEY` only, never from an
argument (arguments are visible in `ps`). Its value, length, hash, fingerprint,
prefix and suffix are never printed, logged or persisted. Only endpoint names
and HTTP status codes are emitted.

Usage:
    read -s -p "API key: " JUVAL_IDP_API_KEY; echo; export JUVAL_IDP_API_KEY
    python tools/diagnose_api_key_401.py \
        --base http://127.0.0.1:9011 \
        --application-id 84f077a0-b2b0-4655-8168-082b2233d029

Exit codes are a machine-checkable gate, so a live run can be chained behind
this check with `&&` and refuse to start unless authentication was confirmed:

    0  AUTHENTICATION_CONFIRMED_OK, and the not-granted control was refused
    1  NO_AUTHENTICATION_EVIDENCE_OBTAINED
    2  INCONCLUSIVE -- server unreachable, or no key supplied
    3  SCOPE VIOLATION -- a not-granted endpoint answered, so the key is
       wider than its recorded ACL
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Optional

TIMEOUT = 15

# A syntactically plausible but deliberately invalid key, used as a control.
# It is not derived from any real secret.
INVALID_KEY_CONTROL = "0" * 32


def transport_faults(api_key: str) -> list[str]:
    """Name the *classes* of malformation present in a supplied key value.

    A credential can be perfectly valid on the server yet fail every request
    because the copy held by the caller picked up characters during capture.
    Surrounding whitespace, an embedded CR (which survives `read`, since it is
    not in the default `IFS`) or a non-ASCII character substituted by a text
    editor all produce an unconditional 401 that is indistinguishable from a
    permissions failure.

    This is corroborated evidence, not a hypothetical: the Audit Log entry for
    the current key records its name as `"JUVAL Identity Verification 3 "` --
    with a trailing space -- so the capture path demonstrably carries stray
    whitespace.

    Only the *names* of the fault classes are returned. The value, its length,
    any hash, fingerprint, prefix or suffix are never derived or emitted.
    """
    faults = []
    if api_key != api_key.strip():
        faults.append("surrounding whitespace")
    if "\r" in api_key:
        faults.append("carriage return (survives `read`; not in default IFS)")
    if "\n" in api_key:
        faults.append("newline")
    if any(c.isspace() for c in api_key.strip()):
        faults.append("embedded whitespace")
    if not api_key.isascii():
        faults.append("non-ASCII character (editor substitution?)")
    if any(ord(c) < 32 for c in api_key):
        faults.append("control character")
    return faults


@dataclass(frozen=True)
class Probe:
    """One HTTP probe. `granted` marks endpoints the key should be able to use."""

    label: str
    method: str
    path: str
    body: Optional[dict]
    granted: bool
    expected_if_working: str


@dataclass(frozen=True)
class Result:
    probe: Probe
    status: Optional[int]
    error: Optional[str] = None

    @property
    def is_401(self) -> bool:
        return self.status == 401


def build_diagnostic_probes() -> list[Probe]:
    """Probe set for a single-grant diagnostic key (§46).

    The key carries exactly one permission, `GET /api/application`. A freshly
    created key, captured seconds earlier, isolates *current* API-key
    authentication from the custody and provenance of values captured days
    ago: a `200` says authentication works today and moves the question back
    to the old credentials, a `401` says a brand-new key with one verified
    grant also fails, which no custody explanation covers.

    Both probes are reads. Nothing here can mutate any state.
    """
    return [
        Probe(
            label="GET /api/application  (the only grant)",
            method="GET",
            path="/api/application",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="GET /api/tenant (NOT granted -- control)",
            method="GET",
            path="/api/tenant",
            body=None,
            granted=False,
            expected_if_working="401",
        ),
    ]


def build_behavioral_probes(application_id: str, *, skip_login: bool = False) -> list[Probe]:
    """Probe set for the six-grant behavioral credential (§50).

    Exercises **all six** selectable grants, and leads with the bare
    `GET /api/application` -- the exact call and exact path that `Diagnostic 2`
    answered `200` to. The earlier Behavioral 1 gate ran the `iv3` profile,
    which probes `GET /api/application/{id}` instead and, with `--skip-login`,
    never touched `POST /api/login` at all. So the run that worked and the run
    that failed differed in two ways beyond the credential itself. Both are
    removed here, at no cost, so a future failure cannot be attributed to
    probe shape.

    `POST /api/two-factor/login` is deliberately absent: it is not API-key
    gated and has no grant to test (§49).

    Nothing here can mutate identity state -- every body is deliberately
    invalid or targets a freshly generated UUID. `POST /api/login` is the only
    probe with any side effect, a failed-login record against a login id that
    matches no user; it is the only way to exercise that grant, and
    `--skip-login` omits it.
    """
    absent_user = str(uuid.uuid4())
    probes = [
        Probe(
            label="GET /api/application  (bare -- Diagnostic 2 got 200 here)",
            method="GET",
            path="/api/application",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="GET /api/application/{id}",
            method="GET",
            path=f"/api/application/{application_id}",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="GET /api/user/action?userId=<absent>",
            method="GET",
            path=f"/api/user/action?userId={absent_user}",
            body=None,
            granted=True,
            expected_if_working="200 or 404",
        ),
        Probe(
            label="POST /api/user (empty body)",
            method="POST",
            path="/api/user",
            body={},
            granted=True,
            expected_if_working="400",
        ),
        Probe(
            label="POST /api/user/registration (empty body)",
            method="POST",
            path="/api/user/registration",
            body={},
            granted=True,
            expected_if_working="400",
        ),
        Probe(
            label="POST /api/user/two-factor/<absent> (empty body)",
            method="POST",
            path=f"/api/user/two-factor/{absent_user}",
            body={},
            granted=True,
            expected_if_working="400 or 404",
        ),
    ]
    if not skip_login:
        probes.append(
            Probe(
                label="POST /api/login (absent loginId -- 6th grant)",
                method="POST",
                path="/api/login",
                body={
                    "loginId": f"juval-diagnostic-{uuid.uuid4()}@invalid.example",
                    "password": str(uuid.uuid4()),
                    "applicationId": application_id,
                },
                granted=True,
                expected_if_working="404",
            )
        )
    probes.append(
        Probe(
            label="GET /api/tenant (NOT granted -- control)",
            method="GET",
            path="/api/tenant",
            body=None,
            granted=False,
            expected_if_working="401",
        )
    )
    return probes


def build_bootstrap_probes(application_id: str) -> list[Probe]:
    """Probe set for the unscoped `JUVAl bootstrap` keys (§43.9).

    All three bootstrap rows grant `/api/application` and `/api/tenant`
    (GET/POST/PATCH); only `de00c6d3` also grants `/api/jwt/vend`. Every probe
    here is a read, except `POST /api/jwt/vend` with an empty body, which
    fails validation and mints no token.

    `GET /api/tenant` is the point of this profile: §39.2 recorded exactly that
    call returning `200` on 2026-09-01, and the row has not been modified since
    16:23:35 that day, has not expired, and sits on a process that has not
    restarted. It is the one call with a documented working result to compare
    against.
    """
    return [
        Probe(
            label="GET /api/tenant  (§39.2 recorded 200)",
            method="GET",
            path="/api/tenant",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="GET /api/application",
            method="GET",
            path="/api/application",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="GET /api/application/{id}",
            method="GET",
            path=f"/api/application/{application_id}",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="POST /api/jwt/vend (empty body; de00c6d3 only)",
            method="POST",
            path="/api/jwt/vend",
            body={},
            granted=True,
            expected_if_working="400 (401 if not the de00c6d3 row)",
        ),
        Probe(
            label="GET /api/user/action (NOT granted -- control)",
            method="GET",
            path=f"/api/user/action?userId={uuid.uuid4()}",
            body=None,
            granted=False,
            expected_if_working="401",
        ),
    ]


def build_probes(application_id: str, *, skip_login: bool) -> list[Probe]:
    """Return the IV3 probe set. Random UUIDs guarantee the targets do not exist."""
    absent_user = str(uuid.uuid4())
    absent_login = f"juval-diagnostic-{uuid.uuid4()}@invalid.example"

    probes = [
        Probe(
            label="GET /api/application/{id}",
            method="GET",
            path=f"/api/application/{application_id}",
            body=None,
            granted=True,
            expected_if_working="200",
        ),
        Probe(
            label="GET /api/user/action?userId=<absent>",
            method="GET",
            path=f"/api/user/action?userId={absent_user}",
            body=None,
            granted=True,
            expected_if_working="200 or 404",
        ),
        Probe(
            label="POST /api/user (empty body)",
            method="POST",
            path="/api/user",
            body={},
            granted=True,
            expected_if_working="400",
        ),
        Probe(
            label="POST /api/user/registration (empty body)",
            method="POST",
            path="/api/user/registration",
            body={},
            granted=True,
            expected_if_working="400",
        ),
        Probe(
            label="POST /api/user/two-factor/<absent> (empty body)",
            method="POST",
            path=f"/api/user/two-factor/{absent_user}",
            body={},
            granted=True,
            expected_if_working="400 or 404",
        ),
    ]

    if not skip_login:
        probes.append(
            Probe(
                label="POST /api/login (absent loginId)",
                method="POST",
                path="/api/login",
                body={
                    "loginId": absent_login,
                    "password": str(uuid.uuid4()),
                    "applicationId": application_id,
                },
                granted=True,
                expected_if_working="404",
            )
        )

    # Negative control: NOT in the key's ACL, so a scoped key must be refused.
    probes.append(
        Probe(
            label="GET /api/tenant (NOT granted -- control)",
            method="GET",
            path="/api/tenant",
            body=None,
            granted=False,
            expected_if_working="401",
        )
    )
    return probes


def send(
    base: str,
    probe: Probe,
    api_key: Optional[str],
    tenant_id: Optional[str] = None,
) -> Result:
    """Issue one probe. Returns the status code; never echoes the key."""
    data = json.dumps(probe.body).encode() if probe.body is not None else None
    request = urllib.request.Request(base + probe.path, data=data, method=probe.method)
    if api_key is not None:
        request.add_header("Authorization", api_key)
    if tenant_id is not None:
        request.add_header("X-FusionAuth-TenantId", tenant_id)
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
            return Result(probe, response.status)
    except urllib.error.HTTPError as exc:
        return Result(probe, exc.code)
    except urllib.error.URLError as exc:
        # `exc.reason` is a socket/SSL error; it never contains request headers.
        return Result(probe, None, error=str(exc.reason))


def classify(results: list[Result]) -> tuple[str, str]:
    """Return (verdict, explanation) from the granted-endpoint statuses only."""
    granted = [r for r in results if r.probe.granted]
    unreachable = [r for r in granted if r.status is None]
    if unreachable:
        return (
            "INCONCLUSIVE",
            "One or more probes could not reach the server; no conclusion drawn.",
        )

    non_401 = [r for r in granted if not r.is_401]
    if non_401:
        labels = ", ".join(r.probe.label for r in non_401)
        return (
            "AUTHENTICATION_CONFIRMED_OK",
            "The value used in THIS run authenticates: it produced a non-401 "
            f"status on {len(non_401)} granted endpoint(s) ({labels}). Any "
            "remaining 401 in this run is therefore an authorization result, "
            "not a bad credential.\n"
            "  Scope: this says nothing about any OTHER credential. It does not "
            "establish that some previously captured value corresponds to its "
            "intended row, and it does not eliminate the custody/provenance "
            "hypothesis for historical keys -- only that the runtime accepted "
            "the value presented here.",
        )

    return (
        "NO_AUTHENTICATION_EVIDENCE_OBTAINED",
        f"All {len(granted)} granted endpoints returned 401, so this run "
        "produced no evidence that the supplied value ever authenticated. That "
        "is the limit of what it shows. It does NOT by itself identify which "
        "of these is true, and they are not distinguishable from status codes "
        "alone:\n"
        "    (a) the value is not any key FusionAuth stores;\n"
        "    (b) the value is a correct key that was damaged in capture;\n"
        "    (c) the key is stored correctly and the runtime lookup or "
        "verification is at fault.\n"
        "  Do not declare a root cause, rotate the key, or broaden the ACL on "
        "the strength of this result.",
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default=os.environ.get("JUVAL_IDP_BASE", "http://127.0.0.1:9011"))
    parser.add_argument("--application-id", required=True)
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="send X-FusionAuth-TenantId with every probe (a tenant id is "
        "not a secret; it appears throughout this repo's documentation)",
    )
    parser.add_argument(
        "--skip-login",
        action="store_true",
        help="omit the POST /api/login probe (its only side effect is a "
        "failed-login record against a login id that matches no user)",
    )
    parser.add_argument(
        "--profile",
        choices=("behavioral", "iv3", "bootstrap", "diagnostic"),
        default="iv3",
        help="which key's granted endpoints to probe (default: iv3)",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("JUVAL_IDP_API_KEY")
    if not api_key:
        print(
            "JUVAL_IDP_API_KEY is not set. Load it without echoing it:\n"
            '  read -s -p "API key: " JUVAL_IDP_API_KEY; echo; export JUVAL_IDP_API_KEY',
            file=sys.stderr,
        )
        return 2

    if args.profile == "behavioral":
        probes = build_behavioral_probes(args.application_id, skip_login=args.skip_login)
    elif args.profile == "diagnostic":
        probes = build_diagnostic_probes()
    elif args.profile == "bootstrap":
        probes = build_bootstrap_probes(args.application_id)
    else:
        probes = build_probes(args.application_id, skip_login=args.skip_login)

    print(f"base = {args.base}")
    print(f"profile = {args.profile}")
    if args.tenant_id:
        print("X-FusionAuth-TenantId header: sent")
    print("(the API key value is never printed, hashed or persisted)\n")

    print("--- baseline controls -------------------------------------------")
    # Same endpoint the profile probes, so the controls are comparable.
    baseline = probes[0]
    no_auth = send(args.base, baseline, None, args.tenant_id)
    bad_key = send(args.base, baseline, INVALID_KEY_CONTROL, args.tenant_id)
    print(f"  no Authorization header       -> {no_auth.status} (expect 401)")
    print(f"  deliberately invalid key      -> {bad_key.status} (expect 401)")
    if no_auth.status != 401 or bad_key.status != 401:
        print("  WARNING: baseline is not 401; the 401 signature assumed below "
              "does not hold on this server.")

    print("\n--- probes with the supplied key --------------------------------")
    results = []
    for probe in probes:
        result = send(args.base, probe, api_key, args.tenant_id)
        results.append(result)
        marker = "grant " if probe.granted else "control"
        shown = result.status if result.status is not None else f"ERROR {result.error}"
        print(f"  [{marker}] {probe.label:<48} -> {shown}  (working: {probe.expected_if_working})")

    # A malformed *copy* of a valid key 401s on everything. Retry once with the
    # value sanitised; if that changes the outcome, the server was never at
    # fault. Only the fault class and the retry's status are printed.
    faults = transport_faults(api_key)
    if faults and all(r.is_401 for r in results if r.probe.granted):
        print("\n--- credential transport check -----------------------------------")
        print(f"  the supplied value carries: {', '.join(faults)}")
        sanitised = api_key.strip()
        retry = send(args.base, probes[0], sanitised, args.tenant_id)
        print(f"  retry of {probes[0].label} with surrounding whitespace removed -> {retry.status}")
        if retry.status is not None and not retry.is_401:
            print(
                "\n  ROOT CAUSE FOUND: the key value is valid; the copy held by "
                "the caller was malformed in transport. Re-capture it cleanly. "
                "No FusionAuth or database change is required."
            )
            return 0
        print("  sanitising did not change the outcome; the fault is elsewhere.")

    verdict, explanation = classify(results)
    print("\n--- verdict ------------------------------------------------------")
    print(f"  {verdict}")
    print(f"  {explanation}")

    control = next((r for r in results if not r.probe.granted), None)
    if control is not None and control.status is not None and not control.is_401:
        print(
            f"\n  SCOPE VIOLATION: the not-granted control endpoint "
            f"({control.probe.label}) returned {control.status}, not 401. The key "
            "is behaving as WIDER than its recorded ACL. Report this before "
            "drawing any other conclusion, and do not run anything behind this "
            "check."
        )
        return 3

    # Exit codes are a machine-checkable gate, so a caller can chain a live
    # run behind this check with `&&` and have it refuse to start unless
    # authentication was actually confirmed:
    #   0 = AUTHENTICATION_CONFIRMED_OK, and the not-granted control was
    #       correctly refused
    #   1 = NO_AUTHENTICATION_EVIDENCE_OBTAINED
    #   2 = INCONCLUSIVE (server unreachable, or no key supplied)
    #   3 = SCOPE VIOLATION: a not-granted endpoint answered, so the key is
    #       wider than its recorded ACL
    return {"AUTHENTICATION_CONFIRMED_OK": 0, "INCONCLUSIVE": 2}.get(verdict, 1)


if __name__ == "__main__":
    raise SystemExit(main())
