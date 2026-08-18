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

## Consequences and rollback

Un IdP gestionado reduce código de seguridad propio, pero introduce dependencia
de proveedor/plan y requiere verificaciones contractuales. La decisión es
reversible antes de crear usuarios o integrar el backend; cambiar de IdP
después exigirá revisar claims, sesiones, roles y evidencia.
