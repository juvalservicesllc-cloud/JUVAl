# ADR-037 — Harden nginx-generated identity responses

**Estado: Aceptada. Fecha: 2026-09-10.** Authority: the operator's Autonomous
Accelerator instruction authorizes evidence-supported N-1 remediation and
low-risk N-3 hardening in inactive templates and disposable labs. This decision
does not authorize production activation or new public routes.

## Decision and evidence

Pin `absolute_redirect off` and `server_tokens off` in the existing inactive
identity server block. The prior lab proved that nginx generates redirects for
`/css`, `/js`, `/images` using the request Host, HTTP scheme and loopback port.
Relative redirects preserve browser path resolution without reflecting those
values. Suppress nginx version disclosure in its headers and generated bodies.

The [nginx directive reference](https://nginx.org/en/docs/http/ngx_http_core_module.html#absolute_redirect)
defines relative nginx redirects when absolute redirects are disabled;
[server_tokens](https://nginx.org/en/docs/http/ngx_http_core_module.html#server_tokens)
controls version emission. This does not sanitize upstream redirects or hide
the existence of nginx.

**LAB_BEHAVIOURALLY_VERIFIED**: 90 nginx tests passed against the shipped
modified template using a user-space nginx binary and disposable echo upstream.
Tests cover all existing positive/negative routes and headers, nine combinations
of bare prefixes and Host values with query preservation, and version omission
on 301/400/404 responses. Denied and redirected requests never reach upstream.
No FusionAuth, public listener, TLS endpoint or runtime config was changed.

## Deferred boundaries

The final asset allow-list still requires real JUVAl login evidence. No new
`/fonts/`, `/images/`, `/assets/` or `/oauth2/userinfo` exposure is authorized.
N-1 is fixed in the template/lab, **not production verified**. D-1 remains open.
N-3 is partial: nosniff requires correct CSS/JS MIME responses; frame policy,
Referrer-Policy, Permissions-Policy and CSP require hosted-flow compatibility.
HSTS depends on the actual HTTPS hostname. Rate limiting needs a separate
policy accounting for shared NAT, OAuth retries and provider lockout.

Rollback before activation: revert these two directives in a new commit and
rerun the lab. Any later deployment rollback requires normal production change
control; no production deployment occurred in this decision.
