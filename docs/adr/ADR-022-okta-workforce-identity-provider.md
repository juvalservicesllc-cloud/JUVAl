# ADR-022: Okta Workforce Identity as the human identity provider (Proposed)

- Estado: **Propuesta** — técnicamente resuelta, **pendiente de aprobación
  comercial del usuario** (contrato anual mínimo, §5).
- Fecha: 2026-08-18.
- Alcance: elección del Identity Provider para **identidad humana** (RF-03) y
  la frontera de autorización backend (RF-04). No crea cuentas, tenant,
  credenciales ni contrato.
- Supersede: la conclusión `RECOMMENDED IdP = NONE` de
  [`ADR-021`](ADR-021-identity-provider-authentication-boundary.md)
  §"Final two-gap investigation and Cognito rejection". ADR-021 sigue siendo
  la fuente normativa de la **matriz de ownership de 25 controles** y del
  conjunto `HARD IdP REQUIREMENTS`; este ADR solo resuelve *qué proveedor*
  los satisface.

## Contexto

ADR-021 estableció, mediante una matriz de ownership de 25 controles, que solo
**11** son `HARD IdP REQUIREMENTS` — los que ningún otro layer (backend,
organización, infraestructura, credenciales de servicio) puede absorber
legítimamente sin construir autenticación propia:

`HARD IdP REQUIREMENTS = { 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 }` — el set
completo de composición de contraseña (≥12 caracteres, mayúscula, minúscula,
número, carácter especial, exclusión de nombre/username, historial de 10,
edad mínima 1 día, edad máxima 365 días) más MFA obligatorio y bloqueo por
intentos fallidos ≤10.

Tres candidatos fueron eliminados o dejados sin resolver:

| Candidato | Resultado ADR-021 | Bloqueo |
|---|---|---|
| Amazon Cognito | **REJECTED** | GAP A (edad mínima) y GAP B (exclusión de nombre) = `E — NOT_SUPPORTED` |
| Microsoft Entra External ID | **ELIMINATED** | Mínimo nativo de 8 caracteres; historial solo de la última contraseña |
| Clerk | **UNRESOLVED** | 6 de 11 requisitos HARD sin configuración publicada verificable |

La pregunta pendiente no era "¿existe algún IdP?" sino **"¿existe un IdP cuya
política de contraseñas incluya nativamente edad mínima y exclusión de
nombre?"** — dos controles que son estándar en IAM *workforce* (empleados) y
raros en plataformas *CIAM* (clientes). Los tres candidatos anteriores eran
productos CIAM. Esa es la razón estructural del fallo, y la razón de mirar
hacia identidad workforce.

## Decisión candidata

**Okta Workforce Identity** como Identity Provider de identidad humana.

Okta satisface **los 11 requisitos HARD de forma nativa y configurable**,
incluidos exactamente los dos que descalificaron a Cognito.

### Verificación contra documentación primaria (2026-08-18)

Todos los nombres de configuración están citados **verbatim** de la
documentación oficial de Okta.

| # | Requisito Amazon | Setting nativo de Okta (verbatim) | Rango / límite | Estado |
|---|---|---|---|---|
| 3 | ≥12 caracteres | "Require a minimum number of characters in passwords." | 4–30 caracteres → 12 configurable | `CONFIGURABLE_VERIFIED` |
| 4 | Mayúscula | "Upper case letter: Require at least one upper-case letter in the password." | on/off | `CONFIGURABLE_VERIFIED` |
| 5 | Minúscula | "Lower case letter: Require at least one lower-case letter in the password." | on/off | `CONFIGURABLE_VERIFIED` |
| 6 | Número | "Number (0-9): Require at least one number from zero to nine in the password." | on/off | `CONFIGURABLE_VERIFIED` |
| 7 | Carácter especial | "Symbol (e.g., !@#$%^&*): Require at least one symbol in the password." | on/off | `CONFIGURABLE_VERIFIED` |
| 8 | **Exclusión de nombre/username (GAP B de Cognito)** | "Does not contain part of username: Don't allow parts of the username in the password." / "Does not contain first name: Don't allow the user's first name in the password." / "Does not contain last name: Don't allow the user's family name in the password." | tres toggles independientes | **`CONFIGURABLE_VERIFIED`** |
| 9 | Historial de 10 | "Enforce password history for last N passwords" | 1–30 → 10 configurable | `CONFIGURABLE_VERIFIED` |
| 10 | **Edad mínima 1 día (GAP A de Cognito)** | "Minimum password age is N units: Enter the minimum time interval required between password changes." | hasta 9.999 minutos → 1.440 min = 1 día | **`CONFIGURABLE_VERIFIED`** |
| 11 | Edad máxima ≤365 días | "Password expires after N days" | hasta 999 días → 365 configurable | `CONFIGURABLE_VERIFIED` |
| 12 | MFA obligatorio | Authenticator enrollment policies / MFA enrollment policy | política por grupo/global | `CONFIGURABLE_VERIFIED` |
| 13 | Bloqueo ≤10 intentos | "Lock out user after N unsuccessful attempts: The number of times users can enter an incorrect password before the account is locked." | máximo 100 → 10 configurable | `CONFIGURABLE_VERIFIED` |

Fuentes oficiales, verificadas 2026-08-18:

- [Configure the password authenticator (Okta Identity Engine)](https://help.okta.com/oie/en-us/content/topics/identity-engine/authenticators/configure-password.htm)
  — origen de los toggles de complejidad y de las tres reglas
  "Does not contain…".
- [Configure a password policy](https://help.okta.com/en-us/content/topics/security/policies/configure-password-policies.htm)
  — origen de historial, edad mínima, expiración y bloqueo, con sus rangos.
- [Authenticator enrollment policies](https://help.okta.com/oie/en-us/Content/Topics/identity-engine/policies/about-mfa-enrollment-policies.htm)
  — MFA.

`GAP A CLASSIFICATION (Okta) = A — NATIVE_VERIFIED`
`GAP B CLASSIFICATION (Okta) = A — NATIVE_VERIFIED`

Ninguno de los dos requiere control gestionado, trabajo programado, ni
inspección de contraseña en claro fuera del IdP — a diferencia del diseño
`PASSWORD_MAX_AGE_CONTROL` que ADR-021 tuvo que construir para Cognito, aquí
innecesario porque la expiración es nativa.

### Candidatos descartados en esta ronda

| Candidato | Resultado | Evidencia |
|---|---|---|
| **Microsoft Entra ID (workforce, cloud-only)** | **ELIMINATED** | La política de contraseñas es en su mayoría **no modificable**: "A minimum of 8 characters"; "Requires three out of four of the following types of characters" (no los cuatro); "Password change history: The last password *can't* be used again" (historial de 1, no 10); no existe ningún setting de edad mínima; no existe regla de exclusión de nombre. Falla los requisitos HARD 3, 4–7, 8, 9 y 10. Fuente: [Self-service password reset policies](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-sspr-policy), verificada 2026-08-18. |
| **JumpCloud** | `NEEDS_VERIFICATION` (no seleccionado) | Documenta longitud mínima, complejidad, historial ("originality"), expiración y lockout, pero **no** documenta edad mínima de contraseña ni exclusión de nombre/username en las páginas oficiales revisadas. No se puede afirmar que satisfaga los requisitos HARD 8 y 10. Cerrarlo exigiría un tenant real. |

No se evaluaron más candidatos: Okta cierra el set HARD completo con evidencia
primaria, y seguir comparando proveedores no cambiaría la decisión técnica —
solo la comercial (§5).

## Frontera arquitectónica (sin cambios respecto a ADR-021)

Okta **no** absorbe los 14 controles restantes de la matriz de ADR-021. La
separación se mantiene:

```
Usuario → PWA → Okta (AuthN, MFA, política de contraseñas)
              → token OIDC/JWT
              → FastAPI (validación de token + AuthZ/RBAC)
              → recursos JUVAl
```

- **Okta posee:** identidad humana, contraseñas, MFA, bloqueo, ciclo de vida
  de cuenta, eventos de autenticación.
- **FastAPI posee:** validación del token (emisor, firma vía JWKS, audiencia,
  expiración), autorización por recurso, RBAC. Nunca confía en el frontend.
- **Organización posee:** revisión trimestral de accesos, offboarding ≤24 h,
  plan de respuesta a incidentes.
- **Infraestructura / credenciales de servicio:** SP-API, base de datos y
  despliegue siguen siendo un dominio separado — nunca contraseñas humanas.

JUVAl **no** implementa: base de datos de contraseñas, hashing, validación de
composición, historial, motor de edad de contraseña, ni protocolo MFA
(§12 del contrato de trabajo, `CLAUDE.md` §16).

## Consecuencias

**A favor:** cierra los dos bloqueos HARD que ningún candidato anterior podía
cerrar; elimina la necesidad del control gestionado de expiración diseñado
para Cognito; OIDC/JWT estándar, por lo que la implementación backend es
independiente del proveedor; eventos de autenticación exportables como
evidencia RF-03; ciclo de vida de cuenta (suspensión/desactivación) nativo
para RF-04 y para el requisito de revocación ≤24 h.

**En contra:** coste recurrente (§5); dependencia de un proveedor externo para
la autenticación; Okta es producto *workforce*, por lo que el modelo mental es
"empleados de la organización", que coincide con el uso real de JUVAl
(operadores internos, private developer) pero **no** serviría si JUVAl
alguna vez expusiera registro público de clientes — ese sería un cambio de
alcance que requeriría un ADR nuevo.

**Rollback:** la implementación backend valida OIDC genérico (emisor,
JWKS, audiencia, claims). Cambiar de proveedor OIDC exige reconfiguración
(`JUVAL_OIDC_ISSUER`/`JUVAL_OIDC_AUDIENCE`) y una nueva verificación de
política de contraseñas, no reescribir la capa de autorización.

## 5. Bloqueo comercial — EXTERNAL USER ACTION REQUIRED

Okta Workforce Identity **no tiene un plan de producción gratuito**.

| Hecho | Valor | Fuente |
|---|---|---|
| Contrato anual mínimo | **1.500 USD/año** | [Okta Pricing](https://www.okta.com/pricing/), verificado 2026-08-18 |
| Starter Suite | 6 USD/usuario/mes, facturado anualmente | Íd. |
| Essentials Suite | 17 USD/usuario/mes, facturado anualmente | Íd. |
| Integrator Free Plan | Hasta 10 usuarios activos, **no producción** — "you should not connect the generated app instance in your Integrator Free Plan org to your production environment" | [Okta Integrator Free Plan org configurations](https://developer.okta.com/docs/reference/org-defaults/), verificado 2026-08-18 |

Consecuencias operativas:

1. **La selección definitiva del proveedor requiere aprobación del usuario**,
   porque implica un compromiso comercial recurrente. El agente no la aprueba.
2. El **Integrator Free Plan sí puede usarse para producir
   `CONFIGURATION_EVIDENCE`** de que la política de contraseñas de Amazon es
   configurable exactamente con los valores exigidos, sin coste y sin datos de
   producción. Eso es evidencia de capacidad, **no** evidencia de un control
   en producción, y así debe declararse.
3. Mientras no exista tenant de producción, **RF-03 no puede cerrar**: la
   mitad backend (validación de token, RBAC) sí es implementable y testeable
   ahora; la mitad IdP (política aplicada, MFA activo, evidencia exportada)
   queda `BLOCKED_EXTERNAL`.

`ADR-022 = PROPOSED / TECHNICALLY RESOLVED / PENDING COMMERCIAL APPROVAL`
`IDENTITY SECURITY GATE = BLOCKED` (implementación y evidencia pendientes)

## Estado

**Propuesta.** No aprobada. La decisión técnica está cerrada con evidencia
primaria; la decisión comercial pertenece al usuario.
