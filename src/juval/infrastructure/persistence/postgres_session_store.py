"""PostgreSQL/Supabase durable session storage (ADR-036).

Implements the same ports as `infrastructure/sessions/in_memory_session_store.py`
(`application/session_store.py`), so `interfaces/api/bff.py` switches between
them by configuration, with no change to any caller.

Why durable at all
------------------
ADR-034 put the OAuth tokens on the server, which gave the backend session
state it never had. Railway may run more than one instance: a session created
on instance A must be readable on instance B, and -- less obviously but just as
importantly -- a login started on A must be completable by a callback that
lands on B. The in-memory adapter satisfies neither, which is why it is
forbidden in production rather than merely discouraged.

Driver: `psycopg` (the `postgres` extra), matching
`supabase_execution_run_store.py`. Imported lazily so that importing this
module, and constructing the store, work without it -- only opening a
connection needs it.

Storage rules this adapter enforces
-----------------------------------
* the raw session id, CSRF token, `state` and `nonce` are **never** written --
  only SHA-256 digests (`application/session_store.py::digest`);
* access, refresh and PKCE-verifier values are written **only** as AES-256-GCM
  envelopes produced by `infrastructure/crypto/token_cipher.py`, with the key
  living in the backend environment and never in this database;
* every ciphertext is bound by AEAD associated data to the row and column it
  belongs to, so a ciphertext moved between rows or columns fails to decrypt.

Atomicity
---------
`consume` is a single `DELETE ... RETURNING`, so a replayed or concurrent
callback finds nothing -- the single-use property of the OAuth transaction is
enforced by the database, not by application timing.

`replace_tokens` is a single `UPDATE ... WHERE refresh_generation = %s`, so of
two concurrent refreshes exactly one can win; the loser is told it lost and
re-reads instead of clobbering a refresh token the winner has already used.

Decryption failure is treated as session invalidity, never as an error to
surface: a row whose ciphertext will not authenticate is unusable, and the
correct response is to make the caller log in again.
"""

from __future__ import annotations

from contextlib import contextmanager

import logging
from datetime import datetime
from typing import Any, Optional

from juval.application.session_store import (
    OAuthTransaction,
    OAuthTransactionRecord,
    Session,
    SessionRecord,
    digest,
)
from juval.infrastructure.crypto.token_cipher import (
    TokenCipher,
    TokenDecryptionError,
    context_for,
)

logger = logging.getLogger("juval.infrastructure.persistence.postgres_session_store")

_ACCESS = "access_token"
_REFRESH = "refresh_token"
_VERIFIER = "code_verifier"


def _require_driver():
    try:
        import psycopg  # noqa: PLC0415 - deliberately lazy, see module docstring
    except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "psycopg is required for durable sessions: install the 'postgres' extra "
            "(pip install -e '.[postgres]')"
        ) from exc
    return psycopg


def verify_session_database(dsn: str) -> None:
    """Read-only startup check of the selected database and ADR-036 boundary.

    Does not read rows, create tables, or run migrations. Missing tables,
    incompatible columns/digest keys, non-owner roles, disabled/forced RLS or any policy
    abort startup. Driver diagnostics may contain credentials: suppress them.
    Connection and SQL waits are bounded independently.
    """
    try:
        with _require_driver().connect(dsn, connect_timeout=5) as conn:
            conn.execute("set transaction read only")
            conn.execute("set local statement_timeout = '5s'")
            rows = conn.execute(
                "select relrowsecurity, relforcerowsecurity, "
                "relowner = (select oid from pg_roles where rolname = current_user), "
                "not exists (select 1 from pg_policy where polrelid = c.oid) "
                "from pg_class c where c.oid in "
                "(to_regclass('identity_sessions'), to_regclass('identity_oauth_transactions')) "
                "and relkind = 'r'"
            ).fetchall()
            if len(rows) != 2 or any(row != (True, False, True, True) for row in rows):
                raise RuntimeError("session schema does not satisfy ADR-036")
            # Both upserts and single-use transaction custody require a valid,
            # nondeferrable primary key on exactly the digest column.
            for table, column in (
                ("identity_sessions", "session_digest"),
                ("identity_oauth_transactions", "transaction_digest"),
            ):
                key_count = conn.execute(
                    "select count(*) from pg_constraint c "
                    "join pg_attribute a on a.attrelid = c.conrelid "
                    "join pg_index i on i.indexrelid = c.conindid "
                    "where c.conrelid = to_regclass(%s) and c.contype = 'p' "
                    "and not c.condeferrable and c.convalidated and i.indisvalid "
                    "and a.attname = %s and c.conkey = array[a.attnum]",
                    (table, column),
                ).fetchone()[0]
                if key_count != 1:
                    raise RuntimeError("session digest primary key is missing or incompatible")
            # Resolve every column used by the adapters without reading tokens.
            conn.execute(
                "select session_digest, subject, roles, csrf_digest, "
                "access_token_ciphertext, refresh_token_ciphertext, crypto_key_id, "
                "access_token_expires_at, created_at, last_seen_at, expires_at, "
                "revoked_at, refresh_generation from identity_sessions limit 0"
            )
            conn.execute(
                "select transaction_digest, state_digest, nonce_digest, "
                "code_verifier_ciphertext, crypto_key_id, redirect_uri, return_to, "
                "created_at, expires_at from identity_oauth_transactions limit 0"
            )
    except Exception:
        raise RuntimeError(
            "durable session database readiness failed; verify connectivity, migration, "
            "table ownership and zero-policy RLS (ADR-036)"
        ) from None


class _PostgresBacked:
    def __init__(self, dsn: str, cipher: TokenCipher) -> None:
        self._dsn = dsn
        self._cipher = cipher

    def _connect(self):
        return _require_driver().connect(self._dsn, connect_timeout=5)


class PostgresOAuthTransactionStore(_PostgresBacked):
    def start(self, transaction: OAuthTransaction) -> None:
        transaction_digest = digest(transaction.transaction_id)
        verifier = self._cipher.encrypt(
            transaction.code_verifier, context=context_for(transaction_digest, _VERIFIER)
        )
        with self._connect() as conn:
            conn.execute(
                """
                insert into identity_oauth_transactions (
                    transaction_digest, state_digest, nonce_digest,
                    code_verifier_ciphertext, crypto_key_id,
                    redirect_uri, return_to, created_at, expires_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (transaction_digest) do nothing
                """,
                (
                    transaction_digest,
                    digest(transaction.state),
                    digest(transaction.nonce),
                    verifier,
                    self._cipher.primary_key_id,
                    transaction.redirect_uri,
                    transaction.return_to,
                    transaction.created_at,
                    transaction.expires_at,
                ),
            )

    def consume(self, transaction_id: str, now: datetime) -> Optional[OAuthTransactionRecord]:
        transaction_digest = digest(transaction_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                delete from identity_oauth_transactions
                 where transaction_digest = %s
             returning state_digest, nonce_digest, code_verifier_ciphertext,
                       redirect_uri, return_to, expires_at
                """,
                (transaction_digest,),
            ).fetchone()
        if row is None:
            return None
        state_digest, nonce_digest, verifier_ct, redirect_uri, return_to, expires_at = row
        if expires_at <= now:
            # Already deleted by the statement above; an expired transaction is
            # simply unusable.
            return None
        try:
            verifier = self._cipher.decrypt(
                verifier_ct, context=context_for(transaction_digest, _VERIFIER)
            )
        except TokenDecryptionError:
            logger.warning("oauth transaction verifier failed decryption; treating as invalid")
            return None
        return OAuthTransactionRecord(
            state_digest=state_digest,
            nonce_digest=nonce_digest,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
            return_to=return_to,
        )

    def purge_expired(self, now: datetime) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "delete from identity_oauth_transactions where expires_at <= %s", (now,)
            )
            return cur.rowcount or 0


class PostgresSessionStore(_PostgresBacked):
    @contextmanager
    def refresh_guard(self, session_id: str):
        # Transaction-scoped lock: released on normal exit, exception or lost
        # connection. Stable 64-bit namespace; collisions only defer refresh.
        key = int(digest("juval-refresh:" + session_id)[:16], 16)
        if key >= 2**63:
            key -= 2**64
        with self._connect() as conn:
            conn.execute("set local statement_timeout = '5s'")
            acquired = conn.execute(
                "select pg_try_advisory_xact_lock(%s)", (key,)
            ).fetchone()[0]
            yield acquired

    def save(self, session: Session) -> None:
        session_digest = digest(session.session_id)
        access = self._seal(session.access_token, session_digest, _ACCESS)
        refresh = self._seal(session.refresh_token, session_digest, _REFRESH)
        with self._connect() as conn:
            conn.execute(
                """
                insert into identity_sessions (
                    session_digest, subject, roles, csrf_digest,
                    access_token_ciphertext, refresh_token_ciphertext, crypto_key_id,
                    access_token_expires_at, created_at, last_seen_at, expires_at,
                    revoked_at, refresh_generation
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, null, 0)
                on conflict (session_digest) do update set
                    subject                  = excluded.subject,
                    roles                    = excluded.roles,
                    csrf_digest              = excluded.csrf_digest,
                    access_token_ciphertext  = excluded.access_token_ciphertext,
                    refresh_token_ciphertext = excluded.refresh_token_ciphertext,
                    crypto_key_id            = excluded.crypto_key_id,
                    access_token_expires_at  = excluded.access_token_expires_at,
                    last_seen_at             = excluded.last_seen_at,
                    expires_at               = excluded.expires_at,
                    revoked_at               = null
                """,
                (
                    session_digest,
                    session.subject,
                    list(session.roles),
                    digest(session.csrf_token),
                    access,
                    refresh,
                    self._cipher.primary_key_id,
                    session.access_token_expires_at,
                    session.created_at,
                    session.created_at,
                    session.expires_at,
                ),
            )

    def load(self, session_id: str, now: datetime) -> Optional[SessionRecord]:
        session_digest = digest(session_id)
        with self._connect() as conn:
            row = conn.execute(
                """
                select subject, roles, csrf_digest,
                       access_token_ciphertext, refresh_token_ciphertext,
                       access_token_expires_at, created_at, expires_at,
                       revoked_at, refresh_generation
                  from identity_sessions
                 where session_digest = %s
                """,
                (session_digest,),
            ).fetchone()
            if row is None:
                return None
            (
                subject,
                roles,
                csrf_digest,
                access_ct,
                refresh_ct,
                access_expires_at,
                created_at,
                expires_at,
                revoked_at,
                generation,
            ) = row
            if revoked_at is not None or expires_at <= now:
                return None
            # Touch last_seen_at on the same connection. Purely observational --
            # nothing authorises on it -- so a failure here must never deny a
            # valid session.
            conn.execute(
                "update identity_sessions set last_seen_at = %s where session_digest = %s",
                (now, session_digest),
            )

        try:
            access = self._open(access_ct, session_digest, _ACCESS)
            refresh = self._open(refresh_ct, session_digest, _REFRESH)
        except TokenDecryptionError:
            # Wrong key, rotated-out key, corrupt or moved ciphertext. The row
            # is unusable; fail closed and make the caller re-authenticate.
            logger.warning("session token failed decryption; treating session as invalid")
            return None

        return SessionRecord(
            session_digest=session_digest,
            subject=subject,
            roles=tuple(roles or ()),
            csrf_digest=csrf_digest,
            created_at=created_at,
            expires_at=expires_at,
            access_token=access,
            refresh_token=refresh,
            access_token_expires_at=access_expires_at,
            refresh_generation=generation,
        )

    def revoke(self, session_id: str, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update identity_sessions
                   set revoked_at = %s,
                       access_token_ciphertext = null,
                       refresh_token_ciphertext = null
                 where session_digest = %s and revoked_at is null
                """,
                (now, digest(session_id)),
            )

    def replace_tokens(
        self,
        session_id: str,
        expected_generation: int,
        access_token: Optional[str],
        refresh_token: Optional[str],
        access_token_expires_at: Optional[datetime],
        now: datetime,
    ) -> bool:
        session_digest = digest(session_id)
        access = self._seal(access_token, session_digest, _ACCESS)
        refresh = self._seal(refresh_token, session_digest, _REFRESH)
        with self._connect() as conn:
            cur = conn.execute(
                """
                update identity_sessions
                   set access_token_ciphertext  = %s,
                       refresh_token_ciphertext = %s,
                       crypto_key_id            = %s,
                       access_token_expires_at  = %s,
                       last_seen_at             = %s,
                       refresh_generation       = refresh_generation + 1
                 where session_digest     = %s
                   and refresh_generation = %s
                   and revoked_at is null
                   and expires_at > %s
                """,
                (
                    access,
                    refresh,
                    self._cipher.primary_key_id,
                    access_token_expires_at,
                    now,
                    session_digest,
                    expected_generation,
                    now,
                ),
            )
            return (cur.rowcount or 0) == 1

    def purge_expired(self, now: datetime) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "delete from identity_sessions where expires_at <= %s or revoked_at is not null",
                (now,),
            )
            return cur.rowcount or 0

    # -- crypto helpers ---------------------------------------------------

    def _seal(self, value: Optional[str], session_digest: str, field: str) -> Optional[str]:
        if value is None:
            return None
        return self._cipher.encrypt(value, context=context_for(session_digest, field))

    def _open(self, envelope: Optional[Any], session_digest: str, field: str) -> Optional[str]:
        if envelope is None:
            return None
        return self._cipher.decrypt(envelope, context=context_for(session_digest, field))
