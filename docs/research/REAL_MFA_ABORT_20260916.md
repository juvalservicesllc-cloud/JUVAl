# Controlled real MFA resumption — 2026-09-16

Status: ABORTED_AT_PREFLIGHT / BLOCKED. REAL_MFA_EXECUTED = NO.
Initial HEAD 958447c; clean worktree; cached origin/master f03574b, divergence
remote-only/local-only 0/7. All seven existing local commits preserved.

## Authority and baseline

The operator explicitly authorized the two-cycle experiment for Marcus only,
accepted the same-host viewer residual and committed to immediate human Admin
cleanup. These approvals do not verify whole-tree sandboxing. Fresh operator
readbacks identified Marcus e1131f52-ba5a-4031-b168-8a12c4bf4bde in JUVAl, viewer-only
registration in application 84f077a0-b2b0-4655-8168-082b2233d029, no configured MFA
methods, PKCE Required, Exact match and an existing authorized redirect:
`http://127.0.0.1:18080/oauth/callback`.
Classification: HUMAN_ADMIN_READBACK, not independent machine verification.
No redirect was added or removed; the historical empty-list baseline is inapplicable.
The required pre-experiment tenant count of 1 was requested but not confirmed
before technical abort. Final count 0 below is a separate subsequent readback.

Read-only preflight found ports 18080/5901/6081/9222 free, :100 socket/lock absent,
no dedicated Chromium process and the recorded Admin process present. Command
sandbox startup failed with a loopback permission error; approved escalated reads
were used. This is not evidence of a Chromium sandbox regression.

## Containment blocker: static local evidence

The existing synthetic controller/tests remain implemented and passing. Fixtures
use route.fulfill and subsequent JavaScript navigation, not live provider HTTP
redirect chains. Real transport and authorization/PKCE startup remain disabled.

Installed playwright-core: 1.63.0-alpha-2026-08-31, under
`/home/juval/.npm/_npx/86170c4cd1c5da32/node_modules/playwright-core`.
Local types/types.d.ts:4413 documents first-URL-only redirect interception.
Chromium handling in lib/coreBundle.js:36214 branches on redirectedFrom and calls
Fetch.continueRequest without creating a RouteImpl; requestStarted receives no
route. Simply enabling provider route.continue would not establish pre-network
policy/callback containment for HTTP redirects. A post-navigation observer cannot
establish prevention before transport.

Classification: STATIC_LOCAL_CODE_REVIEW; real HTTP redirect containment
NOT_VERIFIED. No runtime leak, callback transmission or provider behavior was
observed; no HTTP redirect reproducer was run. This missing live safety guarantee
does not retract the scoped synthetic results. The operator-required fail-closed
rule caused abort before viewer creation/login. No workaround, transport code or
allowlist expansion was attempted.

## Cycles, route evidence and cleanup

Cycles 1 and 2 NOT_EXECUTED. No private browser/context/profile, Xauthority,
display, viewer, callback listener or other auth runtime was created. Owned-runtime
cleanup NOT_REQUIRED, not a tested lifecycle success. No new real route/method,
enrollment, existing-factor challenge or correlated callback evidence exists.

The operator replied CONTINUE to exact-user deletion, then YES to a separate
complete-list/identity/configuration readback checkpoint confirming:

- JUVAl count 0; exact Marcus identity absent after refresh/search.
- USER deleted, not merely registration.
- Default tenant and Daniel untouched.
- Redirects exactly [http://127.0.0.1:18080/oauth/callback]; Exact match intact.

ADMIN_CLEANUP = HUMAN_ADMIN_READBACK. No Admin automation, API/key workaround,
secret inspection or independent machine verification. No audit-history erasure
claim. Do not reuse/recreate Marcus implicitly for a future attempt.

## Security, decisions and remaining scope

No real password, TOTP, seed, recovery code, authorization code, token, cookie,
client secret or Admin credential was requested, read, captured or derived by
the agent. No DOM, screenshot, console, network-body, storage/profile export,
token exchange, Admin :99 control or redirect mutation. No client state reuse;
neither cycle existed. Frontend remains frozen.

APPROVED: bounded experiment and abort/cleanup by explicit user instruction.
PENDING: reviewed live-transport containment design and synthetic HTTP redirect
chain tests before another real attempt. No callback listener, wider routes or
credential retry workaround. CALLBACK_CONTAINMENT remains SYNTHETICALLY_VERIFIED
for existing fixture scope; this session's real MFA NOT_VERIFIED. Historical
real enrollment evidence remains unchanged. Whole-tree sandbox and MFA/D-1 PARTIAL.
RF-03, Control 6, BFF/token verification, logout/revocation, production and Amazon
are not closed. ADR-041/042 remain Proposed; recommendation: retain this status.
ADR-040 model/percentages unchanged; no recalculation. Ponytail unavailable among
exposed tools/skills; manual correctness, security, scope and simplicity review.

## Validation

- Full `.venv/bin/python -m pytest -q`: 787 passed, 129 skipped, one existing
  Starlette/httpx deprecation warning. Skips cover unavailable nginx, unconfigured
  Supabase/disposable session databases and in-memory storage-inapplicable cases.
  Includes controller wrappers, private-viewer configuration and compliance tests.
- Explicit Node real-flow/restricted-controller tests: 13 passed, no skips.
- No new browser/viewer lab or real provider probe. Documentation-only changes.

- Offline compliance including scoped worktree pattern scan: 8 PASS / 1 WARN /
  0 FAIL; 513 eligible files, no pattern findings. The warning is the preserved
  incident-plan ROLE PLACEHOLDER marker, not a new organizational finding.
  Dependency network audit and historical secret scan were not repeated.
  Pattern scanning is not proof of absolute absence of secrets.
- Final ports 18080/5901/6081/9222 free; :100 socket/lock and dedicated browser
  absent. Recorded Admin PID exists; loopback Admin viewer listeners 5900/6080
  present. No authenticated Admin content was read. No full listener-set equality
  or process-start-time comparison is claimed by these boolean checks.
- git diff --check passed; frontend/frontend-next/demo have no diff from 958447c.
- Fresh git fetch origin failed with SSH publickey rejection. Cached origin/master
  remains f03574b; current remote state is NOT_VERIFIED. No push performed.

Publication recommendation: the documentation is suitable for a local traceable
commit after review; push is blocked pending operator-local SSH authentication,
successful fresh fetch and remote-only=0. No key/passphrase is requested. Exact
final commit/worktree/divergence are reported after the documentation commit.
