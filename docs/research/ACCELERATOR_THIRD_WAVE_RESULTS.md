# Third-wave checkpoint — 2026-09-10

Status: PARTIALLY IMPLEMENTED / external dependencies remain. Seven logical
cycles: durable checkpoint, dependency reconciliation/support floors, executable
preflight, re-login recovery, digest-key readiness, portal evidence, consolidation.

Starting HEAD b338a675be21aabeeeee957acb8884366e2ca115 was independently verified
by authenticated SSH fetch, equal to origin/master at 0/0. The existing locally
authenticated SSH agent was reused; no key/passphrase/token was read, no transport
or SSH configuration changed. Six work commits were pushed normally through
18d207d5231b4028cb8cd27f5d23ee40d9342350 and fetched back at 0/0. This report is
a documentation-only successor; its final Git hash identifies the final checkpoint.

## Work completed and evidence

- df1d2ab: exclude audited vulnerable Python support floors; keep the six-alert
  GitHub discrepancy open. Four npm lockfile audits and installed Python audit
  pass. Direct minimums: multipart0.0.31, PyJWT2.13.0, cryptography50.0.0,
  pytest9.0.3. Separate 23-row allowed-range inventory is NOT the six GitHub alerts.
- f9bc89a: read-only session migration preflight; offline SQL hashes, explicit
  target/backup/pooler/admission gaps; optional bounded metadata check only.
- ade11b1: synthetic HTTP recovery after provider rotation followed by failed
  persistence; refusal revokes old session and fresh login creates a different one.
- 487daeb: startup rejects absent/deferrable digest primary keys in both identity
  tables, without changing migrations or repairing databases.
- e143c82: portal dependency criterion PARTIAL/NOT_VERIFIED until GitHub alert
  metadata is reconciled; regression test prevents retained complete credit.
- 18d207d: canonical status/contracts synchronized; frontend frozen.

Full backend at published 18d207d: **839 PASS / 42 SKIP**, one existing
Starlette/httpx deprecation warning. Corrected-minimum venv full gate passed
839/38 before four additional PostgreSQL-only cases; its final focused PostgreSQL
lab passed **52/2** including those cases. Main PostgreSQL also **52 PASS / 2 SKIP**,
plus actual private cluster restart PASS. All lab clusters removed.

Frontend **155 PASS**, lint/build and Chromium built-PWA service-worker/offline
smoke PASS. No frontend/frontend-next/demo file changed in this wave. Existing
bundle-size warning preserved. Portal **12 model + 4 component/i18n + 3 exporter
PASS**, lint/build PASS; browser E2E not rerun this wave because UI/server behavior
was unchanged (prior 14/14 remains dated evidence, not a new result).

Compliance **9 PASS / 1 WARN / 0 FAIL**; warning is unassigned security owner.
Installed Python and final four exact minimum-version audits clean. The whole
private environment audit initially found outdated bootstrap pip24; updating only
that disposable installer to26.2.0 removed known package advisories, while the
local JUVAl package itself is not a PyPI-auditable dependency. No system install,
production environment upgrade or global security-clean claim.

## ADR-040 measurement

Executed model1.2 against published18d207d after counters-only JUnit export with
that exact tested commit/environment. Weights/scopes unchanged; new unresolved
GitHub evidence reduces dependency credit:

| Dimension | Earned/total | Rounded score |
|---|---|---|
| Implementation | 43/68 | 63% |
| Verification | 16/68 | 24% |
| Production readiness evidence | 0/12 | 0% |
| Security readiness evidence | 4/16 | 25% |
| Amazon readiness evidence | 0/18 | 0% |

Repository evidence scores only; not measured live coverage or Amazon approval.
Reproduce with `JUVAL_EVIDENCE_REF=<commit> npm run sync` and
`node scripts/measure.mjs` in project-portal. No informal percentages reused.

## Remaining hard boundaries

1. GitHub: operator reports6 alerts (4high/2moderate); unauthenticated Dependabot
   API returns401. Exact IDs/packages/manifests/ranges/fixes/states unknown.
   Obtain the six non-secret alert records; never request credentials. Do not
   infer closure from clean npm/pip or absence of warning on a Git push.
2. FusionAuth: no authenticated controllable Admin session established. Exact
   tenant/client existence reverified read-only; real login NOT_VERIFIED,
   redirect baseline NOT_ESTABLISHED, experiment NOT_EXECUTED, restoration
   NOT_APPLICABLE. No temporary redirect added, no credentials submitted.
   D-1 and real nginx/FusionAuth loopback compatibility remain blocked.
3. N-1 remains lab-verified; N-3 partial server_tokens off. Actual hosted/MFA/logout
   evidence required before further headers/allow-list. No public nginx/TLS/HSTS
   or speculative per-IP OAuth limits. ADR-038 accepted same-site subdomains;
   actual owned domain/tunnel/TLS responsibility remains human-selected.
4. Sessions implemented/tested, not activated. Live migration NOT authorized;
   executable preflight and one-shot operator checklist prepared. RF03 runbook
   READY, execution NOT authorized; Control6 PARTIALLY_SATISFIED. Private human
   password/TOTP and disposable-user approval remain required for behavior.
5. Off-host destination, recovery-key custody, security owner and maintenance
   window remain external. Backup/monitor service exit success was observed,
   not interpreted as restore proof or achieved RTO/RPO. No transfer/restore.

## Self-review and cleanup

Both portal commits remain contained in HEAD and origin/master; provenance
branch preserved. Frontend diff empty. FusionAuth MainPID369334/NRestarts0
unchanged; final listeners match baseline. Preview browser/server, private venv,
nginx package extraction and PostgreSQL scratch removed; raw JUnit removed after
sanitized counter export. Intentional ignored portal snapshots/builds remain.
No live migration/auth activation, production user, RF03, DNS/TLS activation,
UFW/SSH/reboot/apt upgrade, Amazon submission, secret collection or destructive Git.

Failures surfaced rather than hidden: candidate crypto49 and bootstrap pip24
failed audits and were corrected; GitHub alert metadata remains explicitly
unresolved. Linux/Python3.12 validation does not prove every platform or every
transitive resolution permitted by package ranges. No direct deployment command was issued; Git-connected portal delivery may run
from pushes, and hosted delivery/protection was not independently reverified.
No tests weakened. Existing
ports/checks reused; Ponytail unavailable, manual simplicity review performed.
