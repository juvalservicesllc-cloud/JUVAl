# Controlled real MFA two-cycle experiment — 2026-09-18

**PARTIALLY IMPLEMENTED / REAL_MFA_PREFLIGHT = PASS.** Initial HEAD
749777c4627f015a8aac9b15f08b9e8d747cd3cb, clean. Experiment not started;
real provider contact NONE, real MFA NOT_EXECUTED. Awaiting human Admin creation
and non-sensitive readback of exactly one disposable Marcus identity.

## Authority and evidence classification

- **EXPLICIT_OPERATOR_AUTHORIZATION (this session):** prepare one Marcus identity
  via the human Admin boundary, two real cycles, human-only secret entry, mandatory
  deletion on success/failure/abort/controller failure/disconnection and exact
  restoration of any changed redirects. No production activation or token exchange.
- **DURABLE_OPERATOR_RISK_ACCEPTANCE:** REAL_MFA_ABORT_20260916 records acceptance of
  the same-host/UID and loopback viewer residuals. Viewer architecture is unchanged:
  reuse private_viewer_lab.viewer_commands, dedicated authenticated :100, loopback
  5901/6081, SSH human access, clipboard suppression, no VNC password. No repeated
  risk acceptance requested. Whole-tree sandbox remains PARTIAL; no RAM/swap/crash
  erasure claim. Protocol enforcement was separately explicitly approved.
- **HUMAN_ADMIN_READBACK:** Marcus absent, complete JUVAl tenant count 0, redirect
  [http://127.0.0.1:18080/oauth/callback], Exact matching, previously PKCE Required.
  Not automated provider verification. A newly created identity needs new readback;
  it must not reuse the deleted identity's old user ID as evidence.
- **CURRENT_READ_ONLY_RUNTIME_CHECK:** Admin process metadata available, :100 free,
  no dedicated browser, ports 18080/5901/6081/9222 free, Xvfb/x11vnc/websockify/
  xdpyinfo/noVNC/dedicated Chromium available. Existing provider listener metadata
  reports *:9011 and *:9012; no binding/firewall change or claim of external
  reachability verification. No HTTP provider request made by preflight.
- **SYNTHETIC_INTEGRATION:** callback gate retained. Because authorized real wiring
  changes the shared adapter, the existing direct/302 lab ran once against the
  changed implementation: PASS, active pipe/interception/finite callbacks, direct
  1 TCP and 302 0 TCP, both 0 bytes / 0 HTTP / no sentinel. Full cleanup and Admin
  metadata restoration passed; 9222 absent during polling. No new lab was created.

These jointly satisfy the preparation preflight, not identity creation, real login,
MFA or final cleanup. Each live cycle additionally refuses occupied resources and
requires private Xauthority, the existing sandbox and actual private-pipe checks
before emitting VIEWER_READY. Human confirms that dedicated viewer before START.

## Prepared execution path

`tools/real_mfa_viewer.py 1` (later `2`) owns one temporary cycle. It reuses viewer
commands and lifecycle helpers, validates all child evidence against the finite
status/path schema, monitors listener/Admin metadata and tears down on callback,
CLOSE, EOF, timeout, signal or failure. Child stderr is suppressed; no viewer image,
clipboard, DOM, cookie/storage, protocol payload or raw error is read/exported.

`tools/real_mfa_controller.mjs` creates a new sandboxed Chromium, installs the same
protocol boundary and builds the fixed JUVAl authorization request internally with
fresh PKCE S256/state/nonce. It emits READY while blank and contacts the provider
only on finite START after human viewer confirmation. Password/TOTP/QR/recovery
screens remain human-private. No authorization-code value is retrieved; no token
endpoint exists in the allowlist or controller interface.

`installAuthorizedRealBoundary` is an explicit trusted entry point using only the
fixed provider 127.0.0.1:9011 and callback 127.0.0.1:18080/oauth/callback. The default
synthetic entry still rejects real policies. Both delegate to unchanged FlowPolicy
and the same Fetch enforcement/cleanup; no parallel authorization policy or broad
agent browser API. This is approved experiment wiring, not JUVAL_AUTH_MODE.

At callback, the owner automatically destroys the entire cycle. Only after the
first owner reports complete cleanup can cycle 2 start in a new process/temp
profile/runtime. Cycle 2 requires a directly observed candidate challenge route
plus separate human confirmation that the UI is an existing-factor challenge.
Callback alone never verifies MFA. Unexpected route/state aborts without URL output.

## Pending human action and mandatory cleanup

One creation/readback request was issued: Marcus Rivera,
email mfa.test.20260913@example.invalid, username mfa-test-20260913,
tenant 5fcaaf07-8832-491a-a6e7-35d348a591b6, application
84f077a0-b2b0-4655-8168-082b2233d029, viewer-only registration.
Human creates and sets the password privately. Readback must identify the new user
ID and complete tenant count 1. Stop on pre-existing identity or another tenant
user; do not create another identity. No redirect/policy mutation requested.

After creation, human deletion of exactly that user is required regardless of any
later failure, followed by independently refreshed complete tenant list at 0 and
exact-user absence. Existing redirect is preserved, not reset to historical [].
Human reports metadata/booleans/counts only; no secret or screenshot is requested.

No real cycle or human cleanup result is claimed yet. RF-03 and Control 6 remain
PARTIAL; ADR-041/042 Proposed and ADR-040 metrics unchanged.

## Preparation validation

Targeted Node policy/protocol tests: 16 PASS. Relevant compliance pytest regression:
182 PASS / 86 SKIP (nginx unavailable, unchanged scope). New finite-output rejection
test covers arbitrary query/extra fields/unknown status/oversized child evidence.
No synthetic sensor retest or unrelated product work. Offline compliance/worktree secret-pattern scan: 8 PASS / 1 historical ROLE
PLACEHOLDER WARN / 0 FAIL, 525 eligible files without findings. Diff whitespace and
frontend/frontend-next/demo/src unchanged checks PASS. Manual self-review preserved
finite evidence, exact origins, human secrets and separate Control 6; repository
review tool unavailable. No real runtime was launched and no provider request made.
One local preparation commit; no push. Further work waits only for the required
human Admin creation/readback, not renewed operator permission.
