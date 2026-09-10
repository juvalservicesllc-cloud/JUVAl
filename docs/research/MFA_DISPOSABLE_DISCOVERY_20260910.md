# Single-user MFA discovery — 2026-09-10

Status: PARTIAL, cleanup VERIFIED. Starting HEAD e7d49ae6f37882cc9e1bc38dff3a15efc9fde841.
The operator authorized exactly one disposable user, human-private password/TOTP,
no forced change, recovery, lockout test, WebAuthn, Control 6 test or RF03 run.
A subsequent explicit authorization allowed an Admin password change for that
same user only. No second user was created.

## Baseline and restoration

Fresh authenticated UI baseline: JUVAl tenant 5fcaaf07-8832-491a-a6e7-35d348a591b6,
application 84f077a0-b2b0-4655-8168-082b2233d029. Unfiltered Users view showed
1–1 of 1 results, sole user in Default; exact-ID tenant form name JUVAl. Thus
JUVAl count 0. Required MFA/authenticator enabled, email/SMS factors disabled;
application inherited MFA. Tenant/application WebAuthn disabled. Redirects []
and ExactMatch. These are VERIFIED_CONFIG, not behavioral claims.

| Mutation | BEFORE | TEMPORARY | AFTER |
|---|---|---|---|
| JUVAl user | 0 | Exactly one fictitious .invalid identity, ID fda5fe1d-f658-4fca-adcc-d5534be75987 | 0; global list 1–1 of 1, only Default, exact disposable links absent |
| Registration | No disposable registration | JUVAl application, no roles | Deleted with user |
| TOTP | No disposable user/factor | One factor visible after human enrollment | Deleted with user |
| Redirects | [] / ExactMatch | Only http://127.0.0.1:18080/oauth/callback | [] / ExactMatch, saved readback |
| Admin password update | Original disposable credential | Attempts rejected by provider policy; no successful update evidenced | User deleted; no credential retained |

passwordChangeRequired was never selected/set; the UI continued to offer the
separate Require password change action, and initial login reached enrollment
without a forced-change page. No policy was weakened. Email delivery was explicitly
set to Do not send at creation. The user was deleted using its exact ID/tenant
and the required DELETE confirmation. Initial delete without that confirmation
had not removed it; cleanup was not claimed until the final complete-list readback.
Provider audit history is not erased or claimed restored; counts/configuration
and the disposable user's associated live state are the restoration scope.

## Actual direct-runtime behavior

Human-private initial credentials advanced to /oauth2/two-factor-enable.
The page required configuring a factor and presented human-private enrollment.
After the human TOTP step it reached /oauth2/two-factor-enable-complete with
Recovery codes heading. The agent did NOT read/export recovery codes, QR or seed.
Done submitted to that exact endpoint, then GET /oauth2/consent continued to the
approved /oauth/callback. A fresh Playwright context intercepted the callback and
returned a static acknowledgment; no authorization-code inspection or token
exchange occurred. Admin readback showed one MFA method and one JUVAl registration.

This disproves the universal hosted-enrollment impossibility inferred from earlier
isolated API results. Those API observations remain historical; the runtime version
was not freshly verified here, so this is not a vendor-version regression claim.
The candidate onboarding direction is recorded in Proposed ADR-041, not silently
promoted to an accepted production policy.

MFA_ENROLLMENT_STATUS = DIRECT_RUNTIME_BEHAVIORALLY_VERIFIED
MFA_CHALLENGE_STATUS = NOT_VERIFIED for a later login using the enrolled factor.
MFA_LOGIN_BEHAVIORAL_STATUS = PARTIAL (enrollment + callback, not complete BFF login).
The sanitized JSON inventory maps methods/paths to stages without protocol values.

| Route/resources | Initial | MFA | Callback/logout | Publication/evidence |
|---|---|---|---|---|
| /oauth2/authorize GET/POST | Observed | Entry | Code-flow architecture | Retain exact; direct runtime |
| /oauth2/two-factor-enable GET/POST | No | Enrollment observed | No | Add exact inactive candidate |
| /oauth2/two-factor-enable-complete GET/POST | No | Completion observed | Continues authorization | Add exact inactive candidate |
| /oauth2/consent GET | No | After enrollment | Observed before callback | Add exact GET only; POST not observed |
| /oauth2/two-factor, /oauth2/two-factor-methods | No | Existing-factor challenge NOT_VERIFIED | No | Existing provisional exact rules |
| /js/qrcode-min-1.0.js, /js/oauth2/OAuth2TwoFactorEnable.js | No | OBSERVED_REAL_JUVAL_MFA | No | Covered by existing /js/ prefix |
| /css/, shared /js/, /images/ | Observed | Observed | Theme resources | Existing prefixes sufficient for observed flow |
| /fonts/ | Not observed | Not observed | Not observed | Remains denied; do not generalize to every MFA state |
| /assets/ | Not observed | Not observed | Not observed | No broad publication; WebAuthn disabled |
| /oauth/callback | No | After completion | Reached browser-intercepted callback | BFF callback behavior/token exchange NOT_VERIFIED |
| /oauth2/token | Protocol only | No exchange tested | No | Existing exact POST, architectural requirement |
| /oauth2/logout | No | No | GET observed, then default / landing | SSO revocation and application logout NOT_VERIFIED |
| / | No | No | Default logout navigation observed | Do not expose IdP root; configure approved app logout target later |
| /password/* | No | No | Recovery excluded | NOT_REQUIRED, ADR-035; remains blocked |
| /oauth2/userinfo | No | No | BFF has no caller | NOT_REQUIRED; remains blocked |
| /admin/*, /api/*, /account/* | No | No | No browser requirement | NOT_PUBLIC; remains blocked |

## Proxy attempt, interruption and gates

The updated inactive template adds only the three exact paths above. Real nginx
syntax/echo-lab gate: 98 PASS, including new method negatives and suffix denials.
The loopback proxy rendered the actual JUVAl initial form. Subsequent human
credential attempts returned Invalid login credentials; the agent stopped retries.
An explicitly authorized password update was rejected first by validation and
then by minimum-age policy. No policy override/unlock/recovery was performed.
This incidental observation is NOT an RF03/Control 6 test or readiness credit.
The experiment was ended and cleaned instead of leaving a user pending indefinitely.

Fresh no-cookie GET checks through the candidate proxy: enrollment 302, completion
200, consent 200; admin/API/password-forgot/userinfo all 404. These statuses do
NOT verify authenticated enrollment through nginx. Actual proxy MFA challenge,
full callback exchange and logout remain blocking gaps. No production activation.

Full backend with disposable nginx: 849 PASS / 43 SKIP, one existing Starlette/httpx
warning. N-1 and forwarded-header/query/negative-upstream properties pass in the
echo lab. Header candidates were NOT exercised over every real enrollment page;
no new header was activated. Prior generic header evidence remains limited.
CSP/HSTS/rate limiting unchanged. PostgreSQL/frontend suites not rerun: no such
implementation change. RF03 remains NOT_AUTHORIZED, Control 6 PARTIALLY_SATISFIED,
Dependabot metadata independently BLOCKED_BY_GITHUB_AUTHORIZATION.

D1_STATUS = PARTIAL. The candidate's enrollment-through-proxy gate, existing-factor
challenge/resources and complete callback/logout must still pass. A fresh
experiment requires new explicit disposable-user authorization: the one-user
allowance of this experiment is exhausted and its identity has been removed.
Use a human-private credential retained correctly for that future session; do not
reuse any credential shared in conversation. No secrets were copied into tools,
artifacts or logs; browser inspection excluded password/TOTP/QR/recovery fields.

Final publication gate: compliance 9 PASS / 1 WARN / 0 FAIL (security role
assignment pending); secret scan clean across 494 files; installed Python
dependencies pip-audit reported no known vulnerabilities. This does not resolve
the unavailable GitHub Dependabot alert metadata. Frozen frontend paths have
no diff from the starting HEAD.
