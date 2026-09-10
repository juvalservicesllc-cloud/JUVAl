"""OIDC token validation and RBAC for the Juval API.

Closes the *backend half* of Amazon finding RF-03 (authentication controls)
and all of RF-04 (job-function / least-privilege access). The *IdP half* of
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

import logging
import os
from dataclasses import dataclass
from typing import Callable, FrozenSet, Optional, Protocol

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
_JWKS_CACHE_LIFESPAN_SECONDS = 300   # re-fetch the key set at least this often
_JWKS_MAX_CACHED_KEYS = 16           # bounded: a hostile `kid` cannot grow it
_JWKS_HTTP_TIMEOUT_SECONDS = 10      # never hang a request on a stalled IdP


@dataclass(frozen=True)
class Principal:
    """An authenticated caller and what it is allowed to do."""

    subject: str
    roles: tuple[str, ...]
    permissions: FrozenSet[str]

    def has(self, permission: str) -> bool:
        return permission in self.permissions


# The principal used when authentication is disabled (local development and
# the existing test suite). It is never produced while JUVAL_AUTH_MODE=oidc.
_ANONYMOUS = Principal(subject="anonymous", roles=(), permissions=ALL_PERMISSIONS)


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

        return Principal(subject=str(claims["sub"]), roles=tuple(roles), permissions=permissions)


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


def auth_mode() -> str:
    """"disabled" (default) or "oidc". Any other value is a fail-fast error."""
    mode = os.environ.get("JUVAL_AUTH_MODE", "disabled")
    if mode not in ("disabled", "oidc"):
        raise RuntimeError(
            f"JUVAL_AUTH_MODE has an unrecognized value: {mode!r} (expected 'disabled' or 'oidc')"
        )
    return mode


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"JUVAL_AUTH_MODE=oidc requires {name} to be set")
    return value


def build_verifier() -> Optional[TokenVerifier]:
    """Build the verifier from the environment, or None when auth is disabled.

    Missing configuration in oidc mode is a startup error, never a silent
    downgrade to unauthenticated access.
    """
    if auth_mode() == "disabled":
        return None

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
    jwks_uri = os.environ.get("JUVAL_OIDC_JWKS_URI") or f"{issuer.rstrip('/')}/.well-known/jwks.json"
    roles_claim = os.environ.get("JUVAL_OIDC_ROLES_CLAIM", "roles")

    jwk_client = jwt.PyJWKClient(
        jwks_uri,
        cache_keys=True,
        max_cached_keys=_JWKS_MAX_CACHED_KEYS,
        cache_jwk_set=True,
        lifespan=_JWKS_CACHE_LIFESPAN_SECONDS,
        timeout=_JWKS_HTTP_TIMEOUT_SECONDS,
    )

    def resolve(token: str) -> object:
        return jwk_client.get_signing_key_from_jwt(token).key

    return TokenVerifier(issuer=issuer, audience=audience, key_resolver=resolve, roles_claim=roles_claim)


# Resolved once at import. Tests and the composition root may override it via
# `set_verifier`, which is also what keeps this module free of import-time
# network access when auth is disabled.
_verifier: Optional[TokenVerifier] = None
_configured = False


def set_verifier(verifier: Optional[TokenVerifier]) -> None:
    """Install (or clear) the process-wide verifier."""
    global _verifier, _configured
    _verifier = verifier
    _configured = True


def current_verifier() -> Optional[TokenVerifier]:
    global _configured
    if not _configured:
        set_verifier(build_verifier())
    return _verifier


def reset_for_tests() -> None:
    """Forget the cached verifier so the next call re-reads the environment."""
    global _verifier, _configured
    _verifier = None
    _configured = False


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
    verifier = current_verifier()
    if verifier is None:
        return _ANONYMOUS

    if _session_resolver is not None:
        principal = _session_resolver(request)
        if principal is not None:
            return principal

    return verifier.verify(_bearer_token(request))


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
