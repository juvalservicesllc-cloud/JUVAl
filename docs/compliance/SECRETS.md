# JUVAl — Credential and Secret Management

| Field | Value |
|---|---|
| Status | **DESIGN + PARTIAL IMPLEMENTATION.** Storage/rotation processes are documented; several depend on infrastructure that is not deployed yet. |
| Last verified | `2026-08-18` |
| Owner | `ROLE PLACEHOLDER — Security Owner` (see `INCIDENT_RESPONSE_PLAN.md` §2) |
| Related controls | `AC-04B`, `AC-04C`, `AC-08`, RF-03 (programmatic half) |

Amazon's RF-03 covers two structurally different things that must never be
conflated: **human passwords** and **programmatic credentials**. Human
identity is owned by the managed IdP (ADR-022, `ADR-021` ownership matrix
items 1–13). *This* document owns everything else: API keys, tokens, database
credentials and deployment credentials, which rotate through infrastructure
processes and are never subject to password composition rules.

---

## 1. Credential inventory

Five classes, deliberately kept separate. A compromise of one must not imply a
compromise of another.

| # | Class | Examples | Where it lives | Rotation | Exists today? |
|---|---|---|---|---|---|
| 1 | **Human identity** | Operator passwords, MFA enrollments | Managed IdP only (ADR-022) | IdP policy: max 365 days, min 1 day | NO — no IdP tenant yet |
| 2 | **SP-API credentials** | `JUVAL_SP_API_LWA_CLIENT_ID`, `..._CLIENT_SECRET`, `..._REFRESH_TOKEN` | Backend-only secret store | **≤12 months** and immediately on compromise (DPP §1.4.2) | **NO** — registration is `REJECTED_REMEDIATION_REQUIRED`; no credential has ever been issued |
| 3 | **Database credentials** | `JUVAL_SUPABASE_DB_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Backend-only secret store / provider dashboard | ≤12 months and on compromise | Provider-side; project exists |
| 4 | **Deployment credentials** | Railway token, Vercel token, GitHub PAT / deploy keys | Provider account, protected by provider MFA | ≤12 months and on operator offboarding | Provider-side |
| 5 | **Service identities** | Future worker/queue identity; the scheduled-job identity if one is ever introduced | Backend-only secret store, scoped per environment | ≤12 months | NO — not implemented |

`SUPABASE_ANON_KEY` and `SUPABASE_URL` are **not** secrets: they are public by
design and protected by Row Level Security. They are listed in `.env.example`
as public precisely so nobody "protects" them and, by symmetry, assumes the
service-role key is equally safe to expose. It is not.

---

## 2. Hard rules

These are non-negotiable (`CLAUDE.md` §16):

1. **No secret in Git, ever.** `.gitignore` excludes `.env`; `.env.example`
   contains names and comments only, never values.
2. **No secret in the frontend.** No `VITE_*` variable may carry a backend
   secret. A Vite build inlines these into JavaScript served to the browser —
   `VITE_SUPABASE_SERVICE_ROLE_KEY` would publish the key to every visitor.
   Only `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` and `VITE_API_BASE_URL`
   are permitted, and all three are public values.
3. **No secret in logs, URLs or error messages.** See §4.
4. **No secret in an incident record, evidence artifact, ticket or chat.**
   Record the credential's *name* and its rotation timestamp, never its value.
5. **No secret hardcoded in source.** Configuration comes from the
   environment.
6. **The backend never needs a client secret to validate a token.** It
   verifies signatures with the IdP's *public* JWKS (`auth.py`). There is no
   IdP secret in the backend at all.

---

## 3. Configuration and fail-fast behavior

Every secret-bearing setting is read from the environment and validated at
startup. A missing or malformed value is a **startup error**, never a silent
fallback to a less secure mode:

| Setting | Enforced by | Failure behavior |
|---|---|---|
| `JUVAL_AUTH_MODE` | `interfaces/api/auth.py::auth_mode` | Unrecognized value raises `RuntimeError` |
| `JUVAL_OIDC_ISSUER` / `JUVAL_OIDC_AUDIENCE` | `auth.py::build_verifier` | Missing in `oidc` mode raises `RuntimeError` — never degrades to unauthenticated |
| `JUVAL_EXECUTION_STORE` | `interfaces/api/main.py::_execution_run_store` | Unrecognized value, or missing connection variable for the selected mode, raises `RuntimeError` — never silently switches store |
| `JUVAL_SUPABASE_DB_URL` | Same | Required when `supabase` is selected |

This "explicit selector wins, missing dependency is fatal" pattern is
deliberate: a stray variable inherited from a developer `.env` must never be
able to redirect production to a different store or turn authentication off.
It is covered by `tests/unit/test_execution_store_selection.py` and
`tests/integration/test_api_auth.py`.

### Production configuration (required)

| Variable | Required production value |
|---|---|
| `JUVAL_AUTH_MODE` | `oidc` — **an unauthenticated deployment cannot satisfy RF-03/RF-04** |
| `JUVAL_EXECUTION_STORE` | `supabase` (explicit; never rely on legacy inference) |
| `JUVAL_CORS_ORIGINS` | The exact deployed frontend origin. Never `*` |

---

## 4. Redaction

The API must never emit a credential into a log line or an HTTP response:

- The unhandled-exception handler logs the request **method and path only**
  and returns a generic `{"detail": "internal server error"}` — a stack trace
  or raw exception is never returned to the caller.
- Token verification failures log the **exception type name only**
  (`ExpiredSignatureError`, `InvalidAudienceError`), never the token, and
  return a deliberately non-specific `invalid or expired token` so the API is
  not an oracle telling an attacker *which* part of their forged token to fix.
- Authorization denials log subject, required permission and role names —
  identifiers, never credentials.
- `tools/compliance_check.py` scans the whole tree for secret-shaped strings
  on every run and in CI.

Regression cover: `tests/integration/test_api_auth.py::test_token_value_never_appears_in_logs`.

---

## 5. Rotation and revocation

| Trigger | Action | Deadline |
|---|---|---|
| Scheduled | Rotate every credential in classes 2–5 | ≤12 months (DPP §1.4.2) |
| Suspected compromise | Rotate immediately; open an incident (`INCIDENT_RESPONSE_PLAN.md` T-01/T-02) | Immediately |
| Operator offboarding | Revoke IdP account and every provider credential the operator could reach | **≤24 hours** (DPP §1.2.3) |
| Provider breach notice | Rotate everything held by that provider | Within 24 h of notice |

Rotation evidence records the credential name, rotation timestamp, who
performed it, and confirmation that the previous value no longer works —
never the value itself.

### Rotation log

| Date | Credential (name only) | Rotated by | Previous value confirmed dead? |
|---|---|---|---|
| — | *No credential has been issued or rotated yet.* | — | — |

---

## 6. Access boundaries

| Who / what | May access |
|---|---|
| Backend runtime (Railway) | Classes 2, 3, 5 via environment; never class 1 or 4 |
| Frontend (Vercel/browser) | Public values only — `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` |
| Operator (human) | Class 1 (their own). Provider consoles per job function; not every operator needs deployment credentials |
| CI (if introduced) | Only credentials required for the specific job, scoped per environment |
| The agent (Claude/Codex) | **None.** No credential value is read, requested, printed or stored by automation |

---

## 7. Current state and gaps

| Item | State |
|---|---|
| `.env` excluded from Git | **IMPLEMENTED** — `.gitignore` |
| `.env.example` has names/comments only, no values | **IMPLEMENTED + VERIFIED** by secret scan |
| Automated secret scanning | **IMPLEMENTED** — `tools/compliance_check.py`, run in tests |
| Fail-fast configuration | **IMPLEMENTED + TESTED** |
| Redaction in logs | **IMPLEMENTED + TESTED** |
| SP-API credential lifecycle | **NOT APPLICABLE YET** — no credential exists; becomes live on reapplication approval |
| Backend-only production secret store | **VERIFIED 2026-08-18** — Railway deployed; `JUVAL_SUPABASE_DB_URL` set via `railway variable set --stdin` (never appeared as a CLI argument or in command output); confirmed present on the service by key name only (`railway variable list --json` piped through a script that prints keys, never values); confirmed absent from the Vercel project (`vercel env ls` shows only `VITE_API_BASE_URL`) and absent from the built frontend bundle (0 matches for `postgres://`/`supabase`/`service_role`) |
| Rotation records | **NONE** — nothing rotated yet; the production DSN has been live since 2026-08-18 and is due for rotation on the standard ≤12-month cadence (§5) |
| Provider MFA on Railway/Vercel/Supabase/GitHub accounts | **NEEDS_VERIFICATION — EXTERNAL USER ACTION** (§8). Attempted via `gh api user --jq .two_factor_authentication` — GitHub no longer reliably exposes this field via the API; inconclusive, not fabricated. Railway/Vercel CLIs expose no account-level MFA introspection. |

## 8. EXTERNAL USER ACTION REQUIRED

| # | Action | Status |
|---|---|---|
| S-1 | Confirm MFA is enabled on the Railway, Vercel, Supabase and GitHub accounts, and record the date (no screenshots containing tokens) | **OPEN** — not verifiable via CLI (see above) |
| S-2 | Enable GitHub secret scanning and push protection on the repository | **DONE — verified 2026-08-18**: `gh api repos/.../JUVAl` → `security_and_analysis.secret_scanning.status = "enabled"`, `secret_scanning_push_protection.status = "enabled"`. Both were already on; this item is closed, not merely re-stated. |
| S-3 | Confirm no historical commit contains a secret (the scanner covers the working tree, not full history) | **OPEN** — not attempted this session; GitHub secret scanning (S-2) covers the pushed history going forward but was not used here to retroactively audit the full commit history |
| S-4 | On first deployment, set `JUVAL_EXECUTION_STORE=supabase` explicitly | **DONE 2026-08-18** — deployed with `JUVAL_EXECUTION_STORE=supabase`. **`JUVAL_AUTH_MODE=oidc` was deliberately NOT set** — the original wording of this item bundled it with the store selector, but enabling OIDC auth without an approved IdP tenant would break every endpoint and contradicts the standing identity block (ADR-021/ADR-022, `IDP_SELECTION = BLOCKED_PENDING_AMAZON_RESPONSE`); corrected here so this item is never read as authorizing that. |
| S-5 *(new)* | Enable GitHub Dependabot security updates (currently `disabled` — `NETWORK_SECURITY.md` §3.2) | **OPEN** |
