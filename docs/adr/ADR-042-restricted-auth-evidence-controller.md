# ADR-042 — Restricted authentication evidence controller and dedicated display

**Estado: Propuesta. Fecha: 2026-09-15.**

## Authority and decision proposed

The operator explicitly approved implementation and synthetic laboratory tests,
not real authentication or permanent acceptance of this ADR. Keep ADR-041 Proposed.

For RF-03 evidence, use a JUVAl-owned, minimal JSON-line controller with private
Playwright objects instead of stock MCP's broad browser interface. Allow only
finite lifecycle statuses and fixed paths. Never expose browser errors, arbitrary
DOM/JS, console, network bodies, storage, screenshots or traces. Query/fragment
values are discarded before any evidence output. Path observation is not proof
that MFA was completed.

Use a separate temporary authenticated Xvfb :100 with TCP disabled; preserve
Admin :99. Retain the existing root-owned Chromium copy and exact-path AppArmor
userns compatibility; preserve Chromium sandboxing. The controller does not
provision or modify that host policy. Synthetic scope only: /login, /challenge,
/callback at a disposable server; FusionAuth ports are rejected.

## Alternatives and consequences

- Stock MCP: rejected for sensitive evidence; automatic console files and URL/title
  metadata are not controlled by snapshot-mode none.
- Shared :99: rejected for this lab; profile separation is not X11 separation.
- A general replacement MCP: unnecessary; three operations suffice for this gate.
- Dedicated VM/account: stronger isolation, deferred; separate displays on the
  same UID do not protect against a malicious process with that UID.

Direct Playwright and Chromium still receive page/session data internally.
Synthetic non-leakage does not prove absence from memory, swap, crash artifacts,
third-party software, malicious host tooling or future authenticated workflows.
Whole-tree sandbox remains PARTIAL; this ADR does not resolve GPU isolation.
No production or Amazon readiness credit follows from these tests.

## Rollback and subsequent authorization

Close the controller, terminate only its own Xvfb, and remove its private temporary
lab directory. No persistent display/service, viewer, MCP change or host-security
mutation is introduced. Source can be reverted using ordinary Git history.

Actual hosted paths, private human viewer, callback containment, independent
Marcus/Admin readback and cleanup must be explicitly designed/authorized before
MFA. Do not enable real authentication by merely changing a port or allowlist.
See ../research/RESTRICTED_AUTH_EVIDENCE_LAB_20260915.md for measured evidence.

## Private viewer synthetic extension — 2026-09-15

The operator authorized and confirmed a non-sensitive human viewer experiment.
A temporary x11vnc/noVNC bridge on IPv4 loopback, attached only to authenticated
:100, passed visual/interaction and normal cleanup checks. Clipboard-related
flags are configured; no clipboard contents were inspected. No VNC password was
created. Same-host and forwarded-port access remain residual risks, unacceptable
to silently waive for real credentials. See
[private viewer evidence](../research/PRIVATE_VIEWER_LAB_20260915.md).
This evidence does not accept the ADR or authorize MFA.

## Real MFA preflight — 2026-09-15

[Real MFA preflight](../research/REAL_MFA_PREFLIGHT_20260915.md) defines the
observed/candidate route split, pre-network callback interception, fresh-cycle
protocol and human-only cleanup path. Execution remains BLOCKED pending fresh
Admin baseline/cleanup commitment, real-flow adapter tests and acceptance of
viewer residual risks. No authenticated execution is approved by this document.
Status remains Proposed; historical renderer evidence does not verify whole-tree
sandboxing or provider-side authentication/cleanup.

## Synthetic real-flow technical closeout — 2026-09-16 UTC

The finite adapter, permanent abort latch, callback interception and fresh-worker
cycles passed synthetic tests; see [scoped evidence](../research/REAL_MFA_TECHNICAL_SYNTHETIC_20260916.md).
No real provider transport is enabled. This supersedes the pending synthetic
adapter-test portion above, not human cleanup/baseline/viewer-risk prerequisites.
Candidate challenge routes remain unverified against FusionAuth. Status: Proposed.

## Controlled real resumption — 2026-09-16

Explicit operator authorization supplied human cleanup commitment, viewer-risk
acceptance and fresh identity/redirect readback. Execution aborted before login:
static installed-Playwright review found HTTP redirects bypass the route handler;
synthetic fulfillment tests do not establish live HTTP redirect containment.
No transport enabled or runtime created. [Evidence and human cleanup](../research/REAL_MFA_ABORT_20260916.md).
Marcus deletion and unchanged pre-existing redirect/Exact match confirmed by
HUMAN_ADMIN_READBACK. Retain Proposed status; a reviewed live boundary and synthetic
redirect-chain tests precede any newly authorized real attempt.

## Synthetic HTTP reproducer stop — 2026-09-16

The direct-navigation control admitted one TCP connection despite one callback
route invocation; no HTTP request/code sentinel was received. The harness stopped
before emitting its actual HTTP 302. Redirect containment remains NOT_VERIFIED;
this does not claim a code leak. [Evidence and candidate tradeoffs](../research/HTTP_REDIRECT_CONTAINMENT_20260916.md).
No candidate was implemented/selected as a safe live boundary. Independent network
isolation would change approved assumptions and requires architectural review.
Status remains Proposed; no runtime MFA, user, redirect or readiness change.

## Approved callback property and failed redirect gate — 2026-09-18

Explicit operator decision APPROVED: protect callback HTTP/OAuth material from
network delivery; a TCP connection without application bytes is not itself failure.
This replaces any interpretation of pre-network as a zero-TCP requirement. The
broader controller ADR remains **Proposed**; no live transport is authorized.

The single bounded test of the existing route/continue architecture completed the
previously unexecuted 302 case: one HTTP request, 753 received bytes and the synthetic
code marker reached the owned receiver without callback handler invocation.
Direct interception reached the finite callback with zero received bytes despite
one TCP connection. Thus the HTTP/OAuth boundary also fails for HTTP redirects.
[Exact evidence and proposed internal pipe interceptor](../research/HTTP_REDIRECT_CONTAINMENT_20260916.md).
That candidate adds a privileged protocol interception boundary and remains PENDING;
no namespace/broker/protocol implementation is silently approved by this amendment.

## Approved protocol-pipe extension — 2026-09-18 (latest)

The operator explicitly **APPROVED implementation** of Chromium protocol-layer
interception through a private process pipe, preserving the existing finite policy.
This supersedes the candidate's PENDING implementation authority above, but does
not accept this ADR, authorize a real provider or enable live transport.

Problem: route.continue allowed a genuine HTTP 302 to bypass the callback handler
and expose a synthetic code to the receiver. The mitigation uses Fetch.requestPaused
at Request stage on every hop and delegates origin/method/path/transition/callback
shape to FlowPolicy. Trusted synthetic origin relocation does not change the exact
production callback. Callback requests are fulfilled locally; rejected requests
abort; approved fixture-provider requests alone continue. Code values are not read.
Pipe-only launch arguments and sandbox flags are checked privately. Target guards
pause extra targets and close the owned browser; protocol errors/detach close it.
No CDP TCP/WebSocket endpoint, Fetch-disable-before-close or general agent protocol
API is introduced. An internal Chromium API dependency is the principal tradeoff
against higher-level routing; no HTTP broker or privileged namespace is added.

Implementation and unit tests exist, but the single bounded integration run stopped
at setup before either navigation. **Runtime enforcement remains NOT_VERIFIED**;
no claim that target/disconnect failure handling is atomically proven in Chromium.
Finite setup-phase diagnostics were added after the run and tested without another
browser execution. [Measured evidence and exact continuation scope](../research/HTTP_REDIRECT_CONTAINMENT_20260916.md).
Same-host/UID, browser/process memory and whole-tree sandbox PARTIAL limitations
remain. Historical failed 302 evidence is preserved. **Status remains Proposed.**
