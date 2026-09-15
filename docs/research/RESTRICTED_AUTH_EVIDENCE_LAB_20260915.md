# Restricted auth evidence synthetic lab — 2026-09-15

Status: IMPLEMENTED / SYNTHETIC LAB VERIFIED. Real MFA: NOT_AUTHORIZED.
Baseline: 32f0ee90caf70370a4e1019629481d9d1aa252fa.
Authority: operator approved this lab; ADR-042 remains PROPOSED.

## Scope and components

- tools/restricted_auth_evidence.mjs: private browser/page handles, JSON-line
  requests limited to `visit` with a fixed synthetic state, `observe`, `close`.
- Output has exactly `status` (READY/OBSERVED/CLOSED/REJECTED/FAILED) and `path`
  (null or /login, /challenge, /callback). No URL host/query/fragment is output.
- Unknown operations, extra keys, malformed JSON, foreign/unapproved paths and
  raw browser exceptions produce only fixed bounded responses. There is no DOM,
  JS, console, network, cookie, storage, screenshot, trace or profile export operation.
- Playwright core is loaded directly from the already-installed MCP 0.0.80
  dependency tree. The stock MCP package is neither invoked nor modified.
- Installed absolute paths are lab prerequisites, not portable deployment defaults.
  No packages, browsers or third-party code were downloaded or installed.
- tools/restricted_auth_display_lab.py creates :100 only if free, with private
  Xauthority and `-nolisten tcp`. It never reads Admin Xauthority. No VNC/viewer
  is created. Controller rejects :99. The auth credential is never logged.

## Reproduction

From repository root, using existing Node, Python, Xvfb and xdpyinfo:

```sh
node --test tests/security/restricted_auth_evidence.test.mjs
.venv/bin/python -m pytest -q tests/compliance/test_restricted_auth_evidence.py tests/compliance/test_compliance_check.py
.venv/bin/python tools/restricted_auth_display_lab.py
```

The last command is an explicit synthetic browser launch; it requires authorization
outside a broken execution sandbox and does not disable Chromium sandboxing. It
requires historical Admin PID 396207 to exist as a preservation baseline and no
existing dedicated browser. Never point the fixture at FusionAuth.

## Measured evidence

- 4 focused Node tests; Python wrapper plus compliance-check tests: 43 passed.
- Synthetic integration: 19 permitted protocol responses; all three fixtures
  executed through their final callback after populating password/TOTP fields,
  recovery page text, title, console errors, cookie/localStorage/sessionStorage,
  OAuth-like query and fragment with deliberately non-secret synthetic markers.
- No marker escaped in stdout; stderr was empty. Unsupported operations and
  extra fields failed closed. Observed paths retained no query or fragment.
- After browser close, 41 residual files in the private runtime directory were
  checked in memory: no marker found. No Playwright temporary-profile directory
  remained. All runtime files were then removed with the temporary directory.
- Correct Xauthority allowed xdpyinfo; empty authority was rejected. Display
  socket/lock removed after termination. No TCP X11 or viewer listener was added.
- Dedicated browser processes absent after close; Admin executable/start time
  unchanged. Listener sets matched baseline; no 9222. Git status unchanged by lab.

Controller-owned persistent artifacts: none by design. The post-close scan also
covered remaining third-party files inside this test's private runtime directory.
It does not claim no transient Chromium storage existed before closure. Fixture
source necessarily contains synthetic markers; those are test inputs, not leakage.

## Security boundary and limitations

The finite JSON protocol is the boundary, not protection from a malicious local
operator importing the module, using shell tools or reconnecting stock MCP.
No automatic console/error/request handlers or evidence file sinks are registered.
Debug environment variables are removed before Playwright loads; browser exceptions
are never serialized. Context storage is nonpersistent; downloads/service workers
are disabled and requests are restricted to the synthetic origin and paths.

Normal-close cleanup is behaviorally verified. SIGKILL, host crash, swap, kernel/
browser memory, third-party logs elsewhere and forensic erasure are NOT_VERIFIED.
Timeout handling is implemented but not claimed behaviorally verified here.
Whole-tree sandbox remains PARTIAL from prior GPU evidence; renderer evidence is
not promoted. X11 authentication/display separation reduces cross-client exposure,
but same-UID isolation and a private human viewer remain unresolved for real MFA.

No passwords/TOTP of real users, FusionAuth, Marcus, OAuth token exchange or Admin
state were accessed. No AppArmor/sysctl/permissions/capabilities were changed.
No frontend/runtime/domain code was modified. No production/Amazon claim, RF-03
closure, Dependabot closure or ADR-040 metric increase follows from this lab.

Next gate: review this synthetic result, then authorize a bounded private-viewer
and real-flow interface design (including callback interception and exact cleanup).
Human-only secret entry remains mandatory; stock MCP is not cleared for it.

## Commit gates

Focused Python compliance tests: 43 passed (including the wrapper running all
4 Node boundary tests). Offline compliance checks: 7 PASS, 1 WARN, 0 FAIL. The
warning is the existing incident-plan ROLE PLACEHOLDER marker; this lab does not
reclassify incident-plan approvals or close organizational evidence. Working-tree
pattern secret scan: PASS; no pattern finding in scanned eligible files. This is
not an absolute absence-of-secrets claim or a new historical-history scan.
`git diff --check`: PASS. Dependency/network audit not rerun: no dependency or
backend changes. Frozen frontend trees unchanged. No ADR-040 scope/metric change.
