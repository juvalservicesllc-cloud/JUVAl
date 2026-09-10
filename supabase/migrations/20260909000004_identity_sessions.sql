-- Juval — identity sessions and OAuth transactions (ADR-036, ADR-034)
--
-- Deliberately SEPARATE from execution_runs / execution_run_records /
-- batches. Those tables are the audit trail of the product's domain
-- (ADR-013/ADR-017/ADR-019); these two are identity infrastructure. Mixing
-- them would couple a security-lifecycle table to a domain-persistence
-- lifecycle, and would make "delete a user's sessions" and "delete a run"
-- the same kind of operation, which they are not.
--
-- NOT YET APPLIED to any live Supabase project. This file documents the
-- schema; applying it requires `supabase db push` / `supabase migration up`
-- or the SQL editor of an actual project. See docs/architecture/SUPABASE.md.
--
-- WHAT IS DELIBERATELY NOT STORED HERE
--   * the raw session id            -- only its SHA-256 digest (see below)
--   * the raw CSRF token            -- only its digest
--   * the raw OAuth `state`/`nonce` -- only their digests
--   * access / refresh tokens in plaintext -- AES-256-GCM ciphertext only
--   * passwords, TOTP secrets       -- JUVAl never receives or stores these
--   * full ID-token claims          -- `subject` and `roles` are all the
--                                      authorization decision needs
--
-- WHY DIGESTS AND NOT THE VALUES
-- The session id the browser presents is a bearer credential: whoever holds
-- it is the user. Storing it verbatim means a single SELECT on this table is
-- a session-hijacking kit. Storing SHA-256 makes the table useless for
-- impersonation while remaining exactly as lookupable, because the server
-- hashes the presented id and looks up the digest. A plain SHA-256 (not a
-- password hash) is correct here: these ids are 256 bits of CSPRNG output, so
-- there is no dictionary to attack and no need for a slow KDF.
--
-- WHY CIPHERTEXT AND NOT "SUPABASE ENCRYPTS AT REST"
-- Encryption at rest protects the disk, not the table. Anything that can read
-- the row -- a leaked connection string, an over-broad role, a backup, a
-- support query -- would hold live OAuth tokens. The key lives only in the
-- backend's environment and never in this database (ADR-036).

create table if not exists identity_sessions (
    -- SHA-256 (hex) of the session id carried in the juval_session cookie.
    session_digest            text        primary key,
    subject                   text        not null,
    roles                     text[]      not null default '{}',
    -- SHA-256 (hex) of the CSRF token carried in the juval_csrf cookie.
    csrf_digest               text        not null,
    -- AES-256-GCM envelopes: 'v1.<key_id>.<nonce>.<ciphertext||tag>'.
    access_token_ciphertext   text,
    refresh_token_ciphertext  text,
    -- Which key produced the ciphertext. An identifier, never key material;
    -- it exists so rotation progress is observable in SQL.
    crypto_key_id             text,
    access_token_expires_at   timestamptz,
    created_at                timestamptz not null,
    last_seen_at              timestamptz not null,
    expires_at                timestamptz not null,
    revoked_at                timestamptz,
    -- Optimistic-concurrency counter for refresh-token rotation. Two
    -- concurrent refreshes both read generation N; only one UPDATE with
    -- `where refresh_generation = N` can succeed, so the loser retries and
    -- reads the winner's token instead of overwriting it.
    refresh_generation        integer     not null default 0
);

comment on table identity_sessions is
    'Server-side BFF sessions (ADR-034/ADR-036). Session id and CSRF token are '
    'stored as SHA-256 digests; OAuth tokens as AES-256-GCM ciphertext whose key '
    'never enters this database.';

-- Cleanup and expiry sweeps scan by time, never by subject.
create index if not exists identity_sessions_expires_at_idx
    on identity_sessions (expires_at);

create table if not exists identity_oauth_transactions (
    -- SHA-256 (hex) of the id carried in the juval_oauth_txn cookie.
    transaction_digest        text        primary key,
    -- SHA-256 (hex) of the OAuth `state`. Compared digest-to-digest.
    state_digest              text        not null,
    -- SHA-256 (hex) of the OIDC `nonce`, compared against the id_token claim.
    nonce_digest              text        not null,
    -- The PKCE verifier IS a secret and is encrypted, not digested: the
    -- token exchange needs its plaintext value.
    code_verifier_ciphertext  text        not null,
    crypto_key_id             text,
    redirect_uri              text        not null,
    return_to                 text,
    created_at                timestamptz not null,
    expires_at                timestamptz not null
);

comment on table identity_oauth_transactions is
    'In-flight Authorization Code + PKCE exchanges (ADR-034). Single-use: the '
    'callback consumes a row with DELETE ... RETURNING, so a replayed callback '
    'finds nothing. Rows live minutes, not hours.';

create index if not exists identity_oauth_transactions_expires_at_idx
    on identity_oauth_transactions (expires_at);

-- Row Level Security: enabled with NO policies, on purpose.
--
-- Unlike execution_runs, this is not "we have no user identity to write a
-- policy against yet". It is permanent: **no browser, and no Supabase anon or
-- authenticated API key, may ever read these tables.** The only legitimate
-- client is the JUVAl backend connecting as the database owner over a direct
-- PostgreSQL connection, which bypasses RLS by design. Enabling RLS with zero
-- policies makes the PostgREST surface fail closed, so an accidentally
-- exposed anon key cannot become a session dump.
--
-- DEPLOYMENT PRECONDITION, verified 2026-09-10 against a disposable
-- PostgreSQL 16.15 cluster: `FORCE ROW LEVEL SECURITY` is deliberately NOT
-- set, because the table owner must keep bypassing RLS -- that owner is the
-- backend, and it is the only legitimate reader. The corollary is a
-- requirement on the connection string: **JUVAL_SESSION_DB_URL must connect as
-- the role that owns these tables.** A narrower role would be refused every
-- row by the zero-policy RLS and every login would fail closed. Adding a
-- policy to work around that would defeat the purpose of the table.
alter table identity_sessions          enable row level security;
alter table identity_oauth_transactions enable row level security;
