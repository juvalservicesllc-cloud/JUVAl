# Identity + Amazon deep research — architecture validation pass

**Date: 2026-09-09.** Research-only. **No production mutation, no login, no
user creation, no API-key use, no configuration change, no frontend change,
no commit, no push.** Every external source was accessed 2026-09-09 unless
stated otherwise.

**Baseline verified independently at the start of this pass:**
`HEAD = 26b4f9d4cf9e765b7f547863714ccc855a521c95`, working tree carrying only
`M docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` (the §52 append). This
matches the state the task declared.

**Evidence classes used throughout** (the quality bar this document is held
to):

| Class | Meaning |
|---|---|
| `VERIFIED_OFFICIAL_DOC` | Vendor's own current documentation, quoted |
| `VERIFIED_SOURCE_CODE` | Read from JUVAl's repository this pass |
| `VERIFIED_LOCAL` | Measured on JUVAl infrastructure in a prior session and recorded in this repo |
| `VERIFIED_EXTERNAL_REPRO` | Reproduced outside JUVAl by a third party with published steps |
| `HISTORICAL_ISSUE` | Vendor issue tracker entry, version-bound, not necessarily current |
| `INFERENCE` | Reasoning over the above; explicitly not measured |
| `NOT_PROVEN` | Hypothesis compatible with evidence, not established by it |
| `NOT_FOUND` | Searched for, not located |

---

## 1. Executive conclusion

Five findings, in order of how much they change the plan.

**1. The declared runtime architecture does not exist in the frontend, and the
published identity surface cannot serve it.** `browser -> FusionAuth OIDC ->
authorization code -> PKCE -> JWT -> JWKS -> FastAPI -> RBAC` is the *target*.
Measured: `frontend/src` contains **zero** OIDC, PKCE, token or
`Authorization`-header code (`VERIFIED_SOURCE_CODE` — a grep for
`oidc|pkce|fusionauth|Bearer|access_token|code_verifier` across `frontend/`,
`frontend-next/` and `demo/` returns nothing), and `frontend/src/api.ts` /
`api/client.ts` send no credential at all. Independently,
`deploy/fusionauth/nginx-fusionauth-public.conf` is an allow-list of exactly
two paths — `/.well-known/openid-configuration` and `/.well-known/jwks.json` —
with `location / { return 404; }`. A browser authorization-code flow needs
`/oauth2/authorize`, `/oauth2/token`, the hosted login pages and their static
assets. **As designed today, Phase 2 would publish an issuer against which no
human can log in.** This is not a defect in either artifact — each is correct
for what it was built for — but the two have never been reconciled against the
runtime story. Turning on `JUVAL_AUTH_MODE=oidc` today would return `401` on
every request the existing frontend makes.

**2. Control 6 cannot be closed inside FusionAuth, at any price tier, and
Amazon's requirement is not escapable by avoiding PII.** FusionAuth's tenant
password policy offers exactly one name-related rule — *"Reject passwords
containing user login Id"* (`VERIFIED_OFFICIAL_DOC`) — which is the login
identifier, never `firstName`/`lastName`. No password-validation lambda type
exists; the Login Validation lambda does not receive a password
(`VERIFIED_OFFICIAL_DOC`). And Amazon's Key Security Control Guidance ties the
password rules — including *"must not include any part of the user's name"* —
to **DPP §1.4, the general security requirements**, not to the PII-specific
§2. So a private, non-PII, non-restricted-role integration is still in scope.
The remaining question was never "can FusionAuth do it" (it cannot); it is
"which JUVAl-owned path can, with full coverage". Section 5 answers that.

**3. External evidence materially strengthens H8-D — but as vendor-documented
behavior, not as a defect.** FusionAuth documents, in its own API
authentication reference: *"When you create a new key, it will take time for
the API key to be usable. Usually this less than one second. In rare cases
where node communication fails, it may take up to 60 seconds."*
(`VERIFIED_OFFICIAL_DOC`). §52.2 derived the same asynchrony from bytecode and
classified it `STRUCTURALLY_POSSIBLE_NOT_PROVEN`. The vendor documents it as
expected behavior. This does **not** promote it to root cause for any specific
historical `401`, and it explicitly cannot explain IV3 (§52.4's reasoning is
unaffected). It does change the expected value of further debugging: the one
mechanism that survives is a documented, non-defect timing property, and the
residual questions are runtime-memory questions this project refuses to ask.

**4. The `401` in FusionAuth is not a discriminator, by vendor design.**
Official docs: *"All secured APIs will return an `401 Unauthorized` response
if improper credentials are provided"* (`VERIFIED_OFFICIAL_DOC`), and the open
vendor issue [#46](https://github.com/FusionAuth/fusionauth-issues/issues/46)
("Better usage of 401 vs 403", still open, labelled architecture/enhancement)
records that *"most errors returned by the API are under the umbrella of
Http401 Unauthorized"*. §43's title — "authentication and authorization are
still indistinguishable" — was correct, and it is a **vendor property, not a
JUVAl measurement gap**. No amount of black-box probing separates them.

**5. Amazon classification is very likely correct, and the role surface can be
kept entirely outside the restricted/PII set.** Private Seller application,
self-authorized, Primary User of the seller account — that matches JUVAl's
stated use case (`VERIFIED_OFFICIAL_DOC`). Amazon marks exactly four roles
restricted (Direct-to-Consumer Shipping, Professional Services, Tax Invoicing,
Tax Remittance); **Product Listing is not restricted and carries no PII**.
JUVAl's functionality (catalog identity, dimensions, rank, pricing inputs)
lives entirely in the non-restricted set. That does not lift RF-01…RF-05 — those
are the five general controls Amazon requires of every developer — but it does
mean the PII-only escalations (30-day vulnerability scans, annual pen tests,
30-day deletion) are avoidable by design, and that should be an explicit,
documented architectural commitment rather than an accident.

**Nothing in this pass changes any compliance gate.** `API_AUTH = FAIL`,
`ROOT_CAUSE = NOT_PROVEN`, `CONTROL_6 = B — PARTIALLY_SATISFIED`,
`RF-03/RF-04 = NOT_VERIFIED`, `REAPPLICATION GATE = BLOCKED` all stand.

---

## 2. Current architecture, reconstructed from code

Read this pass, not from documentation.

### 2.1 What exists

| Component | File | State |
|---|---|---|
| OIDC/JWT validation | `src/juval/interfaces/api/auth.py::TokenVerifier.verify` | Implemented |
| JWKS retrieval + caching | same, `build_verifier` -> `jwt.PyJWKClient(jwks_uri)` | Implemented (library defaults) |
| Discovery | **not used** — JWKS URI is derived, not discovered | See 6.2 |
| Issuer / audience / expiry | `jwt.decode(..., audience=, issuer=, options={"require": [...]})` | Implemented |
| Algorithm pinning | `_ALLOWED_ALGORITHMS = ["RS256"]` | Implemented |
| Role extraction | `_roles_from_claims` (list or space-separated string) | Implemented |
| RBAC | `ROLE_PERMISSIONS` (`viewer`/`operator`/`admin`) + `require(permission)` | Implemented |
| 401 vs 403 | 401 = no/invalid token; 403 = authenticated but lacking permission | Implemented, correct |
| Enforcement points | 10+ `Depends(require(...))` across `main.py` | Implemented |
| Failure behavior | fail-closed; missing config in `oidc` mode is a startup `RuntimeError` | Implemented |
| Tests | `tests/integration/test_api_auth.py`, 29 test functions | Present |
| **Browser OIDC client** | — | **DOES NOT EXIST** |
| **Login/logout UI, token storage, refresh** | — | **DOES NOT EXIST** |
| **Public authorize/token endpoints** | `nginx-fusionauth-public.conf` returns 404 | **NOT PUBLISHED** |

`VERIFIED_SOURCE_CODE` for every row.

### 2.2 The three-plane picture

```
  ADMIN PLANE (humans + one-off tooling)         RUNTIME PLANE (product)
  ------------------------------------          ------------------------
  FusionAuth admin console  (operator)          browser (Vercel SPA)
  tools/configure_fusionauth.py   \                    |  <-- NOT IMPLEMENTED
  tools/verify_rbac.py             > API KEY           v
  tools/verify_identity_behavior.py/              FusionAuth OIDC
                                                  /oauth2/authorize   <-- 404 in
                                                  /oauth2/token           the planned
        ^                                              |                  public conf
        |                                              v
   ALL FAILURES IN §39-§52 LIVE HERE            JWT (RS256)
   API_AUTH = FAIL                                     |
                                                       v
                                                FastAPI on Railway
                                                auth.py: JWKS (anonymous)
                                                          |
                                                          v
                                                       RBAC
```

The separation ADR-032 asserts is real and verified: `build_verifier` consumes
only the anonymous JWKS document; no code path in `src/` reads
`JUVAL_IDP_API_KEY`. `VERIFIED_SOURCE_CODE`. **The API-key anomaly is confined
to the admin plane.** That conclusion survives this research pass unchanged.

### 2.3 The gap that matters

`JUVAL_AUTH_MODE` is unset in production, so `current_principal` returns
`_ANONYMOUS`, which holds `ALL_PERMISSIONS`. The deployed Railway backend is
therefore **fully open**. This was a deliberate, recorded decision
(`docs/compliance/SECRETS.md` S-4: *"`JUVAL_AUTH_MODE=oidc` was deliberately
NOT set"*), correct at the time because enabling it without an IdP tenant
would break every endpoint. It is now the *second* reason it cannot be turned
on: even with a tenant, the frontend sends no token. Both blockers must clear
together.

---

## 3. FusionAuth 1.69 supported authentication state machine

### 3.1 Answers to the twelve questions asked

| # | Question | Answer | Class |
|---|---|---|---|
| 1 | User creation | `POST /api/user` (API key) or admin console. Password validated against tenant `passwordValidationRules` at creation | `VERIFIED_OFFICIAL_DOC` |
| 2 | Application registration | `POST /api/user/registration`; `require_registration=false` on the JUVAl app means an unregistered user may still authenticate at the tenant | `VERIFIED_OFFICIAL_DOC` + `VERIFIED_LOCAL` (config baseline) |
| 3 | OAuth authorization request | `/oauth2/authorize` with `response_type=code`, PKCE `S256` (app policy = Required), `state`, `nonce` | `VERIFIED_OFFICIAL_DOC` |
| 4 | Password authentication | Hosted login page, or `POST /api/login` (API-key protected, tenant-scoped key accepted) | `VERIFIED_OFFICIAL_DOC` |
| 5 | `passwordChangeRequired` | Login API answers **`203`** with `changePasswordId` + `changePasswordReason` (`Administrative`, `Breached`, `Expired`, `Validation`) | `VERIFIED_OFFICIAL_DOC` + `HISTORICAL_ISSUE` #741 |
| 6 | `loginPolicy = Required` | Forces a two-factor challenge on every login | `VERIFIED_OFFICIAL_DOC` |
| 7 | **User with no MFA method** | **Cannot log in.** Vendor doc: the Required policy *"requires a two-factor challenge; if a user does not have configured two-factor methods, they will not be able to log in."* | `VERIFIED_OFFICIAL_DOC` |
| 8 | MFA enrollment | `POST /api/user/two-factor/{userId}` (API key), admin console, or the self-service account portal — **which is a paid Starter feature, not Community** | `VERIFIED_OFFICIAL_DOC` |
| 9 | MFA challenge | Login API returns **`242`** with `twoFactorId` + available methods; completed at `POST /api/two-factor/login`, which takes **no API key** (the one-time `twoFactorId` is the credential) | `VERIFIED_OFFICIAL_DOC` + `VERIFIED_LOCAL` (§49.1 measurement) |
| 10 | Forced password change | Hosted `/password/change`, or `POST /api/user/change-password` with the `changePasswordId`. **With MFA enabled, a trust token from a completed two-factor workflow is required** | `VERIFIED_OFFICIAL_DOC` (forum, vendor staff) + `HISTORICAL_ISSUE` #1591 (2FA moved before change-password in 1.33.0) |
| 11 | Lockout | `UserAction`, time-based, `preventLogin`; Login API answers `423` for a locked account | `VERIFIED_OFFICIAL_DOC` + `HISTORICAL_ISSUE` #2524 |
| 12 | Callback / token issuance | `/oauth2/token` exchanges `code` + `code_verifier`; RS256 JWT signed with the tenant/app key published at `/.well-known/jwks.json` | `VERIFIED_OFFICIAL_DOC` |

### 3.2 The three questions that were asked pointedly

**Order of `passwordChangeRequired` vs MFA.** In the **Login API**, the two are
mutually exclusive terminal statuses of one call: `242` (two-factor required)
is returned when MFA gates the login; `203` (change password) is returned once
credentials are accepted and no MFA gate stands in the way. In the **hosted
OAuth flow**, issue [#1591](https://github.com/FusionAuth/fusionauth-issues/issues/1591)
("Move 2FA before Change Password workflow when not already in a login flow")
was **implemented in 1.33.0**, and vendor staff state that changing a password
while 2FA is enabled *"requires a trust token, which can be obtained by
completing a two-factor workflow"*. So the supported order is **MFA first,
password change second**. `VERIFIED_OFFICIAL_DOC` + `HISTORICAL_ISSUE`.
The exact 1.69.0 hosted-page sequence is **NOT_PROVEN** here and is a lab
question (§14).

**Does `loginPolicy=Required` force enrollment?** **No.** It blocks. Vendor
docs and staff are consistent: *"With the FusionAuth hosted login pages, it
isn't currently possible to automatically force users to enroll in MFA during
the login flow"*, and the workaround offered is to build your own MFA page
against the APIs. Open feature requests
[#2305](https://github.com/FusionAuth/fusionauth-issues/issues/2305),
[#2285](https://github.com/FusionAuth/fusionauth-issues/issues/2285) confirm
the capability is still requested. `VERIFIED_OFFICIAL_DOC`.

**Is there a supported self-service password-change flow?** Two, with an
important edition caveat. (a) The hosted **forgot-password** flow, which
requires working SMTP on the instance — Community. (b) The **self-service
account portal** (`/account/`), where a user changes their own password and
manages TOTP — **a paid Starter feature, not Community**
(`VERIFIED_OFFICIAL_DOC`, pricing page). JUVAl runs **Community**. This is a
finding with direct consequences, developed in §5.

**Does password validation behave identically across the four paths?**
**Not established, and it must not be assumed.** The tenant
`passwordValidationRules` are documented as applying *"when a new user is
created or a user requests a password change"*, which covers admin-API set and
change-password. `validateOnLogin` covers login. **No official statement
asserts identical behavior across admin-console set, admin-API set,
self-service change and forced change**, and issue #741 is precisely a case
where a `Validation`-reason forced change could not be satisfied through the
normal endpoint. Classification: `NOT_PROVEN`. This is lab question L-2.

### 3.3 State machine (JUVAl's configured tenant: MFA Required, lockout 10/30min, history 10, minLength 12)

```
                         ( no user exists )
                                 |
        operator: admin console / POST /api/user  [password validated
                                 |                 against tenant rules]
                                 v
                        +------------------+
                        |  user, no MFA    |
                        +------------------+
                                 |
        registration (POST /api/user/registration) -- optional here:
        require_registration = false
                                 |
                                 v
            /oauth2/authorize?response_type=code&code_challenge=S256...
                                 |
                                 v
                   +---------------------------+
                   |  hosted login: user+pass  |
                   +---------------------------+
                       |            |            |
        invalid creds  |            | locked     | valid
        (Login API 404)|            | (423)      |
                       v            v            v
                   [ retry ]   [ UserAction  ]  +--------------------------+
                   after 10 -> [ 30 min lock ]  | loginPolicy = Required   |
                                                +--------------------------+
                                                   |                    |
                                 has TOTP method   |                    | NO method
                                                   v                    v
                                        +---------------------+   ####################
                                        | 2FA challenge (242) |   #  DEAD END        #
                                        | /api/two-factor/    |   #  cannot log in;  #
                                        |   login  (no key)   |   #  hosted pages do #
                                        +---------------------+   #  not enroll      #
                                                   |              ####################
                                     wrong code -> 404
                                                   |
                                                   v
                                     +----------------------------+
                                     | passwordChangeRequired ?   |
                                     +----------------------------+
                                        | yes (203)        | no
                                        v                  |
                            /password/change               |
                            (needs trust token             |
                             from the 2FA step)            |
                                        |                  |
                                        +---------+--------+
                                                  v
                                       authorization code issued
                                                  |
                                    /oauth2/token + code_verifier
                                                  |
                                                  v
                                   RS256 JWT (iss, aud=clientId, exp,
                                   roles) --> published at
                                   /.well-known/jwks.json
                                                  |
                                                  v
                                   FastAPI auth.py verify -> Principal -> RBAC
```

**The `DEAD END` box is the operationally decisive fact of this section.** The
JUVAl tenant has `loginPolicy = Required` and **zero users**. Every user
created from here forward is born into that box and must have TOTP enrolled
out-of-band — admin console or `POST /api/user/two-factor/{userId}` — before
they can ever authenticate. On Community edition there is no self-service
portal to do it in. Any onboarding design that assumes "create user, they log
in, they enroll" is wrong for this configuration.

---

## 4. API-key anomaly: external research

**No API-key experiment was run this pass.** Research only.

### 4.1 What the vendor documents (not an issue — expected behavior)

From FusionAuth's *Authenticate with our APIs* reference, verbatim:

> "When you create a new key, it will take time for the API key to be usable.
> Usually this less than one second. In rare cases where node communication
> fails, it may take up to 60 seconds."

and

> "All secured APIs will return an `401 Unauthorized` response if improper
> credentials are provided."

and, on tenant-scoped keys:

> "the tenant Id provided in the header must be the same as the Id of the
> tenant the key is associated with."

`VERIFIED_OFFICIAL_DOC` — https://fusionauth.io/docs/apis/authentication,
accessed 2026-09-09.

The first quote is the vendor's own statement of §52.2's mechanism. §52
derived it from bytecode and called it `STRUCTURALLY_POSSIBLE_NOT_PROVEN`; the
vendor calls it documented behavior. **The correct update is to the mechanism's
class, not to the root cause**: H8-D is now
`VENDOR_DOCUMENTED_MECHANISM / NOT_PROVEN_AS_CAUSE`.

The second quote is decisive for method: `401` covers invalid credential **and**
insufficient permission. FusionAuth does not distinguish them on the wire.

### 4.2 Candidate known issues, classified

| # | Source | Class | Applies to JUVAl? |
|---|---|---|---|
| B-1 | Vendor doc: new key not immediately usable, up to 60 s | `VERIFIED_OFFICIAL_DOC` | **POSSIBLY_RELATED** — structurally identical to the `JUVAL Capture Diagnostic Final` observation (create, probe immediately, `401`). Cannot explain IV3, which survived a restart (§52.4). Cannot be confirmed retrospectively: no probe timestamps relative to creation are recorded with sub-minute resolution for the failing runs |
| B-2 | [#1675](https://github.com/FusionAuth/fusionauth-issues/issues/1675) — `"permissions": {}` produces a permanently `401` key until re-saved in the UI; **open**; observed 1.33–1.36 | `HISTORICAL_ISSUE` | **NOT_MATCHING** — JUVAl's keys were created in the admin UI with explicit grants selected, which is exactly the path that issue says *fixes* the condition. Version distance is also large (1.36 vs 1.69) |
| B-3 | [terraform-provider #126](https://github.com/FusionAuth/terraform-provider-fusionauth/issues/126) — same empty-permissions mechanism via Terraform; closed | `HISTORICAL_ISSUE` | **NOT_MATCHING** — JUVAl uses no Terraform provider |
| B-4 | [#1787](https://github.com/FusionAuth/fusionauth-issues/issues/1787) — `POST /api/jwt/vend` returns `401` for a key without Key Manager; **closed, labelled unreproducible**; 1.36.5 | `HISTORICAL_ISSUE` | **POSSIBLY_RELATED** — this is a near-exact description of §39 ("`jwt/vend` ACL approved; endpoint still rejects the key"). It was never reproduced by the vendor and never fixed. §40 later succeeded, so JUVAl's own history is inconsistent with a deterministic version-level defect |
| B-5 | [#46](https://github.com/FusionAuth/fusionauth-issues/issues/46) — 401 used where 403 is meant; **open** | `HISTORICAL_ISSUE` | **MATCHED_KNOWN_ISSUE**, as an interpretive fact. It does not cause the anomaly; it explains why §39–§51 could not separate authn from authz by status code. That was never a JUVAl methodology failure |
| B-6 | 1.65.0 breaking change — *"removed access via tenant-scoped API keys to endpoints that impact a FusionAuth installation beyond the scope of a single tenant"*; 1.66.0 extended it to webhook endpoints, which *"respond with a `401` error code whenever a user provides the `X-FusionAuth-TenantId` header"* | `VERIFIED_OFFICIAL_DOC` (release notes) | **NOT_MATCHING for the failing endpoints** — checked against FusionAuth's *API Endpoints Guarded by API Keys* reference: `POST /api/user`, `POST /api/user/registration`, `POST /api/login`, `GET /api/user/action`, `POST /api/user/two-factor/{userId}`, `POST /api/jwt/vend`, `GET /api/application`, `/api/tenant`, `POST /api/application/role` are all **"API Key Authentication — a tenant-scoped or global API key may be used"**. **Corroborating side-finding:** `GET /api/status` **is** Global-API-Key-only, which independently vindicates §38.1's decision to stop sending a tenant-scoped key to it |
| B-7 | [#373](https://github.com/FusionAuth/fusionauth-issues/issues/373) / forum "Failed to request a cache reload" — vendor staff attribute it to inter-node communication failure (TLS/cert), with the master node unable to notify peers | `HISTORICAL_ISSUE` | **POSSIBLY_RELATED, previously unconsidered** — see hypothesis H-N1 in §11. JUVAl has **two observed listeners (`:9011`, `:9012`)** on a nominally single-node install. If the node's self-notification target is misconfigured, `DistributedCacheNotifier` retries and logs, and the `AuthenticationKey` cache stays stale indefinitely — which is exactly the shape of a key that never becomes usable and only recovers on restart |

### 4.3 Verdict for Track B

```
MATCHED_KNOWN_ISSUE  = B-5 only, and only as an explanation of why the
                       investigation could not discriminate -- not as a cause
POSSIBLY_RELATED     = B-1, B-4, B-7
NOT_MATCHING         = B-2, B-3, B-6
NO_EVIDENCE          = a FusionAuth defect in 1.69.0 API-key authentication
```

**`ROOT_CAUSE = NOT_PROVEN` is retained.** No external source uniquely
supports any single mechanism, and one confirmed observation (IV3 failing
after a restart that demonstrably repopulated the cache) is incompatible with
the best-supported mechanism.

**Why further debugging has low expected value**, stated as a decision, not a
mood:

1. The one mechanism the vendor documents (B-1) is **not a defect** and is
   **not retrospectively distinguishable** from custody error without probe
   timestamps that were not captured.
2. `401` is documented as non-discriminating (B-5), so no black-box probe can
   separate "key not found" from "endpoint not granted". Every further probe
   yields the same one bit already collected many times.
3. The remaining questions are **runtime-memory** questions (§52.5), and
   inspecting that memory is refused on security grounds because the map holds
   literal key values. That refusal is correct and should not be revisited.
4. **The production runtime consumes no administrative API key**
   (`VERIFIED_SOURCE_CODE`). The anomaly's blast radius is verification
   tooling. Fixing tooling that the target architecture does not need is
   negative-value work.
5. Every remaining RF-03 behavior (password policy, lockout, MFA, Control 6)
   is observable through **user-facing flows that use no API key at all**
   (§16). The dependency that made this a blocker is removable.

**ADR-032 remains architecturally sound**, and this pass strengthens it: the
lifecycle separation is the reason a total failure of the admin credential
plane leaves the product's security posture untouched. One amendment is worth
recording — a *sixth* lifecycle bucket now exists in practice and is not named
in ADR-032: **"no credential at all"**, the class the next verification phase
belongs to.

---

## 5. Control 6 — findings and options

### 5.1 What FusionAuth actually offers

The tenant Password tab, enumerated from vendor documentation
(`VERIFIED_OFFICIAL_DOC`, accessed 2026-09-09):

minimum length · maximum length · uppercase & lowercase · special character ·
number · minimum age · expiration · **"Reject passwords containing user login
Id"** · reject previous passwords (+ count) · re-validate on login · breach
detection (paid) · lockout (failed attempts, duration, unit) · hashing scheme.

**`disallowUserLoginId` — precise answer to the question asked.** The admin-UI
label is *"Reject passwords containing user login Id"*, described as
*"prevent users from including their login Id in their password"*. It covers
**the login identifier only** — email and/or username, whichever the tenant
uses. It does **not** cover `firstName`, `lastName`, `middleName` or
`fullName`. Two honesty notes: (a) the field name `disallowUserLoginId` does
**not** appear in the current *Retrieve a Tenant* API field reference
(`NOT_FOUND` in official API docs, 2026-09-09), even though the setting is
present in the admin UI and in JUVAl's measured tenant baseline
(`VERIFIED_LOCAL`); (b) JUVAl's tenant currently has it set to **`false`**,
so even the partial protection it offers is presently **off**. That is a
configuration observation, not a compliance claim, and closing it is a
one-setting change that costs nothing and moves nothing on its own.

### 5.2 Every extension point evaluated

| Mechanism | Sees plaintext password? | Can block before storage? | Edition | Verdict |
|---|---|---|---|---|
| `passwordValidationRules` | n/a (internal) | yes | Community | **Cannot express the rule** |
| Login Validation lambda | **No** — receives `result`, `user`, `registration`, `context`; no password | at login only | Community | Not applicable |
| MFA Requirement lambda | No | no | Community | Not applicable |
| Self-Service Registration Validation lambda | **Undocumented** — receives `result`, `user`, `registration`, `formContext`, `context` (1.64+). Whether `user.password` carries the submitted value is `NOT_PROVEN` | registration only | **Paid (Advanced Registration Forms)** | Even if it worked: wrong coverage (registration only) **and** JUVAl has `registration_enabled = false` |
| Advanced registration form field regex | No cross-field comparison possible | registration only | Paid | Cannot express the rule |
| Webhooks (`user.create`, `user.update`) | No — fired **after** persistence | no | Community | Detective at best, never preventive |
| Custom password encryptor plugin | Yes (password + salt) but **no user context** | no (it hashes; it does not validate) | Community | Cannot express the rule; abusing it would be custom authentication |
| Client-side password rule validation | Yes, in the browser | **trivially bypassable** | Community | Never a control |
| Self-service account portal | n/a | n/a | **Paid (Starter)** | **Not available to JUVAl** — which shrinks the attack surface of Option C considerably |

`VERIFIED_OFFICIAL_DOC` for every row except the one marked `NOT_PROVEN`.

**Conclusion: FusionAuth Community has no native control, and no supported
extension point in any FusionAuth tier can reject a password based on
`firstName`/`lastName` before storage.** Paid tiers do not change this.

### 5.3 Where the requirement comes from, and whether it can be avoided

Amazon's *Key Security Control Guidance*, quoted:

> "Establish password complexity requirements: minimum 12 characters with
> mixed case letters, numbers, and special characters, and must not include
> any part of the user's name. Configure password history to prevent reuse of
> the last 10 passwords and configure password lifecycle settings with a
> minimum password age of 1 day and a maximum password expiration period of
> 365 days. Deploy Multifactor Authentication (MFA) for all accounts that use
> approved second factors (TOTP, hardware tokens, or biometric
> authentication)."

The guidance maps this to **DPP §1.4 — General Security Requirements**, the
section that applies to all solution providers, not to §2 (PII-specific).
`VERIFIED_OFFICIAL_DOC`, accessed 2026-09-09. **Avoiding PII does not avoid
Control 6.** ADR-021's classification of item 8 as a HARD IdP requirement was
correct and stays correct.

### 5.4 Options matrix

| | A — FusionAuth native | B — FusionAuth supported extension | C — JUVAl pre-validation on the provisioning path | D — separate identity service / gateway | E — documented compensating control |
|---|---|---|---|---|---|
| **Correctness** | Impossible — rule not expressible | Impossible (no hook sees the password at a covered path) | Exact rule, exactly expressible | Exact rule | No technical enforcement |
| **Security** | n/a | n/a | Real preventive control on every path JUVAl owns | Real, but a new authentication-adjacent component | Zero preventive value; organizational only |
| **Bypass risk** | n/a | n/a | **Operator using the FusionAuth admin console directly** (residual, disclosed); hosted forgot-password if SMTP is ever configured | Bypassable by anything reaching FusionAuth directly | Fully bypassable |
| **Covers admin password reset** | n/a | No | Yes for the tool path; **No** for the console path | Only if the console is proxied too | No |
| **Covers self-service change** | n/a | No | **Non-issue on Community** — the self-service account portal is a paid feature JUVAl does not have | Yes | No |
| **Covers registration** | n/a | Registration only, paid | Yes (`registration_enabled = false` today anyway) | Yes | No |
| **Operational cost** | — | Paid tier + build + no coverage | One small validated provisioning tool, reusing existing patterns | New service, new failure mode, new attack surface | Near zero |
| **Amazon auditability** | — | — | **High** — a script, its tests, and a provisioning record are exactly the artifact shape Amazon's security-controls narrative wants | Medium (must explain a bespoke auth-path component) | Low — a policy statement with no evidence of enforcement |
| **Community-edition compatible** | n/a | **No** | **Yes** | Yes | Yes |
| **CLAUDE.md §16 "never custom authentication"** | — | — | **Compatible** — validates an input *before* handing it to the IdP; performs no authentication, stores no password, computes no hash | **Violates the spirit** — a component in the credential path | Compatible |

### 5.5 Recommendation — **Option C**

**Recommend Option C: JUVAl owns password provisioning, and validates
`firstName`/`lastName` exclusion before the value ever reaches FusionAuth.**
Do not implement it in this phase; it needs the ADR in §13 first.

Why C and not the others:

- A and B are not options; they are impossibilities established by vendor
  documentation.
- D introduces a component in the credential path for one validation rule.
  That is disproportionate and rubs directly against CLAUDE.md §16.
- E alone concedes a HARD requirement Amazon states in mandatory language,
  while a real control is available at low cost. E is not the answer, but part
  of E survives inside C: see below.

What makes C credible here specifically, and would not make it credible
elsewhere: **on Community edition JUVAl's password-set surface is unusually
small.** There is no self-service account portal. Self-service registration is
disabled. That leaves three paths — the provisioning tool (covered by C), the
hosted forgot-password flow (inert without SMTP; a lab/config question, not an
assumption), and the FusionAuth admin console used by the operator. Only the
third is a genuine residual, it belongs to a single named person who is also
the security owner, and it is exactly the kind of thing a compensating control
plus a naming standard is honest about. So the recommendation is precisely:

**C as the enforced control, with the admin-console path disclosed as residual
risk under a named organizational standard.** Not "C or E" — C, with E doing
the small job it is actually good for.

Two prerequisites before C can be claimed as a control, both of which are
verification, not implementation:
1. establish whether the hosted `/password/forgot` and `/password/change`
   routes are reachable and completable on this instance (SMTP state);
2. establish whether tenant password rules are applied identically on the
   admin-API set path (§3.2, `NOT_PROVEN`).

Also, independently of all of this and costing nothing: **turn
`disallowUserLoginId` on**. It does not close Control 6 and must never be
reported as doing so, but leaving an available partial control switched off is
not defensible in a security narrative submitted to Amazon.

---

## 6. FastAPI / OIDC / JWT / JWKS — implementation vs references

### 6.1 Comparison table

| Concern | JUVAl pattern | Reference pattern | Difference | Security relevance | Required action |
|---|---|---|---|---|---|
| Grant type | Not implemented client-side | Authorization code + PKCE S256 (RFC 9700 §2.1.1: *"Public clients MUST use PKCE"*) | **Everything** | Critical | **INVESTIGATE → decide** (§12) |
| Algorithm | `algorithms=["RS256"]`, hardcoded | Same in every reference | None | — | KEEP |
| Issuer | `issuer=` passed to `jwt.decode` | Same | None | — | KEEP |
| Audience | `audience=` passed to `jwt.decode`; RFC 9700 §2.3 requires the RS to refuse tokens not meant for it | Same | None | — | KEEP |
| Required claims | `{"require": ["exp","iat","iss","aud","sub"]}` | Rarely this explicit | JUVAl is **stricter** | — | KEEP |
| JWKS retrieval | `PyJWKClient(jwks_uri)`; URI **derived** as `<issuer>/.well-known/jwks.json`, discovery document not fetched | Most references fetch `/.well-known/openid-configuration` and read `jwks_uri` from it | JUVAl hardcodes the OIDC Discovery §4 convention | Low today (FusionAuth follows it, and `JUVAL_OIDC_JWKS_URI` overrides). It does mean the `issuer` published in discovery is never cross-checked | **KEEP**, with the override documented as the escape hatch |
| JWKS caching | Library defaults: `cache_jwk_set=True`, `lifespan=300`, `timeout=30` (PyJWT 2.13.0 in `.venv`) | Explicit cache config, often with a documented refresh policy | Implicit, not asserted anywhere | Medium — an unstated dependency on library defaults | **INVESTIGATE**: pin the values explicitly and assert them in a test |
| Key rotation | Handled by PyJWKClient re-fetch on unknown `kid` | Same | None | — | KEEP |
| Algorithm confusion | Prevented by RS256 pin | Same | None | — | KEEP |
| Clock skew | **No `leeway`** — PyJWT default is 0 | References commonly allow 30–60 s | JUVAl is stricter than necessary | Low, but a real source of spurious `401` between two hosts (Railway ↔ juval-server) with independent clocks | **CHANGE**: small explicit leeway, justified in a comment |
| Token type | Not checked (`typ`, or access-vs-ID) | Some references assert the token is an access token | JUVAl would accept an ID token with the right `aud` | Low-medium | **INVESTIGATE** |
| Role claim trust | `roles` claim read from the verified token; unknown roles map to **no** permissions | Same | None — the fail-closed default is right | — | KEEP |
| 401 vs 403 | 401 for missing/invalid token, 403 for authenticated-but-unauthorized | RFC 6750 semantics | None. **Notably better than FusionAuth's own API** (issue #46) | — | KEEP |
| `WWW-Authenticate` | Sent on missing/malformed header; **not** on invalid token | RFC 6750 expects it on invalid-token too | Minor | Low | **CHANGE** (trivial) |
| Failure behavior | JWKS unreachable → 401; unknown `JUVAL_AUTH_MODE` → `RuntimeError`; missing config in `oidc` mode → startup failure | Same fail-closed posture | None | — | KEEP |
| Error leakage | Generic `"invalid or expired token"`; reason logged server-side only | Same | None | — | KEEP |
| Refresh tokens | Not handled (no client) | Rotation, and RFC 9700 §4.10.1 sender-constraining as SHOULD | Not started | High once a client exists | **INVESTIGATE** |
| Browser token storage | Not handled | HttpOnly cookies via a BFF strongly preferred over `localStorage` | Not started | **High** | **INVESTIGATE → ADR** |
| Logout / session invalidation | Not handled | Local session + IdP `end_session` | Not started | Medium | **INVESTIGATE** |

### 6.2 The cross-domain problem, stated plainly

FusionAuth ships a **Hosted Backend** (since 1.45.0) that would remove most of
the SPA risk: it runs `/app/login`, `/app/callback`, `/app/refresh`,
`/app/logout`, handles PKCE and `state` for you, and stores tokens in
`HttpOnly`, `Secure`, `SameSite=Lax` cookies (`app.at`, `app.rt`), explicitly
steering developers away from `localStorage`. `VERIFIED_OFFICIAL_DOC`.

It cannot be used as JUVAl is deployed. The vendor states the requirement
directly: **the application and FusionAuth must share a domain or be
subdomains of one**; cross-origin fails on cookie scope regardless of CORS.
JUVAl's frontend is on Vercel, backend on Railway, IdP on a `juval-server`
tunnel — three unrelated origins.

So the real decision is a fork with exactly two credible branches:

- **(i) BFF on the JUVAl backend.** The FastAPI service becomes the
  confidential client: it runs the code+PKCE exchange, keeps tokens
  server-side, issues an `HttpOnly` session cookie to the SPA. Matches the
  reference architecture in `zitadel/example-auth-fastapi` (server-side
  sessions, signed cookies, full logout). Requires the SPA and API to share a
  site for cookies, or a deliberate cross-site cookie design.
- **(ii) Public SPA client with PKCE**, tokens in memory (never
  `localStorage`), silent refresh via refresh-token rotation. Simpler; weaker;
  RFC 9700 tolerates it only with PKCE and careful storage.

**This is a PENDING architectural decision** (CLAUDE.md §3) and must not be
resolved by whichever is easier to implement. It is ADR material (§13).

---

## 7. GitHub / vendor repository study

Eight entries, chosen for relevance and maintenance, not stars.

| # | Repository / issue | Maintainer | Currentness | Architecture / what it shows | Auth flow | Token validation | Password/MFA relevance | JUVAl can learn | JUVAl should NOT copy |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `FusionAuth/fusionauth-quickstart-python-flask-web` | **Vendor** | Maintained | Server-side web app against FusionAuth | Authorization code | Server-side session after exchange | — | Vendor's own idea of a correct integration shape | Its Flask session model — JUVAl's client is an SPA on a different origin |
| 2 | FusionAuth **Hosted Backend** (`/app/*`, docs + implementation) | **Vendor** | 1.45.0+ | Vendor-run BFF, `HttpOnly` cookies, PKCE and `state` handled for you | Code + PKCE | Cookies, not browser storage | — | **The cookie/storage posture is the target to match** | The mechanism itself — same-domain requirement makes it unusable here |
| 3 | `cleanenergyexchange/fastapi-zitadel-auth` | Community, active | Current | FastAPI resource-server library: JWKS validation, roles, Swagger PKCE | Resource server | Local JWKS, async OIDC config load | — | Async discovery loading; typed claims; Swagger PKCE wiring | Its Zitadel-specific role claim shape |
| 4 | `zitadel/example-auth-fastapi` | **Vendor (Zitadel)** | Current | **Server-side session** FastAPI app, signed cookies, full IdP logout | Code + PKCE via Authlib | Handled by Authlib | — | **The closest published shape to branch (i)**; its logout completeness | Authlib as a dependency decision — that is a separate CLAUDE.md §20 question |
| 5 | `SogoKato/oidc-fastapi-authlib` | Community | Moderate | Minimal FastAPI + Authlib OIDC RP | Code | Authlib | — | Minimal RP surface | Minimalism at the expense of explicit claim requirements — JUVAl's `require` list is better |
| 6 | [`fusionauth-issues#1591`](https://github.com/FusionAuth/fusionauth-issues/issues/1591) | Vendor tracker | **Closed, shipped 1.33.0** | 2FA moved before change-password outside a login flow | — | — | **Directly answers Track A ordering** | The supported order is MFA → password change | Reading it as a full 1.69.0 hosted-page spec — it is one change, not the spec |
| 7 | [`fusionauth-issues#1675`](https://github.com/FusionAuth/fusionauth-issues/issues/1675) + [`terraform-provider#126`](https://github.com/FusionAuth/terraform-provider-fusionauth/issues/126) | Vendor tracker | #1675 **open**, 1.33–1.36 | `permissions: {}` → permanently `401` until UI re-save | — | — | Nearest published "valid key returns 401" report | That a `401` on a believed-valid key has precedent, with a **configuration** cause | Concluding JUVAl matches it — JUVAl's keys were UI-created with explicit grants |
| 8 | [`fusionauth-issues#1787`](https://github.com/FusionAuth/fusionauth-issues/issues/1787) + [`#46`](https://github.com/FusionAuth/fusionauth-issues/issues/46) | Vendor tracker | #1787 **closed unreproducible**; #46 **open** | `jwt/vend` 401 despite grants; 401/403 conflation | — | — | Explains §39 and why §39–§51 could not discriminate | **That vendors close unreproducible auth anomalies too** — a strong prior for stopping | Treating "unreproducible" as "does not exist", or as "is a defect" |

Also consulted for Track A: [#2305](https://github.com/FusionAuth/fusionauth-issues/issues/2305),
[#2285](https://github.com/FusionAuth/fusionauth-issues/issues/2285) (MFA
enrollment enforcement — still open feature requests),
[#741](https://github.com/FusionAuth/fusionauth-issues/issues/741) (`203`
loop, closed), [#2524](https://github.com/FusionAuth/fusionauth-issues/issues/2524)
(`423` on lockout).

---

## 8. Amazon SP-API classification analysis

| # | `CURRENT_ASSUMPTION` (JUVAl docs) | `OFFICIAL_CURRENT_REQUIREMENT` (2026-09-09) | Verdict | `ACTION` |
|---|---|---|---|---|
| E-1 | Private developer, own seller account (`AMAZON_SP_API_COMPLIANCE.md` line 207: "Own seller account only — DECLARED YES") | *"Private seller applications are applications for sellers that are available only to your organization, and are self-authorized."* Data Access selection: *"Private Developer: I build application(s) that integrate my own company with Amazon Services APIs"* | **MATCH** | Keep; record the exact Data Access wording in the reapplication package |
| E-2 | Self-authorization NOT PERFORMED, deferred until after approval | *"To self-authorize a Seller Central account, you must be the Primary User of that account."* Private apps can be authorized in draft status | **MATCH** | Confirm the user is Primary User — `NOT_VERIFIED` in this repo |
| E-3 | Product Listing is the planning target; restricted/PII status `NEEDS_VERIFICATION` (AC-03, AC-19) | Restricted roles are exactly four: Direct-to-Consumer Shipping, Professional Services, Tax Invoicing, Tax Remittance. *"Restricted means that the role requires sensitive information, which might include personally identifiable information (PII)."* **Product Listing is not restricted** | **MATCH, and resolvable now** | **Close AC-03/AC-19 as `NON_RESTRICTED_BY_DESIGN`** and make "JUVAl requests no restricted role and processes no Amazon PII" an architectural commitment, not a status |
| E-4 | DPP §2 applicability unresolved; AC-11A/AC-13A `NEEDS_VERIFICATION` (30-day scans, annual pen test, 12-month log retention) | Non-PII developers: five core controls (credentials, network protection, user access control, 24-hour incident notification, monitoring). PII adds *"vulnerability scans every 30 days and penetration tests every 365 days"*, encryption, *"a 30-day deletion rule"* | **MATCH with the repo's cautious reading** | Keep the caution, but note the burden is now **decidable**: commit to the non-restricted role set and DPP §2's PII escalations do not attach |
| E-5 | Control 6 (name exclusion) is a HARD IdP requirement (ADR-021 item 8) | Key Security Control Guidance places the password rules under **DPP §1.4 general requirements**, mandatory language, not PII-scoped | **MATCH — and the escape hatch is closed** | Control 6 stays in scope. §5.5 is the path |
| E-6 | RF-03 needs an IdP that natively enforces every password rule | Amazon states *controls*, not *implementations*; nothing read this pass requires the IdP specifically to be the enforcement point | **UNKNOWN** | This is exactly the §21 clarification, still `AMAZON_RESPONSE = PENDING`. Do not assume either reading |
| E-7 | Case 21652891301 rejection driven by RF-01…RF-05 | Amazon's five non-PII controls map 1:1 onto RF-01…RF-05 | **MATCH** | Structure the reapplication narrative on Amazon's own five headings, in the user's own words |
| E-8 | §21 clarification was submitted; no Case ID, no text recorded | — | **MISMATCH — evidence gap in the repo** | Either recover the Case ID/text or **withdraw reliance on it** and decide Control 6 on JUVAl's own terms (§5.5). Do not keep a gate blocked on an unrecorded message |

**Evidence architecture, not prose.** Amazon asks for truthful, original
answers. What the reapplication needs is a per-control evidence table — control
→ mechanism → artifact in this repository → how it was verified → date —
which is precisely what `SP_API_REGISTRATION_REMEDIATION.md` already produces.
No application prose is drafted here, deliberately.

---

## 9. Evidence hierarchy applied

| Tier | Used for |
|---|---|
| **1 — Official docs** | FusionAuth API authentication reference (key propagation, 401 semantics, tenant-scoped keys); tenant Password settings; MFA login policy; Hosted Backend; release notes 1.65/1.66/1.69; API Endpoints Guarded by API Keys; pricing/editions. Amazon: register-as-a-private-developer, roles reference, security-compliance overview, Key Security Control Guidance, self-authorization. RFC 9700 |
| **2 — Vendor repos / trackers** | `fusionauth-issues` #46, #741, #1591, #1675, #1787, #2285, #2305, #2524; `terraform-provider-fusionauth` #126; `FusionAuth/fusionauth-quickstart-python-flask-web`; `zitadel/example-auth-fastapi` |
| **3 — Mature OSS** | `cleanenergyexchange/fastapi-zitadel-auth`, `SogoKato/oidc-fastapi-authlib` |
| **4 — Forums** | FusionAuth community threads on `DistributedCacheNotifier`, MFA enforcement, password change with 2FA — used **only** where a vendor staff member answers, and never above tier 1 |
| **5 — Inference** | Marked `INFERENCE` at each use. No conclusion in §1 rests on tier 5 alone |

Two places where the honest answer is "the direct page did not load": the
FusionAuth **Login API** reference page returned 404 at every URL tried on
2026-09-09 (`/docs/apis/login`, `/docs/apis/login/`, `/docs/v1/tech/apis/login`,
`/docs/lifecycle/authenticate-users/login-api/`). The `203`/`242` semantics in
§3 therefore rest on FusionAuth documentation **quoted through search
indexing**, corroborated by issue #741 (`203` with `changePasswordId` /
`changePasswordReason`) and by JUVAl's own §49.1 measurements of
`/api/two-factor/login`. Treat the codes as `VERIFIED_OFFICIAL_DOC`, and the
**exhaustiveness** of the status-code list as `NOT_PROVEN`.

---

## 10. Contradictions found in existing JUVAl documentation

| # | Contradiction | Which side is right |
|---|---|---|
| C-1 | `src/juval/interfaces/api/auth.py` module docstring says the IdP half is *"owned by the managed Identity Provider (ADR-022)"*, and `pyproject.toml` line 11 cites ADR-022 for the PyJWT dependency. **ADR-022 is `RECHAZADA/SUPERSEDED`** (Okta, 2026-08-19) | **Code behavior is right, the citations are stale.** Should read ADR-028 (provider) + ADR-031 (hosting). Documentation-only fix |
| C-2 | Same file: `_roles_from_claims` docstring reasons about *"Okta groups"* | Stale. The behavior (list-or-string) is provider-agnostic and correct |
| C-3 | `CLAUDE.md` §14 row states RBAC is *"aplicado server-side en los 5 endpoints"*. Measured: **10+** endpoints carry `Depends(require(...))` | Code is right; CLAUDE.md undercounts |
| C-4 | `CLAUDE.md` §18 says *"`docs/adr/` contiene **26 ADRs** (ADR-001 a ADR-026; verificado por conteo 2026-08-20)"*. Measured: **32 files**, ADR-001…ADR-032 | Code/filesystem is right; CLAUDE.md §18 is stale (its own header already says 31) |
| C-5 | CLAUDE.md header says *"31 ADRs (ADR-001 a ADR-031)"*; ADR-032 exists and is `Aceptada` | Filesystem is right |
| C-6 | Declared runtime architecture is browser→OIDC→PKCE; `frontend/` contains no auth code and the planned public nginx conf 404s the OAuth endpoints | **Neither doc is wrong about its own scope; the architecture was never reconciled.** This is the §12 decision |
| C-7 | `AMAZON_SP_API_COMPLIANCE.md` AC-03/AC-19 hold restricted/PII determination at `NEEDS_VERIFICATION` | Was correct when written; **now decidable** from the current roles reference (§8 E-3) |
| C-8 | §21 records `AMAZON_IDENTITY_CLARIFICATION = SENT` with no Case ID and no recoverable text, while gates cite it as a pending input | The document already flags this as an evidence gap. It should stop being load-bearing (§8 E-8) |
| C-9 | ADR-032's amendment history: seven grants, then corrected to six selectable grants | The **correction is right** and this pass adds independent support — FusionAuth's endpoint reference has no `/api/two-factor/login` row at all, consistent with it not being API-key-guarded |

None of these is a behavior defect. C-1…C-5 are documentation drift; C-6 is
the real architectural finding.

---

## 11. Root-cause hypothesis matrix

| ID | Hypothesis | Supporting evidence | Contradicting evidence | External evidence | Status | Confidence |
|---|---|---|---|---|---|---|
| H8-D | A mutation-triggered `AuthenticationKey` cache reload had not completed when the request was served | §52.2 bytecode: `DistributedCacheNotifier` is asynchronous; Capture Final's create→probe→`401` shape | Cannot explain IV3, which failed **after** a restart that demonstrably repopulated the cache (§52.4) | **Vendor documents exactly this**: new key *"may take up to 60 seconds"* to become usable | **VENDOR_DOCUMENTED_MECHANISM / NOT_PROVEN as the cause of any specific 401** | Mechanism: high. Causation: low |
| H-N1 | **New this pass.** Single-node self-notification is misconfigured, so reloads never land and the cache stays stale until restart | JUVAl runs **two listeners (`:9011`, `:9012`)** on a nominally single-node install — an unexplained observation carried since §33; `DistributedCacheNotifier.run()` POSTs `/api/cache/reload` to node URLs and retries on failure (§52.2) | IV3 also failed after a restart, and a restart repopulates from the DB regardless of notification | Vendor staff attribute "Failed to request a cache reload" to inter-node communication failure; consequence is stale caches | **STRUCTURALLY_POSSIBLE / NOT_PROVEN** | Low-medium. Testable **read-only**: the FusionAuth log would carry the notifier error |
| H-CUSTODY | The value transmitted differed from the value persisted (transcription, encoding, whitespace, truncation) | Survives everything; §52.4 names it the surviving explanation for IV3 | Capture Final was verified **byte-for-byte** identical to the persisted value revealed by FusionAuth (§52.3) | Auth path does **no** trim/strip on the header (§52.1) — so custody must be exact, which raises the bar for this hypothesis, not lowers it | **NOT_PROVEN, and for IV3 (`key_format=1`, not retrievable) NOT PROVABLE IN PRINCIPLE** | Medium for IV3, low for Capture Final |
| H-GRANT | The `401`s were authorization (endpoint not in the key's grant map), not authentication | FusionAuth returns `401` for both (`VERIFIED_OFFICIAL_DOC`); §52.1 shows `allowedMethods` failing to an exception; permission rows key on `actionURI`, and a granted row may not cover the exact URI a tool calls | §47: a fresh key with the same grant shape authenticated | Issue #46 (open): 401 used where 403 belongs | **NOT_PROVEN, and NOT DISTINGUISHABLE by black-box probing** | Low-medium |
| H-1675 | Empty-permissions super-key defect | — | JUVAl's keys were UI-created with explicit grants — the path that issue says *repairs* the condition | Issue #1675 open, 1.33–1.36 | **NOT_MATCHING** | Very low |
| H-165 | 1.65/1.66 tenant-scoped-key hardening rejects the calls | Version 1.69.0 > 1.65.0; keys are tenant-scoped; tenant header is sent on most calls | **Every endpoint used is documented "tenant-scoped or global may be used"** | FusionAuth *API Endpoints Guarded by API Keys* reference | **NOT_MATCHING** (and it explains `GET /api/status`, which is global-only) | Very low as a cause; high as a closed line |
| H-DEFECT | FusionAuth 1.69.0 has a defect in API-key authentication | — | No reproducible implementation-level contradiction was ever demonstrated (§52.3) | No matching vendor issue for 1.6x | **NO_EVIDENCE — NOT CLAIMED** | — |

**Aggregate: `ROOT_CAUSE = NOT_PROVEN`.** The three failing credentials do not
share one mechanism, and §52's refusal to record them as if they did is
upheld.

---

## 12. Architecture verdict per component

| Component | Verdict | Why |
|---|---|---|
| `auth.py` token verification (RS256 pin, iss/aud/exp, required claims) | **KEEP** | Matches or exceeds every reference |
| `auth.py` RBAC + `require()` + 401/403 split | **KEEP** | Correct RFC 6750 semantics; better than the IdP's own API |
| Fail-closed config (`build_verifier`, `auth_mode`) | **KEEP** | Startup error over silent downgrade is right |
| JWKS URI derivation (no discovery fetch) | **KEEP** | Convention + explicit override; document the choice |
| JWKS cache parameters (implicit library defaults) | **CHANGE** | Make explicit and test-asserted |
| Clock skew (`leeway = 0`) | **CHANGE** | Two hosts, independent clocks; small explicit leeway |
| `WWW-Authenticate` on invalid token | **CHANGE** | Trivial RFC 6750 conformance |
| Token-type / `typ` check | **INVESTIGATE** | Decide whether an ID token should be rejected |
| Stale ADR-022 citations in `auth.py` / `pyproject.toml` | **CHANGE** | Documentation-only (C-1, C-2) |
| **Browser OIDC client (login, PKCE, token custody, refresh, logout)** | **INVESTIGATE → ADR → build** | Does not exist; blocks `JUVAL_AUTH_MODE=oidc` entirely |
| **Public issuer surface (`nginx-fusionauth-public.conf`)** | **INVESTIGATE → CHANGE** | Two-path allow-list cannot serve a browser login. Widening it is a deliberate attack-surface decision, exactly as the file's own comment demands |
| FusionAuth Hosted Backend (`/app/*`) | **REMOVE from consideration** | Same-domain requirement is incompatible with Vercel + Railway + tunnel |
| Administrative API-key tooling (`configure_fusionauth`, `verify_rbac`, `verify_identity_behavior`) | **INVESTIGATE → likely REMOVE from the critical path** | `API_AUTH = FAIL`, root cause unprovable, and the evidence it produces is obtainable without it (§16) |
| ADR-032 lifecycle separation | **KEEP** | Vindicated: total admin-plane failure, zero runtime impact |
| `disallowUserLoginId = false` | **CHANGE** | Free partial control currently switched off. Never report it as closing Control 6 |
| Control 6 enforcement | **INVESTIGATE → ADR → build (Option C)** | §5.5 |
| `JUVAL_AUTH_MODE` unset in production | **KEEP for now, gate explicitly** | Correct today; must flip only when the frontend client and the public issuer surface both exist |

---

## 13. ADRs required

| ADR | Subject | Status to open with |
|---|---|---|
| **ADR-033** | Identity verification strategy: retire administrative-API-key-dependent behavioral verification; verify RF-03 through user-facing flows; define the isolated lab as the only place unresolved runtime behavior is reproduced | **Propuesta** — created this pass |
| ADR-034 | **Browser authentication topology**: BFF-on-backend vs public SPA client with PKCE; token custody; refresh; logout. Includes the public issuer surface that topology requires | Not created — needs the user's decision, and it is a §3 "no decide silenciosamente" class decision |
| ADR-035 | **Control 6 enforcement**: Option C as the enforced control, admin-console path as disclosed residual risk under a naming standard | Not created — depends on the two verifications in §5.5 |

ADR-009 and ADR-021 sit at `Estado: Propuesta` today, so a Proposed state is an
established convention in this repository. ADR-033 follows it.

---

## 14. Isolated reproduction plan (specification only — nothing built)

**Not created this pass.** Specification only, as instructed.

**Isolation boundary — analysis, not preference.** A separate *tenant* on the
production instance is **insufficient**: the questions are instance-level
(cache/notifier behavior, node self-notification, hosted-page ordering), and a
tenant boundary does not isolate any of them. It also puts experiments on the
host that carries JUVAl's only repository copy. **Required boundary: a
separate, disposable FusionAuth instance.**

**Lab specification**

| Property | Requirement |
|---|---|
| Version | Exactly **1.69.0** — the deployed version, pinned by digest, not by tag |
| Substrate | Container/VM on the operator's workstation, **not `juval-server`**; no inbound port |
| Database | Fresh PostgreSQL, empty schema, created and destroyed with the lab |
| Configuration | Kickstart file in the repo, reproducing the JUVAl tenant policy from `deploy/fusionauth/tenant-password-policy.template.json` — minLength 12, mixed case, number, non-alpha, history 10, lockout 10/30 min, **MFA `loginPolicy = Required`**, TOTP HmacSHA1/6/30 |
| Secrets | **None from production.** No production API key, no production user, no production tenant/application id, no production issuer, no `.env` |
| Users | Synthetic only, obviously-synthetic names, generated per run |
| Teardown | Automatic: destroy container **and** volume at the end of every run; the lab is never long-lived |
| Output | A machine-readable transcript of statuses and observed ordering — never a secret, never a password, never a TOTP secret, never a JWT |

**Questions the lab exists to answer, and nothing else**

| ID | Question | Why it needs runtime |
|---|---|---|
| **L-1** | With `loginPolicy = Required` and a user having no TOTP method, what does the **hosted** login page do in 1.69.0 — block, or offer enrollment? | §3.2 answer rests on docs + forum, and the hosted-page behavior is version-sensitive. It determines the entire onboarding design |
| **L-2** | Are tenant password rules applied identically at admin-console set, admin-API set, forced change and self-service change? | §3.2 `NOT_PROVEN`; it is the prerequisite for claiming Option C has coverage (§5.5) |
| **L-3** | Exact 1.69.0 hosted-page ordering of `passwordChangeRequired` vs the 2FA challenge, and whether a trust token is required | §3.2 rests on a 1.33.0 issue and forum answers |
| **L-4** | Is the hosted `/password/forgot` route reachable and completable without SMTP? | Determines whether Option C's coverage claim has a hole |
| **L-5** | Does the Self-Service Registration Validation lambda receive a usable plaintext password? | The only remaining chance of a FusionAuth-native Control 6, currently `NOT_PROVEN`. **Paid-tier gated** — run only if a trial license is available; otherwise leave `NOT_PROVEN` and proceed with Option C |
| **L-6** | *(conditional, low priority)* Reproduce B-1: create a key and probe it at t+0 s, +2 s, +10 s, +60 s | **Only** run if the user wants the API-key question formally closed. It can confirm the vendor's documented timing; it can **never** retroactively explain IV3 or Capture Final. Recommended **NOT** to run |

Nothing in the lab touches production. Nothing in the lab needs a production
credential. If the lab cannot answer a question without one, the question does
not belong in the lab.

---

## 15. What NOT to test anymore

Closed. Reopening any of these needs a new, concrete failure — not curiosity.

1. **Any black-box API-key probe against production.** `401` is documented as
   non-discriminating; every probe returns the same one bit.
2. **The historical credentials** (IV1, IV2, IV3, Behavioral 1/2, the two
   Capture Diagnostic Final rows). IV3 is `key_format=1` and not retrievable:
   its custody question is **unanswerable in principle**.
3. **`authentication_keys` row forensics.** §44/§51 exhausted it; §52 closed it.
4. **Static forensics of the FusionAuth API-key path.** `SimpleCache`,
   `/api/cache/reload` internals, further bytecode.
5. **Process memory, heap, `tcpdump`, `strace`.** Refused on security grounds —
   the cache holds literal key values. This refusal is permanent.
6. **Whether this is a FusionAuth defect.** No reproducible contradiction was
   demonstrated; the vendor documents a non-defect mechanism with the same
   shape. Filing a vendor issue with what exists today would be filing
   `NOT_PROVEN`.
7. **Okta, Cognito, Entra, Auth0, Supabase Auth, JumpCloud, ZITADEL.**
   Rejected in ADR-021/ADR-022. Not reopened by anything found here.
8. **Whether avoiding PII avoids Control 6.** Answered: it does not (§5.3).

One deletion remains outstanding and is unrelated to testing: the two
`JUVAL Capture Diagnostic Final` rows (§52.6), `key_format=0`, literal values
stored in the clear, expiry ≠ deletion. Operator action, admin UI, ids verified
before deleting.

---

## 16. Minimum next implementation phase

One phase. Not a sequence of probes. Sequenced by dependency, and every step
is verification or documentation until the user makes the two decisions the
agent is not allowed to make alone.

**Phase objective: produce RF-03/RF-04 behavioral evidence with zero
administrative API keys, and unblock the runtime architecture decision.**

1. **Documentation truth pass** (agent, no risk): fix C-1…C-5 — stale ADR-022
   citations in `auth.py`/`pyproject.toml`, the 5-vs-10 endpoint count, the
   26-vs-32 ADR count. No behavior change.
2. **Backend hardening pass** (agent, small): explicit JWKS cache parameters,
   explicit clock-skew leeway, `WWW-Authenticate` on invalid token, plus tests.
   All three are §12 `CHANGE` verdicts with no decision content.
3. **Operator-driven behavioral verification, credential-free** (operator +
   agent): the operator creates one disposable user and enrolls TOTP **in the
   admin console**; the agent then observes only public flows — hosted login,
   wrong password ×10 to observe lockout, TOTP challenge, password rules on
   change — recording statuses, never secrets. This produces the RF-03 evidence
   that has been blocked since §41, **and it needs no API key at all**. It is
   the operational form of ADR-033.
4. **Two user decisions**, put to the user as decisions, not options to be
   quietly resolved: (a) browser authentication topology — BFF vs public SPA
   client (→ ADR-034); (b) Control 6 — confirm Option C (→ ADR-035).
5. **Only then**: implement the chosen client, widen the public issuer surface
   to exactly what that client needs, and flip `JUVAL_AUTH_MODE=oidc` — in that
   order, never before.

Steps 1–3 are unblocked today. Steps 4–5 are `PENDING DECISION`.

---

## 17. Remaining unknowns

| # | Unknown | Class | How it would be resolved |
|---|---|---|---|
| U-1 | Why any specific historical request returned `401` | `NOT_PROVEN`, and for IV3 **unprovable in principle** | Nothing available. Accept |
| U-2 | Why two listeners (`:9011`, `:9012`) exist on a single-node install | `NOT_PROVEN` | Read-only: FusionAuth configuration + service logs. Cheap; do it during step 3 |
| U-3 | Hosted-page behavior with `loginPolicy=Required` and no TOTP method (1.69.0) | `NOT_PROVEN` | Lab L-1, or step 3's operator run |
| U-4 | Whether password rules apply identically across all four set/change paths | `NOT_PROVEN` | Lab L-2 |
| U-5 | Whether `/password/forgot` is completable without SMTP | `NOT_PROVEN` | Lab L-4 / read-only config check |
| U-6 | Whether the Self-Service Registration Validation lambda sees a plaintext password | `NOT_PROVEN` | Lab L-5, paid-tier gated. Do not block on it |
| U-7 | Whether Amazon accepts Solution-Provider-side enforcement of Control 6 | `UNKNOWN` — §21 clarification unanswered and unrecoverable | Either recover the case or decide without it (§8 E-8) |
| U-8 | Whether the user is Primary User of the seller account (self-authorization prerequisite) | `NOT_VERIFIED` in this repo | One question to the user |
| U-9 | Exhaustiveness of the FusionAuth Login API status-code list | `NOT_PROVEN` — the reference page 404'd at every URL tried | Retry the vendor docs later, or read the 1.69.0 OpenAPI spec |

---

## Source register

FusionAuth (accessed 2026-09-09): [Authenticate with our APIs](https://fusionauth.io/docs/apis/authentication) ·
[API Endpoints Guarded by API Keys](https://fusionauth.io/docs/reference/api-endpoints) ·
[Tenants / password settings](https://fusionauth.io/docs/get-started/core-concepts/tenants) ·
[Retrieve a Tenant](https://fusionauth.io/docs/apis/tenants/retrieve-a-tenant) ·
[Multi-Factor Authentication](https://fusionauth.io/docs/lifecycle/authenticate-users/multi-factor-authentication) ·
[Login Validation Lambda](https://fusionauth.io/docs/extend/code/lambdas/login-validation) ·
[Self-Service Registration Validation Lambda](https://fusionauth.io/docs/extend/code/lambdas/self-service-registration) ·
[Hosted Backend API](https://fusionauth.io/docs/apis/hosted-backend) ·
[Release Notes](https://fusionauth.io/docs/release-notes) ·
[Pricing / editions](https://fusionauth.io/pricing) ·
forum threads on `DistributedCacheNotifier` and password-change-with-2FA (tier 4, vendor-staff answers only).

FusionAuth issue tracker: [#46](https://github.com/FusionAuth/fusionauth-issues/issues/46) ·
[#741](https://github.com/FusionAuth/fusionauth-issues/issues/741) ·
[#1591](https://github.com/FusionAuth/fusionauth-issues/issues/1591) ·
[#1675](https://github.com/FusionAuth/fusionauth-issues/issues/1675) ·
[#1787](https://github.com/FusionAuth/fusionauth-issues/issues/1787) ·
[#2285](https://github.com/FusionAuth/fusionauth-issues/issues/2285) ·
[#2305](https://github.com/FusionAuth/fusionauth-issues/issues/2305) ·
[#2524](https://github.com/FusionAuth/fusionauth-issues/issues/2524) ·
[terraform-provider #126](https://github.com/FusionAuth/terraform-provider-fusionauth/issues/126).

Amazon (accessed 2026-09-09): [Register as a Private SP-API Developer](https://developer-docs.amazon/sp-api/docs/register-as-a-private-developer) ·
[Roles in the Selling Partner API](https://developer-docs.amazon/sp-api/docs/roles-in-the-selling-partner-api) ·
[SP-API Security and Compliance Overview](https://developer-docs.amazon.com/sp-api/docs/security-compliance-overview) ·
[Key Security Control Guidance](https://developer-docs.amazon/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration) ·
[Authorize Private Applications (self-authorization)](https://developer-docs.amazon/sp-api/docs/self-authorization).

Standards: [RFC 9700 — Best Current Practice for OAuth 2.0 Security](https://datatracker.ietf.org/doc/html/rfc9700).

Reference implementations: `FusionAuth/fusionauth-quickstart-python-flask-web` ·
`zitadel/example-auth-fastapi` · `cleanenergyexchange/fastapi-zitadel-auth` ·
`SogoKato/oidc-fastapi-authlib`.

---

# ISOLATED REPRODUCTION RESULTS

**Added 2026-09-09, same day, separate pass.** This section is appended, not
merged into the research above: §14 specified a lab, and this records what
happened when it was attempted.

**First attempt (design pass): BLOCKED before creation** — recorded in R.1-R.4
below, preserved unchanged. **Second attempt (execution pass, same day, after
operator authorisation of Option B): EXECUTED, ANSWERED, AND TORN DOWN** — see
R.5. Full detail in `docs/research/FUSIONAUTH_169_IDENTITY_LAB.md`.

## R.1 Why it is blocked

The lab host **is** `juval-server`, the production host. Measured capability
inventory (2026-09-09):

- no `docker`, `podman`, `nerdctl` or `systemd-nspawn`;
- `/usr/local/fusionauth` is `drwxr-x--- fusionauth:root` — the installed
  1.69.0 binaries and its bundled JRE are **unreadable** by the working user;
- **no system Java at all**; FusionAuth 1.69 requires Java 21;
- **no passwordless sudo**;
- no PostgreSQL credential for the working user.

One capability is unexpectedly favourable: `initdb`, `pg_ctl` and `postgres`
are world-executable, so a **fully isolated PostgreSQL cluster can be created
in user space with no root at all** — own postmaster, own data directory, own
unix socket, no TCP port. The database half of the isolation problem is solved
without privilege.

The remaining half is not. Obtaining a FusionAuth 1.69.0 tree plus a Java 21
runtime needs either a download or one `sudo cp` of the installed tree. Both
are operator decisions under this phase's rules, so work stopped rather than
proceeding.

**Docker is not required and is not proposed.** The selected mechanism
introduces no container runtime, so no ADR-033 authorisation question about
Docker arises.

## R.2 Unintended LXD snap installation — recorded, not buried

The capability probe `lxc --version` invoked `/usr/sbin/lxc`, which on Ubuntu
24.04 is a `lxd-installer` shim that **installs the LXD snap on first
invocation**. It did (`snap changes` ID 6, Done, 14:50–14:51 UTC). This was
unintended and unapproved.

Measured blast radius: LXD daemon `inactive`, `lxd init` never run, **no
`lxdbr0`**, network interfaces unchanged (`lo`, `wlo1`), production
`fusionauth-app` `MainPID`/`NRestarts` unchanged. The firewall could not be
inspected without root, so "no firewall rule was added" is **unverified rather
than claimed** — `lxd init`, the step that would add rules, was not run.

Removal needs the operator (`snap remove lxd`; optionally
`apt purge lxd-installer`). **Recommended.** Process correction adopted for the
rest of this phase: capability probing uses `command -v` / `ls -l` / `dpkg -S`
only — on this distribution, invoking a binary can *be* an installation.

## R.3 Production isolation evidence

| Property | Before | After | Verdict |
|---|---|---|---|
| `fusionauth-app` `MainPID` | `369334` | `369334` | unchanged |
| `NRestarts` | `0` | `0` | unchanged |
| `ActiveEnterTimestamp` | `2026-09-07 18:46:43 UTC` | identical | **not restarted** |
| Listeners | `*:9011`, `*:9012` | identical | unchanged |
| Tenant / application / users | untouched | untouched | no API call, no login, no key |
| `git HEAD` | `26b4f9d` | `26b4f9d` | unchanged |
| `frontend/`, `frontend-next/`, `demo/` | clean | clean | unchanged |

## R.4 Effect on the open questions

None of §17's unknowns moved. U-3 (L-1), U-4 (L-2), U-5 (L-4) and the L-3
ordering question remain `NOT_PROVEN` and now carry a named, costed path to
resolution. `CONTROL_6` remains `B — PARTIALLY_SATISFIED`; the coverage probe
that ADR-035 depends on (C6-01…C6-04) was specified and not run.

One side observation from the baseline capture, unrelated to the lab and **not
acted upon**: `systemctl status fusionauth-app` reports that the unit file or
its drop-ins changed on disk and a `daemon-reload` is pending. This predates
this session. It is a production action and belongs to the operator.

## R.5 Execution pass — lab built, questions answered, lab destroyed

Operator authorised Option B. A FusionAuth **1.69.0** instance (vendor ZIP) ran
against a private PostgreSQL 16 cluster on `127.0.0.1:9411`/`:55432`, was
configured to JUVAl's tenant policy, answered every question, and was destroyed.
Production `fusionauth-app` finished with `MainPID=369334`, `NRestarts=0` and
`ActiveEnterTimestamp 2026-09-07 18:46:43 UTC` — **identical to baseline**.

| Question | Answer | Class |
|---|---|---|
| **L-1** | `loginPolicy=Required` + no enrolled method → **`242`** with `methods: []` and `configurableMethods: ["authenticator"]`. The challenge cannot be satisfied (`421`) **and** the enrolment endpoint also returns `421` — a closed loop. Login is not refused; it is made unsatisfiable | `VERIFIED_LAB` |
| **L-2** | Five API surfaces — admin-API create, admin-API change, forced change, key-protected self-service change, forgot-minted `changePasswordId` — **all enforce the identical rule set with identical error codes** (`tooShort`, `requireNumber`, `onlyAlpha`, `singleCase`, `previouslyUsed`). Equivalence **measured**, not assumed. **Admin console: `NOT_TESTED`** | `VERIFIED_LAB` |
| **L-3** | **MFA precedes password change.** Single-variable control: `loginPolicy=Disabled` + `passwordChangeRequired` → `203`; flip only the policy to `Required` → `242`. Full path: `242` → second factor → `203` → change → `200` | `VERIFIED_LAB` |
| **L-4** | `/password/forgot` and `/password/change` exist on Community. `POST /api/user/forgot-password` → **`403`** without usable SMTP, **but** with `sendForgotPasswordEmail:false` it returns **`200` plus a `changePasswordId`** usable with **no API key** — an email-ownership bypass, not a rule bypass | `VERIFIED_LAB` |
| **Control 6** | `firstName` and `lastName` in a password: **accepted**, including with `disallowUserLoginId=true`. Positive control fires: full email → `containsEmail`, username → `containsUsername`. `CONTROL_6 = B — PARTIALLY_SATISFIED`, unchanged, now **behavioural** rather than documentary | `VERIFIED_LAB` |

### R.5.1 Corrections this lab forces on the research above

1. **§5.2 / §5.5 — the self-service account portal is NOT paid-only.**
   `GET /account/?client_id=<app>` returned **200 on unlicensed Community**.
   The pricing-page-derived claim is **withdrawn**, and with it §5.5's argument
   that Community makes Option C's bypass surface unusually small. Option C is
   still the recommendation, but on narrower grounds and with conditions.
2. **§17 U-2 — answered.** The unexplained second listener (`:9012`) on
   `juval-server` is **stock 1.69.0 behaviour**: a clean instance with no
   management port configured attempts the same second listener. Not a
   misconfiguration.
3. **§14 lab spec — two premises were wrong.** The FusionAuth ZIP **bundles its
   own JRE** (the separately downloaded Temurin 21 went unused), and
   `fusionauth-app.management-port` is **not a recognised 1.69.0 property**, so
   the lab repeatedly attempted to bind production's `9012` and was refused by
   the OS. Fail-safe here, but a genuine isolation defect: a future lab on this
   host must never run while production is stopped.

### R.5.2 What still is not measured

The FusionAuth **admin console** password-set path. Driving it needs a live
administrator credential typed into the session transcript, which the phase's
secret rules forbid. It is `NOT_TESTED` — not inferred from the five API
surfaces that were tested — and it is the one input ADR-035 still lacks.
