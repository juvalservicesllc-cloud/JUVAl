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

## Consequences and rollback

Un IdP gestionado reduce código de seguridad propio, pero introduce dependencia
de proveedor/plan y requiere verificaciones contractuales. La decisión es
reversible antes de crear usuarios o integrar el backend; cambiar de IdP
después exigirá revisar claims, sesiones, roles y evidencia.
