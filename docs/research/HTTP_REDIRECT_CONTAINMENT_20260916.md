# HTTP redirect containment: synthetic reproducer and design review — 2026-09-16

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
