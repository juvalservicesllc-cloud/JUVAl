# JUVAl identity/security — current readiness and operator runbook

**2026-09-10 accelerator. Status: PARTIALLY IMPLEMENTED.** Authoritative
workspace: `/home/juval/JUVAl/APP`. This ledger supersedes dated implementation
snapshots in project plans, contracts and research; historical experiments are
not reclassified as production evidence. Git commits identify the exact changes.

## Evidence ledger

| Claim | Classification | Evidence / confidence |
|---|---|---|
| Starting repository | VERIFIED_LOCAL | `16189b7`, clean, cached origin `32c3aef`, local 0/3; high |
| Current remote | VERIFIED_READ_ONLY via HTTPS | `6a6d07c`, two remote-only portal commits; SSH push authentication unavailable; histories diverge |
| Exact tenant/application IDs exist | VERIFIED_RUNTIME_READ_ONLY | 2026-09-10 public controls: tenant 200 vs four 500 controls; real client invalid_redirect_uri vs random invalid_client_id; high for existence only |
| Tenant/application names and role names | NOT_REVERIFIED | Admin readback not available; never recreate existing objects |
| Real login surface | NOT_VERIFIED / BLOCKED_BY_REDIRECT_CONFIGURATION | No authenticated Admin browser capability in agent; baseline not read; no mutation |
| BFF/session store | IMPLEMENTED_TESTED_NOT_ACTIVATED | ADR-034/036; startup readiness and revoked-session projection corrected |
| N-1 | REMEDIATED_TEMPLATE / LAB_BEHAVIOURALLY_VERIFIED | ADR-037; relative 301, query retention, no upstream contact; 90 nginx tests |
| D-1 / final asset allow-list | BLOCKED | Generic CSS fonts/icon evidence only; real login needed |
| N-3 | PARTIAL | nginx version suppressed; other headers/rate policy await flow compatibility |
| Public TLS/hostname/issuer | NOT_ESTABLISHED | ADR-031 approved network boundary; actual names/provider pending |
| Browser site topology | PENDING_DECISION | ADR-038: cross-site Vercel/Railway domains incompatible with Lax fetch cookies |
| Control 6 / RF03 / Amazon | PARTIALLY_SATISFIED / NOT_EXECUTED / BLOCKED | Code/tests and isolated provider lab cannot prove effective production behavior |
| SEC-DEPS-01 | REVIEWED / PATCH_PENDING_FREEZE_EXCEPTION | `compliance/SEC_DEPS_01_REVIEW.md`; backend clean, five unique frontend advisories |

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
measurement: 44 passed, 2 structural memory skips. Migration and down migration
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

1. Resolve divergent histories: remote `6a6d07c` adds two portal commits from
   `32c3aef`, while Linux has the three original identity commits plus accelerator
   work. No rebase/history rewrite and no merge merely to synchronize are allowed.
   Operator must authorize a non-rewriting integration merge (or provide another
   explicit preservation strategy). Restore SSH authentication locally, then fetch,
   gate and fast-forward push only when remote-only=0. Never share passphrase/key.
2. Operator Admin session plus exact redirect baseline/add/readback/probe/cleanup;
   then real asset inventory, D-1 allow-list and nginx/FusionAuth integration.
3. Choose owned public hostnames, tunnel/TLS responsibility and ADR-038 topology.
4. Approve dependency-only frontend freeze exception for the isolated patch in
   SEC_DEPS_01_REVIEW; no visual/frontend feature changes.
5. Authorize exact live session migration after backup/role verification, plus
   eventual BFF/frontend activation only when identity gates permit it.
6. Approve disposable RF03 identities/procedure and provide human password/TOTP
   interaction; approve effective Control 6 production provisioning policy.
7. Name security owner, off-host backup destination and maintenance window;
   record restore/incident/access-review evidence. Amazon submission remains
   separately human controlled.

Backend/domain roadmap review: Decision Score formulas, commercial thresholds
and HAZMAT/BULKY severities require business approval; external risk/data
sources require authorized source decisions. No sourcing formulas or provenance
were changed. Reproducibility model extensions require their own concrete design
scope and should not displace the current identity gate. Project Intelligence portal was absent from the initial Linux tree but is
present in two newly fetched remote-only commits. It must be preserved during
history reconciliation; its publication is connected to Git according to remote
docs (not independently reverified in Vercel). All five accelerator progress
percentages are **NOT_MEASURED**, not inferred from the portal weighted model.
