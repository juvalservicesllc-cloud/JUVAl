# D-1 minimum public surface — fifth wave, 2026-09-10

Status: PARTIAL. Starting Git HEAD 57b2e66a1a2534298c5d417ee83e5c4c954bf9f9
matched origin/master after authenticated fetch; 0/0 and clean.
No provider configuration, redirect, user, password or MFA state was mutated.
Initial real JUVAl login evidence remains the fourth-wave experiment in
REAL_JUVAL_LOGIN_20260910.md; it is not a successful authentication claim.

## Password recovery decision

PASSWORD_RECOVERY = BLOCKED_BY_BEHAVIORAL_EVIDENCE for effective recovery behavior.
PASSWORD_RECOVERY_PUBLICATION_DECISION = NOT_REQUIRED under the approved current
operator-managed architecture; /password/* remains explicitly excluded by
ADR-035 Condition 2. An HTML link is not authorization to widen this boundary.
The fourth-wave real login visibly references /password/forgot. A fresh generic
GET returns 200 and its form/resources; /password/change without a recovery
context returns 302 toward /password/forgot. Neither proves tenant-specific
recovery enablement, email delivery or a completed password change.

Current tenant/application recovery template selection, SMTP readiness, WebAuthn
flags and MFA settings require authenticated Admin readback. A fresh controllable
Admin window needs private operator authentication. No credential fields or
existing browser profile were inspected. These configuration claims remain
NOT_VERIFIED in this wave; historical placeholder SMTP is not current evidence.

The supported provider workflow requires delivery configuration for unauthenticated
recovery. The authenticated API can instead create a reset identifier without
sending a message, which is why its grants remain restricted. No such API was
called here. See [FusionAuth forgot-password API](https://fusionauth.io/docs/apis/users/forgot-password).
That documentation also distinguishes disabled template configuration from a
renderable form; HTTP 200 alone cannot establish an enabled recovery process.

Interactions remain untested: MFA after reset, forced-change completion, lockout
persistence/clearance and effective Control 6 name exclusion. The JUVAl password
validator does not automatically protect hosted recovery. ADR-035 documents the
operator-console bypass as a residual procedural risk. Publishing recovery now
would introduce an unverified write path. Hiding a link alone would not prevent
access to that path; allow-list denial must remain authoritative.

The repository RF-03 mapping requires password/MFA/lifecycle controls, not a
particular hosted recovery endpoint. This is a reading of the recorded reviewer
requirements, not a new Amazon policy interpretation or approval. Operator
recovery availability, identity verification, security-owner coverage and
turnaround remain operational prerequisites. Do not disable recovery globally
or edit the theme merely to hide the link during this wave. A future change to
self-service recovery requires an ADR covering Control 6, MFA, lockout, delivery,
revocation and audit evidence. RF03-P6 now explicitly records ADR-035's prohibition
on passwordChangeRequired; disposable-user permission alone must not silently
supersede that architecture.

## MFA and conditional asset evidence

Fresh loopback GET /oauth2/two-factor returns 200; /oauth2/two-factor-methods
returns 302 toward authorize. Thus ROUTE_EXISTS/ROUTE_REACHABLE for the tested
GET context; ROUTE_REQUIRED_BY_REAL_FLOW and complete-flow
ROUTE_BEHAVIORALLY_VERIFIED remain NOT_VERIFIED. An error or context-free page
can return 200. No password/TOTP, enrolment or disposable user was used.
MFA_BEHAVIORAL_CHECKPOINT_REQUIRED = YES.

The provider documents separate method-selection and code-entry templates;
that supports their intended purpose, not proof that this application's flow
has traversed them. [FusionAuth MFA documentation](https://fusionauth.io/docs/lifecycle/authenticate-users/multi-factor-authentication).
Current WebAuthn enablement cannot be inferred from CSS: it is separately
configured at tenant/application level. [FusionAuth tenant configuration](https://fusionauth.io/docs/get-started/core-concepts/tenants).

Fresh CSS dependency extraction found five fontawesome files (eot/svg/ttf/woff/
woff2), all GET 200 with font/image MIME, and /assets/icons/fingerprint-overlay.svg
200 image/svg+xml. These stylesheets were loaded on the real initial form in
the prior wave, but the font/icon requests were not observed in that render.
Classification: CONDITIONAL, not required by an observed JUVAl MFA/WebAuthn flow.
The literal /css/entrypoints/${request.contextPath}/assets/icons/fingerprint-overlay.svg
also remains in CSS and returns 404. Do not silently repair or broaden routing
for an unexpanded provider template reference.

If future real behavior requires the fingerprint icon, prefer its exact path;
never infer a broad /assets/ rule. For fonts, compare the stable family filenames
against a prefix when actual glyph use is established; test supported browser
fallbacks and provider upgrades before declaring enumeration maintainable.
No WebAuthn feature was enabled to manufacture a requirement.

## Minimum-public-surface matrix

Evidence: A = accepted ADR-034/035; R4 = real initial login fourth wave;
G5 = generic GET fifth wave; C5 = shared CSS fifth wave. Y = established for
that phase; N = not required by current architecture/observed phase;
? = not verified; conditional = only if that feature/state is used.
Confidence is in the stated decision, not blanket authentication correctness.

| PATH | PURPOSE | EVIDENCE_SOURCE | INITIAL LOGIN | MFA | RECOVERY | WEBAUTHN | PUBLICATION_DECISION | CONFIDENCE |
|---|---|---|---|---|---|---|---|---|---|
| /oauth2/authorize | Code authorization/form | A,R4 | Y | ? | ? | ? | Retain exact GET/POST | High for initial form |
| /oauth2/token | BFF code/refresh exchange | A | N (render only) | Post-login protocol | N | Post-login protocol | Retain exact POST; exchange not exercised | High architecture |
| /oauth2/logout | IdP logout | A | N | Post-login | N | Post-login | Retain exact GET; full logout unverified | High architecture |
| /.well-known/openid-configuration | Discovery | A | Protocol | Protocol | N | Protocol | Retain exact GET | High |
| /.well-known/jwks.json | Signature keys | A | Protocol | Protocol | N | Protocol | Retain exact GET | High |
| /css/ | Shared styles | R4,G5 | Y | Generic only | Generic only | ? | Retain GET prefix | High initial; limited later |
| /js/ | Hosted behavior | R4,G5 | Y | Generic only | Generic only | ? | Retain GET prefix, version-compatible | High initial; limited later |
| /images/ | Theme/icons | R4,G5 | Y | Generic only | Generic only | ? | Retain current GET prefix | High initial |
| /fonts/ | Conditional glyphs | C5 | Not requested | ? | ? | ? | Keep denied pending real glyph requirement | Medium; conditional |
| /assets/icons/fingerprint-overlay.svg | Passkey affordance | C5 | Not requested | ? | N observed | conditional | Keep denied; exact candidate only | Medium; feature unknown |
| /assets/ | Arbitrary assets | No broad evidence | N observed | ? | ? | ? | Do not publish broad prefix | High absence of justification |
| /password/forgot | Hosted reset initiation | A,R4,G5 | Link only | N | Y if self-service chosen | N | NOT_REQUIRED by approved operator model; deny | High architectural exclusion |
| /password/change | Hosted reset/change | A,G5 | N | N | conditional | N | Deny; forced-change prohibited by ADR-035 | High architectural exclusion |
| /oauth2/two-factor | Factor code entry | A,G5 | N | ? real; generic 200 | ? | ? | Retain provisional exact rule; flow gate open | Medium purpose, low flow |
| /oauth2/two-factor-methods | Factor choice | A,G5 | N | ? real; generic 302 | ? | ? | Retain provisional exact rule; flow gate open | Medium purpose, low flow |
| /oauth2/userinfo | User info | A; no BFF caller | N | N | N | N | Deny; advertised does not mean required | High; BFF_USERINFO_REQUIRED=NO |
| /admin/* | Administration | A | N | N | Operator-private only | Operator-private only | Never public | High |
| /api/* | Provider internal API | A | N browser | N browser | Operator-private only | N browser | Never public | High |
| /account/* | Self-service account | A | N | N approved model | N approved model | N approved model | Never public | High |

D1_STATUS = PARTIAL. Recovery has an explicit approved exclusion; its visible
link/operational handling is a separate unresolved UX/operations matter. Remaining
critical gaps: actual MFA method/code transitions and resources under approved
configuration, WebAuthn enablement readback and any resulting supported-flow
requirements, conditional glyph use, and post-login logout/callback behavior.
Do not convert a reachability result into a successful MFA or production result.

## N-3 disposable header experiment

Run with the existing Playwright dependency, no package installation:

```
JUVAL_LAB_CHROMIUM=/path/to/cached/chromium node tools/fusionauth_header_lab.mjs
```

Ten renders: baseline plus each candidate independently, on two generic pages
(/oauth2/two-factor and /password/forgot). Fresh contexts; GET-only loopback
proxy to real FusionAuth; no cookies/auth headers/query values forwarded;
external requests blocked; no forms submitted. This is a disposable Node proxy,
NOT the nginx deployment. Assertions check header readback, HTTP 200, resource
failures, two loaded stylesheets and execution of the existing Prime library.
All ten passed. It does not exercise real MFA, WebAuthn, iframe SSO or recovery.

| Candidate | Security benefit | Compatibility evidence | MFA/WebAuthn risk | Decision |
|---|---|---|---|---|
| X-Content-Type-Options: nosniff | Limits MIME-based script/style interpretation | Generic real-provider pages and fetched scripts/styles pass | Unobserved later assets could have wrong MIME | Candidate passes limited lab; defer template activation until actual flow |
| Referrer-Policy: same-origin | Avoids cross-origin referrer disclosure | Generic resource loading passes | Actual OAuth/logout navigation not tested; same-origin still includes path/query | Candidate only; no full-flow claim |
| X-Frame-Options: SAMEORIGIN | Restricts cross-origin framing | Top-level generic renders pass | Does NOT prove iframe/SSO compatibility | Defer pending frame-flow requirements |
| Permissions-Policy: publickey-credentials-get=(self), publickey-credentials-create=(self) | Limits credential API delegation to self | Header readback and generic render pass | No authenticator call or cross-origin frame tested | Defer pending actual WebAuthn configuration |
| CSP | Resource/framing constraints | NOT_EXECUTED | Full dynamic dependency/violation inventory absent | Do not activate |
| HSTS | HTTPS-only persistence | NOT_EXECUTED | Real HTTPS/domain absent | Defer |
| Per-IP authorize throttle | Abuse control | NOT_EXECUTED | Shared NAT/retry denial-of-service risk | No naive rule |

N-1 remains remediated. The existing nginx template was unchanged. Fresh generic
nginx-to-real-FusionAuth GET probes, denied paths and hostile-header relative
redirect checks passed through --generic-surface-only, without a temporary URI.
Header delivery upstream is separately covered by the echo lab; do not infer
it from provider status. No accidental public surface expansion occurred.

## Validation and remaining checkpoint

Fresh backend gate with extracted user-space nginx: 841 PASS / 43 SKIP, one
existing Starlette/httpx deprecation warning. Generic real-upstream lab: 32 GET
paths and three hostile-header relative-redirect checks passed. Header lab:
10 renders passed, including header readback and Prime execution. Compliance:
9 PASS / 1 WARN / 0 FAIL; secret scan 493 files, no findings. Python installed
dependency audit reports no advisories. npm audits, PostgreSQL and frozen
frontend suites NOT_RUN this wave: no dependency, DB or frontend changes.
No GitHub CLI is available; DEPENDABOT_METADATA=BLOCKED_BY_GITHUB_AUTHORIZATION,
DEPENDENCY_SECURITY_STATUS=PARTIAL / GITHUB_METADATA_REQUIRED. No alert identity
is inferred and this does not block independent work.

Admin private authentication remains required for exact tenant/application
readback; the new window on display :99 is retained deliberately for that
handoff. All header proxies, lab browsers and nginx scratch were removed.
No temporary redirect was added, so restoration is NOT_APPLICABLE_NO_MUTATION;
the historical []/ExactMatch baseline was not reused as a current observation.
Actual MFA discovery requires separate disposable-user and private credential/
TOTP authorization. RF03 execution remains NOT_AUTHORIZED. Live migration,
production auth, public infrastructure, actual domain and Amazon submission
remain outside this run's authorization. Off-host destination/custody and
security-owner decisions remain human. No new ADR policy was adopted; accepted
ADR-035 was applied and ADR-037's evidence updated. Ponytail unavailable;
manual simplicity/security review used. No frontend or nginx-template change.
