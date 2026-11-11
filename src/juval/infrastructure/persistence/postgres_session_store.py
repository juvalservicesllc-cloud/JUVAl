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
from datetime import datetime, timedelta
from typing import Any, Optional

from juval.application.session_store import (
    DEFAULT_IDLE_TIMEOUT,
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


def _wait_for_refresher(conn, key: int, wait: timedelta) -> None:
    """Block until the refresher holding `key` ends its transaction, at most `wait`.

    Acquiring the lock here only proves the refresher finished; this caller is
    not the refresher, so the lock is released at once by committing. On
    `lock_timeout` the transaction is rolled back. Either way the caller
    re-reads the session and never contacts the provider.
    """
    milliseconds = max(1, int(wait.total_seconds() * 1000))
    conn.execute(
        "select set_config('lock_timeout', %s, true), set_config('statement_timeout', %s, true)",
        (f"{milliseconds}ms", f"{milliseconds + 5000}ms"),   # lock_timeout is the bound
    )
    try:
        conn.execute("select pg_advisory_xact_lock(%s)", (key,))
    except _require_driver().errors.LockNotAvailable:
        conn.rollback()
        return
    conn.commit()


_SESSION_CRUD = {
    "identity_sessions": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "identity_oauth_transactions": ("SELECT", "INSERT", "DELETE"),
}


def _verify_session_runtime_boundary(conn) -> None:
    """Check only the identity runtime boundary; Gate B2 audits wider capabilities."""
    role = conn.execute(
        "select current_user, session_user, rolsuper, rolbypassrls, "
        "rolcreatedb, rolcreaterole, rolreplication, rolcanlogin, "
        "current_setting('server_version_num')::integer, "
        "exists (select 1 from pg_auth_members m "
        "where m.member = r.oid or m.roleid = r.oid) "
        "from pg_roles r where r.rolname = current_user"
    ).fetchone()
    if (
        role is None
        or role[:8] != ("juval_backend", "juval_backend", False, False, False, False, False, True)
        or role[9] is not False
    ):
        raise RuntimeError("session runtime role does not satisfy ADR-048")
    version = role[8]
    if conn.execute("select has_schema_privilege(current_user, 'public', 'USAGE')").fetchone() != (True,):
        raise RuntimeError("session schema is inaccessible")
    rows = conn.execute(
        "select c.relname, c.relrowsecurity, c.relforcerowsecurity, "
        "c.relowner = (select oid from pg_roles where rolname = current_user), "
        "c.oid = to_regclass(c.relname) "
        "from pg_class c join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' and c.relname = any(%s)",
        (list(_SESSION_CRUD),),
    ).fetchall()
    # The adapters use unqualified names: reject search_path shadowing as well.
    if (
        len(rows) != 2
        or {row[0] for row in rows} != set(_SESSION_CRUD)
        or any(row[1:] != (True, False, False, True) for row in rows)
    ):
        raise RuntimeError("session tables do not satisfy ADR-048")

    expected_policies = set()
    for table, commands in _SESSION_CRUD.items():
        for command in commands:
            expected_policies.add((
                table, "juval_backend_" + command.lower(), "PERMISSIVE",
                ("juval_backend",), command,
                "true" if command != "INSERT" else None,
                "true" if command in ("INSERT", "UPDATE") else None,
            ))
    policies = conn.execute(
        "select tablename, policyname, permissive, roles, cmd, qual, with_check "
        "from pg_policies where schemaname = 'public' and tablename = any(%s)",
        (list(_SESSION_CRUD),),
    ).fetchall()
    observed_policies = {
        (table, name, permissive, tuple(roles), command, qual, check)
        for table, name, permissive, roles, command, qual, check in policies
    }
    if len(policies) != len(expected_policies) or observed_policies != expected_policies:
        raise RuntimeError("session runtime policies do not satisfy ADR-048")

    privileges = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
    if version >= 170000:
        privileges.append("MAINTAIN")
    for table, commands in _SESSION_CRUD.items():
        # Effective privileges include PUBLIC and inherited grants, unlike ACL inspection.
        effective = conn.execute(
            "select privilege, has_table_privilege(current_user, %s, privilege) "
            "from unnest(%s::text[]) as p(privilege)",
            ("public." + table, privileges),
        ).fetchall()
        if len(effective) != len(privileges) or dict(effective) != {
            privilege: privilege in commands for privilege in privileges
        }:
            raise RuntimeError("session runtime privileges do not satisfy ADR-048")


def verify_session_database(dsn: str) -> None:
    """Bounded, read-only startup check of the ADR-048 identity runtime boundary.

    No token rows, migrations or repairs. Require non-owner juval_backend,
    exact command policies/effective CRUD, columns and digest primary keys.
    Wider capability/default-privilege auditing belongs to Gate B2.
    Driver diagnostics may contain credentials: suppress them.
    """
    try:
        with _require_driver().connect(dsn, connect_timeout=5, autocommit=False) as conn:
            try:
                conn.execute("set transaction read only")
                conn.execute("set local statement_timeout = '5s'")
                if conn.execute("show transaction_read_only").fetchone() != ("on",):
                    raise RuntimeError("session readiness transaction is not read-only")
                _verify_session_runtime_boundary(conn)
                # Preserve the ADR-036 digest-key and column compatibility checks.
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
                        ("public." + table, column),
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
            finally:
                conn.rollback()
    except Exception:
        raise RuntimeError(
            "durable session database readiness failed; verify connectivity, migration, "
            "non-owner runtime role, effective CRUD and explicit RLS policies (ADR-048)"
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
    def __init__(self, dsn: str, cipher: TokenCipher, idle_timeout: timedelta = DEFAULT_IDLE_TIMEOUT) -> None:
        super().__init__(dsn, cipher)
        self._idle_timeout = idle_timeout

    @contextmanager
    def refresh_guard(self, session_id: str, wait: timedelta = timedelta(0)):
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
            if not acquired and wait > timedelta(0):
                _wait_for_refresher(conn, key, wait)
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
            # Check validity, idle timeout and record activity in ONE
            # statement: two concurrent requests cannot interleave a stale
            # check with a touch, and activity never moves backwards.
            params = {"digest": session_digest, "now": now, "idle": self._idle_timeout}
            row = conn.execute(
                """
                update identity_sessions
                   set last_seen_at = greatest(last_seen_at, %(now)s)
                 where session_digest = %(digest)s
                   and revoked_at is null
                   and expires_at > %(now)s
                   and last_seen_at > %(now)s - %(idle)s
             returning subject, roles, csrf_digest,
                       access_token_ciphertext, refresh_token_ciphertext,
                       access_token_expires_at, created_at, expires_at,
                       refresh_generation
                """,
                params,
            ).fetchone()
            if row is None:
                # An idle session is revoked, not merely refused, so neither a
                # clock correction nor a longer timeout can revive it.
                conn.execute(
                    """
                    update identity_sessions
                       set revoked_at = %(now)s,
                           access_token_ciphertext = null,
                           refresh_token_ciphertext = null
                     where session_digest = %(digest)s
                       and revoked_at is null
                       and last_seen_at <= %(now)s - %(idle)s
                    """,
                    params,
                )
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
                generation,
            ) = row

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
        roles: Optional[tuple] = None,
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
                       last_seen_at             = greatest(last_seen_at, %s),
                       roles                    = coalesce(%s::text[], roles),
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
                    list(roles) if roles is not None else None,
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


def revoke_sessions(dsn: str, now: datetime, subject: Optional[str] = None) -> int:
    """Operator revocation (SEC-01E): every live session, or every one of `subject`.

    Used before an issuer change (all) and when a person's roles change or
    they leave (one subject). Same effect as `revoke()`: the row stays for
    audit, the encrypted tokens are erased. Returns how many were revoked.
    """
    with _require_driver().connect(dsn, connect_timeout=5) as conn:
        cur = conn.execute(
            """
            update identity_sessions
               set revoked_at = %(now)s,
                   access_token_ciphertext = null,
                   refresh_token_ciphertext = null
             where revoked_at is null
               and (%(subject)s::text is null or subject = %(subject)s::text)
            """,
            {"now": now, "subject": subject},
        )
        return cur.rowcount or 0
