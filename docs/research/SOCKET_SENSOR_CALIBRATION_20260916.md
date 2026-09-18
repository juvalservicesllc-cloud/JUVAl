# Synthetic socket observation calibration — 2026-09-16

Integration update 2026-09-18: explicit operator authorization supersedes the
historical no-integration/no-commit checkpoint below. Sensor and calibration tests
were reviewed and retained unchanged; the existing HTTP reproducer now uses this
sensor. The [one bounded browser run](HTTP_REDIRECT_CONTAINMENT_20260916.md) failed
the HTTP/OAuth boundary on an actual 302. Calibration success is not containment.

Status: IMPLEMENTED / SYNTHETIC_TEST calibration passed; human review pending. Initial HEAD e2dec00, clean;
cached origin/master f03574b, cached 0/9. REMOTE_STATE NOT_VERIFIED. No remote Git.
Authority: explicit operator approval of L0-L9 and observability-only calibration.
This document and expectations are written BEFORE the first calibration execution.

## Scope and design

Two new Node modules under tests/security only. No browser, redirect, IdP or OAuth.
Each owned IPv4-loopback ephemeral socket is observed at receive-side L5 BEFORE
its chunks are passed to Node's independent HTTP parser over an unbound in-memory
Duplex. Parser responses are discarded in memory, never sent to a destination.
No payload logging/export. Markers use a prefix automaton retaining indexes only;
no received target/suffix is retained by the matcher. Node's HTTP parser can hold
transient request/header data internally; this is not memory-erasure evidence.
A separate recognizer accepts the calibration GET/HTTP/1.1 request-line grammar;
header terminator recognition is syntactic progress, not semantic HTTP validity.
Parsed requests are counted only on complete HTTP message end, not merely headers.

Counters are bounded (4096 bytes; 16 complete requests). Timeout, protocol failure,
truncation, sensor failure, abnormal close and unattributed socket prevent a complete
observation. Marker=false only means not observed. Only clean, attributed, complete
zero-byte observation can emit NO_APPLICATION_BYTES_OBSERVED_WITHIN_SENSOR_BOUNDARY.
Never PROVEN_NO_SEND_ATTEMPT or any containment-verified state.

Fixture peer attribution uses the local owned client's port and accepted peer tuple;
this is a trusted synthetic lifecycle correlation, not same-UID adversary isolation.
All clients/listeners/parser streams must terminate. No real callback port or
public bind; assigned ports are checked against the protected set. No persistent
runtime directory, capture, trace, screenshot or compiled Python fixture is needed.

## Expectations fixed before execution

Each row/socket expects exactly one TCP accept. Bytes are fixed fixture lengths,
independently checked against client bytesWritten for the streamed send fixtures.
L/T/P = recognized request line / header terminator seen / complete parsed requests.
Except where listed: no marker, timeout, protocol failure, sensor error or abnormal
close; attribution true. Every incomplete result is INCONCLUSIVE, even with bytes.
Complete positive-byte results are APPLICATION_BYTES_OBSERVED, not containment PASS.

| Case | Expected bytes | L/T/P | Marker | observation_complete | Expected result/reason |
|---|---:|---|---|---|---|
| A empty clean TCP | 0 | false/false/0 | false | true | Scoped receive-side negative |
| B one byte G | 1 | false/false/0 | false | false | INCONCLUSIVE, truncated HTTP |
| C incomplete headers | 34 | true/false/0 | false | false | INCONCLUSIVE, truncated HTTP |
| D marker split into individual writes, each observed before next | 76 | true/true/1 | true | true | APPLICATION_BYTES_OBSERVED |
| E complete HTTP without marker | 38 | true/true/1 | false | true | APPLICATION_BYTES_OBSERVED |
| F invalid HTTP | 5 | false/true/0 | false | false | INCONCLUSIVE, protocol failure |
| G reset, no payload | 0 | false/false/0 | false | false | INCONCLUSIVE, abnormal close |
| H idle timeout | 0 | false/false/0 | false | false | INCONCLUSIVE, timeout + abnormal close |
| I sequential D then E | 76, 38 | true/true/1 each | true, false | true each | Independent states |
| J simultaneous split marker across distinct sockets | 60, 60 | true/true/1 each | false each | true each | No cross-socket matching |
| K unattributed clean empty socket | 0 | false/false/0 | false | false | INCONCLUSIVE, attribution absent |
| L sensor abort | 0 | false/false/0 | false | false | INCONCLUSIVE, sensor error + abnormal close |
| M oversize input | 4096 saturated | false/false/0 | false | false | INCONCLUSIVE, sensor error + abnormal close |

First command planned: node --test tests/security/socket_observation_sensor.test.mjs.
Assertions will not be adjusted to actual results just to obtain PASS. An implementation
failure must be diagnosed and reported; a contradiction of the approved model stops work.

## Preserved security classification

REPRODUCER_RESULT INCONCLUSIVE; HTTP_302_CASE NOT_EXECUTED;
CODE_BOUNDARY_CROSSING NOT_OBSERVED for the prior browser investigation;
REAL_HTTP_REDIRECT_CONTAINMENT NOT_VERIFIED; redirect bypass STATIC_LOCAL_CODE_REVIEW;
BEHAVIORALLY_VERIFIED_SYNTHETIC_HTTP_REDIRECT NOT_VERIFIED; REDIRECT_CONTAINMENT_BLOCKED.
Intentional marker reception in these calibration fixtures is not evidence about
that prior experiment, real OAuth traffic, or a safe containment implementation.
NETWORK_CONTAINMENT, APPLICATION_DATA_CONTAINMENT and PERSISTENCE_CONTAINMENT remain
distinct. The prior zero-TCP assertion is unchanged. ADR-041/042 Proposed; ADR-040
and its percentages unchanged. No production readiness or compliance credit.

Historical expectation-freeze state: calibration NOT_EXECUTED. Results below were
added after execution; no expected counter, flag or classification was relaxed.

## Actual measured results

Both focused executions passed all 13 cases, 0 failed, 0 skipped. The first execution
passed before manual review added a fixture guard for extra unattributed accepted
connections; the final execution passed with that stricter guard. Expectations
A-M were unchanged. The final test process exited 0 in approximately 0.40 seconds.
Every case asserts the complete finite report against its predeclared expected
object, including counters, flags, observation_complete and classification.
Therefore each cell of the expectation matrix above matched its actual result.

A: complete zero-byte receive-side negative. B/C: bytes received, incomplete HTTP,
INCONCLUSIVE. D: marker recognized despite deliberate per-character fragmentation
with each receive boundary acknowledged before the next write. E: complete HTTP.
F: protocol failure. G: owned client reset produced abnormal-close INCONCLUSIVE.
H: timeout produced INCONCLUSIVE, never negative success. I/J: sequential and
interleaved simultaneous sockets retained independent matching/parser state.
K: attribution absent prevented a complete negative. L: sensor abort prevented a
complete negative. M: overflow saturated the counter, raised sensor_error and
remained INCONCLUSIVE; 4096 is not an exact count of the oversized stream.

There were 15 owned client/socket observations across 13 cases. The sensors are
independent per socket; fixture cleanup checks every raw socket/client is closed,
all observation promises settle and the listener is not listening. Unexpected
accepted sockets unclaimed by the fixture are rejected at cleanup. These checks
run after success and after intentionally injected observation failures.

## Validation and hygiene

- Syntax checks for both new Node files: PASS before calibration.
- Final focused command: node --test tests/security/socket_observation_sensor.test.mjs,
  13 PASS / 0 SKIP. Captured test output contained no marker, request target or
  fixture header; no raw output artifact was written.
- Regression command with PYTHONDONTWRITEBYTECODE=1 and Python -B:
  pytest -q -rs tests/compliance: 181 PASS / 86 SKIP. All 86 require unavailable
  nginx; nginx behavior is NOT_VERIFIED. This includes prior controller/viewer
  configuration tests, not a browser execution. No full backend or dependency
  network audit was necessary for these test-only modules.
- Full listener set compared before/after both calibration runs: restored.
  No persistent sensor process or runtime directory is created; Node process exits.
- git diff --check and separate untracked-file whitespace checks passed.
  Protected frontend/frontend-next/demo/src, existing controllers/reproducer and
  ADR-040/041/042 have no diff from e2dec00.
- Sentinel scan over tools/tests/docs including ignored regular files found only
  the original two fixture sources and the new observation module. No unexpected
  derived/runtime artifact; prior bytecode remains absent. Python scans used -B.

## Limitations and self-review

The sensor measures bytes DELIVERED to its socket observer, not attempted writes,
packets discarded before reception or all OS/network activity. Complete means its
bounded, attributed, cleanly finished fixture observation passed every coverage
check; it does not prove no send attempt. Empty clean close can be a complete
negative without an HTTP request. Invalid/truncated HTTP deliberately keeps the
combined report incomplete even when positive byte observations are available.
A false marker flag on an incomplete report never proves absence of transmission.

Raw chunks and Node parser objects exist transiently in memory. The matcher stores
only fixed-pattern indexes, and the fixture-specific request-line recognizer stores
no target. Node's semantic parser transiently handles request/header strings.
No forensic memory/swap/deleted-file guarantee, TLS decoding, arbitrary HTTP method
recognition, marker encoding normalization or malicious same-UID isolation is claimed.
The HTTP parser is unbound and parser responses are discarded: this is synthetic
measurement instrumentation, not a deployed callback receiver or egress barrier.

No browser, 302, FusionAuth, MFA, user, real credential/code, token exchange, OAuth
change, 18080 listener, public bind, CDP, Admin automation, firewall/namespace/SSH,
production-tree change, dependency change or Git remote action occurred. No old
redirect assertion changed. No readiness percentages or ADR acceptance changed.
Manual correctness, state isolation, finite-output, cleanup and simplicity review performed. No new dependency.

Stop at the human review gate. Next proposed step is a separately authorized design
for sensor integration in a synthetic browser fixture, with the zero-TCP condition
preserved; do not run that fixture or a 302 merely because calibration passed.
No commit, integration or containment implementation is authorized by this evidence.
