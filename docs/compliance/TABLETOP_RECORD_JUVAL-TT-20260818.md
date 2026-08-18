# Tabletop Exercise Record — `JUVAL-TT-20260818`

> Evidence for Amazon finding RF-05 (plan is exercised and reviewed).
> Escenario preparado en `TABLETOP_001_PREPARED_SCENARIO.md`. Ejercicio
> realizado como conversación guiada (el agente narró la situación y las
> preguntas de decisión; Daniel E. Liendo respondió cada una como la
> decisión real). No fue un simulacro cronometrado en vivo con reloj
> visible para ambas partes — el estimado de duración es aproximado.

## Exercise metadata

| Field | Value |
|---|---|
| Exercise ID | `JUVAL-TT-20260818` |
| Date (UTC) | 2026-08-18 |
| Facilitator | Agente (Claude), narrando el escenario e injects |
| Participants (roles) | Daniel E. Liendo (IC / Security Owner / IMPOC / Technical Responder) — participó y tomó las decisiones. Jocsimar C. Gonzalez (Deputy) **no participó** en esta sesión. |
| Plan version exercised | `0.1.0-DRAFT` |
| Duration | ~15–20 minutos (estimado por el participante) |

## Scenario

Alerta de GitHub secret scanning: posible token de acceso de Amazon
(SP-API) detectado en un commit subido al repositorio público de JUVAl,
40 minutos antes de la detección. Tomado de
`TABLETOP_001_PREPARED_SCENARIO.md`, inject 1.

## Walkthrough

| Step | Plan section | Performed? | Elapsed from "detection" | Notes |
|---|---|---|---|---|
| Detection recorded, IC assigned | §4.1 | Sí | No cronometrado (ejercicio conversacional) | Ante la alerta, Daniel confirmó que revisaría el commit él mismo antes de decidir cualquier otra cosa |
| Containment actions identified | §4.2 | **Distinto al plan** | — | El plan indica "contener primero, confirmar después" (§4.2: "Revoke first"). Daniel decidió **confirmar primero** si el string era una credencial real antes de actuar. Registrado como hallazgo (ver Gaps found) |
| Credential revocation walked | §4.3 | Sí | — | Se confirmó que JUVAl no tiene, ni ha tenido nunca, una credencial SP-API real emitida (registro `REJECTED_REMEDIATION_REQUIRED`) — no había nada que rotar |
| Amazon Information determination | §4.4 | Sí | — | Determinación: no hay Información de Amazon involucrada, porque no existe ninguna credencial real de Amazon en JUVAl hoy. Daniel confirmó esta conclusión explícitamente, citando el estado de registro como evidencia |
| Evidence preservation | §4.5 | **No ejercitado** | — | No se recorrió explícitamente en esta sesión — queda como pendiente para el próximo ejercicio (ver Gaps found) |
| **Amazon notification DRAFTED (never sent)** | §5 | N/A | N/A | No se redactó notificación: la determinación de §4.4 fue que no hay Información de Amazon involucrada |
| Recovery plan stated | §4.6 | Sí | — | Daniel indicó que limpiaría el texto del commit del repositorio como acción de higiene, aunque no fuera una credencial real |

**Time from simulated detection to a drafted Amazon notification:** N/A —
no se requirió notificación, dado que la determinación fue que no había
Información de Amazon involucrada.

## Confirmation

- [x] No message was actually sent to `security@amazon.com`.
- [x] No real credential was rotated or exposed during the exercise.
- [x] No secret value was written into any exercise artifact.

## Gaps found

| # | Gap | Severity | Corrective action | Owner | Due |
|---|---|---|---|---|---|
| 1 | El primer instinto del IC es confirmar si algo es real antes de actuar, pero el plan (§4.2) indica contener/revocar primero y confirmar después — la brecha entre el reflejo natural y el procedimiento escrito | Bajo (procedimental, no expuso nada real) | Reforzar la regla "revoke first" del §4.2 en la próxima revisión del plan o recordarla explícitamente antes del próximo tabletop | Daniel E. Liendo (Security Owner) | Antes de la próxima revisión del plan, `2027-02-18` |
| 2 | El paso de preservación de evidencia (§4.5) no se ejercitó en este ejercicio — no se sabe cómo se vería en la práctica (qué exportar, dónde guardarlo) | Bajo | Ejercitar §4.5 explícitamente en el próximo tabletop (rotar el escenario, per §10) | Daniel E. Liendo (Security Owner) | Próximo tabletop |

## Plan changes resulting

| Change | Section | New plan version |
|---|---|---|
| Ninguno aplicado todavía — los dos hallazgos de arriba quedan como recordatorio para la próxima revisión/ejercicio, no ameritan cambiar el texto del plan por sí solos | — | `0.1.0-DRAFT` (sin cambios) |
