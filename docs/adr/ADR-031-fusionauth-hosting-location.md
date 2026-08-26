# ADR-031 — Dónde se aloja FusionAuth

**Estado: Aceptada — Opción A (FusionAuth Community self-hosted en
`juval-server`)**, por decisión explícita del usuario, 2026-08-26.
**Fecha: 2026-08-26** (propuesta y decisión el mismo día; el texto de la
propuesta se conserva íntegro más abajo — ver §"Decisión").
**Enmienda que provoca:** ADR-027 §"Enmienda 2026-08-26" (dos cláusulas).
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

## Recomendación previa a la decisión (agente) — NO es la decisión

> Lo que sigue en esta sección es el análisis del agente **antes** de que el
> usuario decidiera, conservado sin alterar por trazabilidad. **El usuario
> eligió la Opción A, no la B.** Las razones por las que esta recomendación no
> prevaleció, y las condiciones bajo las que A es defendible, están en
> §"Decisión". Esta sección no debe citarse como la postura vigente.

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

## Decisión

**Opción A: FusionAuth Community self-hosted en `juval-server`.** Decisión
explícita del usuario, 2026-08-26, contra la recomendación del agente. Queda
`APPROVED` (CLAUDE.md §3) y este ADR pasa a `Aceptada`.

Razón dada por el usuario: `juval-server` fue adquirido y endurecido
*precisamente* para servir como infraestructura propia de JUVAl y desbloquear
los requisitos de seguridad/Amazon. La Opción B (FusionAuth Cloud) introduce un
coste recurrente no presupuestado para una capacidad que el hardware ya
existente cubre. **Esta decisión no se reabre**; el planteamiento
"Cloud vs. self-hosted" está cerrado.

### Por qué la objeción del agente no bloquea la decisión

La objeción de la Opción A tenía dos partes. La primera era real y se resuelve
por procedimiento; la segunda resultó estar mal planteada:

1. *"Contradice un ADR Aceptado"* — cierto, y por eso ADR-027 se **enmienda
   formalmente** en la misma operación, acotado a dos cláusulas nombradas
   (ADR-027 §"Enmienda 2026-08-26"). No se reinterpreta ni se ignora.
2. *"Para servir a producción habría que exponerlo a internet con TLS, lo que
   rompe la frontera de red de ADR-027"* — **esto asumía un puerto entrante**.
   No hace falta. Un túnel de **salida** publica un extremo HTTPS gestionado sin
   abrir ningún puerto de escucha, sin port-forwarding y sin IP pública estable
   (§"Frontera de red (Opción A)"). La frontera que ADR-027 protege — "no abrir
   puertos de aplicación a la LAN ni a internet" — se mantiene literalmente
   intacta: el despliegue completo se hace con **cero reglas `ufw allow`
   nuevas**.

Lo que **sí** sigue siendo cierto de la objeción, y se registra como riesgo
aceptado en §"Consecuencias": este host pasa a ser una dependencia dura de la
autenticación de producción, y su disponibilidad, parcheo y backup dejan de ser
"deseables" para ser requisitos operativos.

### Alcance exacto de lo aprobado

| Aprobado | No aprobado por este ADR |
|---|---|
| Instalar FusionAuth Community + PostgreSQL + proxy inverso en `juval-server`, todos ligados a loopback o sin regla de firewall | Alojar datos de negocio de JUVAl en esa PostgreSQL |
| Publicar hacia internet **sólo** los extremos de identidad estrictamente necesarios, vía túnel de salida | Abrir puertos entrantes en UFW o en el router |
| Producir la evidencia RF-03 de política de contraseñas contra una instancia real | Marcar `VERIFIED` ningún control sin evidencia medida |
| Mantener la administración (`/admin`, `/api`) fuera de la superficie pública | Exponer la administración, ni siquiera "temporalmente" |
| — | Activar `JUVAL_AUTH_MODE=oidc` antes de la verificación runtime |

### Frontera de red (Opción A)

Tres zonas, y ninguna transición entre ellas ocurre por defecto:

| Zona | Qué contiene | Control que la sostiene |
|---|---|---|
| **PUBLIC** | Únicamente `GET /.well-known/openid-configuration` y `GET /.well-known/jwks.json`, servidos a través del túnel de salida | Lista de rutas permitidas en el proxy inverso; todo lo demás responde 404 |
| **LAN-ONLY** | SSH `:22`; los servidores de desarrollo `:5173` y `:8000` (riesgo LAN aceptado, H-3, sin cambio) | Reglas UFW **ya existentes**; no se añade ninguna |
| **LOCALHOST / INTERNAL** | PostgreSQL `:5432`, el proxy inverso, y FusionAuth `:9011` | PostgreSQL y el proxy escuchan en `127.0.0.1`. FusionAuth **no** tiene propiedad de bind-address y escucha en todas las interfaces (verificado en su `fusionauth.properties` de plantilla, 1.69.0) — la política `DEFAULT_INPUT_POLICY="DROP"` de UFW, sin regla `allow` para `9011`, es lo que lo mantiene inalcanzable fuera del host |

Consecuencia deliberada: la administración de FusionAuth **no es alcanzable ni
desde la LAN**. El operador llega a ella con reenvío de puerto sobre SSH
(`ssh -L 9011:127.0.0.1:9011 juval@192.168.0.26`), reutilizando el único canal
autenticado que ya existe y está verificado como key-only (H-5).

El backend de JUVAl en Railway sólo necesita la zona PUBLIC, y sólo el JWKS:
`interfaces/api/auth.py` resuelve las claves desde
`<issuer>/.well-known/jwks.json` y valida emisor/audiencia/expiración
localmente — no hace ninguna otra llamada al IdP. El documento de discovery se
publica junto a él por convención OIDC y porque `tools/verify_oidc.py` lo
comprueba.

### Lo que esta decisión deja abierto (y por qué no es una excusa)

**El mecanismo concreto del túnel de salida es una decisión del usuario**, no
del agente: requiere una cuenta en un tercero y, en una de las dos opciones, un
dominio. Está aislado como un único punto de bloqueo — ver
`deploy/fusionauth/README.md` §"Fase 2". Todo lo demás (instalación, base de
datos, política de contraseñas, evidencia de los controles 1-11 salvo el 10 y
el 6, backup/restore, verificación OIDC) **no depende de esa decisión** y se
ejecuta antes, en una fase que no toca la red externa en absoluto.

## Consecuencias

**A favor**

- Coste de licencia e infraestructura `$0` — FusionAuth Community cubre los
  controles de contraseña, el bloqueo de cuenta y MFA por TOTP que Amazon exige
  (verificado 2026-08-26 contra la documentación de planes: TOTP es Community;
  email/SMS MFA y *breached password detection* son de pago y quedan
  desactivados).
- Desbloquea RF-03/RF-04, que llevaban bloqueados en una decisión, no en
  trabajo.
- Un solo host que ya está endurecido, medido y monitorizado.

**En contra — riesgos aceptados explícitamente**

| Riesgo | Consecuencia real | Mitigación acordada |
|---|---|---|
| `juval-server` pasa a ser dependencia dura de la autenticación de producción | Si el host cae, ningún usuario puede autenticarse contra el backend de Railway | Es un riesgo aceptado. No hay alta disponibilidad y **no se debe afirmar que la haya**. Antes de que existan usuarios reales debe revisarse si eso es tolerable |
| Aparece una categoría de datos no regenerable (identidad) | Un fallo de disco sin backup pierde usuarios y claves de firma de forma irrecuperable | `deploy/fusionauth/backup.sh` + procedimiento de restore probado son **requisito de despliegue**, no un extra (ADR-027 §"Enmienda", consecuencia sobre backup) |
| Superficie de ataque nueva en el único host con copia del repositorio | Una vulnerabilidad de FusionAuth alcanzable desde internet tocaría ese host | Superficie pública reducida a dos rutas de sólo lectura; administración y API REST nunca públicas; parcheo con procedimiento documentado y versión fijada |
| Hardware de 2 núcleos compartido con `pytest`, `npm build` y Playwright | Contención de CPU durante desarrollo; logins lentos | Heap de la JVM fijado; `search.type=database` (sin Elasticsearch); H-11 debe cubrir los servicios nuevos antes de considerarlo verificado |
| El emisor depende de un tercero (el túnel) | Si el túnel cae, Railway no puede obtener el JWKS y toda petición autenticada falla | Riesgo aceptado y **documentado como tal**; es la misma clase de dependencia que Railway/Vercel/Supabase ya introducen |

**Neutro**

- El control 6 (exclusión del nombre del usuario en la contraseña) **no cambia**
  con esta decisión: sigue `B — PARTIALLY_SATISFIED`. Alojar el IdP uno mismo no
  añade ningún mecanismo que inspeccione la contraseña en claro antes de
  persistirla, y construir uno sería autenticación propia, que CLAUDE.md
  prohíbe. Ver `IDENTITY_DEPLOYMENT_FUSIONAUTH.md` §2.

**Rollback**

Desinstalar es reversible y está documentado (`deploy/fusionauth/README.md`
§"Rollback"): `systemctl disable --now fusionauth-app`, `dpkg -r`, borrar la
base de datos, retirar el proxy. Nada del backend de JUVAl cambia — la frontera
OIDC es agnóstica de proveedor y `JUVAL_AUTH_MODE` vuelve a `disabled`. Si en
el futuro se prefiere la Opción B o C, el trabajo reutilizable (plantilla de
tenant, `tools/verify_oidc.py`, la propia frontera del backend) se conserva
íntegro; sólo cambia el valor del emisor.

## Estado

**Aceptada, 2026-08-26 — Opción A.** Decisión explícita del usuario, tomada con
el conflicto de ADR-027 a la vista y resuelta enmendando ADR-027 formalmente en
la misma operación.

`IMPLEMENTATION = NOT_IMPLEMENTED` en el momento de aceptar: este ADR autoriza
y define el despliegue, **no lo ejecuta**. Aceptar no es desplegar, y desplegar
no será verificar — los tres estados se mantienen separados en
`SP_API_REGISTRATION_REMEDIATION.md`.
