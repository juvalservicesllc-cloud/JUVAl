# JUVAl identity/security — current readiness and operator runbook

**2026-09-10 accelerator fifth wave. Status: PARTIALLY IMPLEMENTED.** Authoritative
workspace: `/home/juval/JUVAl/APP`. This ledger supersedes dated implementation
snapshots in project plans, contracts and research; historical experiments are
not reclassified as production evidence. Git commits identify the exact changes.

## Evidence ledger

| Claim | Classification | Evidence / confidence |
|---|---|---|
| Starting repository | VERIFIED_LOCAL | `16189b7`, clean, cached origin `32c3aef`, local 0/3; high |
| Durable Git checkpoint | VERIFIED via authenticated SSH fetch | `b338a67` matched origin/master 0/0 at third-wave resume; subsequent commits use normal gated pushes |
| Exact tenant/application IDs exist | VERIFIED_RUNTIME_READ_ONLY | 2026-09-10 public controls: tenant 200 vs four 500 controls; real client invalid_redirect_uri vs random invalid_client_id; high for existence only |
| Tenant/application names and role names | NOT_REVERIFIED | Admin readback not available; never recreate existing objects |
| Real login surface | INITIAL_LOGIN_BEHAVIORALLY_VERIFIED / RUNTIME_LOOPBACK_VERIFIED | Real Chromium render and nginx GET probes; exact redirect restoration verified; docs/research/REAL_JUVAL_LOGIN_20260910.md |
| BFF/session store | IMPLEMENTED_TESTED_NOT_ACTIVATED | ADR-034/036; startup readiness and revoked-session projection corrected |
| N-1 | REMEDIATED_TEMPLATE / LAB_BEHAVIOURALLY_VERIFIED | ADR-037; relative 301, query retention, no upstream contact; 90 nginx tests |
| D-1 / final asset allow-list | PARTIAL | Initial render verified; MFA/WebAuthn/fonts remain open; hosted recovery explicitly excluded by ADR-035; see FUSIONAUTH_D1_FIFTH_WAVE.md |
| N-3 | PARTIAL | nginx version suppressed; four header candidates pass generic-provider render only; real MFA/WebAuthn/frame compatibility remains open |
| Public TLS/hostname/issuer | NOT_ESTABLISHED | ADR-031 approved network boundary; actual names/provider pending |
| Browser site topology | APPROVED_SAME_SITE_SUBDOMAINS | ADR-038 accepted; Chromium semantics lab passed; actual domain/public browser flow pending |
| Control 6 / RF03 / Amazon | PARTIALLY_SATISFIED / NOT_EXECUTED / BLOCKED | Code/tests and isolated provider lab cannot prove effective production behavior |
| SEC-DEPS-01 | DISCREPANCY_OPEN | Six GitHub alerts reported (4 high/2 moderate), exact metadata unavailable (API 401); current npm/installed audits clean; unsafe Python support floors corrected separately |

Auth/DB variables are UNSET **in the agent environment**. Remote deployment
variables were not inspected; prior inactive deployment status is not freshly
reverified. Production auth is not activated by any task here.

## Temporary real-login session — exact procedure

Operator authenticates locally in the existing FusionAuth Admin UI. Do not
send credentials, screenshots of secret fields, cookies or browser profiles.
Select application `84f077a0-b2b0-4655-8168-082b2233d029`, verify tenant
`5fcaaf07-8832-491a-a6e7-35d348a591b6`. Preserve the exact ordered redirect list
and matching-mode configuration privately before any edit. If baseline cannot
be established, do not mutate. If the temporary URI already exists, stop to
resolve the baseline/cleanup conflict; never remove a pre-existing value.

Add only `http://127.0.0.1:18080/oauth/callback`; preserve every other setting,
save and read back. Then the already-authorized probe is:

```bash
.venv/bin/python tools/fusionauth_surface_discovery.py --real-login --temporary-redirect-confirmed
```

The flag attests operator baseline/add/readback; it does not perform or verify
Admin changes. Code+PKCE S256, exact client, no client secret, one GET, no cookie
jar, no redirect following, no credentials submitted, no callback listener.
It emits only referenced same-origin paths when a recognizable authorize login
form exists; error/generic pages remain NOT_VERIFIED. This is HTML reference
evidence, not rendered-browser completeness. Tooling is tested; real execution
has NOT occurred. Browser observation must separately capture path-only CSS,
JS, images, font and conditional resource requests without HAR/raw HTML/secrets.
Compare generic/real references as OBSERVED_REAL_JUVAL_LOGIN,
OBSERVED_GENERIC_FORM, BOTH, CONDITIONAL or NOT_OBSERVED.

**Always clean up immediately**, including probe failure: remove only the
newly-added URI, restore the original list and read it back. Required evidence:
`TEMP_REDIRECT_PRESENT_AFTER_CLEANUP=NO`, `ORIGINAL_CONFIG_RESTORED=YES`.
Restoration failure is a hard stop. Current state: BASELINE NOT_ESTABLISHED,
MUTATION NOT_EXECUTED, CLEANUP NOT_APPLICABLE; original configuration has not
been independently verified.

## TLS / hostname / issuer activation preparation

Approved boundary: managed TLS endpoint → outbound tunnel from juval-server →
nginx `127.0.0.1:8080` → FusionAuth `127.0.0.1:9011`. No inbound firewall
opening, admin/API/account/password paths remain denied. Choose the tunnel
provider, domain ownership and certificate renewal responsibility before public
activation; provider TLS does not itself prove the inner route is restricted.
No production domain is invented here. ADR-038 adds the browser/API same-site
requirement or an explicitly validated alternate ingress.

| Setting / contract | Readiness requirement |
|---|---|
| Fixed public proxy host include | Actual identity hostname only; client Host cannot choose it; missing include fails nginx config test |
| Tenant issuer / public URLs | Read baseline in Admin UI; align tenant issuer and advertised discovery endpoints with approved HTTPS identity URL; exact `iss` equality required by backend |
| JUVAL_OIDC_ISSUER / AUDIENCE / CLIENT_ID | Actual issuer plus the exact application client ID; no guess from incoming Host |
| Authorization/token/JWKS/end-session endpoints | Confirm against selected tenant discovery; do not assume every path is issuer-relative if tenant issuer includes an identifier |
| JUVAL_BFF_REDIRECT_URI | Exact approved HTTPS API `/api/v1/auth/callback`; register exact match; temporary localhost URI is never production config |
| Post-login and post-logout destinations | Explicit HTTPS approved app destinations, not current relative `/` defaults pointing at API origin; verify FusionAuth logout registration and browser navigation |
| Cookies | Secure enabled, host-only, Lax; never set insecure local opt-out in production; top-level GET callback |
| CORS / CSRF | Explicit PWA origin, credentials included, X-JUVAL-CSRF on mutations; no wildcard; API session projection supplies validated CSRF value |
| Logging | No authorization query strings, request bodies or Cookie/Set-Cookie values in proxy/tunnel/provider logs; verify actual provider access-log policy before public login |

Validate discovery/JWKS and rendered hosted flow first through a disposable
proxy, then loopback runtime, then external TLS only after authorization.
Test all allowed and denied routes, Host variants, slash variants, queries,
MIME types, CSS/JS/images/fonts, conditional assets and MFA pages. Never infer
production compatibility from the echo lab. No `/oauth2/userinfo` caller exists
in the BFF; do not publish it. Do not publish broad `/assets/` for one icon.

## Session production migration and operations

Run `.venv/bin/python tools/session_store_lab.py`: private UTF-8 PostgreSQL
Unix socket, runtime env stripped, random schemas, teardown. Latest disposable
measurement: 48 passed, 2 structural memory skips; actual private PostgreSQL
restart preserves a live session, revocation and consumed-transaction refusal. Migration and down migration
repeat safely in the lab; unrelated sentinel data survives. This is not live
Supabase evidence or permission to run a live migration.

Before an explicitly authorized live migration: take a protected backup,
identify exact project/schema and **table-owning backend role**; ensure no
browser/PostgREST policies grant access. Apply only the reviewed identity SQL
with that owner; no FORCE RLS. Configure postgres store and backend-only keyring
through secret management. The read-only startup check now rejects unreachable
DBs, missing columns/tables and ownership/RLS policy errors. It does not repair
schemas, fully fingerprint types/indexes or prove long-term availability.
Check a real two-instance login/callback and restart, revocation, expired
sessions, replay refusal and RLS denial from an unprivileged role before use.

Rollback is destructive to sessions: stop admitting logins, follow approved
rollback, expect all sessions/in-flight OAuth exchanges to be lost; never drop
live tables without explicit authorization. Do not roll back to anonymous auth
on a public deployment. In an incident, isolate access until corrected.

Backups: protect ciphertext and keyring separately. **Do not restore old live
sessions**: a backup can resurrect revoked sessions and replay consumed OAuth
transactions. After an authorized recovery, invalidate session/transaction
state before reopening the BFF and require login; product execution data has a
separate retention/recovery lifecycle. Plan key rotation additively; all workers
must retain old decryption keys until old rows are gone. Key loss logs users out,
not loss of sourcing records. Restore rehearsal and live migration remain human
controlled. TTL cleanup exists as `purge_expired`, scheduling not activated;
monitor row growth and schedule only in the approved deployment environment.

## RF03 compact human test plan (prepared, not executed)

Use approved disposable identities only, never the operator's admin account.
Before the session, operator confirms exact tenant/app/policy baseline, disposable
user authorization and cleanup ownership. Password/TOTP entry remains entirely
operator-controlled. No API-key forensics or automated secret entry is needed.
Do not create users as part of the asset-only experiment above.

| Step | Operator action / required evidence |
|---|---|
| Baseline | Record non-secret tenant password length/composition/history/age, lockout count/duration and MFA required policy; compare to approved template, never assume it applied |
| Positive control | Valid disposable user on actual intended hosted path reaches required MFA; failure to reach policy means BLOCKED, not PASS |
| Password negatives | Individually test short, missing uppercase/lowercase, number and symbol; each must fail for the intended policy while a compliant password succeeds |
| Control 6 | Test first/last-name-containing passwords on every intended create/change/reset path; test through JUVAl validator and separately Admin residual; absence of a production provisioning route cannot yield SATISFIED |
| History / age | Reject reuse per actual history setting; minimum-age immediate change negative. Maximum-age production time behavior needs elapsed-time/provider evidence; synthetic lab clock evidence stays separate |
| Lockout | With a valid positive control first, enter wrong passwords up to approved limit (template 10), confirm lockout then correct-password refusal; record attempt counts/times, never passwords; verify recovery after configured interval (template 30 min) |
| MFA negatives | Missing/wrong TOTP cannot authenticate, correct TOTP succeeds, a consumed code/challenge cannot replay; do not persist code/secret/challenge values |
| RBAC / logout | When BFF topology is activated: viewer cannot create/export, operator can, unknown role denies, logout invalidates server session; trace request status only |
| Cleanup | Operator disables/removes only approved disposable users; revoke sessions; restore any temporary settings and read back; record completion or hard-stop failure |

Record case ID, date, build/version, route path, expected policy, status and
sanitized result. HTTP 401/403 infrastructure authorization failure is BLOCKED,
not password-policy PASS. No HAR, raw token response, password or TOTP artifact.
Existing behavioral API tool is not invoked; ADR-033 remains PROPOSED. Control 6
stays PARTIALLY_SATISFIED until effective production-path evidence and residual
acceptance support any stronger claim. No Amazon submission is authorized.

## Infrastructure triage (read-only runtime, 2026-09-10)

| Item | Current observation | Disposition |
|---|---|---|
| FusionAuth/PostgreSQL | active; FusionAuth PID 369334, NRestarts 0 | Stable, unchanged |
| Wildcard listeners 9011/9012, SSH 22, CUPS 631 | Observed; firewall effective reachability not reverified | SHOULD_FIX_BEFORE_PUBLIC: operator verifies UFW including IPv6 and CUPS/SSH exposure; do not infer internet reachability from bind alone |
| Backup system timer | enabled/active; last service exit success 2026-09-10 03:33:11 UTC | IMPLEMENTED_RUNTIME_OBSERVED; restore/content freshness not verified by an exit code |
| Monitor user timer | enabled/active; service success 2026-09-10 16:56:41 UTC | IMPLEMENTED_RUNTIME_OBSERVED; not a full capacity/load test |
| Off-host encrypted backup | No approved destination found | BLOCKS_PRODUCTION / HUMAN decision; on-host dump does not survive host loss |
| Fresh-host installer | Prior static tests, manual runtime install | TECH_DEBT / fresh-host destructive lab requires a suitable isolated host; do not rerun against stable runtime |
| OS reboot marker | `/var/run/reboot-required` present | SHOULD_FIX_BEFORE_PUBLIC / HUMAN maintenance window; no upgrade/reboot executed |
| Public identity infrastructure | No active production nginx/tunnel/TLS established | BLOCKS_PRODUCTION |

## Prioritized remaining queue and stop boundaries

1. Git histories and portal branch are integrated and checkpoint b338a67 was
   verified via authenticated SSH at 0/0. Continue gated normal pushes. Obtain
   the six non-secret Dependabot alert records to resolve the discrepancy; SSH
   authentication does not grant REST alert access. Never request a token.
2. Provide a controllable authenticated Admin browser or perform the compact
   operator redirect procedure locally: exact baseline, single temporary URI,
   probe without login, removal/readback. No baseline or mutation yet.
3. Select actual owned domain, identity tunnel/TLS provider/owner. Architectural
   topology is accepted, not a pending decision; real assets/D-1/public login
   and compatible remaining N-3 headers await hosted-flow evidence.
4. Approve live session migration only with the one-shot packet in
   `compliance/IDENTITY_OPERATOR_CHECKPOINT.md`; actual DB/pooler/role/backup
   preflight and production-path login remain external prerequisites.
5. Authorize RF03 disposable identities/procedure and private password/TOTP
   input. RF03 runbook ready, execution NOT authorized; effective Control 6
   behavior and production provisioning remain unverified.
6. Name security owner, off-host destination/recovery custody and maintenance
   window. Backup targets are proposals, not achieved RTO/RPO. No reboot,
   apt upgrade, firewall/SSH change, paid purchase or Amazon submission.

Backend/domain roadmap review: Decision Score formulas, commercial thresholds
and HAZMAT/BULKY severities require business approval; external risk/data
sources require authorized source decisions. No sourcing formulas or provenance
were changed. Reproducibility model extensions require their own concrete design
scope and should not displace the current identity gate. Project Intelligence portal is now integrated, including both preserved
readiness commits. ADR-040/model 1.2 defines five independent evidence measures;
use `node scripts/measure.mjs` against an exact committed snapshot. These are
curated evidence scores, not measured live system coverage or Amazon approval.

## Historical first-wave integration rehearsal and resume boundary

Superseded operationally by the authorized second-wave merges; retained as dated evidence.

Core tested revision `3a17e125397b975efb582c87f614d1538ec15b10`; preserved portal
branch `accelerator/portal-readiness` at
`29e90a6ae71266d15b61a976edfa972a25f96da5` (remote portal history plus two draft
updates). A disposable detached worktree merged them **without committing**:
no conflicts, integrated tree `92c0529328c6c1de6d5245f8726164d33a7b7f18`.
Gate: **825 passed / 36 skipped**, compliance **9 PASS / 1 WARN / 0 FAIL**,
secret scan clean (457 files). Product frontend diff empty. Preview aborted and
worktrees removed; the portal branch/commits remain durable locally.

After explicit integration authorization, the concrete reviewed operation is
`git merge --no-ff accelerator/portal-readiness` on clean authoritative master,
followed by gates, a fresh fetch and fast-forward push only if remote-only=0.
This command is **not executed on master**. It preserves both remote commits,
all Linux identity history and the portal updates; no rebase or force push.
SSH authentication must be restored locally for the configured push transport.

The full backend gate above tested the integrated tree, not an invented merge
commit. The portal's separate JUnit record accurately retains the earlier clean
`63568c4` measurement (821/36); it is not relabelled with a different revision.
Portal: 10 model + 4 component/i18n + 3 exporter tests; lint/build/audit passed.
No new browser E2E or hosted deployment claim. Generated snapshots/builds were
removed with the disposable worktree; committed scripts/config reproduce them.

All task-created nginx/PostgreSQL scratch and listeners removed. FusionAuth
PID 369334/NRestarts 0 unchanged; baseline listener inventory unchanged. No
redirect mutation was made, so original Admin configuration remains unverified,
not "restored successfully". No paid purchase, public DNS or migration occurred.


## Second-wave verification and residuals

Full backend after ADR-039: 834 PASS / 38 SKIP with disposable nginx. PostgreSQL
48 PASS / 2 memory-only SKIP plus actual restart probe PASS and cleanup. HTTP
refresh concurrency, expired writes and provider outage handling corrected;
see ADR-039 for connection/rotation crash residuals. No production migration.
Browser cookie semantics: same-site fetch positive, cross-site negative,
host-only/HttpOnly visibility and top-level GET PASS in synthetic Chromium lab;
not actual TLS/DNS/BFF/FusionAuth. Production frontend source untouched; only
frontend/package-lock.json changed under security exception.

N-3 decision: server_tokens off retained; candidate Referrer-Policy same-origin
minimizes cross-origin URL disclosure while preserving same-origin resource
requests. Do not add it or nosniff until real hosted/MFA/logout compatibility and
CSS/JS MIME readback are available. Frame/CSP policy awaits SSO iframe behavior;
Permissions-Policy must preserve WebAuthn. HSTS awaits real HTTPS/domain; no
naive per-IP authorize limit. Template remains inactive and no allow-list widened.

Runtime exact-ID controls re-run: tenant exists, client invalid_redirect_uri
vs invalid_client_id control. FusionAuth PID 369334/NRestarts 0 unchanged.
Names/roles NOT_REVERIFIED. REAL_LOGIN remains NOT_VERIFIED. Temporary redirect
BASELINE NOT_ESTABLISHED, RESULT NOT_EXECUTED, CLEANUP NOT_APPLICABLE; do not
claim original configuration restored when no baseline was inspected.

Prepared migration/RF03/off-host packet: `compliance/IDENTITY_OPERATOR_CHECKPOINT.md`.
Forensics and commit map: `research/ACCELERATOR_SECOND_WAVE_GIT.md`.
Manual simplicity/self-review performed; Ponytail callable capability unavailable.


## Third-wave current evidence

Full backend: 839 PASS / 42 SKIP in the final installed environment; the corrected-minimum
environment passed 839/38 before four additional PostgreSQL-only negative cases,
with disposable nginx. PostgreSQL: 52 PASS / 2 SKIP plus restart PASS. Executable
session preflight: 4 PASS; offline hashes only unless explicit metadata check.
New synthetic HTTP test verifies re-login recovery after provider rotation then
persistence failure; no real user, provider login or live DB used.

python-multipart >=0.0.31, PyJWT >=2.13.0, cryptography >=50.0.0, pytest >=9.0.3
exclude audited vulnerable support ranges. Installed packages were already newer;
no production environment upgrade. The full disposable dependency environment
was audited after upgrading its bootstrap pip 24.0 to 26.2.0; no known package
advisories then remained, with the local JUVAl project itself non-PyPI/unscannable.
This does not reconcile or dismiss the six unknown GitHub alerts.

Frontend 155 PASS, lint/build/PWA smoke PASS; all three frozen trees unchanged
this wave. Portal criterion dependency-remediation is PARTIAL/NOT_VERIFIED while
GitHub metadata is unresolved; measure through ADR-040 rather than retaining old
scores. Real login/redirect baseline still unavailable. No configuration mutation
or claimed restoration. N-1 retained and tested; N-3/final allow-list require real
hosted/MFA/logout evidence. Rate-policy thresholds require measured legitimate
flow/retry/NAT behavior; no synthetic number is treated as production-safe.

RF03, off-host recovery and domain architecture runbooks re-reviewed; their
remaining actions need explicit user/provider evidence. No new production
controls claimed. Authoritative dependency detail:
`compliance/DEPENDENCY_THIRD_WAVE_RECONCILIATION.md`.

## Fourth wave — persisted key rotation (2026-09-10)

`test_additive_key_rotation_preserves_then_reencrypts_sessions` exercises the
PostgreSQL adapter with generated disposable keys: additive rotation reads old
rows, a successful token replacement becomes readable with only the new key,
and untouched rows still require the old key. Removing an old key prematurely
fails closed. This is SCRATCH_DATABASE_BEHAVIOURALLY_VERIFIED, not deployed
rotation. No production keyring or database was changed. The isolated contract
passes 53 tests with 2 memory-only skips; actual private PostgreSQL restart also
passes and the cluster is removed. Full backend gate: 839 PASS / 43 SKIP, with
disposable nginx available; skipped database cases run in the separate lab.

## Fifth-wave safe discovery

See `docs/research/FUSIONAUTH_D1_FIFTH_WAVE.md` for the per-route matrix,
recovery exclusion rationale, generic runtime/conditional CSS evidence and
individual header experiments. No redirect or provider configuration changed.
MFA_BEHAVIORAL_CHECKPOINT_REQUIRED=YES; configuration readback awaits private
Admin authentication. RF03-P6 is BLOCKED_BY_ARCHITECTURE under ADR-035, not an
authorization to set passwordChangeRequired. D1 remains PARTIAL.
