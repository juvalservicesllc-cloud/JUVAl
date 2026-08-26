# ADR-031 — Dónde se aloja FusionAuth

**Estado: Propuesta** — requiere decisión explícita del usuario.
**Fecha: 2026-08-26**
**Relacionada con:** ADR-027 (rol permanente de `juval-server`), ADR-028
(FusionAuth como dirección aprobada), ADR-021 (evidencia medida de
proveedores), ADR-017 (Supabase como persistencia de producción),
`docs/compliance/IDENTITY_DEPLOYMENT_FUSIONAUTH.md`,
`docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` §30.

## Contexto

ADR-028 aprobó **FusionAuth** como dirección de proveedor de identidad. Es una
selección, no una implementación: no hay tenant, no hay despliegue, no hay
configuración, y `RF-03`/`RF-04` siguen `NOT_VERIFIED`. El siguiente paso
externo (E-1, §20.5/§30) dejó de ser una compra y pasó a ser un **despliegue**.

Desplegar exige responder una pregunta que ningún ADR responde todavía:
**¿dónde corre FusionAuth?**

El candidato obvio es `juval-server`: es el host que el usuario construyó y
endureció precisamente para sostener el esfuerzo de seguridad/Amazon, ya tiene
UFW, fail2ban, SSH por clave, journald persistente y monitorización de
capacidad (`HOST_CONTROLS_JUVAL_SERVER.md`), y tiene recursos suficientes
(~1.5–2 GiB de RAM adicionales sobre 13 GiB).

**Pero ADR-027 lo prohíbe explícitamente.** Su sección "Decisión" dice, entre
lo que este host **no** es:

> **Identity server** — ningún IdP se despliega aquí; la identidad humana
> sigue `PENDING` (ADR-021/022) y, si algún día se resuelve, seguirá siendo un
> servicio gestionado externo, nunca construido en este host.

Y cierra: *"Cualquier extensión de este rol … requiere un ADR nuevo — este
documento **no** es una autorización general para crecer el rol por
conveniencia."*

ADR-027 además deriva de una instrucción textual del usuario (*"NO será
automáticamente: … identity server"*). Por lo tanto esto **no** es una
extensión compatible: es un conflicto directo con un ADR Aceptado, y con la
instrucción que lo originó. `CLAUDE.md` §3 y §18 obligan a reportar el
conflicto en vez de resolverlo silenciosamente.

Este ADR existe para que el usuario decida con el conflicto a la vista, no
para presuponer la respuesta.

## Opciones

### Opción A — FusionAuth en `juval-server` (requiere modificar ADR-027)

- **A favor**: el host ya existe, ya está endurecido y ya fue construido para
  este propósito; coste de licencia e infraestructura $0; una sola máquina que
  mantener; latencia LAN irrelevante aquí.
- **En contra**: contradice una decisión Aceptada y una instrucción explícita
  del usuario. Convierte un nodo de development/validation en un componente del
  que depende la autenticación de producción — si el backend en Railway valida
  tokens contra este emisor, **un host LAN-only pasa a ser una dependencia dura
  de producción**, y ADR-027 §"Fronteras de red" prohíbe exponerlo fuera de la
  LAN. Sin exposición pública, Railway no puede alcanzar el JWKS.
- **Consecuencia técnica decisiva**: para que sirva a producción habría que
  exponerlo a internet con TLS, lo que rompe simultáneamente la frontera de red
  de ADR-027 y aumenta la superficie de ataque del único host con acceso al
  repositorio.

### Opción B — FusionAuth Cloud (servicio gestionado del mismo proveedor)

- **A favor**: coherente con ADR-027 (*"seguirá siendo un servicio gestionado
  externo"*) y con ADR-017/ADR-018 (persistencia y backend gestionados);
  alcanzable desde Railway sin exponer la LAN; parcheo, TLS, backups y
  disponibilidad los opera el proveedor; **no requiere modificar ningún ADR
  Aceptado**.
- **En contra**: coste recurrente no presupuestado (ADR-021 registró
  `LICENSE_COST = $0` sólo para Community self-hosted); requiere alta en un
  tercero.

### Opción C — FusionAuth self-hosted en un host dedicado nuevo (VPS)

- **A favor**: no toca `juval-server` ni su ADR; alcanzable desde Railway;
  mantiene `LICENSE_COST = $0`.
- **En contra**: introduce un host de producción nuevo que hay que endurecer,
  parchear, monitorizar y respaldar — el trabajo que
  `HOST_CONTROLS_JUVAL_SERVER.md` documentó para un host, repetido para otro,
  y esta vez expuesto a internet. ADR-021 ya advirtió que la operación
  self-hosted **no está presupuestada**.

### Opción D — despliegue local sólo para verificación, producción aparte

`juval-server` aloja una instancia FusionAuth **exclusivamente** para producir
la evidencia de configuración que Amazon pide (política de contraseñas, MFA,
lockout, JWKS, emisión de tokens), sin que ningún sistema de producción
dependa jamás de ella; la instancia de producción se decide después (B o C).

- **A favor**: desbloquea RF-03 parcialmente **hoy** — la evidencia de que la
  política es configurable a los valores exactos de Amazon es exportable desde
  cualquier instancia; no crea dependencia de producción; sigue LAN-only, así
  que no rompe las fronteras de red de ADR-027.
- **En contra**: sigue siendo "un IdP desplegado aquí", que es literalmente lo
  que ADR-027 excluye — requiere igualmente una modificación acotada de
  ADR-027, aunque mucho más estrecha que la Opción A. Y la evidencia de
  *configuración* no es evidencia de *operación*: no demuestra que la identidad
  de producción esté gobernada por esa política.

## Recomendación

**Opción B para producción**, y **Opción D sólo si el usuario quiere adelantar
la evidencia de configuración** mientras decide.

Razonamiento: B es la única opción que no exige modificar un ADR Aceptado, es
la que ADR-027 ya anticipó en su propio texto (*"servicio gestionado
externo"*), y es coherente con el resto de la arquitectura, que ya delega
persistencia (Supabase) y hosting (Railway) en servicios gestionados. A es la
más tentadora y la peor: convierte el nodo de desarrollo en dependencia dura de
producción y obliga a exponerlo a internet.

**Esta recomendación no se implementa sin decisión del usuario.** El coste
recurrente de B es real y no está presupuestado, y ésa es exactamente la clase
de decisión que `CLAUDE.md` §3 reserva al usuario.

## Consecuencias

- Mientras este ADR siga `Propuesta`, **no se despliega FusionAuth en ningún
  sitio**, y `RF-03`/`RF-04` permanecen `NOT_VERIFIED`. El bloqueo es una
  decisión pendiente, no una limitación técnica.
- Si se acepta A o D, **ADR-027 debe modificarse explícitamente** en la misma
  operación — nunca reinterpretarse. La modificación debe ser mínima y nombrar
  qué frontera se mueve y cuál se mantiene.
- Si se acepta B o C, ADR-027 queda intacto y este ADR sólo registra dónde vive
  el servicio.
- Ninguna opción cierra el control 6 (exclusión del nombre,
  `B — PARTIALLY_SATISFIED`, ADR-021). Es independiente del alojamiento.

## Estado

**Propuesta, 2026-08-26.** No implementada. Requiere decisión explícita del
usuario entre A, B, C o D, y — en los casos A y D — una modificación
explícita de ADR-027.
