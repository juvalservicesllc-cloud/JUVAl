# FusionAuth public surface — read-only discovery

**Date: 2026-09-10.** Status: **EXECUTED, READ-ONLY.** The running FusionAuth
1.69.0 instance on `juval-server` was queried over loopback with GET and HEAD
only. **No FusionAuth state was modified**: no user created, no tenant,
application, OAuth, MFA or password-policy change, no API key used, no admin
credential used, no login attempted, no form submitted, no service restarted.
`JUVAL_AUTH_MODE` remains unset, no migration was applied, nginx was not
activated, no firewall rule was touched and `frontend/` was not opened.

Companion documents: `NGINX_PUBLIC_SURFACE_LAB.md` (which measured the
*proxy*) and `FUSIONAUTH_169_IDENTITY_LAB.md` (which measured the *provider*
in an isolated lab). This one measures the **running provider**, read-only, to
answer the question the nginx lab explicitly could not: what do FusionAuth's
hosted pages actually request?

Reproduce with:

```bash
python tools/fusionauth_surface_discovery.py
python -m pytest tests/compliance/test_fusionauth_surface_discovery.py -q
```

---

## 1. Safety properties, enforced in code rather than promised

`tools/fusionauth_surface_discovery.py::fetch()` is the only network call in
the module, and it raises rather than proceeds when either invariant is
broken:

| Invariant | Mechanism | Tested |
|---|---|---|
| GET/HEAD only | `method not in SAFE_METHODS` → `UnsafeRequest` | 5 methods |
| Loopback only | literal loopback IP, HTTP(S), no URL credentials, environment proxies disabled → `UnsafeRequest` | 3 hosts |
| No credentials | no API key, client secret, password or TOTP is read or accepted | by construction |
| No secret in output | `sanitize_url()` redacts all query values except numeric dotted `version` metadata; cookies are reported as `SET_COOKIE_PRESENT = YES/NO` only | 17 parameters |
| Redirects not followed | `_NoRedirect` — a redirect is evidence, not a hop | — |

Cookie headers arrive transiently in the HTTP response; values are discarded by
the transport and never printed or persisted. HTML is parsed transiently, never saved. Sensitive query
values (`state`, `nonce`, `code`, `client_id`, `tenantId`, `code_challenge`, …)
are redacted in every URL in this document.

## 2. What was reachable

`http://127.0.0.1:9011` and `:9012` both serve the discovery document; both
report the same issuer. Only `:9011` was probed further.

## 3. OIDC runtime metadata — `RUNTIME_READ_ONLY_VERIFIED`

| Key | Runtime value (path only) | Repository expectation | Verdict |
|---|---|---|---|
| `issuer` | `http://127.0.0.1:9011` | public host, Phase 2 | **RUNTIME_DIFF, expected** — no public host exists yet |
| `authorization_endpoint` | `/oauth2/authorize` | published | REPOSITORY_MATCH |
| `token_endpoint` | `/oauth2/token` | published | REPOSITORY_MATCH |
| `end_session_endpoint` | `/oauth2/logout` | published | REPOSITORY_MATCH |
| `jwks_uri` | `/.well-known/jwks.json` | published | REPOSITORY_MATCH |
| `userinfo_endpoint` | `/oauth2/userinfo` | **not published** | **RUNTIME_DIFF — deliberate, see below** |
| `device_authorization_endpoint` | `/oauth2/device_authorize` | not published | REPOSITORY_MATCH (path name differs, see §7) |
| `code_challenge_methods_supported` | `["S256"]` | ADR-034 requires S256 | REPOSITORY_MATCH |

**The `userinfo` difference is correct and should stay.** Nothing in JUVAl
calls it — `grep -rn userinfo src/` returns nothing; the BFF uses only
authorize, token and logout, and `auth.py` reads JWKS. Identity claims come
from the ID token. The allow-list being *narrower* than the discovery document
is the allow-list working.

It is, however, a contract mismatch worth writing down: JUVAl will publish a
discovery document advertising an endpoint that answers 404. That is safe for
JUVAl's own BFF and surprising for any future standards-conformant client.

`id_token_signing_alg_values_supported` advertises nine algorithms including
`HS256`. `interfaces/api/auth.py` pins `RS256` only, which is the correct
defence against algorithm confusion — the provider's breadth does not widen
JUVAl's acceptance.

## 4. Pages observed

> **CORRECTION, 2026-09-10 (second pass).** An earlier revision of this section
> stated that "no JUVAl tenant or application exists". **That was wrong, and it
> was an inference, not a measurement** — it rested on a stale line in
> `CLAUDE.md` plus a generic error page returned for a placeholder zero-UUID
> `client_id`. Both objects exist; see §14. The login form still could not be
> rendered, but for an entirely different reason: the tested redirect URI is rejected; the exact configured list remains unknown. The claim is corrected here rather than deleted, because the
> reasoning error is the useful part.

The hosted login form could not be rendered (§14.4), and no attempt was made
to create or modify any FusionAuth object.

| Request | Status | Type | Bytes | `SET_COOKIE_PRESENT` | Page |
|---|---|---|---|---|---|
| `GET /oauth2/authorize` | 200 | text/html | 6177 | YES | themed **error** page |
| `GET /password/forgot` | 200 | text/html | 8541 | YES | real hosted **form** page |
| `GET /oauth2/logout` | 302 | — | 0 | YES | → `/` |

`/password/forgot` is the important one. It is a genuine hosted form page —
same theme, same layout, a real `<form>` — and therefore a far better
structural proxy for the login form than the error page. It was **rendered,
never submitted**; the tool has no code path that can POST, so no mail was
sent and no reset was initiated.

**Both HTML pages reference an identical set of 20 same-origin assets.** That
is evidence the hosted theme loads one common bundle on every page. It is *not*
proof that the login form loads nothing further — see §8.

## 5. `PUBLIC_ASSET_PATHS`

Same-origin, de-duplicated, sanitised. "Required for initial render" is
`unknown` wherever the answer depends on the login page specifically.

| Path | Element | Same-origin | Observed on generic pages (real login requirement UNKNOWN) |
|---|---|---|---|
| `/css/entrypoints/fusionauth-hosted.css?version=1.69.0` | `link` | yes | **yes** — the page's only layout stylesheet |
| `/css/font-awesome-4.7.0.min.css` | `link` | yes | **yes** — icon font used by the form controls |
| `/js/Util.js?version=1.69.0` | `script` | yes | yes |
| `/js/prime-min-1.7.0.js?version=1.69.0` | `script` | yes | yes |
| `/js/oauth2/LocaleSelect.js?version=1.69.0` | `script` | yes | yes |
| `/images/footer-logo.svg` | `img` | yes | yes |
| `/images/manifest.json` | `link` | yes | no — PWA manifest |
| `/images/favicon-{16x16,32x32,96x96,128}.png` | `link` | yes | no — browser chrome |
| `/images/apple-icon-{57,60,72,76,114,120,144,152,180}…png` | `link` | yes | no — iOS home screen |
| `/password/forgot` | `form` | yes | n/a — the form posts to itself |
| `/oauth2/authorize?…` | `a` | yes | n/a — "back to login" link |
| `https://fusionauth.io` | `a` | **no** | no — vendor footer link |

HTML references were extracted; GET fetched the pages and stylesheets.
This is not a browser network trace. Historical HEAD checks are in §6.

## 6. Finding D-1 — generic CSS references outside the allow-list

This is the finding the HTML alone could not produce. Stylesheets pull
sub-resources through `url(...)`, which no amount of page-source reading
reveals. Following the two same-origin stylesheets one level:

| Sub-resource | Exists on the instance | Current nginx allow-list |
|---|---|---|
| `/fonts/fontawesome-webfont.woff2` | **200**, 77 160 B | **404 — NOT PUBLISHED** |
| `/fonts/fontawesome-webfont.woff` | **200**, 98 024 B | **404 — NOT PUBLISHED** |
| `/fonts/fontawesome-webfont.ttf` | **200**, 165 548 B | **404 — NOT PUBLISHED** |
| `/fonts/fontawesome-webfont.eot` | **200**, 165 742 B | **404 — NOT PUBLISHED** |
| `/fonts/fontawesome-webfont.svg` | **200**, 444 379 B | **404 — NOT PUBLISHED** |
| `/assets/icons/fingerprint-overlay.svg` | **200**, 29 338 B | **404 — NOT PUBLISHED** |

Verified with HEAD against the running instance: all six exist and all six
would be refused by `deploy/fusionauth/nginx-fusionauth-public.conf` as it
stands.

**Consequence (conditional).** Generic pages reference the icon-font files;
missing publication may affect rendered glyphs if the real login uses the
same CSS and glyphs. CSS references alone do not establish browser requests,
visual breakage or functional compatibility. The real JUVAl login has not
been observed.

`/assets/` is the more interesting of the two: it is referenced only from CSS
for a WebAuthn affordance, so it would have been missed by any review that read
the page source, and its necessity depends on whether WebAuthn is ever enabled.

**Observation, not a defect claim:** `fusionauth-hosted.css` also contains a
literal, unexpanded `${request.contextPath}` inside a `url(...)`, producing the
path `/css/entrypoints/${request.contextPath}/assets/icons/fingerprint-overlay.svg`,
which the instance answers **404** itself. That is a FusionAuth packaging
cosmetic issue, not a JUVAl one, and it is recorded rather than repaired.

## 7. Prefix classification (Task 6)

**A. Are all three referenced?** Yes — all of `/css/`, `/js/` and `/images/`
appear, on both observed pages.

**B/C/D. Exact children and versioning:**

| Prefix | Paths seen | Version-bearing | Nested deeper than one level |
|---|---|---|---|
| `/css/` | 2 | **2** — `?version=1.69.0` and `font-awesome-4.7.0` in the filename | yes: `/css/entrypoints/…` |
| `/js/` | 3 | **3** — all `?version=1.69.0`; one also `prime-min-1.7.0` | yes: `/js/oauth2/…` |
| `/images/` | 15 | 0 | no |

**E. Would an exact allow-list be stable across restarts and upgrades?**
Not established across upgrades. A filename containing a library version may
change on upgrade. **A query-only `?version=` change does not break an nginx
exact location**, because location matching excludes query arguments. Keeping
CSS/JS prefixes is a conservative maintenance candidate, not a demonstrated
requirement derived from query strings alone.

**F. Is a narrow prefix safer and maintainable?** For `/css/` and `/js/`, the
prefix is a maintenance candidate: exact paths need review on upgrades. For `/images/`, 15 stable, unversioned paths make
narrowing genuinely available.

| Prefix | Classification | Basis |
|---|---|---|
| `/css/` | **REQUIRED_AS_PREFIX** | one filename version; upgrade risk, generic evidence only |
| `/js/` | **REQUIRED_AS_PREFIX** | one filename version; upgrade risk, generic evidence only |
| `/images/` | **CAN_NARROW** | 15 stable paths, none version-bearing |
| `/fonts/` | **GENERIC_FORM_REQUIRED candidate** (D-1) | 5 files, referenced from CSS, all 404 today |
| `/assets/` | **CONDITIONAL exact icon candidate** (D-1) | 1 file, CSS-referenced; never a broad `/assets/` rule |

These are **generic-page observations and provisional recommendations** for
this instance at version 1.69.0, not verified real-login requirements.
They are not a guarantee about any future version, which is precisely the
argument for prefixes over exact paths.

## 8. Two-factor routes (Task 7) — `REQUIRES_BEHAVIORAL_MFA_TEST`

Both routes exist and are handled; neither is 404. But the probe **cannot
establish necessity**, and this is the decisive negative result:

| Route | Unauthenticated GET | Interpretation |
|---|---|---|
| `/oauth2/two-factor` | **200**, themed error page (6177 B) | route exists; errors without a valid two-factor state |
| `/oauth2/two-factor-methods` | **302** → `/oauth2/authorize?tenantId=<redacted>` | route exists; bounces back to authorize without state |
| `/oauth2/two-factor-enable` | 302 → `/oauth2/authorize?tenantId=<redacted>` | route exists; deliberately **not** published |
| `/oauth2/two-factor-enable-complete` | 200, themed error page | route exists; deliberately **not** published |

**Why this is not evidence of necessity.** `/oauth2/register` and
`/oauth2/passwordless` return the *byte-identical* 6177-byte error page. Those
two are routes the allow-list deliberately refuses. A 200-with-error-page is
FusionAuth's generic answer for "this hosted route exists but has no valid
state", and it is indistinguishable between a route the flow needs and one it
never touches.

Establishing that the login flow actually traverses `/oauth2/two-factor`
requires a real login against a tenant with `loginPolicy = Required` and a user
holding an enrolled factor — i.e. exactly the behavioural MFA test this task
excludes. **Classification stands at `REQUIRES_BEHAVIORAL_MFA_TEST`; the two
routes are not promoted, and they continue to block Phase 2.**

## 9. Corroboration of two existing decisions

- **ADR-035 Condition 2 (`/password/*` closed) is vindicated by runtime
  evidence.** `GET /password/forgot` returns a live, fully rendered password
  reset form. It is a real password-adjacent surface, exactly as the nginx
  template's comment asserted, and the allow-list correctly refuses it.
- `GET /api/status` returns 200 JSON on loopback, and `/admin` and `/account`
  both answer 301 → slashed form. All three are 404 at the proxy, measured in
  `NGINX_PUBLIC_SURFACE_LAB.md`.

## 10. `FIVE_RULES_UPDATED_STATUS`

| Rule | Before | After this pass |
|---|---|---|
| `/oauth2/two-factor` | NOT_VERIFIED | **REQUIRES_BEHAVIORAL_FLOW** — route exists, necessity unproven |
| `/oauth2/two-factor-methods` | NOT_VERIFIED | **REQUIRES_BEHAVIORAL_FLOW** — route exists, necessity unproven |
| `^~ /css/` | NOT_VERIFIED | **GENERIC ONLY — REQUIRED_AS_PREFIX candidate** |
| `^~ /js/` | NOT_VERIFIED | **GENERIC ONLY — REQUIRED_AS_PREFIX candidate** |
| `^~ /images/` | NOT_VERIFIED | **GENERIC ONLY — CAN_NARROW candidate** |

The three static prefixes have generic-page evidence only; real JUVAl login
compatibility is NOT_VERIFIED. MFA remains unresolved. Phase 2 stays blocked.

## 11. What this does not change

`CONTROL_6_AMAZON = PARTIALLY_SATISFIED`. `RF03_BEHAVIORAL = NOT_EXECUTED`.
`AMAZON_REAPPLICATION = BLOCKED`. `IDENTITY_SECURITY_GATE = BLOCKED`.
`JUVAL_AUTH_MODE` unset. `NGINX_PRODUCTION = NOT_ACTIVE`. `MIGRATIONS =
NOT_APPLIED`.

**None of this is production evidence and none may be cited to Amazon.** It is
a read-only observation of a development instance whose identity objects are
not in service: `JUVAL_AUTH_MODE` is unset, policy and login history were not reverified in this pass. (An earlier revision of this sentence said
"with no tenant, no application and no user" — the first two are false, see
§14; whether any user exists was never measured either way.)

---

## 12. N-1 remediation analysis (Task 8) — **no change applied**

D-1 changes this analysis. Before this pass, "narrow the prefixes" looked like
the obvious least-exposure answer. The evidence says otherwise for two of the
three, and says the allow-list is simultaneously **too wide in shape and too
narrow in coverage**: it publishes three broad prefixes while omitting two referenced by generic CSS, with actual login need unverified.

Recall N-1: `/css`, `/js` and `/images` (unslashed) answer **301**, not 404,
because nginx redirects an unslashed URI to a slash-terminated prefix location
handled by `proxy_pass`. The `Location` is built from the client's `Host`, over
`http`, and leaks the listener port. Any option that keeps a prefix rule
inherits this behaviour; `absolute_redirect off;` is a candidate for relative redirects; an exact
unslashed deny location is another design option. Neither was implemented.

| Option | Security | Compatibility | Maintenance | Upgrade risk | Evidence support |
|---|---|---|---|---|---|
| **A** — `absolute_redirect off` alone | Removes host reflection, scheme downgrade and port leak. Prefix breadth unchanged | Full | None | None | Strong: N-1 is measured, and the directive addresses exactly its three consequences |
| **B** — keep prefixes + `absolute_redirect off` | As A. Breadth is the residual | Full | Low | None | Strong for `/css/` and `/js/` (§7 E); the `/images/` breadth is unjustified by evidence |
| **C** — narrow the prefixes | Marginal gain; still prefixes, still 301 unless combined with A | Full **only if** each narrowed prefix still covers the versioned children | Medium | **Low-to-medium**: narrowing `/css/` to `/css/entrypoints/` drops `font-awesome-4.7.0.min.css` | Weak — the useful narrowing is `/images/`, the least dangerous prefix |
| **D** — exact path allow-list | Narrowest paths; exact locations avoid automatic slash redirects | Actual flow unverified | Recheck on upgrades | Filename changes may break rules; query-only changes do not | Candidate, not ruled out by generic HTML |
| **E** — narrow/exact where evidence supports + `absolute_redirect off` | Relative nginx redirects plus limited publication | Pending real-login evidence | Recheck upgrades | Unverified | Preferred provisional design, not compatibility proof |

**Recommendation: Option E**, with these specifics, *as a decision for the
operator, not an applied change*:

1. Add `absolute_redirect off;` at server scope in a **future** diff; verify
   relative Location headers under hostile Host inputs in the disposable lab.
   This addresses nginx-generated redirects, not upstream redirects.
2. Retain `^~ /css/` and `^~ /js/` provisionally, with current method limits.
   Filename version changes create upgrade risk; query-only versions do not.
3. Consider `/fonts/` only after real-login CSS evidence. Compare exact observed
   font files with a prefix; do not infer every font format is requested.
4. Keep `/assets/` denied. If actual evidence justifies the WebAuthn overlay,
   consider only `location = /assets/icons/fingerprint-overlay.svg`, never a
   broad prefix for this one file. An unresolved CSS template variable is not
   evidence that the corrected URL is requested.
5. Consider exact observed `/images/` resources, including manifest-referenced
   icons, after real-login evidence; generic observations alone cannot close it.

**DIFF PLAN ONLY / PENDING VALIDATION.** This is not a final real-JUVAl plan:
the exact tenant and application exist, but redirect configuration blocks
rendering. No nginx template, hosting or authentication setting was changed.

## 13. N-3 hardening inventory (Task 9) — **decision table only, nothing implemented**

The blocker labels below are proposed engineering release criteria, not newly
approved Amazon requirements. Private means this unauthenticated loopback lab;
public means an eventual internet-facing identity service. No enforcement is
implemented by this document.

| Control | Recommended layer | Compatibility risk | Security benefit | Private blocker | Public blocker (proposed) |
|---|---|---|---|---|---|
| `server_tokens off` | nginx | Low | Reduces version disclosure, does not patch vulnerabilities | No | No; defense in depth |
| HSTS | Actual HTTPS termination edge, topology still undecided | Cached policy can lock out HTTP; avoid premature preload/includeSubDomains | Prevents later HTTP downgrade | No | Yes for HTTPS-only release policy |
| CSP | FusionAuth theme, coordinated with edge | High: inline code, nonce/hash and resource dependencies must be observed | Restricts script/resource injection | No | Yes, compatible policy required before public release |
| `X-Content-Type-Options: nosniff` | Edge, preserve correct provider MIME types | Incorrect CSS/JS MIME types may stop loading | Reduces MIME confusion | No | Yes, after MIME validation |
| `Referrer-Policy: no-referrer` candidate | Identity provider/edge, consistent policy | Check integrations relying on Referer | Prevents authorization URL referrer leakage | No | Yes |
| `Permissions-Policy` | Edge | Overbroad policy can disable WebAuthn | Limits unnecessary browser capabilities | No | No; defense in depth |
| CSP `frame-ancestors` / X-Frame-Options | Provider policy plus consistent edge coverage | Can break intentional embedding; redirect BFF needs none | Clickjacking protection | No | Yes |
| Rate limit `/oauth2/authorize` | Edge volumetric controls; FusionAuth account policy separately | Shared NATs, trusted client IP and GET/POST retries need tuning | Reduces abuse volume; not a substitute for lockout | No | Yes; values/topology PENDING |

Two structural notes:

- The template is a `server {}` block. `server_tokens`, and anything else set
  in the surrounding `http {}` of `/etc/nginx/nginx.conf`, would apply — and
  that file is **not in this repository**. So none of the above is currently
  pinned by anything JUVAl version-controls. Whatever is chosen should live in
  the template itself, so the repository is the source of truth.
- `limit_req` needs care specifically because `/oauth2/authorize` serves both
  the GET that renders the form and the POST that submits credentials
  (measured in `NGINX_PUBLIC_SURFACE_LAB.md`). A rate limit keyed on the path
  alone throttles both.

**Nothing here is implemented, and none of it should be until the login page
can actually be rendered.**

---

# 14. Runtime identity reconciliation (second pass, 2026-09-10)

A contradiction was raised against §4 of the first pass: prior context recorded
a dedicated JUVAl tenant, application and roles, while this document asserted
that neither existed. **The first pass was wrong.** This section establishes
which objects exist, by measurement rather than inference, and explains the
error.

Still read-only: no object was created, modified or deleted; no API key, admin
credential, password or TOTP was used; nothing was restarted.

## 14.1 How absence was wrongly concluded

The first pass sent `client_id=00000000-0000-0000-0000-000000000000` — a
placeholder, never the real application id — and received FusionAuth's generic
themed error page. That page was read as "no application configured". It also
leaned on `CLAUDE.md`'s "sin tenant `JUVAl` todavía", which is stale.

Neither is evidence of absence. FusionAuth returns the *same* 200 error page
for a malformed request, an unknown client and several other faults; §8 of this
document already made exactly that point about the two-factor routes, and the
first pass then failed to apply it one section earlier.

`DISCOVERY_ABSENCE_CAUSE = WRONG_DISCOVERY_INPUT`, compounded by
`RUNTIME_STATE_DIFFERS_FROM_PRIOR_EVIDENCE` in the documentation.

## 14.2 Authoritative method actually used

The intended method — read-only SQL against the FusionAuth database — is
**BLOCKED**, and was not attempted beyond establishing that:

| Route to the database | Result |
|---|---|
| Peer authentication as the working user | `FATAL: role "juval" does not exist` |
| `sudo -u postgres psql` | `sudo: a password is required` |
| Reading the password from `fusionauth.properties` | **Prohibited** — a database credential. Not opened |

No credential file was read and no connection string appears anywhere in this
document. `SQL_EVIDENCE = BLOCKED`.

What replaced it is stronger than it sounds: **discriminating public probes
with control groups**. FusionAuth's OAuth error body distinguishes fault
classes, and that distinction is unauthenticated and read-only.

## 14.3 Findings

**Tenant `5fcaaf07-8832-491a-a6e7-35d348a591b6` exists.** FusionAuth serves a
tenant-scoped discovery document:

| Request | Result |
|---|---|
| `/.well-known/openid-configuration/5fcaaf07-…` | **200**, valid discovery document |
| the same path with 4 independently generated random UUIDs | **500** × 4 |
| `…/00000000-0000-0000-0000-000000000000` | **500** |

A tenant id that resolves behaves differently from one that does not, and the
claimed id is on the resolving side. `TENANT_ID_EXISTS = YES`
(`RUNTIME_READ_ONLY_VERIFIED`).

**Application `84f077a0-b2b0-4655-8168-082b2233d029` exists.** The OAuth error
class is the discriminator:

| `client_id` | `error` | `error_reason` |
|---|---|---|
| random UUID | `invalid_client` | `invalid_client_id` |
| **`84f077a0-…`** | `invalid_request` | **`invalid_redirect_uri`** |

FusionAuth validated the client and then rejected the *probe's own*
`redirect_uri`. It cannot reach redirect-URI validation for a client it does
not know. `APPLICATION_ID_EXISTS = YES` (`RUNTIME_READ_ONLY_VERIFIED`).

**The application is bound to that tenant.** Adding `tenantId` to the same
request:

| `tenantId` | `error_reason` |
|---|---|
| `5fcaaf07-…` (claimed) | `invalid_redirect_uri` — client and tenant both resolved |
| random UUID | `invalid_tenant_id` |

`APPLICATION_TENANT_ID = 5fcaaf07-8832-491a-a6e7-35d348a591b6`
(`RUNTIME_READ_ONLY_VERIFIED`).

**What public evidence cannot establish**, and is therefore left unverified
rather than assumed:

| Item | Status | Why |
|---|---|---|
| `TENANT_NAME` | **NOT_VERIFIED** | Not exposed by any public endpoint. The name `JUVAl` is prior context, not a measurement |
| `APPLICATION_NAME` | **NOT_VERIFIED** | As above |
| `ROLE_NAMES` (`viewer`/`operator`/`admin`) | **NOT_VERIFIED** | Roles appear in tokens and in the API, neither of which is reachable read-only without a credential |

## 14.4 The real hosted login page — `BLOCKED_BY_REDIRECT_CONFIGURATION`

Every `redirect_uri` tried is rejected with `invalid_redirect_uri`, and the
repository explains why. `tools/configure_fusionauth.py::ensure_application`
sets `oauthConfiguration` with **no `authorizedRedirectURLs` at all**, and says
so deliberately:

> "no production redirect URI is invented here; the operator adds one when that
> flow is built"

The application exists and the tested redirect URIs are rejected. The exact
authorized-redirect list has **not** been read; it must not be assumed empty.
Making it render would require adding a redirect URI — a configuration change,
and was outside the earlier read-only pass. The recovery task authorizes
only the temporary loopback URI via existing Admin UI, subject to baseline and cleanup.

One honest limit: FusionAuth returns `invalid_redirect_uri` both when no URIs
are configured and when the supplied one is merely absent from a non-empty
list. Four candidates were tried (a bounded confirmation, not enumeration) and
all four were rejected identically. The repository explains why an empty list is plausible, but does not establish
current runtime configuration. Record the exact list in Admin UI before mutation.

`REAL_JUVAL_HOSTED_LOGIN = BLOCKED_BY_REDIRECT_CONFIGURATION`.

**Consequence for Tasks 7-9:** no real JUVAl login page could be observed, so
no asset can be classified `OBSERVED_REAL_JUVAL_LOGIN`. Everything in §5 and §6
remains `OBSERVED_GENERIC_FUSIONAUTH_FORM` — the hosted theme's common bundle,
seen on the error page and the forgot-password form. That distinction is
preserved rather than collapsed.

## 14.5 Asset classification at current evidence

| Prefix | Current-evidence classification | Basis | Changed by this pass? |
|---|---|---|---|
| `/css/` | **REQUIRED_AS_PREFIX** | 2/2 version-bearing (`?version=1.69.0`, `font-awesome-4.7.0`) | No |
| `/js/` | **REQUIRED_AS_PREFIX** | 3/3 version-bearing | No |
| `/images/` | **CAN_NARROW** | 15 stable, unversioned paths | No |
| `/fonts/` | **GENERIC_FORM_ONLY — CSS references observed** | 5 files, CSS-referenced, all 200 on the instance, all 404 at the proxy | Downgraded from "observed required for login": the login page was never seen |
| `/assets/icons/fingerprint-overlay.svg` | **WEBAUTHN_CONDITIONAL** | One file, referenced from CSS for a WebAuthn affordance. **Do not generalise `/assets/` from one file** | Yes — explicitly not promoted to a prefix |

D-1 stands: `/fonts/` is referenced by the shared theme stylesheet loaded on
every hosted page observed, so the same theme may need font resources when matching glyphs are rendered.
That is an inference, not an observed real-login request.

## 14.6 Status ledger

```
TENANT_RUNTIME_EXISTENCE      = EXISTS (RUNTIME_READ_ONLY_VERIFIED)
APPLICATION_RUNTIME_EXISTENCE = EXISTS (RUNTIME_READ_ONLY_VERIFIED)
APPLICATION_TENANT_BINDING    = CONFIRMED (RUNTIME_READ_ONLY_VERIFIED)
TENANT_NAME / APP_NAME        = NOT_VERIFIED (not publicly exposed)
ROLE_RUNTIME_EXISTENCE        = NOT_VERIFIED (needs API or DB)
SQL_EVIDENCE                  = BLOCKED (no role, no passwordless sudo,
                                credential file prohibited)
REAL_JUVAL_HOSTED_LOGIN       = BLOCKED_BY_REDIRECT_CONFIGURATION
TWO_FACTOR_ROUTES             = REQUIRES_BEHAVIORAL_MFA_TEST (unchanged)
```

**`CLAUDE.md` corrected during recovery:** both exact IDs exist; names and roles
were not reverified; do not recreate either object. The remaining blocker is
redirect configuration, not tenant/application absence.

Unchanged and unchangeable here: `CONTROL_6_AMAZON = PARTIALLY_SATISFIED`,
`RF03_BEHAVIORAL = NOT_EXECUTED`, `AMAZON_REAPPLICATION = BLOCKED`,
`JUVAL_AUTH_MODE` unset. **None of this is production evidence and none may be
cited to Amazon.**


## 15. Recovery checkpoint — 2026-09-10

Recovered from disk at `3a599ba57f36731e2e04c3382f29cf8e54840d7d`;
local `origin/master` is `32c3aef63352e1de1eac908dc0409681d3b29886`.
Both reported commits exist: `acf5cf1` (nginx lab) and `3a599ba` (cipher tests).
The four interrupted files were preserved and reviewed; no prior commit was
amended, no production cipher or nginx file changed. No push or fetch.
All specifically requested files exist. Historical `AGENTS.md`/phase-plan
claims about missing Git, frontend, tenant and old test counts are not the
current runtime baseline; broader reconciliation remains future work.

Fresh loopback GET probes reconfirm tenant discovery 200 versus four controls
500, real client `invalid_redirect_uri` versus random client
`invalid_client_id`. Names and roles remain NOT_REVERIFIED. No database access.
BFF source (`src/juval/interfaces/api/bff.py`) exchanges/refreshes at the token
endpoint and verifies ID tokens; no userinfo call exists in `src/`.

Review fixes: literal loopback HTTP(S), no environment proxy, no URL credentials,
five-second socket timeout, 4 MiB response cap and closed responses; cookie
values discarded, query values redacted by default (numeric version metadata
only retained), arbitrary HTML titles omitted, CSS cross-origin resources
excluded, generic evidence labelled, logout GET removed, unknown OAuth errors
and failed tenant discovery no longer prove existence/absence. No DNS is used.
Socket timeout is not a total wall-clock budget against a continuously trickling
response; this tool is restricted to the local trusted service. CSS parsing is
one level and not a browser: runtime JS, imports and conditional resources may
be missing. No real-login completeness claim is made.

Fresh generic HTML: authorize error 6177 bytes; forgot form 8541 bytes; two CSS,
three JS, fifteen image/manifest references, five font references, one exact
fingerprint icon plus the unresolved CSS template path. These remain
`OBSERVED_GENERIC_FORM`; no resource is `OBSERVED_REAL_JUVAL_LOGIN` or `BOTH`.
The fingerprint icon's necessity is `CONDITIONAL`.

### Temporary redirect experiment — not started

`TEMP_REDIRECT_BASELINE = NOT_ESTABLISHED` (exact Admin UI list not read).
`TEMP_REDIRECT_MUTATION = NOT_EXECUTED`.
`REAL_JUVAL_HOSTED_LOGIN_STATUS = BLOCKED_BY_REDIRECT_CONFIGURATION`.
Execution is additionally blocked because this agent session exposes no browser
or computer-control capability to inspect an existing authenticated Admin UI.
An authenticated session may exist on the operator desktop; that is unknown,
not evidence that login is required. No browser profile/cookie store was read.

The user already approved exactly `http://127.0.0.1:18080/oauth/callback`.
No renewed approval is needed. Operator handoff through the existing Admin UI:

1. Open Applications and select by exact ID
   `84f077a0-b2b0-4655-8168-082b2233d029`; verify tenant ID
   `5fcaaf07-8832-491a-a6e7-35d348a591b6`. Do not recreate objects.
2. In OAuth configuration, record the exact Authorized redirect URLs list
   (including order). Do not expose client secrets or take secret screenshots.
   If admin login is required, stop agent actions; operator authenticates
   privately. No password/TOTP is requested by the agent.
3. Only with baseline recorded and observation/cleanup ready, add the one URI
   above, preserving every existing entry. Save and read back its presence.
   If already present at baseline, stop: it must not be removed as a new entry.
4. Fetch only the real client's unauthenticated authorization-code page with
   PKCE S256, without login or callback completion. Keep verifier/state/nonce
   transient, report paths only, no HTML/cookies/screenshots persisted. No
   callback listener is needed. Real-login recognition must exclude OAuth
   error pages; a 200 alone is insufficient.
5. After success or failure, remove only the URI added in step 3, save, reopen
   and compare the exact original list. Require absence and exact restoration.
   If either cannot be proven, stop further work.

`TEMP_REDIRECT_CLEANUP = NOT_APPLICABLE (no mutation)`.
`ORIGINAL_CONFIG_RESTORED = NOT_APPLICABLE / NOT_INDEPENDENTLY_VERIFIED`.
Do not interpret these as proof of the baseline or successful cleanup.
N-1 and D-1 remain remediation pending; §12 is a provisional diff plan, not a
final plan based on real JUVAl evidence. N-3 remains design only (§13).

### Review and integrity boundary

Ponytail is declared in repository instructions but no callable plugin or local
Ponytail skill was found in this session. Manual simplicity/security self-review
performed: stdlib only, existing discovery parser retained, no architecture or
runtime activation changes. This is not a claimed Ponytail execution.

Runtime baseline: FusionAuth MainPID `369334`, NRestarts `0`, active since
`Mon 2026-09-07 18:46:43 UTC`; PostgreSQL active; nginx process count 0;
`JUVAL_AUTH_MODE`, session DB URL and Supabase DB URL unset in the agent process.
No remote deployment environment is claimed reverified. Existing TCP listeners:
loopback 6080/5900/5432 and DNS 53; wildcard 22/631/9011/9012 (IPv4/IPv6 as
reported by `ss`). Existing wildcard listeners were not introduced by this task;
firewall reachability was not tested or changed.

No users/API keys created, no login submitted or automated, no credentials
requested/read, no migration, no frontend changes, no nginx behavior change,
no service restart and no temporary callback listener. Runtime global user/key
counts were not queried; statements describe this task's actions.

Sources consulted for design semantics: [nginx core directives](https://nginx.org/en/docs/http/ngx_http_core_module.html#absolute_redirect)
(relative nginx redirects), [nginx rate limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
(request limiting configuration), [CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy)
and [HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security).
These support directive/header semantics, not real JUVAl compatibility or
approval of a new deployment policy.


### Validation at the recovered checkpoint

- Final backend: `.venv/bin/python -m pytest -q` — **734 passed, 96 skipped,
  0 failed**, 14.62 s; one existing Starlette/httpx deprecation warning.
- Relevant discovery/nginx/cipher tests — **138 passed, 68 skipped**; nginx
  behavioral tests skipped because no nginx binary is available. The historical
  59-probe/4-measurement lab result is preserved, not claimed rerun here.
- Production cipher unchanged. Confirmed actual test token 27 bytes, sealed
  bytes 43, exhaustive bit flips 344; the prior commit changes tests only.
- Compliance checker: **9 PASS / 1 WARN / 0 FAIL**; warning is the incident
  response plan role placeholder. Installed dependency audit reports no known
  vulnerabilities. Existing secret scanner: **422 files, no matches**.
- `git diff --check`: PASS. No dependency added.
- Runtime reread matches the baseline PID/restarts/activation timestamp,
  PostgreSQL active, identical TCP listener set, nginx count 0.

Overall **PARTIALLY IMPLEMENTED**: discovery recovery validated; the controlled
redirect experiment is **BLOCKED**, real-login surface **NOT_VERIFIED**.

## 16. Accelerator boundary update — 2026-09-10

ADR-037 resolves nginx-generated N-1 in the inactive template with relative
redirects and suppresses nginx version disclosure (N-3 partial), measured by
90 disposable nginx tests. This is independent proxy evidence; it does not
change the generic asset inventory, establish real JUVAl login requirements,
resolve D-1, or activate public auth. Baseline/temporary redirect mutation still
NOT_EXECUTED; no cleanup claim may be inferred from the new proxy tests.

### Prepared exact-client probe (accelerator)

`--real-login --temporary-redirect-confirmed` prepares the already-approved
code+PKCE S256 request only after operator baseline/add/readback. One GET,
exact JUVAl client/temporary URI, no client secret, no callback or cookie reuse;
output contains same-origin path references only. A recognized authorize form
is labelled OBSERVED_REAL_JUVAL_LOGIN with HTML-only evidence scope, never
browser completeness. Unknown/error/generic pages fail closed. **103 discovery
tests passed**; the real-client mode has NOT been executed against runtime.
Fresh existence-only probes still return tenant 200 vs four 500 controls and
real-client invalid_redirect_uri vs random-client invalid_client_id.
The cleanup/runbook is `docs/IDENTITY_SECURITY_READINESS.md`.

## Continuación 2026-09-10 — login real observado

El bloqueo de baseline queda superado: lista vacía / ExactMatch leída mediante
Admin autenticado; callback temporal añadido, probado y eliminado con readback
exacto en cada ciclo. Login inicial real renderizado en Chromium; nginx real
loopback devuelve formulario y assets iniciales. D-1 PARTIAL: MFA/WebAuthn/fuentes
y recuperación aún pendientes. No producción ni Control 6 satisfecho. Evidencia:
`docs/research/REAL_JUVAL_LOGIN_20260910.md` y JSON sanitizados asociados.
