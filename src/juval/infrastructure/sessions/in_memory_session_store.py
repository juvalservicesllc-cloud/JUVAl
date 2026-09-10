"""In-memory adapters for `application/session_store.py`.

Scope, stated plainly: **one process only, and never production.** Sessions are
lost on restart and invisible to any other instance. ADR-036 permits this
adapter for unit tests, integration tests and single-process local development,
and forbids it in production; `interfaces/api/bff.py::build_stores` enforces
that by refusing to select it when durable storage is required.

These adapters obey the same digest-only contract as the PostgreSQL one: they
store `digest(session_id)`, never the id itself. That is not necessary for
security in a process-local dict -- it is necessary so the two adapters cannot
drift, and so a test that passes here means something about production.

Thread safety: FastAPI serves from a thread pool, so both stores take a lock.
The critical sections are `consume` (look-up and delete must be one step) and
`replace_tokens` (read-compare-write must be one step), for exactly the reasons
their port docstrings give.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from juval.application.session_store import (
    OAuthTransaction,
    OAuthTransactionRecord,
    Session,
    SessionRecord,
    digest,
)


@dataclass
class _StoredTransaction:
    record: OAuthTransactionRecord
    expires_at: datetime


@dataclass
class _StoredSession:
    record: SessionRecord
    revoked_at: Optional[datetime] = None


class InMemoryOAuthTransactionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, _StoredTransaction] = {}

    def start(self, transaction: OAuthTransaction) -> None:
        stored = _StoredTransaction(
            record=OAuthTransactionRecord(
                state_digest=digest(transaction.state),
                nonce_digest=digest(transaction.nonce),
                code_verifier=transaction.code_verifier,
                redirect_uri=transaction.redirect_uri,
                return_to=transaction.return_to,
            ),
            expires_at=transaction.expires_at,
        )
        with self._lock:
            self._items[digest(transaction.transaction_id)] = stored

    def consume(self, transaction_id: str, now: datetime) -> Optional[OAuthTransactionRecord]:
        with self._lock:
            stored = self._items.pop(digest(transaction_id), None)
        if stored is None or stored.expires_at <= now:
            return None
        return stored.record

    def purge_expired(self, now: datetime) -> int:
        with self._lock:
            stale = [k for k, v in self._items.items() if v.expires_at <= now]
            for k in stale:
                del self._items[k]
        return len(stale)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, _StoredSession] = {}

    def save(self, session: Session) -> None:
        record = SessionRecord(
            session_digest=digest(session.session_id),
            subject=session.subject,
            roles=tuple(session.roles),
            csrf_digest=digest(session.csrf_token),
            created_at=session.created_at,
            expires_at=session.expires_at,
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            access_token_expires_at=session.access_token_expires_at,
            refresh_generation=0,
        )
        with self._lock:
            self._items[record.session_digest] = _StoredSession(record=record)

    def load(self, session_id: str, now: datetime) -> Optional[SessionRecord]:
        key = digest(session_id)
        with self._lock:
            stored = self._items.get(key)
            if stored is None:
                return None
            if stored.revoked_at is not None or stored.record.expires_at <= now:
                # Removed on read rather than by a sweeper: no background task,
                # and an expired or revoked id can never be resurrected.
                self._items.pop(key, None)
                return None
            return stored.record

    def revoke(self, session_id: str, now: datetime) -> None:
        with self._lock:
            self._items.pop(digest(session_id), None)

    def replace_tokens(
        self,
        session_id: str,
        expected_generation: int,
        access_token: Optional[str],
        refresh_token: Optional[str],
        access_token_expires_at: Optional[datetime],
        now: datetime,
    ) -> bool:
        key = digest(session_id)
        with self._lock:
            stored = self._items.get(key)
            if stored is None or stored.revoked_at is not None:
                return False
            if stored.record.refresh_generation != expected_generation:
                return False  # a concurrent refresh already won
            import dataclasses

            stored.record = dataclasses.replace(
                stored.record,
                access_token=access_token,
                refresh_token=refresh_token,
                access_token_expires_at=access_token_expires_at,
                refresh_generation=expected_generation + 1,
            )
            return True

    def purge_expired(self, now: datetime) -> int:
        with self._lock:
            stale = [
                k
                for k, v in self._items.items()
                if v.record.expires_at <= now or v.revoked_at is not None
            ]
            for k in stale:
                del self._items[k]
        return len(stale)
