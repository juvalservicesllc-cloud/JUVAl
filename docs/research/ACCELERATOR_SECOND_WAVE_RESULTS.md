# Accelerator second-wave results — 2026-09-10

Status: PARTIALLY IMPLEMENTED / HARD_EXTERNAL_BOUNDARY. Eleven logical work
cycles: remote merge, portal preservation, dependency patch, session correctness,
ADR-038, browser semantics, database restart, measurement model, portal route
regression, operator procedures, final consolidation. No production completion.

Starting HEAD: `5e264a66d3cb60f1ef2e0281f84a7d38e74c11ae`.
Tested milestone: `1655688b1684f5bfe543da3bd82ca30cfc950f1b`.
This report is a documentation-only successor. Remote remains
`6a6d07c04c17cbf7e3714c32d3d2e1576d5ddf6a`; normal push failed twice with
Permission denied (publickey), no commits published. Current exact head is the
commit containing this report. Fresh HTTPS fetch confirms no remote-only work.
See ACCELERATOR_SECOND_WAVE_GIT.md for all initial hashes/author/date/file maps.
Remote merges 5c52451 and 880334c retain both remote commits, twelve initial local
commits and e91d7d8/29e90a6 portal commits. Portal branch remains reachable;
no orphaned useful work, no rebase/force/reset/history deletion.

## Final measured gates

| Gate | Result / scope |
|---|---|
| Backend | 834 PASS, 38 SKIP, 1 existing Starlette/httpx deprecation warning; full pytest with disposable nginx |
| PostgreSQL | 48 PASS, 2 memory-only SKIP; actual private cluster restart PASS; cleanup confirmed |
| Nginx | 90/90 PASS; echo-upstream lab only, not real hosted-login or production |
| Frontend | 155 PASS; lint/build PASS, existing chunk-size warning; Chromium PWA activation/control/offline shell PASS |
| Portal | 11 model + 4 component/i18n + 3 Python exporter PASS; lint/build PASS; 14 browser E2E PASS after correcting private-path fallback |
| Browser cookies | Synthetic same-site/cross-site/HttpOnly/host-only/top-level GET semantics PASS; no provider, TLS or real BFF |
| Dependency audit | Zero current npm advisories in all four lockfiles; installed Python pip-audit clean; private GitHub alert closure NOT_VERIFIED |
| Compliance | 9 PASS, 1 WARN (security-owner assignment), 0 FAIL; not Amazon approval |
| Frontend integrity | Only frontend/package-lock.json changed under explicit security exception; frontend-next/demo untouched |

Five unique advisories patched: fast-uri GHSA-5jgf-p345-68v8,
GHSA-f65p-4m7j-42xc, GHSA-fph4-wmhf-6fwf, GHSA-jqff-g426-hqxp;
Vitest GHSA-82fw-gwwq-j7x9. Targets 3.1.6 and 4.1.11, respectively.
No product source/UX changes. Deployment versions remain unverified.

## Independent evidence measurements

ADR-040, model 1.2, measured against tested milestone above using
`JUVAL_EVIDENCE_REF=<SHA> npm run sync` then `node scripts/measure.mjs`:

| Dimension | Earned / total weight | Rounded score |
|---|---|---|
| Implementation | 44/68 (31 criteria) | 65% |
| Verification | 18/68 (31 criteria) | 26% |
| Production readiness evidence | 0/12 (7 criteria) | 0% |
| Security readiness evidence | 6/16 (9 criteria) | 38% |
| Amazon readiness evidence | 0/18 (8 criteria) | 0% |

These are curated evidence credits, not measured live coverage, an estimate of
all commercial functionality, actual security effectiveness or Amazon approval.
Zero denotes no qualifying production evidence in the explicit scope. Actual
production coverage and achieved backup RTO/RPO remain NOT_MEASURED.

## Boundary and human action queue

1. Authenticate GitHub locally using the SSH agent; never share passphrase/key.
   Next: fresh fetch, verify remote-only=0, normal push and HEAD==origin/master.
2. Provide controllable authenticated FusionAuth Admin access or run the exact
   redirect procedure locally. Baseline NOT_ESTABLISHED, mutation NOT_EXECUTED,
   cleanup NOT_APPLICABLE; original restoration cannot be claimed. Real login
   NOT_VERIFIED, D-1 blocked, real nginx/FusionAuth integration NOT_EXECUTED.
3. Choose owned domain and identity tunnel/TLS responsibility. ADR-038 same-site
   app/api/id accepted; public hostname/issuer/TLS NOT_ESTABLISHED. N-1 lab fixed,
   N-3 partial (server_tokens off); other headers await actual hosted/MFA/logout.
4. Review/approve exact production migration packet with DB owner/pooler/backup
   preflight. Sessions IMPLEMENTED_TESTED_NOT_ACTIVATED. No live migration
   authorized. ADR-039 residual provider/DB crash atomicity requires re-login.
5. Authorize disposable RF03 identities and private password/TOTP session using
   compliance/IDENTITY_OPERATOR_CHECKPOINT.md. Runbook READY; execution NOT
   authorized. Control 6 PARTIALLY_SATISFIED, Amazon reapplication BLOCKED.
6. Assign security owner, off-host encrypted destination/key custody, retention
   acceptance and maintenance window. No backup transfer, reboot/apt/UFW/SSH
   changes, port opening, payment, destructive operation or Amazon submission.

All independent work above is committed. Further public compatibility work
requires the exact login evidence; publication and actual production gates need
the listed external actions. Business scoring/risk/source decisions remain pending.

## Cleanup and self-review

No temporary redirect change or production auth activation. FusionAuth PID369334,
NRestarts0 unchanged. Host listeners restored to initial inventory. Owned preview
servers, Chromium contexts, disposable PostgreSQL/nginx directories and E2E
scratch removed. Installed node_modules and ignored portal build/sanitized
snapshot counters remain intentional local tooling outputs. Raw JUnit removed
following counters-only export with exact tested SHA/environment.

Correctness: failures found by real tests fixed, no test weakened. Traceability:
immutable history and explicit evidence scopes retained. Reproducibility: clean
installs, disposable labs, metadata-only migration preflight and exact measurements.
Security: no secrets, new public routes or production changes; no inferred fact
promoted to VERIFIED. Simplicity: existing stdlib/store ports and Playwright;
no new dependencies. Ponytail unavailable; manual simplicity review performed.
