# ADR-039 — Exclude overlapping provider refresh requests

**Estado: Aceptada. Fecha: 2026-09-10.** Authority: accelerator authorization to
correct session concurrency and failure behavior before activation. Complements
ADR-034/036; no live migration or production activation authorized.

## Context

Generation CAS protects the database write, but previously two callers could
send the same rotating refresh token before either write completed. A provider
rejection could revoke the winner's session. Existing sequential CAS tests did
not exercise overlapping network requests. HTTP 429/5xx were also incorrectly
classified as permanent refresh rejection.

## Decision

Add a nonblocking refresh guard to the session store port. Memory uses a bounded
active-key set (removed in finally), under its existing mutex. PostgreSQL uses
transaction-scoped `pg_try_advisory_xact_lock` with a stable namespaced signed
64-bit digest. A collision only delays renewal, never grants authentication.
The transaction stays open for the provider call and releases on exit/error.
Busy callers skip refresh; they still load the normal authenticated session.
Reload inside the guard, before network I/O, so stale generations never replay
a token. Preserve conditional writes, reject expired/revoked rows, and preserve
logout during refresh. A guard/database error fails closed before provider I/O.
All runtime PostgreSQL connection attempts now use connect_timeout=5; guard SQL
has a five-second statement timeout. No schema change or extra dependency.

HTTP 429 and 5xx preserve the current session as a temporary provider failure;
other HTTP errors retain the existing rejection policy. Never log response bodies.

## Consequences

One additional PostgreSQL connection/transaction per due refresh, not per fresh
authenticated read. Nonblocking contention avoids a queue of waiting refreshes.
Deployment must allow transaction-scoped advisory locks and size connections for
concurrent due refreshes plus ordinary store operations. Validate through the
actual DB endpoint; do not assume every pooler has identical semantics.

Provider rotation and DB persistence cannot be atomic. Process failure after
rotation can lose the new token; a later permanent rejection requires login.
Loss of the guard connection during a provider request can release exclusion
before that request finishes. These are residual distributed-failure modes, not
claims of exactly-once OAuth. Monitor sanitized failures and require re-login;
never silently activate anonymous auth. A provider timeout is a socket timeout,
not a proven end-to-end deadline. No pooling optimization without load evidence.

## Verification

Deterministic overlapping-call test with Events asserts one provider request;
stale-generation follow-up never replays. Shared memory/PostgreSQL contract
verifies exclusion across independent store instances, independent session
progress, exception cleanup and expired-write refusal. Logout during refresh
cannot resurrect a session. HTTP 429/500/502/503/504 retain the session.
Disposable PostgreSQL evidence is separate from live Supabase and FusionAuth
behavior. Public production behavior remains NOT_VERIFIED.

Primary reference: [PostgreSQL 16 advisory locks](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS), checked 2026-09-10. Transaction locks release at transaction end; this does not make external HTTP atomic.

Follow-up lab: tools/session_store_lab.py now performs an actual fast restart of
its private PostgreSQL cluster after saving/revoking synthetic sessions and
consuming an OAuth transaction. A new adapter after restart observes the live
session, rejects the revoked session and refuses transaction replay. PASS on
2026-09-10; private cluster and synthetic artifacts removed. This does not
substitute for a deployment restart/pooler test.
