# Real JUVAl hosted login — 2026-09-10

## Initial login evidence

INITIAL_LOGIN_BEHAVIORALLY_VERIFIED. Actual application
84f077a0-b2b0-4655-8168-082b2233d029, approved callback
http://127.0.0.1:18080/oauth/callback. Authenticated Admin UI readback established
complete authorizedRedirectURLs = [] and authorizedURLValidationPolicy = ExactMatch.
Only the callback was added; saved form readback showed exactly that one URI.
Three bounded render/lab cycles each restored [] / ExactMatch by saved readback.
TEMP_REDIRECT_PRESENT_AFTER_CLEANUP = NO
ORIGINAL_REDIRECT_CONFIGURATION_RESTORED = YES
No other form control was edited. No credential submitted to the JUVAl login,
no user created, no callback completed or code exchanged. Admin authentication
was performed privately by the operator. No secret values were extracted.

Fresh Chromium context, service workers blocked, only literal-loopback origin
allowed: authorization code request with ephemeral S256 challenge, state and
nonce. Both loginId and password fields visible; POST form action /oauth2/authorize.
Waited for network idle and document.fonts.ready. Only paths/status/MIME/resource
types captured, never HAR, screenshots, cookies, HTML bodies or query values.
The HTML probe separately confirms status 200 and real login form signature.

| Path group | Observation | Public decision for current evidence |
|---|---|---|
| /css/ | BOTH: two stylesheets loaded by real browser, 200 text/css | REQUIRED_PUBLIC; retain prefix for theme/upgrade compatibility |
| /js/ | BOTH: seven scripts loaded, 200 text/javascript | REQUIRED_PUBLIC; retain prefix, including versioned prime library |
| /images/ | BOTH: footer logo and favicons loaded; additional icon sizes/manifest referenced in HTML and 200 through proxy | REQUIRED_PUBLIC; retain current prefix pending wider device coverage |
| /fonts/ | CONDITIONAL: generic/shared CSS references; no font request in this actual render | UNKNOWN for later UI states; remains denied, do not claim D-1 fully resolved |
| /assets/icons/fingerprint-overlay.svg | CONDITIONAL: generic shared theme/WebAuthn evidence; not requested in actual render | CONDITIONAL; remains denied pending actual WebAuthn requirement |
| broad /assets/ | NOT_OBSERVED | NOT_REQUIRED by observed render; no broad publication justified |
| /oauth2/authorize | OBSERVED_REAL_JUVAL_LOGIN form and document | REQUIRED_PUBLIC |
| /oauth2/two-factor | NOT_OBSERVED in credential-free login; direct GET 200 through proxy | UNKNOWN for effective MFA flow; existing rule not promoted by status alone |
| /oauth2/two-factor-methods | NOT_OBSERVED in login; direct GET 302, not followed | UNKNOWN for effective MFA flow |
| /password/forgot | OBSERVED_REAL_JUVAL_LOGIN navigation reference; 404 through proxy | Excluded by existing security boundary; user-facing recovery remains unresolved |
| /oauth2/userinfo | NOT_OBSERVED, BFF has no caller; 404 through proxy | NOT_REQUIRED by BFF; advertised discovery is not a requirement |

D1_STATUS = PARTIAL: initial render works with existing allow-list; conditional
fonts/WebAuthn, MFA and recovery-path compatibility remain unverified. No nginx
publication was widened. Initial login evidence is not complete authentication
flow evidence and is not PRODUCTION_VERIFIED.

## Real upstream loopback lab

`tools/fusionauth_nginx_loopback.py --temporary-redirect-confirmed` requires
user-space JUVAL_NGINX_BIN and independent Admin baseline/add/readback first.
It renders the unchanged template with an ephemeral loopback listener and
placeholder Host idp.lab.invalid, upstream real 127.0.0.1:9011. No public domain
is invented. Access/error logs disabled; all processes/scratch cleaned in finally.
After every run, remove only the temporary URI in Admin, save and verify full
original list/policy. The flag does not itself prove configuration or cleanup.

RUNTIME_LOOPBACK_VERIFIED for initial authorize HTML and 38 GET paths. All
observed initial CSS/JS/images return 200; /admin, /api, /account, /password,
/password/forgot and /oauth2/userinfo remain 404. Fonts and conditional icon
remain 404 intentionally pending evidence. Three unslashed prefixes return
relative 301 with query preserved despite hostile Host and forwarded headers.
Header arrival at upstream is established separately by the echo lab, not by
real-provider status alone. No 9011/9012 listener or public configuration changed.

N-1 remains remediated. N-3 server_tokens remains tested; correct observed CSS/JS
MIME strengthens nosniff readiness but does not prove MFA/WebAuthn compatibility.
No new CSP, HSTS, frame, Permissions-Policy or IP rate limit activated.

Sanitized path artifacts alongside this report preserve the actual observations.
Reproduce browser inventory using an ephemeral Playwright context with the above
network restrictions and exact PKCE request; do not use an authenticated Admin
context for the JUVAl login probe. Public/TLS, RF03 and production session
activation remain separately blocked and unauthorized.

## Validation gate

Full backend with disposable nginx: 841 PASS / 43 SKIP; one existing
Starlette/httpx deprecation warning. New lab tests enforce explicit precondition
and reject private-route/required-asset regressions. Compliance 9 PASS / 1 WARN
(security owner) / 0 FAIL. Secret scan 488 files, no findings. Frozen frontend
trees unchanged. PostgreSQL behavior was not changed by this continuation; its
prior fourth-wave 53 PASS / 2 SKIP is not a newly executed result here.
