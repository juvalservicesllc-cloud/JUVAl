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
