"""Structured security events (SEC-01E): the input for alerting.

One JSON object per line on the `juval.security` logger, so any log pipeline
can count and alert on them without an external service (none is contracted
yet). The vocabulary is closed: an unknown event or field is a programming
error, caught by the tests that exercise every emitting site.

Values are short classifications only -- never tokens, cookies, CSRF values,
DSNs, emails, roles lists or raw subjects. A subject is reduced to a stable
12-hex fingerprint: enough to see that one identity keeps failing, useless
for recovering who it is outside JUVAl's own records.

Alert rules over these events: docs/architecture/TENANCY_ACTIVATION_RUNBOOK.md §11.
"""

from __future__ import annotations

import hashlib
import json
import logging

logger = logging.getLogger("juval.security")

EVENTS = frozenset({
    "auth.token_rejected",          # a bearer/ID token failed verification
    "auth.jwks_unavailable",        # signing keys could not be fetched
    "session.store_unavailable",    # session store failed -> 503
    "session.ended",                # a session stopped authorizing (reason)
    "membership.store_unavailable",  # membership lookup failed -> 503
    "access.denied",                # rbac, csrf or tenant refusal
    "startup.failed",               # the instance refused to start (stage)
})

_FIELDS = frozenset({"reason", "kind", "permission", "subject_fp", "stage"})


def subject_fingerprint(subject: str) -> str:
    return hashlib.sha256(("juval-subject:" + subject).encode("utf-8")).hexdigest()[:12]


def emit(event: str, level: int = logging.WARNING, **fields: str) -> None:
    if event not in EVENTS or not set(fields) <= _FIELDS:
        raise ValueError(f"unknown security event or field: {event}")
    logger.log(level, json.dumps({"event": event, **fields}, sort_keys=True, separators=(",", ":")))
