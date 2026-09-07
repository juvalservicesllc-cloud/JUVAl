"""Behavioral verification of password/lockout/MFA/Control-6 against a real,
disposable JUVAl-tenant FusionAuth user.

`tools/verify_rbac.py` proves the RBAC boundary using a token minted via
`POST /api/jwt/vend` -- it never touches a credential or a real login.
This tool closes the gap that leaves open: it creates real, disposable users
in the `JUVAl` tenant/application and exercises the actual FusionAuth
runtime paths -- `POST /api/user`, `POST /api/user/registration`,
`POST /api/login`, TOTP enrollment, and the two-factor login challenge --
to observe what FusionAuth *does*, not just what its configuration says it
should do.

Endpoints were derived from FusionAuth's own 1.69.0 OpenAPI specification
(https://github.com/FusionAuth/fusionauth-openapi, `info.version: 1.69.0`,
confirmed against the exact deployed instance version), not from memory or
prose docs -- see the exact-endpoint comments on each request below.

Design constraints (all enforced in code, not just by convention):

  * fails closed against anything but the confirmed `JUVAl` tenant and
    application -- see `verify_targeting()`. There is no default tenant/
    application id; both must be supplied and are independently checked
    against FusionAuth's own record before any write;
  * never issues `DELETE` -- `Client._request` raises if asked to. Cleanup
    strategy is documented below, deliberately not deletion;
  * the API key is read from `JUVAL_IDP_API_KEY` in the environment only,
    same secret hygiene as `tools/configure_fusionauth.py` and
    `tools/verify_rbac.py` -- never an argument, never printed, never
    persisted;
  * passwords, TOTP secrets, TOTP codes and JWTs are held only in local
    variables for the lifetime of one check and are never included in a
    `Finding.detail`, printed, or logged. Only non-secret metadata (HTTP
    status, error codes, field names, timestamps, ids) is ever surfaced;
  * a live run needs both `--execute` and
    `JUVAL_IDENTITY_VERIFICATION_CONFIRM=yes-run-live-writes` in the
    environment. Without both, the tool only prints its planned sequence
    (`--dry-run`, also the default) and makes zero network calls.

Cleanup strategy -- deliberately NOT deletion:

Every disposable user this tool creates is tagged (`user.data`) with the
tool name, the case it was created for, and a timestamp, and uses an
obviously synthetic `firstName`/`lastName` so it is unmistakable in the
FusionAuth admin UI's user list. Its password is never recorded anywhere
outside one local variable for the duration of its own check, so once the
process exits, the account is not usably authenticatable by anyone who
only has read access to FusionAuth -- it becomes an inert, clearly-labeled
fixture, not a live credential. True deactivation (`user.active = false`)
would need `PATCH /api/user/{userId}`, which this tool deliberately does
not request or use (see the ACL matrix in the accompanying compliance
report) -- disposable users accumulate in the tenant across runs. This is
the explicit tradeoff reported to the operator rather than granting DELETE
or PATCH for cleanup convenience.

Usage (a live run needs its own separate least-privilege API key --
see the ACL matrix; never the JUVAl Bootstrap key):

    JUVAL_IDP_API_KEY=... \\
    JUVAL_IDP_TENANT_ID=<JUVAl tenant id> \\
    JUVAL_IDP_APPLICATION_ID=<JUVAl application id> \\
    python tools/verify_identity_behavior.py --dry-run

    # Live (needs the extra confirmation gate too):
    JUVAL_IDP_API_KEY=... JUVAL_IDP_TENANT_ID=... JUVAL_IDP_APPLICATION_ID=... \\
    JUVAL_IDENTITY_VERIFICATION_CONFIRM=yes-run-live-writes \\
    python tools/verify_identity_behavior.py --execute

Exit code is non-zero if any case is classified FAIL.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

TIMEOUT = 15

TENANT_NAME = "JUVAl"
APPLICATION_NAME = "JUVAl"

# Amazon control 6 ("reject a password containing any part of the user's
# name") test fixtures. Synthetic, non-sensitive, unmistakably test data --
# never a real person's name.
CONTROL6_FIRST_NAME = "Zzqxctrlsix"
CONTROL6_LAST_NAME = "QqvxNamecheck"

# firstName/lastName for every other disposable user this tool creates, so
# any of them is instantly recognizable in the FusionAuth admin UI.
DISPOSABLE_FIRST_NAME = "ZzvIdentityVerification"
DISPOSABLE_LAST_NAME = "DisposableTestUser"

# The tenant's authenticator config (deploy/fusionauth/tenant-password-
# policy.template.json): HmacSHA1, 6 digits, 30s step. Hardcoded here
# because it must match what was actually configured, not a library default.
_TOTP_ALGORITHM = hashlib.sha1
_TOTP_DIGITS = 6
_TOTP_PERIOD = 30


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_TESTED = "NOT_TESTED"


@dataclass(frozen=True)
class Finding:
    case_id: str
    status: Status
    detail: str  # never a password, TOTP secret/code, or token value


class IdentityVerificationError(RuntimeError):
    pass


# --- TOTP (RFC 6238), stdlib only -------------------------------------
#
# GET /api/two-factor/secret exists in FusionAuth's API but its OpenAPI
# operation (`generateTwoFactorSecretUsingJWTWithId`) overrides the global
# ApiKeyAuth security scheme with `BearerAuth` -- it authenticates with an
# end user's own JWT, not an API key, so it is not reachable by this tool's
# API-key-only design. A TOTP secret is just cryptographically random
# bytes; generating it locally is equivalent and needs no FusionAuth call
# or ACL grant at all.


def random_totp_secret(length: int = 20) -> str:
    return base64.b32encode(os.urandom(length)).decode("ascii").rstrip("=")


def totp_code(secret_base32: str, *, at: Optional[float] = None) -> str:
    padded = secret_base32.upper()
    padded += "=" * ((8 - len(padded) % 8) % 8)
    key = base64.b32decode(padded)
    counter = int((at if at is not None else time.time()) // _TOTP_PERIOD)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, _TOTP_ALGORITHM).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**_TOTP_DIGITS)
    return str(code_int).zfill(_TOTP_DIGITS)


def wrong_totp_code(secret_base32: str) -> str:
    """A 6-digit code guaranteed to differ from the currently-valid one."""
    correct = int(totp_code(secret_base32))
    return str((correct + 1) % (10**_TOTP_DIGITS)).zfill(_TOTP_DIGITS)


# --- Disposable identities ---------------------------------------------


def disposable_login_id(label: str) -> str:
    """A unique, non-deliverable email for one disposable test user.

    `.invalid` is reserved by RFC 2606 for addresses guaranteed not to
    resolve -- appropriate for a synthetic account that must never receive
    real mail and must never collide with a real account.
    """
    suffix = uuid.uuid4().hex[:12]
    return f"verify-identity-{label}-{suffix}@juval-identity-verification.invalid"


def compliant_password(unique: str) -> str:
    """Satisfies every configured rule: length>=12, mixed case, digit, special."""
    return f"Vvz9!{unique}Qx"


def _tag(case_id: str) -> dict:
    return {
        "juval_identity_verification": True,
        "createdBy": "tools/verify_identity_behavior.py",
        "case": case_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }


# --- FusionAuth client ---------------------------------------------------


class Client:
    """Minimal FusionAuth API client. Prints no secret. Never issues DELETE."""

    def __init__(self, base: str, api_key: str, tenant_id: str) -> None:
        self._base = base.rstrip("/")
        self._api_key = api_key
        self._tenant_id = tenant_id

    def request(self, method: str, path: str, body: Optional[dict] = None, *, scope_tenant: bool = True) -> tuple[int, dict]:
        if method == "DELETE":
            raise IdentityVerificationError(
                "this tool never issues DELETE -- see the module docstring's cleanup strategy"
            )
        url = f"{self._base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", self._api_key)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if scope_tenant:
            request.add_header("X-FusionAuth-TenantId", self._tenant_id)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, (json.loads(raw) if raw else {})
            except json.JSONDecodeError:
                return exc.code, {}
        except (urllib.error.URLError, TimeoutError) as exc:
            raise IdentityVerificationError(f"{method} {path} -> {type(exc).__name__}: {exc}") from exc


def verify_targeting(client: Client, tenant_id: str, application_id: str) -> None:
    """Fail closed: refuse anything but the confirmed JUVAl tenant/application.

    Deliberately uses only `GET /api/application/{id}` (an endpoint this
    tool needs regardless) rather than also requiring a `/api/tenant` read
    permission on this key -- the application's own `tenantId` field is
    sufficient proof, and requesting a tenant-read permission the tool does
    not otherwise need would widen the ACL for no reason.
    """
    status, body = client.request("GET", f"/api/application/{application_id}")
    application = body.get("application", {})
    if (
        status != 200
        or application.get("name") != APPLICATION_NAME
        or application.get("tenantId") != tenant_id
    ):
        raise IdentityVerificationError(
            f"application {application_id} did not resolve to {APPLICATION_NAME!r} under "
            f"tenant {tenant_id} (status={status}, name={application.get('name')!r}, "
            f"tenantId={application.get('tenantId')!r}) -- refusing to proceed. This tool "
            "never operates against the Default tenant or an unconfirmed application."
        )


# --- User/registration helpers -------------------------------------------


def create_disposable_user(
    client: Client, *, case_id: str, password: str, first_name: str = DISPOSABLE_FIRST_NAME, last_name: str = DISPOSABLE_LAST_NAME
) -> tuple[int, dict]:
    """POST /api/user (OpenAPI 1.69.0: createUser). Returns (status, body)."""
    login_id = disposable_login_id(case_id)
    body = {
        "user": {
            "email": login_id,
            "username": login_id,
            "password": password,
            "firstName": first_name,
            "lastName": last_name,
            "data": _tag(case_id),
        }
    }
    return client.request("POST", "/api/user", body)


def register_to_application(client: Client, *, user_id: str, application_id: str, roles: list[str]) -> tuple[int, dict]:
    """POST /api/user/registration/{userId} (OpenAPI 1.69.0: registerWithId)."""
    body = {"registration": {"applicationId": application_id, "roles": roles}}
    return client.request("POST", f"/api/user/registration/{user_id}", body)


def login(client: Client, *, login_id: str, password: str, application_id: str) -> tuple[int, dict]:
    """POST /api/login (OpenAPI 1.69.0: loginWithId)."""
    body = {"loginId": login_id, "password": password, "applicationId": application_id}
    return client.request("POST", "/api/login", body)


def enroll_totp(client: Client, *, user_id: str, secret: str) -> tuple[int, dict]:
    """POST /api/user/two-factor/{userId} (OpenAPI 1.69.0: enableTwoFactorWithId)."""
    code = totp_code(secret)
    body = {"method": "authenticator", "secret": secret, "code": code}
    return client.request("POST", f"/api/user/two-factor/{user_id}", body)


def complete_two_factor_login(client: Client, *, two_factor_id: str, code: str) -> tuple[int, dict]:
    """POST /api/two-factor/login (OpenAPI 1.69.0: twoFactorLoginWithId)."""
    body = {"twoFactorId": two_factor_id, "code": code}
    return client.request("POST", "/api/two-factor/login", body, scope_tenant=False)


def read_lockout_state(client: Client, *, user_id: str) -> tuple[int, dict]:
    """GET /api/user/action?userId=&preventingLogin=true (OpenAPI 1.69.0: retrieveUserActioning).

    NOT `GET /api/user/{userId}` -- the User schema carries no lockout
    field. Lockout is represented as an active `UserActionLog` (the applied
    instance of `FailedAuthenticationConfiguration.userActionId`), and this
    is the endpoint that filters to just the ones currently blocking login.
    `UserActionLog.expiry` is the unlock timestamp.
    """
    return client.request(
        "GET", f"/api/user/action?userId={user_id}&preventingLogin=true", scope_tenant=False
    )


# --- Test groups -----------------------------------------------------------


def run_password_tests(client: Client) -> list[Finding]:
    findings: list[Finding] = []

    cases = [
        ("P-01", "valid compliant password accepted", compliant_password(uuid.uuid4().hex[:6]), True),
        ("P-02", "shorter than configured minimum (12) rejected", "Vz9!Qx", False),
        ("P-03", "missing mixed case (all lowercase) rejected", "vvzz9!qxqxqxqx", False),
        ("P-04", "missing mixed case (all uppercase) rejected", "VVZZ9!QXQXQXQX", False),
        ("P-05", "missing digit rejected", "VvzzQx!QxQxQxQx", False),
        ("P-06", "missing special character rejected", "VvzzQx9QxQxQxQx", False),
    ]
    for case_id, label, password, expect_accept in cases:
        status, body = create_disposable_user(client, case_id=case_id, password=password)
        accepted = status == 200
        if accepted == expect_accept:
            findings.append(Finding(case_id, Status.PASS, f"{label}: status={status} (as expected)"))
        else:
            field_errors = sorted((body.get("fieldErrors") or {}).keys())
            findings.append(
                Finding(
                    case_id,
                    Status.FAIL,
                    f"{label}: status={status}, expected accept={expect_accept}, "
                    f"fieldErrors keys={field_errors}",
                )
            )

    findings.append(
        Finding(
            "P-07",
            Status.NOT_TESTED,
            "minimum/maximum password age (controls 8, 9) is READ-BACK VERIFIED "
            "(§38) but not behaviorally testable in a single pass: minimumPasswordAge="
            "86400s means a same-day repeat change cannot demonstrate the rejection "
            "without waiting a full day. Would need POST /api/user/forgot-password + "
            "POST /api/user/change-password/{id}, both outside this tool's ACL.",
        )
    )
    findings.append(
        Finding(
            "P-08",
            Status.NOT_TESTED,
            "password history (control 7) needs at least one prior password change on "
            "the same user to test reuse-rejection, which needs the self-service "
            "change-password flow (POST /api/user/forgot-password + POST /api/user/"
            "change-password/{id}) -- outside this tool's ACL, not invented as evidence.",
        )
    )
    return findings


def run_mfa_enforcement_observation(client: Client, application_id: str) -> list[Finding]:
    """M-01: what a never-enrolled user's login looks like under loginPolicy=Required.

    Deliberately observational, not a fixed assertion -- FusionAuth's exact
    behavior for an un-enrolled user under a Required tenant MFA policy is
    not something the OpenAPI spec encodes, and this tool does not invent
    evidence for behavior it has not actually observed running live.
    """
    password = compliant_password(uuid.uuid4().hex[:6])
    status, body = create_disposable_user(client, case_id="M-01", password=password)
    if status != 200:
        return [Finding("M-01", Status.BLOCKED, f"disposable user creation failed: status={status}")]
    user_id = body["user"]["id"]
    login_id = body["user"]["email"]

    reg_status, _ = register_to_application(client, user_id=user_id, application_id=application_id, roles=["viewer"])
    if reg_status != 200:
        return [Finding("M-01", Status.BLOCKED, f"application registration failed: status={reg_status}")]

    status, body = login(client, login_id=login_id, password=password, application_id=application_id)
    has_two_factor_id = "twoFactorId" in body
    return [
        Finding(
            "M-01",
            Status.PASS,
            f"tenant MFA enforcement observed for a never-enrolled user: login status={status}, "
            f"twoFactorId present={has_two_factor_id} -- recorded as evidence of actual behavior, "
            "not asserted a priori. A 242/twoFactorId response would mean FusionAuth forces "
            "enrollment at login; a 200 would mean an un-enrolled account can still complete "
            "login despite loginPolicy=Required, which would itself be a compliance-relevant "
            "finding about the strength of tenant-wide MFA enforcement.",
        )
    ]


def run_lockout_and_mfa_sequence(client: Client, application_id: str, *, too_many_attempts: int) -> list[Finding]:
    findings: list[Finding] = []
    password = compliant_password(uuid.uuid4().hex[:6])
    wrong_password = password + "-wrong"

    status, body = create_disposable_user(client, case_id="lockout-mfa", password=password)
    if status != 200:
        return [Finding("L/M-setup", Status.BLOCKED, f"disposable user creation failed: status={status}")]
    user_id = body["user"]["id"]
    login_id = body["user"]["email"]

    reg_status, _ = register_to_application(client, user_id=user_id, application_id=application_id, roles=["viewer"])
    if reg_status != 200:
        return [Finding("L/M-setup", Status.BLOCKED, f"application registration failed: status={reg_status}")]

    secret = random_totp_secret()
    status, body = enroll_totp(client, user_id=user_id, secret=secret)
    if status != 200:
        findings.append(Finding("M-02/M-03", Status.FAIL, f"TOTP enrollment failed: status={status}"))
        return findings
    findings.append(Finding("M-02", Status.PASS, "TOTP secret generated locally (no FusionAuth call needed)"))
    findings.append(Finding("M-03", Status.PASS, f"TOTP enrolled on disposable user: status={status}"))

    # M-04 / L-01: correct password before any failures -> MFA challenge, not final success.
    status, body = login(client, login_id=login_id, password=password, application_id=application_id)
    two_factor_id = body.get("twoFactorId")
    if status == 242 and two_factor_id:
        findings.append(
            Finding("M-04", Status.PASS, f"correct password -> status=242, twoFactorId present (not a final token)")
        )
        findings.append(Finding("L-01", Status.PASS, "valid login accepted (pre-lockout, pre-2FA-completion)"))
    else:
        findings.append(
            Finding("M-04", Status.FAIL, f"expected 242+twoFactorId for a correct password, got status={status}")
        )
        findings.append(Finding("L-01", Status.FAIL, f"correct password did not yield the expected pre-2FA success signal (status={status})"))
    # M-05 / M-06 / M-07: the second-factor challenge.
    #
    # POST /api/two-factor/login is a SEVENTH endpoint, outside the approved
    # six-permission ACL. FusionAuth answers a bad TOTP code with 404; a 401/403
    # means the key was refused before the MFA check ever ran. Scoring such a
    # response as "not 200, therefore the wrong code was rejected" would launder
    # an authorization failure into behavioral evidence -- the exact error this
    # investigation exists to avoid. See SP_API_REGISTRATION_REMEDIATION.md §47.
    UNAUTHORIZED = (401, 403)
    two_factor_unauthorized = False

    if not two_factor_id:
        findings.append(Finding("M-05", Status.BLOCKED, "no twoFactorId from M-04 to challenge"))
        findings.append(Finding("M-06", Status.BLOCKED, "no twoFactorId from M-04 to challenge"))
        findings.append(Finding("M-07", Status.NOT_TESTED, "depends on M-06"))
    else:
        status, _ = complete_two_factor_login(
            client, two_factor_id=two_factor_id, code=wrong_totp_code(secret)
        )
        if status in UNAUTHORIZED:
            two_factor_unauthorized = True
            findings.append(
                Finding(
                    "M-05",
                    Status.BLOCKED,
                    f"status={status} on POST /api/two-factor/login -- rejected before the "
                    "MFA check; this is not evidence about TOTP validation",
                )
            )
        else:
            findings.append(
                Finding(
                    "M-05",
                    Status.PASS if status != 200 else Status.FAIL,
                    f"invalid TOTP code -> status={status} (expected not 200)",
                )
            )

        if two_factor_unauthorized:
            findings.append(
                Finding(
                    "M-06",
                    Status.BLOCKED,
                    "POST /api/two-factor/login is not authorized for this key",
                )
            )
            findings.append(
                Finding(
                    "M-07",
                    Status.BLOCKED,
                    "token issuance could not be observed: the second-factor call was "
                    "rejected at the authorization layer",
                )
            )
        else:
            status, body = login(
                client, login_id=login_id, password=password, application_id=application_id
            )
            two_factor_id_2 = body.get("twoFactorId")
            if not two_factor_id_2:
                findings.append(Finding("M-06", Status.BLOCKED, "could not obtain a second twoFactorId to test the correct code"))
                findings.append(Finding("M-07", Status.NOT_TESTED, "depends on M-06"))
            else:
                status, body = complete_two_factor_login(
                    client, two_factor_id=two_factor_id_2, code=totp_code(secret)
                )
                token_issued = "token" in body
                if status in UNAUTHORIZED:
                    findings.append(
                        Finding(
                            "M-06",
                            Status.BLOCKED,
                            f"status={status} on POST /api/two-factor/login -- rejected "
                            "before the MFA check; not evidence about TOTP validation",
                        )
                    )
                    findings.append(
                        Finding(
                            "M-07",
                            Status.BLOCKED,
                            "token issuance could not be observed: the second-factor call "
                            "was rejected at the authorization layer",
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            "M-06",
                            Status.PASS if status == 200 and token_issued else Status.FAIL,
                            f"valid TOTP code -> status={status}, token issued={token_issued}",
                        )
                    )
                    findings.append(
                        Finding(
                            "M-07",
                            Status.PASS if token_issued else Status.FAIL,
                            "token was issued only after the second factor completed, not at the first /api/login call",
                        )
                    )

    # L-02: wrong password, (threshold - 1) times -> not yet locked.
    for _ in range(too_many_attempts - 1):
        login(client, login_id=login_id, password=wrong_password, application_id=application_id)
    status, body = read_lockout_state(client, user_id=user_id)
    actions = body.get("actions", []) if status == 200 else None
    if status == 200 and not actions:
        findings.append(Finding("L-02", Status.PASS, f"{too_many_attempts - 1} failed attempts, not yet locked (0 blocking actions)"))
    else:
        findings.append(Finding("L-02", Status.FAIL, f"expected 0 blocking actions after {too_many_attempts - 1} failures, got status={status} actions={len(actions) if actions is not None else 'n/a'}"))

    # L-03: one more wrong attempt hits the threshold -> locked.
    login(client, login_id=login_id, password=wrong_password, application_id=application_id)
    status, body = read_lockout_state(client, user_id=user_id)
    actions = body.get("actions", []) if status == 200 else None
    if status == 200 and actions:
        expiry = actions[0].get("expiry")
        findings.append(Finding("L-03", Status.PASS, f"lockout triggered at the {too_many_attempts}th failure: 1 blocking action present"))
        findings.append(Finding("L-05", Status.PASS, f"lock read back: expiry={'present' if expiry else 'absent'} (unlock timestamp)"))
    else:
        findings.append(Finding("L-03", Status.FAIL, f"expected a blocking action at the {too_many_attempts}th failure, got status={status} actions={len(actions) if actions is not None else 'n/a'}"))
        findings.append(Finding("L-05", Status.BLOCKED, "no lock present to read back"))

    # L-04: correct credentials while locked must NOT bypass the lock.
    status, body = login(client, login_id=login_id, password=password, application_id=application_id)
    if status in (401, 403):
        # Rejected before the credential was ever evaluated. FusionAuth answers
        # a bad credential with 404, not 401, so a 401 here is the API key
        # lacking POST /api/login -- it is not evidence that the lock held.
        findings.append(
            Finding(
                "L-04",
                Status.BLOCKED,
                f"status={status} on POST /api/login -- rejected at the authorization "
                "layer, before any credential check; this is not evidence about lockout",
            )
        )
    elif status not in (200, 242):
        findings.append(Finding("L-04", Status.PASS, f"correct password while locked -> status={status} (not 200/242, lockout held)"))
    else:
        findings.append(Finding("L-04", Status.FAIL, f"correct password while locked -> status={status}, lockout did NOT hold"))

    findings.append(
        Finding(
            "L-unlock-duration",
            Status.NOT_TESTED,
            "unlock-after-duration is READ-BACK CONFIGURED (actionDuration=30 minutes, "
            "§38.3) but deliberately NOT waited out in this pass -- would require a "
            "30-minute idle wait solely to manufacture evidence, which this tool refuses "
            "to do. L-05's expiry timestamp is the configuration-backed read-back instead.",
        )
    )
    return findings


def run_control6_tests(client: Client) -> list[Finding]:
    """C6-01/C6-02: does native FusionAuth reject a password containing the
    user's firstName/lastName? Expected to demonstrate the gap, not close
    it -- Control 6 stays B/PARTIALLY_SATISFIED regardless of the outcome
    (ADR-021: FusionAuth >=1.63 rejects only the login identifier, not
    firstName/lastName). This tool never modifies FusionAuth to force a
    different result.
    """
    findings: list[Finding] = []
    cases = [
        ("C6-01", "password contains full firstName", CONTROL6_FIRST_NAME, CONTROL6_LAST_NAME, CONTROL6_FIRST_NAME),
        ("C6-02", "password contains full lastName", CONTROL6_FIRST_NAME, CONTROL6_LAST_NAME, CONTROL6_LAST_NAME),
    ]
    for case_id, label, first_name, last_name, name_component in cases:
        password = f"{name_component}9!Qx"  # satisfies length/case/digit/special; isolates the name variable
        status, _ = create_disposable_user(
            client, case_id=case_id, password=password, first_name=first_name, last_name=last_name
        )
        accepted = status == 200
        findings.append(
            Finding(
                case_id,
                Status.PASS,  # the check itself always succeeds at producing evidence
                f"{label}: creation status={status} ({'accepted' if accepted else 'rejected'}). "
                "Classification stays PARTIALLY_SATISFIED/B regardless: FusionAuth's native "
                "check (ADR-021) only rejects the login identifier, never firstName/lastName -- "
                "this result is behavioral evidence of that gap, not a control closure.",
            )
        )
    return findings


# --- Orchestration -----------------------------------------------------


def run_all(client: Client, application_id: str, *, too_many_attempts: int) -> list[Finding]:
    findings: list[Finding] = []
    findings += run_password_tests(client)
    findings += run_mfa_enforcement_observation(client, application_id)
    findings += run_lockout_and_mfa_sequence(client, application_id, too_many_attempts=too_many_attempts)
    findings += run_control6_tests(client)
    return findings


def render(findings: list[Finding]) -> str:
    width = max((len(f.case_id) for f in findings), default=0)
    lines = [f"{f.status.value:<11} {f.case_id:<{width}}  {f.detail}" for f in findings]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=os.environ.get("JUVAL_IDP_BASE", "http://127.0.0.1:9011"))
    parser.add_argument("--execute", action="store_true", help="perform live writes (needs the confirmation env var too)")
    parser.add_argument("--dry-run", action="store_true", help="print the planned sequence and exit (default)")
    parser.add_argument("--too-many-attempts", type=int, default=int(os.environ.get("JUVAL_IDP_TOO_MANY_ATTEMPTS", "10")))
    args = parser.parse_args()

    api_key = os.environ.get("JUVAL_IDP_API_KEY")
    tenant_id = os.environ.get("JUVAL_IDP_TENANT_ID")
    application_id = os.environ.get("JUVAL_IDP_APPLICATION_ID")
    confirm = os.environ.get("JUVAL_IDENTITY_VERIFICATION_CONFIRM")

    if not api_key:
        print("JUVAL_IDP_API_KEY is not set.", file=sys.stderr)
        return 2
    if not tenant_id or not application_id:
        print("JUVAL_IDP_TENANT_ID and JUVAL_IDP_APPLICATION_ID are both required -- "
              "there is no default; this tool refuses to guess a tenant/application.", file=sys.stderr)
        return 2

    live = args.execute and not args.dry_run
    if live and confirm != "yes-run-live-writes":
        print("--execute requires JUVAL_IDENTITY_VERIFICATION_CONFIRM=yes-run-live-writes "
              "in the environment as a second, explicit gate.", file=sys.stderr)
        return 2

    if not live:
        print("DRY RUN -- no network calls will be made. Planned sequence:")
        print("  1. verify_targeting()            GET  /api/application/{id}")
        print("  2. run_password_tests()          POST /api/user  (P-01..P-06)")
        print("  3. run_mfa_enforcement_observation()  POST /api/user, POST /api/user/registration, POST /api/login  (M-01)")
        print("  4. run_lockout_and_mfa_sequence() POST /api/user, POST /api/user/registration,")
        print("                                    POST /api/user/two-factor/{id}, POST /api/login,")
        print("                                    POST /api/two-factor/login, GET /api/user/action  (M-02..M-07, L-01..L-05)")
        print("  5. run_control6_tests()          POST /api/user  (C6-01, C6-02)")
        print(f"  target tenant:      {tenant_id}")
        print(f"  target application: {application_id}")
        print("Pass --execute with JUVAL_IDENTITY_VERIFICATION_CONFIRM=yes-run-live-writes to run for real.")
        return 0

    client = Client(args.base, api_key, tenant_id)
    try:
        verify_targeting(client, tenant_id, application_id)
    except IdentityVerificationError as exc:
        print(f"FAILED preflight: {exc}", file=sys.stderr)
        return 1

    findings = run_all(client, application_id, too_many_attempts=args.too_many_attempts)
    print(render(findings))
    print()
    print("No password, TOTP secret/code, or token value was printed by this tool.")
    return 1 if any(f.status == Status.FAIL for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
