# ADR-038 — Browser site topology for BFF activation

**Estado: Propuesta / PENDING. Fecha: 2026-09-10.** No domain, deployment or
cookie-policy change is approved by this document. Complements ADR-034/031.

## Problem verified in source

BFF cookies are host-only, Secure by default and SameSite=Lax. The callback is
a top-level GET, which is compatible with Lax. However, the PWA on a Vercel
provider domain fetching a Railway provider domain is cross-site, not merely
cross-origin. `allow_credentials=True` and fetch credentials do not override
SameSite. [Cookie semantics](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie#samesitesamesite-value)
exclude cross-site subresource requests under Lax. The earlier CORS comments
were insufficient as an activation plan.

## Proposed decision for the operator

Choose stable HTTPS browser/API names under the same registrable domain
(different origins are allowed). Keep host-only Lax/Secure cookies and explicit
credentialed CORS. The PWA obtains the CSRF value from `/api/v1/auth/session`
(which validates the API-host CSRF cookie and projects it), not by attempting
to read another hostname's cookie. This requires frontend integration after
the freeze is lifted; it is not implemented by changing DNS alone.

Alternative: route the BFF/API through the PWA's origin, provided the ingress
preserves all Set-Cookie headers and supports existing upload/download limits.
ADR-018 rejected Vercel Functions as the backend; do not silently reintroduce
its constraints through a proxy. No proxy/provider is selected here.

Keep unrelated sites plus SameSite=None: deferred, because it changes the
cookie/CSRF boundary and adds third-party-cookie availability constraints.
Never implement it as a silent fix for failed login.

## Acceptance before activation

Select actual frontend/API/identity hosts and TLS ownership; record exact
callback and logout URLs; verify browser login, credentialed reads and writes,
CSRF negatives, logout and all upload/download limits through the chosen
public topology. Preserve the ADR-031 outbound tunnel and loopback allow-list;
do not open inbound FusionAuth or its admin UI. Until then:
`BROWSER_SITE_TOPOLOGY = PENDING_DECISION`, `PUBLIC_LOGIN = NOT_VERIFIED`.
