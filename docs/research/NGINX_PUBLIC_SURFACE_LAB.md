# nginx public identity surface — laboratory measurement

**Date: 2026-09-10.** Status: **EXECUTED AND TORN DOWN.** The shipped template
`deploy/fusionauth/nginx-fusionauth-public.conf` was run under a real nginx on
loopback against a disposable echo upstream. **No production runtime was
touched**: nginx was never activated, `/etc/nginx` was never read or written,
FusionAuth was never contacted, no LAN port was opened, `JUVAL_AUTH_MODE` was
not set, and no migration was applied.

Governing decisions: ADR-034 (BFF), ADR-035 (Condition 2 — the never-publish
list), ADR-031 (network frontier). Companion lab:
`FUSIONAUTH_169_IDENTITY_LAB.md`, which measured the *provider*; this one
measures the *proxy*, and the distinction is the whole point of §5.

Reproduce with:

```bash
python tools/nginx_surface_lab.py            # 59 probes + 4 measurements
python -m pytest tests/compliance/test_nginx_public_surface.py -q
```

---

## 1. Why a laboratory and not another reading

Every claim about this file has so far come from reading it. Reading cannot
establish that an allow-list denies what it claims to deny, and it cannot
establish that nothing denied reaches the upstream — the property the file
exists to provide. It also could not have found either of the two findings in
§4, both of which are behaviours nginx supplies on its own, invisible in the
text of the configuration.

`nginx -t` is not the test either. A configuration that parses is a
configuration that parses.

## 2. Lab architecture

```
  probe client  ──►  nginx 1.24.0  ──►  echo upstream (Python, stdlib)
  (http.client)      127.0.0.1:<eph>     127.0.0.1:<eph>
                     scratch prefix      records every request it receives
```

| Property | Choice | Why |
|---|---|---|
| nginx binary | `apt-get download nginx` + `dpkg-deb -x` into a scratch directory | A user-space binary. **No `sudo`, no `apt install`, no system package state.** `nginx -v` → `nginx/1.24.0 (Ubuntu)` |
| Prefix, pid, logs, temp paths | one `mktemp -d`, removed in `finally` | Nothing outside the scratch tree exists after the run |
| Configuration | the **shipped template**, three narrow substitutions | See §3 — this is what makes the results transferable |
| Listener | ephemeral port on `127.0.0.1` | Never `8080`; never a LAN interface |
| Upstream | disposable echo server | Never `9011`/`9012`. **The lab is structurally incapable of reaching FusionAuth**, even if it were running on the same host |
| Credentials | none | The lab has no API key, no client secret and no token, so it has none to leak |

## 3. What was substituted, and what could not be

`render_lab_config()` rewrites exactly three things and then asserts that every
`location`, `limit_except`, `return` and `proxy_set_header` line survived
byte-identical. If a future template grows a rule that needs rewriting to run
here, that assertion fires rather than the lab silently testing something else.

| Substituted | From | To |
|---|---|---|
| Listener | `listen 127.0.0.1:8080;` | ephemeral loopback port |
| Upstream | `http://127.0.0.1:9011` (×10) | the echo server's port |
| Hostname include | `include /etc/nginx/juval-fusionauth-host.conf;` | `set $juval_public_host "idp.lab.invalid";` |

The include is absent from the repository by design. Measured separately: with
the include removed and nothing put in its place, **`nginx -t` rejects the
configuration** and names `juval_public_host`. That is fail-closed — had nginx
tolerated it, `$juval_public_host` would have expanded to the empty string and
FusionAuth would have advertised an issuer with a blank host.

`idp.lab.invalid` uses the RFC 2606 reserved TLD: it cannot resolve, so no
probe can leave the host even by accident.

## 4. Findings

### N-1 — "everything else is 404" has three exceptions, and they are not inert

nginx redirects an unslashed URI to a prefix location that ends in a slash and
is handled by `proxy_pass`. The template has three such locations, so:

```
GET /css      Host: attacker.example
-> 301  Location: http://attacker.example:<listen-port>/css/
```

Measured for `/css`, `/js` and `/images`. The `Location` is built from the
**client's own `Host` header** plus this listener's scheme and port.
`proxy_set_header Host $juval_public_host` cannot influence it, because the
redirect is generated before anything is proxied.

Three consequences, all on the public surface:

| | Observed | Consequence |
|---|---|---|
| Host reflection | `attacker.example` appears in `Location` | The identity origin emits a redirect to a host the client chose |
| Scheme | `http://` | A downgrade on a surface that is https-only by construction |
| Port | `:8080` in production | Discloses the loopback port of the identity surface |

`absolute_redirect off;` collapses all three into a relative `Location: /css/`.
**Not applied** — it is a behaviour change to a deployment template, so it is a
decision, not a cleanup. Until decided, this is a known exposure. The three
prefixes are already the widest and least justified rules in the file (§5), so
the cheapest resolution may be to remove them rather than to patch them.

### N-2 — traversal above the root fails closed, and earlier than expected

`/../admin`, `/%2e%2e/admin` and `/js/../../api/user` return **400** before any
location is chosen. `//admin`, `/admin/./` and `/css/./../admin` normalise and
land in the 404 catch-all. No traversal variant probed reached the upstream.

This was expected to be 404; 400 is stronger, and the difference is recorded
because a future nginx change here would be a real regression.

### N-3 — the template pins no security headers and no rate limit

The 404 response carries no HSTS, `X-Frame-Options`, `X-Content-Type-Options`,
`Content-Security-Policy` or `Referrer-Policy`, and identifies the server as
`nginx/1.24.0 (Ubuntu)` in both header and body — `server_tokens` is unset.

This is a statement about the template, not about production: the file is a
`server {}` block, and whatever `/etc/nginx/nginx.conf` sets in the surrounding
`http {}` context would apply. That file is not in this repository, so **the
template alone does not pin any of it**. Recorded so the gap is not assumed
closed.

There is also no `limit_req` on `/oauth2/authorize`, which is the endpoint the
hosted form posts credentials to. Password spraying against the public identity
surface is currently bounded by nothing in this file. `NOT_A_DEFECT_YET` —
Phase 2 has not happened — but it belongs in the Phase 2 decision.

## 5. The distinction that governs every classification below

The five rules the template marks `NOT_VERIFIED` are **not** unverified because
nobody checked the proxy. They are unverified because nobody has established
what FusionAuth 1.69.0 does:

* does it serve `/oauth2/two-factor` and `/oauth2/two-factor-methods` at all?
* which asset paths do its hosted login and second-factor pages actually
  request — are `/css/`, `/js/` and `/images/` the right prefixes, or even
  prefixes at all?

Those are questions about the provider. **This lab cannot answer them**, by
construction: its upstream is an echo server. Answering them needs a fresh
FusionAuth 1.69.0 instance, which is out of scope here and remains a Phase 2
prerequisite. Nothing in §6 promotes them.

What the lab *does* settle is that the proxy dispatches, denies and forwards as
written — including the two places where it measurably does not (§4).

## 6. Rule-by-rule classification

`LAB_BEHAVIOURALLY_VERIFIED` below means: measured under a real nginx against a
mock upstream, asserted in `tests/compliance/test_nginx_public_surface.py`,
reproducible from a clean checkout. It is **not** production evidence and may
not be cited to Amazon.

| # | Rule | Proxy dispatch | Provider need |
|---|---|---|---|
| 1 | `= /.well-known/openid-configuration` | **LAB_BEHAVIOURALLY_VERIFIED** — GET/HEAD 200, POST 403 | VERIFIED (protocol) |
| 2 | `= /.well-known/jwks.json` | **LAB_BEHAVIOURALLY_VERIFIED** — GET 200, POST 403 | VERIFIED (protocol) |
| 3 | `= /oauth2/authorize` | **LAB_BEHAVIOURALLY_VERIFIED** — GET/POST 200 with the query intact, DELETE 403 | VERIFIED (protocol) |
| 4 | `= /oauth2/token` | **LAB_BEHAVIOURALLY_VERIFIED** — POST 200, GET/OPTIONS 403 | VERIFIED (protocol) |
| 5 | `= /oauth2/logout` | **LAB_BEHAVIOURALLY_VERIFIED** — GET 200, POST 403 | VERIFIED (protocol) |
| 6 | `= /oauth2/two-factor` | **LAB_BEHAVIOURALLY_VERIFIED** — GET/POST 200, PUT 403 | **NOT_VERIFIED** |
| 7 | `= /oauth2/two-factor-methods` | **LAB_BEHAVIOURALLY_VERIFIED** — GET/POST 200 | **NOT_VERIFIED** |
| 8 | `^~ /css/` | **LAB_BEHAVIOURALLY_VERIFIED** — GET 200, POST 403; **plus finding N-1** | **NOT_VERIFIED** |
| 9 | `^~ /js/` | as above, plus N-1 | **NOT_VERIFIED** |
| 10 | `^~ /images/` | as above, plus N-1 | **NOT_VERIFIED** |
| 11 | `/` (catch-all) | **LAB_BEHAVIOURALLY_VERIFIED** — 404, never proxies | n/a |

Cross-cutting properties, all `LAB_BEHAVIOURALLY_VERIFIED`:

| Property | Measured |
|---|---|
| **No denied request reaches the upstream** | 0 of 45 non-proxied probes made upstream contact (8 wrong-method, 31 unpublished, 3 malformed, 3 redirected) |
| Never-publish list (ADR-035 Condition 2) | `/admin`, `/admin/`, `/admin/login` (GET and POST), `/api`, `/api/user` (GET and POST), `/api/status`, `/account`, `/account/`, `/password/forgot`, `/password/change` → all 404 |
| Unused OAuth flows | `/oauth2/{register,passwordless,device,consent,start-idp-link,two-factor-enable,two-factor-enable-complete}` → all 404 |
| Exact means exact | `/oauth2/authorize/`, `/oauth2/authorizex`, `/oauth2/token/x`, `/OAuth2/authorize`, `/.well-known/`, `/.well-known/security.txt` → all 404 |
| `Host` forwarded | `idp.lab.invalid` even when the client sends `attacker.example` |
| `X-Forwarded-Host` | `idp.lab.invalid`, client value discarded |
| `X-Forwarded-Proto` | `https` even when the client sends `http` |
| `X-Forwarded-Port` | `443` even when the client sends `80` |
| `X-Forwarded-For` | `203.0.113.9, 127.0.0.1` — appends, does not replace |
| Query preservation | `/oauth2/authorize?…` forwarded byte for byte, including `state`, `nonce`, `code_challenge_method=S256` and the percent-encoded `redirect_uri` |
| Missing host include | `nginx -t` rejects the file and names the variable |

The forwarded-header row matters beyond hygiene: FusionAuth builds its issuer
from those headers, and `interfaces/api/auth.py` validates tokens against a
fixed issuer. A client able to move either one would break that agreement. It
cannot.

## 7. What this does not change

| Marker | Value | Why unchanged |
|---|---|---|
| `CONTROL_6_AMAZON` | `PARTIALLY_SATISFIED` | Untouched by this pass |
| `RF03_BEHAVIORAL` | `NOT_EXECUTED` | Needs a running IdP and a real user |
| `AMAZON_REAPPLICATION` | `BLOCKED` | Unchanged |
| `IDENTITY_SECURITY_GATE` | `BLOCKED` | Unchanged |
| `JUVAL_AUTH_MODE` | unset | Unchanged |
| Phase 2 | blocked | The five provider-side questions of §5 are still open, and N-1 is now an open decision on top of them |

**Nothing in this document is production evidence and none of it may be cited
to Amazon.** It is a laboratory measurement of a template that is not deployed.

## 8. Teardown

The nginx process was terminated, the echo server closed, and the scratch
prefix removed by the harness's `finally` block. The downloaded `.deb` files and
the extracted binary live only in the session scratch directory and are not
part of the repository. No process, socket, or temporary directory survives the
run; `tools/nginx_surface_lab.py` is idempotent and leaves nothing behind.

## 9. Open decisions handed back

1. **N-1**: apply `absolute_redirect off;`, narrow the three prefixes to exact
   asset paths, or remove them — one of the three, before Phase 2.
2. **N-3**: decide whether the template must pin its own security headers and a
   `limit_req` on `/oauth2/authorize`, rather than inheriting whatever the host
   `http {}` block happens to set.
3. The five provider-side questions of §5 still require a fresh FusionAuth
   1.69.0 lab. Unchanged from 2026-09-09.

## 10. Accelerator remediation — 2026-09-10 (supersedes open N-1 above)

ADR-037 pins relative nginx redirects and suppresses version disclosure in the
inactive template. Fresh lab: **90 passed, 0 skipped**. N-1 is
`REMEDIATED_TEMPLATE / LAB_BEHAVIOURALLY_VERIFIED`; not production verified.
`/css`, `/js`, `/images` return relative 301 with queries preserved, under three
Host variants each; none reach upstream. N-3 version disclosure is fixed in
generated 301/400/404 responses. Other headers and rate limits remain pending
compatibility/policy. The historical measurements above describe the old file.

The allow-list is unchanged. D-1 and the real-login asset inventory remain
blocked by redirect baseline/Admin UI access. No service activation or public
TLS occurred. Reproduce with the test command above and a user-space nginx.
