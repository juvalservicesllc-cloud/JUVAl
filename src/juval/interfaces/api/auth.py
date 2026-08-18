"""OIDC token validation and RBAC for the Juval API.

Closes the *backend half* of Amazon finding RF-03 (authentication controls)
and all of RF-04 (job-function / least-privilege access). The *IdP half* of
RF-03 -- password composition, history, minimum/maximum age, MFA, lockout --
is owned by the managed Identity Provider (ADR-022) and is deliberately not
implemented here: JUVAl never stores a password, a password hash, or performs
any authentication cryptography of its own (CLAUDE.md Sec. 16, ADR-021
control-ownership matrix).

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
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.InvalidTokenError as exc:
            # Deliberately generic to the caller (no oracle about *why* the
            # token failed); the specific reason stays in the server log.
            logger.warning("token rejected: %s", type(exc).__name__)
            raise HTTPException(status_code=401, detail="invalid or expired token") from exc
        except Exception as exc:  # key retrieval failure (JWKS unreachable, etc.)
            logger.warning("token key resolution failed: %s", type(exc).__name__)
            raise HTTPException(status_code=401, detail="invalid or expired token") from exc

        roles = _roles_from_claims(claims, self._roles_claim)
        permissions: FrozenSet[str] = frozenset().union(
            *(ROLE_PERMISSIONS.get(role, frozenset()) for role in roles)
        ) if roles else frozenset()

        return Principal(subject=str(claims["sub"]), roles=tuple(roles), permissions=permissions)


def _roles_from_claims(claims: dict, roles_claim: str) -> list[str]:
    """Read the roles claim, tolerating the two shapes IdPs actually emit.

    Okta groups arrive as a JSON array; some providers emit a space-separated
    string. Anything else yields no roles -- which means no permissions, not
    full access.
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
    jwks_uri = os.environ.get("JUVAL_OIDC_JWKS_URI") or f"{issuer.rstrip('/')}/v1/keys"
    roles_claim = os.environ.get("JUVAL_OIDC_ROLES_CLAIM", "roles")

    jwk_client = jwt.PyJWKClient(jwks_uri)

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


def current_principal(request: Request) -> Principal:
    """Resolve the caller. Raises 401 when auth is enabled and the token fails."""
    verifier = current_verifier()
    if verifier is None:
        return _ANONYMOUS
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
