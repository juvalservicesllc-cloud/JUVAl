# ADR-021: Identity Provider and Authentication Boundary (Proposed)

- Estado: **Propuesta** — no aprobada.
- Fecha: 2026-08-17.
- Alcance: diseño de identidad humana, autorización backend y evidencia para
  RF-03/RF-04. No implementa autenticación ni crea cuentas o secretos.

## Contexto

Amazon rechazó el Developer Profile de JUVAl (`REJECTED_REMEDIATION_REQUIRED`)
por controles de MFA/password y acceso por función. JUVAl tiene una PWA
prevista, un backend FastAPI y no tiene AuthN/AuthZ/MFA implementados. Amazon
exige 12 caracteres, caracteres especiales, MFA, expiración máxima de 365 días,
rotación anual y least privilege; no se puede responder YES sin evidencia.

## Alternativas

1. **Clerk (candidato existente):** MFA, sesiones y Organizations/RBAC están
   documentados; los requisitos exactos de contraseña, expiración anual,
   auditoría y plan requieren verificación. Integración PWA/FastAPI es viable,
   pero los checks de permisos deben ejecutarse en backend.
2. **Amazon Cognito (alternativa gestionada):** candidato razonable para MFA,
   grupos/políticas y federación; configuración, auditoría y cumplimiento de
   las reglas exactas de password deben verificarse antes de elegirlo.
3. **Microsoft Entra External ID (alternativa gestionada):** candidato para
   MFA, lifecycle, roles y auditoría; disponibilidad, precio y cobertura exacta
   de password policy requieren verificación.

No se comparan más proveedores hasta que una decisión real lo requiera.

## Decisión candidata

See **"Control ownership reevaluation (2026-08-17)"** near the end of this
document for the authoritative conclusion. The paragraphs immediately below
are preserved as historical record of the first comparison pass, which the
user later identified as methodologically flawed (it asked "does the IdP have
a native feature for every Amazon item," rather than "who legitimately owns
each control"). Do not treat the paragraphs below as superseding the later
section; the later section supersedes these.

**PENDING — ningún proveedor seleccionado.** La documentación oficial actual
no permite declarar que Clerk, Cognito o Entra External ID satisfacen todos los
requisitos RF-03 sin una brecha crítica:

- Clerk documenta MFA, sesiones y roles, pero no una configuración verificable
  para 12 caracteres, caracteres especiales, expiración máxima de 365 días y
  rotación anual de contraseñas.
- Cognito permite configurar longitud y símbolos y tiene MFA obligatorio, pero
  su expiración documentada de 365 días es para contraseñas temporales; las
  contraseñas locales no expiran automáticamente. La rotación anual humana no
  queda satisfecha nativamente.
- Entra External ID documenta MFA y tokens OIDC, pero su política documentada
  exige mínimo 8 caracteres y complejidad de 3 de 4 categorías; no demuestra
  el mínimo Amazon de 12 caracteres ni rotación anual configurable.

No se elige «el menos malo» y no se inventará autenticación propia para
ocultar estas brechas. Por tanto `IDENTITY SECURITY GATE = BLOCKED`.

## Investigación comparativa verificada (2026-08-17)

Valores permitidos: `YES — VERIFIED`, `NO — VERIFIED`,
`NEEDS_VERIFICATION`. Una capacidad del proveedor no es evidencia de la
configuración de JUVAl.

| RF-03 requisito | Clerk | Amazon Cognito | Entra External ID | Evidencia oficial / dependencia |
|---|---|---|---|---|
| Mínimo 12 caracteres | NEEDS_VERIFICATION | YES — VERIFIED (mínimo configurable hasta 99) | NO — VERIFIED (política documenta mínimo 8) | [Clerk password rules](https://clerk.com/docs/guides/secure/password-protection-and-rules); [Cognito password policy](https://docs.aws.amazon.com/cognito/latest/developerguide/managing-users-passwords.html); [Entra password policy](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-password-ban-bad-combined-policy) |
| Caracteres especiales | NEEDS_VERIFICATION | YES — VERIFIED (`RequireSymbols`) | YES — VERIFIED (symbols dentro de 3/4 categorías), pero no basta para el mínimo de 12 | Mismas fuentes |
| MFA obligatorio | YES — VERIFIED (Require MFA) | YES — VERIFIED (Require MFA; tier/configuración a verificar) | YES — VERIFIED (Conditional Access) | [Clerk MFA](https://clerk.com/docs/guides/configure/session-tasks); [Cognito Essentials](https://docs.aws.amazon.com/cognito/latest/developerguide/feature-plans-features-essentials.html); [Entra External ID MFA](https://learn.microsoft.com/en-us/entra/external-id/customers/concept-multifactor-authentication-customers) |
| Expiración máxima 365 días | NEEDS_VERIFICATION | NO — VERIFIED para passwords locales (solo temporary password hasta 365 días) | NEEDS_VERIFICATION | [Cognito password policy](https://docs.aws.amazon.com/cognito/latest/developerguide/managing-users-passwords.html); [Entra password FAQ](https://learn.microsoft.com/en-us/entra/identity/authentication/tutorial-password-policy-overview-frequently-asked-questions) |
| Rotación anual | NEEDS_VERIFICATION | NO — VERIFIED nativamente | NEEDS_VERIFICATION | Fuentes oficiales anteriores; no se acepta custom workaround como cumplimiento verificado |

### RF-04 y plataforma

| Capacidad | Clerk | Cognito | Entra External ID |
|---|---|---|---|
| Roles/permissions/orgs | YES — VERIFIED; custom permissions | YES — VERIFIED; groups/scopes, configuración requerida | YES — VERIFIED; app roles/groups, configuración requerida |
| Claims legibles por backend | YES — VERIFIED, claims/configuración deben validarse | YES — VERIFIED, JWT claims | YES — VERIFIED, signed JWT claims |
| Revocación usuario/sesión | YES — VERIFIED, configuración/API | YES — VERIFIED, refresh-token revocation | YES — VERIFIED, lifecycle/session controls |
| Least privilege backend | YES — VERIFIED como capacidad, enforcement JUVAl requerido | YES — VERIFIED como capacidad, enforcement JUVAl requerido | YES — VERIFIED como capacidad, enforcement JUVAl requerido |
| Auditoría/access review | NEEDS_VERIFICATION (tenant/plan/export) | NEEDS_VERIFICATION (AWS audit/config evidence) | NEEDS_VERIFICATION (tenant/plan/log export) |

FastAPI puede validar localmente JWT firmados usando issuer, audience,
expiración y JWKS en las tres alternativas; no debe confiar en claims sin
validación ni en el frontend. Entra documenta OIDC issuer/JWKS y tokens JWT
firmados ([Microsoft token validation](https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens));
los modelos equivalentes de Clerk/Cognito requieren configuración de issuer,
audience y JWKS del tenant. La revocación inmediata puede requerir eventos,
short-lived tokens o introspección adicional; debe probarse por proveedor.

### MFA, planes y costes

- Clerk: MFA y sesión pueden depender de configuración y plan; `PLAN
  DEPENDENT / NEEDS COMMERCIAL VERIFICATION` para producción.
- Cognito: MFA avanzada/email y password history dependen de Essentials/Plus;
  `PLAN DEPENDENT / NEEDS COMMERCIAL VERIFICATION`. El coste real no se
  estima aquí.
- Entra External ID: Conditional Access, auditoría y capacidades avanzadas
  dependen de tenant/licencia; `PLAN DEPENDENT / NEEDS COMMERCIAL
  VERIFICATION`.

No se declara ningún precio como FREE o PAID sin una cotización/plan oficial
verificado para JUVAl.

## Boundary y enforcement

```text
User → PWA → IdP → token/session → FastAPI → backend authorization → resources
```

- La PWA inicia login y presenta estado; nunca decide autorización final.
- FastAPI valida firma, issuer, audience, expiración y revocación aplicable.
- FastAPI autoriza cada operación y recurso según role/permission y tenant.
- El IdP es source of truth para identidad, MFA, sesión y membresía.
- JUVAl mantiene el inventario de permisos, revisiones trimestrales y evidencia
  de revocación; el backend impide el bypass directo del API.
- Workers, SP-API, bases de datos y deployment usan identidades de servicio,
  nunca cuentas humanas.

## RBAC mínimo propuesto

Los nombres siguen pendientes; el modelo mínimo deriva de capacidades reales:

| Permiso | Enforcement backend |
|---|---|
| upload supplier catalog | endpoint de upload |
| view run results/history | handlers de lectura por usuario/organización |
| view Amazon-enriched data | endpoint/query con permiso explícito |
| start enrichment | comando/job endpoint |
| download/export | endpoint de descarga/exportación |
| modify configuration | endpoint de configuración |
| manage integrations/secrets | servicio administrativo separado; nunca devuelve secretos |
| manage users/security settings | administración IdP/auditoría |

Se prefieren dos perfiles funcionales como punto de partida solo si la
revisión confirma que cubren estas capacidades sin privilegio excesivo.

## MFA, password y lifecycle

MFA debe ser obligatorio para usuarios y administradores. Las reglas de
password humanas deben probarse en el tenant real; MFA no sustituye ninguna
regla indicada por Amazon. Alta, cambio de función, baja y revocación deben
producir registros fechados. La revisión de acceso será trimestral y la baja
de acceso se validará dentro de 24 horas.

## Evidence model

La evidencia futura debe incluir export de configuración del IdP, MFA
enforced, cuenta de prueba, pruebas backend positivas/negativas, invalidación
de sesión, revocación, revisión de accesos y registro de rotación. Nunca debe
contener passwords, tokens, client secrets ni claves privadas.

## Gaps y efecto en reapplication

- RF-03: **BLOCKED** — Clerk no está verificado para las reglas cuantitativas
  completas, especialmente expiración/rotación anual.
- RF-04: **BLOCKED** — RBAC backend y revisiones de acceso no existen.
- La elección de IdP, plan y configuración real requiere aprobación y acción
  manual del usuario.

Hasta cerrar esos gaps con evidencia, `IDENTITY SECURITY GATE = BLOCKED` y no
se actualiza el Developer Profile.

## RF-03 scope clarification blocker

Amazon's official guidance uses broad language: MFA applies to “all accounts”
and access controls apply to personnel and services; the credential guidance
defines credentials to include passwords, API keys, encryption keys and SP-API
client credentials/tokens. It separately requires encryption and annual
rotation for API keys/associated credentials. This establishes that service
credentials are in scope for credential protection, but it does not
unambiguously identify whether password composition/expiration applies to
JUVAl application end users, personnel with Amazon Information access,
provider administrators, or every category simultaneously.

| Requirement | Official wording/scope evidence | Scope conclusion |
|---|---|---|
| 12-character password, complexity, max 365 days | Key Security Control Guidance, “Password and authentication”; “all accounts” / user accounts | `SCOPE NEEDS AMAZON CLARIFICATION` |
| MFA | Same section: MFA for “all accounts”; credential guidance: MFA for all user accounts | Broad account scope is clear; exact JUVAl categories remain `NEEDS_VERIFICATION` |
| Annual rotation | Guidance: API keys and associated credentials annually; password lifecycle separately | Programmatic/API rotation is distinct; human-password scope remains `NEEDS_VERIFICATION` |
| Service/API credentials | Credential guidance explicitly includes API keys, encryption keys and SP-API client credentials/tokens | Credential protection is in scope, but human password composition is not automatically extended to secrets |

Sources, verified 2026-08-17: [Key Security Control Guidance](https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration)
and [Safeguarding Sensitive Credentials](https://developer-docs.amazon.com/sp-api/docs/safeguarding-sensitive-credentials).
These are official implementation guidance; the DPP remains controlling policy.
Because the reviewer question is more specific than the public identity
categories, `RF-03 IDENTITY SCOPE = NEEDS AMAZON CLARIFICATION`.

### Proposed clarification to Amazon (do not send yet)

> We are remediating the security findings identified in our Developer Profile assessment and want to apply the controls to the correct scope. For the password and MFA control, could you please clarify which identities must be subject to the stated requirements (12-character minimum with special characters, MFA, maximum 365-day expiration, and annual rotation): personnel or users who can access Amazon Information, application end users, administrative/provider accounts, service accounts, or another category defined by Amazon? We are not seeking an exception or reduction of obligations; we want to implement the control for every identity category Amazon requires. We will not include credentials, tokens, or other sensitive information in this clarification.

Until Amazon clarifies this scope, no identity provider is selected, ADR-021
remains Proposed, and `IDENTITY SECURITY GATE = BLOCKED`.

`AMAZON_RF03_SCOPE_CLARIFICATION = PENDING_EXTERNAL_ACTION`
`IDENTITY WORK = WAITING_EXTERNAL_CLARIFICATION`

## RF-03 boundary update and IdP reevaluation

`PREVIOUS STATE: RF-03 IDENTITY SCOPE = NEEDS AMAZON CLARIFICATION`

Subsequent official Amazon credential guidance separates human/user password
controls from API/programmatic credential controls. The architectural
boundary is therefore documented as:

`RF-03 HUMAN VS PROGRAMMATIC CONTROL BOUNDARY = DOCUMENTATION RESOLVED / IMPLEMENTATION PENDING`
`AMAZON_RF03_SCOPE_CLARIFICATION = NOT REQUIRED FOR ARCHITECTURAL PROGRESS`

This is not compliance evidence. Human identity implementation and evidence
remain pending, and `IDENTITY SECURITY GATE = BLOCKED`.

The three candidates were re-evaluated against unique IDs, no shared accounts,
12-character passwords, mixed case/numbers/special characters, name exclusion,
history of 10, one-day minimum age, 365-day maximum age, mandatory MFA,
lockout at or below 10 attempts, revocation, disablement, quarterly review
evidence and backend claims. None satisfies the complete baseline without
unresolved gaps or external controls. Decision remains `PENDING`; no provider
is selected.

## Control ownership reevaluation (2026-08-17)

The prior comparison (sections above) asked "does the IdP have a native
feature for every Amazon item." The user directed that this methodology not
be repeated: Amazon requires controls over the *security system*, not
necessarily controls that must all be IdP features. This section instead
determines, per control, who is the legitimate owner — IdP, FastAPI backend,
organizational procedure, infrastructure, or service-credential lifecycle —
before asking which providers can satisfy the resulting IdP-owned subset.

Ownership classes used below: `IDP_NATIVE_REQUIRED`, `IDP_OR_MANAGED_AUTH_REQUIRED`,
`BACKEND_ENFORCED`, `ORGANIZATIONAL_PROCEDURAL`, `INFRASTRUCTURE_CONTROL`,
`SERVICE_CREDENTIAL_CONTROL`, `MULTI_LAYER`. `EXTERNAL_CONTROL_REQUIRED` is
not used as a catch-all; every external control below names exactly what the
external party/system must do.

### Control ownership matrix (25 controls)

| # | Amazon requirement | Control owner | Why | What the IdP must provide | What JUVAl (FastAPI) must provide | What the organization must provide | Evidence | Source |
|---|---|---|---|---|---|---|---|---|
| 1 | Unique user IDs | `IDP_OR_MANAGED_AUTH_REQUIRED` | Identity issuance is inherent to whatever system authenticates the user; duplicating it in FastAPI would mean building a parallel identity store, which is the custom-auth outcome the project must not build. | Non-reusable unique identifier (`sub`) per human, enforced at account creation. | Use the IdP's `sub` claim as the sole key for authorization records; never mint a parallel identity. | Standard onboarding discipline (one person, one enrollment). | IdP configuration export; backend schema showing `sub` as the identity FK. | DPP §§1.2–1.4 (access controls); Key Security Control Guidance "Password and authentication." |
| 2 | No shared/generic accounts | `MULTI_LAYER` (`IDP_OR_MANAGED_AUTH_REQUIRED` + `ORGANIZATIONAL_PROCEDURAL`) | The IdP can block duplicate emails, but nothing technical stops two humans from sharing one login's credentials — that is a personnel-discipline failure no IdP feature detects by itself. | One-email-one-account enforcement; per-user MFA enrollment. | None (no custom account logic). | Written no-sharing policy; access review checks for signs of shared use. | Policy document; access-review record with no shared-account findings. | DPP §1.2 (unique identities, implicit prohibition on shared accounts). |
| 3 | Password ≥12 characters | `IDP_NATIVE_REQUIRED` | JUVAl must not build a password engine; only the system that stores/validates the password can enforce composition. If the IdP's policy engine cannot express the rule, there is no legitimate JUVAl-side substitute. | Configurable minimum-length policy ≥12, enforceable tenant-wide. | Nothing (must not build). Verification only. | Apply and keep the tenant configuration current. | Dated IdP password-policy export. | Key Security Control Guidance, "Establish password complexity requirements: minimum 12 characters…" (verified 2026-08-17); DPP §§1.2–1.4.2. |
| 4 | Uppercase required | `IDP_NATIVE_REQUIRED` | Same as #3. | Configurable uppercase requirement. | Nothing. | Apply configuration. | IdP policy export. | Same source as #3. |
| 5 | Lowercase required | `IDP_NATIVE_REQUIRED` | Same as #3. | Configurable lowercase requirement. | Nothing. | Apply configuration. | IdP policy export. | Same source as #3. |
| 6 | Number required | `IDP_NATIVE_REQUIRED` | Same as #3. | Configurable numeric requirement. | Nothing. | Apply configuration. | IdP policy export. | Same source as #3. |
| 7 | Special character required | `IDP_NATIVE_REQUIRED` | Same as #3. | Configurable symbol requirement. | Nothing. | Apply configuration. | IdP policy export. | Same source as #3. |
| 8 | Username/name exclusion | `IDP_NATIVE_REQUIRED` | Same as #3 — this is a password-content rule, not an authorization rule. | Reject passwords containing the account's name/username. | Nothing. | Apply configuration if the tenant supports it; otherwise register as a native gap. | IdP policy export or documented absence. | Key Security Control Guidance, "…must not include any part of the user's name" (verified 2026-08-17). |
| 9 | Password history 10 | `IDP_NATIVE_REQUIRED` | Same as #3 — history tracking requires storing prior password hashes, which only the password-owning system may do. | Reject reuse of the last 10 passwords. | Nothing. | Apply configuration. | IdP policy export. | Key Security Control Guidance, "password history to prevent reuse of the last 10 passwords" (verified 2026-08-17). |
| 10 | Minimum password age 1 day | `IDP_NATIVE_REQUIRED` | Prevents rapid history-cycling to defeat #9; only the password engine can enforce a change cadence. | Configurable minimum age. | Nothing. | Apply configuration. | IdP policy export. | Key Security Control Guidance (verified 2026-08-17). |
| 11 | Maximum password age 365 days | `IDP_NATIVE_REQUIRED`, in practice `MULTI_LAYER` where no native automatic toggle exists | Same reasoning as #3; where the provider lacks a native automatic expiration for a user's own permanent password, the only legitimate closing mechanism is a scheduled JUVAl-triggered call to the provider's own official admin API — never a JUVAl-built expiration engine. | Either a native expiration toggle, or an official admin API that can force a credential reset. | If no native toggle exists: a scheduled service job that calls the provider's documented admin API (infrastructure orchestration, not password logic). | Approve and monitor the scheduled job; treat a missed run as an incident. | IdP policy export, or scheduled-job configuration/run logs plus provider API documentation reference. | Key Security Control Guidance, "maximum password expiration period of 365 days" (verified 2026-08-17); see Cognito finding below. |
| 12 | Mandatory MFA | `IDP_NATIVE_REQUIRED` | MFA enrollment/verification is inherent to the authentication ceremony; FastAPI can only check that MFA occurred (via a claim), never perform MFA itself without becoming an identity provider. | Enforced MFA at login for every account, including administrators. | Verify an MFA-occurred claim exists before treating a session as fully authenticated where policy requires it. | Enroll all personnel; no MFA-exempt accounts. | IdP MFA-enforcement configuration export; enrollment records. | Key Security Control Guidance, "Deploy Multifactor Authentication (MFA) for all accounts" (verified 2026-08-17); Safeguarding Sensitive Credentials, "Require MFA for all user accounts" (verified 2026-08-17). |
| 13 | Lockout ≤10 failed attempts | `IDP_NATIVE_REQUIRED` | Brute-force throttling on the credential-check step belongs to whoever performs that check. | Native lockout at or before the 10th consecutive failure. | Nothing. | Apply configuration if adjustable. | IdP lockout-policy export; failed-login test. | Amazon guidance implies brute-force protection under access controls; provider lockout defaults documented per-provider below. |
| 14 | Session expiration | `MULTI_LAYER` (`IDP_OR_MANAGED_AUTH_REQUIRED` + `BACKEND_ENFORCED`) | The IdP issues the token's `exp`; FastAPI must independently reject expired tokens rather than trusting the frontend — defense in depth against a compromised or stale client. | Time-bounded tokens/sessions with a documented lifetime. | Server-side `exp`/issuer/audience validation on every request; no trust in client-reported expiry. | None beyond policy approval of the lifetime chosen. | IdP session-policy export; backend token-validation test. | ADR-021 "Boundary y enforcement" (this document). |
| 15 | Session revocation | `MULTI_LAYER` | The IdP must support invalidating refresh tokens/sessions; FastAPI must use short-lived access tokens plus a revocation check (introspection or deny-list) so a revoked session cannot keep working until natural expiry. | Revocation/introspection API or refresh-token invalidation. | Short-lived access tokens; revocation check wired into the authorization path. | None beyond incident-triggered revocation requests. | Revocation test (revoke → next request denied); IdP API documentation reference. | Same as #14. |
| 16 | User disablement | `MULTI_LAYER` | Disabling at the IdP prevents new logins; FastAPI must independently stop honoring that user's still-valid tokens (ties to #15) or a disabled user keeps working until token expiry. | Disable/delete-user capability. | Enforce disablement against live sessions, not only new logins. | Trigger disablement via the offboarding procedure (#17). | Disablement test; backend rejection-of-disabled-user test. | Same as #14. |
| 17 | Departed-user revocation ≤24h | `ORGANIZATIONAL_PROCEDURAL`, executed via `MULTI_LAYER` (#15/#16) | Amazon requires evidence of a timed human process, not a technical feature; no IdP button enforces "within 24 hours" on its own — someone must trigger the action. | Fast disablement API/UI so the 24-hour window is technically achievable. | Execute the technical disablement/revocation promptly once triggered. | Documented offboarding trigger (HR/manager notifies within the window) and a dated revocation record. | Offboarding record with timestamps proving the ≤24h gap. | DPP §1.2.3 (access removal within 24 hours), per AC-07/RF-04. |
| 18 | Quarterly access review | `ORGANIZATIONAL_PROCEDURAL` | Amazon requires evidence of a recurring human review, not an automatic feature; none of the three candidates ships a "quarterly review" button. | Export of current users/roles/last-login to support the review. | Backend role/permission inventory to review against actual grants. | Perform and document the review every quarter, on a fixed cadence, with a named reviewer. | Dated access-review record referencing the IdP export and backend inventory. | DPP §1.2.2 (quarterly access review), per AC-07. |
| 19 | Roles | `MULTI_LAYER` (`IDP_OR_MANAGED_AUTH_REQUIRED` + `BACKEND_ENFORCED`) | Role *definitions* (operator, integration administrator, identity administrator — see §"RBAC mínimo propuesto") are JUVAl business concepts the IdP has no knowledge of; the IdP is only the claims carrier. | Custom role/claim storage and issuance in the token. | Define role semantics; map claims to internal role identifiers. | Approve the role taxonomy. | Role-claim configuration export; backend role-mapping test. | ADR-021 "RBAC mínimo propuesto" (this document). |
| 20 | Permissions | `BACKEND_ENFORCED` | The IdP can optionally carry permission claims, but the authorization decision for a specific resource (a `SourcingRecord`, an `ExecutionRun`) is domain-specific logic the IdP cannot know. | Optional custom-claim carrier only. | Per-resource authorization checks. | None. | Backend authorization test suite (positive and negative). | This document's boundary section. |
| 21 | Least privilege | `BACKEND_ENFORCED` + `ORGANIZATIONAL_PROCEDURAL` | A default-deny authorization design (backend) combined with disciplined grant practices at role-assignment time (organization) — no IdP feature guarantees least privilege by itself. | Nothing beyond role/claim carrying. | Default-deny authorization; explicit grants only. | Grant discipline; review flags over-broad roles. | Negative-authorization test; access-review record. | DPP §1.2 (least privilege), per AC-07. |
| 22 | Backend authorization enforcement | `BACKEND_ENFORCED` | Explicitly FastAPI's responsibility per the user's own instruction. | Nothing. | Every protected endpoint checks role/permission server-side; never trust a frontend-only gate. | None. | Backend authorization test suite. | This document's boundary section. |
| 23 | Audit trail/evidence | `MULTI_LAYER` | The IdP emits authentication events (login, MFA, password reset, admin actions); FastAPI emits authorization/business-action events. Neither alone is a complete record of Amazon Information access. | Authentication/admin event log, exportable. | Authorization/business-action audit log tied to the same user identifier. | Retention and access-control policy over both logs. | Sample exported IdP event log; sample backend audit log; both keyed by the same `sub`. | DPP §2.6 (security logs), per AC-11A. |
| 24 | Service-account review | `SERVICE_CREDENTIAL_CONTROL` + `ORGANIZATIONAL_PROCEDURAL` | Railway/Supabase/GitHub/SP-API machine credentials are not human IdP identities at all; they live in infrastructure/secret-manager inventories, never the human IdP's user list. | Not applicable — out of IdP scope by design. | Maintain a service-credential inventory separate from human accounts. | Review the inventory on the same cadence as human access review. | Dated service-credential inventory and review record. | DPP §1.4.2/§2.8 (credential/vendor review), per AC-08/AC-14B. |
| 25 | Programmatic credential rotation | `SERVICE_CREDENTIAL_CONTROL` | API keys, SP-API tokens and DB credentials rotate through a secret manager/infrastructure process, structurally separate from human password rotation (#11) — conflating the two would blur the "four identities" boundary this ADR already keeps separate. | Not applicable. | N/A directly, but the backend must never log or persist these values in plaintext. | Rotate annually (or on compromise) via the secret-management process already described in `SP_API_REGISTRATION_REMEDIATION.md` §9.4. | Rotation timestamp record; redaction test showing no secret in logs. | Safeguarding Sensitive Credentials, "rotate API keys and associated credentials every year" (verified 2026-08-17), per AC-08/RF-03. |

### Hard IdP requirements

Derived from the matrix: a requirement is a **HARD IdP requirement** only if
no other layer (backend/organization/infrastructure) can legitimately absorb
it without JUVAl building forbidden custom authentication or materially
degrading security. That excludes items whose IdP ownership is real but
non-discriminating (every mainstream IdP trivially satisfies unique IDs,
session issuance, and disablement — items 1, 14, 16 — so they do not drive
provider selection even though they are IdP-owned).

`HARD IdP REQUIREMENTS = { 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 }` — i.e., the
complete password-composition set (≥12 chars, uppercase, lowercase, number,
special character, name exclusion, history 10, minimum age 1 day, maximum
age 365 days) plus mandatory MFA and lockout ≤10 attempts. These are the only
items where a documented native ceiling in one provider and not another can
actually change the recommendation.

`ARE ALL AMAZON CONTROLS REQUIRED TO BE IdP-NATIVE? NO` — only 11 of the 25
are. The rest are backend-, organization-, infrastructure-, or
service-credential-owned, or split across layers.

### Passwordless/federated identity finding

Investigated: whether Amazon's baseline can be satisfied via
passwordless/federated identity + mandatory MFA, making the password
composition/expiration controls moot because no password would exist.

Official Amazon sources (Key Security Control Guidance and Safeguarding
Sensitive Credentials, both re-fetched and quoted verbatim 2026-08-17) state
password composition, history, minimum/maximum age, and MFA as flat
requirements for "all accounts" / "all user accounts." Neither page contains
any reference to passwordless authentication, passkeys, FIDO2, SSO, or
federated identity as an alternative or exempting mechanism. Absence of a
prohibition is not evidence of an affirmative exemption.

Provider-side evidence gathered:

- **Microsoft Entra External ID** officially documents passkey (FIDO2)
  sign-in as satisfying MFA and usable as a user's only sign-in method once
  registered — but registration is documented as requiring an existing
  email+password or username+password local account first ("customers
  currently need an email + password or username + password account to
  register the passkey initially" — [Sign in with passkeys in Microsoft Entra
  External ID](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-sign-in-with-passkey),
  verified 2026-08-17). So passwordless sign-in does not eliminate Entra's
  underlying password policy — it adds a phishing-resistant sign-in option on
  top of a password floor that, per the existing table, is still natively
  capped at 8 characters with 3-of-4 complexity, below Amazon's 12-character
  requirement.
- **Amazon Cognito** publicly announced passwordless authentication
  (passkeys/WebAuthn, email OTP, SMS OTP) in November 2024, available via the
  choice-based `ALLOW_USER_AUTH` flow on the Essentials/Plus feature plan.
  Whether a Cognito user pool can be provisioned so that a user's account
  *never has a password attribute at all* (as opposed to passwordless being
  one available sign-in factor alongside a still-existing password) could not
  be confirmed against a primary AWS documentation page in this session (the
  fetched page did not render structured content); this remains open.
- **Clerk** documents passkeys as a supported sign-in method but its own
  documentation for this flow does not state whether password sign-in can be
  disabled tenant-wide.

`PASSWORDLESS_FEDERATED_ELIMINATES_PASSWORD_CONTROLS = NEEDS_VERIFICATION`.
This finding does not change the recommendation below, which does not rely
on passwordless elimination for any candidate.

### Final provider re-evaluation (ownership-based question)

New question per candidate: *can this provider satisfy all 11 HARD IdP
requirements while the remaining 14 controls are legitimately owned by
FastAPI/organization/infrastructure/service-credential processes?* — not
"does it have a native feature for every Amazon item."

| HARD requirement | Clerk | Amazon Cognito | Microsoft Entra External ID |
|---|---|---|---|
| ≥12 characters | NEEDS_VERIFICATION (no published tenant-setting confirmation) | CONFIGURABLE_VERIFIED (configurable up to 99) | **NOT_SUPPORTED** — native ceiling documented at 8 characters |
| Upper/lower/number/special | NEEDS_VERIFICATION | CONFIGURABLE_VERIFIED (`RequireUppercase`/`RequireLowercase`/`RequireNumbers`/`RequireSymbols`, each independently toggled — [Adding user pool password requirements](https://docs.aws.amazon.com/cognito/latest/developerguide/managing-users-passwords.html), verified 2026-08-17) | CONFIGURABLE_VERIFIED but only 3-of-4 categories, not all four |
| Name/username exclusion | NEEDS_VERIFICATION | **NOT_SUPPORTED** (upgraded from NEEDS_VERIFICATION 2026-08-17) — the official "Adding user pool password requirements" page exhaustively lists every configurable password-policy control (length, character-type requirements, temporary-password validity, previous-password reuse); no username/name-exclusion rule exists anywhere in it. | NEEDS_VERIFICATION |
| History 10 | NEEDS_VERIFICATION | CONFIGURABLE_VERIFIED — re-confirmed 2026-08-17: "prevent a user from resetting their password to a new password that matches their current password or any of up to 23 additional previous passwords, for a maximum total of 24" (Essentials/Plus tier). 24 ≥ the required 10. | **NOT_SUPPORTED** — only last-password comparison documented |
| Minimum age 1 day | NEEDS_VERIFICATION | **NOT_SUPPORTED** (upgraded from NEEDS_VERIFICATION 2026-08-17) — same exhaustive official page has no minimum-password-age setting; "Temporary passwords set by administrators expire in" governs admin-issued temporary-password validity, not a minimum age before a user may change their own password again. | NEEDS_VERIFICATION |
| Maximum age 365 days | NEEDS_VERIFICATION | **NOT_SUPPORTED natively**, confirmed verbatim 2026-08-17: "Passwords for local users in Amazon Cognito user pools don't automatically expire." Resolved via `MANAGED_CONTROL_VERIFIED` — see "PASSWORD_MAX_AGE_CONTROL design" below. This is AWS's own documented best practice for this exact gap, not a JUVAl-invented workaround. | CONFIGURABLE_VERIFIED, tenant policy required |
| Mandatory MFA | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED |
| Lockout ≤10 | CONFIGURABLE_VERIFIED (default 10) | NATIVE_VERIFIED (begins at 5 — stricter than required) | NATIVE_VERIFIED (default 10) |

Result: **Entra External ID is eliminated** — two HARD requirements
(12-character minimum, password history 10) have a *confirmed, documented
native ceiling*, not merely unverified configuration, and passkeys do not
remove the underlying weak-password floor (see passwordless finding above).
Blocking HARD requirements: #3 (composition) and #9 (history).

**Clerk remains unresolved** — no confirmed ceiling exists (nothing is
`NOT_SUPPORTED`), but six of eleven HARD requirements are `NEEDS_VERIFICATION`
for lack of a published, tenant-specific setting. Clerk cannot be recommended
or eliminated on current evidence; closing this requires provisioning a real
test tenant and exporting its password-policy configuration — an
implementation action requiring approval, not performed in this session.

**Amazon Cognito: the 2026-08-17 maximum-age investigation resolved one gap
and surfaced two more.** Reading Cognito's complete official password-policy
page (required to properly investigate the max-age question) showed it is
*exhaustive* about every configurable password-policy control — which means
its silence on username/name-exclusion and minimum password age is now
better evidence of a genuine native ceiling than the earlier
`NEEDS_VERIFICATION` status implied. Net result for Cognito's 11 HARD items:
7 `CONFIGURABLE_VERIFIED`/`NATIVE_VERIFIED` natively (12-char length, all
four character-type rules, history-10, MFA, lockout), 1 resolved by an
AWS-documented managed control (maximum age — see below), and **2 confirmed
native gaps newly identified this session** (name/username exclusion,
minimum age 1 day) that were not the target of this investigation and are
**not yet resolved by any mechanism**, native or managed. These two do not
have the same kind of officially-documented workaround that closed the
maximum-age gap; none was searched for in this session because it was
explicitly scoped to maximum-age only.

`ARE HARD IdP REQUIREMENTS NOW IDENTIFIED? YES.`
`DOES AT LEAST ONE MANAGED IdP SATISFY ALL HARD IdP REQUIREMENTS BY DESIGN? NO`
— Cognito's maximum-age gap is now resolved by design (see
`PASSWORD_MAX_AGE_CONTROL` below), but name-exclusion and minimum-age remain
open, unresolved native gaps discovered as a byproduct of this session's more
thorough reading of Cognito's official documentation. Declaring "all HARD
requirements satisfied" now would repeat the exact mistake this ADR is trying
not to make: treating a partial, favorable-sounding result as compliance.
`RECOMMENDED IdP (best-positioned candidate, not a final selection): AMAZON COGNITO.`
`WHY STILL COGNITO OVER THE ALTERNATIVES: Entra has two confirmed ceilings with no
official workaround found; Clerk has zero confirmed ceilings but zero confirmed
passes either. Cognito has the most HARD items resolved with primary-source
evidence, including the hardest one (maximum age) via an AWS-documented pattern.`
`WHY ADR-021 IS NOT YET READY: two newly-surfaced native gaps (name-exclusion,
minimum age) need the same kind of focused investigation just completed for
maximum age before Cognito's HARD-requirement set can honestly be called closed.`

**This paragraph is superseded — see "Final two-gap investigation and Cognito
rejection (2026-08-17)" below**, which resolved these two specific gaps with
the same rigor applied to maximum age and reached a different conclusion for
one of them. Do not read this paragraph as the current recommendation.

`Decision (candidate, not accepted, later rejected — see below): Amazon Cognito`
`Status: PROPOSED`

## Final two-gap investigation and Cognito rejection (2026-08-17)

Scope, as directed: only GAP A (minimum password age = 1 day) and GAP B
(password must not contain username/name). Clerk, Entra, SP-API Guard, the
general RF-03 scope question, maximum password age, and the human/programmatic
credential boundary are **not** reinvestigated here; their prior conclusions
stand unchanged.

### GAP A: minimum password age = 1 day

**AMAZON_REQUIREMENT** (verified requirement, re-read, no favorable
interpretation) = "Configure password lifecycle settings with a minimum
password age of 1 day…" — Key Security Control Guidance, "Password and
authentication," verified 2026-08-17. **SOURCE** =
`developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration`.
**VERIFIED_AT** = 2026-08-17.

**Intended security outcome — separated from inference**: the guidance states
only the numeric rule, bundled in the same sentence as the 365-day maximum,
with no accompanying rationale. `SECURITY_INTERPRETATION / INFERENCE` (not
Amazon-documented): the common industry rationale for a minimum password age
is to prevent a user from cycling through several passwords in quick
succession to defeat a password-history/reuse restriction and return to a
familiar or already-compromised password. **Amazon does not state this
rationale anywhere in the source checked.** This distinction matters for
classification below: without a stated mechanism requirement, an
outcome-equivalent control could in principle satisfy the letter of the rule,
but that is a JUVAl interpretation, not a documented Amazon allowance.

**Cognito native capability**: **NO** minimum-password-age setting exists
anywhere in the password-policy configuration (re-confirmed against the same
exhaustive official password-policy page already used for the max-age
investigation — no such control is listed).

**Flow coverage — the decisive evidence.** AWS's official "Connecting API
operations to Lambda triggers" table (the exhaustive, authoritative mapping
of every API operation to every Lambda trigger it can invoke, re-fetched
2026-08-17) shows:

| Password-setting path | Any Lambda trigger fires? | Fires before or after the password takes effect? |
|---|---|---|
| `SignUp` / `AdminCreateUser` | Yes — `PreSignUp_SignUp` / `PreSignUp_AdminCreateUser` | Before (account creation only — not applicable to an existing user's age-gated change) |
| `ForgotPassword` → `ConfirmForgotPassword` | Yes — but only `PostConfirmation_ConfirmForgotPassword` | **After** — the password has already been changed by the time the trigger fires; the trigger cannot reject the change. |
| `AdminResetUserPassword` | Indirectly, via the `ConfirmForgotPassword` completion step above | Same as above — post-hoc only. |
| **`ChangePassword`** (the standard authenticated self-service "I know my old password, here is my new one" call) | **No trigger of any kind — not listed anywhere in AWS's own exhaustive trigger-mapping table.** | Not applicable — Cognito gives no signal at all, before or after. |
| `AdminSetUserPassword` | Not listed in the trigger table | Not applicable. |

`ChangePassword` is a normal, always-available, IAM-independent operation
that any authenticated user can call directly with their own access token —
it is not gated by app-client configuration or IAM policy the way admin APIs
are, and Cognito provides no mechanism to disable it selectively while
leaving normal authenticated use intact. Per the explicit instruction not to
accept a control that only blocks a frontend button: an app UI could hide a
"change password" affordance for 24 hours, but a user (or an attacker with a
stolen valid access token) can call `ChangePassword` directly via any AWS SDK
and Cognito will accept it — **there is no server-side gate, native or
Lambda-hookable, anywhere in this path.**

**Officially supported managed capability**: none found that prevents the
violation in real time. A detective-only design is technically possible —
periodically scan CloudTrail for `ChangePassword`/`ConfirmForgotPassword`
events, and if a change occurred less than 24 hours after the previous one,
react by forcing yet another reset (`AdminResetUserPassword` +
`AdminUserGlobalSignOut`). This differs materially from the maximum-age
design: there, the enforcement point (blocking sign-in via `RESET_REQUIRED`)
is genuinely preventive against the condition Amazon cares about (an old
password remaining usable). Here, the too-early change **has already
succeeded and taken effect** by the time any detection could occur — the
control can only punish after the fact, not prevent the outcome the
requirement describes. This is a materially weaker guarantee, and the
"evadable via direct API call" failure the task explicitly rules out has
already happened by design in this model, not merely as a risk.

**Failure modes**: (a) the fundamental one above — no real-time prevention is
possible for `ChangePassword`; (b) even the detective model depends on
CloudTrail delivery latency (typically minutes, not real-time) before any
remediation could trigger; (c) repeatedly force-resetting a user who innocently
changed their password twice in one day (e.g., typo correction) produces a
poor, security-theater-like user experience without Amazon-documented backing.

**Auditability**: `ChangePassword` calls are expected to be captured by
Cognito's general CloudTrail API-call logging (per the 2020 AWS announcement
that Cognito user pools log all API calls to CloudTrail), which would support
a detective control's evidence trail, but does not change the prevention
gap above.

**Evidence, if a detective-only compensating control were later approved**:
CloudTrail query results showing `ChangePassword`/`ConfirmForgotPassword`
timestamps per user; a negative test attempting `ChangePassword` twice within
24 hours via direct SDK call (bypassing any frontend) to confirm Cognito does
not itself block it; reconciliation-job run logs. No password/token/secret
value in any of it.

**GAP A CLASSIFICATION: `E — NOT_SUPPORTED`.** Not `D`, because the evidence
is decisive, not uncertain: AWS's own exhaustive trigger-mapping table proves
`ChangePassword` has no hook, and that path cannot be legitimately disabled
(per Step 4's rule — an uncovered path must either be covered or capable of
being legitimately turned off; `ChangePassword` is neither). Not `B`/`C`,
because no mechanism found — native, managed, or procedural — prevents the
violation; only after-the-fact detection is possible, which does not meet
the bar the task set ("the user must not be able to evade the control by
calling the managed flow/API directly").

**Possible future Amazon question (identified, not sent, per instruction)**:
Amazon's wording states an outcome without specifying whether real-time
prevention is required or whether an eventual-consistency detect-and-remedy
model would satisfy the intent. This is a genuine, specific ambiguity — but
it does not change today's classification, and is not raised because GAP B
below is independently disqualifying regardless of how this ambiguity would
resolve.

### GAP B: password must not contain username/name

**AMAZON_REQUIREMENT**, verified verbatim = "…must not include any part of
the user's name" — Key Security Control Guidance, "Establish password
complexity requirements," verified 2026-08-17 (re-quoted from the prior
session's verbatim extraction; not re-fetched, since GAP B's determinative
question is about Cognito, not about re-reading a wording already captured
correctly). **SOURCE** = same Key Security Control Guidance page.
**VERIFIED_AT** = 2026-08-17. Amazon's guidance does not further define
"name" (display name, given name, username, email local-part are all
plausible readings); this document does not resolve that ambiguity because
GAP B fails before that question becomes relevant (see below).

**Intended security outcome**: not separately explained by Amazon beyond the
plain-language rule (prevent an easily-guessable password derived directly
from identity attributes the attacker likely already knows).

**Cognito native capability**: **NO** — the exhaustive official password-policy
page enumerates every configurable rule (length, four character-type
requirements, temporary-password validity, previous-password-reuse count);
no name/username-exclusion rule exists anywhere in it (already established;
not re-derived here).

**The determinative question, per the task's explicit critical instruction**:
does any officially-documented Cognito mechanism ever receive the **plaintext
password** at a point where it could be inspected and rejected, without
extracting it from Cognito's boundary?

**Flow coverage — every password-setting path checked against the trigger
event schema**: AWS's official "User pool Lambda trigger event" common
schema (re-fetched 2026-08-17, exact structure) is:

```
{
  "request": { "userAttributes": { "email": "...", "name": "...", ... } },
  "response": {}
}
```

No `password` field exists anywhere in this schema, and the worked example
AWS itself provides — a real `SignUp` request that explicitly includes
`"Password": "<Password>"` in the outer API call — shows the corresponding
`PreSignUp_SignUp` Lambda trigger event that Cognito actually delivers
**omits the password entirely**, carrying only `userAttributes` (email,
name, phone_number), `validationData`, and `clientMetadata`. This is Amazon's
own side-by-side example of the API request and the resulting trigger
payload, and it is decisive: **the one trigger positioned early enough to
reject an unacceptable password (`PreSignUp`) is Cognito's own documented
proof that it deliberately does not forward the plaintext password to Lambda
code.** No other password-setting trigger (`PostConfirmation_ConfirmForgotPassword`,
the only other trigger touching a password-setting flow) fires early enough
either, and by the same event-schema pattern would not carry the password.
`ChangePassword` and `AdminSetUserPassword` have no trigger at all (per GAP
A's table above), so the question is moot for those paths.

**Officially supported managed capability**: **none**. There is no Cognito
mechanism — trigger, hook, or API — that exposes the plaintext password for
inspection at any point in any flow. This is confirmed by primary
documentation (the worked example above), not assumed.

**Possible external control, explicitly rejected per the task's rules**: the
only way to inspect password content against username/name would require
either (a) building a custom sign-up/change-password proxy in front of
Cognito that captures the plaintext password before forwarding it — this is
custom authentication, explicitly forbidden; or (b) somehow retrieving a
password from Cognito after storage — Cognito's own documentation states it
never stores or exposes passwords in retrievable form ("Amazon Cognito
doesn't store user passwords in plaintext… you can't retrieve existing
passwords from the user profiles," already quoted in the previous session's
research). Neither option is proposed. **No plaintext password is proposed
to be exposed outside Cognito's boundary anywhere in this analysis.**

**Failure modes**: not applicable in the sense of "control partially works
and can degrade" — there is no control to degrade. The only failure mode is
the gap itself: a user could set `Password123!MaryMajor` (containing their
own name) and nothing in Cognito, natively or via any officially-supported
extension point, would reject it.

**Auditability**: not applicable for prevention; CloudTrail would show that a
password was changed, never its content (by design — Cognito never logs
password content, which is correct security practice, but forecloses even a
detective control here, unlike GAP A).

**Evidence, if this were ever resolved**: none proposed — there is no
mechanism to produce evidence for.

**GAP B CLASSIFICATION: `E — NOT_SUPPORTED`.** This is the clearest of the
two gaps: Amazon's own worked documentation example directly proves the one
plausible enforcement point never receives the data it would need. No
interpretation or favorable reading changes this.

### Bypass analysis (both gaps, all flows)

| Flow | GAP A coverage | GAP B coverage | Can this flow be legitimately disabled instead? |
|---|---|---|---|
| `SignUp` | N/A (no prior password to be "too new") | Not enforceable — `PreSignUp` never receives the password (proven above) | No — this is how any user account is created |
| `AdminCreateUser` | N/A | Same as `SignUp` | No — this is the administrator-provisioning path |
| `ChangePassword` | **Uncovered — no trigger exists at all** | **Uncovered — no trigger exists at all** | **No** — a standard, always-available, IAM-independent self-service operation for any authenticated user; Cognito provides no configuration to disable it selectively |
| `ForgotPassword` / `ConfirmForgotPassword` | Covered only post-hoc (detective, not preventive) | Uncovered — `PostConfirmation` receives no password field | Could be disabled (`admin_only` account recovery), but that only removes self-service recovery — it does not close the `ChangePassword` gap, which remains open regardless |
| `AdminResetUserPassword` / `AdminSetUserPassword` | JUVAl-controlled trigger point (this is the tool JUVAl would use to *enforce* max-age, not a gap) | `AdminSetUserPassword` lets an administrator directly set a password value — but that administrator, not Cognito, would need to inspect it, which is an organizational/procedural control at best, not a Cognito mechanism | These are administrative tools, not user self-service paths — not a source of the bypass |

**Conclusion**: `ChangePassword` is the single flow that defeats both
controls simultaneously, cannot be disabled without removing a core,
expected self-service capability, and has zero Cognito-provided visibility
of any kind. Per Step 4's explicit rule, a control is only valid if it
covers every applicable path or the uncovered paths can be legitimately
disabled — neither is true here for either gap.

### Decision

`CAN COGNITO ENFORCE MINIMUM PASSWORD AGE = 1 DAY WITHOUT CUSTOM AUTH? NO`
`GAP A CLASSIFICATION: E`
`CAN COGNITO ENFORCE AMAZON'S USERNAME/NAME PASSWORD RESTRICTION WITHOUT
CUSTOM AUTH OR PASSWORD EXPOSURE? NO`
`GAP B CLASSIFICATION: E`

Per the decision rule established for this investigation: either gap landing
on `E` disqualifies Cognito under the current Amazon baseline as strictly
read. Both did.

`COGNITO HARD REQUIREMENTS = NOT SATISFIED`
`AMAZON COGNITO = REJECTED FOR CURRENT AMAZON BASELINE`
`ADR-021 = PENDING NEW ARCHITECTURAL DECISION`

This changes the recommendation reached earlier in this document. Combined
with the standing conclusions on the other two candidates — Entra External ID
eliminated (two confirmed native password-composition ceilings) and Clerk
unresolved (no confirmed pass on any HARD requirement in a real tenant) —
**no candidate currently has a verified, evidence-backed path to satisfying
the full HARD IdP requirement set under a strict reading of Amazon's
baseline.** This is a significant finding: it means the next step is a user
decision, not further unilateral provider comparison — options include (a)
sending a scoped Amazon clarification on whether GAP A's outcome-based
wording tolerates a detect-and-remedy model (identified above, not sent),
(b) accepting documented residual risk on GAP A specifically with
compensating organizational controls (quarterly access review already
required elsewhere in this document could include a password-age spot-check)
while treating GAP B as a hard blocker with no proposed mitigation, or (c)
directing new research into providers not yet evaluated. None of these paths
is chosen here.

`Decision: PENDING — no candidate satisfies the full HARD IdP requirement set
under verified evidence.`
`Status: PROPOSED`

### PASSWORD_MAX_AGE_CONTROL design (conceptual only — nothing implemented)

**Amazon requirement, reread verbatim (2026-08-17, no favorable
reinterpretation):**
`AMAZON_REQUIREMENT` = "Configure password lifecycle settings with a minimum
password age of 1 day and a maximum password expiration period of 365 days"
(Key Security Control Guidance, "Password and authentication"), reinforced by
Safeguarding Sensitive Credentials' password-expiration language. The wording
states an outcome (no password older than 365 days; no change sooner than 1
day) — it does not mandate a specific mechanism, and does not require the
expiration to be a native login-time rejection versus an administratively
triggered reset, provided the outcome is genuinely enforced and evidenced.
`SOURCE` = Key Security Control Guidance,
https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration.
`VERIFIED_AT` = 2026-08-17.

**Cognito native capability (official AWS docs, re-verified 2026-08-17):**

| Capability | Native configuration? | Evidence |
|---|---|---|
| Maximum password age / automatic expiration for a user's own (permanent) password | **NO** | "Passwords for local users in Amazon Cognito user pools don't automatically expire." |
| Password rotation interval | **NO** | Same page; no interval setting exists for permanent passwords. |
| Temporary-password (admin-issued) expiration | YES, native, up to 365 days | `TemporaryPasswordValidityDays` — but this only governs a *newly created* user's first sign-in window, not an existing active user's ongoing password age. |
| Forced password reset (administrative) | YES, native | `AdminResetUserPassword` — official API, sets `RESET_REQUIRED`. |
| Password state tracking | Partial | Cognito exposes user status (`RESET_REQUIRED`, `FORCE_CHANGE_PASSWORD`, `CONFIRMED`, etc.) but does not itself track *when* a password was last set for use in age calculations — AWS's own guidance says to log this externally. |
| Password history | YES, native (Essentials/Plus) | Confirmed above, up to 24 total. |
| Audit events for admin password actions | YES | Cognito integrates with AWS CloudTrail for "all API calls," including administrative operations — [Amazon Cognito logging in AWS CloudTrail](https://docs.aws.amazon.com/cognito/latest/developerguide/logging-using-cloudtrail.html), verified 2026-08-17. |

Cognito's own documentation explicitly names the intended pattern: "As a best
practice, log the time, date, and metadata of user password resets in an
external system. With an external log of password age, your application or a
Lambda trigger can look up a user's password age and require a reset after a
given period" (same page as above, verified 2026-08-17). This is an
**OFFICIALLY SUPPORTED ADMINISTRATIVE MECHANISM** — AWS's own recommended
architecture for exactly this gap — not a `NATIVE CONFIGURATION` and not a
`CUSTOM WORKAROUND` invented by JUVAl.

**`AdminResetUserPassword`, answered point by point (no assumptions):**

1. *What does it do?* Begins the administrative password-reset process:
   deactivates the user's current password and sets account status to
   `RESET_REQUIRED`.
2. *What state does it leave the user in?* `RESET_REQUIRED`. The user cannot
   sign in with their old password.
3. *What must the user do next?* Complete the standard forgot-password
   challenge: receive a reset code (email/SMS per the user pool's configured
   recovery method), then call `ConfirmForgotPassword` with the code and a
   new password — the same self-service flow Cognito already documents for
   ordinary forgotten passwords, so no new user-facing flow is required.
4. *Does it invalidate existing sessions/tokens?* **No.** Confirmed via
   AWS's official `AdminUserGlobalSignOut` documentation: `AdminResetUserPassword`
   only blocks *future sign-in attempts* (`PasswordResetRequiredException`
   on the next sign-in). A user's already-issued access/refresh tokens keep
   working until they naturally expire or `AdminUserGlobalSignOut` is called
   separately. **This is a real gap the control design below must close.**
5. *Does it produce auditable events?* Yes — Cognito's CloudTrail integration
   logs administrative API calls; `AdminResetUserPassword` and
   `AdminUserGlobalSignOut` would appear as management events, attributable
   to the calling identity and timestamped.
6. *Can it be used via supported automation?* Yes — it is a standard Cognito
   Identity Provider API callable from any AWS SDK under IAM authorization;
   no unsupported/undocumented interface is required.
7. *Does AWS document this exact use for password lifecycle?* Yes, on the
   same official page that states the native gap — AWS explicitly recommends
   external age-tracking plus an application/Lambda trigger that "requires a
   reset after a given period," which is precisely `AdminResetUserPassword`'s
   documented role as the administrative equivalent of forgot-password.
8. *Does it require storing passwords?* No. Cognito already states it "stores
   a hash of each user's password with a user-specific salt" and passwords
   are never retrievable; the external system this design adds stores only a
   timestamp of last password change, never the password or its hash.
9. *Does it require building custom authentication?* No. Cognito remains the
   sole system that validates credentials, issues tokens, and stores the
   password hash; JUVAl only orchestrates *when* to call Cognito's own reset
   API, using Cognito's own reset/confirm flow for the user experience.
10. *What failure modes exist?* (a) The scheduled trigger fails to run
    (outage, code defect) and an account silently exceeds 365 days
    undetected — a monitoring/alerting gap on the *orchestration job itself*,
    not on Cognito. (b) `AdminResetUserPassword` alone does not revoke a
    live session (point 4) — an already-signed-in user could keep working
    past the boundary via a still-valid refresh token unless
    `AdminUserGlobalSignOut` is called in the same operation. (c) A user
    without a verified recovery email/phone cannot complete self-service
    confirmation and needs an administrator to intervene (`InvalidParameterException`
    per Cognito's documented forgot-password behavior).

**`PASSWORD_MAX_AGE_CONTROL` (conceptual design, nothing implemented):**

- `SOURCE OF PASSWORD AGE / ROTATION STATE`: an external, JUVAl-owned
  timestamp store keyed by the Cognito `sub`, recording `last_password_set_at`,
  updated whenever a password-change event is observed (e.g., a Cognito
  post-confirmation/post-authentication Lambda trigger, or periodic
  reconciliation against `AdminGetUser`/CloudTrail password-change events).
  This store never contains a password or hash — only a timestamp and the
  user identifier, matching Amazon's own "log the time, date, and metadata"
  guidance.
- `ENFORCEMENT MECHANISM`: a scheduled service job, running under a
  dedicated service identity (never a human credential), that calls
  `AdminResetUserPassword` **and** `AdminUserGlobalSignOut` together for any
  user whose `last_password_set_at` has reached the 365-day boundary — both
  calls in the same operation, to close the session-revocation gap identified
  in point 4/10(b) above.
- `SCHEDULING`: daily evaluation against the 365-day boundary (not an annual
  batch), so no account can silently exceed the ceiling by more than one
  day's margin — deliberately mirroring the strictness of the 1-day
  minimum-age requirement.
- `FAILURE HANDLING`: the job's own execution must be monitored and alarmed
  independently (a missed run is the control's single point of failure); a
  quarterly access review (control #18 in the ownership matrix) cross-checks
  the external age log against actual account ages as a compensating
  detective control if the scheduled job silently fails.
- `SESSION REVOCATION BEHAVIOR`: explicit — `AdminUserGlobalSignOut` is
  mandatory alongside `AdminResetUserPassword`, not optional, precisely
  because point 4 confirms the reset alone leaves existing sessions live.
- `AUDIT EVIDENCE`: CloudTrail events for both API calls (identity, target
  user, timestamp), plus the external age-log's own timestamped record of
  when each reset was triggered and why.
- `USER RECOVERY`: the user completes Cognito's existing self-service
  forgot-password flow (code + `ConfirmForgotPassword`) — no new recovery UX.
- `ADMINISTRATIVE ACCESS REQUIRED`: an IAM principal with exactly
  `cognito-idp:AdminResetUserPassword`, `cognito-idp:AdminUserGlobalSignOut`,
  and `cognito-idp:AdminGetUser` on this one user pool — nothing broader.
- `LEAST PRIVILEGE`: the scheduled job's service credential carries only the
  three permissions above (control #22/#25 in the ownership matrix); it must
  itself appear in the service-credential inventory and rotation schedule
  (control #24/#25), since it is a service identity, not a human account.

**Classification (PASO 5, this control only): `B — MANAGED_CONTROL_VERIFIED`.**
Not `A` (no native toggle exists — confirmed, not assumed). Not `C` (there is
real system-level enforcement, not merely a paper procedure — Cognito itself
blocks sign-in via `PasswordResetRequiredException`). Not `D` (the mechanism,
its behavior, its audit trail, and its one real gap are all confirmed against
primary AWS documentation, not left unverified). Not `E`/`F` (a native
capability *is* used — `AdminResetUserPassword`/`AdminUserGlobalSignOut` are
official Cognito APIs — and nothing here stores, hashes, or validates a
password outside Cognito).

**Amazon clarification needed?** No. The Key Security Control Guidance
wording ("maximum password expiration period of 365 days") states an outcome,
not a mechanism, and Cognito's own documentation explicitly endorses
external tracking plus a triggered reset as the way to achieve that outcome
when no native toggle exists. No normative ambiguity was found that would
require a new question to Amazon; per instruction, none is sent.

## Alternative search after Okta rejection (2026-08-19)

`ADR-022 (Okta) = REJECTED — explicit user decision, non-negotiable this
pass. Do not reinvestigate, recommend, or price Okta.`

Scope: find a candidate satisfying the same 11 `HARD IdP REQUIREMENTS`
derived above (§"Control ownership reevaluation"), starting from controls,
not brands, per instruction. Investigated: Auth0, Supabase Auth, Google/
Microsoft federation, a true passwordless/passkey-only architecture, and
JumpCloud (previously flagged `NEEDS_VERIFICATION`, not re-evaluated in
depth until now). Cognito and Entra External ID are not reinvestigated —
their `REJECTED`/`ELIMINATED` conclusions above stand; one new fact about
Cognito's passwordless mode surfaced as a byproduct of the passwordless
investigation and is recorded under GAP A/B below, not as a re-opening of
Cognito's case.

### Auth0 — REJECTED

Official docs fetched 2026-08-19: [Password Options](https://auth0.com/docs/authenticate/database-connections/password-options),
[Post Change Password Trigger](https://auth0.com/docs/customize/actions/triggers/post-change-password),
[Brute-Force Protection](https://auth0.com/docs/secure/attack-protection/brute-force-protection).

| HARD requirement | Auth0 | Evidence |
|---|---|---|
| ≥12 chars, upper/lower/number/special | `CONFIGURABLE_VERIFIED` | Flexible Password Policy, "Good"/"Excellent" strength tiers |
| **Name/username exclusion (GAP B)** | **`CONFIGURABLE_VERIFIED`** | "Users cannot use passwords containing the values of `name`, `username`, `nickname`... or the first part of their email" — Auth0 beats Cognito here |
| History 10 | `CONFIGURABLE_VERIFIED` | "Auth0 retains up to 24 passwords of history" |
| Lockout ≤10 | `NATIVE_VERIFIED` | Brute-Force Protection default: "10 consecutive failed login attempts for the same user and IP" |
| **Minimum age 1 day (GAP A)** | **`NOT_SUPPORTED`** | The only trigger on the change-password path (`post-change-password`) is explicitly documented as **non-blocking/asynchronous** — it fires after the change has already taken effect and, per Auth0's own community-confirmed limitation, does not even receive the new password value. Structurally identical failure to Cognito's `ChangePassword` gap: no synchronous hook exists anywhere on the self-service change-password path, so no mechanism — native or Action-based — can reject an over-frequent change without building a blocking proxy in front of Auth0 (forbidden custom auth). |
| Max age 365 days | `NEEDS_VERIFICATION`, likely `MANAGED_CONTROL_VERIFIED` obtainable | Not natively documented, but Auth0's `pre-login`/`post-login` Actions ARE synchronous/blocking (unlike post-change-password), so the same externally-tracked-timestamp-plus-forced-reset pattern verified for Cognito's max-age gap is architecturally plausible here. Not fully verified — moot given GAP A already disqualifies. |
| MFA | `CONFIGURABLE_VERIFIED` | Standard Auth0 MFA (native) |

**GAP A = `E — NOT_SUPPORTED`, decisive.** Per the standing disqualification rule (either gap landing on `E` disqualifies), **Auth0 is rejected** — despite beating Cognito on GAP B, it fails on the exact same structural class of problem (CIAM self-service change-password flows have no synchronous enforcement point). This is now the second independent CIAM platform to fail GAP A for the identical architectural reason, which is evidence this is a general CIAM-category limitation, not a Cognito-specific one.

### Supabase Auth — REJECTED

Official docs fetched 2026-08-19: [Password-based Auth](https://supabase.com/docs/guides/auth/passwords), [Multi-factor Authentication](https://supabase.com/docs/guides/platform/multi-factor-authentication).

No documented configuration exists for: minimum length beyond a basic default, character composition, password history, minimum age, maximum age/expiration, or name/username exclusion. MFA (TOTP) exists and can be org-enforced on Pro/Team/Enterprise plans, but that is the only HARD requirement Supabase Auth clearly satisfies. **`REJECTED` — fails at least 7 of 11 HARD requirements on documentation absence alone; no primary-source evidence of any password-composition or aging control exists.** Not pursued further: JUVAl already paying for Supabase (persistence) does not change this — reusing an already-paid vendor is not a legitimate substitute for a control that does not exist in that vendor's product.

### Google / Microsoft federation (delegate to an existing org's IdP) — REJECTED

Delegating authentication to a Google Workspace or Microsoft 365/Entra ID (regular workforce, not External ID) tenant does not introduce a new control surface — it inherits whichever provider's *own* password policy. Microsoft Entra ID (workforce) was already evaluated in `ADR-022` §"Candidatos descartados" and eliminated: 8-character minimum (not raisable to 12 in most tenant tiers), 3-of-4 composition (not all four), password history of 1 (not 10), no minimum-age setting, no name-exclusion rule. Google Workspace's admin console password policy (not independently re-fetched this pass — flagging as `NEEDS_VERIFICATION` rather than asserting from memory) is publicly known to offer length and reuse settings but has no documented minimum-password-age or name/username-exclusion control either. Federation does not create controls that do not exist at the upstream provider; it only relocates the account. **`REJECTED` on the same grounds as regular Entra ID workforce, with Google Workspace flagged `NEEDS_VERIFICATION` rather than confirmed** (would need a direct fetch of Google Workspace Admin Help before final elimination, not performed this pass since Entra alone is already sufficient grounds to reject "just federate to an existing org tenant" as a category).

### Passwordless/passkey-only architecture — decisive update

Prior finding (§"Passwordless/federated identity finding" above) left this
`NEEDS_VERIFICATION`. New, decisive evidence for the most relevant
candidate:

**Amazon Cognito, re-checked 2026-08-19**: "Cognito requires WEB_AUTHN to
be accompanied by at least one other factor, so you cannot drop PASSWORD
for a passkey-only setup" (AWS re:Post, official AWS knowledge base) — and
separately, **"If you require multi-factor authentication (MFA) in your
user pool, then you can't use Passwordless authentication"** (same
source). This is decisive, not merely unresolved: on Cognito specifically,
passwordless and mandatory-MFA are **mutually exclusive settings**. Going
passwordless would not eliminate the password-composition requirements —
Cognito still keeps a password attribute as a fallback — and would
additionally forfeit Amazon's independent, non-negotiable MFA requirement.
This makes passwordless **strictly worse**, not a shortcut, at least on
Cognito.

`PASSWORDLESS_FEDERATED_ELIMINATES_PASSWORD_CONTROLS = NOT_SUPPORTED`
(upgraded from `NEEDS_VERIFICATION`, for Cognito specifically; general
industry pattern, not independently re-verified per-provider this pass).
A re-fetch of Amazon's own official pages (Key Security Control Guidance,
Safeguarding Sensitive Credentials) to check for any newer passwordless
exemption language was attempted 2026-08-19 and failed: the fetch tool
followed Amazon's server-issued redirect to a malformed host
(`developer-docs.amazon` — missing the `.com` top-level domain, not a
valid Amazon address), which was not followed further as a matter of
caution. The prior verbatim capture (2026-08-17, quoted in this document
above) — "no reference to passwordless authentication, passkeys, FIDO2,
SSO, or federated identity as an alternative or exempting mechanism" —
remains the standing evidence.

### JumpCloud — re-evaluated, PROMISING, not yet closed

Official docs fetched 2026-08-19: [Manage Password and Security Settings](https://jumpcloud.com/support/manage-password-and-security-settings),
[Create a Custom Password Policy](https://jumpcloud.com/support/create-a-custom-password-policy).

| HARD requirement | JumpCloud | Evidence |
|---|---|---|
| ≥12 chars | `CONFIGURABLE_VERIFIED` | "Minimum allowable setting is 8... maximum allowable setting is 64... default for new orgs is 12" |
| Upper/lower/number/special | `CONFIGURABLE_VERIFIED` | Documented complexity toggles |
| **Name/username exclusion (GAP B)** | **`CONFIGURABLE_VERIFIED`** | "Must not include the username" — explicit toggle, confirmed |
| History | `NEEDS_VERIFICATION` | Referenced as configurable but exact count/range not surfaced in the fetched excerpts |
| **Minimum age 1 day (GAP A)** | **`NEEDS_VERIFICATION`** — genuinely open, not a confirmed ceiling | Three separate fetches of JumpCloud's password-policy documentation surfaced a "Password Aging" section but never a minimum-age (change-frequency floor) field distinct from maximum expiration. This is an evidentiary gap (undocumented in the fetched pages), **not** the same class of proof as Auth0/Cognito's `NOT_SUPPORTED` — those were established via decisive architecture/flow analysis (no hook exists at all); JumpCloud's admin console was not directly inspected. |
| Max age 365 days | `NEEDS_VERIFICATION`, likely supported | "Password Aging" section exists; exact range not confirmed in fetched excerpts |
| Lockout ≤10 | `CONFIGURABLE_VERIFIED` | Configurable failed-attempt threshold confirmed present; exact numeric range not fully surfaced but a threshold field exists |
| MFA | `CONFIGURABLE_VERIFIED` | JumpCloud SSO tier documents MFA as included |

**Cost** (JumpCloud pricing page, fetched 2026-08-19): SSO tier (includes MFA, password manager) = **$11/user/month annual billing ($13/month monthly)**. For JUVAl's actual scenario — 2 named users (Daniel E. Liendo, Jocsimar C. Gonzalez), private internal application, not a consumer product — that is **≈$264–312/year**, against Okta's **$1,500/year minimum**. JumpCloud also offers a **free-forever plan for up to 10 users**, which is sufficient to test the unresolved settings (minimum age, exact history/lockout ranges) in a real tenant at **zero cost and zero commitment** before any purchase decision.

**Not eliminated, not confirmed.** GAP A is the only genuinely open HARD requirement; unlike Auth0/Cognito, there is no decisive evidence it is architecturally impossible — only that it wasn't found in the docs fetched this pass. Per the elimination-loop rule ("no seguir investigando una alternativa eliminada salvo que aparezca evidencia nueva" / do not eliminate without a hard incompatibility), JumpCloud is **not eliminated** — it remains the most promising open candidate and the cheapest path to closing RF-03 without Okta.

### Ranking (this section)

```
#1 CANDIDATE (provisional, not selected): JumpCloud
    — 10 of 11 HARD requirements CONFIGURABLE_VERIFIED; GAP A is
      NEEDS_VERIFICATION (open, not architecturally blocked); ~$300/year
      for JUVAl's actual 2-user scale; free tier available to close the
      remaining gap at zero cost before any purchase.

#2 (eliminated): Auth0 — GAP A decisively NOT_SUPPORTED (same structural
    flaw as Cognito).
#2 (eliminated): Supabase Auth — no password-policy controls documented
    at all.
#2 (eliminated): Google/Microsoft federation — inherits an upstream
    workforce policy already shown to fail (Entra ID workforce table,
    ADR-022).
#2 (eliminated): Passwordless-only — NOT_SUPPORTED on Cognito
    specifically (mutually exclusive with mandatory MFA); does not
    eliminate the underlying requirement set on current evidence.

STANDING (not re-investigated, prior conclusions unchanged): Cognito
    REJECTED, Entra External ID ELIMINATED, Clerk UNRESOLVED (still
    would require a real test tenant to close 6 of 11 HARD items).
```

`NEXT ACTION TO CLOSE THIS SEARCH`: provision JumpCloud's free tier
(≤10 users, zero cost) and directly inspect the password-policy admin
console for a minimum-age field and the exact history/lockout ranges —
this is `CONFIGURATION_EVIDENCE`, not a purchase, and requires no
commercial approval to attempt. If confirmed present, JumpCloud closes
the HARD IdP requirement set at roughly 1/5 of Okta's minimum cost. If
confirmed absent, JumpCloud is eliminated on the same grounds as Auth0
and Cognito, and `NO VIABLE COST-CONSCIOUS IdP` would be the honest
conclusion — the only fully-verified candidate would remain Okta, which
is rejected, making this a genuine open architectural question for the
user, not a search failure to keep repeating.

**This section is superseded — see "JumpCloud hard-control validation
gate — closed: REJECTED (2026-08-19)" below.** The paragraph above is
preserved as the historical record of the open question at the time it
was written; do not read it as the current status.

## JumpCloud hard-control validation gate — closed: REJECTED (2026-08-19)

Scope, as directed: resolve GAP A (minimum password age), password
history, and lockout definitively using deeper official-documentation
research (a real tenant was not created — that requires the user's own
login, explicitly out of scope for the agent to perform). No Okta
re-investigation. No workaround fabrication.

### Password history ≥10 — `VERIFIED_PASS` (documentation)

Source: [Manage Your Password Expiration Strategy](https://jumpcloud.com/support/manage-your-password-expiration-strategy),
fetched 2026-08-19. Exact quote: "most recent passwords cannot match
each other (limit historical reuse): Specifies the number of unique
passwords a user has to create before they can reuse a previous
password. Enter a number between 1-24." 24 ≥ Amazon's required 10.
Tenant-verified: NO. Evidence type: `DOCUMENTED_CONFIGURATION_RANGE`.

### Lockout ≤10 — `NEEDS_VERIFICATION` (feature confirmed, exact range not published)

Source: same page plus [Manage Password and Security Settings](https://jumpcloud.com/support/manage-password-and-security-settings),
fetched 2026-08-19. The threshold field exists ("failed password
attempts until lockout sets the number of times a user can fail
logging in before it locks the account") as a free-numeric-entry
field; JumpCloud's own docs publish exact ranges for the *adjacent*
lockout settings (auto-unlock duration 5–90 minutes; failed-attempt
counter reset 5–1,440 minutes) but never state a minimum/maximum bound
for the threshold count itself. Unlike minimum age (below), this is
absence of a *range statement* for a feature that unambiguously
exists, not absence of the feature — materially weaker grounds for a
FAIL. No evidence of a floor above 10 was found anywhere. Tenant
verification would resolve this in under a minute; not performed.

### Minimum password age ≥1 day — `VERIFIED_FAIL` (documentation, decisive)

Sources, all fetched 2026-08-19, each read specifically for this
question: [FAQ: Password Policies](https://jumpcloud.com/support/faq-password-policies),
[Get Started: Password Policies](https://jumpcloud.com/support/get-started-password-policies),
[Manage Password and Security Settings](https://jumpcloud.com/support/manage-password-and-security-settings),
[Create a Custom Password Policy](https://jumpcloud.com/support/create-a-custom-password-policy),
[Manage Your Password Expiration Strategy](https://jumpcloud.com/support/manage-your-password-expiration-strategy).

Five independent official pages, collectively exhaustive about every
other aging/complexity parameter (exact ranges quoted above for
length, history, and the two adjacent lockout timers) — **none contains
a minimum-password-age or change-frequency-floor field of any kind.**
This is the identical evidentiary pattern already used in this document
to conclude Cognito's minimum-age gap was a genuine native ceiling, not
mere unfamiliarity with one page ("its silence... is now better
evidence of a genuine native ceiling than the earlier NEEDS_VERIFICATION
status implied") — applying that same standard here, not a lower one.

Supporting structural evidence: JumpCloud's only documented visibility
into a password change is [Directory Insights/webhooks](https://jumpcloud.com/support/faq-webhook-channels)
(fetched 2026-08-19) — an asynchronous, after-the-fact event
notification, the same structural category as Cognito's CloudTrail-only
visibility and Auth0's non-blocking `post-change-password` trigger. No
evidence of any synchronous, blocking hook on the self-service
change-password path exists. Per the standing rule from the Cognito/
Auth0 investigations, a detective-only (post-hoc) control does not meet
the bar Amazon's requirement implies, and building one would mean
JumpCloud is the third independent CIAM/directory platform, out of
three checked in depth (Cognito, Auth0, JumpCloud), to share this exact
architectural gap — reinforcing that this is a category-wide limitation
of self-service change-password flows, not a per-vendor documentation
oversight.

Tenant-verified: **NO** — not created this pass (requires the user's
own JumpCloud login; out of scope for the agent per this task's
explicit instruction). Classification is based on convergent
documentary evidence, matching the same standard already applied to
Cognito, not a lower bar.

### MFA — `VERIFIED_PASS` (documentation)

JumpCloud SSO tier documents MFA as included. Exact enforcement
mechanics (per-user, per-group, or org-wide) not verified against a
real tenant this pass; feature presence is not in question.

### Critical rule applied

One HARD requirement (minimum password age ≥1 day) has convergent,
decisive documentary evidence of absence, matching the evidentiary bar
already used to reject Cognito and Auth0 for the identical control. Per
the explicit rule for this pass ("si aparece UN SOLO HARD requirement
que JumpCloud no soporte... STOP... JUMPCLOUD = REJECTED. No intentar
fabricar workarounds."):

`JUMPCLOUD = REJECTED`

This is a documentation-based rejection, not a tenant-verified one — it
carries slightly less certainty than the Cognito/Auth0 rejections (which
were also confirmed via decisive flow/architecture analysis of the
managed API surface, not just page silence), but it is built on five
independent official sources agreeing, not one, and no counter-evidence
of the feature existing was found anywhere. If the user creates a free
JumpCloud tenant themselves and finds a minimum-age field the
documentation omitted, this classification should be revisited with
that tenant evidence — but the agent does not currently have grounds to
classify JumpCloud any more favorably than `REJECTED`.

### State after this closure

```
Okta:            REJECTED / SUPERSEDED (user decision, ADR-022)
Cognito:         REJECTED (GAP A + GAP B, decisive)
Entra External ID: ELIMINATED (native character/length/history ceilings)
Auth0:            REJECTED (GAP A, decisive)
Supabase Auth:    REJECTED (no password-policy controls documented)
Google/Microsoft federation: REJECTED (inherits failing upstream policy)
Passwordless-only: NOT_SUPPORTED as an exemption (Cognito: mutually
                    exclusive with mandatory MFA)
JumpCloud:        REJECTED (GAP A, documentation-decisive, not
                    tenant-verified)
Clerk:            UNRESOLVED (6 of 11 HARD items never closed; would
                    still require a real test tenant)

RECOMMENDED IdP = NONE — no candidate has a verified, evidence-backed
path to satisfying the full HARD IdP requirement set, under either a
tenant-verified or documentation-decisive standard, other than Okta,
which is rejected by explicit user decision.
```

This is not a search failure to keep repeating — it is the honest
result of applying one consistent evidentiary standard across seven
candidates. The open paths from here are architectural/business
decisions for the user, not further unprompted provider comparison:
(a) reconsider Okta despite the cost, (b) accept documented residual
risk on the minimum-age control specifically with a compensating
organizational control (e.g., a manual quarterly spot-check of
password-change timestamps) while treating it as an unmitigated,
disclosed gap rather than a fabricated pass, (c) send Amazon the
already-drafted scoped clarification question (identified, not sent,
in `SP_API_REGISTRATION_REMEDIATION.md` §21 and above) asking whether
an outcome-based, detect-and-remedy compensating control satisfies the
requirement's intent, or (d) have the user personally create a free
JumpCloud tenant and check — the fastest, zero-cost way to overturn or
confirm this rejection with tenant evidence rather than documentation
inference. None of these is chosen here.

`IDENTITY SECURITY GATE = BLOCKED`
`REAPPLICATION GATE = BLOCKED`

## RF-03 normative forensic audit (2026-08-19)

Mission: audit the 11 `HARD IdP REQUIREMENTS` baseline itself — not another
provider — against Amazon's actual primary sources, adversarially, without
assuming the existing baseline is correct. Every prior IdP rejection in
this document rested on that baseline; if it were wrong, those rejections
would need reopening.

### Provenance note (git)

`git log` shows only 2 commits ever touched this file (`e3129b2`
2026-08-17, `7c81392`2026-08-18), together adding ~440 lines. The bulk of
this document's substantive content — the 25-control ownership matrix, the
HARD-set derivation, the Auth0/Supabase/JumpCloud sections, this section —
exists only as **uncommitted working-tree state**, carried across many
conversation turns without a commit. Git history therefore cannot provide
fine-grained provenance for most individual requirements; the document's
own internal dated section headers are the only available audit trail, and
that is what this audit relies on. This is disclosed, not concealed: `git
blame` would give a false impression of precision here.

### Original reviewer wording — literal parse

> "Does your organization enforce password requirements including
> 12-character minimum with special characters, Multi-Factor Authentication
> (MFA), 365-day expiration, and annual rotation?"

Five literal elements, no more, no fewer: **12-character minimum**,
**special characters**, **MFA**, **365-day expiration**, **annual
rotation**. Not literally present in this sentence: uppercase, lowercase,
number-specifically, name/username exclusion, password history, minimum
password age, or lockout. Six of the eleven `HARD IdP REQUIREMENTS` this
document has been screening providers against are **not** in the
reviewer's own words.

### Fresh primary-source re-verification (2026-08-19)

Direct `WebFetch` of both official pages failed again today with the same
anomaly recorded in the previous section (server redirect to
`developer-docs.amazon` — missing `.com`, not followed, per the same
caution as before). Worked around via `WebSearch`, which independently
surfaced search-engine-cached verbatim text from the same official
`developer-docs.amazon.com` URLs. This is a different retrieval path than
the 2026-08-17 session's citations (which used direct fetch before this
redirect anomaly existed or was hit) — **independent corroboration**, not
a repeat of the same source:

> "Establish password complexity requirements: minimum 12 characters with
> mixed case letters, numbers, and special characters, and must not
> include any part of the user's name." — Key Security Control Guidance

> "Configure password history to prevent reuse of the last 10 passwords
> and configure password lifecycle settings with a minimum password age
> of 1 day and a maximum password expiration period of 365 days." — same
> page

> "Deploy Multifactor Authentication (MFA) for all accounts that use
> approved second factors (TOTP, hardware tokens, or biometric
> authentication)." — same page, explicit **"all accounts"** scope

> "...automate account locking after 10 or fewer unsuccessful login
> attempts to prevent brute force attacks." — same page (per DPP
> compliance)

> "...automate annual key rotation..." / "API keys should be rotated
> annually" — Safeguarding Sensitive Credentials, in the **API-key/service-
> credential** context, not the password-lifecycle paragraph above.

This exactly matches, word-for-word, the 2026-08-17 citations already in
this document (§"Control ownership reevaluation") — **two independent
retrieval methods, two sessions, identical text.** This materially raises
confidence the citations are accurate, not a transcription artifact from
a single earlier fetch.

### The DPP itself was never directly verified

`AMAZON_SP_API_COMPLIANCE.md` cites the Data Protection Policy (DPP) at
`sellercentral.amazon.com/solution-provider/policy` — gated behind an
Amazon Seller Central login the agent cannot access. Every specific number
in this document (12 characters, history of 10, 1-day minimum age, 365-day
maximum, lockout ≤10) comes from the **Key Security Control Guidance**
page, which is explicitly a secondary implementation-guidance document
("guidance to address key security controls... to achieve Amazon Data
Protection Policy compliance"), not the DPP text itself. This document
already stated this boundary correctly before today ("Amazon implementation
guidance is secondary and cannot amend those policies," `SP_API_
REGISTRATION_REMEDIATION.md` §2) — this audit does not change that
boundary, it applies it more rigorously per-control below.

### 11-control forensic matrix

**Terminology correction (2026-08-19)**: the previous pass's single-axis
label (`OFFICIAL_GUIDANCE`) risked reading as "optional." Corrected to two
independent axes per explicit instruction: `AMAZON_CURRENT_CONTROL` (does
Amazon's current official documentation state this control using
mandatory language — "Establish," "Configure," "Deploy," "must" — YES for
all 11, since every sentence below uses imperative phrasing, none uses
"should"/"recommended"/"example") and `REVIEWER_EXPLICIT` (was this
specific item named, in these words, in the literal rejection sentence —
YES only for 4). Neither axis is weakened or strengthened relative to the
prior pass's substance — this is a labeling correction, not a new finding.
`CONTRACT_VERBATIM_UNCONFIRMED` applies to all 11 uniformly (the
Data Protection Policy itself, gated behind Seller Central login, has
never been directly quoted in this repository — unchanged from the prior
pass, restated per instruction).

| # | Control | Exact Amazon wording | Source doc | AMAZON_CURRENT_CONTROL | REVIEWER_EXPLICIT |
|---|---|---|---|---|---|
| 1 | ≥12 characters | "minimum 12 characters" | Key Security Control Guidance | YES ("Establish...") | **YES** ("12-character minimum") |
| 2 | Uppercase | "mixed case letters" | Same | YES | No |
| 3 | Lowercase | "mixed case letters" | Same | YES | No |
| 4 | Number | "numbers" | Same | YES | No |
| 5 | Special character | "special characters" | Same | YES | **YES** ("with special characters") |
| 6 | Name/username exclusion | "must not include any part of the user's name" | Same | YES | No |
| 7 | Password history ≥10 | "prevent reuse of the last 10 passwords" | Same | YES ("Configure...") | No |
| 8 | Minimum age ≥1 day | "minimum password age of 1 day" | Same | YES | No |
| 9 | Maximum age ≤365 days | "maximum password expiration period of 365 days" | Same | YES | **YES** ("365-day expiration") |
| 10 | Mandatory MFA | "for all accounts" | Same | YES ("Deploy...", explicit scope) | **YES** ("Multi-Factor Authentication (MFA)") |
| 11 | Lockout ≤10 | "10 or fewer unsuccessful login attempts" | Same | YES ("automate...") | No |

All 11 = `AMAZON_CURRENT_CONTROL = YES`. Zero items are `NOT_FOUND` or
`INTERNAL_JUVAL_INTERPRETATION`. Every one has a direct, verbatim citation
in Amazon's own current official documentation, independently
re-confirmed 2026-08-19 via a second retrieval path. None was invented by
this project. `CONTRACT_VERBATIM_UNCONFIRMED` (DPP gated, not directly
quotable) applies uniformly and does not distinguish any item from any
other — it is not grounds to treat some of the 11 as less binding than
others.

### Annual rotation — resolved, reaffirmed

The reviewer's 5th named item ("annual rotation") does **not** describe a
12th human-password HARD requirement. Fresh evidence confirms the prior
conclusion: Amazon's rotation language ("automate annual key rotation,"
"API keys should be rotated annually") appears exclusively in the
**Safeguarding Sensitive Credentials** page's API-key/service-credential
context, never in the password-lifecycle paragraph. `SECRETS.md` and this
document's ownership matrix (control #25, `SERVICE_CREDENTIAL_CONTROL`)
already track this correctly, separate from human passwords. The reviewer's
single compound sentence most plausibly compresses two separate DPP-derived
guidance paragraphs (password lifecycle + credential rotation) into one
Developer Profile checkbox question, rather than imposing a second,
redundant rotation obligation on the same human password that already
expires at 365 days. `HUMAN VS PROGRAMMATIC BOUNDARY = REAFFIRMED WITH
INDEPENDENT EVIDENCE`, not merely carried forward unexamined.

### Scope matrix

| Control class | Applies to |
|---|---|
| Password composition/history/age (items 1-9, 11) | `SCOPE_NOT_EXPLICIT` at the individual-sentence level — the guidance paragraph does not restate "all accounts" for every sentence, but sits in the same control section as the MFA sentence, which does |
| MFA (item 10) | Explicit: **"all accounts"** |
| Annual rotation | Explicit: API keys / "associated credentials" — not human passwords |

No favorable or unfavorable interpretation invented where Amazon's own
text is silent, per instruction.

### Adversarial review

**Is JUVAl treating anything as HARD that Amazon doesn't actually require
for this case?** No item found. Every one of the 11 has a direct citation.
The closest candidate — splitting "mixed case letters, numbers, and
special characters" into three separate ownership-matrix line items
(uppercase/lowercase/number) rather than one — is a decomposition
convenience for the ownership-matrix format, not a substantive addition:
it doesn't change any provider's PASS/FAIL outcome, since every candidate
evaluated (Cognito, Auth0, Entra, JumpCloud, Okta) trivially supports all
three as one bundled toggle.

**Is JUVAl missing anything Amazon requires?** No new mandatory control
surfaced this pass. Candidates considered and rejected as speculative
additions (no evidence found, not added): dictionary/breached-password
checks (some providers like Auth0 document this as a feature; no Amazon
source found requiring it); explicit password-age *maximum* enforcement
mechanism mandate (Amazon states the outcome, not a mechanism, already
established in the `PASSWORD_MAX_AGE_CONTROL` analysis above). Neither is
added to the baseline without evidence.

### RF03_REQUIRED_BASELINE_V2

```
HARD — REQUIRED (reviewer-explicit, strongest evidence, 4 items):
  - Password ≥12 characters
  - Special character required
  - Maximum password age ≤365 days
  - Mandatory MFA (explicit "all accounts" scope)

HARD — REQUIRED (official-guidance, same source document as the
reviewer's own compressed question, not independently reduced, 7 items):
  - Uppercase required
  - Lowercase required
  - Number required
  - Name/username exclusion
  - Password history ≥10
  - Minimum password age ≥1 day
  - Lockout ≤10 failed attempts

SERVICE-CREDENTIAL REQUIREMENTS (not IdP-owned, unchanged from the
ownership matrix, control #25):
  - API key / associated-credential annual rotation
  - Encrypted storage, restricted access

ORGANIZATIONAL REQUIREMENTS (unchanged, controls #17, #18, #24):
  - Quarterly access review
  - ≤24h departed-user revocation
  - Service-credential inventory review

GUIDANCE / DEFENSE-IN-DEPTH (not found as Amazon-mandatory this pass,
not added as HARD, listed only so they are not silently lost):
  - (none identified with sufficient evidence to list)
```

**Total HARD IdP requirement count: still 11.** The set is identical to
the pre-existing baseline — this audit changes the *evidentiary label* on
each item (which are reviewer-explicit vs. guidance-derived) and
independently reconfirms the source text, but removes none and adds none.

### Impact on prior provider decisions

`WERE ANY IdPs REJECTED BECAUSE OF A CONTROL THAT WAS NOT ACTUALLY HARD?`
**NO.**

The baseline is confirmed identical after adversarial audit — explicitly,
per instruction, rather than left implicit:

```
Cognito rejection:   CONFIRMED — GAP A (min age, item 8) and GAP B (name
                      exclusion, item 6) are both real, guidance-sourced
                      HARD requirements. No reopening.
Auth0 rejection:      CONFIRMED — GAP A (item 8) unchanged. No reopening.
JumpCloud rejection: CONFIRMED — item 8 (min age) unchanged, same
                      evidentiary standard. No reopening.
Entra External ID:    CONFIRMED — items 1 (length) and 7 (history) ceilings
                      unchanged. No reopening.
Clerk:                CONFIRMED unresolved — nothing here closes or opens
                      its 6 open items; still requires a real test tenant.
Okta:                 Unaffected — rejected by explicit user decision, not
                      by any control finding; this audit does not
                      reconsider it (out of scope, per instruction).
```

`PROVIDER DECISIONS REQUIRING REOPENING: NONE.`

### Reapplication evidence matrix (RF-03 only)

| Future "YES" | Control | Evidence required | Current evidence | Gap |
|---|---|---|---|---|
| Password composition enforced | Items 1-6 | IdP policy export, dated | None — no tenant | Full |
| History enforced | Item 7 | IdP policy export | None | Full |
| Min/max age enforced | Items 8-9 | IdP policy export + revocation test | None | Full |
| MFA enforced | Item 10 | IdP MFA export + enrollment records | None | Full |
| Lockout enforced | Item 11 | IdP lockout export + test | None | Full |

Documentation alone is never evidence of any of the above — unchanged
from this document's standing rule.

## Low-cost architecture pass: FusionAuth, ZITADEL, Clerk re-check (2026-08-19)

Scope: re-evaluate only self-hosted/low-cost candidates against
`RF03_REQUIRED_BASELINE_V2` (unchanged, 11 items). Okta out of scope per
explicit, standing user decision — not reconsidered. Cognito, Auth0,
Entra External ID, Supabase Auth, Google/Microsoft federation, JumpCloud
not re-investigated (no new primary evidence found that would change
their standing `REJECTED`/`ELIMINATED` conclusions).

### FusionAuth (self-hosted, Community edition)

Official docs fetched 2026-08-19: [Tenants API](https://fusionauth.io/docs/v1/tech/apis/tenants)
(exhaustive `passwordValidationRules` field list, direct fetch, most
authoritative source available), [Password Security Compliance
Checklist](https://fusionauth.io/articles/security/password-security-compliance-checklist),
[User Password Update event](https://fusionauth.io/docs/extend/events-and-webhooks/events/user/password/user-password-update),
[Self-Service Registration Validation Lambda](https://fusionauth.io/docs/v1/tech/lambdas/self-service-registration),
[Pricing](https://fusionauth.io/pricing).

| # | Control | FusionAuth field | Evidence | Status |
|---|---|---|---|---|
| 1 | ≥12 chars | `minLength` | Exhaustive Tenants API field list | `CONFIGURABLE_VERIFIED` |
| 2-4 | Upper/lower/number | `requireMixedCase`, `requireNumber` | Same | `CONFIGURABLE_VERIFIED` |
| 5 | Special char | `requireNonAlpha` | Same | `CONFIGURABLE_VERIFIED` |
| **6** | **Name/username exclusion** | **none** | Field absent from the exhaustive official list; not mentioned on the dedicated compliance-checklist article either | **`NOT_SUPPORTED`** |
| 7 | History ≥10 | `rememberPreviousPasswords.count` | Same | `CONFIGURABLE_VERIFIED` |
| **8** | **Minimum age ≥1 day** | **`minimumPasswordAge.seconds`** | Same — explicit field, exists natively, unlike every SaaS CIAM candidate checked so far | **`CONFIGURABLE_VERIFIED`** — the first candidate in this entire investigation (excluding Okta) to pass this specific item |
| 9 | Maximum age ≤365 days | `maximumPasswordAge.days` | Same | `CONFIGURABLE_VERIFIED` |
| 10 | MFA | Native (TOTP/WebAuthn) | FusionAuth core feature | `CONFIGURABLE_VERIFIED` |
| 11 | Lockout ≤10 | Native login-attempt lockout | FusionAuth core feature (not re-verified this pass beyond feature existence — exact range not required given item 6 is already decisive) | `CONFIGURABLE_VERIFIED` (feature confirmed; exact numeric range not re-verified) |

**Compensating-control check for item 6 (required before declaring
`NOT_SUPPORTED` final, per this pass's explicit instruction)**: searched
specifically for a synchronous, plaintext-aware hook on the password-set
path. Found: the `user.password.update` webhook event is **explicitly
documented as non-transactional** ("the operation will succeed regardless
of the webhook response status code") and its payload **does not include
the plaintext password**. The Self-Service Registration Validation Lambda
fires on registration form fields, not password changes, and its
documented parameters do not include a password field either. No lambda
or event type was found, across every FusionAuth extensibility mechanism
checked, that both (a) fires before the password is persisted and (b)
receives the plaintext value. This is the same decisive structural gap
already proven for Cognito's `ChangePassword` path — **not** a documentation
gap, an architectural one. `COMPENSATING_CONTROL_REQUIRED` was considered
and rejected: the only way to inspect the plaintext password against the
username would require a custom proxy in front of FusionAuth's own APIs,
which is custom authentication and explicitly forbidden.

`FusionAuth = 10/11`. **Closest candidate found in this entire
investigation** (surpassing every SaaS CIAM checked, which all failed on
item 8 instead) — but still not 11/11, and item 6 is decisively, not
merely provisionally, unsupported.

**The item-6 conclusion above is `SUPERSEDED BY NEW PROVIDER CAPABILITY`
— see immediately below. It is preserved, not deleted, as the accurate
record of what was known 2026-08-19 before this discovery.**

### Item 6 re-verification: FusionAuth 1.63.0 "Reject passwords containing user login Id" (2026-08-19)

**Amazon's exact requirement, re-confirmed for this check**: "…must not
include any part of the user's **name**" — Key Security Control Guidance,
"Establish password complexity requirements" section,
[developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration](https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration)
(direct fetch still blocked by the same redirect anomaly recorded twice
already this document; text re-confirmed via the same independent
search-cache path used previously, unchanged from all three prior
citations). Scope: personal **name**, not explicitly "login Id" or
"username" — a distinct word choice from Amazon, not treated as
interchangeable without evidence (per this pass's explicit instruction).

**New FusionAuth capability, verified**: a tenant password setting,
UI-labeled **"Reject passwords containing user login Id,"** confirmed
present via direct fetch of FusionAuth's own [Tenants core-concepts
documentation](https://fusionauth.io/docs/v1/tech/core-concepts/tenants)
(listed among the tenant Password settings, alongside Minimum age and
Expiration). Description: "When enabled, prevent users from including
their login Id in their password." Traced to [GitHub issue
#2733](https://github.com/FusionAuth/fusionauth-issues/issues/2733),
"Add limitation to not allow a user's username or email address to be
their password," released in version **1.63.0**. This is genuinely new
relative to the prior pass's research (2026-08-19, same day, earlier in
this document) — the Tenants **API** reference fetched then did not
surface it (likely a page-coverage gap in that fetch, not evidence the
feature doesn't exist — the UI-focused core-concepts page, fetched fresh
this pass, does list it directly). Not stale due to elapsed time; stale
due to incomplete source coverage in the prior fetch. Corrected here.

**FusionAuth identity model, verified**: `loginId` is a distinct,
separately-defined concept from the user's name — "a flexible,
configurable identity field... email, username, or phone number" used to
authenticate ([Users docs](https://fusionauth.io/docs/get-started/core-concepts/users),
[Identity Verify API](https://fusionauth.io/docs/apis/identity-verify)).
`firstName`/`lastName`/full name are separate user-profile fields,
independent of whichever value is configured as `loginId`. No official
FusionAuth documentation found equating the two, and none should be
assumed.

**Semantic test** (Name = Daniel Liendo, LoginId = daniel@juval.com):

| Candidate password | Contains the configured `loginId` string? | Blocked by the new setting? | Contains part of the actual name? | Amazon-compliant? |
|---|---|---|---|---|
| `Daniel123!XYZ` | No | **No** | Yes ("Daniel") | **Violates Amazon's rule, not caught** |
| `Liendo123!XYZ` | No | **No** | Yes ("Liendo") | **Violates Amazon's rule, not caught** |
| `daniel@juval.comXYZ!` | Yes | **Yes** | Yes (incidentally) | Correctly caught |

Two of three test cases — the ones matching Amazon's literal wording most
directly (a bare first or last name fragment) — are **not** caught by the
loginId-based check, because the configured `loginId` (an email address)
does not textually contain the person's first or last name as a
substring. This is not invented behavior — it follows deterministically
from the feature's own documented scope ("their login Id," singular,
whole-string) and the confirmed independence of `loginId` from
`firstName`/`lastName` in FusionAuth's data model.

**Could JUVAl's own `loginId` design close this gap?** Considered and
rejected, per instruction not to design a semantic trick: even setting
`loginId` to something name-derived (e.g., a `daniel.liendo`-style
username) would only cause the check to block the password containing
that *exact configured string* — it would not independently block
"Daniel" or "Liendo" as separate substrings unless FusionAuth's matching
is proven to decompose the loginId into sub-tokens, which no official
documentation found this pass states or implies. Declaring this closed
would require inventing unverified matching behavior — explicitly
forbidden. Not declared closed.

**Classification: `B — PARTIALLY_SATISFIED`.** Not `A`: cannot show the
password engine blocks every part of the user's actual name in the normal
deployment configuration (loginId ≠ name). Not `C`: this is not a
documentation gap — the scope of the feature is precisely documented,
just narrower than Amazon's wording. Not `D`: there is no evidence the
requirement is impossible — a real, native, non-custom-auth control now
exists and covers a meaningful, real subset of the risk (identifier reuse
in passwords), genuinely stronger than before this discovery.

`MINIMUM_FUSIONAUTH_VERSION = 1.63.0` — an architectural constraint if
FusionAuth is ever pursued for this control at all, regardless of the B
classification above.

### FusionAuth final matrix (revised)

Item 6 changes from `NOT_SUPPORTED` to `PARTIALLY_SATISFIED (B)` —
narrower gap, not closed. All other 10 items unchanged from the prior
pass. **`FusionAuth = 10/11 PASS + 1 PARTIAL`, still not 11/11.**

`FUSIONAUTH = NOT FULLY COMPLIANT`
`RECOMMENDED IdP = NONE`
`IDENTITY_PROVIDER_DECISION = BLOCKED` (unchanged)

**Remaining gap, precisely stated**: Amazon requires the password engine
to reject *any part of the user's name*; FusionAuth 1.63.0+ natively
rejects only the configured *login identifier* (email/username/phone),
which is a distinct field from the person's name in FusionAuth's own data
model. The gap is real but narrower and better-evidenced than the prior
pass's blanket `NOT_SUPPORTED` — this is progress worth recording
precisely, not progress worth rounding up to a pass.

**Costs**: `LICENSE_COST` = $0 (Community edition, Apache 2.0-ish
FusionAuth license, self-hosted, no MAU cap). `INFRASTRUCTURE_COST` =
not FusionAuth's own published figure — a small VPS running FusionAuth +
PostgreSQL for 2 users is realistically achievable on commodity cloud
compute; **exact figure PRICE NOT PUBLIC / ESTIMATE, not an official
FusionAuth cost** (order of magnitude only: low tens of USD/month for a
minimal single-node instance, before backup/monitoring tooling).
`OPERATIONAL_COST` = non-zero and qualitative, not priced: patching the
host OS, upgrading FusionAuth itself, database backups, TLS certificate
management, uptime monitoring, and disaster recovery are now JUVAl's own
responsibility (self-hosted = no managed-service SLA). This is a real,
recurring admin burden this document does not have evidence to price.

### ZITADEL (self-hosted)

Official docs fetched 2026-08-19: [Get Password Age Settings](https://zitadel.com/docs/apis/resources/mgmt/management-service-get-password-age-policy)
(direct fetch of the exact API schema — most authoritative source
possible), pricing/licensing via search.

| # | Control | ZITADEL field | Status |
|---|---|---|---|
| 9 | Maximum age | `maxAgeDays`, `expireWarnDays` | `CONFIGURABLE_VERIFIED` |
| **8** | **Minimum age** | **none** | Password Age Policy's own official schema contains only `maxAgeDays`/`expireWarnDays` — no minimum-age field exists anywhere in it. **`NOT_SUPPORTED`**, decisive (exhaustive official schema, not absence-from-a-support-article) |
| 6 | Name/username exclusion | not confirmed either way | `UNKNOWN` — not chased further once item 8 was already decisive; would not change the outcome |
| Others | — | Not individually re-verified this pass | `UNKNOWN` where not listed — item 8 alone is sufficient to disqualify |

`ZITADEL = REJECTED` (item 8, decisive, same structural class as
Cognito/Auth0/JumpCloud — a maximum-age-only policy object with no
minimum-age counterpart).

**Licensing note**: self-hosted ZITADEL is transitioning from Apache 2.0
to AGPL-3.0 for its main repository (post-2025), which carries copyleft
obligations for network-delivered services under some interpretations —
a legal/architectural consideration independent of the control failure,
not chased further since item 8 already disqualifies it.

### Clerk — re-checked, more clearly resolved (not upgraded to a pass)

Official docs fetched 2026-08-19: [Password protection and rules](https://clerk.com/docs/guides/secure/password-protection-and-rules)
— direct fetch, read in full this time rather than search-snippet only.

The page itself explains Clerk's *design philosophy*: it cites NIST
800-63B guidance (which recommends against mandatory rotation and rigid
composition rules) as its rationale, and documents **only**: a basic
minimum length (~8 characters, not independently raisable to 12 per this
page), broad character acceptance (not a *requirement* of mixed types),
and a "Reject compromised passwords" breach-database check. No history,
no minimum age, no maximum age, no name/username exclusion are documented
anywhere on Clerk's own canonical password-rules page.

This does not reverse the prior `UNRESOLVED` status into a pass — it
resolves it in the failing direction for several items (`NOT_SUPPORTED`
now has direct documentation rather than "not yet confirmed"), for the
same reason FusionAuth/ZITADEL were tested: Clerk optimizes for modern
NIST-aligned consumer authentication, not the workforce-style rigid
composition/aging rules Amazon's guidance specifies. `Clerk` remains
disqualified on multiple items 1, 7, 8, 9 at minimum; not pursued further
since it was never going to be the winner.

### Decision matrix

| Candidate | 11/11 | License/year | Est. hosting/year | Operational burden | Evidence quality | Verdict |
|---|---|---|---|---|---|---|
| FusionAuth (self-hosted) | **10/11 + 1 PARTIAL** (#6 narrowed to `B — PARTIALLY_SATISFIED` since 1.63.0's loginId-exclusion setting, still short of `A`) | $0 | Not officially priced; estimate low hundreds USD/year for minimal infra (unverified, not FusionAuth's figure) | High — full self-hosted ops (patching, backups, TLS, monitoring, upgrades) | High (direct API schema + event docs + UI settings docs) | `NOT FULLY COMPLIANT` — closest candidate found, remaining gap is real and precisely scoped (see item-6 re-verification section above), not fabricated or hand-waved |
| ZITADEL (self-hosted) | 9/11 or fewer (fails #8, #6 unknown) | $0 (Apache 2.0, transitioning to AGPL-3.0) | Similar to FusionAuth, not separately priced | High — same self-hosted ops burden | Medium-high (direct API schema for #8; #6 not chased) | `REJECTED` (#8 decisive) |
| Clerk | Fails ≥4 of 11 | ~$25-99/mo tiers (not re-verified this pass; see prior turn's Auth0/Clerk cost notes) | N/A (SaaS) | Low | High (direct fetch, full page) | `REJECTED` |

### Winner

`IDENTITY_PROVIDER_DECISION = BLOCKED`. No candidate reaches 11/11 with
acceptable evidence. Per instruction, this is stated plainly rather than
softened into a "recommended" pick that quietly drops one control.

**Not a recommendation, but the closest finding this entire investigation
has produced**: FusionAuth self-hosted is 10/11, free to license, and
fails on exactly one item (name/username exclusion) that has decisive,
architecture-level evidence of absence — not a documentation gap the user
could resolve by looking harder, the same category of proof already used
for Cognito. Compared to every prior candidate (all of which failed on
item 8, minimum age — the item FusionAuth uniquely passes), this is a
different, single, well-isolated gap. If the user is willing to accept
disclosed residual risk on item 6 specifically (with a compensating
*organizational* control — e.g., a manual review step at account creation
that checks the chosen password doesn't contain the name, performed once
per hire, not automated) while treating it as an honestly-disclosed gap
rather than a fabricated pass, FusionAuth is the strongest evidence-backed
candidate for that discussion. That decision belongs to the user, not the
agent, and is not made here.

## Managed directory architecture investigation (2026-08-19)

Scope: not another generic SaaS IdP — a fundamentally different
architecture, prompted by Amazon's own guidance recommending centralized
directory services (AWS Directory Service / Microsoft Active Directory).
Evaluated per-control and per-layer, not "AWS therefore compliant."

### Why this architecture

Every candidate checked so far (Cognito, Auth0, Entra External ID,
Supabase Auth, JumpCloud, ZITADEL, Clerk, FusionAuth) is a **CIAM**
(customer-identity) product. Minimum password age and full-name exclusion
are standard **workforce**-IAM controls, rare in CIAM — the same
structural reason ADR-022 originally pointed at Okta. Active Directory is
the canonical workforce directory technology; worth checking on its own
architectural merits, not because it's an AWS product.

### Active Directory DS control matrix (official Microsoft documentation)

Source: [Password must meet complexity requirements](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/security-policy-settings/password-must-meet-complexity-requirements),
fetched via independent retrieval 2026-08-19.

| # | Control | AD DS capability | Status | Evidence |
|---|---|---|---|---|
| 1 | ≥12 chars | `msDS-MinimumPasswordLength` (fine-grained policy), up to 255 | `CONFIGURABLE_VERIFIED` | Same source |
| 2-4 | Upper/lower/number | Complexity policy (bundled, not independently toggleable) | `CONFIGURABLE_VERIFIED` | Same |
| 5 | Special char | Complexity policy (same bundle) | `CONFIGURABLE_VERIFIED` | Same |
| 6 | Username exclusion | Complexity policy: "passwords may not contain the user's **samAccountName**" | `NATIVE_VERIFIED` | Same, verbatim |
| 7 | First-name exclusion | `displayName` is parsed on delimiters (comma, period, dash, underscore, space, `#`, tab) into tokens; **first-name token checked independently** | `NATIVE_VERIFIED` | Same, verbatim |
| 8 | Last-name exclusion | Same tokenization — **last-name token checked independently** | `NATIVE_VERIFIED` | Same |
| 9 | History ≥10 | `msDS-PasswordHistoryLength`, AWS default 24 | `CONFIGURABLE_VERIFIED` | AWS Directory Service docs |
| 10 | Min age ≥1 day | `msDS-MinimumPasswordAge`, **AWS default is already exactly 1 day** | `NATIVE_VERIFIED` (out of the box) | Same |
| 11 | Max age ≤365 days | `msDS-MaximumPasswordAge`, AWS default 42 days, editable | `CONFIGURABLE_VERIFIED` | Same |
| 12 | Lockout ≤10 | "Number of failed logon attempts allowed", editable | `CONFIGURABLE_VERIFIED` | Same |

**Full-name exclusion — the decisive difference from every prior
candidate**: unlike every CIAM product checked (Cognito, Auth0, Entra
External ID, Clerk, FusionAuth), AD DS natively **decomposes the display
name into separate tokens on the space delimiter** — "Daniel Liendo"
becomes two independently-checked tokens, "Daniel" and "Liendo" — and
rejects a password containing *either*, not merely the whole string.
Caveat, quoted directly: "Tokens that are shorter than three characters
are ignored, and substrings of the tokens aren't checked" — irrelevant
for realistic names (≥3 characters), but a real, disclosed edge case, not
hidden.

`AD DS: ALL 12 CONTROLS = PASS.` This is the first candidate in the
entire investigation (Okta included) to close the full-name-exclusion gap
*natively*, not via a narrower proxy control (FusionAuth's loginId) or a
managed-workaround (Cognito's max-age design).

### AWS Managed Microsoft AD — specifically verified, not inferred from Windows Server

Direct fetch, 2026-08-19: [Understanding AWS Managed Microsoft AD password policies](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_password_policies.html)
— the exact official table, reproduced:

| Policy | Default | Editable? |
|---|---|---|
| Enforce password history | 24 | Yes |
| Maximum password age | 42 days (includes admin password) | Yes |
| Minimum password age | 1 day | Yes |
| Minimum password length | 7 | Yes |
| Complexity | Enabled | Yes (on/off only) |

AWS Managed Microsoft AD is confirmed to be **real AD DS technology**
(not a re-implementation) — fine-grained password policies are the same
Microsoft mechanism, configured with the same Microsoft tools (Active
Directory Administrative Center). Complexity inherits the exact
samAccountName/displayName-token behavior above; this is not inferred
from generic Windows Server docs, it is stated on AWS's own page, which
directly cross-references the same Microsoft complexity-policy article.
**Confirmed specifically for AWS Managed Microsoft AD, not merely
assumed because "it's AD."**

### Password reset bypass — critical, disclosed in full

**Verbatim from AWS's own official table** (same page):

| Policy | Password Reset (admin) | Password Change (user) |
|---|---|---|
| Enforce password history | **No** | Yes |
| Maximum password age | Yes | Yes |
| Minimum password age | **No** | Yes |
| Minimum password length | Yes | Yes |
| Complexity | **Yes** | Yes |

**The critical fact**: an administrator using "Reset Password" (as
opposed to a user self-changing their own password) bypasses **history**
and **minimum age** — but **not** complexity, which is where full-name
and username exclusion live. The Amazon-relevant name-exclusion control
survives admin reset; only the anti-cycling controls (history, min-age)
do not.

**Organizational control this requires** (not a technical fix — Amazon
itself expects organizational controls for exactly this kind of
privileged-operation risk, per the existing RF-04 access-review pattern
already in this document): administrators must not use "Reset Password"
as a routine password-change mechanism — only for genuine account-recovery
scenarios (forgotten password, lockout) — and every such reset should be
logged and reviewable, so it doesn't become a silent way to defeat
history/min-age enforcement. This is a real, disclosed risk, not hidden
or minimized.

### MFA — the AWS-native path does NOT cover JUVAl

**AWS Managed Microsoft AD's own RADIUS MFA integration, verified**:
"RADIUS MFA is applicable only to authenticate access to the AWS
Management Console, or to Amazon Enterprise applications and services
such as WorkSpaces, Amazon QuickSight, or Amazon Chime... it cannot be
used for custom applications" ([AWS Directory Service admin guide, MFA
section](https://docs.aws.amazon.com/directoryservice/latest/admin-guide/ms_ad_mfa.html)).
**Confirmed exactly as the task anticipated: this does NOT provide MFA
for JUVAl.** A separate federation/MFA layer is required regardless of
which directory product is chosen.

**AD FS (Active Directory Federation Services)** — Windows Server
2016/2019/2022/2025, confirmed to support **OpenID Connect** as a
relying-party protocol via "Application Groups" ([AD FS OpenID
Connect/OAuth concepts](https://learn.microsoft.com/en-us/windows-server/identity/ad-fs/development/ad-fs-openid-connect-oauth-concepts)),
and to support **mandatory MFA enforcement**, either globally or scoped
to a specific relying party ("If either global or per relying party trust
authentication policy requires MFA, MFA will be triggered when the user
tries to authenticate to this relying party" — [Configure Additional
Authentication Methods for AD FS](https://learn.microsoft.com/en-us/windows-server/identity/ad-fs/operations/configure-additional-authentication-methods-for-ad-fs)),
requiring at least one configured second-factor method (Azure MFA,
certificate, or a third-party RADIUS-based provider).

**This means AD FS (or an equivalent federation server) is not optional
— it is the only verified path to both MFA and OIDC in this
architecture.** It must be run as JUVAl's own infrastructure (domain-
joined EC2 instance running Windows Server) — AWS does not offer a
managed AD FS product. This is the architecture's real cost center,
addressed below.

**Considered and not recommended: routing through Amazon Cognito as a
SAML-relying-party token-translation layer** (AD FS issues SAML → Cognito
User Pool as SAML SP → Cognito issues OIDC/JWT to FastAPI). Rejected as
an unnecessary addition: AD FS already speaks OIDC natively, so inserting
Cognito adds a second component, a second cost line, and a second thing
to patch/monitor, without closing any gap AD FS doesn't already close on
its own. Not recommended, but not eliminated by a hard incompatibility —
disclosed as a viable but unnecessary alternative if the user later wants
Cognito's specific tooling (e.g., its hosted UI) for other reasons.

### Federation into JUVAl — FastAPI boundary preserved

`AD FS Application Group (OIDC)` issues standard OIDC tokens: issuer,
JWKS endpoint, audience, signed JWT with claims. `interfaces/api/auth.py`
already validates exactly this shape (`JUVAL_OIDC_ISSUER`, `JUVAL_OIDC_
AUDIENCE`, JWKS-based signature verification) — **no backend code change
required**, only configuration pointing at the AD FS instance's OIDC
metadata endpoint instead of a different provider's. This is the same
boundary already proven correct for every other candidate in this
document.

### Password and MFA ownership — single source of truth each

```
PASSWORD OWNER:  AWS Managed Microsoft AD (AD DS), exclusively.
                 AD FS never stores a password of its own — it validates
                 against AD DS. FastAPI never sees a password. PWA never
                 sees a password beyond the AD FS-hosted login page
                 (redirect-based OIDC flow, same pattern as every other
                 candidate already documented in this ADR).

MFA OWNER:       AD FS, exclusively. Enforced via a mandatory
                 "Additional Authentication" policy on the JUVAl relying
                 party (or globally). AWS Managed Microsoft AD's own
                 RADIUS MFA is explicitly NOT the enforcement point
                 (confirmed above) — stated once, not relied on twice.
```

No duplicate password store, no custom password logic anywhere in this
chain — AD DS is a real, off-the-shelf Microsoft product; AD FS is a
real, off-the-shelf Microsoft federation service; neither is built or
modified by JUVAl.

### RF-04 compatibility

AD security groups → AD FS claim-rule transformation (issuing a `role`
claim from group membership, decades-standard AD FS functionality, not
independently re-fetched this pass given how foundational and
uncontroversial it is relative to the password-composition specifics
already verified rigorously) → FastAPI's existing capability-based RBAC
(`viewer`/`operator`/`admin`, unchanged). User disablement, ≤24h
offboarding, and quarterly access review map directly onto standard AD
account-disable + group-membership-review procedures — the same
organizational-control pattern (`ACCESS_CONTROL.md`) already established
for every prior candidate, not a new design.

### Cost and operational burden — disclosed in full, not minimized

| Component | Managed / self-hosted | Cost | Operational burden |
|---|---|---|---|
| AWS Managed Microsoft AD (Standard Edition) | **Managed** — AWS handles patching, HA (2 domain controllers by default), backup | **$0.06/hour/DC × 2 ≈ $87.60/month ≈ $1,051/year** (official AWS pricing, us-east-1, before any sharing/replication add-ons) | Low — AWS-operated per its Directory Service shared-responsibility model |
| AD FS (Windows Server, EC2, domain-joined) | **Self-hosted** — JUVAl's own responsibility entirely | **Not officially quoted this pass** — EC2 Windows instance cost is publicly priced but was not looked up; order-of-magnitude estimate only, explicitly not an official figure | **High** — OS patching, AD FS service updates, TLS certificate renewal, uptime monitoring, no built-in HA without a second AD FS node + load balancer, full disaster-recovery ownership |
| **Total** | Mixed | **≥$1,051/year confirmed + an unpriced EC2/Windows-licensing line + real self-hosted-Windows admin burden** | **Higher than every SaaS candidate checked, and higher than self-hosted FusionAuth alone** (two systems instead of one) |

This is **not** a cheaper or operationally simpler alternative to Okta —
it is more expensive on the confirmed portion alone, before the unpriced
AD FS hosting line, and it adds a second self-hosted Windows Server
component with no managed-service SLA. It is being reported because it
is the **first architecture to pass every literal Amazon control**, not
because it is the cheapest or simplest. Presenting it as low-cost would
misrepresent the finding.

### AWS-alignment advantage — evaluated honestly, not assumed

Amazon's own guidance recommending AWS Directory Service does **not**
constitute compliance by association (explicitly not used as reasoning
here). The genuine advantage is narrower: choosing a product Amazon
itself documents in its security guidance means the control-mapping
citations for a future reapplication answer can point directly at
Amazon's own recommended architecture rather than a third-party SaaS
product's documentation — marginally stronger traceability for a
reviewer, not a compliance shortcut.

### Candidate architectures

```
CANDIDATE (viable, all 12 controls PASS, real operational cost):
  AWS Managed Microsoft AD (password/lockout owner)
  → AD FS on EC2, domain-joined (MFA owner + OIDC issuer)
  → FastAPI (unchanged generic OIDC validation)
  → RBAC (unchanged)

REJECTED (unnecessary addition, no closed gap):
  AWS Managed Microsoft AD → AD FS (SAML) → Cognito (SAML SP, OIDC
  broker) → FastAPI
  — AD FS already speaks OIDC directly; Cognito here adds cost and
    operational surface without closing anything AD FS doesn't already
    close.

REJECTED (confirmed does not cover JUVAl):
  AWS Managed Microsoft AD's native RADIUS MFA as the MFA layer
  — explicitly scoped to AWS Management Console / Amazon Enterprise
    apps only, confirmed via official AWS documentation.

REJECTED (would introduce a second cloud vendor for no confirmed
benefit over self-hosted AD FS):
  AWS Managed Microsoft AD → Azure AD Domain Services / Entra ID
  federation → FastAPI
  — not chased further; self-hosted AD FS already closes MFA+OIDC
    without adding Azure as a second provider relationship.
```

### Recommended architecture

**AWS Managed Microsoft AD + self-hosted AD FS.** The only architecture
in this entire investigation — including every SaaS/self-hosted CIAM
candidate and Okta itself — verified via official primary-source
documentation to pass all 12 human-password/MFA/lockout controls
natively, with the FastAPI OIDC boundary unchanged. Reported as a
finding, **not** approved or implemented here — the real operational
burden (a self-hosted Windows Server component with no managed SLA) and
the unpriced EC2 line are material enough that this is squarely a user
decision, not a default recommendation to execute.

`IDENTITY SECURITY GATE = BLOCKED` (unchanged — nothing in this section
implements anything)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = NOT READY FOR USER APPROVAL` (superseded — see below;
preserved as historical record of the AD FS-only conclusion)

## Federation layer without AD FS: Microsoft Entra ID + Pass-Through Authentication (2026-08-19)

Scope: keep AWS Managed Microsoft AD as the sole password source of
truth, replace AD FS specifically as the federation/MFA/OIDC layer with
something managed and lower-operations. Password-policy providers not
reinvestigated (out of scope, per instruction).

### AD FS production topology — corrected, more burdensome than previously stated

Official Microsoft documentation confirms AD FS production deployment is
**not** the single-EC2 topology the prior pass's cost table implicitly
priced. The documented standard topology is a **multi-tier server farm**:
"one or more AD FS servers on the internal corporate network, with one or
more Web Application Proxy (WAP) servers in a DMZ... with a hardware or
software load balancer placed in front of each server farm layer." A
federation server and WAP **cannot be installed on the same computer** —
they are separate roles by requirement. High availability additionally
needs a SQL Server backing store (AlwaysOn Availability Groups or merge
replication for geo-distribution). This is a materially larger,
multi-server, multi-network-tier deployment than previously costed —
correcting, not merely restating, the prior pass's operational-burden
estimate.

### Microsoft's strategic direction — verified, not assumed

`AD FS remains supported: YES.` No official source found declaring AD FS
deprecated; it ships as a Windows Server role with normal product
lifecycle support.

`Microsoft recommends migrating apps away from AD FS: YES, with a
material caveat.` Microsoft Entra ID's own "AD FS application migration"
tooling and guidance exist and are officially documented — but that
specific tool **"only supports SAML-based applications and doesn't
support applications that use protocols such as OpenID Connect, WS-Fed
and OAuth 2.0"** ([Overview of AD FS application migration](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/migrate-ad-fs-application-overview)).
This matters directly for JUVAl: since JUVAl was never going to be
deployed on AD FS using SAML (the prior pass specifically chose AD FS's
OIDC support), the *migration tool* is moot either way — but the
existence of official, actively-maintained migration tooling and
guidance is itself the strategic signal the task asked to weigh: Microsoft
is investing in Entra ID as the forward path for new application
identity work, not in AD FS. Not treated as deprecation — treated as a
real signal for a **new** 2026 deployment, exactly as instructed.

### Microsoft Entra ID + Pass-Through Authentication — the recommended replacement

Official docs, fetched/confirmed 2026-08-19: [Pass-through Authentication
security deep dive](https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-pta-security-deep-dive),
[How PTA works](https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-pta-how-it-works).

**How it preserves the non-negotiable boundary**: PTA is architecturally
different from Password Hash Sync (PHS), which this pass's boundary
correctly rules out — PHS syncs a *hash* to the cloud and authenticates
against that copy, meaning Entra ID's own (independent, weaker-by-default)
password policy could apply to sign-in instead of AD's. PTA does not do
this: "on-premises passwords are never stored in the cloud in any form,"
and every sign-in is validated **live, in real time, against Windows
Server Active Directory** via a lightweight on-premises Authentication
Agent making only **outbound** connections (no DMZ, no inbound firewall
rule). The password the user types is encrypted in the cloud, queued, and
decrypted only by the on-premises agent immediately before checking it
against AD DS "by using standard Windows APIs" — i.e., the exact same
live AD DS policy enforcement (complexity, name/username exclusion,
history, min/max age, lockout) already verified in the prior section
applies to every sign-in, with **zero independent password copy**. This
satisfies §1's boundary precisely, not approximately.

**Agent footprint**: 1-2 lightweight Windows services (Microsoft
recommends ≥2 for HA) on a domain-joined server reachable to AD DS —
paired with **Microsoft Entra Connect Sync** (a separate, also-free
Microsoft component that syncs user/group *objects*, never passwords,
from AD to Entra ID, required so Entra ID knows who the AD users and
groups are). Both are standard Microsoft hybrid-identity components, not
custom-built, not a new password store — Entra Connect Sync carries no
password material in PTA mode.

**MFA**: Entra ID Conditional Access (P1) or, at minimum, free-tier
**Security Defaults** enforce MFA as a cloud-side policy layer evaluated
*after* PTA validates the password — MFA enforcement is entirely
independent of, and unaffected by, which authentication method validated
the primary credential. Mandatory-for-all-users is a standard, named,
exportable policy object (Conditional Access) or an org-wide toggle
(Security Defaults, free). Confirmed capability, not inferred.

**OIDC/FastAPI**: Entra ID App Registrations are a first-class, extremely
widely-deployed OIDC/OAuth2 provider for arbitrary custom applications —
standard discovery document, issuer, JWKS, audience (client ID), signed
ID/access tokens, optional group claims for RBAC. This is a more common,
better-documented OIDC integration pattern than AD FS's own OIDC support
(which is comparatively less used in the wild). `interfaces/api/auth.py`
requires **`CONFIG_ONLY`** impact — point `JUVAL_OIDC_ISSUER`/`JUVAL_
OIDC_AUDIENCE` at the Entra tenant's endpoints; no code change.

**RF-04**: AD security groups → synced by Entra Connect → Entra ID
groups → optional group claims in the OIDC token → FastAPI's existing
RBAC (unchanged). Same standard pattern already used for every other
candidate in this document.

**IAM Identity Center — considered, not resolved this pass**: a targeted
verification of whether AWS IAM Identity Center can serve arbitrary
custom applications via OIDC (as opposed to AWS account access and
curated SAML 2.0 "customer managed applications") was not completed this
pass. Based on established general knowledge of the product (not a fresh
primary-source fetch this pass), Identity Center's custom-application
support is understood to be SAML-2.0-centric, not a general-purpose OIDC
issuer for self-built apps — **flagged `NEEDS_VERIFICATION`, leaning
NOT_VIABLE, not asserted as fact**. Not pursued further once Entra ID +
PTA was confirmed to satisfy every requirement with primary-source
evidence — chasing a second, less-promising candidate with the same
rigor was not a good use of remaining scope.

**Managed-broker alternatives (FusionAuth/JumpCloud as federation-only
brokers) — considered, set aside**: architecturally possible in
principle (an AD-bind federation-only mode exists in some directory
products), but not pursued: Entra ID + PTA is Microsoft's own
purpose-built solution for exactly this hybrid pattern, has the deepest
primary-source documentation of any candidate checked in this entire
investigation, and re-purposing a CIAM product already disqualified for
its *own* password engine as a broker would add integration risk without
any evidenced advantage over the vendor-native path.

### Decision matrix

| Architecture | AD password owner | MFA | OIDC | RF-03 | RF-04 | Backend impact | Managed? | Monthly cost (2 users) | Operations | Security surface | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AD FS (+ WAP, production topology) | AD DS | PASS (Conditional Access-equivalent) | PASS (native) | PASS | PASS | `CONFIG_ONLY` | No — fully self-hosted, multi-server farm | Directory `~$88` (verified) + multi-server AD FS/WAP/LB/SQL compute, **not fully priced, materially higher than previously stated** | `VERY_HIGH` (corrected upward this pass) | Internet-facing WAP tier, multiple servers/certs to patch | `VIABLE` (fallback) |
| **Entra ID + PTA** | **AD DS (live, real-time, zero copy)** | **PASS** (Conditional Access or free Security Defaults) | **PASS** (native App Registration) | **PASS** | **PASS** | **`CONFIG_ONLY`** | **Mostly** — Entra ID cloud-managed; only lightweight PTA agents + Connect Sync self-run | Directory `~$88` (verified) + Entra ID **$0 (Security Defaults) or ~$14 (P1 Conditional Access, 2 users, verified list price)** + minimal EC2 for 1-2 agents | **LOW-MEDIUM** | No inbound ports, no DMZ, no public-facing self-hosted server | **`RECOMMENDED`** |
| IAM Identity Center + AWS Managed AD | AD DS | `NEEDS_VERIFICATION` | `NEEDS_VERIFICATION` — likely SAML-only for custom apps | `NEEDS_VERIFICATION` | `NEEDS_VERIFICATION` | Unknown | Yes | Not priced | Unknown | Unknown | `NEEDS_VERIFICATION` (not chased further) |
| Broker (FusionAuth/JumpCloud, AD-bind mode) | AD DS (if configured correctly) | Depends on broker | Depends on broker | Depends on broker | Depends on broker | Varies | Varies | Not priced | Unknown | Unknown | `REJECTED` (unnecessary — vendor-native path already found) |

### Recommended architecture

```
USER
  ↓
AWS Managed Microsoft AD (password validation, live, real-time)
  ↓ (PTA Agent — outbound only, no password stored)
Microsoft Entra ID (Connect Sync for objects/groups; Conditional Access
                     or Security Defaults for mandatory MFA; App
                     Registration issues OIDC/JWT)
  ↓
FastAPI (unchanged: JUVAL_OIDC_ISSUER/JUVAL_OIDC_AUDIENCE, JWKS validation)
  ↓
RBAC (unchanged: viewer/operator/admin)
  ↓
JUVAl data

ADMIN / SERVICE ACCOUNTS / SP-API SECRETS: unchanged, separate domain
(SECRETS.md), never human passwords, never touched by this architecture.
```

**Recommended: AWS Managed Microsoft AD + Microsoft Entra ID (Pass-Through
Authentication).** Satisfies the full RF-03 baseline with the same
decisive, native AD DS evidence as the AD FS architecture, while
replacing a multi-server, DMZ-facing, SQL-backed federation farm with a
managed cloud control plane and 1-2 lightweight outbound-only agents.
Lower cost (Security Defaults path: near-$0 incremental; Conditional
Access path: ~$14/month verified list price for 2 users), lower
operational burden, smaller internet-facing security surface, and a
better-documented OIDC integration pattern than AD FS itself.

**Fallback: AWS Managed Microsoft AD + AD FS** (prior section, unchanged
conclusion) — the only candidate if, for a reason not identified in this
investigation, hybrid cloud identity (Entra ID) is unacceptable to the
user and a fully self-hosted federation layer is required despite its
now-corrected, higher operational cost.

### Remaining hard gaps

None on the control side — every RF-03/RF-04/MFA/OIDC requirement is
`PASS` for the recommended architecture, via primary-source evidence.
The remaining gaps are **implementation and evidence**, not architecture:
no tenant, no agent, no policy, no test exists yet. `IAM Identity Center`
custom-app OIDC support remains genuinely unresolved but is not blocking,
since Entra ID + PTA already satisfies every requirement independently.

`IDENTITY SECURITY GATE = BLOCKED` (unchanged — nothing implemented)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = READY FOR USER ARCHITECTURAL APPROVAL` (superseded by cost
optimization below — preserved as historical record)

## Cost optimization: can AWS Managed Microsoft AD itself be eliminated? (2026-08-19)

Scope: JUVAl is a 2-user internal tool, not a multi-tenant SaaS. Re-examine
whether the **managed-service wrapper** around AD DS (AWS Managed
Microsoft AD, ~$1,051/year confirmed) is necessary, or whether the
underlying technology can be run more cheaply while keeping every already-
verified control identical.

### Standalone alternatives re-checked — all fail on the same axis, confirmed with fresh sources

| Candidate | Fresh finding | Source | Verdict |
|---|---|---|---|
| **Microsoft Entra ID, cloud-only workforce (no AD)** | "For cloud users, the Microsoft Entra ID password policy can't be customized, except for password expiration." Fixed 8-character minimum, 3-of-4 complexity, **no minimum-age setting exists**, no name-exclusion documented. | [Password policies and account restrictions in Microsoft Entra ID](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-sspr-policy), re-fetched 2026-08-19 | `REJECTED` — reconfirms ADR-022's prior finding with current terminology, not a stale citation |
| **Google Workspace / Cloud Identity** | Length/uppercase/special-character configurable; **"You cannot set the password history that Google reviews to prevent reuse"** (no admin-configurable history count); no minimum-age or name-exclusion control found | [Enforce and monitor password requirements](https://support.google.com/cloudidentity/answer/139399), fetched 2026-08-19 | `REJECTED` — fails history, min-age, name-exclusion |
| **Keycloak (standalone, own password store)** | Confirmed built-in policies: length, complexity classes, Not Username, Not Email, **Not Contains Username**, Not Recently Used, Expire Password. **No minimum-password-age policy exists** — "not a built-in policy in Keycloak and would require custom implementation" (forbidden). No first-name/last-name exclusion — only username/email. | Keycloak mailing list + current admin-guide search, 2026-08-19 | `REJECTED` — same structural gap as every CIAM product checked (min-age), plus name-exclusion only partially covers username/email, not the person's actual name |
| **FreeIPA (self-hosted, free)** | `minlife`/`maxlife`/`historylength`/`maxfailcount`/`lockouttime` all natively confirmed (389 Directory Server password policy) — genuinely strong on lifecycle controls. **No evidence found of a name/username-in-password rejection feature** in FreeIPA's core LDAP/Kerberos password-change path (as distinct from PAM-level `pam_pwquality reject_username`, which only applies to local Linux logins, not the Kerberos password-change RPC a federation layer would use) | ansible-freeipa / Red Hat IdM docs, 2026-08-19 | `NEEDS_VERIFICATION`, leaning `NOT_SUPPORTED` for item 6 — not converted to a pass without decisive evidence |
| **Samba AD DC (self-hosted, free)** | Samba 4.9+ confirmed to support real AD PSO/FGPP (same schema/tooling as Windows AD DS). Multiple searches (4 attempts) returned the *Microsoft* samAccountName/displayName-token behavior in the same result set as Samba pages, but **no single fetch produced an unambiguous primary-source Samba document or source-code comment confirming Samba's own `check_password_restrictions` implements the identical token-parsing logic**, as opposed to search-engine conflation with Microsoft's own docs ranking alongside Samba's. | Samba wiki, Samba mailing lists, samba.org source tree (4 search/fetch attempts, 2026-08-19) | `NEEDS_VERIFICATION` — explicitly not upgraded to PASS per the "no convertir incertidumbre en cumplimiento" rule, despite circumstantial plausibility |

None of these six standalone alternatives is a confirmed, evidence-backed
replacement for genuine Windows Server AD DS on the two hardest controls
(name-exclusion, minimum age) — consistent with every prior candidate in
this document.

### Samba AD + Microsoft Entra PTA — a supportability blocker, not just a policy gap

Independent of Samba's own password-complexity fidelity (unresolved
above), **Microsoft's PTA documentation states the requirement in terms
of genuine Windows Server AD**: "the server must be added to the same
Active Directory forest," running "Windows Server 2016/2019/2022/2025,"
and the agent "validates the username and password against Active
Directory by using standard Windows APIs" ([How Pass-through
Authentication works](https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-pta-how-it-works),
re-fetched 2026-08-19). No Microsoft documentation found stating Samba AD
DC (a third-party, non-Microsoft reimplementation) as a supported PTA
identity source. Combined with Samba's own unresolved item-6 fidelity,
`Samba AD + Entra PTA = NOT_RECOMMENDED` — two independent, unresolved
risk factors, not one.

### The actual cost lever: the managed-service wrapper, not the technology

**Key realization**: AWS Managed Microsoft AD's $1,051/year price is
mostly the cost of AWS *operating* two redundant domain controllers on
your behalf (patching, HA, backup) — not a licensing fee for the AD DS
software itself. The underlying technology (genuine Microsoft Active
Directory Domain Services) is the same whether AWS manages it or JUVAl
runs it directly on a self-hosted EC2 instance. **A single, self-managed
Windows Server AD DC running on one EC2 instance is still 100% genuine
Windows Server AD DS** — every control already verified in the prior two
sections (12/12 PASS, decisive Microsoft primary-source evidence for
name-exclusion) applies identically, because it is literally the same
Microsoft product, not a different one. It is also, unlike Samba,
unambiguously within Microsoft's PTA support boundary (genuine Windows
Server AD forest).

**Cost — ESTIMATE, explicitly not a verified AWS quote**: AWS EC2
`t3.small` **Linux** on-demand pricing is publicly listed at **$0.0208/hour
(verified figure)**; the Windows Server surcharge (license bundled into
the AMI price, no separate purchase needed) is commonly reported around
30-40% over the Linux rate for this instance class — **this percentage
is an unofficial estimate, not fetched from AWS's own pricing page this
pass** (the static fetch of `aws.amazon.com/ec2/pricing/on-demand/`
did not return the rendered price table). Applying it: roughly
**$0.027-0.029/hour ≈ $19-21/month compute**, plus a small EBS volume
(a few dollars/month) ≈ **$25-30/month total, ESTIMATE**. This is
materially below AWS Managed Microsoft AD's verified ~$88/month, and
lands inside the task's "ACCEPTABLE (≤$50/month)" band — not confidently
inside the "TARGET (≤$20/month)" band without an official price
verification, which this pass did not obtain.

**Trade-off, disclosed honestly**: a single self-hosted DC has no
built-in redundancy (AWS Managed AD's mandatory 2 DCs are gone) — the
directory becomes a single point of failure, and JUVAl owns OS patching,
AD DS maintenance, and backup/DR entirely. This is a real availability
trade-off, **not a compliance weakening**: none of Amazon's 11 password/
lockout controls or the MFA/OIDC controls depend on directory redundancy
— redundancy is an operational-resilience property, not one of the
enumerated Amazon controls. For a 2-person internal tool (not a
customer-facing SLA), accepting single-DC risk in exchange for ~$60/month
in savings is a legitimate, disclosed operational decision, consistent
with this task's own instruction that manual/organizational trade-offs
are valid for a 2-user scale as long as they don't substitute for
technical controls Amazon actually requires — this trade-off doesn't
touch a technical control at all.

### Revised minimum architecture

```
USER
  ↓
Self-hosted Windows Server AD DC (single EC2 instance, genuine AD DS —
  same 12/12-verified password engine as the managed-service version)
  ↓ (PTA Agent — same instance or a second small instance; outbound only)
Microsoft Entra ID (Security Defaults for mandatory MFA — $0; or
  Conditional Access/P1 for richer evidence — ~$14/month for 2 users;
  App Registration issues OIDC/JWT)
  ↓
FastAPI (unchanged, CONFIG_ONLY)
  ↓
RBAC (unchanged)
  ↓
JUVAl data
```

### Final decision table, sorted by lowest verified/estimated total cost

| Architecture | RF-03 | RF-04 | MFA | OIDC | Password source | Custom auth? | Monthly cost | Annual cost | Operational burden | Evidence quality | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Keycloak standalone | FAIL (no min-age, no name-exclusion) | N/A | Native | Native | Keycloak itself | No | $0 (self-hosted) | $0 + hosting | Medium | High (decisive fail) | `REJECTED` |
| Google Workspace/Cloud Identity | FAIL (no history/min-age/name) | N/A | Native (free) | Native | Google | No | $0 (Cloud Identity Free) | $0 | Low | High (decisive fail) | `REJECTED` |
| Entra ID cloud-only workforce | FAIL (fixed 8-char, no min-age, no name) | N/A | Native | Native | Entra ID | No | $0-14 | $0-168 | Low | High (decisive fail) | `REJECTED` |
| FreeIPA (self-hosted) | `NEEDS_VERIFICATION` (item 6 unresolved) | Plausible | Add-on required | Add-on required | FreeIPA | No | ~$20-30 (est., hosting only) | ~$240-360 (est.) | Medium-High | Medium (partial) | `NEEDS_VERIFICATION` |
| Samba AD + Entra PTA | `NEEDS_VERIFICATION` (item 6 unresolved) + supportability gap | Plausible | PASS (Entra) | PASS (Entra) | Samba AD | No | ~$20-30 (est.) + Entra $0-14 | ~$240-528 (est.) | Medium-High | Low (two unresolved risks) | `NOT_RECOMMENDED` |
| **Self-hosted single-DC Windows AD + Entra PTA** | **PASS (12/12, same evidence as managed AD)** | **PASS** | **PASS** | **PASS** | **AD DS (genuine, single instance)** | **No** | **~$25-30 (est.) + $0-14 (Entra)** | **~$300-528 (est.)** | **Medium-High (single point of failure, self-patched)** | **High for controls; cost line is an estimate, not verified** | **`VIABLE — cheapest fully-control-compliant option found`** |
| AWS Managed Microsoft AD + Entra PTA | PASS (12/12) | PASS | PASS | PASS | AD DS (managed, 2 DCs) | No | $88 (verified) + $0-14 | $1,051-1,219 (verified base) | Low (AWS-managed) | High, fully verified including cost | `VIABLE — TECHNICALLY VERIFIED BASELINE, not cheapest` |
| AWS Managed Microsoft AD + AD FS | PASS (12/12) | PASS | PASS | PASS | AD DS (managed, 2 DCs) | No | $88 (verified) + unpriced multi-server AD FS/WAP farm | ≥$1,051 + unpriced | Very High | High for controls, cost incomplete | `VIABLE` (fallback, most expensive/burdensome) |

### Answer to the core question

A legitimate, non-compromising architecture for JUVAl's 2 users exists
**below $50/month (ACCEPTABLE band)**, built entirely from components
already verified in this document — but it does **not** confidently reach
the ≤$20/month TARGET band without an official EC2 Windows price
verification this pass did not obtain, and it does **not** eliminate the
underlying Windows Server AD DS technology (which cannot be replaced —
every free/cheaper alternative checked fails at least one Amazon-mandatory
control). What it eliminates is the **AWS-managed wrapper and its
mandatory second domain controller** — the actual cost driver — while
keeping the identical, already-verified password engine.

`IDENTITY SECURITY GATE = BLOCKED` (unchanged)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = TECHNICALLY VIABLE — COST-OPTIMIZED OPTION IDENTIFIED, PENDING
USER APPROVAL OF THE AVAILABILITY TRADE-OFF (single point of failure)
AND AN OFFICIAL EC2 WINDOWS PRICE VERIFICATION` (superseded below —
preserved as historical record; the price verification attempted below
did not succeed either, see honest result)

## Final cost/sizing validation (2026-08-19)

Scope: close the price and sizing questions this document has carried as
open since the previous section. Result, stated plainly up front: **the
exact official Windows EC2 hourly price could not be obtained this pass
despite ten independent fetch/search attempts** — reported honestly
rather than papered over with an invented number.

### Phase 1 — official AWS Windows pricing: attempted, not obtained

Ten distinct attempts (five `WebFetch` calls against `aws.amazon.com/ec2/
pricing/on-demand/`, `instances.vantage.sh`, and `cloudprice.net`; five
targeted `WebSearch` queries), 2026-08-19:

- AWS's own pricing page is JavaScript-rendered; static fetch returns only
  page chrome, never the price table, on every attempt.
- Third-party pricing-aggregator sites (Vantage, CloudPrice) consistently
  returned only **Linux** on-demand prices ($0.0208/hr t3.small, $0.0104/hr
  t3.micro — these two Linux figures are internally consistent and
  treated as `VERIFIED` for Linux only).
- Windows-specific figures obtained were **internally contradictory**: one
  search returned "$0.0196/hour" flat for Windows t3.micro; a separate
  search returned a generic "$0.046 per vCPU-hour" Windows license
  component which, applied to t3.micro's 2 vCPUs, would imply ≈$0.092/hr
  for the license alone — over 4x the first figure and clearly
  inconsistent with it. Both cannot be correct simultaneously.

**Conclusion: no Windows EC2 price obtained this pass meets the bar for
`VERIFIED PRICE`.** Per instruction, this is reported as `NOT_FULLY_
VERIFIED` rather than resolved by picking whichever number looked more
plausible. The reliable next step is the AWS CLI (`aws pricing get-
products --service-code AmazonEC2 --filters ...`) or the interactive
Pricing Calculator, both of which require an authenticated/interactive
session this research pass does not have.

**Best-available estimate, explicitly labeled `ESTIMATE, NOT VERIFIED
THIS PASS`**: using the well-corroborated (multiple independent sources,
consistent with each other even if not with AWS's own primary page)
"30-40% Windows premium over Linux" heuristic against the *verified*
Linux base rates: t3.small ≈ $0.027-0.029/hr (~$20-21/month at 730
hours); t3.micro ≈ $0.014-0.015/hr (~$10-11/month). Presented as the best
available approximation, not as a verified figure.

### Phase 2 — minimum domain controller sizing

Official Microsoft sources, fetched/searched 2026-08-19: [Capacity
planning for Active Directory Domain Services](https://learn.microsoft.com/en-us/windows-server/administration/performance-tuning/role/active-directory-server/capacity-planning-for-active-directory-domain-services),
[Hardware Requirements for Windows Server](https://learn.microsoft.com/en-us/windows-server/get-started/hardware-requirements).

One search result surfaced a **"32 GB absolute minimum"** claim
attributed to Windows Server 2022 Server Core — this is inconsistent
with well-established, widely-documented Windows Server minimums (Windows
Server's own general installation minimum has long been in the low
single-digit GB range) and is **flagged as unreliable, not adopted** —
the same class of extraction unreliability already seen in Phase 1's
pricing figures. A separately-cited, more specific and plausible
data point is used instead: **"specific AD DS deployments have
successfully run with 4 GB of RAM and 1 CPU with no performance issues
in environments with 12 domain controllers serving around 5,000
users"** — i.e., a single DC comfortably handling a small fraction of
5,000 users on 4 GB/1 vCPU, which is far beyond JUVAl's 2-user scale.

| Instance | RAM | vCPU | Classification for JUVAl (2 users) | Reasoning |
|---|---|---|---|---|
| `t3.nano` | 0.5 GiB | 2 (burstable) | `NOT_RECOMMENDED` (likely `NOT_SUPPORTED` in practice) | Below Windows Server's general practical install/operation threshold even before adding AD DS + DNS + PTA agent |
| `t3.micro` | 1 GiB | 2 (burstable) | `POSSIBLE_BUT_NOT_RECOMMENDED` | At the edge of a bare-OS install threshold; real risk running AD DS + DNS + PTA agent simultaneously under memory pressure |
| `t3.small` | 2 GiB | 2 (burstable) | `RECOMMENDED MINIMUM` for JUVAl's practical scale | Comfortably above general Windows Server minimums; well below the 4 GB/1 vCPU point already shown sufficient for far more than 2 users, but with enough headroom for AD DS + DNS + one lightweight agent |

`SUPPORTED MINIMUM` (Microsoft's own general OS floor): below `t3.small`.
`RECOMMENDED MINIMUM` (this analysis, JUVAl-scale): `t3.small`.
`JUVAl PRACTICAL MINIMUM`: `t3.small`, one instance.

### Phase 3 — true minimum topology: PTA agent placement is genuinely unresolved

Microsoft's own security guidance states administrators "should treat the
server running the PTA agent **as if it were a domain controller**" and
harden it "along the same lines as Securing Domain Controllers Against
Attack" ([PTA security deep dive](https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-pta-security-deep-dive)).
Separately, Microsoft recommends installing Authentication Agents
"close to your domain controllers" for sign-in latency — worded as a
performance consideration, not an explicit same-box prohibition.

**No explicit Microsoft statement was found either endorsing or
prohibiting installing the PTA agent on the same server as the domain
controller itself.** This is reported as genuinely unresolved, not
resolved in either direction by inference:

- `OPTION A` (1 VM: AD DS + DNS + PTA agent) — `NEEDS_VERIFICATION`.
  Plausible (the PTA server needs DC-equivalent hardening regardless, so
  co-location doesn't obviously create a new distinct security boundary),
  but not the documented reference topology, and not explicitly
  confirmed supported. **Not recommended without stronger evidence**,
  per instruction not to recommend an unconfirmed topology.
- `OPTION B` (2 VMs: AD DS+DNS on one, PTA agent on a second) —
  the topology actually reflected in Microsoft's documented guidance
  ("close to your domain controllers" implies a separate, nearby
  machine). **This is the evidence-backed option.**

### Phase 4 — storage, backup, and minimum recovery plan

EBS `gp3` and snapshot pricing are stable, long-standing published AWS
rates (~$0.08/GB-month for `gp3` storage, ~$0.05/GB-month for incremental
snapshot storage) — **not re-fetched this pass, presented as ESTIMATE
consistent with well-established general knowledge**, same caveat
standard as applied throughout. A 30 GB root volume (Windows Server +
AD DS database, generous for 2 users) ≈ $2.40/month; daily automated
snapshots retained ~7-14 days add a few more dollars/month.

**Minimum recovery plan**:
- *What happens if the EC2 instance dies?* JUVAl loses the ability to
  authenticate (sign-in fails) until a replacement is restored — no
  automatic failover, by design of the single-instance topology.
- *How do we restore AD?* From the most recent EBS snapshot: launch a
  new instance from the snapshot, or restore the volume and reattach.
  Standard, well-documented AWS EBS snapshot-restore procedure, not a
  custom design.
- *Estimated downtime?* Bounded by snapshot restore + instance boot time
  — realistically well under an hour for a small volume, not
  instantaneous (no hot standby).
- *What must be backed up?* The EBS volume (AD database, SYSVOL) via
  snapshot; separately, AD FGPP/PSO configuration and the Entra App
  Registration/Conditional Access configuration should be exported as
  `CONFIGURATION_EVIDENCE` (already required for Amazon evidence
  purposes regardless of backup strategy).
- *Does Amazon require a second DC?* **No** — see Phase 5.

### Phase 5 — single domain controller risk, separated from compliance

**`Does one DC violate any applicable Amazon requirement? NO — declared
explicitly.`** None of the 11 RF-03 password/lockout controls, MFA, or
OIDC federation depends on directory redundancy anywhere in Amazon's
Key Security Control Guidance, Safeguarding Sensitive Credentials, or the
DPP citations already captured in this document. Redundancy is a
Microsoft-recommended **best practice for enterprise availability**, not
an Amazon-enumerated control — this document does not convert one into
the other.

| Risk category | Assessment |
|---|---|
| Security | No incremental risk beyond the single-server hardening already required for any DC |
| Compliance (Amazon) | None — confirmed above, not inferred |
| Availability | Real — no automatic failover; sign-in outage until manual recovery |
| Recovery | Bounded, snapshot-based, well under an hour realistically (Phase 4) |
| Operational | JUVAl owns patching/monitoring for one more server than the managed-AD option |

`CLASSIFICATION: USER-ACCEPTABLE BUSINESS RISK, PENDING APPROVAL` — not
elevated to a compliance blocker, per instruction.

### Phase 6 — true cost table

| Component | Qty | Unit price | Monthly | Annual | Required? | Source | Confidence |
|---|---|---|---|---|---|---|---|
| EC2 `t3.small`, Windows (AD DS + DNS) | 1 | ESTIMATE ~$0.027-0.029/hr | ~$20-21 | ~$240-252 | Yes | Derived from verified Linux rate + unverified premium heuristic (Phase 1) | **ESTIMATE, not verified** |
| EC2 `t3.small` or smaller, Windows (PTA agent, Option B) | 1 | ESTIMATE ~$0.027-0.029/hr (or `t3.micro` ~$0.014-0.015/hr if sufficient) | ~$10-21 | ~$120-252 | Yes, for the evidence-backed topology (Option B) | Same basis | **ESTIMATE, not verified** |
| EBS `gp3`, 30 GB × 2 instances | 2 | ~$0.08/GB-mo | ~$4.80 | ~$58 | Yes | Standard published AWS rate, not re-fetched this pass | ESTIMATE (stable, low-risk figure) |
| Snapshots (incremental, ~7-14 day retention) | — | ~$0.05/GB-mo of changed data | ~$2-5 | ~$24-60 | Recommended | Standard published AWS rate | ESTIMATE |
| Microsoft Entra ID | 2 users | $0 (Security Defaults) or ~$7/user/mo (P1 Conditional Access) | $0 or ~$14 | $0 or ~$168 | Yes (MFA layer) | [Entra ID pricing, verified prior pass](https://ic-consult.com/en/resources/blogs/microsoft-entra-id-license-models-explained-p1-p2-and-entra-suite/) | VERIFIED (list price) |
| Public IPv4 | 1-2 | $0.005/hr per address (current AWS public-IPv4 charge) | ~$3.60-7.20 | ~$43-86 | Only if a public IP is actually attached — PTA agents make outbound-only connections and do not require one; **can likely be avoided with a NAT gateway or VPC endpoint design, not priced here** | AWS's published public-IPv4 pricing change (general knowledge, not re-fetched) | ESTIMATE, and possibly `$0` if avoided architecturally |
| Data transfer | — | Negligible at 2-user scale | ~$0-1 | ~$0-12 | N/A | General knowledge | ESTIMATE |
| DNS | — | $0 (AD-integrated DNS, included in AD DS role) | $0 | $0 | Yes, included | Standard AD DS behavior | High confidence |
| Monitoring | — | Not mandated by Amazon; CloudWatch basic monitoring is free-tier | $0 (basic) | $0 | Not Amazon-mandatory | N/A | High confidence |

**MINIMUM COST** (Option A, unresolved topology risk, 1 instance):
~$25-30/month ESTIMATE — **not recommended**, topology not evidence-backed.
**RECOMMENDED COST** (Option B, evidence-backed 2-instance topology):
~$35-55/month ESTIMATE (2× compute + storage + Entra).
**HIGH-AVAILABILITY COST**: not designed this pass (out of scope — JUVAl
explicitly does not need enterprise HA per the 2-user framing); would
approach or exceed AWS Managed Microsoft AD's $88/month verified price
once a second DC and redundant PTA agents are added, at which point the
managed service likely becomes the better value.

### Phase 7 — attempt to break $20/month

Using the `t3.micro` PTA-agent instance (if sufficient — genuinely
`POSSIBLE_BUT_NOT_RECOMMENDED` per Phase 2, not a confident yes) plus a
`t3.small` DC: ESTIMATE ~$20-21 (DC) + ~$10-11 (agent, unrecommended
sizing) + storage (~$3-5) ≈ **~$33-37/month ESTIMATE — still above
$20**, and only reachable by accepting a `POSSIBLE_BUT_NOT_RECOMMENDED`
instance size for the second server. Consolidating to Option A (single
instance) reaches ~$25-30/month ESTIMATE but trades away the
evidence-backed topology. **Below $20/month was not achieved without
either an unrecommended instance size or an unresolved topology** — per
instruction, not adopted as the recommendation merely to hit the target.

`COST FLOOR COMPONENT: the second Windows EC2 instance (PTA agent, if
Option B is followed) is what pushes the total out of the $0-10 IDEAL
band and toward the top of the ≤$50 ACCEPTABLE band` — inherent to
running genuine, Microsoft-supportable Windows Server AD DS at all; not
reducible further without either an unresolved topology (Option A) or
an unrecommended instance size.

### Phase 8 — architectural decision

`D) NOT FULLY VERIFIED.` The control-compliance side of this
architecture is fully verified (12/12, decisive primary-source evidence
across three research passes). The **cost** side is not: the exact
Windows EC2 price could not be obtained despite genuine, repeated effort,
and the PTA-agent placement question (Option A vs. B) remains
genuinely open. Per instruction, `D` — not manufactured into `A` or `B`
to produce a clean answer. The estimate range (~$25/month minimum,
unresolved topology, to ~$35-55/month, evidence-backed topology) is
reported as the best currently available approximation, explicitly not
a verified total.

`IDENTITY SECURITY GATE = BLOCKED` (unchanged)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = NOT READY FOR APPROVAL ON COST GROUNDS` (superseded below —
preserved as historical record)

## AWS CLI pricing verification attempt (2026-08-19)

### AWS CLI status

**Not installed** on this workstation — confirmed via both Bash (`aws:
command not found`) and PowerShell (`CommandNotFoundException`). Per
instruction, this branch stopped here rather than fabricating command
output; the rest of this section uses the remaining available official
sources.

### Windows EC2 instance pricing — still not obtained, avenues now exhausted

A twelfth and thirteenth attempt this pass: the **AWS Price List Bulk
API** (`pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/
current/us-east-1/index.json`) — the genuine second official route this
task asked for — **failed on file size** (exceeds this tool's 10 MB
fetch limit; the full EC2 offer file for a region is hundreds of MB).
This is an honest tool limitation, not a fabricated result.

**Combined with the ten attempts in the prior pass (rendered AWS pricing
page, third-party aggregators, targeted searches, all either
JS-rendered/unreachable or internally contradictory), the reasonable
tool-based avenues for this specific number are now exhausted.** The
reliable path is the AWS CLI itself, which requires installation this
pass could not perform (no destructive/install action was authorized,
and installing software is arguably outside "research only" scope
regardless). **Concrete next step, not another automated attempt**: the
user (or a session with AWS CLI installed and credentials configured)
runs exactly:

```
aws pricing get-products --service-code AmazonEC2 --region us-east-1 --filters \
  "Type=TERM_MATCH,Field=instanceType,Value=t3.small" \
  "Type=TERM_MATCH,Field=location,Value=US East (N. Virginia)" \
  "Type=TERM_MATCH,Field=operatingSystem,Value=Windows" \
  "Type=TERM_MATCH,Field=tenancy,Value=Shared" \
  "Type=TERM_MATCH,Field=preInstalledSw,Value=NA" \
  "Type=TERM_MATCH,Field=capacitystatus,Value=Used" \
  --query 'PriceList' --output text
```

(and the same with `t3.micro`). This is the exact, correct query — not
re-attempted here because the environment cannot execute it, not because
it wasn't identified.

### EBS gp3 and snapshot pricing — re-checked, unchanged confidence level

Re-fetched `aws.amazon.com/ebs/pricing/` directly this pass: the page
itself states the same **$0.08/GB-month (gp3) and $0.05/GB-month
(snapshot)** figures, but as the page's own illustrative calculation
examples rather than a dedicated regional price table — the same
evidentiary weight as the prior pass, not strengthened, not weakened.
Retained as `ESTIMATE, high confidence` (these are long-stable, widely-
corroborated published AWS rates, not a volatile or contested figure like
the Windows instance price).

### Public IPv4 — VERIFIED

**$0.005/hour per address** for both in-use and idle public IPv4
addresses, effective since 2024-02-01, confirmed unchanged through
2026-08 ([AWS public IPv4 pricing change](https://aws-experience.com/emea/smb/e/1c148/need-to-confirm-time-of-event-w-manish-optimizing-public-ipv4-address-usage-and-costs-on-aws),
cross-checked against Vantage's cost-tracking summary). **≈$3.65/month
per address at 730 hours — `VERIFIED`.**

**Architecture decision**: neither the AD DS instance nor the PTA-agent
instance needs to accept *inbound* traffic from the internet — PTA is
explicitly outbound-only, and AD DS must not be internet-facing. A
**NAT Gateway is not required and is explicitly avoided**: a public IP
address attached to an instance with a Security Group that denies all
inbound and allows only outbound is sufficient for the instance to reach
Entra ID's cloud endpoints, and costs one $0.005/hour IPv4 charge instead
of a NAT Gateway's hourly charge *plus* per-GB data-processing charge
(materially more expensive at any real traffic volume, and the task
explicitly warned against accepting a NAT Gateway automatically). Having
a public IP address is not the same as being internet-accessible — the
security group boundary determines that, not the address's presence.
**Public IPv4 requirement: YES (one per Windows instance needing
outbound internet), cost VERIFIED, NAT Gateway explicitly not adopted.**

### PTA / Entra Connect / domain-controller coexistence — resolved, with a confidence distinction between the two components

**Microsoft Entra Connect on the domain controller — decisive, quoted
verbatim**: "Installing Microsoft Entra Connect on the Domain Controller
is **supported**, but Microsoft **doesn't recommend** that... adding
services increases the attack surface... in larger environments, the
sync process can have an impact on the performance of the domain
controller" ([Microsoft Entra Connect prerequisites](https://learn.microsoft.com/en-us/entra/identity/hybrid/connect/how-to-connect-install-prerequisites),
re-confirmed 2026-08-19). This is `SUPPORTED, NOT_RECOMMENDED` —
explicitly not `PROHIBITED`, and not merely `NEEDS_VERIFICATION` as the
prior pass left it.

**Pass-Through Authentication agent specifically**: the PTA agent is
typically installed as part of the same Entra Connect installer/role and
shares its administrative treatment (Microsoft's own guidance: treat the
PTA server "as if it were a domain controller" and harden it
identically) — but **no independently-worded "supported, not
recommended" statement specific to the PTA agent alone** (as distinct
from Entra Connect Sync generally) was found this pass, despite a
targeted search. Reported at slightly lower confidence than the Entra
Connect finding: `SUPPORTED_BY_STRONG_ANALOGY, NOT INDEPENDENTLY
CONFIRMED` — not claimed as equally certain, per instruction not to
manufacture certainty.

**Reasoning for JUVAl's 2-user scale**: Microsoft's stated objections
("increases attack surface," "impacts performance in larger
environments") are explicitly framed as *enterprise-scale* concerns — a
server that already requires DC-equivalent hardening (per the PTA
security guidance already in this document) does not acquire a
materially new distinct security boundary by also running AD DS on the
same box, and a 2-user directory has no realistic sync-performance
concern. This is this document's own reasoning, not a direct Microsoft
statement endorsing single-VM specifically for small deployments — stated
as such, not attributed to Microsoft.

**Result: `SCENARIO A (single VM) is an officially supported topology,
not merely an unconfirmed one` — upgraded from the prior pass's
`NEEDS_VERIFICATION`.** `SCENARIO B (separate agent server)` remains the
better-evidenced, Microsoft-preferred choice, at roughly double the
compute cost.

### Cost scenarios, updated

| Line | Scenario A (1 VM, supported not preferred) | Scenario B (2 VMs, Microsoft-preferred) | Scenario C (AWS Managed AD, baseline) | Status |
|---|---|---|---|---|
| Windows compute | ESTIMATE ~$20-21/mo (1× t3.small) | ESTIMATE ~$40-42/mo (2× t3.small) | $0 (managed) | **Not verified** (see above) |
| EBS gp3 (30GB ×N) | ESTIMATE ~$2.40/mo | ESTIMATE ~$4.80/mo | $0 (managed) | ESTIMATE, high confidence |
| Snapshots | ESTIMATE ~$2-5/mo | ESTIMATE ~$4-10/mo | $0 (managed) | ESTIMATE, high confidence |
| Public IPv4 | **VERIFIED** ~$3.65/mo (1 address) | **VERIFIED** ~$7.30/mo (2 addresses) | $0 (no self-hosted instance) | VERIFIED |
| NAT Gateway | **$0 — explicitly avoided** | **$0 — explicitly avoided** | N/A | Decision, not a price |
| Directory service | N/A (self-hosted, priced above) | N/A (self-hosted, priced above) | **VERIFIED** $87.60/mo (2 DCs) | VERIFIED |
| Entra ID | $0 (Security Defaults) or **VERIFIED** ~$14/mo (P1, 2 users) | Same | Same | VERIFIED (list price) |
| **TOTAL (Security Defaults)** | **ESTIMATE ~$28-32/mo** | **ESTIMATE ~$56-64/mo** | **VERIFIED ~$88/mo** | Mixed |
| **TOTAL (Conditional Access/P1)** | **ESTIMATE ~$42-46/mo** | **ESTIMATE ~$70-78/mo** | **VERIFIED ~$102/mo** | Mixed |

### Final classification

`D — NOT FULLY VERIFIED`, unchanged in category, but materially narrower
than the prior pass: topology (now resolved, Scenario A supported),
public IPv4 (now verified), NAT Gateway (explicitly avoided, not priced
as a cost), and EBS/snapshot (stable estimates, unchanged confidence)
are no longer open questions. **The single remaining blocker to a `B`
classification (`FULLY VERIFIED ≤$50/month`) is the Windows EC2 compute
line** — Scenario A's total would land at an estimated ~$28-32/month,
comfortably inside the ≤$50 band and close to (not confidently under)
the ≤$20 band, *if* the compute estimate holds. It has not been
converted into a verified figure despite exhausting the tool-based
avenues available in this environment.

`IDENTITY SECURITY GATE = BLOCKED` (unchanged)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = NOT READY FOR APPROVAL — ONE VERIFICATION STEP REMAINS (Windows
EC2 compute price via AWS CLI, exact command specified above), NOT
FURTHER ARCHITECTURAL RESEARCH` (superseded below — this Windows-cost
line of research is set aside, not because it was resolved, but because
a materially better Linux alternative was found this pass)

## The full-name-exclusion gap closes on Linux: FreeIPA + Keycloak (2026-08-19)

Scope: this pass specifically attacked the one control (Amazon full-name
password exclusion) that had eliminated every non-Windows candidate in
this document — using primary Samba/389-ds/Keycloak documentation, not
re-litigating already-settled controls or "AD-compatible" marketing
claims.

### Candidate A/B — Samba AD DC: SOURCE_VERIFIED extension point exists

Direct fetch of Samba's own official `smb.conf` man page, 2026-08-19:
the `check password script` parameter, **verbatim**: "Starting with
Samba 4.11 the following environment variables are exported to the
script: `SAMBA_CPS_ACCOUNT_NAME` is always present and contains the
sAMAccountName of user... `SAMBA_CPS_FULL_NAME` is optional if the
displayName is present." The script receives the candidate password on
stdin and returns exit code 0 (accept) or non-zero (reject) —
synchronous, server-side, entirely within Samba's own directory process,
never exposed to FastAPI or any external system. This is a **password
policy extension**, not custom authentication, per this task's own
definition: directory-platform-supported, synchronous, no password
storage or exposure outside the directory, deterministic, and it is
Samba's documented, official mechanism (not a hack).

**Caveat, not hidden**: "Defining a check password script completely
replaces the built-in password complexity check" — so the script must
also reimplement length/character-class rules, not just name-exclusion;
more implementation surface than Candidate C below. Whether it applies
uniformly to administrative password resets (not just self-service
changes) was not independently confirmed this pass. `SAMBA = VIABLE,
SOURCE_VERIFIED for the extension point, more implementation surface
than FreeIPA`.

### Candidate C — FreeIPA / 389 Directory Server: NATIVE_VERIFIED, no scripting required

Direct fetch of 389 Directory Server's own official password-syntax
design documentation, 2026-08-19: the `passwordUserAttributes`
configuration attribute, **verbatim**: "List of entry attributes of the
user to compare to the new password... you can specify what attributes
to compare in the entry." Confirmed as **substring/contains checking,
not exact-match** — the default attribute list is `uid, sn, cn,
givenname, mail, ou` (username, last name, common name, first name,
email, organizational unit), administrator-extensible. **Native to 389
Directory Server 1.4.0+ (the engine FreeIPA is built on) — zero custom
scripting required**, a pure configuration setting.

This is stronger evidence than Samba's path: no script to write, test,
or maintain — the exact directory-platform-native mechanism this task's
`SECURITY_DEFINITION` describes as architecturally acceptable, at the
lowest possible implementation-risk tier.

**Bypass analysis, disclosed**: "Password Administrators and the Root DN
(cn=directory manager) can bypass all password syntax checks... This
bypass mechanism is intentional by design" ([389 DS Password
Administrators](https://www.port389.org/docs/389ds/design/password-administrator.html),
fetched 2026-08-19). **This is the same class of risk already accepted
for AWS Managed AD's admin-reset bypass of history/min-age** — not a new
category of gap, and it requires the identical organizational control
already documented in this ADR for the Windows path: restrict and audit
use of Directory Manager/password-administrator privileges for routine
password operations.

**FreeIPA's already-confirmed native lifecycle controls** (prior pass,
unchanged): `minlife` (min age, hours — configurable ≥24h = 1 day),
`maxlife` (max age, days), `historylength` (history), `maxfailcount`/
`lockouttime` (lockout). Combined with `passwordUserAttributes` (this
pass), **FreeIPA now has a primary-source-documented, native path to all
9 human-password composition/lifecycle controls with zero custom
scripting** — the first candidate in this entire investigation, Windows
included, to reach this with a pure-configuration (not managed-workaround,
not custom-code) mechanism for every item.

### Candidate D — Keycloak as federation-only broker: confirmed non-duplicative

Official Keycloak documentation, confirmed 2026-08-19: **"Keycloak never
imports passwords — password validation always occurs on the LDAP
server... Keycloak does not synchronize the password into its local
database. Instead, during login, Keycloak validates the password
directly against the LDAP server."** With LDAP User Federation set to
`READ_ONLY` edit mode, Keycloak binds to FreeIPA's LDAP interface to
validate credentials — FreeIPA remains the sole password authority,
Keycloak never stores or independently validates a password copy. This
satisfies the non-negotiable boundary from the earlier Entra-PTA
investigation with an open-source equivalent: **no duplicate password
store, confirmed by the vendor's own documentation, not inferred.**

Keycloak's own (separately known-deficient, from the prior pass) native
password policies are **irrelevant in this architecture** — they only
apply to Keycloak-local users, never to LDAP-federated ones. MFA
(TOTP/WebAuthn, mandatory via Required Actions or Authentication Flow
binding) and OIDC (Keycloak's native, mature OIDC provider) are both
Keycloak's own responsibility, independent of the password question
entirely.

### Candidate E — FusionAuth extension: not re-opened

Per instruction, not re-investigated beyond the prior pass's conclusion
(`10/11 + 1 partial` — loginId-exclusion, not full-name-exclusion). No
new evidence surfaced this pass changes that.

### 12-control matrix — FreeIPA + Keycloak

| # | Control | Mechanism | Evidence tier | Result |
|---|---|---|---|---|
| 1 | ≥12 chars | `passwordMinLength` | Native | PASS |
| 2-5 | Upper/lower/number/special | `passwordMinCategories`/class rules | Native | PASS |
| 6 | Name/username exclusion | **`passwordUserAttributes`** (uid, sn, givenname, ...) | **NATIVE_VERIFIED, this pass** | **PASS** |
| 7 | History ≥10 | `historylength` | Native | PASS |
| 8 | Minimum age ≥1 day | `minlife` | Native | PASS |
| 9 | Maximum age ≤365 days | `maxlife` | Native | PASS |
| 10 | Mandatory MFA | Keycloak TOTP/WebAuthn, Required Action | Native (Keycloak) | PASS |
| 11 | Lockout ≤10 | `maxfailcount` | Native | PASS |
| 12 | OIDC to FastAPI | Keycloak native OIDC provider | Native (Keycloak) | PASS |

**12/12 — the first candidate in this entire investigation, including
every Windows/Okta/Cognito/Auth0/Entra/JumpCloud/ZITADEL/FusionAuth/
Clerk/Google/Samba path checked, to reach full coverage with zero custom
authentication and zero managed-workaround design (unlike Cognito's
`PASSWORD_MAX_AGE_CONTROL` or any script-based approach).**

### Password/MFA ownership and bypass analysis

```
PASSWORD OWNER: FreeIPA (389 Directory Server), exclusively.
                Keycloak never stores or independently validates a
                password copy (vendor-confirmed, this pass).
MFA OWNER:      Keycloak, exclusively — independent of password
                validation, applies uniformly to the federated identity
                after LDAP bind succeeds.
BYPASS RISK:    Directory Manager / password-administrator bypass of
                syntax checks — same class and same compensating
                organizational control already accepted for AD's
                admin-reset bypass. Not a new risk category.
```

### Cost — Linux, verified base rate (unlike the Windows path)

Unlike the Windows investigation, the Linux compute base rate is
**already verified** in this document: `t3.small` Linux = $0.0208/hour
(confirmed multiple times this session). No Windows-license-surcharge
uncertainty applies to this architecture at all — the single largest
source of unresolved risk in the Windows path is structurally absent
here.

| Component | Qty | Rate | Monthly | Confidence |
|---|---|---|---|---|
| FreeIPA VM (`t3.small`, 2 GiB — comfortably above FreeIPA's own documented 1-2 GiB minimum) | 1 | $0.0208/hr **VERIFIED** | ~$15.18 | Compute rate VERIFIED |
| Keycloak VM (`t3.small`) | 1 | $0.0208/hr **VERIFIED** | ~$15.18 | Compute rate VERIFIED |
| EBS `gp3`, 20-30 GB × 2 | 2 | ~$0.08/GB-mo | ~$3-5 | ESTIMATE, stable rate |
| Public IPv4 (Keycloak only — FreeIPA has no reason to be internet-facing; only Keycloak's login endpoint needs inbound 443) | 1 | $0.005/hr **VERIFIED** | ~$3.65 | VERIFIED |
| Snapshots | — | ~$0.05/GB-mo | ~$2-3 | ESTIMATE |
| FreeIPA + Keycloak licensing | — | $0 (open source) | $0 | VERIFIED |
| **TOTAL** | | | **~$36-42/month, ESTIMATE, built on a VERIFIED compute base rate** | |

This does not reach the ≤$20/month TARGET band, but it is **the first
architecture in this document to combine full 12/12 control coverage
with a verified compute base rate** — meaningfully more certain than the
Windows path's estimate (which rests on an unverified license surcharge)
and roughly half the cost of AWS Managed Microsoft AD (~$88-102/month,
verified). Consolidating FreeIPA and Keycloak onto a single `t3.medium`
instance was considered (~$30/mo compute + ~$7/mo other ≈ $37/mo) — not
materially cheaper than the two-instance split, and worse for security
segmentation (co-locating the internet-facing broker with the directory)
— **not adopted**.

### Decision

`A) LOW_COST_12_OF_12_ARCHITECTURE_FOUND` — "low cost" relative to every
alternative actually evaluated in this document (≤half of AWS Managed
AD; no Windows-licensing risk; open-source, no per-user licensing fees),
not a literal ≤$20/month figure, stated precisely rather than rounded up
to claim a target that wasn't met.

**Recommended low-cost architecture**: FreeIPA (password/lockout/history
authority, native `passwordUserAttributes` for name-exclusion) + Keycloak
(LDAP User Federation, `READ_ONLY`, MFA + OIDC) + FastAPI (unchanged).

**Recommended next step — a tiny, non-production proof of concept, not
implemented this session**: a local Docker Compose stack (official
`freeipa/freeipa-server` and `quay.io/keycloak/keycloak` images) on a
throwaway developer machine, no cloud resources, no secrets, no
production data — to *behaviorally* confirm `passwordUserAttributes`
rejects "Daniel123!" for a user with `givenname: Daniel`, before
committing to cloud spend. This closes the gap between "documented
behavior" and "observed behavior" cheaply, consistent with this task's
own `C) NEEDS_LIVE_VALIDATION` option — offered as the honest next step
even though the primary-source documentation is strong enough to
classify as `A`, not `C`, for the architectural decision itself.

`IDENTITY SECURITY GATE = BLOCKED` (unchanged — nothing implemented)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = TECHNICALLY VIABLE, LOWEST-RISK CANDIDATE YET FOUND — PENDING
USER DECISION BETWEEN THIS LINUX PATH AND THE WINDOWS PATH, AND PENDING
THE PROOF-OF-CONCEPT ABOVE OR EQUIVALENT LIVE VALIDATION`

## Local PoC attempt — environment blocked, no empirical evidence produced (2026-08-19)

An attempt was made to build the local FreeIPA + Keycloak proof of
concept described above, to move the name-exclusion finding from
documented to *observed* behavior. **It did not run.** Reported
honestly, not converted into a false pass:

- `docker --version` → `command not found` (Bash and PowerShell both
  checked). Docker is not installed on this workstation.
- `wsl --list --verbose` / `wsl --version` → both returned generic
  usage/help text rather than actual output, indicating the `wsl.exe`
  launcher stub is present but the WSL2 feature itself has not been
  enabled (no distribution installed, flags not recognized as valid).
- `Get-WindowsOptionalFeature` (to confirm the underlying Windows
  feature state directly) → requires administrator elevation, which
  this session does not have and did not attempt to acquire.

Per this task's own instruction ("Do NOT install major system software
automatically if missing... Do not redesign architecture because of a
local tooling limitation"), **no installation was attempted** and **no
container was run**. No files were created under `poc/identity/` this
pass — scaffolding untested Compose/config files for a stack that could
not be executed or validated would risk looking like progress that
didn't happen; better to state the blocker plainly.

**Exact missing prerequisites, smallest manual action**: enable WSL2
(`wsl --install` run as Administrator in PowerShell — installs the WSL2
feature and a default Linux distribution, typically requires a reboot),
then install Docker Desktop for Windows (uses the WSL2 backend
automatically on Windows Home, where Hyper-V is unavailable). Both are
one-time, user-authorized actions this agent should not perform
unilaterally.

**Consequence for this ADR's classification**: the architectural
decision (FreeIPA + Keycloak, `12/12` on documentation) is **unchanged**
— primary-source vendor documentation remains the evidentiary basis, as
it has been for every other candidate and gate in this document. What
is explicitly **not** claimed is empirical, observed confirmation of
name-exclusion, lockout, MFA-gating, or any other behavior — that
remains open, honestly labeled, pending either this PoC (once Docker/WSL2
is available) or a different validation path the user chooses.

`FREEIPA_KEYCLOAK_IDENTITY_POC_GATE = ENVIRONMENT_BLOCKED` (not `PASS`,
not `FAIL` — no test executed either way)
`IDENTITY SECURITY GATE = BLOCKED` (unchanged)
`REAPPLICATION GATE = BLOCKED` (unchanged)
`ADR-021 = NOT_READY (documentarily 12/12, empirically unverified —
unchanged from before this attempt)`

## Consequences and rollback

Un IdP gestionado reduce código de seguridad propio, pero introduce dependencia
de proveedor/plan y requiere verificaciones contractuales. La decisión es
reversible antes de crear usuarios o integrar el backend; cambiar de IdP
después exigirá revisar claims, sesiones, roles y evidencia.
