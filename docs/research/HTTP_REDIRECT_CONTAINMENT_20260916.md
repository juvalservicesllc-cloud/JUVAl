# HTTP redirect containment: synthetic reproducer and design review — 2026-09-16

## Corrective protocol integration — 2026-09-18 (current, gate CLOSED)

**IMPLEMENTED / PROTOCOL_BOUNDARY = INTEGRATION_VERIFIED (synthetic scope).**
Initial HEAD 7699d02de78492a71d160199a62bbf8d176a151c, clean. Operator explicitly
authorized autonomous corrections and reruns of the same synthetic laboratory.
No new architecture, real provider, identity creation or real MFA authorization.

### Root causes and bounded correction history

Six invocations of the same tools/http_redirect_gap_lab.py; no second laboratory.
The first five stopped before navigation; the sixth executed both cases and PASSED.
No browser callback experiment was repeated after PASS.

| Invocation | Finite result | Action before next invocation |
|---|---|---|
| 1 | PIPE_CHECK | Add --enable-automation to the owned laboratory browser launch |
| 2 | TARGET_GUARD | Separate root/child/target-event diagnostic stages |
| 3 | OTHER_TARGET_ATTACHED | Check expected page type and classify attached target type finitely |
| 4 | OTHER_TARGET_OTHER | Refine known auxiliary target-type labels, without exporting target data |
| 5 | OTHER_TARGET_OTHER | Destroy discovered auxiliary targets during blank-page preparation |
| 6 | PROTOCOL_CALLBACK_CONTAINMENT_PASS | Close gate; no further browser experiment |

Two functional corrections, three bounded diagnostic refinements. First cause:
installed Playwright does not add --enable-automation by default, while installed
protocol.d.ts explicitly requires it for Browser.getBrowserCommandLine. Adding it
allows the existing pipe/sandbox assertion to execute; no assertion was removed.
Second cause: initial auto-attachment discovers an auxiliary target, triggering the
runtime unknown-target abort before navigation. No arbitrary target details were
exported; do not infer that auxiliary target's role or content from its category.

The correction destroys every unowned target discovered during blank-page setup,
awaits successful closure, and never resumes it. Closure failure aborts installation.
After setup, an unexpected target still closes the entire owned browser. The bound
of 16 setup discards prevents an unbounded lifecycle loop. This is initialization
wiring, not a target allowlist expansion. FlowPolicy remains unchanged and is the
sole route/transition/callback authority. The exact logical callback stays
http://127.0.0.1:18080/oauth/callback; only owned synthetic ports are relocated.
Unit tests cover successful setup discard, failed discard and runtime target abort.

### Decisive measured acceptance

Command for each invocation: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B
 tools/http_redirect_gap_lab.py. Final exit **0**, setup_failure=null.

| Measurement | Direct callback | Actual HTTP 302 callback |
|---|---:|---:|
| Navigation actually attempted | true | true |
| Browser callback request event | 1 | 1 |
| Pipe-only protocol installation checked | true | true |
| Callback intercepted by protocol | true | true |
| Redirect-generated callback intercepted | false (not a redirect) | true |
| Source HTTP 302 emitted | 0 | 1 |
| Receiver TCP connections | 1 | 0 |
| Receiver application bytes | 0 | 0 |
| Receiver HTTP requests | 0 | 0 |
| Receiver code sentinel observed | false | false |
| Sensor observation complete | true | true |
| Finite policy/controller callback reached | true | true |
| Protocol failure | false | false |

CALLBACK_302_CONTAINMENT = PASS.
CALLBACK_TCP_CONNECTION = MAY_OCCUR (direct case observed one).
CALLBACK_HTTP_OAUTH_MATERIAL_NETWORK_EXPOSURE = NONE_DETECTED_IN_BOUNDED_SYNTHETIC_TEST.
CALLBACK_CONTAINMENT = SYNTHETICALLY_VERIFIED_AT_HTTP_OAUTH_MATERIAL_BOUNDARY.
Zero received bytes supports the query/code/state/fragment-equivalent material
boundary in these cases; no separate fragment-transmission claim is made. This is
not proof of zero packets, zero TCP, absolute nondisclosure or memory erasure.

Each case used a newly launched sandboxed browser. All runs reported owned browser,
servers, display and temporary runtime removed; listener set restored and Admin
process metadata unchanged. Port 9222 was absent before, throughout runtime polling
and after. The final successful run had no code sentinel in child output, empty
stderr and 0 code-marker matches in 41 owned runtime regular files scanned after
browser close. Scope excludes deleted files, memory/swap/crash forensics and hostile
same-UID processes. No provider contact, real secret/OAuth material, user/config
change, frontend edit, host-security change or Git publication occurred.

The historical route-level failure remains below: actual 302 delivered 1 HTTP
request, 753 bytes and the synthetic code marker. The first protocol attempt was
inconclusive before navigation. Neither result is rewritten as a first-try success.
The corrected protocol gate is now closed; no further callback laboratory is due.

### Current MFA preflight and single human checkpoint

REAL_MFA_PREFLIGHT = BLOCKED_BY_HUMAN_AUTHORIZATION, not callback containment.
Marcus absent and complete JUVAl Users count 0 remain HUMAN_ADMIN_READBACK.
Existing redirect [http://127.0.0.1:18080/oauth/callback], Exact match and earlier
PKCE Required retain their recorded human evidence; these synthetic corrections
changed no provider configuration and do not make that baseline newly stale.
Viewer residual-risk acceptance is already recorded in REAL_MFA_ABORT_20260916;
no repeat acceptance is requested while that boundary remains unchanged.

One next checkpoint: explicit authorization for the future real-flow preparation,
human creation of exactly one Marcus disposable identity (not an additional second
identity), and the two-cycle real experiment; plus a named/available human operator's
cleanup commitment for that newly created identity on success, failure, abort,
controller failure or disconnection. Delete only that exact user; independently
read back complete tenant list at 0; restore any temporarily changed redirects
exactly. Do not create or start anything under this synthetic authorization.

After authorized creation, its exact identity/application registration and changed
pre-experiment count require readback once; this is new-state evidence, not repeated
verification of the unchanged zero-user baseline. Real transport remains deliberately
disabled in code and must only be wired for the separately authorized next phase.
No real-provider/MFA behavior is credited by this gate. ADR-041/042 remain Proposed;
Control 6 PARTIAL and ADR-040 measurements unchanged.


### Final delivery checks (after PASS; no further browser execution)

- Targeted Node/security suite once: 18 PASS / 0 SKIP, covering finite policy,
  protocol enforcement and restricted evidence output. Setup-discard positive and
  failure tests added for the actual correction; no new policy matrix or sensor lab.
- Relevant pytest regression once: 181 PASS / 86 SKIP; all skips require unavailable
  nginx, which this change does not modify. No skip counted as evidence.
- Offline compliance plus worktree secret-pattern scan: 8 PASS / 1 WARN / 0 FAIL;
  521 eligible files without findings. Warning is the pre-existing historical
  ROLE PLACEHOLDER. No dependency network audit, historical scan or absolute claim.
- git diff --check PASS; frontend/frontend-next/demo/src unchanged from initial HEAD.
- Self-review: actual direct and 302 navigation, active pipe interception and finite
  completion proved in the bounded fixture; no received callback application bytes
  or sentinel; no real provider/secret/identity; sandbox preserved; owned resources
  cleaned; Admin preserved; prior failed/inconclusive evidence retained. No new
  validation layer or browser experiment after PASS. Manual simplicity review;
  repository-required review tool unavailable. ADR-040 metrics unchanged.
- One coherent local corrective/evidence commit; no push or remote Git operation.

## Protocol-pipe implementation attempt — 2026-09-18 (historical)

**PARTIALLY IMPLEMENTED / integration INCONCLUSIVE / callback gate NOT CLOSED.**
Initial HEAD d9c1434db45348fe1c153792136f2ad0d751c0e6, clean worktree.
Explicit operator approval authorizes private-pipe Chromium protocol interception,
existing finite policy reuse and one bounded integration execution. No live transport,
identity creation, MFA or production authorization. Zero TCP remains unnecessary.

### Implementation and authority

New tools/protocol_auth_boundary.mjs installs Fetch interception at Request stage
for all URLs, including redirect-generated requests, on the owned blank page.
It delegates request decisions to the unchanged FlowPolicy; no second route or
transition policy. Only synthetic IPv4-loopback fixture origins can be relocated
to the existing logical provider/callback origins. It preserves credentials, path,
query and fragment for policy evaluation; it never retrieves a code value. Exact
production callback remains http://127.0.0.1:18080/oauth/callback. Real policies,
provider ports and non-fixture destinations are rejected before transport.

The adapter requires --remote-debugging-pipe and rejects network debugging and
sandbox-disabling flags using private Browser.getBrowserCommandLine output. No
argument or protocol object is exported. Fetch callback fulfillment uses a fixed
body, no-store, no-referrer and restrictive CSP; only approved fixture-provider
requests may continue. Protocol errors or unknown requests close the owned browser.
Extra targets are configured to pause and trigger closure; no arbitrary target is
resumed. Normal close destroys the browser without first disabling Fetch. New
unit tests exercise the protocol actions against the real finite policy, including
origin/path/method/shape/transition rejection and setup/detach/error handling.

The existing receiver, calibration and display/lifecycle harness are reused;
no new browser laboratory, dependency, socket control endpoint or broker. The
fixture now launches a fresh browser for each case and polls for port 9222 during
execution. Existing sensor implementation/tests remain unchanged.

### One authorized integration execution

Command: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/http_redirect_gap_lab.py.
Exit **1**, REPRODUCER_INCONCLUSIVE. Preparation/installation did not return successfully;
the fixture sets navigation_attempted only after adapter installation returns.
Both direct and 302 navigation_attempted=false. Thus **neither case executed**.
No source HTTP 302 emitted, callback browser event, protocol callback interception,
finite callback state, receiver TCP connection, application byte, HTTP request or
code marker was observed. These zero counters are NOT containment evidence.

The original finite error boundary suppressed the underlying installation error;
the exact failed protocol operation is **NOT_ESTABLISHED**. Do not attribute this
to Fetch redirect handling, target guards, pipe flags or sandbox configuration
without evidence. No sentinel crossed a receiver in this run, but the historical
route-level 302 failure below remains authoritative for that implementation.

The run closed browser/servers and removed owned display/socket/lock/runtime.
Listener baseline and Admin process metadata restored; X11 authentication checks
passed. Port 9222 absent at baseline, runtime polling and final listener comparison.
No sentinel in captured output, stderr empty; 41 remaining owned runtime regular
files had zero code-marker matches before temporary-directory removal. These are
scoped cleanup/artifact results, not RAM/swap/crash-erasure evidence.

### Bounded correction and next checkpoint

Targeted tests initially found origin relocation retained the ephemeral source
port; corrected by assigning hostname and port explicitly. Policy tests then
passed. The one browser integration subsequently stopped at installation as above.
After that stop, the same adapter/harness gained a fixed setup-failure phase enum
(ownership, pipe check, page session, target guard, WebSocket guard, Fetch enable).
Only these labels can escape; underlying exceptions/URLs/arguments remain private.
Unit tests verify the finite failure label. This improves the existing diagnostic
output, not a second validation layer. **No second browser run occurred**, so no
phase label is retroactively assigned to the measured failure.

Next exact human action: authorize one corrective execution of this same synthetic
harness with finite setup diagnostics, retaining the already-approved architecture
and all prohibitions. The explicit one-integration budget is exhausted; this is
an execution-scope checkpoint, not a request to approve another architecture or
repeat an unchanged successful test. Implementation is not labeled verified.

REAL_MFA_PREFLIGHT remains BLOCKED by incomplete protocol-adapter integration.
Marcus absent, JUVAl count 0 and redirect/Exact match retain HUMAN_ADMIN_READBACK;
no fresh provider observation. Prior viewer-risk acceptance remains recorded.
Future identity creation, cleanup scope and real experiment still require explicit
human authorization after technical closure; none is requested/executed here.
ADR-041/042 Proposed. ADR-040 metrics and all production/Amazon claims unchanged.


### Validation and review for the protocol attempt

- Targeted unit tests: 13 PASS after port relocation correction (9 existing policy,
  4 new adapter tests); affected adapter tests rerun after finite diagnostics,
  4 PASS. No calibrated sensor or previous failed browser experiment rerun.
- Relevant security regression once: pytest -q -rs tests/compliance,
  181 PASS / 86 SKIP. Skips require unavailable nginx; no nginx behavior changed.
- Single browser integration: exit 1 / INCONCLUSIVE before navigation, not PASS.
- Offline compliance/worktree secret-pattern scan: 8 PASS / 1 historical
  ROLE PLACEHOLDER WARN / 0 FAIL; 521 eligible files without pattern findings.
  No dependency network audit or history scan. No absolute secret-absence claim.
- Node syntax and git diff whitespace checks PASS; frontend/frontend-next/demo/src
  unchanged from starting HEAD. New files are source/tests, not generated artifacts.
- Self-review: policy centralized and unchanged, material containment not yet
  demonstrated, historical 302 failure preserved, no live data/provider/identity,
  no sandbox weakening/public control endpoint/push. Only configured private pipe
  and port-polling evidence are claimed; successful adapter installation is not.
  Repository-required review tool unavailable; manual simplicity review performed.
- One local partial-implementation/evidence commit; no publication. The next scope
  decision is one corrective synthetic execution, not real MFA or identity creation.

## Current decision and final bounded execution — 2026-09-18

**PARTIALLY IMPLEMENTED; CALLBACK GATE FAILED / REAL_MFA_PREFLIGHT BLOCKED.**
Initial HEAD e2dec00de3d4c47a333a0c6ee3109aade9e0de33. Three pre-existing
untracked calibration files were inspected before modification: report
SOCKET_SENSOR_CALIBRATION_20260916.md and tests/security/socket_observation_sensor.mjs
plus socket_observation_sensor.test.mjs. Legitimate authorized synthetic calibration,
not generated artifacts; no real credentials/material found in source review.
They add raw-byte and incomplete-observation detection absent from the old HTTP
counter, not a second containment mechanism. Retained for this local commit;
the calibrated sensor and its test implementation are unchanged.

**APPROVED by explicit operator instruction:** required property is
NO_CALLBACK_HTTP_REQUEST_WITH_OAUTH_MATERIAL_LEAVES_BROWSER_BOUNDARY.
Zero TCP is not required. An empty connection alone does not fail the gate.
This supersedes the old zero-TCP acceptance condition below, not its measurements.
Memory/kernel/swap/crash erasure and absence of packets are not claimed.

Reused the existing reproducer/lifecycle harness and calibrated receive-side
sensor. One bounded browser execution only; no second lab or rerun. Receiver and
source bound only ephemeral IPv4 loopback ports, excluding IdP/viewer/CDP/18080.
The receiver observes raw application bytes before an unbound in-memory HTTP
parser. Any received bytes conservatively stop the experiment and trigger cleanup.
Direct interception uses existing FlowPolicy and RealFlowController.observe;
fixture-only origin relocation maps the ephemeral sink to the policy callback.
This does not enable the production controller or prove its entire live lifecycle.
A fixed synthetic fragment is included in navigation, with no claim that fragments
normally travel in HTTP. The detector reports the code marker, not separate state
or fragment matches. Zero received bytes covers all material for the direct case;
the positive code marker alone is sufficient to fail the redirect case.

Command: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B tools/http_redirect_gap_lab.py.
Exit **2**, GAP_REPRODUCED_CONTAINMENT_BLOCKED, expected failure signaling preserved.

| Measured field | Direct interception | Actual HTTP 302 |
|---|---:|---:|
| Navigation attempted | true | true |
| Source 302 emitted | 0 | 1 |
| Callback browser request event | 1 | 1 |
| Callback handler invoked | 1 | 0 |
| TCP connections accepted | 1 | 1 |
| Application bytes received | 0 | 753 |
| Complete HTTP requests parsed | 0 | 1 |
| Synthetic code marker received | false | true |
| Sensor observation complete | true | true |
| Finite controller CALLBACK_REACHED | true | false |

Evidence classification: **BEHAVIORALLY_VERIFIED_SYNTHETIC_HTTP_REDIRECT_BYPASS**.
CALLBACK_TCP_CONNECTION = MAY_OCCUR / OBSERVED.
CALLBACK_HTTP_REQUEST_WITH_OAUTH_MATERIAL = OBSERVED_AT_SYNTHETIC_RECEIVER_302.
CALLBACK_OAUTH_SENTINEL_NETWORK_EXPOSURE = DETECTED_SYNTHETIC_ONLY.
CALLBACK_CONTAINMENT = FAILED_AT_HTTP_OAUTH_MATERIAL_BOUNDARY_FOR_302.
Direct success is scoped; it cannot close the combined gate. Route/transition
policy regressions remain separate from transport enforcement: a bypassed handler
cannot enforce its policy on the redirected network request.

Browser and both servers closed; authenticated X11 positive/negative checks passed;
owned display/socket/lock/runtime removed; full listener baseline restored;
Admin process metadata unchanged, with no Admin content interaction.
Child output contained no sentinel and stderr was empty. After browser close,
41 owned runtime regular files contained zero code-marker matches. This is a
scoped artifact check, not forensic memory/swap/deleted-file erasure evidence.
No real provider contact, real OAuth values, password/TOTP, real MFA, Marcus
recreation, redirect mutation, public listener, sandbox weakening or frontend edit.

Marcus absent, tenant count 0, redirect [http://127.0.0.1:18080/oauth/callback]
and Exact match remain **HUMAN_ADMIN_READBACK** from the prior cleanup, reaffirmed
by the operator in this task; no automated provider verification. Prior viewer-risk
acceptance remains documented. No repetitive confirmation is requested. A future
new identity and its cleanup obligation need explicitly scoped authorization after
a valid transport boundary exists; this run authorizes neither.

Next concrete decision, **PENDING**: approve a narrowly scoped internal browser
protocol interceptor over the existing private pipe, pausing every request/hop,
including redirects, applying the existing finite policy before HTTP delivery,
fulfilling the callback locally and aborting unknown routes/transitions. No TCP CDP,
agent-facing arbitrary commands, secret exports or sandbox change. Target attachment
and disconnect failure behavior must be resolved in that implementation; this is a
candidate, not a proven boundary. Broker and namespace alternatives remain below.
This extends a privileged security boundary and requires architectural approval.
The one-run authorization is exhausted; no further browser validation was run.

Other next branches remain human/external gated in IDENTITY_SECURITY_READINESS:
RF-01/RF-05 actual participant decisions/timing, RF-02 public boundary authorization,
RF-04 personnel/access decisions, sessions production migration authorization.
No independent implementation gap justifies bypassing those boundaries.
ADR-041/042 remain Proposed, Control 6 PARTIAL; ADR-040 scores unchanged.

### Validation and closeout — 2026-09-18

- Single bounded browser run: exit 2, measured 302 containment failure above;
  not counted as a passing security test. No correction/retest browser loop.
- Relevant regression once: pytest -q -rs tests/compliance, 181 PASS / 86 SKIP;
  all skips require unavailable nginx. Includes finite unexpected-route/transition
  latch and disabled-live-transport tests; these do not prove network enforcement
  when a redirect bypasses the handler.
- Node syntax checks PASS for reproducer, sensor, calibration tests and controller.
  Unchanged 13-case calibration retains its dated passing evidence; not rerun.
- Offline compliance and worktree pattern scan: 8 PASS / 1 WARN / 0 FAIL;
  519 eligible files without secret-pattern findings. Warning is the existing
  historical ROLE PLACEHOLDER. No dependency network audit or history scan.
- Diff whitespace and unchanged frontend/frontend-next/demo/src gates PASS.
  Review: measured positive evidence preserved; no raw payload exported; no
  absolute nondisclosure/erasure claim; no new dependency or production code.
  Repository-mandated review tool unavailable; manual simplicity review performed.
- One coherent local evidence/instrumentation commit authorized by this task;
  no fetch/push. A failed containment result is retained honestly, not marked green.

### Historical 2026-09-16 report (superseded where stated above)

Status: BLOCKED / PENDING DECISION. No containment implementation selected.
Starting HEAD 2714dbf, clean; cached origin/master f03574b, remote-only/local-only
0/8. REMOTE_STATE = NOT_VERIFIED. No fetch, SSH remediation, commit or push.
The operator authorized design and synthetic testing only, with immediate STOP
on inability to guarantee pre-transport containment or sentinel boundary crossing.

## Reproducer and observed result

New standalone tests/security/http_redirect_gap.mjs uses two owned HTTP servers
bound to ephemeral IPv4-loopback ports. One emits a genuine HTTP 302 Location to
the other, carrying a fixed synthetic code sentinel. No caller-supplied destination,
IdP route, real code, credential or token exchange exists. No listener on 18080,
5901, 6081 or 9222; no viewer, public bind, proxy or CDP TCP endpoint.

The callback sink independently counts TCP connections and parsed HTTP requests,
reducing synthetic request-target inspection to a boolean sentinel match. It never
logs targets/headers/body. Browser request events and route-handler invocations
are counted separately. The direct-navigation control runs before the HTTP 302
case; it requires zero TCP connections, zero HTTP requests and one callback route
invocation. All other routed traffic is aborted. The sink immediately initiates
shutdown if an HTTP request arrives; no retries or later cases follow a crossing.
This is an explicit gap reproducer, not a safe live transport adapter.

The lifecycle owner tools/http_redirect_gap_lab.py creates authenticated :100,
fresh Xauthority and private HOME/TMPDIR, launches the existing sandboxed Chromium
with a nonpersistent context, and suppresses unbounded output. Admin :99 is never
controlled. No console, DOM, trace, screenshot or storage export is enabled.

**Observed single run: exit 1, REPRODUCER_INCONCLUSIVE.**

| Measurement | Direct callback control | HTTP 302 case |
|---|---:|---:|
| Navigation attempted | true | false |
| Callback browser request event | 1 | 0 |
| Callback route-handler calls | 1 | 0 |
| Callback TCP connections accepted | 1 | 0 |
| Callback HTTP requests parsed | 0 | 0 |
| Synthetic code observed in sink request target | false | false |
| Source HTTP redirects emitted | 0 | 0 |

The direct control's zero-TCP assertion failed before the source navigation.
No assertion was weakened and the experiment was not rerun. A TCP connection
without an HTTP request is NOT proof that the code crossed the boundary; a
speculative/preconnection explanation is only a hypothesis. No raw TCP payload
capture was performed. The fixture's 302 branch exists but was NOT EXECUTED.
The original HTTP-redirect bypass is therefore still only STATIC_LOCAL_CODE_REVIEW,
not behaviorally reproduced or refuted by this run. The stop concerns inability
to claim pre-TCP containment, not an observed real or synthetic code leak.

Independent runtime evidence: SYNTHETIC_TEST for the direct connection counters.
BEHAVIORALLY_VERIFIED_SYNTHETIC_HTTP_REDIRECT = NOT_VERIFIED.
REAL_HTTP_REDIRECT_CONTAINMENT = NOT_VERIFIED. Neither the old synthetic pass nor
this direct control establishes provider-style HTTP redirect containment.

## Cleanup and artifacts

The direct-control failure ran the cleanup path: browser and both servers closed;
no dedicated browser remained, :100 socket/lock and owned temporary directory
removed. Full listener set restored; recorded Admin executable/start-time metadata
unchanged; repository status unchanged by runtime. X11 authenticated connection
accepted and empty-authority connection rejected. No host policy was changed.

Captured child output contained no code sentinel and stderr was empty. 41 regular
files remaining under the owned synthetic runtime after browser close contained
zero code-sentinel matches. Source fixture literals are test inputs, not leakage.
This check does not inspect already-deleted/transient files, unlinked files,
artifacts outside the owned runtime, swap or memory; it cannot prove absolute
absence of persistence. Only the code sentinel was scanned in these residual files.
Normal cleanup after this failing control was verified; cleanup after a successful
HTTP redirect-containment case was NOT_VERIFIED because no such case occurred.

## Threat model and candidate architectures (design only)

Protected property: the callback's code-bearing request target must not reach
its callback TCP destination or agent/log/artifact exports. Separate this from the
stronger zero-TCP-connection assertion used in the preflight/control. Redirects,
unknown origins/ports/paths, malformed inputs, OAuth errors, controller loss and
partial cleanup must not be silently allowed. The same-host/same-UID residual and
whole-tree sandbox PARTIAL remain; no candidate here protects against a malicious
process with the same authority merely by changing browser routing.

| Candidate | Interception point / HTTP redirects / failure behavior | OAuth and isolation implications | Cleanup, leakage and testability |
|---|---|---|---|
| Existing Playwright route + continue | Request routing; static implementation skips redirected requests. Direct control admits a TCP connection even when fulfilled. Does not establish pre-transport guarantee. | No PKCE/state/nonce or configuration change; existing same-UID residual. | Existing browser lifecycle is simple; code may bypass handler on redirects. Independent TCP/HTTP sink test required. Rejected as sufficient boundary. |
| route.fetch with maxRedirects=0, then fulfill | Interpose at each upstream response; a broker can inspect Location before requesting the next hop. Browser fulfillment of a 30x must itself be handled, not assumed safe. | Same URL/PKCE/state/nonce could be retained; no real redirect configuration change needed in principle. Moves bodies/cookies/response headers through broker and changes the earlier restricted handling assumptions. | Broker/context must close together; a follow-redirect mistake or logging can disclose query data. Full real 30x, session/cookie and failure tests required. PENDING architectural review; not implemented. |
| Lower-level browser interception over existing private pipe | Browser network request pause on every redirect could precede HTTP transmission; zero TCP preconnect is not guaranteed. Must cover new targets and handler installation failures. | No OAuth change or PKCE/state/nonce change in principle, but adds a privileged protocol boundary. No CDP TCP, sandbox weakening or arbitrary agent commands allowed. | Disconnect/resume/target races may fail open; cleanup must close owned browser. Real redirect and disconnect fault tests required before trusting it. PENDING; no CDP shortcut used. |
| Dedicated network namespace with minimal broker | Kernel egress boundary could deny callback TCP independent of browser redirect behavior; narrowly allow only a controlled provider broker. Fail-closed requires no bypass route and deny policy surviving controller failure. | PKCE/state/nonce remain per transaction. Same logical OAuth URI might be retained, but loopback topology and isolation change; no silent assumption that existing provider access works. Adds privilege/lifecycle assumptions requiring human architectural review. | Namespace/broker must be owned and removed; broker must avoid secret logs and unchecked forwarding. Prove attempted connects cannot reach a trap and test broker/process failure. PENDING design, not configured. |
| Callback receiver or altered OAuth response mode/URI | Receiver acts after TCP transmission and cannot meet this boundary; response-mode change alone does not establish containment. | Receiver retains same-host risk; response/URI changes alter approved OAuth assumptions and may require real configuration changes. | Listener cleanup cannot undo receipt. Easy to observe but wrong security property. Rejected for this phase. |

No candidate is selected as verified or approved for live use. The strongest
independent egress option changes approved topology/isolation assumptions and
must be reviewed rather than implemented here. The minimally invasive browser
options still need proven failure behavior and cannot currently guarantee the
required property. Work stopped; no containment fix or broader case matrix was
attempted after the failed control.

## Coverage and authority limits

Executed: direct synthetic callback with code; independently counted TCP/HTTP;
cleanup on failure; post-close scoped code-sentinel/output checks.
Not executed: HTTP 302 branch, multihop redirects, OAuth error, unexpected callback
path/host/port, malformed URL, injected containment failures, successful redirect
cleanup. Existing controller pure tests are preserved but do not substitute for
these missing HTTP cases. No claim that all phase acceptance criteria are met.

No FusionAuth contact, real MFA, user recreation, Admin content/secret inspection,
OAuth mutation, dependency change, frontend/backend change, public listener,
firewall/SSH change or Git rewrite. Historical HUMAN_ADMIN_READBACK (Marcus deleted,
JUVAl 0, Default/Daniel and existing redirect/Exact match intact) is preserved and
not relabelled as a new automated check. ADR-041/042 remain Proposed. ADR-040 and
readiness percentages unchanged. RF-03, Control 6, production/Amazon not satisfied.

APPROVED: isolated reproducer and bounded cleanup by current user instruction.
PENDING: architectural review of the exact pre-transport requirement and an
independent containment boundary. Another real MFA preflight is not yet justified.
Ponytail unavailable among exposed tools/skills; manual simplicity/security and
claim-scope review. No new dependency or modification to existing controllers.

## Closeout validation and review

- `node --check tests/security/http_redirect_gap.mjs`: PASS.
- `.venv/bin/python tools/http_redirect_gap_lab.py`: exit 1 / INCONCLUSIVE,
  measured table above. This is a failed containment control, not a passing test.
- Focused pytest controller/private-viewer/compliance-check regressions: 47 PASS.
- Broader `pytest -q -rs tests/compliance`: 181 PASS / 86 SKIP. All 86 skips
  explicitly require an unavailable nginx binary; nginx behavior is not verified.
- Full backend/database/frontend suites not rerun in this phase: changes are an
  independent synthetic reproducer, lifecycle harness and documentation only.
- Offline compliance plus worktree secret-pattern scan: 8 PASS / 1 WARN / 0 FAIL,
  516 eligible files without pattern findings. Warning: existing historical
  incident-plan ROLE PLACEHOLDER. No dependency network audit/history scan run;
  no absolute absence-of-secrets claim.
- git diff --check PASS; git diff --exit-code 2714dbf -- frontend frontend-next
  demo src PASS (empty). Independent post-close check confirms private ports free,
  :100 absent and no dedicated Chromium. Installed Playwright version reread:
  1.63.0-alpha-2026-08-31.
- Final HEAD remains 2714dbf; cached origin/master f03574b, cached 0/8.
  Three tracked documentation files modified and three new files untracked;
  no commit without the separately required human approval. No fetch or push.

Self-review: no pre-transport containment proof; real 302 fixture authored but not
executed; one TCP connection observed with no parsed HTTP request/code match;
static evidence not promoted to redirect behavioral proof; no IdP/OAuth/frontend
or existing Git history changes. Only two temporary loopback listeners were added
and removed, not publicly exposed. Fail-closed assertion unchanged; no repeated
experiment after STOP. Cleanup and evidence scope reviewed manually; Ponytail not
available. Remaining work requires architectural review, not real MFA initiation.
