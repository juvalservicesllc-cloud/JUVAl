# ADR-028: FusionAuth como dirección aprobada de proveedor de identidad

- Estado: **Aceptada** — 2026-08-24. Decisión explícita del usuario.
- Alcance: **selección de dirección de proveedor únicamente.** No implementa,
  no despliega, no configura, no crea tenants, no crea usuarios y no produce
  evidencia de cumplimiento para Amazon.
- Relacionada con: ADR-021 (investigación de proveedores y matriz de
  controles), ADR-022 (Okta — `RECHAZADA (SUPERSEDED)`), ADR-027 (rol de
  `juval-server`), `docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` §30,
  `docs/compliance/ACCESS_CONTROL.md`.

## Contexto

La identidad humana de JUVAl lleva abierta desde el rechazo del Developer
Profile por parte de Amazon (`REJECTED_REMEDIATION_REQUIRED`, RF-03/RF-04).
El backend ya tiene la mitad técnica implementada y probada
(`interfaces/api/auth.py`: validación OIDC/JWT y RBAC por capacidades, 33
tests negativos), pero está **inactiva** (`JUVAL_AUTH_MODE` sin definir) y no
existe ningún proveedor.

Dos decisiones previas acotan el punto de partida:

1. **ADR-022 — Okta: `RECHAZADA (SUPERSEDED)`, 2026-08-19**, por decisión
   explícita del usuario. **No se reabre en este ADR.**
2. **ADR-021** documenta una investigación larga de candidatos. Sus dos
   conclusiones relevantes aquí, citadas sin alterarlas:
   - `FusionAuth = 10/11 PASS + 1 PARTIAL`, `FUSIONAUTH = NOT FULLY
     COMPLIANT`. El propio ADR-021 lo calificó como *«Not a recommendation,
     but the closest finding this entire investigation has produced»*.
   - Un pase **posterior** dentro del mismo ADR-021 encontró **FreeIPA +
     Keycloak con `12/12`** sobre documentación primaria, y lo declaró
     *«Recommended low-cost architecture»*. Su gate empírico quedó en
     `FREEIPA_KEYCLOAK_IDENTITY_POC_GATE = ENVIRONMENT_BLOCKED` (Docker/WSL2
     ausentes en la estación de trabajo), y el ADR cerró como
     `ADR-021 = NOT_READY (documentarily 12/12, empirically unverified)`.

Es decir: **ADR-021 no seleccionó FusionAuth y clasificó por encima de él a
FreeIPA + Keycloak.** Este ADR existe precisamente para dejar constancia de
que la decisión del usuario se toma **con ese hecho a la vista**, no por
desconocerlo.

## Decisión

**`FusionAuth = SELECTED / APPROVED DIRECTION`**, por decisión explícita del
usuario (2026-08-24).

Esta decisión **prevalece sobre el ranking por evidencia de ADR-021**. La
elección de proveedor es una decisión de negocio y arquitectura del usuario
(CLAUDE.md §3); el agente aporta la evidencia, no el veredicto. ADR-021 se
conserva íntegro y sin modificar: su matriz de 12 controles, su hallazgo
`12/12` para FreeIPA + Keycloak y su clasificación `10/11 + 1 PARTIAL` para
FusionAuth siguen siendo el registro fiel de lo que se midió.

`MINIMUM_FUSIONAUTH_VERSION = 1.63.0` — restricción arquitectónica heredada
de ADR-021: la opción de tenant *«Reject passwords containing user login Id»*
sólo existe desde esa versión.

## Lo que esta decisión NO establece

Esta separación es normativa, no una advertencia de cortesía:

```
PROVIDER DECISION      = FusionAuth (SELECTED / APPROVED DIRECTION)
IMPLEMENTATION         = NOT_IMPLEMENTED  (sin tenant, sin despliegue,
                                           sin configuración, sin usuarios)
RUNTIME                = INACTIVE         (JUVAL_AUTH_MODE sin definir)
AMAZON RF-03 / RF-04   = NOT_VERIFIED     (seleccionar no es cumplir)
IDENTITY SECURITY GATE = BLOCKED          (sin cambio)
REAPPLICATION GATE     = BLOCKED          (sin cambio)
```

- **Seleccionar un proveedor no implementa nada.** No existe tenant, ni
  despliegue, ni política aplicada, ni evidencia exportada.
- **Seleccionar un proveedor no satisface ningún control de Amazon.** RF-03 y
  RF-04 siguen `PARTIAL`/`NOT_COMPLIANT` exactamente como antes de este ADR.
  Ninguna afirmación de cumplimiento puede citar este documento.
- **El gap conocido sigue abierto.** ADR-021 clasificó el control 6
  (exclusión del nombre del usuario en la contraseña) como
  `B — PARTIALLY_SATISFIED`: FusionAuth 1.63.0+ rechaza nativamente el
  *login Id* configurado, que en su propio modelo de datos es un campo
  distinto de `firstName`/`lastName`. Amazon exige rechazar *«any part of the
  user's name»*. Cerrar ese gap exige una de estas vías, ninguna decidida
  aquí: (a) riesgo residual aceptado y declarado con un control organizativo
  compensatorio, (b) respuesta de Amazon a la aclaración ya redactada (§21 de
  `SP_API_REGISTRATION_REMEDIATION.md`), o (c) evidencia nueva de producto que
  hoy no existe.
- **No se instala ni se despliega FusionAuth en esta decisión.** Ninguna
  acción operativa se deriva automáticamente de este ADR.

## Frontera con ADR-027

**FusionAuth no se alojará en `juval-server`.** ADR-027 (aceptado el mismo
día) excluye explícitamente el rol de *identity server* para ese host. Cuando
la implementación se aborde, el alojamiento concreto será una decisión
separada — y si alguna vez se propusiera `juval-server` como destino, exigiría
modificar ADR-027 primero, no interpretarlo de forma flexible.

## Alternativas consideradas

1. **FreeIPA + Keycloak** (`12/12` documental, ADR-021). **No elegida**, pese
   a ser el candidato mejor clasificado por evidencia: su verificación
   empírica nunca se ejecutó (`ENVIRONMENT_BLOCKED`) y son dos componentes
   autoalojados en lugar de uno. La decisión del usuario prevalece; el
   hallazgo queda registrado y disponible si esta dirección se revierte.
2. **Okta** (ADR-022). Descartada — decisión explícita del usuario,
   `RECHAZADA (SUPERSEDED)`. No se reabre.
3. **Mantener `RECOMMENDED IdP = NONE`.** Rechazada: era el estado anterior y
   dejaba RF-03 sin ninguna dirección, bloqueando indefinidamente cualquier
   planificación de Fase 9.
4. **CIAM gestionado (Cognito, Auth0, Entra External ID, Supabase Auth,
   Clerk, JumpCloud, ZITADEL).** Todos `REJECTED`/`ELIMINATED` en ADR-021,
   la mayoría por el control 8 (edad mínima de contraseña), que FusionAuth sí
   satisface nativamente.

## Consecuencias

- **Operativas**: FusionAuth Community es autoalojado. Parcheo del SO,
  actualizaciones del propio FusionAuth, backups de PostgreSQL, gestión de
  certificados TLS, monitorización y recuperación pasan a ser responsabilidad
  de JUVAl. ADR-021 registra este coste como *«non-zero and qualitative, not
  priced»*; sigue sin cuantificar.
- **Licencia**: `LICENSE_COST = $0` (Community). El coste de infraestructura
  no está cotizado oficialmente y ADR-021 sólo ofrece un orden de magnitud.
- **Backend**: sin cambios. `interfaces/api/auth.py` valida OIDC/JWT genérico
  (emisor, JWKS, audiencia, expiración); no contiene nada específico de
  proveedor y no requiere modificación por esta decisión.
- **Cumplimiento**: ninguna fila de RF-01…RF-05 cambia de estado por este ADR.

## Rollback

Reversible sin coste técnico mientras no exista tenant, usuarios ni
integración: hoy no hay nada desplegado que deshacer. A partir de la creación
de usuarios reales, cambiar de proveedor exigiría revisar claims, sesiones,
roles y evidencia — el mismo criterio que ADR-021 ya fijaba. FreeIPA +
Keycloak queda documentado en ADR-021 como la alternativa mejor evidenciada
si esta dirección se revierte.

## Trazabilidad

Este ADR **no modifica ni borra** ADR-021 ni ADR-022. Los tres se leen juntos:
ADR-021 es la evidencia medida, ADR-022 el cierre de Okta, y ADR-028 la
decisión de dirección del usuario tomada sobre esa evidencia. Cualquier
discrepancia aparente entre el ranking de ADR-021 y la selección de este
documento es deliberada y está explicada arriba, no es un descuido.
