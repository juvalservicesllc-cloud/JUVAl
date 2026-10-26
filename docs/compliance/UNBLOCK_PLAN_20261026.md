# Security, identity and Dependabot unblock plan — 2026-10-26

**Status: PLAN.** Nothing here activates, deploys, migrates or changes
production. It orders the remaining work and names who can do each step. The
detailed procedures already exist and are linked, not repeated:
[IDENTITY_SECURITY_READINESS.md](../IDENTITY_SECURITY_READINESS.md) (ledger),
[ACCESS_CONTROL.md](ACCESS_CONTROL.md), [NETWORK_SECURITY.md](NETWORK_SECURITY.md),
[deploy/fusionauth/README.md](../../deploy/fusionauth/README.md), ADR-034/036/038/041/042,
[DEPENDENCY_THIRD_WAVE_RECONCILIATION.md](DEPENDENCY_THIRD_WAVE_RECONCILIATION.md).
Measured at HEAD `4bb5764` in the isolated clone; ADR-040 44/68 · 17/68 · 0/12 · 5/16 · 0/18.

## 1. Evidence classes

### Confirmed in this clone (2026-10-26)

| # | Fact | Evidence |
|---|---|---|
| C1 | If `JUVAL_AUTH_MODE` is unset the API runs with **every endpoint unauthenticated** (default `disabled`, anonymous principal with all permissions) and logs a warning. | `auth.py::auth_mode`, `_ANONYMOUS`; `main.py` startup warning |
| C2 | `railway.toml` binds `0.0.0.0:$PORT` and sets no auth variable: the auth mode of the deployment lives only in Railway's variables. | `railway.toml` |
| C3 | CORS is an explicit allow-list (empty by default, never `*`) with credentials; cookies are `Secure` unless the exact local opt-out is set. | `main.py`, `service.cors_origins`, `bff._cookie_secure` |
| C4 | BFF contract tested: cookie session, CSRF double submit, distinct exact 403 bodies, CSRF guard runs before any handler side effect. | `tests/integration/test_api_bff.py` 40 passed at `4bb5764` |
| C5 | `frontend-next/` consumes that contract (credentials, CSRF, 401/403 handling). **`frontend/` — the production PWA under ADR-030 — sends no credential at all.** | `e0d748d`; `frontend/src` has no auth code |
| C6 | npm registry audits now report advisories in all four lockfiles, **all dev/build-time** (`npm audit --omit=dev` = 0 in each): vite (high, direct), source-map-js, undici, @vitest/mocker/vitest; `frontend/` also brace-expansion, fast-uri, serialize-javascript. This supersedes the 2026-09-10 "zero advisories" statement. | §2 of the dependency reconciliation, 2026-10-26 re-check |
| C7 | pip-audit of `.venv`: direct runtime deps clean (pyjwt 2.15.1, cryptography 50.0.2, python-multipart 0.0.32, fastapi 0.143.3); flagged `pip 24.0` (installer) and `certifi 2026.7.22` (transitive). | scratch-venv pip-audit, `-c constraints-audit.txt` |
| C8 | Listeners on `juval-server`: `0.0.0.0:22`, `0.0.0.0:631`, `*:9011`, `*:9012`; everything else loopback. UFW state is **not readable** by this user. | `ss -ltn`; matches the 2026-09-21 matrix in NETWORK_SECURITY.md |

### Documented historically, not re-verified

- Railway backend deployed 2026-08-18 at `https://juval-backend-production.up.railway.app`
  with `JUVAL_AUTH_MODE` unset; Vercel `frontend/` pointing at it; Supabase RLS
  fail-closed verified live 2026-08-18. ACCESS_CONTROL.md: "deployment variables
  were not reread in this recovery".
- FusionAuth installed on `juval-server` (loopback admin), tenant/app exist;
  real MFA preflight PASS, real MFA **not executed**; operator **MFA freeze** since 2026-09-18.

### Not verifiable from this environment

Whether the Railway service still runs, its current variables, whether Supabase
still holds run data, whether Vercel still points at it, and therefore whether
an unauthenticated public API exists **today**. No claim of current exposure is
made. The isolated clone has no Railway/Vercel/GitHub credentials and must not
probe production data endpoints.

## 2. Pending decisions

| ID | Decision | Owner | Source |
|---|---|---|---|
| D0 | What to do with the Railway deployment while auth is inactive (keep / restrict / suspend / purge synthetic data), once step 0 confirms its state | Operator | ACCESS_CONTROL §5, readiness "do not roll back to anonymous auth on a public deployment" |
| D1 | Issuer tunnel and domain: Cloudflare Tunnel (recommended, own domain) or Tailscale Funnel | Operator (account/domain) | fusionauth README §6, `HUMAN_DOMAIN_SELECTION_PENDING` |
| D2 | Exact app/api/id hosts, TLS issuance/renewal owner, logging policy | Operator + architecture | ADR-038 "Acceptance and consequences" |
| D3 | Which PWA receives users at activation: `frontend/` has no BFF client and would get 401 on every call; `frontend-next/` has it but is not at parity (GOLDEN 9/24) and has no logout/session indicator | User (ADR-030) | C5, ADR-030 §5 |
| D4 | Accept or reject ADR-041 (hosted MFA enrollment routes) and ADR-042 (restricted auth evidence controller) | Architecture | both `Propuesta` |
| D5 | Lift the MFA freeze for one bounded real experiment | Operator | readiness 2026-09-18 |
| D6 | Authorize the ADR-036 live session-store migration (Supabase PostgreSQL + keyring) | Operator | Fase 8/9 gates, `BLOCKED_LIVE_AUTHORIZATION` |
| D7 | Control 6 residual acceptance for Amazon | Operator / compliance | ADR-035 |
| D8 | Authorization to update dev-tool lockfiles in frozen `frontend/` and immutable `demo/` (or to accept dev-only advisories there) | User | CLAUDE.md freeze, ADR-030 |

## 3. Dependabot — exact input needed

The six operator-reported alerts cannot be read here (no `gh`, the remote is a
local bundle, the public API answers 401). Export them once; the output contains
no secret. From a machine where `gh` is logged in with **Dependabot alerts: read**
(fine-grained) or `security_events` (classic):

```bash
gh api -H "Accept: application/vnd.github+json" --paginate \
  "/repos/juvalservicesllc-cloud/JUVAl/dependabot/alerts?state=open&per_page=100" \
  --jq '.[] | [.number, .state, .security_advisory.ghsa_id, (.security_advisory.cve_id // "-"),
               .dependency.package.ecosystem, .dependency.package.name, .dependency.manifest_path,
               .dependency.scope, .security_vulnerability.vulnerable_version_range,
               (.security_vulnerability.first_patched_version.identifier // "none"),
               .security_advisory.severity] | @tsv' > dependabot-open.tsv
```

Without `gh`: GitHub → Security → Dependabot → each open alert, copying the same
fields. Never paste a token. One row per alert:

| Field | Example (format only) |
|---|---|
| Alert number | `17` |
| State | `open` |
| GHSA | `GHSA-xxxx-xxxx-xxxx` |
| CVE | `CVE-2026-NNNNN` or `-` |
| Ecosystem | `npm` / `pip` |
| Package | `vite` |
| Manifest | `frontend-next/package-lock.json` |
| Scope | `development` / `runtime` |
| Vulnerable range | `>= 8.2.0, < 8.2.3` |
| First patched | `8.2.3` or `none` |
| Severity | `high` |

Then Claude maps each row to the local audits (C6/C7), classifies
runtime vs dev, proposes the minimal lockfile/floor change per manifest, runs the
affected app's typecheck/tests/build and both audits, and records the result in
the dependency reconciliation document. Frozen manifests wait for D8.

## 4. Ordered plan

| Step | Who | Action | What proves it | ADR-040 criteria that could move (never automatic) |
|---|---|---|---|---|
| 0 | Operator (read-only) | Confirm the deployment: `railway status`; `railway variables --kv \| cut -d= -f1` (names only) and `railway variables --kv \| grep '^JUVAL_AUTH_MODE='`; `curl -s -o /dev/null -w '%{http_code}\n' https://juval-backend-production.up.railway.app/api/v1/runs` (200 = public unauthenticated read; 401 = auth on; other = down). Same for the Vercel URL. Then decide D0. | Dated readback in the ledger | none directly; resolves the unknown in §1 |
| 1 | Operator | Export the six Dependabot alerts (§3) | `dependabot-open.tsv` | — |
| 2 | Claude (isolated) | Reconcile alerts; remediate unfrozen manifests (`project-portal/`, and `frontend-next/` dev tools if authorized); re-audit; document | audits + affected test/build | `dependency-remediation` (2) |
| 3 | User / architecture | D1, D2, D3, D4, D7 | ADR updates with `Aceptada` and exact hosts | none directly |
| 4 | Claude (isolated) | Only after D3: the chosen PWA's missing auth pieces (frontend-next: session indicator and logout via `POST /api/v1/auth/logout` + `end_session_url`) — needs a frontend authorization beyond the A/B/C lift | component tests + lab API in `oidc` mode with seeded sessions | none alone |
| 5 | Operator + external | Domain/tunnel, TLS; `configure_fusionauth.py --issuer https://<public>`; outside probes in fusionauth README §6 | JWKS reachable; `/admin` and `/api/status` 404 from outside | `issuer` (2) |
| 6 | Operator | D5: lift freeze for one bounded experiment; real hosted login + MFA enrollment/challenge through the public surface; per-user MFA enrollment report; lockout on a test account | `verify_oidc.py --tenant-policy`, enrollment report, human readback | `identity-runtime` (3), `rf-03` (3) |
| 7 | Operator | D6: run `session_migration_preflight.py`, apply the reviewed ADR-036 migration, verify role/RLS denial | preflight PASS + RLS negative from unprivileged role | prerequisite for 8 |
| 8 | Operator | Activate: `JUVAL_AUTH_MODE=oidc` + exact `JUVAL_CORS_ORIGINS` + BFF vars on Railway; deploy the D3 PWA | `verify_rbac.py --backend <url>`; ADR-038 browser matrix (Lax cookie, credentialed reads/writes, hostile-origin and CSRF negatives, expiry, logout, upload/download) | `rf-04` (2), `control-6` (2), `rf03-behavior` (2); unblocks the Fase 4 universal-gate item 5, so `pwa-gate` (2) can then be evaluated |
| 9 | Operator | Governance track: Deputy availability, formal review (kept for 2027-02-18), RF-02 workstation/CUPS items, public ingress/TLS/logging evidence | ledger records | `rf-01`, `rf-02`, `rf-05` (6) |
| 10 | External | Amazon reapplication only after 0–9 | Amazon decision | `amazon-approval` (3) |

Production readiness (0/12) and Amazon readiness (0/18) need
`PRODUCTION_VERIFIED` evidence by design; lab, tabletop and synthetic results
never earn them.

## 5. Reversibility and risks

- Step 8 is reversible by setting `JUVAL_AUTH_MODE=disabled` (fusionauth README §7),
  but that restores an **unauthenticated** API; on a public deployment the
  rollback is to restrict or suspend access instead.
- Activating auth while `frontend/` serves users breaks every request (C5) — D3 first.
- Session-store rollback loses all sessions; never restore old live sessions.
- Dev-tool advisories (C6) affect developers running dev servers; keep dev
  servers on loopback (as `frontend-next/README.md` does).
