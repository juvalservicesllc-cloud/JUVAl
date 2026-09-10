"""Ports: server-side custody for browser sessions and in-flight OAuth transactions.

Defined in the Application Layer for the same reason as
`execution_run_store.py`: the things being stored are plain dataclasses with no
infrastructure in them, and concrete adapters live in `infrastructure/` and
depend on this contract, never the reverse (ADR-001).

Why these exist
---------------
ADR-034 puts the OAuth tokens on the server. The browser holds an opaque
session id in an HttpOnly cookie and nothing else, so an XSS in the PWA cannot
read an access token, a refresh token or a PKCE verifier. Something
server-side has to hold them; this is the contract for that something.

Two stores, not one, because the lifetimes differ: an OAuth transaction lives
for the seconds between `/auth/login` and `/auth/callback` and is single-use; a
session lives for hours and is read on every request.

Presented values vs stored values -- why there are four dataclasses
-------------------------------------------------------------------
`Session` and `OAuthTransaction` are what the BFF *creates*: they carry the raw
session id, the raw CSRF token, the raw `state` and `nonce`. `SessionRecord`
and `OAuthTransactionRecord` are what a store *returns*: the raw bearer-shaped
values are gone, replaced by digests.

That asymmetry is the point. A durable store must never hold a value that is
itself a credential -- a `SELECT` on the sessions table must not be a
session-hijacking kit (ADR-036). Making it two types means the restriction is
enforced by the type system rather than by remembering, and it makes the
in-memory adapter obey exactly the same rule as the PostgreSQL one instead of
being quietly more permissive.

Comparison is therefore always digest-to-digest, via `digest()` below and
`hmac.compare_digest`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import ContextManager, Optional, Protocol, Tuple


def digest(value: str) -> str:
    """SHA-256 hex of a high-entropy identifier.

    A plain hash, deliberately not a password KDF: these values are 256 bits of
    CSPRNG output, so there is no dictionary to attack and a slow KDF would add
    latency to every request while buying nothing.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# --- what the BFF creates ---------------------------------------------


@dataclass(frozen=True)
class OAuthTransaction:
    """One in-flight Authorization Code + PKCE exchange, as created.

    * `state` -- CSRF binding between the authorization request and its
      callback (RFC 9700 Sec. 2.1.3).
    * `code_verifier` -- the PKCE secret. The only field a store must keep
      recoverable, because the token exchange needs its plaintext.
    * `nonce` -- binds the ID token to this request, defeating replay.
    * `redirect_uri` -- echoed to the token endpoint exactly as sent, so a
      mismatch is caught server-side rather than trusted from the callback.
    """

    transaction_id: str
    state: str
    code_verifier: str
    nonce: str
    redirect_uri: str
    created_at: datetime
    expires_at: datetime
    return_to: Optional[str] = None


@dataclass(frozen=True)
class Session:
    """An authenticated browser session, as created."""

    session_id: str
    subject: str
    roles: Tuple[str, ...]
    csrf_token: str
    created_at: datetime
    expires_at: datetime
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    access_token_expires_at: Optional[datetime] = None


# --- what a store returns ---------------------------------------------


@dataclass(frozen=True)
class OAuthTransactionRecord:
    state_digest: str
    nonce_digest: str
    code_verifier: str
    redirect_uri: str
    return_to: Optional[str] = None


@dataclass(frozen=True)
class SessionRecord:
    """A loaded session. Carries no value that is a credential on its own.

    `access_token`/`refresh_token` are present because the BFF must be able to
    refresh and call the IdP; they never leave the server (`bff.py` has no path
    that serialises them to a response).
    """

    session_digest: str
    subject: str
    roles: Tuple[str, ...]
    csrf_digest: str
    created_at: datetime
    expires_at: datetime
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    access_token_expires_at: Optional[datetime] = None
    refresh_generation: int = 0


# --- the ports ---------------------------------------------------------


class OAuthTransactionStore(Protocol):
    def start(self, transaction: OAuthTransaction) -> None:
        """Persist a pending transaction."""

    def consume(self, transaction_id: str, now: datetime) -> Optional[OAuthTransactionRecord]:
        """Return the transaction and delete it, **atomically**.

        Single-use by contract: a replayed callback must find nothing the
        second time, and two concurrent callbacks must not both succeed -- so
        an implementation may not read-then-delete in two steps. Returns None
        when unknown or expired; the caller cannot distinguish the two and must
        not try.
        """

    def purge_expired(self, now: datetime) -> int:
        """Delete expired rows. Returns how many. Safe to call concurrently."""


class SessionStore(Protocol):
    def refresh_guard(self, session_id: str) -> ContextManager[bool]:
        """Nonblocking exclusion across refresh callers sharing this store.

        Yield True only to the sole refresher until context exit. A busy caller
        skips refresh; it must not contact the provider with a stale token.
        PostgreSQL implementations must coordinate across processes.
        """

    def save(self, session: Session) -> None:
        """Create or replace a session."""

    def load(self, session_id: str, now: datetime) -> Optional[SessionRecord]:
        """Return the session, or None when unknown, expired or revoked."""

    def revoke(self, session_id: str, now: datetime) -> None:
        """End a session immediately. Idempotent -- logging out twice is fine."""

    def replace_tokens(
        self,
        session_id: str,
        expected_generation: int,
        access_token: Optional[str],
        refresh_token: Optional[str],
        access_token_expires_at: Optional[datetime],
        now: datetime,
    ) -> bool:
        """Atomically swap the stored tokens after a refresh.

        Returns True when this caller won. Returns **False** when
        `expected_generation` no longer matches -- meaning a concurrent refresh
        already replaced the tokens, and the caller must re-read rather than
        overwrite. This is what stops a lost update from silently invalidating
        a refresh token that another request is about to use.
        """

    def purge_expired(self, now: datetime) -> int:
        """Delete expired and revoked rows. Returns how many."""
