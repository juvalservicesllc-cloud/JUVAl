# ADR-038 — Same-site browser topology for BFF activation

**Estado: Aceptada. Fecha: 2026-09-10.** Authority: second-wave authorization C.
Architectural direction approved; actual domain, DNS, deployment and activation
are not approved by this ADR. Complements ADR-018/031/034/036.

## Context

BFF cookies are host-only, Secure and SameSite=Lax. A PWA on a Vercel provider
domain fetching an unrelated Railway provider domain is cross-site. Credentialed
CORS does not override SameSite. Production must use HTTPS endpoints under one
owned registrable domain. `HUMAN_DOMAIN_SELECTION_PENDING`.

## Decision

Select separate same-site app/API/identity subdomains: conceptual
`https://app.<owned-domain>`, `https://api.<owned-domain>` and
`https://id.<owned-domain>`. These are placeholders, never deployable settings.
Vercel continues serving the PWA; Railway serves FastAPI/BFF directly under its
custom hostname. Identity retains the ADR-031 managed TLS/outbound tunnel to
loopback nginx/FusionAuth boundary. This avoids adding a second data-plane proxy
to uploads/downloads and preserves separate provider responsibilities.

| Concern | A: app/api/id subdomains — selected | B: same-origin /api rewrite |
|---|---|---|
| Cookies | Host-only API cookies; Secure/Lax; app cannot read API cookie directly | Host-only app cookies; proxy must preserve all Set-Cookie headers and paths |
| CORS | Explicit single app origin, credentialed requests and necessary methods/headers | Browser/API same-origin eliminates CORS for this path; direct upstream still secured |
| CSRF | Required on mutations; same-site is not a trust boundary against a compromised sibling | Still required; same-origin does not remove XSS or CSRF obligations |
| Deployment | Three names/TLS routes; Vercel and Railway custom domains; identity tunnel selected separately | Two browser names but additional rewrite routing/cache/header responsibility on Vercel |
| Upload/download | Direct API ingress, existing Railway limits still must be verified | Adds proxy limits, buffering, timeout and cache behavior to acceptance tests |
| Issuer | Stable id hostname; independent of PWA/API deployment | Same stable identity issuer; API rewrite does not change OIDC issuer |
| WS/SSE | No current backend WS/SSE endpoint found; future direct API streaming needs its own tests | Not required today; future upgrade/streaming behavior must be proven through rewrite, not inferred from Functions |
| Observability | Separate request IDs/status/latency at each service; no auth query/body/header values | Extra hop needs correlated errors and cache checks; same sanitization requirements |
| Failure modes | API/identity failures distinguishable; CORS/DNS misconfiguration explicit | PWA rewrite/cache/header outage can also break API; upstream still a dependency |

Vercel supports external-origin rewrites, so B is feasible, not rejected as
impossible. Its extra ingress behavior is unnecessary for current JUVAl and is
not yet validated. Reconsider with measured benefit and a new ADR amendment.
No unrelated-provider-domain production fallback and no SameSite=None workaround.

## Browser and OAuth contract

Keep Secure=True, host-only cookies (no Domain), HttpOnly session/transaction
cookies and Lax. Top-level GET authorization callback is compatible with Lax;
credentialed same-site app→API fetch includes API cookies. This is a semantic
design claim; real selected-host browser verification is still NOT_EXECUTED.

PWA integration must obtain the CSRF value from `/api/v1/auth/session`, which
validates the API-host CSRF cookie before projecting it. Send credentials and
X-JUVAL-CSRF on mutations. Do not read a sibling hostname's cookie or widen
Domain. No wildcard CORS, suffix-based origin trust or preview-origin wildcard.
An attacker-controlled sibling is same-site: CSRF token validation remains
mandatory. Secure trusted subdomains and prevent orphaned DNS records.

Register the exact API `/api/v1/auth/callback` HTTPS URI; no wildcard or provider
preview redirect. Pin issuer and verify exact token `iss`, discovery/JWKS/token
URLs and advertised public endpoints through the fixed-host proxy. Identity
Admin and API remain private; public /oauth2/userinfo remains unnecessary.

Logout first revokes the BFF session with CSRF protection and clears cookies;
then navigate to the configured FusionAuth end-session endpoint and an exact
approved app destination. Defaults pointing to `/` on the API host must be
replaced explicitly before activation. FusionAuth application/tenant logout
settings and iframe SSO behavior require real browser evidence; do not add frame
restrictions blindly. No promise that logout revokes every external bearer token.

## Acceptance and consequences

Domain choice remains HUMAN_DOMAIN_SELECTION_PENDING. Before activation record
TLS issuance/renewal owner, exact hosts/issuer/callback/logout origins, tunnel
provider and logging policy. Verify real browser login, Lax cookie delivery,
credentialed reads/writes, hostile-origin/CSRF negatives, expired session and
logout, uploads/downloads through the actual endpoints. No public activation,
frontend auth feature changes or production migration in this decision.
`BROWSER_SITE_TOPOLOGY = APPROVED_SAME_SITE_SUBDOMAINS`;
`PUBLIC_LOGIN = NOT_VERIFIED`.

## Primary sources checked 2026-09-10

- [Vercel external rewrites and cache behavior](https://vercel.com/docs/routing/rewrites): external proxying exists; upstream cache controls require explicit review.
- [Railway custom domains](https://docs.railway.com/networking/domains/working-with-domains): custom names and automatic certificate provisioning supported.
- [FusionAuth proxy setup](https://fusionauth.io/docs/operate/deploy/proxy-setup): external host/proxy configuration is part of public endpoint correctness.
- [FusionAuth logout](https://fusionauth.io/docs/apis/oauth/logout): configured redirect/logout destinations are required.
- [Cookie SameSite semantics](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#samesitesamesite-value).

Provider documentation supports capabilities, not a verified JUVAl deployment.
