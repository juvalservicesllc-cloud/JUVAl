"""Backend-for-Frontend: the browser's half of OIDC, kept on the server.

ADR-034. The PWA never holds an access token, a refresh token, a PKCE
verifier, an OAuth `state`, a `twoFactorId` or a `changePasswordId`. It holds
one opaque session id in an `HttpOnly` cookie. Everything else lives in
`application/session_store.py` behind this module.

    browser  --Secure HttpOnly cookie-->  JUVAl BFF  --code+PKCE-->  FusionAuth
                                              |                          |
                                              +<-------- JWT/JWKS -------+
                                              v
                                        Principal -> RBAC (auth.py)

Why a BFF and not a public SPA client
-------------------------------------
FusionAuth ships a Hosted Backend that would do this, but it requires the app
and FusionAuth to share a domain; JUVAl is Vercel + Railway + a tunnelled
issuer, three origins, so it is unusable (measured in the research pass). The
alternative -- a public SPA client holding tokens in browser memory -- puts
refresh tokens within reach of any XSS in a UI that is under active redesign
(ADR-023/029/030). RFC 9700 Sec. 4.9.3 says access tokens are secrets. So they
stay on the server. ADR-034 rejects SPA bearer custody explicitly.

What this module deliberately does NOT do
-----------------------------------------
No password is read, set, or proxied here, and no FusionAuth administrative
endpoint is reachable through it. Password provisioning is a separate,
narrower surface (`application/password_provisioning.py`, ADR-035) and is not
wired to HTTP at all.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from juval.application.session_store import (
    OAuthTransaction,
    OAuthTransactionStore,
    Session,
    SessionRecord,
    SessionStore,
    digest,
)
from juval.infrastructure.crypto.token_cipher import TokenCipher, TokenCryptoUnavailable
from juval.infrastructure.sessions.in_memory_session_store import (
    InMemoryOAuthTransactionStore,
    InMemorySessionStore,
)

from . import auth as auth_module
from .auth import ROLE_PERMISSIONS, Principal

logger = logging.getLogger("juval.interfaces.api.bff")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# --- Cookies ----------------------------------------------------------
#
# SameSite=Lax, not Strict and not None, and the reason is the callback:
# FusionAuth returns the user by a **top-level GET navigation** to
# `/api/v1/auth/callback`. `Lax` sends cookies on exactly that (top-level, safe
# method) and withholds them from cross-site POSTs and sub-resource requests --
# which is the CSRF property we want. `Strict` would withhold the transaction
# cookie on the callback and break the flow outright. `None` would send our
# cookies on every cross-site request, which is strictly worse and would also
# require `Secure` anyway. So `Lax` is the strictest value that works.
SESSION_COOKIE = "juval_session"
TRANSACTION_COOKIE = "juval_oauth_txn"
CSRF_COOKIE = "juval_csrf"
CSRF_HEADER = "X-JUVAL-CSRF"

_SESSION_TTL = timedelta(hours=8)
_TRANSACTION_TTL = timedelta(minutes=10)
_HTTP_TIMEOUT_SECONDS = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cookie_secure() -> bool:
    """`Secure` is on unless explicitly disabled for local HTTP development.

    Fail-closed: any value other than the exact opt-out string leaves it on, so
    a typo in the environment cannot silently drop the flag in production.
    """
    return os.environ.get("JUVAL_BFF_INSECURE_COOKIES") != "yes-local-http-only"


@dataclass(frozen=True)
class BffConfig:
    """Everything the BFF needs, resolved once, never guessed.

    `redirect_uri` is stored rather than derived from the incoming request:
    deriving it from `Host`/`X-Forwarded-Host` would let a spoofed header
    change where the authorization code is sent. It is sent to the
    authorization endpoint and echoed to the token endpoint, and RFC 9700
    Sec. 2.1 requires the AS to match it exactly.
    """

    issuer: str
    client_id: str
    client_secret: Optional[str]
    redirect_uri: str
    post_login_redirect: str
    post_logout_redirect: str
    authorization_endpoint: str
    token_endpoint: str
    end_session_endpoint: Optional[str]
    scope: str = "openid profile email"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"JUVAL_AUTH_MODE=oidc requires {name} to be set")
    return value


#: Every variable that belongs to the browser half of OIDC. Presence of ANY of
#: them is what marks a deployment as intending to run the BFF, which is how
#: `build_config` tells "bearer-only API" apart from "browser login configured
#: incorrectly". The first is fatal-free; the second must fail loudly.
_BFF_ENV_VARS = (
    "JUVAL_OIDC_CLIENT_ID",
    "JUVAL_OIDC_CLIENT_SECRET",
    "JUVAL_BFF_REDIRECT_URI",
    "JUVAL_OIDC_AUTHORIZATION_ENDPOINT",
    "JUVAL_OIDC_TOKEN_ENDPOINT",
    "JUVAL_OIDC_END_SESSION_ENDPOINT",
)


def browser_login_intended() -> bool:
    """True when the deployment has asked for the browser flow at all.

    A JUVAl deployment may legitimately be bearer-only: `auth.py` verifies
    tokens minted elsewhere and no human ever logs in through this process. In
    that shape none of `_BFF_ENV_VARS` is set and the BFF routes answer 404,
    which is honest rather than degraded -- no session can be created, so
    nothing is weakened. Setting *some* of them is the dangerous state, and
    `build_config` raises for it (see `_required`).
    """
    return any(os.environ.get(name) for name in _BFF_ENV_VARS)


def build_config() -> Optional[BffConfig]:
    """Build the BFF configuration, or None when the browser flow is not in use.

    Returns None in exactly two cases -- authentication disabled, or a
    bearer-only deployment that set no BFF variable at all. A *partially*
    configured browser flow raises instead: half a login is a configuration
    error, and discovering it at the first user's redirect is too late.

    Endpoint URLs default to FusionAuth's published OAuth2 paths under the
    issuer and can each be overridden, so a provider that deviates is a
    configuration change rather than a code change -- the same contract
    `auth.py::build_verifier` already honours for the JWKS URI.
    """
    if auth_module.auth_mode() == "disabled":
        return None
    if not browser_login_intended():
        return None

    issuer = _required("JUVAL_OIDC_ISSUER").rstrip("/")
    return BffConfig(
        issuer=issuer,
        client_id=_required("JUVAL_OIDC_CLIENT_ID"),
        client_secret=os.environ.get("JUVAL_OIDC_CLIENT_SECRET") or None,
        redirect_uri=_required("JUVAL_BFF_REDIRECT_URI"),
        post_login_redirect=os.environ.get("JUVAL_BFF_POST_LOGIN_REDIRECT", "/"),
        post_logout_redirect=os.environ.get("JUVAL_BFF_POST_LOGOUT_REDIRECT", "/"),
        authorization_endpoint=os.environ.get(
            "JUVAL_OIDC_AUTHORIZATION_ENDPOINT", f"{issuer}/oauth2/authorize"
        ),
        token_endpoint=os.environ.get("JUVAL_OIDC_TOKEN_ENDPOINT", f"{issuer}/oauth2/token"),
        end_session_endpoint=os.environ.get(
            "JUVAL_OIDC_END_SESSION_ENDPOINT", f"{issuer}/oauth2/logout"
        ),
    )


# --- Composition root -------------------------------------------------
#
# There is exactly ONE place the stores are chosen: `ensure_configured()`.
# Every consumer -- login, callback, session resolution, refresh, CSRF, logout
# -- reaches them through `session_store()` / `transaction_store()`, which call
# it first. Reading the module globals directly is what allowed a worker that
# had never served `/login` to answer from the default in-memory store while
# `build_stores()` had selected PostgreSQL: fail-closed (a 401), but a broken
# multi-instance session layer, which is the thing ADR-036 exists to provide.
#
# The globals below are the *pre-initialisation* placeholders. They are never
# the answer to a request: `_configured` is False until `ensure_configured()`
# or `configure()` has run, and both accessors refuse to hand anything out
# before that.

_config: Optional[BffConfig] = None
_configured = False
_sessions: SessionStore = InMemorySessionStore()
_transactions: OAuthTransactionStore = InMemoryOAuthTransactionStore()

#: Explicit opt-in required to run in-memory sessions while OIDC is on. The
#: value is deliberately a sentence, not "true": nobody sets this by accident,
#: and it cannot be arrived at by copying a boolean from another variable.
_MEMORY_OPT_IN = "yes-single-process-development-only"


def build_stores() -> tuple[SessionStore, OAuthTransactionStore]:
    """Select the session backend. **Fails closed; never falls back silently.**

    ADR-036: in-memory sessions are permitted for tests and single-process
    local development and forbidden in production. The failure mode that
    matters is not "durable storage is unavailable" -- it is "durable storage
    was unavailable and nobody noticed, so logins started working
    intermittently across instances". So an unavailable or unconfigured
    durable store raises at startup rather than degrading.

    Two shapes need no durable store at all, and neither is a fallback:

    * authentication disabled -- no session exists, and no endpoint authorises;
    * a bearer-only deployment (OIDC on, no BFF variable set, and no store
      named explicitly). There, `build_config()` returns None, so `/login` and
      `/callback` answer 404 through `_require_config()` -- the only two
      writers a session can have. Nothing can be stored, so demanding a
      database would be a startup failure for a capability the deployment
      never asked for. Naming `JUVAL_SESSION_STORE` overrides this and is
      honoured strictly, so an operator who *does* want the store checked gets
      it checked.
    """
    if auth_module.auth_mode() == "disabled":
        return InMemorySessionStore(), InMemoryOAuthTransactionStore()

    named_backend = os.environ.get("JUVAL_SESSION_STORE")
    if named_backend is None and not browser_login_intended():
        logger.info(
            "no browser-login configuration present -- the BFF routes are disabled "
            "and no session store is required (bearer tokens only)."
        )
        return InMemorySessionStore(), InMemoryOAuthTransactionStore()

    backend = named_backend or "postgres"

    if backend == "memory":
        if os.environ.get("JUVAL_SESSION_STORE_MEMORY_CONFIRM") != _MEMORY_OPT_IN:
            raise RuntimeError(
                "JUVAL_SESSION_STORE=memory with JUVAL_AUTH_MODE=oidc requires "
                f"JUVAL_SESSION_STORE_MEMORY_CONFIRM={_MEMORY_OPT_IN}. In-memory "
                "sessions are single-process only and are forbidden in production "
                "(ADR-036)."
            )
        logger.warning(
            "JUVAL_SESSION_STORE=memory -- sessions are process-local and lost on "
            "restart. Single-process development only; never production (ADR-036)."
        )
        return InMemorySessionStore(), InMemoryOAuthTransactionStore()

    if backend != "postgres":
        raise RuntimeError(
            f"JUVAL_SESSION_STORE has an unrecognized value: {backend!r} "
            "(expected 'postgres' or 'memory')"
        )

    dsn = os.environ.get("JUVAL_SESSION_DB_URL") or os.environ.get("JUVAL_SUPABASE_DB_URL")
    if not dsn:
        raise RuntimeError(
            "JUVAL_SESSION_STORE=postgres requires JUVAL_SESSION_DB_URL (or "
            "JUVAL_SUPABASE_DB_URL) to be set"
        )
    try:
        cipher = TokenCipher.from_environment()
    except TokenCryptoUnavailable as exc:
        # Deliberately fatal. Running without the key would mean either storing
        # tokens in the clear or losing them -- neither is an acceptable
        # degraded mode.
        raise RuntimeError(f"durable sessions cannot start: {exc}") from exc

    from juval.infrastructure.persistence.postgres_session_store import (
        PostgresOAuthTransactionStore,
        PostgresSessionStore,
        verify_session_database,
    )

    verify_session_database(dsn)
    return PostgresSessionStore(dsn, cipher), PostgresOAuthTransactionStore(dsn, cipher)


def configure(
    config: Optional[BffConfig] = None,
    sessions: Optional[SessionStore] = None,
    transactions: Optional[OAuthTransactionStore] = None,
) -> None:
    """Install configuration and stores. Tests and the composition root use it."""
    global _config, _configured, _sessions, _transactions
    _config = config
    _configured = True
    if sessions is not None:
        _sessions = sessions
    if transactions is not None:
        _transactions = transactions


def reset_for_tests() -> None:
    global _config, _configured, _sessions, _transactions
    _config = None
    _configured = False
    _sessions = InMemorySessionStore()
    _transactions = InMemoryOAuthTransactionStore()


def ensure_configured() -> None:
    """Initialise the process once. Idempotent; raises rather than degrading.

    This is the single initialisation point. It is called from the FastAPI
    lifespan (so an invalid production configuration stops startup rather than
    surfacing as an intermittent runtime fault) and, defensively, from every
    store accessor, so that a process which somehow reaches a request first --
    an embedded worker, a test, a future entrypoint -- still cannot serve one
    against an unconfigured store.

    Anything wrong raises: an unknown backend, a missing DSN, a missing
    encryption key, in-memory sessions under OIDC without the explicit opt-in,
    or a half-configured browser flow. There is deliberately no path here that
    falls back to a weaker store.
    """
    global _configured
    if _configured:
        return
    sessions, transactions = build_stores()
    configure(build_config(), sessions=sessions, transactions=transactions)


def current_config() -> Optional[BffConfig]:
    ensure_configured()
    return _config


def session_store() -> SessionStore:
    """The one session store this process uses. Never the placeholder."""
    ensure_configured()
    return _sessions


def transaction_store() -> OAuthTransactionStore:
    """The one OAuth transaction store this process uses."""
    ensure_configured()
    return _transactions


def _require_config() -> BffConfig:
    config = current_config()
    if config is None:
        # Not 500: the deployment is simply not running the browser flow.
        # Saying so plainly beats a stack trace, and it cannot be mistaken for
        # an auth failure. The two reasons are distinguished because they call
        # for different fixes -- turn authentication on, or configure the BFF.
        detail = (
            "authentication is not enabled"
            if auth_module.auth_mode() == "disabled"
            else "browser authentication is not configured"
        )
        raise HTTPException(status_code=404, detail=detail)
    return config


# --- PKCE -------------------------------------------------------------


def _pkce_pair() -> tuple[str, str]:
    """(verifier, S256 challenge). RFC 7636; S256 only -- `plain` is not offered.

    RFC 9700 Sec. 2.1.1: public clients MUST use PKCE. JUVAl's BFF is a
    confidential client and would survive without it, but PKCE also defeats
    authorization-code injection at the redirect, which a client secret does
    not, so it is used regardless of client type.
    """
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verifier, challenge


def _safe_return_to(raw: Optional[str], fallback: str) -> str:
    """Only same-site, path-absolute returns. Blocks open redirects.

    Anything with a scheme or an authority is rejected outright, including
    protocol-relative `//evil.example`, which is why the second character is
    checked and not just the first.
    """
    if not raw or not raw.startswith("/") or raw.startswith("//"):
        return fallback
    return raw


# --- Endpoints --------------------------------------------------------


@router.get("/login")
def login(request: Request, return_to: Optional[str] = None) -> Response:
    """Begin Authorization Code + PKCE. Redirects the browser to the IdP."""
    config = _require_config()
    verifier, challenge = _pkce_pair()
    transaction = OAuthTransaction(
        transaction_id=secrets.token_urlsafe(32),
        state=secrets.token_urlsafe(32),
        code_verifier=verifier,
        nonce=secrets.token_urlsafe(32),
        redirect_uri=config.redirect_uri,
        created_at=_now(),
        expires_at=_now() + _TRANSACTION_TTL,
        return_to=_safe_return_to(return_to, config.post_login_redirect),
    )
    transaction_store().start(transaction)

    query = urllib.parse.urlencode(
        {
            "client_id": config.client_id,
            "response_type": "code",
            "redirect_uri": config.redirect_uri,
            "scope": config.scope,
            "state": transaction.state,
            "nonce": transaction.nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(f"{config.authorization_endpoint}?{query}", status_code=302)
    response.set_cookie(
        TRANSACTION_COOKIE,
        transaction.transaction_id,
        max_age=int(_TRANSACTION_TTL.total_seconds()),
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/api/v1/auth",
    )
    return response


@router.get("/callback")
def callback(request: Request, code: Optional[str] = None, state: Optional[str] = None) -> Response:
    """Finish the exchange, create the session, hand back only a cookie."""
    config = _require_config()

    transaction_id = request.cookies.get(TRANSACTION_COOKIE)
    if not transaction_id or not code or not state:
        raise HTTPException(status_code=400, detail="invalid authorization response")

    transaction = transaction_store().consume(transaction_id, _now())
    if transaction is None:
        # Unknown, expired, or already used. A replayed callback lands here
        # because `consume` is single-use, which is the point.
        raise HTTPException(status_code=400, detail="invalid authorization response")

    if not hmac.compare_digest(transaction.state_digest, digest(state)):
        logger.warning("oauth state mismatch")
        raise HTTPException(status_code=400, detail="invalid authorization response")

    token_response = _exchange_code(config, code, transaction)
    id_token = token_response.get("id_token")
    if not isinstance(id_token, str):
        raise HTTPException(status_code=502, detail="identity provider returned no id_token")

    claims = _verify_id_token(id_token, transaction.nonce_digest)

    roles = auth_module._roles_from_claims(claims, os.environ.get("JUVAL_OIDC_ROLES_CLAIM", "roles"))
    session = Session(
        session_id=secrets.token_urlsafe(32),
        subject=str(claims["sub"]),
        roles=tuple(roles),
        csrf_token=secrets.token_urlsafe(32),
        created_at=_now(),
        expires_at=_now() + _SESSION_TTL,
        access_token=token_response.get("access_token"),
        refresh_token=token_response.get("refresh_token"),
        access_token_expires_at=_expires_at(token_response.get("expires_in")),
    )
    session_store().save(session)

    response = RedirectResponse(
        _safe_return_to(transaction.return_to, config.post_login_redirect), status_code=302
    )
    _set_session_cookies(response, session)
    response.delete_cookie(TRANSACTION_COOKIE, path="/api/v1/auth")
    return response


@router.get("/session")
def session_view(request: Request) -> JSONResponse:
    """What the browser is allowed to know about its own session.

    A deliberate projection, not a serialization: subject, roles, derived
    permissions and expiry. No access token, no refresh token, no ID token, no
    raw claims. The CSRF token is returned because the browser must echo it,
    and it is not a bearer credential -- it authorizes nothing on its own.
    """
    session_id = request.cookies.get(SESSION_COOKIE)
    session = session_store().load(session_id, _now()) if session_id else None
    if session is None:
        return JSONResponse({"authenticated": False}, status_code=200)

    # Opportunistic refresh: this is the endpoint the SPA polls, so it is the
    # natural place to keep the access token alive. Doing it on every request
    # instead would put a network call to the IdP in the hot path.
    refresh_if_needed(session_id, session)
    # None can mean either no refresh or revocation. Never revive the snapshot
    # loaded before a rejected refresh (or a concurrent logout).
    session = session_store().load(session_id, _now())
    if session is None:
        response = JSONResponse({"authenticated": False}, status_code=200)
        _clear_session_cookies(response)
        return response

    body = {
        "authenticated": True,
        "subject": session.subject,
        "roles": list(session.roles),
        "permissions": sorted(_permissions_for(session.roles)),
        "expires_at": session.expires_at.isoformat(),
    }
    # The CSRF token is never stored server-side -- only its digest is. It is
    # echoed back from the caller's own cookie, and only after that cookie is
    # verified against the digest, so this cannot be used to read another
    # session's token.
    presented = request.cookies.get(CSRF_COOKIE)
    if presented and hmac.compare_digest(digest(presented), session.csrf_digest):
        body["csrf_token"] = presented
    return JSONResponse(body)


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    """End the session. CSRF-protected, and idempotent by design."""
    session_id = request.cookies.get(SESSION_COOKIE)
    session = session_store().load(session_id, _now()) if session_id else None
    if session is not None:
        require_csrf(request, session)
        # Revoke server-side: clearing the cookie alone would leave a valid
        # session id usable by anyone who captured it.
        session_store().revoke(session_id, _now())

    config = current_config()
    body: dict[str, Any] = {"logged_out": True}
    if config is not None and config.end_session_endpoint:
        # Propagating logout to the IdP is a *browser* navigation, so the BFF
        # cannot perform it: it hands the URL back and the client navigates.
        # Without this the JUVAl session ends while the FusionAuth SSO session
        # survives, and the next /login silently re-authenticates.
        body["end_session_url"] = (
            f"{config.end_session_endpoint}?"
            + urllib.parse.urlencode(
                {"client_id": config.client_id, "post_logout_redirect_uri": config.post_logout_redirect}
            )
        )
    response = JSONResponse(body)
    _clear_session_cookies(response)
    return response


# --- Session plumbing -------------------------------------------------


def _set_session_cookies(response: Response, session: Session) -> None:
    max_age = int((session.expires_at - _now()).total_seconds())
    response.set_cookie(
        SESSION_COOKIE,
        session.session_id,
        max_age=max_age,
        httponly=True,          # unreadable by JavaScript: this is the credential
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        session.csrf_token,
        max_age=max_age,
        httponly=False,         # deliberately readable: the SPA must echo it
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _session_from_request(request: Request) -> Optional[SessionRecord]:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    return session_store().load(session_id, _now())


def _permissions_for(roles: tuple[str, ...]) -> frozenset[str]:
    if not roles:
        return frozenset()
    return frozenset().union(*(ROLE_PERMISSIONS.get(r, frozenset()) for r in roles))


def principal_from_session(request: Request) -> Optional[Principal]:
    """`auth.py` session resolver. Returns None when there is no valid session.

    Returning None rather than raising is deliberate: absence of a session is
    not an error, it just means the bearer path should be tried next.
    """
    session = _session_from_request(request)
    if session is None:
        return None
    return Principal(
        subject=session.subject,
        roles=session.roles,
        permissions=_permissions_for(session.roles),
    )


def require_csrf(request: Request, session: Optional[SessionRecord] = None) -> None:
    """Double-submit CSRF check for state-changing, cookie-authenticated calls.

    `SameSite=Lax` already blocks cross-site POSTs in current browsers; this is
    the second layer, because `Lax` is a browser behaviour and not a server
    control, and because a same-site subdomain compromise defeats it. The
    header cannot be set cross-origin without CORS approval, and the CORS
    policy never returns `*` (`service.cors_origins`).

    Only cookie-authenticated requests are checked. A bearer-token caller is
    not a browser and cannot be CSRF'd -- demanding a CSRF header from it would
    be theatre that breaks service clients.
    """
    session = session or _session_from_request(request)
    if session is None:
        return
    supplied = request.headers.get(CSRF_HEADER, "")
    if not supplied or not hmac.compare_digest(digest(supplied), session.csrf_digest):
        logger.warning("csrf check failed for subject=%s", session.subject)
        raise HTTPException(status_code=403, detail="csrf token missing or invalid")


def csrf_guard(request: Request) -> None:
    """FastAPI dependency form of `require_csrf`, for state-changing endpoints."""
    require_csrf(request)


# --- Refresh rotation -------------------------------------------------

#: Refresh once the access token is within this window of expiring. Wide
#: enough that an ordinary request never races the expiry, narrow enough that
#: the IdP is not called on every poll.
_REFRESH_SKEW = timedelta(seconds=120)


def refresh_if_needed(session_id: str, record: SessionRecord) -> Optional[SessionRecord]:
    """Renew under store-wide exclusion; preserve session id and CAS writes.

    Reload after acquiring the guard: the caller may hold an older generation.
    Busy refreshers skip provider I/O. Guard failure propagates fail-closed.
    A process/DB failure after provider rotation can still require a new login;
    the database and external provider do not share an atomic transaction.
    """
    if record.refresh_token is None or record.access_token_expires_at is None:
        return None
    if record.access_token_expires_at - _now() > _REFRESH_SKEW:
        return None
    with session_store().refresh_guard(session_id) as acquired:
        if not acquired:
            return None
        current = session_store().load(session_id, _now())
        if current is None:
            return None
        if current.refresh_generation != record.refresh_generation:
            return current
        return _refresh_exclusive(session_id, current)


def _refresh_exclusive(session_id: str, record: SessionRecord) -> Optional[SessionRecord]:
    if record.refresh_token is None or record.access_token_expires_at is None:
        return None
    if record.access_token_expires_at - _now() > _REFRESH_SKEW:
        return None

    config = current_config()
    if config is None:
        return None

    try:
        token_response = _refresh_tokens(config, record.refresh_token)
    except _RefreshRejected:
        # The IdP refused it. Holding a refused refresh token is worse than
        # holding none, and a replayed token means the session is suspect.
        logger.warning("refresh rejected by the identity provider; revoking session")
        session_store().revoke(session_id, _now())
        return None
    except Exception:  # transport failure, IdP down
        logger.warning("refresh call failed; keeping the existing session")
        return None

    access = token_response.get("access_token")
    refresh = token_response.get("refresh_token") or record.refresh_token
    expires_at = _expires_at(token_response.get("expires_in"))

    try:
        won = session_store().replace_tokens(
            session_id,
            expected_generation=record.refresh_generation,
            access_token=access,
            refresh_token=refresh,
            access_token_expires_at=expires_at,
            now=_now(),
        )
    except Exception:
        logger.warning("refresh persistence failed; existing session left untouched")
        return None

    if not won:
        # A concurrent request refreshed first. Its tokens are the live ones.
        logger.info("refresh lost the race; re-reading the winning session state")
        return session_store().load(session_id, _now())

    return session_store().load(session_id, _now())


class _RefreshRejected(RuntimeError):
    """The IdP refused the refresh token (4xx), as opposed to being unreachable."""


def _refresh_tokens(config: BffConfig, refresh_token: str) -> Mapping[str, Any]:
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": config.client_id,
    }
    if config.client_secret:
        form["client_secret"] = config.client_secret
    request = urllib.request.Request(
        config.token_endpoint,
        data=urllib.parse.urlencode(form).encode("ascii"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as raw:
            return json.loads(raw.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The body may quote the refresh token; it is never read or logged.
        if exc.code == 429 or exc.code >= 500:
            raise RuntimeError("identity provider temporarily unavailable") from None
        raise _RefreshRejected(f"HTTP {exc.code}") from None


# --- IdP calls --------------------------------------------------------


def _exchange_code(config: BffConfig, code: str, transaction: OAuthTransaction) -> Mapping[str, Any]:
    """POST the code + verifier to the token endpoint.

    stdlib `urllib`, not a new HTTP dependency: this is one form POST, and
    CLAUDE.md Sec. 20 asks for stdlib before a dependency.
    """
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": transaction.redirect_uri,
        "client_id": config.client_id,
        "code_verifier": transaction.code_verifier,
    }
    if config.client_secret:
        form["client_secret"] = config.client_secret

    request = urllib.request.Request(
        config.token_endpoint,
        data=urllib.parse.urlencode(form).encode("ascii"),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as raw:
            return json.loads(raw.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The IdP's error body may quote the code; it never reaches the client.
        logger.warning("token exchange rejected: HTTP %s", exc.code)
        raise HTTPException(status_code=400, detail="authorization code exchange failed") from exc
    except Exception as exc:
        logger.warning("token exchange failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="identity provider unreachable") from exc


def _verify_id_token(id_token: str, expected_nonce_digest: str) -> Mapping[str, Any]:
    """Verify the ID token with the same verifier the API uses for bearers.

    Reusing `auth.py`'s verifier is the point: issuer, audience, expiry, RS256
    pinning, required claims, JWKS cache and clock skew are defined once. A
    second, subtly different verification path here is exactly the kind of
    duplicate security logic that eventually diverges.
    """
    verifier = auth_module.current_verifier()
    if verifier is None:
        raise HTTPException(status_code=404, detail="authentication is not enabled")

    verifier.verify(id_token)  # raises 401 on any failure

    claims = jwt.decode(id_token, options={"verify_signature": False})
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not hmac.compare_digest(digest(nonce), expected_nonce_digest):
        # Signature already checked above; this binds the token to *this*
        # authorization request, which the signature alone does not do.
        logger.warning("id_token nonce mismatch")
        raise HTTPException(status_code=400, detail="invalid authorization response")
    return claims


def _expires_at(expires_in: Any) -> Optional[datetime]:
    try:
        return _now() + timedelta(seconds=int(expires_in))
    except (TypeError, ValueError):
        return None
