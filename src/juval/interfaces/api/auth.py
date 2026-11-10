"""OIDC token validation and RBAC for the Juval API.

Closes the *backend half* of Amazon finding RF-03 (authentication controls)
and the backend enforcement portion of RF-04 (job-function / least-privilege
access). Personnel reviews, removal drills and production activation remain
separate evidence requirements. The *IdP half* of
RF-03 -- password composition, history, minimum/maximum age, MFA, lockout --
is owned by the Identity Provider -- FusionAuth, self-hosted on `juval-server`
(ADR-028 provider, ADR-031 hosting) -- and is deliberately not implemented
here: JUVAl never stores a password, a password hash, or performs any
authentication cryptography of its own (CLAUDE.md Sec. 16, ADR-021
control-ownership matrix).

One exception, and only one: Amazon Control 6 (a password must not contain
part of the user's name) is enforced by JUVAl in `domain/password_policy.py`,
because FusionAuth 1.69.0 provably does not implement it (measured, ADR-035).
That is a validation of a value *before* it is handed to the IdP; it is still
not authentication, and no password is ever stored here.

This module is **provider-agnostic**. It validates standard OIDC/JWT claims
(issuer, signature via JWKS, audience, expiry) so that changing IdP is a
configuration change, not a rewrite.

Enforcement is server-side and fail-closed. A frontend that hides a button is
never an authorization control (RF-04); every protected endpoint resolves a
`Principal` here and checks a permission before doing any work.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from dataclasses import dataclass
from typing import Callable, FrozenSet, Optional, Protocol
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger("juval.interfaces.api.auth")

# --- Permissions ------------------------------------------------------
# Capabilities are derived from what the API actually exposes today, not
# from a speculative role hierarchy (CLAUDE.md Sec. 4/22). Add a permission
# only when an endpoint really needs it.

RUNS_CREATE = "runs:create"
RUNS_READ = "runs:read"
RUNS_EXPORT = "runs:export"

ALL_PERMISSIONS: FrozenSet[str] = frozenset({RUNS_CREATE, RUNS_READ, RUNS_EXPORT})

# Role -> permissions. Least privilege: `viewer` cannot start a run or pull an
# export; only `operator` and `admin` can. Roles arrive as an IdP claim and are
# never stored or minted by JUVAl.
ROLE_PERMISSIONS: dict[str, FrozenSet[str]] = {
    "viewer": frozenset({RUNS_READ}),
    "operator": frozenset({RUNS_READ, RUNS_CREATE, RUNS_EXPORT}),
    "admin": ALL_PERMISSIONS,
}

# Algorithms accepted when verifying a token signature. Pinned to asymmetric
# RS256 on purpose: accepting "none" or a symmetric algorithm here would allow
# the classic JWT algorithm-confusion forgery, where an attacker signs a token
# with the *public* key material and the server accepts it.
_ALLOWED_ALGORITHMS = ["RS256"]

# Claims a token must carry before it is even considered. Missing any of them
# is a rejection, not a default.
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub"]

# Clock skew tolerance, in seconds, for `exp`/`iat`/`nbf`.
#
# PyJWT defaults to zero. Zero is right when one machine issues and verifies;
# it is wrong here, where the issuer runs on `juval-server` and the verifier on
# Railway, with independent clocks and no shared NTP discipline between them. A
# few seconds of drift would surface as sporadic, unreproducible 401s. Sixty
# seconds is small enough that an expired token is not meaningfully usable and
# large enough to absorb ordinary drift; it is a deliberate number, not a
# library default.
_CLOCK_SKEW_LEEWAY_SECONDS = 60

# JWKS cache parameters, set explicitly rather than inherited.
#
# PyJWT's own defaults happen to be close to these today, but relying on a
# library default for a security-relevant cache means a dependency bump can
# change token-verification behaviour with no diff in this repository. Naming
# them makes that impossible and makes them testable.
#
# Only the whole key set is cached, never individual keys: PyJWT's per-key
# cache (`cache_keys=True`) is an LRU with no expiry, so a key the IdP retired
# -- e.g. after a compromise -- would keep verifying until a restart (SEC-01E).
# With the set cache alone, a retired key stops verifying within the lifespan.
_JWKS_CACHE_LIFESPAN_SECONDS = 300   # re-fetch the key set at least this often
_JWKS_HTTP_TIMEOUT_SECONDS = 10      # never hang a request on a stalled IdP
# An unknown `kid` forces at most one re-fetch per this many seconds, so a flood
# of forged kids cannot hammer the IdP; a newly rotated-in key may be refused
# (401, fail closed) for up to this long after the previous fetch.
_JWKS_REFRESH_COOLDOWN_SECONDS = 30


@dataclass(frozen=True)
class Principal:
    """An authenticated caller and what it is allowed to do.

    `(issuer, subject)` is the stable identity (ADR-056): `sub` is unique only
    within its issuer, and it -- never an email or a name -- is what
    organization memberships are keyed by.
    """

    subject: str
    roles: tuple[str, ...]
    permissions: FrozenSet[str]
    issuer: str

    def __post_init__(self) -> None:
        if not self.subject or not self.issuer:
            raise ValueError("a principal needs a subject and an issuer")

    def has(self, permission: str) -> bool:
        return permission in self.permissions


# The only principal that exists without a credential (ADR-055). It is returned
# solely by the loopback lab mode, and only for a request that passes
# `lab_request_allowed`; no OIDC code path can produce it.
_LAB_PRINCIPAL = Principal(subject="local-lab-unauthenticated", roles=(), permissions=ALL_PERMISSIONS,
                           issuer="urn:juval:local-lab")


class KeyResolver(Protocol):
    """Returns the public key that signed `token`.

    In production this is PyJWT's `PyJWKClient`, which fetches and caches the
    IdP's JWKS. Injecting it keeps `TokenVerifier` unit-testable with a locally
    generated key pair -- real signature verification, no network.
    """

    def __call__(self, token: str) -> object: ...


class TokenVerifier:
    """Verifies an OIDC access/ID token and maps its roles to permissions."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        key_resolver: KeyResolver,
        roles_claim: str = "roles",
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_resolver = key_resolver
        self._roles_claim = roles_claim

    @property
    def issuer(self) -> str:
        """The only issuer this verifier accepts; BFF sessions inherit it."""
        return self._issuer

    @property
    def roles_claim(self) -> str:
        """The claim read at startup; the BFF maps session roles with it too."""
        return self._roles_claim

    def verify(self, token: str) -> Principal:
        """Return the Principal for `token`, or raise HTTPException(401)."""
        try:
            key = self._key_resolver(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=_ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.InvalidTokenError as exc:
            # Deliberately generic to the caller (no oracle about *why* the
            # token failed); the specific reason stays in the server log.
            logger.warning("token rejected: %s", type(exc).__name__)
            raise _invalid_token() from exc
        except Exception as exc:  # key retrieval failure (JWKS unreachable, etc.)
            logger.warning("token key resolution failed: %s", type(exc).__name__)
            raise _invalid_token() from exc

        roles = _roles_from_claims(claims, self._roles_claim)
        permissions: FrozenSet[str] = frozenset().union(
            *(ROLE_PERMISSIONS.get(role, frozenset()) for role in roles)
        ) if roles else frozenset()

        return Principal(subject=str(claims["sub"]), roles=tuple(roles), permissions=permissions,
                         issuer=str(claims["iss"]))


def _invalid_token() -> HTTPException:
    """401 for a token that was supplied but did not verify.

    RFC 6750 Sec. 3 requires the challenge on *every* 401 from a bearer-token
    resource, not only on a missing credential: a client that gets a bare 401
    has no protocol-level way to learn it should re-authenticate. `error=` is
    the generic `invalid_token` -- naming the specific failure would turn this
    response into an oracle, and the reason is already in the server log.
    """
    return HTTPException(
        status_code=401,
        detail="invalid or expired token",
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


def _roles_from_claims(claims: dict, roles_claim: str) -> list[str]:
    """Read the roles claim, tolerating the two shapes IdPs actually emit.

    FusionAuth emits `roles` as a JSON array; some providers emit a
    space-separated string. Anything else yields no roles -- which means no
    permissions, not full access. (This tolerance predates the provider
    decision and stays: the boundary is provider-agnostic by design, and a
    provider change must remain a configuration change.)
    """
    raw = claims.get(roles_claim)
    if isinstance(raw, list):
        return [str(r) for r in raw]
    if isinstance(raw, str):
        return raw.split()
    return []


# --- Configuration ----------------------------------------------------


AUTH_MODES = ("disabled", "oidc")

#: ADR-055: the loopback lab must be asked for twice -- the mode and this
#: sentence. It is a sentence, not "true", so it is never set by accident or
#: copied from another boolean (the same pattern as bff._MEMORY_OPT_IN).
LAB_CONFIRM_ENV = "JUVAL_AUTH_DISABLED_CONFIRM"
LAB_CONFIRM_VALUE = "yes-loopback-lab-only"

# Variables a hosting platform injects into every deployment. Their presence
# means "this is not a workstation", so the lab mode refuses to start. This is
# one layer, never the only one (ADR-055): a platform not listed here is still
# stopped by the per-request loopback check.
_HOSTING_ENV_PREFIXES = ("RAILWAY_", "VERCEL")

# Headers a reverse proxy, tunnel or CDN adds. A lab request carrying any of
# them arrived through something other than a direct loopback connection.
_FORWARDING_HEADERS = (
    "forwarded",
    "via",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-real-ip",
    "cf-connecting-ip",
    "cf-ray",
    "true-client-ip",
)


def auth_mode() -> str:
    """"oidc" or "disabled". There is no default (ADR-055).

    A missing, empty or unknown value is a startup error. The value itself is
    never echoed: an operator who pasted something else into this variable
    should not see it again in a log.
    """
    mode = os.environ.get("JUVAL_AUTH_MODE")
    if mode is None or not mode.strip():
        raise RuntimeError(
            "JUVAL_AUTH_MODE must be set: 'oidc' for any deployment, or 'disabled' "
            f"only for a loopback lab together with {LAB_CONFIRM_ENV} (ADR-055). "
            "There is no default."
        )
    if mode not in AUTH_MODES:
        raise RuntimeError("JUVAL_AUTH_MODE has an unrecognized value (expected 'oidc' or 'disabled')")
    return mode


def _loopback_ip(address: object) -> bool:
    """True only for a literal loopback IP (127.0.0.0/8, ::1, IPv4-mapped)."""
    if not isinstance(address, str):
        return False
    try:
        ip = ipaddress.ip_address(address.strip("[]"))
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback


def _loopback_name(hostname: Optional[str]) -> bool:
    return hostname is not None and (hostname.lower() == "localhost" or _loopback_ip(hostname))


def _loopback_origin(origin: str) -> bool:
    if "@" in origin:  # userinfo would let the parsed hostname hide the real one
        return False
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and _loopback_name(parts.hostname)


def check_lab_environment() -> None:
    """Refuse the lab mode anywhere it could be a deployment. Raises on failure."""
    if os.environ.get(LAB_CONFIRM_ENV) != LAB_CONFIRM_VALUE:
        raise RuntimeError(
            f"JUVAL_AUTH_MODE=disabled requires {LAB_CONFIRM_ENV}={LAB_CONFIRM_VALUE}. "
            "It leaves every endpoint unauthenticated and is for a loopback lab only (ADR-055)."
        )
    if any(name.startswith(_HOSTING_ENV_PREFIXES) for name in os.environ):
        raise RuntimeError(
            "JUVAL_AUTH_MODE=disabled refused: a hosting platform variable "
            "(RAILWAY_* or VERCEL*) is present. Deployments must use oidc (ADR-055)."
        )
    origins = [o.strip() for o in os.environ.get("JUVAL_CORS_ORIGINS", "").split(",") if o.strip()]
    if any(not _loopback_origin(origin) for origin in origins):
        raise RuntimeError(
            "JUVAL_AUTH_MODE=disabled refused: JUVAL_CORS_ORIGINS lists a non-loopback "
            "origin. The lab serves loopback origins only (ADR-055)."
        )


def lab_request_allowed(request: Request) -> bool:
    """Whether a lab-mode request came straight from this machine.

    All of these must hold: the peer and the local socket address are loopback
    IPs (uvicorn takes both from the socket), no proxy/tunnel header is
    present, the Host names a loopback address (this also defeats DNS
    rebinding), and any Origin is a loopback origin (a public web page cannot
    drive the lab from the operator's browser).

    This is not a proof of privacy: a process on this machine that relays
    traffic, rewrites Host and strips every forwarding header is
    indistinguishable from a local client. That case is excluded by policy
    (ADR-055), not detected.
    """
    client = request.scope.get("client")
    server = request.scope.get("server")
    if not client or not server or not (_loopback_ip(client[0]) and _loopback_ip(server[0])):
        return False
    headers = request.headers
    if any(name in headers for name in _FORWARDING_HEADERS):
        return False
    host = headers.get("host")
    if host is None or "@" in host or not _loopback_name(urlsplit(f"//{host}").hostname):
        return False
    origin = headers.get("origin")
    return origin is None or _loopback_origin(origin)


@dataclass(frozen=True)
class AuthSettings:
    """The authentication state of one running application. Immutable.

    Resolved once at startup and installed on `app.state`; nothing reads the
    environment again to decide who may do what. The constructor enforces the
    one invariant that matters: OIDC always has a verifier, and the lab never
    has one, so "no verifier" can never be read as "no authentication".
    """

    mode: str
    verifier: Optional["TokenVerifier"] = None

    def __post_init__(self) -> None:
        if self.mode not in AUTH_MODES:
            raise ValueError("unknown authentication mode")
        if self.mode == "oidc" and self.verifier is None:
            raise ValueError("oidc mode requires a token verifier")
        if self.mode == "disabled" and self.verifier is not None:
            raise ValueError("the lab mode must not carry a token verifier")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"JUVAL_AUTH_MODE=oidc requires {name} to be set")
    return value


def build_verifier() -> TokenVerifier:
    """Build the OIDC verifier from the environment.

    Missing configuration is a startup error, never a silent downgrade to
    unauthenticated access. Constructing it does not contact the IdP: the JWKS
    is fetched on the first verification.
    """
    issuer = _required_env("JUVAL_OIDC_ISSUER")
    audience = _required_env("JUVAL_OIDC_AUDIENCE")
    # The fallback is the OpenID Provider Metadata convention
    # (`<issuer>/.well-known/jwks.json`, OpenID Connect Discovery 1.0 §4), not
    # any one vendor's path. It previously defaulted to Okta's `/v1/keys`,
    # written while ADR-022 was the plan; Okta was rejected (ADR-022
    # RECHAZADA/SUPERSEDED, 2026-08-19) and the approved direction is now
    # FusionAuth (ADR-028), which publishes `/.well-known/jwks.json`. A
    # vendor-shaped default in a provider-agnostic boundary is a trap: it
    # fails only at the first real token verification, as a 401, long after
    # startup succeeded. `JUVAL_OIDC_JWKS_URI` remains the explicit override
    # for any provider that deviates from the convention.
    return jwks_verifier(
        issuer,
        audience,
        os.environ.get("JUVAL_OIDC_JWKS_URI") or default_jwks_uri(issuer),
        os.environ.get("JUVAL_OIDC_ROLES_CLAIM", "roles"),
    )


def default_jwks_uri(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


def jwks_verifier(issuer: str, audience: str, jwks_uri: str, roles_claim: str = "roles") -> TokenVerifier:
    """The production verifier: RS256 keys from `jwks_uri`, pinned cache settings.

    `tools/verify_oidc.py` uses this same function, so pre-activation evidence
    exercises exactly the code path the API runs.
    """
    jwk_client = jwt.PyJWKClient(
        jwks_uri,
        cache_keys=False,
        cache_jwk_set=True,
        lifespan=_JWKS_CACHE_LIFESPAN_SECONDS,
        timeout=_JWKS_HTTP_TIMEOUT_SECONDS,
        cooldown_duration=_JWKS_REFRESH_COOLDOWN_SECONDS,
    )

    def resolve(token: str) -> object:
        return jwk_client.get_signing_key_from_jwt(token).key

    return TokenVerifier(issuer=issuer, audience=audience, key_resolver=resolve, roles_claim=roles_claim)


# A verifier supplied *before* startup instead of the one built from the
# environment (tests use a local key pair). It only replaces how the OIDC
# verifier is built; clearing it with None means "build from the environment",
# never "no authentication" -- the mode alone decides that.
_verifier_override: Optional[TokenVerifier] = None


def set_verifier(verifier: Optional[TokenVerifier]) -> None:
    """Use `verifier` for OIDC at the next startup (None: build from the environment)."""
    global _verifier_override
    _verifier_override = verifier


def reset_for_tests() -> None:
    """Drop a verifier installed with `set_verifier`."""
    set_verifier(None)


def resolve_settings() -> AuthSettings:
    """Read and validate the authentication configuration. Called at startup.

    Every failure raises, so a misconfigured process does not start: no mode,
    an unknown mode, an unconfirmed or hosted lab, or incomplete OIDC.
    """
    mode = auth_mode()
    if mode == "disabled":
        check_lab_environment()
        return AuthSettings(mode="disabled")
    verifier = _verifier_override if _verifier_override is not None else build_verifier()
    return AuthSettings(mode="oidc", verifier=verifier)


_STATE_ATTRIBUTE = "juval_auth"


def install(app, settings: AuthSettings) -> None:
    """Bind `settings` to `app` for the life of this instance. Never replaces."""
    if not isinstance(settings, AuthSettings):
        raise TypeError("install() requires AuthSettings")
    if getattr(app.state, _STATE_ATTRIBUTE, None) is not None:
        raise RuntimeError("authentication is already installed; a running instance cannot change mode")
    setattr(app.state, _STATE_ATTRIBUTE, settings)


def uninstall(app) -> None:
    """Remove the binding when the instance shuts down (lifespan) or a test ends."""
    if getattr(app.state, _STATE_ATTRIBUTE, None) is not None:
        delattr(app.state, _STATE_ATTRIBUTE)


def installed_settings(app) -> AuthSettings:
    """The settings of a started instance; 503 if it was never started."""
    settings = getattr(app.state, _STATE_ATTRIBUTE, None)
    if not isinstance(settings, AuthSettings):
        logger.error("request reached the API before authentication was initialised")
        raise HTTPException(status_code=503, detail="authentication is not initialised")
    return settings


def api_docs_allowed(request: Request) -> bool:
    """/docs, /redoc and /openapi.json: loopback lab only, never under OIDC."""
    settings = getattr(request.app.state, _STATE_ATTRIBUTE, None)
    return isinstance(settings, AuthSettings) and settings.mode == "disabled" and lab_request_allowed(request)


# --- FastAPI wiring ---------------------------------------------------


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header:
        raise HTTPException(
            status_code=401,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


# A resolver installed by `bff.py` that turns a session cookie into a
# Principal. Kept as a hook rather than an import so this module stays free of
# any dependency on the BFF: `auth.py` is also what a non-browser client (the
# test suite, a service caller) goes through, and that path must keep working
# with no session machinery loaded at all.
SessionResolver = Callable[[Request], Optional[Principal]]
_session_resolver: Optional[SessionResolver] = None


def set_session_resolver(resolver: Optional[SessionResolver]) -> None:
    global _session_resolver
    _session_resolver = resolver


def current_principal(request: Request) -> Principal:
    """Resolve the caller. Raises 401 when auth is enabled and nothing verifies.

    Order is deliberate: **session cookie first, bearer token second.**

    The browser is the BFF's client and never holds a bearer token (ADR-034),
    so for it the cookie is the only credential. Trying the cookie first also
    means a stale `Authorization` header left on a browser request cannot
    shadow a valid session. A caller with neither gets the bearer challenge,
    which is the correct hint for the only kind of client that could supply
    one.
    """
    settings = installed_settings(request.app)
    if settings.mode == "disabled":
        if not lab_request_allowed(request):
            logger.warning("lab mode refused a request that was not a direct loopback request")
            raise HTTPException(
                status_code=403,
                detail="unauthenticated lab mode accepts direct loopback requests only",
            )
        return _LAB_PRINCIPAL

    if _session_resolver is not None:
        principal = _session_resolver(request)
        if principal is not None:
            return principal

    return settings.verifier.verify(_bearer_token(request))


def require(permission: str) -> Callable[[Principal], Principal]:
    """FastAPI dependency enforcing one permission, server-side."""

    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.has(permission):
            logger.warning(
                "authorization denied: subject=%s permission=%s roles=%s",
                principal.subject,
                permission,
                ",".join(principal.roles) or "-",
            )
            raise HTTPException(status_code=403, detail="insufficient permissions")
        return principal

    return dependency
