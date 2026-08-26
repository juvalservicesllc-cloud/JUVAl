# FusionAuth deployment and control evidence plan (RF-03 / RF-04)

**2026-08-26.** Companion to ADR-028 (provider direction) and
`SP_API_REGISTRATION_REMEDIATION.md` §30. Turns the approved provider
*direction* into an executable deployment and a verification procedure that
produces Amazon-citable evidence.

**This document is a plan and a set of templates. It is not evidence.** No
FusionAuth instance exists. `IDP_IMPLEMENTATION = NOT_IMPLEMENTED`,
`IDP_RUNTIME = INACTIVE`, `RF-03 / RF-04 = NOT_VERIFIED` — unchanged.

---

## 1. Control matrix — what FusionAuth actually does for each Amazon control

Source: ADR-021's measured evidence, not re-derived here. Classification uses
this mission's taxonomy.

| # | Amazon control | FusionAuth field | Classification | Evidence status |
|---|---|---|---|---|
| 1 | Minimum length ≥ 12 | `passwordValidationRules.minLength` | `CONFIGURABLE` | `NOT_VERIFIED` — no tenant |
| 2 | Uppercase required | `requireMixedCase` | `CONFIGURABLE` | `NOT_VERIFIED` |
| 3 | Lowercase required | `requireMixedCase` | `CONFIGURABLE` | `NOT_VERIFIED` |
| 4 | Numeric required | `requireNumber` | `CONFIGURABLE` | `NOT_VERIFIED` |
| 5 | Special character required | `requireNonAlpha` | `CONFIGURABLE` | `NOT_VERIFIED` |
| **6** | **Password must not contain any part of the user's name** | login-Id rejection (≥ 1.63.0) | **`CUSTOM_EXTENSION_REQUIRED` / unresolved** | **`B — PARTIALLY_SATISFIED`** — see §2 |
| 7 | Password history ≥ 10 | `rememberPreviousPasswords.count` | `CONFIGURABLE` | `NOT_VERIFIED` |
| 8 | Minimum password age ≥ 1 day | `minimumPasswordAge.seconds` | `NATIVE_FUSIONAUTH` | `NOT_VERIFIED` |
| 9 | Maximum password age ≤ 365 days | `maximumPasswordAge.days` | `NATIVE_FUSIONAUTH` | `NOT_VERIFIED` |
| 10 | MFA on all accounts | TOTP / WebAuthn | `CONFIGURABLE` | `NOT_VERIFIED` — enabling a method is not requiring it (§4) |
| 11 | Lockout ≤ 10 attempts | `failedAuthenticationConfiguration.tooManyAttempts` | `CONFIGURABLE` | `NOT_VERIFIED` — feature confirmed, exact range never re-verified (ADR-021) |
| — | Role separation (viewer/operator/admin) | application roles → `roles` claim | `APPLICATION_ENFORCED` | Backend half **implemented and tested** (37 tests); dormant |
| — | Auditability | FusionAuth event log + `journald` | `CONFIGURABLE` | `NOT_VERIFIED` |

**`FUSIONAUTH = 10/11 PASS + 1 PARTIAL`** (ADR-021, unchanged).
`MINIMUM_FUSIONAUTH_VERSION = 1.63.0` — re-confirmed against ADR-021 this
pass; the login-Id rejection setting and `validateOnLogin` do not exist below
it, and applying the template to an older release silently drops them.

## 2. Control 6 — the one open HARD gap, stated precisely

Amazon requires rejecting **any part of the user's name**. FusionAuth ≥ 1.63.0
natively rejects only the configured **login identifier** (email / username /
phone), which is a distinct field from `firstName` / `lastName` in FusionAuth's
own data model.

ADR-021 established this is **architectural, not documentary**: the
`user.password.update` webhook is explicitly non-transactional and its payload
carries no plaintext password; the self-service registration lambda does not
receive a password field. No FusionAuth extensibility mechanism both fires
before the password is persisted *and* receives the plaintext value.

`COMPENSATING_CONTROL_REQUIRED` was considered and **rejected**: the only
mechanism that would work is a custom proxy in front of FusionAuth's own APIs,
which is custom authentication — forbidden by `CLAUDE.md`.

Two admissible resolutions, both requiring the user:

- **R-1** — accept the disclosed residual risk with an organizational
  compensating control (documented account-naming standard + review at the
  quarterly access review), declared honestly to Amazon as a partial.
- **R-2** — Amazon answers the identity-scope clarification already submitted
  (`SP_API_REGISTRATION_REMEDIATION.md` §21), which may narrow the applicable
  scope.

Neither is a code change. **Do not mark control 6 satisfied by deploying.**

## 3. Deployment architecture

### 3.1 Where it runs — BLOCKED on an architectural decision

**`juval-server` is not currently an admissible host.** ADR-027 (Aceptada,
derived from an explicit user instruction) states: *"**Identity server** —
ningún IdP se despliega aquí … seguirá siendo un servicio gestionado externo,
nunca construido en este host"*, and *"Cualquier extensión de este rol …
requiere un ADR nuevo"*.

Hosting FusionAuth there is therefore **case C: it conflicts with an existing
Accepted ADR**, not a compatible extension. `ADR-031` (Propuesta, this pass)
sets out the options with the smallest defensible scope. Deploying before the
user accepts it would silently contradict an Accepted ADR — see §7.

### 3.2 Mechanism — package + systemd, not Docker

Docker is **not approved anywhere in this repository**. FusionAuth's supported
non-container install (zip/deb + systemd unit + external PostgreSQL) is used
instead. This is also the lower-complexity option for a single node
(`CLAUDE.md` §5).

### 3.3 Components required

| Component | Purpose | Note |
|---|---|---|
| FusionAuth app (≥ 1.63.0) | OIDC issuer, JWKS, password engine | JVM service |
| PostgreSQL ≥ 13 | FusionAuth's own store | **Not** JUVAl's production data (ADR-017 unaffected) |
| Search | user search | `database` mode — avoids adding Elasticsearch on this hardware |
| TLS reverse proxy | `iss` must be `https://` | JWKS over plain HTTP is not acceptable evidence |
| systemd units | restart policy, boot persistence | run as a service account, never root (ADR-027) |
| Backup | PostgreSQL dump + keys | identity data is not regenerable from Git |

### 3.4 Steady-state resource estimate

Host: Ryzen 3 3250U (2c/4t), ~13 GiB RAM, ~98 GB root.

| | Estimate |
|---|---|
| FusionAuth JVM | ~1.0–1.5 GiB resident (default heap 512 MB–1 GB + JVM overhead) |
| PostgreSQL | ~250–500 MiB with a small dataset |
| TLS proxy | ~50 MiB |
| **Total added** | **~1.5–2 GiB RAM, ~3–5 GB disk** |

Fits with headroom on RAM and disk. The honest caveats: this is a **2-core**
CPU that already runs `pytest`, `npm build` and Playwright E2E, and a JVM plus
PostgreSQL compete with exactly those workloads; and *installation starting* is
not evidence of adequate steady-state capacity — H-11 capacity alerting
(`HOST_CONTROLS_JUVAL_SERVER.md`) must cover the new services before this can
be called verified.

## 4. Verification procedure — what turns config into evidence

`tools/verify_oidc.py` (added this pass) performs the machine-checkable part.
It is read-only, takes no secret as an argument, prints no token, key or
secret, and exits non-zero on failure.

```
python tools/verify_oidc.py --issuer https://<issuer>
JUVAL_IDP_API_KEY=... python tools/verify_oidc.py --issuer https://<issuer> --tenant-policy
```

| Check | Evidences |
|---|---|
| discovery document reachable, `issuer` matches | the value pinned in `JUVAL_OIDC_ISSUER` is the one tokens will carry |
| JWKS reachable, ≥ 1 key | the backend can verify signatures at all |
| algorithm ∈ {RS256} | matches `auth.py`'s pinned algorithm; no alg-confusion |
| every key has a `kid` | multi-key rotation cannot cause intermittent 401s |
| tenant policy fields vs Amazon values | controls 1–5, 7, 8, 9, 11 |
| control 6 | reported `NOT_VERIFIED` **by design**, so a green run never implies it passed |

Not machine-checkable here, and must be evidenced manually:

- **MFA required for every account** — the template enables TOTP and sets
  `loginPolicy: Required`; enabling a method is not the same as every existing
  user having enrolled. Evidence is a user-by-user enrolment report.
- **Role claim shape** — that `roles` arrives as the backend expects is proven
  by the existing negative tests once a real token exists.
- **Lockout actually locking** — requires deliberate failed logins against a
  dedicated non-sensitive test user.

## 5. JUVAl activation (RF-03/RF-04 runtime)

The backend needs no code change to adopt FusionAuth — the boundary is already
provider-agnostic. One defect **was** found and fixed this pass: the default
JWKS path was Okta's `/v1/keys`, written while ADR-022 was the plan. It now
follows the OIDC Discovery convention (`/.well-known/jwks.json`), which is what
FusionAuth publishes. A vendor-shaped default in a provider-agnostic boundary
fails only at the first real token verification, as a bare 401 long after
startup succeeded.

```
JUVAL_AUTH_MODE=oidc
JUVAL_OIDC_ISSUER=https://<issuer>
JUVAL_OIDC_AUDIENCE=<application client id>
JUVAL_OIDC_ROLES_CLAIM=roles
# JUVAL_OIDC_JWKS_URI only if the provider deviates from the convention
```

**Order matters.** `JUVAL_AUTH_MODE=oidc` with no reachable issuer breaks every
request (`SECRETS.md` §8 S-4). Deploy and verify the IdP first, then flip the
mode, then re-run the negative suite against the real issuer.

## 6. Secrets

Never in Git, never in a `VITE_*` variable, never in this document, never in a
command-line argument. The backend validates tokens with the issuer's **public**
JWKS and needs no client secret to do so.

| Secret | Lives in | Never |
|---|---|---|
| FusionAuth admin password | operator's password manager | Git, docs, logs, shell history |
| FusionAuth API key | host environment / systemd `EnvironmentFile` (mode 0600, root-owned) | repository, unit file body |
| PostgreSQL password | same | repository |
| Application client secret | backend environment only | any frontend bundle |

## 7. What this pass could not do, and why

| Item | Blocker | Class |
|---|---|---|
| Deploy FusionAuth | ADR-027 forbids an IdP on `juval-server`; ADR-031 is `Propuesta` | **Architectural decision — user** |
| Create tenant / application / users | requires a running instance and an admin credential | **User secret / third-party** |
| Export password-policy evidence | requires a tenant | Downstream of the above |
| Close control 6 | architectural in FusionAuth; R-1 or R-2 both need the user or Amazon | **User / Amazon** |
| Set `JUVAL_AUTH_MODE=oidc` in production | would break every request with no issuer | Downstream |
| Re-verify E-5 (workstation patching) | host action | **User** |
| E-8 quarterly access review | no users exist to review yet | Downstream of the IdP |
| Amazon reapplication (E-9) | every RF must reach `COMPLIANT` first | **Amazon** |
