# Identity onboarding — provisioning a JUVAl user under MFA `Required`

**Date: 2026-09-09; evidence correction 2026-09-10.** Historical operator
provisioning design below. The authorized disposable JUVAl experiment has now
observed hosted TOTP enrollment under Required without pre-attaching a factor,
and reached its callback. Therefore the blanket hosted-enrollment impossibility
claim below is superseded for this runtime. Preserve the isolated API results as
historical evidence, not a universal hosted-flow conclusion. Production onboarding
remains unactivated; ADR-041 is Proposed. See MFA_DISPOSABLE_DISCOVERY_20260910.md.

Governing decisions: ADR-034 (BFF), ADR-035 (Control 6), ADR-032 (credential
lifecycle). Measured basis: `docs/research/FUSIONAUTH_169_IDENTITY_LAB.md` §9.2.

---

## 1. The flow that does NOT work, and why

```
create user  ->  first login  ->  enrol MFA          <-- REJECTED
```

Measured on FusionAuth 1.69.0 with `multiFactorConfiguration.loginPolicy =
Required` and a user holding no MFA method:

| Step | Observed |
|---|---|
| `POST /api/login` with the correct password | **`242`**, `methods: []`, `configurableMethods: ["authenticator"]` |
| `POST /api/two-factor/login` with that `twoFactorId` | **`421`** |
| `POST /api/user/two-factor/{userId}` (enrol), four variants | **`421`** every time |

The user cannot complete the challenge **and** cannot enrol the factor that
would let them complete it. FusionAuth's own documentation says such a user
"will not be able to log in"; the measured mechanism is more specific — the
login is not refused, it is made unsatisfiable — and the practical consequence
is the same. FusionAuth's hosted pages do not offer enrolment, and the vendor's
open feature requests (#2285, #2305) confirm that is still true.

**Therefore: a user must never reach `loginPolicy = Required` without a method
already attached.** Any onboarding design that assumes otherwise is wrong for
this configuration, not merely awkward.

## 2. The two mechanisms that do work

Both were measured.

| | **M1 — pre-seed at creation** | **M2 — temporary policy relaxation** |
|---|---|---|
| How | `POST /api/user` with `user.twoFactor.methods[]` carrying the authenticator secret | Set the tenant policy to something other than `Required`, enrol, restore |
| Measured | **`200`**, method present on the user | Enrolment endpoint still returned `421` in the lab — **not confirmed working** |
| Blast radius | One user | **Tenant-wide**: every user is unprotected for the duration |
| Auditability | One create call | Two policy changes plus whatever happened between them |

**M2 is rejected as the default.** Relaxing a tenant-wide MFA policy to onboard
one person removes the control for everyone for as long as the window is open,
and it is precisely the kind of change that gets left switched off. ADR-034's
principle — prefer a per-user mechanism over a global toggle — applies
directly. It is also not even proven to work: the lab's enrolment call returned
`421` with the policy relaxed too.

## 3. Approved model: operator-provisioned, per user

```
1. Operator generates a TOTP secret               (FusionAuth admin console)
2. Operator creates the user with the method attached, first/last name set,
   and a password that has already passed JUVAl's Control 6 validator
3. Operator delivers the secret to the person out of band, once
4. Person adds it to their authenticator app and completes one login
5. Operator confirms the login succeeded and destroys their copy of the secret
```

Properties this preserves:

- **The tenant MFA policy is never relaxed.** Not for a minute, not for one user.
- **Control 6 is enforced before FusionAuth sees the password** — step 2 runs
  the password through `application/password_provisioning.py`, which cannot
  reach an identity adapter without passing `domain/password_policy.py` first.
- **No standing API key is created.** ADR-035 Condition 1 holds.
- **`passwordChangeRequired` is never set** — see §5.

## 4. The manual/automated boundary, stated honestly

**This is a manual operator procedure, and it stays manual.**

Automating it would need a FusionAuth credential carrying `POST /api/user` and
`POST /api/user/two-factor`. ADR-032 scopes such a credential to a narrow,
approved, temporary task, and ADR-035 Condition 1 forbids it as a standing
grant. For an internal organisation onboarding a handful of people, a standing
user-creation credential is a permanent, high-value target bought to save a
few minutes of work a few times a year. That trade is not worth taking.

| | Manual (approved) | Automated (rejected for now) |
|---|---|---|
| Privilege required | Console access, one named operator | Standing API key with user-create + two-factor grants |
| ADR-032 posture | Compatible | Requires an exception |
| When to revisit | If onboarding volume ever makes it a real cost | Needs its own ADR, with a lifecycle-scoped key |

If volume ever justifies automation, the path is a **lifecycle-scoped,
short-lived key issued for one provisioning session and revoked after**, never
a permanent one — the pattern ADR-032 already establishes.

## 5. Two standing rules that fall out of this

1. **JUVAl never sets `passwordChangeRequired`.** Completing that state needs
   the hosted `/password/change` page, which ADR-035 Condition 2 keeps
   unpublished. The operator sets a compliant password directly instead. This
   is also recorded in `deploy/fusionauth/nginx-fusionauth-public.conf`.
2. **The operator's copy of a TOTP secret is destroyed after step 5.** It is a
   credential for as long as it exists; nothing in JUVAl stores it, and no
   JUVAl code ever sees it.

## 6. What is not yet measured

- Whether the FusionAuth admin console enforces the tenant password rules
  (`NOT_TESTED`, lab §9.3) — the same gap ADR-035 records as its residual.
- Why `POST /api/user/two-factor/{userId}` returned `421` in every lab
  configuration. Recorded as an observation, **not** a defect claim.
