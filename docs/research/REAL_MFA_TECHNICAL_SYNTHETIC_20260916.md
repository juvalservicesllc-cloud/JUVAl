# Real-shaped MFA technical gate — closeout 2026-09-16 UTC

Operator session dated 2026-09-15; validation completed after UTC midnight.
Starting committed baseline: 40561074308646d7eb55a4f7c90e9244fd2269d9.
Status: IMPLEMENTED_AND_SYNTHETICALLY_VERIFIED. REAL_MFA_EXECUTED = NO.
REAL_MFA_PREFLIGHT remains BLOCKED.

## Boundary implemented

`tools/real_auth_flow.mjs` supplies a finite route/transition policy, a restricted
start/observe/close interface and the actual pre-network callback route handler.
Provider origin is explicitly 127.0.0.1:9011; callback origin is separately
127.0.0.1:18080. Runtime transport for the real provider is disabled both before
boundary installation and before controller navigation. Tests use only the
reserved synthetic origin `http://juval-mfa-synthetic.invalid`; even that origin
is never fetched from a server. All requests are fulfilled from trusted fixture
strings or aborted. No route.continue/fetch or callback HTTP receiver exists.
WebSocket attempts are closed; service workers/downloads are disabled.

Observed versus candidate routes follow REAL_MFA_PREFLIGHT_20260915.md. Challenge
and method-selection states are explicitly MFA_CHALLENGE_CANDIDATE and
MFA_METHOD_CANDIDATE. Synthetic success does not promote either real route.
Only fixed status/path pairs can leave the controller. Unknown requests, methods,
origins, navigation paths (including same-document changes) and transitions latch
failure; subsequent traffic cannot continue. No arbitrary DOM/JS, console,
network/body, storage, screenshot, trace, URL or exception export is implemented.

Cycle 1 permits enrollment only in order (login, enrollment, completion, optional
consent, callback); it also permits skipping optional enrollment. Cycle 2 requires
a challenge candidate after login. Method selection alone cannot satisfy it;
reenrollment and direct login-to-callback are rejected. Callback success never
produces a VERIFIED_MFA state. Path observations are not proof of actual TOTP use.

Callback handler matches the exact origin/path, GET and main-document request.
It compares expected state privately, rejects malformed/duplicate/extra callback
parameters, and never retrieves the code value. It fulfills a constant no-store,
no-referrer acknowledgment before network. Query and fragment never enter output.
A second callback/transition is rejected. Correlation is not token validation;
no token exchange occurs. Full request URLs necessarily exist transiently inside
Chromium/Playwright; this is not an assertion of memory erasure.

## Fresh-cycle ownership and adversarial evidence

`tests/security/real_auth_synthetic.mjs` owns fresh private runtime directories
and worker processes. Each worker launches its own dedicated sandboxed Chromium
and nonpersistent context. TMPDIR/HOME are private to that worker. The previous
worker/browser/profile is closed, residual processes checked, remaining files
scanned only for synthetic markers, and its directory removed before the next
worker starts. Distinct runtime directories and worker identities are compared
internally and reported only as booleans, without inspecting cookies/storage.

The existing authenticated Xvfb lifecycle harness runs the suite with `--real-flow`.
The display is shared only by sequential synthetic workers in that one laboratory
invocation and is destroyed at its end. No viewer is launched. This is structural
client-side freshness, not provider logout, server-side session invalidation or
complete OS isolation. The future real experiment must still perform its approved
full viewer/display teardown between cycles.

Eight browser cases passed:

1. Cycle 1 enrollment/completion/consent/callback.
2. Fresh cycle 2 method candidate/challenge candidate/consent/callback.
3. Unknown route containing a synthetic marker: rejected.
4. Wrong synthetic origin: rejected before transport.
5. Cycle 2 skips challenge: transition rejected.
6. Wrong callback state: rejected.
7. Same-document navigation to unknown path: rejected.
8. Browser handler exception containing a synthetic full callback URL: bounded FAILED.

32 controller responses contained no sentinel. Captured worker stderr was empty.
328 post-close temporary files contained no sentinel; all worker directories were
removed. Callback code/state/fragment markers also appeared in synthetic URL,
page title/body and console fixtures without leaving the finite boundary.
There was no callback listener or callback request-target log. No real provider
URL was navigated or fetched. Pure tests verify real-origin guards before any
context API/navigation can run; merely having the origin constant is not transport.

## Validation and cleanup

- Node policy/controller tests: 13 passed (9 real-shaped, 4 existing restricted).
- Focused pytest suite: 47 passed, including both Node wrappers, private-viewer
  regressions and compliance-check tests.
- Real-shaped display lab: 8 cases passed, X11 authorized accepted/unauthorized
  rejected, all browser cleanup checks passed, Admin executable/start time stable,
  listener baseline restored, :100 socket/lock and temporary directory removed.
- Existing synthetic display regression: 3 fixtures, 19 responses, no output/artifact
  sentinel leakage; cleanup/Admin/listener checks passed. Human viewer was not rerun.
- No ports 5901, 6081 or 9222; callback port 18080 required free and never bound.
- Offline compliance: 7 PASS, 1 existing incident-plan warning, no FAIL.
- Scoped worktree pattern secret scan and diff checks passed. No absolute
  absence-of-secrets claim. Frozen frontend trees unchanged. No dependency change.

Normal runtime cleanup is verified. Catastrophic process/host failure cleanup,
swap, browser/kernel memory, third-party artifacts outside the owned temporary
scope and forensic recovery remain NOT_VERIFIED. Whole-tree sandbox stays PARTIAL;
no host policy, capabilities, setuid, sysctl, MCP or sandbox settings changed.
The tests are not evidence of production readiness, Amazon approval or RF-03 closure.

## Tomorrow checkpoint

Technical blocker REAL_FLOW_ADAPTER_TESTS is PASS and CALLBACK_CONTAINMENT is
SYNTHETICALLY_VERIFIED. Remaining preflight blockers are exactly:
HUMAN_CLEANUP_COMMITMENT, FRESH_BASELINES, VIEWER_RISK_ACCEPTANCE.
ADR-041/042 remain Proposed; Control 6 remains PARTIALLY_SATISFIED.
Marcus remains untouched and operator-reported. No real MFA was authorized/executed.

First recommended action: review this evidence, then obtain a separately authorized
non-secret human Admin baseline/cleanup commitment and explicit viewer-risk decision.
Do not activate real transport, launch real auth, exchange tokens, mutate redirects
or users, touch Admin :99, widen host security or push without new authorization.
Live authorization initiation/PKCE transaction wiring remains inactive and unverified;
this synthetic core does not make an executable real-MFA command available.
