# Real MFA preflight — 2026-09-15

**REAL_MFA_PREFLIGHT = BLOCKED (execution prerequisites unresolved).**
**REAL_MFA_EXECUTED = NO.** This is a documentation/design review, not permission
to log in or change FusionAuth. Starting HEAD:
54f7822d7d0582c1c749af38d878a892978b99c7.

## Technical closeout — 2026-09-16 UTC

REAL_FLOW_ADAPTER_TESTS = PASS; CALLBACK_CONTAINMENT = SYNTHETICALLY_VERIFIED.
See [technical evidence](REAL_MFA_TECHNICAL_SYNTHETIC_20260916.md).
This closes the synthetic technical portion of item 3 below, superseding its
pending implementation status. Real transport remains disabled. Current unresolved
preflight blockers are HUMAN_CLEANUP_COMMITMENT, FRESH_BASELINES and
VIEWER_RISK_ACCEPTANCE. The following plan remains the real-execution contract,
not permission to run it. REAL_MFA_PREFLIGHT remains BLOCKED.

## 1. Evidence and hard prerequisites

Authority: operator's preflight-only instruction. Sources:
[MFA discovery](MFA_DISPOSABLE_DISCOVERY_20260910.md),
[sanitized method/path inventory](mfa-discovery-evidence-20260910.json),
[private viewer evidence](PRIVATE_VIEWER_LAB_20260915.md), current controller and
viewer harness. Historical results are not fresh provider configuration evidence.

The future mechanism for cleanup is credible in principle: the prior experiment
successfully deleted an exact disposable identity using Admin's DELETE confirmation
and separately reread the complete Users list. That deleted user was NOT Marcus.
No currently authorized automatic Admin/API mechanism can perform this cleanup.
No API-key investigation or sensitive audit query is proposed.

Before authorizing real login, all of these must be resolved:

1. A human Admin operator must explicitly undertake immediate cleanup on success,
   abort or agent disconnection, and remain available for the entire experiment.
   Their ability to delete Marcus and restore application redirects must be
   confirmed before enrollment, not discovered afterward.
2. A separately authorized narrow human Admin readback must verify tenant,
   Marcus identity/registration and complete tenant count, and application redirect
   list plus matching policy. No agent control/read of Admin :99 is proposed.
3. The real-flow controller adapter, transition latch, callback containment and
   two-cycle cleanup must be implemented and synthetically tested. Existing code
   deliberately rejects FusionAuth ports and has only synthetic route names.
4. The operator must explicitly accept or resolve the documented same-host
   loopback-viewer/same-UID risk for private secret entry. Whole-tree sandbox
   remains PARTIAL. No weakening of isolation is part of this plan.

The review defines the plan but does not waive these blockers or guarantee a
human action that has not been agreed. No real experiment may start yet.

## 2. Minimum route/method allowlist

Origin binding: future direct-lab provider origin http://127.0.0.1:9011 only;
no nginx/public-surface change. Callback is a distinct exact origin/path below.
Route classification and protocol role must remain separate. Never output query,
fragment, host, arbitrary URL, unknown path, error text or page content.

| Path | Methods | Evidence / proposed treatment |
|---|---|---|
| /oauth2/authorize | GET, POST | DIRECTLY OBSERVED; initial hosted login |
| /oauth2/two-factor-enable | GET, POST | DIRECTLY OBSERVED; enrollment |
| /oauth2/two-factor-enable-complete | GET, POST | DIRECTLY OBSERVED; completion/recovery-code screen |
| /oauth2/consent | GET | DIRECTLY OBSERVED; POST is not evidenced and remains blocked |
| /oauth/callback | GET | DIRECTLY OBSERVED browser-intercepted arrival; not BFF/token verification |
| /oauth2/two-factor | GET, POST | CANDIDATE_NOT_VERIFIED; proposed bounded challenge allowance only |
| /oauth2/two-factor-methods | GET, POST | CANDIDATE_NOT_VERIFIED; proposed bounded factor-selection allowance only |

Candidate methods are proposals, not measured facts. Approval must explicitly
permit probing these exact candidates; a successful observation changes only that
observation's evidence status. A route alone never proves existing-factor MFA.

Exact GET-only resources observed during initial login/enrollment:

- /css/entrypoints/fusionauth-hosted.css
- /css/font-awesome-4.7.0.min.css
- /images/favicon-128.png
- /images/favicon-32x32.png
- /images/footer-logo.svg
- /js/Util.js
- /js/entrypoints/oauth2/authorize.js
- /js/identityProvider/InProgress.js
- /js/jstz-min-1.0.6.js
- /js/oauth2/Authorize.js
- /js/oauth2/LocaleSelect.js
- /js/oauth2/OAuth2TwoFactorEnable.js
- /js/prime-min-1.7.0.js
- /js/qrcode-min-1.0.js

These are request permissions, not DOM/resource-body exports. No broad resource
prefix is needed for the minimum proposal. Unknown assets stop the branch; do not
silently widen. The historical logout-only /images/logo-gray.svg is not required.
GET /oauth2/logout and GET / were historically observed, but are excluded from
this two-clean-login experiment. Logout/revocation is not tested or credited.

Deny /oauth2/token (no exchange), /oauth2/userinfo, /password/*, /admin/*, /api/*,
/account/*, root, /assets/*, /fonts/*, external origins and WebAuthn. Blocking an
unexpected route means a finite UNEXPECTED_ROUTE/ABORTED result, never echoing its
path. A new reviewed allowlist is required before another experiment.

## 3. Callback containment and redirect baseline

A redirect destination is required to observe completion of the proposed code
flow. Whether a TEMPORARY provider change is needed is NOT_ESTABLISHED: historical
[] / ExactMatch is not today's baseline. Do not infer it from user creation.
Only permitted proposed URI: http://127.0.0.1:18080/oauth/callback.

Preferred minimal design: **browser-side interception before network transmission,
with no callback TCP listener**. The prior real experiment used interception.
Install a context-level handler before starting authorization; match exact origin,
path, GET and main-frame request. Fulfill locally with a constant acknowledgment
and no embedded request data. Thus no HTTP callback server receives a code-bearing
request target, and no callback access log is created. Port 18080 must be checked
free before use; this design never binds it. If interception cannot be proven,
abort rather than fall back to a generic HTTP logger.

Generate fresh PKCE S256/state/nonce entirely inside the restricted process for
each cycle, with no output or persistence. Correlate returned state in memory;
reject missing/mismatched state and OAuth error presence. Do not extract, decode,
store, return, hash or exchange the authorization-code value. Presence-only checks
are not token validation. No ID/access/refresh token is requested or inspected.

Emit only a finite CALLBACK_ARRIVED plus /oauth/callback after expected transition
and correlation checks. Do not call ordinary page URL/title/console snapshots.
Arrival proves a correlated redirect, not a verified token, BFF session or SSO
revocation. URL/query data still transiently exists in browser/Playwright memory;
this is not forensic erasure. Static output/error handling must be adversarially
tested before real use, including malformed requests and abort/close paths.

Redirect procedure, performed only by a separately authorized human Admin:
BEFORE: record exact ordered list and exact matching policy privately; publish
only approved non-sensitive configuration evidence. If any baseline URI contains
sensitive material, do not copy it to chat; stop and resolve safe restoration.
If the sole approved callback is absent, add only it, preserve all other entries
and policy, save and reread. If already present and permitted, make no change.
If policy differs from the expected exact-match architecture, stop; do not switch
policies implicitly. AFTER success or failure: restore precisely BEFORE and reread.
No blanket reset to [] is allowed. Restoration is not claimed until readback.

## 4. Viewer reuse and controller changes required later

Retain private :100, fresh Xauthority, no -ac, -nolisten tcp, root-owned dedicated
Chromium with sandbox enabled, IPv4 loopback VNC 5901/noVNC 6081, clipboard/selection
and remote-command suppression. Never expose CDP TCP or use stock MCP on secrets.
No new privilege, global policy change or reuse of Admin state is necessary.

Reuse lifecycle ownership from private_viewer_lab.py, not its synthetic HTTP
fixture or POST interaction marker. A real-flow adapter must have fixed start,
observe and close operations, no caller-supplied URL/DOM/JS or secret parameters.
Its transition monitor must latch forbidden requests automatically, including
human-triggered navigation between observations. The current synthetic controller
only rejects/aborts requests; it is not a verified real-flow abort coordinator.
Finite route observations and human confirmations must carry distinct provenance.
No arbitrary error string, dialog text, title or resource metadata may escape.

Do not introduce password/TOTP input via stdin/env/files/tool arguments. Stdin
may carry finite CONTINUE/ABORT and lifecycle commands only. No clipboard, image,
trace, console, network/body, cookie/storage/profile export. Human viewport and
input remain in the viewer; the agent never polls secret-bearing DOM.

## 5. Two clean cycles and human checkpoints

Cycle 1: verify all prerequisites, create new private runtime/display/controller,
install containment, then initiate only the fixed authorization flow. Human enters
Marcus's existing password privately. If enrollment is required, human enrolls
privately and passes recovery codes without reading them to the agent, exporting
or recording them. Consent is human-controlled; stop if method/route is unexpected.
After correlated callback, close browser/context and controller; terminate only
owned viewers/Xvfb; verify all owned PIDs, socket/lock/temp directory gone and
listener baseline restored. Preserve no browser state for reuse.

Cycle 2: allocate a NEW temporary directory, new Xauthority, new controller/browser
process and nonpersistent context. Use a new PKCE/state/nonce transaction. Verify
first-cycle processes/temp resources absent before starting. Record lifecycle
booleans and PID/start-time metadata, not cookie/storage contents or identifiers.
This establishes fresh client-side state; /logout navigation is not a substitute.
It does not erase provider-side state or prove server-side logout.

After human password entry, require an allowlisted challenge candidate observed
AND human confirmation that this is a challenge for the existing enrolled factor,
not enrollment. If enrollment is presented again, stop; do not reenroll. Human
privately supplies TOTP, then correlated callback must follow. Only the combined
fresh-cycle, route, human observation and callback evidence supports the scoped
existing-factor claim. No inferred route alone is sufficient.

Finite checkpoints (future use only):

1. ADMIN_BASELINE_AND_CLEANUP_READY: exact identity, count, redirects, cleanup owner.
2. VIEWER_READY: human confirms the correct dedicated window before secrets.
3. HUMAN_CHECKPOINT_PASSWORD: Enter the disposable user's password privately in
   Chromium. Do not paste it into Codex. Reply CONTINUE when complete.
4. HUMAN_CHECKPOINT_TOTP: Complete the TOTP step privately in Chromium. Do not paste
   the code into Codex. Reply CONTINUE when complete. Covers enrollment UI without
   agent inspection of QR/seed; no repeated automated credential attempts.
5. RECOVERY_SCREEN_PASSED: human proceeds without reporting QR/seed/recovery contents.
6. EXISTING_FACTOR_CHALLENGE_SEEN: cycle-2 human boolean confirmation, separately
   labelled HUMAN_REPORTED, followed by private TOTP and callback evidence.
7. ADMIN_CLEANUP_COMPLETE: exact deletion, independent count/absence readback and
   redirect restoration; no secret content is requested.

## 6. Credible cleanup mechanism and blocker

Target identity for fresh human verification:
JUVAl tenant 5fcaaf07-8832-491a-a6e7-35d348a591b6;
application 84f077a0-b2b0-4655-8168-082b2233d029;
Marcus user ID e1131f52-ba5a-4031-b168-8a12c4bf4bde;
username mfa-test-20260913; email mfa.test.20260913@example.invalid;
viewer registration only. These remain operator-reported until fresh readback.
The operator must stop on mismatch, other tenant users, or unexpected role/state.
No passwordChangeRequired changes, user recreation or second disposable identity.

Expected pre-experiment JUVAl count is 1 including Marcus. The required restored
baseline is 0 AFTER deleting him; do not describe the current baseline as zero.
The human operator, under later narrow authorization, uses Admin privately to
select the exact user/tenant, delete the user itself (not just its registration),
complete the explicit DELETE confirmation and reread the list. Do not touch Daniel
Liendo or Default tenant Admin. Existing Admin is never automated or logged out.

Independently of the delete-success notification, refresh a complete tenant-filtered
Users listing, verify count 0, and separately search the exact ID/email for absence.
Human reports only booleans/count and non-secret identity. This is human-admin
readback evidence, NOT independently automated agent verification. If independent
machine readback is mandatory, this preflight remains blocked until a separately
approved safe mechanism exists. No API-key workaround is proposed.

Once the experiment has started, deletion and redirect restoration are mandatory
on success or abort, including failures before enrollment. After enrollment,
operator cleanup must proceed immediately even if the controller/viewer fails.
If Admin access fails, mark USER_CLEANUP_BLOCKED, stop further auth/mutations and
escalate to the named human operator; never claim count zero or erasure of audit
history. No indefinite retry loop or implicit credential rotation is authorized.

## 7. Fail-closed matrix

| Trigger | Required action |
|---|---|
| :100 busy, callback interception/port preflight failure | Do not start auth; remove only owned resources; restore any temporary redirect |
| Unexpected route/method/resource or recovery screen | Latch abort; block request; emit only fixed status; no expanded allowlist/retry |
| Viewer non-loopback bind, unexpected listener or CDP/9222 | Stop owned viewer/browser immediately; verify baseline; no firewall workaround |
| Admin metadata changes | Stop dedicated branch; do not repair/restart Admin; operator decides cleanup access |
| Missing sandbox flag or regression vs accepted renderer evidence | Stop; no no-sandbox/capability/AppArmor workaround; existing GPU limitation stays PARTIAL |
| Output outside schema or possible sensitive output | Stop without echoing payload; do not hash, persist or investigate secret values |
| Human cannot complete MFA, extra factor, forced change, unexpected UI | Abort; no lockout retries, reset, recovery, reenrollment or password policy tests |
| First-cycle cleanup incomplete | Do not start cycle 2; stop and prove cleanup |
| Final browser/viewer/redirect/user cleanup incomplete | Report exact unfinished category; no PASS, no next auth run |

Controller failure cannot be relied on to delete a FusionAuth user. The human
cleanup branch is independent and must be arranged before starting cycle 1.

## 8. Control separation and outcome

Control 6: PARTIALLY_SATISFIED, unchanged. No name-password rejection, forced
change, lockout, reset/recovery or breach-detection tests. RF-03 remains Partial;
no Amazon approval/reapplication, production auth, BFF token verification or
logout claim. ADR-041/042 remain Proposed; ADR-040 metrics unchanged.

This phase changed documentation only. Relevant existing focused tests and offline
compliance/working-tree secret-pattern checks apply; no browser launch is needed.
Next exact step: separately authorize and obtain the non-secret human Admin
baseline/cleanup commitment, then implement/test the real-flow containment adapter
synthetically. Real MFA requires another explicit authorization after those gates.

Validation in this preflight: 46 focused tests passed; offline compliance 7 PASS /
1 pre-existing incident-plan warning / 0 FAIL; scoped worktree pattern secret scan
PASS; git diff --check PASS; no diff in frozen frontend trees. Pattern scanning is
not proof of absolute secret absence. No Git publication attempted.
