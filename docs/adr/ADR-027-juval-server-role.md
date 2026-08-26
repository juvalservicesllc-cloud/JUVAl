# ADR-027 — `juval-server` role: development / validation / backend-worker / automation node

**Estado: Aceptada — ENMENDADA 2026-08-26 por ADR-031**
**Fecha: 2026-08-24** (enmienda: 2026-08-26, ver §"Enmienda 2026-08-26")
**Relacionada con:** ADR-016 (FastAPI backend), ADR-017 (Supabase persistencia
remota), ADR-018 (Railway hosting del backend), ADR-021/ADR-022 (identidad —
sin relación operativa, mencionada solo porque este host nunca sirve
autenticación), `docs/compliance/HOST_CONTROLS_JUVAL_SERVER.md`,
`docs/compliance/NETWORK_SECURITY.md`.

## Contexto

Un segundo nodo físico, `juval-server` (Ubuntu Server 24.04.4 LTS, AMD Ryzen
3 3250U, ~13 GiB RAM, ~98 GiB de raíz, LAN-only en `192.168.0.26`), se sumó al
desarrollo de JUVAl junto al puesto Windows original y GitHub Actions. Hasta
este ADR, su rol nunca se decidió explícitamente — solo se verificó
empíricamente qué hace hoy (`HOST_CONTROLS_JUVAL_SERVER.md`, medido
2026-08-24): sostiene una copia de trabajo del repositorio, corre el backend
Python (`.venv`) y el frontend (Node vía `nvm`), y no ejecuta ningún servicio
JUVAl persistente (`systemctl list-units | grep -i juval` no devuelve
unidades de aplicación). CLAUDE.md §3 exige que una decisión de este tipo
(arquitectura/infraestructura) quede marcada explícitamente `APPROVED` o
`PENDING` — dándole a este host un rol de facto sin ADR sería exactamente el
tipo de decisión silenciosa que el contrato operativo prohíbe.

La pregunta concreta que motiva este ADR: ¿qué es `juval-server`
*permanentemente*, y qué NO es, para que ningún trabajo futuro (backups,
monitoring, un servicio systemd, una base de datos local) se construya
asumiendo un rol que nadie aprobó?

## Decisión

**`juval-server` es un nodo permanente de development / CI-like validation /
backend-worker (cuando corresponda) / automation / operational tooling.**

Concretamente, este host puede legítimamente:

- sostener una copia de trabajo del repositorio y ejecutarla localmente
  (backend `pytest`, frontend `npm test`/`build`/`lint`, E2E Playwright)
  como validación equivalente/complementaria a GitHub Actions, especialmente
  para lo que CI no puede reproducir (navegador real, hardware Linux real);
- ejecutar trabajos de automatización operativa (scripts de mantenimiento,
  verificación de cumplimiento, tareas programadas de bajo riesgo) bajo la
  cuenta `juval`, con `systemd --user` o cron de usuario — nunca como root;
- actuar como **backend-worker** puntual si una tarea concreta lo requiere
  (p. ej. ejecutar un lote de procesamiento manualmente) — esto no lo
  convierte en un servicio persistente salvo que una necesidad real y un ADR
  posterior lo autoricen explícitamente (regla de oro, CLAUDE.md §4).

Y **no** es, ni se convierte automáticamente en, ninguno de:

- **Production primary database** — la persistencia de producción es
  Supabase/PostgreSQL (ADR-017), no SQLite ni Postgres local en este host.
- **Supabase self-host** — Supabase es un servicio gestionado externo
  (ADR-017); este host no aloja una instancia propia.
- **Identity server** — ~~ningún IdP se despliega aquí; la identidad humana
  sigue `PENDING` (ADR-021/022) y, si algún día se resuelve, seguirá siendo
  un servicio gestionado externo, nunca construido en este host~~ —
  **ENMENDADO 2026-08-26 por ADR-031 (Aceptada, Opción A)**: este host **sí**
  aloja FusionAuth Community self-hosted como IdP de JUVAl. Lo que **no**
  cambia: JUVAl no construye autenticación propia (CLAUDE.md §12/§16 sigue
  vigente — se despliega un producto de identidad de terceros, no se escribe
  uno). Alcance exacto de la enmienda en §"Enmienda 2026-08-26".
- **Único servidor de producción pública** — la producción es Railway
  (backend, ADR-018) + Vercel (PWA, ADR-014 más el ADR de deployment
  pendiente); `juval-server` no está expuesto fuera de la LAN (§3, evidencia
  H-3 de `HOST_CONTROLS_JUVAL_SERVER.md`: solo `:22` escuchando en todas las
  interfaces).
- **Reemplazo automático de Vercel/Railway** — nada de lo anterior cambia
  porque este host sea técnicamente capaz de correr el mismo código; sería
  exactamente la confusión entre "puedo hacerlo" y "debemos hacerlo" que
  CLAUDE.md §4 prohíbe.

Cualquier extensión de este rol (convertirlo en servidor de producción,
alojar una base de datos que otros sistemas consulten, exponerlo fuera de la
LAN) requiere un ADR nuevo — este documento **no** es una autorización
general para crecer el rol por conveniencia.

## Alternativas consideradas

1. **No formalizar el rol (statu quo implícito).** Rechazada: viola CLAUDE.md
   §3 (decisión de infraestructura sin marcar APPROVED/PENDING) y deja a
   trabajo futuro (backup, monitoring, systemd units) sin límite declarado
   contra el cual verificarse.
2. **Declarar `juval-server` como servidor de producción secundario /
   réplica.** Rechazada: no hay necesidad real verificada (Railway/Vercel ya
   cubren producción, ADR-018/ADR-014), y contradice la separación entre
   development/CI y producción que el resto de la arquitectura ya asume
   (`HOST_CONTROLS_JUVAL_SERVER.md` §"Scope"). Introduciría una segunda
   fuente de verdad de datos sin que exista un caso de uso que lo requiera.
3. **Rol permanente de development/validation/automation, sin persistencia de
   producción (elegida).** Es la descripción exacta de lo que el host ya
   hace, medido, y no añade capacidad sin necesidad verificada — consistente
   con Ponytail (§5: minimalismo de implementación) y con la Fase actual del
   proyecto (§22: no adelantar fases futuras).

## Fronteras de seguridad

- La cuenta `juval` (uid 1000) es la única cuenta humana; pertenece al grupo
  `sudo` — las acciones administrativas requieren contraseña interactiva
  (`sudo -n true` falla sin ella, verificado), no hay sudo sin contraseña
  configurado.
- Ningún servicio JUVAl corre como root. Cualquier `systemd` unit que se cree
  para automatización debe ejecutar bajo `juval` (o un usuario de servicio
  dedicado sin shell si la tarea lo justifica), con `WorkingDirectory`
  explícito y sin secretos embebidos en la unit (Gate 7 de la misión que
  originó este ADR).
- Secretos (`.env`, `frontend/.env.local`) están presentes localmente para
  desarrollo pero **git-ignored y nunca han sido staged**
  (`tools/compliance_check.py::secret_scan`, verificado 2026-08-24 sobre 315
  archivos) — este host nunca es la fuente de verdad de un secreto de
  producción; los secretos de producción viven en Railway/Vercel/Supabase.
- El repositorio en este host no tiene ninguna razón para retener
  credenciales de producción reales; si alguna vez las necesita para una
  tarea puntual, se tratan como el resto del proyecto trata secretos
  (`docs/compliance/SECRETS.md`), nunca committeadas.

## Fronteras de red

- LAN-only: `192.168.0.26`, sin exposición documentada a internet. Único
  puerto en escucha en todas las interfaces es `:22` (SSH); `:53` (DNS local)
  está atado a loopback únicamente (`ss -tulnp`, evidencia H-3,
  `HOST_CONTROLS_JUVAL_SERVER.md`).
- Este host no debe abrir puertos de aplicación (HTTP/API) a la LAN ni a
  internet como parte de su rol permanente — si un caso de uso futuro lo
  requiriera (p. ej. servir el frontend localmente para probarlo desde otro
  dispositivo de la LAN), es una decisión puntual y temporal, no un cambio de
  rol, y no debe exponerse fuera de la LAN sin una decisión nueva.
  **ENMENDADO 2026-08-26 (ADR-031)**: "una decisión nueva" es exactamente lo
  que ADR-031 registra. La frontera se mueve **sin abrir ningún puerto de
  escucha**: FusionAuth (`:9011`), su proxy (`127.0.0.1`) y PostgreSQL
  (`127.0.0.1`) **no reciben regla `ufw allow` alguna**, de modo que la
  política `DEFAULT_INPUT_POLICY="DROP"` ya verificada (H-1) los mantiene
  inalcanzables incluso desde la LAN. La alcanzabilidad pública se resuelve
  con un túnel **de salida** hacia un extremo HTTPS gestionado, no con un
  puerto entrante — ver ADR-031 §"Frontera de red (Opción A)" y
  `deploy/fusionauth/README.md`.
- UFW y fail2ban están activos (`systemctl is-active`); el ruleset exacto
  sigue sin verificarse por falta de sudo — ver Gate 4 de la auditoría de
  hardening en curso (`HOST_CONTROLS_JUVAL_SERVER.md` H-1/H-2).

## Fronteras de datos

- Este host **no** almacena datos de producción de JUVAl. No hay base de
  datos local con `SourcingRecord`s reales, no hay `ExecutionRun`s de
  producción persistidos aquí — la persistencia de producción es Supabase
  (ADR-017). Verificado 2026-08-24: no existe ningún `.db`/`.sqlite*` en el
  árbol de trabajo (la base SQLite de pruebas E2E es generada y
  git-ignorada, `da4d546`).
- Los únicos artefactos que este host produce y no están en GitHub son
  resultados de ejecución local (reportes de test, builds efímeros de
  `frontend/dist`) — regenerables desde el código fuente, no datos
  irrecuperables.
- Si una tarea de automatización futura necesitara persistir estado local
  (p. ej. un log de ejecuciones de un job programado), ese estado se trata
  como dato operativo del host (§"Expectativas de backup" abajo), nunca como
  sustituto de la persistencia de producción.

## Limitaciones de producción

- Este host **no** debe recibir tráfico de producción, ni real ni de prueba
  con datos reales de clientes/Amazon. Cualquier prueba contra fuentes
  externas reales (Amazon, Supabase de producción) sigue las mismas reglas
  que en cualquier otro entorno de desarrollo (CLAUDE.md §13/§16).
- Este host no participa en el pipeline de deployment de producción
  (Railway/Vercel) más allá de ser, como cualquier máquina de desarrollo, un
  lugar desde el cual un humano podría ejecutar `railway`/`vercel` CLI
  manualmente — eso no lo convierte en infraestructura de producción.
- No se instalan aquí stacks de observabilidad, bases de datos gestionadas, ni
  ningún componente cuyo único propósito sea simular "producción" en este
  host — si se necesita un entorno de staging real, es una decisión nueva.

## Expectativas de backup

- **Código fuente**: ya cubierto — GitHub (`origin`) es el remoto
  versionado; el árbol de trabajo de este host es 100% recuperable
  reclonando, siempre que no haya trabajo sin commitear (regla operativa:
  no dejar trabajo importante sin push por más de una sesión).
- **Configuración local** (dotfiles de shell, configuración de `nvm`, config
  de `git` no sensible): backup deseable pero no crítico — se reconstruye en
  minutos siguiendo `docs/DEVELOPMENT_ENVIRONMENT.md`. No se considera
  bloqueante para el rol de este ADR.
- **Secretos**: explícitamente **fuera** del alcance de cualquier backup a
  un destino que no sea, como mínimo, tan seguro como el propio host —
  nunca a un repositorio Git, nunca a un destino sin cifrar. Si no existe un
  destino de backup seguro verificado, la decisión correcta es no hacer
  backup de secretos, no improvisar uno inseguro.
- **Datos/base de datos**: no aplica — este host no tiene datos de
  producción que respaldar (§"Fronteras de datos"). Si eso cambia, este ADR
  debe revisarse antes de asumir que el mecanismo de backup existente basta.
- Implementación concreta y evidencia de restore: `docs/compliance/HOST_CONTROLS_JUVAL_SERVER.md` §3 (H-12) y el trabajo de la auditoría de hardening en curso (Gate 5).

## Expectativas de recuperación

- Ningún servicio JUVAl necesita sobrevivir un reboot hoy — no hay unidades
  `systemd` de aplicación en este host (verificado 2026-08-24). Tras un
  reboot, el host queda utilizable en cuanto un humano inicia sesión;
  `unattended-upgrades` y `logrotate.timer` están `enabled` y se reinician
  solos.
- `nvm` carga desde `.bashrc`, por lo que una sesión SSH no interactiva
  (`ssh host 'node --version'`) no lo ve — cualquier automatización debe
  cargarlo explícitamente, no asumir un shell interactivo.
- Si en el futuro se crean `systemd` units (p. ej. para monitoring
  programado, Gate 6), deben declarar orden de arranque explícito, política
  de reinicio razonable (`Restart=on-failure`, no reinicio infinito sin
  límite), y un chequeo de salud verificable — nunca asumidos "funcionando"
  sin evidencia.

## Expectativas de observabilidad

- Monitoring en este host debe cubrir, como mínimo, lo que Gate 6 de la
  auditoría de hardening en curso defina: disco, RAM, carga, temperatura,
  salud de servicios, unidades `systemd` fallidas, estado de backup,
  crecimiento de logs — con mecanismos simples y auditables (scripts +
  `systemd --user` timers o cron de usuario), evitando stacks de
  observabilidad grandes para este hardware (Ponytail, CLAUDE.md §5).
- Los logs relevantes ya existen vía `systemd-journald` (persistente,
  `/var/log/journal`) y `rsyslog` (`/var/log/auth.log`, modo `0640
  syslog:adm`) — cualquier automatización nueva debe loguear vía
  `journald`, no reinventar un mecanismo de logging propio.
- Ninguna alerta de este host debe enviarse a un canal que exponga datos
  sensibles (secretos, contenido de Amazon Information) — solo métricas
  operativas del host.

## Consecuencias

**A favor:** cierra una decisión de infraestructura que llevaba meses siendo
implícita; da un límite claro contra el cual medir cualquier trabajo futuro
en este host (backup, monitoring, hardening); no introduce ninguna capacidad
nueva — documenta exactamente lo que el host ya hace y lo que explícitamente
no hace.

**En contra:** ninguna práctica — es puramente declarativo sobre el estado
actual. El único costo es el mantenimiento del documento si el rol cambia.

**Rollback:** si el usuario decide en el futuro que este host sí debe alojar
un servicio persistente o datos de producción, ese es un ADR nuevo que
sustituye a este, no una reinterpretación de este documento.

## Enmienda 2026-08-26 (ADR-031, Opción A)

El usuario decidió que **FusionAuth Community self-hosted es el IdP de JUVAl y
reside en `juval-server`** (ADR-031, `Aceptada`). Esa decisión es incompatible
con dos frases de este documento. La enmienda es deliberadamente **estrecha**:
se mueven dos fronteras nombradas y **todo lo demás sigue vigente sin cambio**.

### Qué cambia (exactamente dos cosas)

| # | Cláusula original | Estado tras la enmienda |
|---|---|---|
| 1 | §Decisión → "**Identity server** — ningún IdP se despliega aquí … seguirá siendo un servicio gestionado externo" | **Derogada.** `juval-server` aloja FusionAuth. La razón que la originaba (no construir autenticación propia) se preserva íntegra: se despliega software de identidad de terceros, no se escribe. |
| 2 | §Fronteras de red → "no debe abrir puertos de aplicación … no debe exponerse fuera de la LAN sin una decisión nueva" | **Satisfecha, no derogada.** ADR-031 *es* la decisión nueva que la cláusula exigía. Y el mecanismo elegido no abre ningún puerto entrante: túnel de salida, cero reglas `ufw allow` nuevas. |

### Qué NO cambia (sigue vigente y verificable)

- **Production primary database** — sigue siendo Supabase (ADR-017). La
  PostgreSQL que se instala aquí es **exclusivamente el almacén interno de
  FusionAuth**; no contiene `SourcingRecord`s, `ExecutionRun`s ni ningún dato
  de negocio de JUVAl, y no la consulta ningún otro sistema.
- **Supabase self-host** — sigue excluido.
- **Único servidor de producción pública** — sigue excluido. Railway (backend)
  y Vercel (PWA) no se mueven. Este host pasa a alojar **un** servicio del que
  la producción depende (el emisor OIDC), lo que es un cambio real de riesgo y
  se registra como tal en ADR-031 §"Consecuencias", no se minimiza.
- **Reemplazo automático de Vercel/Railway** — sigue excluido.
- **Sin sudo sin contraseña; ningún servicio JUVAl como root** — se mantiene y
  se refuerza: el paquete `.deb` de FusionAuth crea la cuenta de sistema
  `fusionauth` (`useradd -M -r -s /usr/sbin/nologin -d /usr/local/fusionauth`)
  y la unit `fusionauth-app.service` corre `User=fusionauth Group=fusionauth`
  — verificado leyendo `postinst` y la unit del paquete 1.69.0 con
  `dpkg-deb`, 2026-08-26, sin instalar nada.
- **Secretos nunca en Git** — se mantiene. La contraseña de PostgreSQL y la API
  key de FusionAuth viven en ficheros del host con permisos restringidos, nunca
  en el repositorio (`deploy/fusionauth/fusionauth.env.example` sólo lleva
  nombres y marcadores).
- **Fronteras de datos** — este host sigue sin almacenar datos de producción de
  JUVAl. Almacena **datos de identidad**, que son una categoría nueva y por eso
  §"Expectativas de backup" cambia: ver abajo.
- **Toda §Fronteras de seguridad, §Limitaciones de producción,
  §Expectativas de recuperación y §Expectativas de observabilidad** — vigentes.

### Consecuencia sobre §"Expectativas de backup"

La línea *"**Datos/base de datos**: no aplica — este host no tiene datos de
producción que respaldar … Si eso cambia, este ADR debe revisarse antes de
asumir que el mecanismo de backup existente basta"* **se activa ahora**. Los
datos de identidad (usuarios, credenciales hasheadas, claves de firma) **no son
regenerables desde Git**, a diferencia de todo lo demás en este host. El plan
de backup/restore concreto vive en `deploy/fusionauth/README.md` y su script
`deploy/fusionauth/backup.sh`; es un requisito de despliegue, no un extra.

### Lo que esta enmienda NO autoriza

- No autoriza alojar aquí datos de negocio de JUVAl.
- No autoriza abrir puertos entrantes en UFW ni port-forwarding en el router.
- No autoriza exponer la UI de administración de FusionAuth (`/admin`) ni su
  API REST (`/api`) fuera del host.
- No autoriza activar `JUVAL_AUTH_MODE=oidc` antes de la verificación runtime.

Cualquiera de esas cuatro cosas requiere, otra vez, una decisión nueva.

## Estado

**Aceptada, 2026-08-24.** Deriva directamente de la instrucción explícita del
usuario ("juval-server tendrá como rol permanente: development;
CI-like validation; backend/worker cuando corresponda; automation;
operational tooling. NO será automáticamente: primary production database;
Supabase self-host; identity server; único public production server;
reemplazo automático de Vercel/Railway") — este ADR formaliza esa decisión
según la convención existente en `docs/adr/`, sin añadir alcance no
autorizado.

**Enmendada, 2026-08-26**, por decisión explícita del usuario registrada en
ADR-031 (`Aceptada`, Opción A): la exclusión "identity server" queda derogada
y la frontera de red queda satisfecha por esa misma decisión. La enmienda es
acotada a esas dos cláusulas — ver §"Enmienda 2026-08-26". El resto de este
ADR sigue Aceptado y sin cambios; este documento **no** queda superseded.
