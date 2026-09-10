# ADR-036 — Almacén de sesiones duradero para el BFF

**Estado: Aceptada**, por decisión explícita del usuario (2026-09-09).
**Fecha: 2026-09-09.** Reemplaza el borrador `Propuesta` del mismo número.
**Relacionada con:** ADR-034 (BFF — esta decisión es su prerrequisito de
activación), ADR-017 (Supabase/PostgreSQL como persistencia de producción),
ADR-018 (Railway), ADR-032 (ciclo de vida de credenciales), ADR-035 (Control 6),
`supabase/migrations/20260909000004_identity_sessions.sql`,
`src/juval/infrastructure/persistence/postgres_session_store.py`,
`src/juval/infrastructure/crypto/token_cipher.py`.

## Contexto

ADR-034 puso los tokens OAuth en el servidor, lo que dio al backend un estado
de sesión que nunca había tenido: todos los endpoints anteriores eran sin
estado. Railway puede ejecutar varias instancias. Sin almacenamiento
compartido fallan **dos** cosas, y la segunda es la que se pasa por alto: una
sesión creada en la instancia A es desconocida en la B, **y** un login iniciado
en A no puede completarse por un callback que aterrice en B — el
`OAuthTransaction` con el `code_verifier` y el `state` vive sólo en A.

## Decisión

**Sesiones duraderas en la instancia PostgreSQL/Supabase ya aprobada
(ADR-017)**, detrás de los puertos existentes de
`application/session_store.py`.

### Por qué no las alternativas

| Opción | Veredicto |
|---|---|
| **En memoria** | **Rechazada para producción.** No sobrevive a un reinicio ni cruza instancias. Permitida — y sólo permitida — en tests unitarios, tests de integración y desarrollo local de un solo proceso |
| **Redis / almacén externo** | **Diferida.** Introduce proveedor, credencial, coste recurrente y monitorización nuevos para un volumen de sesiones que es el equipo interno del usuario. Si algún día la latencia de una consulta indexada por id resulta ser un problema medido, se reabre con un ADR propio |
| **Cookie firmada/cifrada** | **Rechazada por contradicción directa con ADR-034**, no por preferencia. Serializar el access/refresh token hacia el navegador — aunque vaya cifrado — devuelve los tokens al navegador y hace que la seguridad dependa de una clave de cifrado en lugar de la *ausencia* del secreto. Además no permite revocación inmediata: una cookie válida lo sigue siendo hasta expirar |

### Modelo de datos

Dos tablas de infraestructura de identidad, deliberadamente **separadas** de
`execution_runs`/`execution_run_records`/`batches`: aquéllas son la traza de
auditoría del dominio del producto (ADR-013/017/019), éstas son ciclo de vida
de seguridad. Mezclarlas haría que "borrar las sesiones de un usuario" y
"borrar una corrida" fueran la misma clase de operación, y no lo son.

`identity_sessions`: `session_digest` (PK), `subject`, `roles`, `csrf_digest`,
`access_token_ciphertext`, `refresh_token_ciphertext`, `crypto_key_id`,
`access_token_expires_at`, `created_at`, `last_seen_at`, `expires_at`,
`revoked_at`, `refresh_generation`.

`identity_oauth_transactions`: `transaction_digest` (PK), `state_digest`,
`nonce_digest`, `code_verifier_ciphertext`, `crypto_key_id`, `redirect_uri`,
`return_to`, `created_at`, `expires_at`.

**Lo que NO se guarda, y por qué:**

- **el id de sesión en claro** — es una credencial portadora: quien lo tiene
  *es* el usuario. Guardarlo verbatim convierte un `SELECT` sobre la tabla en
  un kit de secuestro de sesiones. Se guarda `SHA-256`, igual de consultable
  (el servidor hashea lo que presenta el navegador) e inútil para suplantar.
  Hash simple y no un KDF de contraseñas **a propósito**: son 256 bits de
  CSPRNG, no hay diccionario que atacar y un KDF lento añadiría latencia a cada
  petición a cambio de nada;
- **el token CSRF en claro** — mismo razonamiento, mismo tratamiento;
- **`state` y `nonce` en claro** — sólo se comparan, así que basta el digest;
- **contraseñas, secretos TOTP** — JUVAl nunca los recibe;
- **el `code_verifier` tras el callback** — la fila se borra al consumirla;
- **claims completos del ID token** — `subject` y `roles` es todo lo que
  necesita la decisión de autorización.

El `code_verifier` es la única excepción a "digest en vez de valor": el
intercambio de token necesita su texto plano, así que se **cifra**.

Esta asimetría está impuesta por tipos, no por disciplina: `Session` y
`OAuthTransaction` (lo que el BFF crea, con los valores en claro) son tipos
distintos de `SessionRecord` y `OAuthTransactionRecord` (lo que un almacén
devuelve, sólo con digests). Así el adaptador en memoria obedece exactamente la
misma regla que el de PostgreSQL en lugar de ser calladamente más permisivo.

### Modelo criptográfico

**Primitiva**: AES-256-GCM (`cryptography`, ya presente como dependencia
transitiva de `pyjwt[crypto]` — **no se añade ninguna dependencia**). Es AEAD:
una sola primitiva da confidencialidad e integridad, así que un texto cifrado
manipulado falla al descifrar en vez de producir basura silenciosamente. **No
se compone criptografía a mano.**

**Formato versionado**: `v1.<key_id>.<nonce b64url>.<ciphertext||tag b64url>`.
El prefijo de esquema permite introducir un `v2` (otra cifra, otro KDF) y
leerlo junto al `v1` sin día de corte.

**Nonce**: 96 bits, `os.urandom`, **uno nuevo por cifrado**. GCM pierde
confidencialidad *e* integridad de forma catastrófica si se reutiliza un nonce
con la misma clave; por eso no se deriva de nada.

**Datos asociados (AAD)**: cada cifrado se liga a la fila y a la columna a la
que pertenece (`digest de sesión` + nombre de campo). Mover un texto cifrado de
refresh al campo de access, o a la fila de otro usuario, **falla la
autenticación** en vez de descifrar. La confidencialidad sola no detectaría eso.

**Origen de la clave**: variable de entorno `JUVAL_SESSION_ENCRYPTION_KEYS`,
formato `<key_id>:<clave base64 de 32 bytes>[,...]`. La primera entrada es la
primaria y cifra; todas descifran. **Nunca** en una tabla de Supabase, **nunca**
en el repositorio, **nunca** en una variable `VITE_*` (ésas se compilan dentro
del bundle del navegador). Ninguna función de este módulo registra, imprime ni
devuelve material de clave.

**Rotación**: aditiva. Se añade una clave nueva como primaria conservando la
anterior; `needs_reencryption()` marca los sobres antiguos para volver a
cifrarlos de forma oportunista en una escritura que ya iba a ocurrir; cuando no
quedan filas con la clave vieja, se retira del keyring. Sin trabajo de
migración.

**No se afirma que el cifrado en reposo de Supabase proteja el texto plano.**
Protege el disco, no la tabla. Cualquier cosa que pueda leer la fila — una
cadena de conexión filtrada, un rol demasiado amplio, un backup, una consulta
de soporte — tendría tokens OAuth vivos. Por eso el texto cifrado lo produce y
consume JUVAl, y la clave no entra en esta base de datos.

**Comportamiento ante fallo**: un fallo de descifrado (clave equivocada, clave
rotada fuera, texto corrupto, AAD que no cuadra) se trata como **sesión
inválida**, nunca como error a propagar. Se falla cerrado y el llamador vuelve
a autenticarse. Todas las causas comparten un único tipo de error a propósito:
distinguirlas sería una señal con forma de oráculo, y la respuesta correcta es
la misma en todos los casos.

### TTL, revocación, limpieza

- Sesión: 8 h; transacción OAuth: 10 min.
- Revocación: `revoke()` marca `revoked_at` y **borra los textos cifrados**;
  `load()` devuelve `None` para una sesión revocada. El logout revoca en el
  servidor — borrar sólo la cookie dejaría un id de sesión válido y usable por
  quien lo hubiera capturado.
- Limpieza: perezosa al leer, más `purge_expired()` invocable. Sin tarea en
  segundo plano en este corte.
- Uso único de la transacción: `DELETE ... RETURNING` en una sola sentencia, así
  que un callback repetido o concurrente no encuentra nada. Lo garantiza la
  base de datos, no el tiempo de la aplicación.

### Rotación de refresh y concurrencia

`replace_tokens` es un `UPDATE ... WHERE refresh_generation = %s`. De dos
refrescos concurrentes gana exactamente uno; al perdedor se le **dice** que
perdió y relee en vez de sobrescribir un refresh token que el ganador ya usó.
Eso es lo que impide la actualización perdida.

**El id de sesión no rota en el refresco.** Rotarlo invalidaría la cookie de
todas las demás peticiones en vuelo del mismo navegador — un cierre de sesión
autoinfligido bajo concurrencia normal. Lo que se reemplaza es el *refresh
token*, que es de lo que trata la rotación en OAuth.

- IdP rechaza el refresh → la sesión se **revoca**: conservar un refresh token
  rechazado es peor que no tener ninguno, y un token repetido hace la sesión
  sospechosa.
- IdP inalcanzable → la sesión se conserva: el RBAC de JUVAl autoriza con los
  roles capturados en el login y no llama al IdP por petición.
- Fallo de escritura en base tras un refresh exitoso → no se persiste nada; el
  siguiente intento parte de la generación almacenada. El coste es un refresh
  desperdiciado, no una sesión rota.

### Semántica multi-instancia y fallo

Cualquier instancia puede leer cualquier sesión y consumir cualquier
transacción. Si la base no responde no hay login — aceptable, porque sin base
tampoco hay producto, pero queda escrito.

**Fail-closed, sin degradación silenciosa**: `bff.py::build_stores` levanta
`RuntimeError` si falta el DSN, falta la clave, el backend es desconocido, o se
pide `memory` con `JUVAL_AUTH_MODE=oidc` sin el opt-in explícito
`JUVAL_SESSION_STORE_MEMORY_CONFIRM=yes-single-process-development-only`.
El modo de fallo que importa no es "el almacén duradero no estaba disponible",
sino "no estaba disponible y nadie se enteró, así que los logins empezaron a
funcionar de forma intermitente entre instancias".

**Cuándo se levanta — corregido 2026-09-10.** Este ADR decía «al arrancar» y la
implementación original lo hacía de forma perezosa, en la primera petición que
tocara el BFF: un DSN malo se habría manifestado como un 500 intermitente en la
instancia que atendiera esa petición, que es exactamente el modo de fallo que
el párrafo anterior dice evitar. Ahora la validación ocurre en el `lifespan` de
FastAPI (`interfaces/api/main.py::_lifespan` → `bff.ensure_configured()`), así
que una configuración inválida **impide arrancar el proceso**.

**Un único punto de inicialización.** `ensure_configured()` es idempotente y es
el único sitio donde se eligen los almacenes; login, callback, resolución de
sesión, refresh, CSRF y logout llegan a ellos por `session_store()` /
`transaction_store()`, que lo invocan primero. Antes de esa corrección los
consumidores leían el global de módulo directamente y podían responder desde el
adaptador en memoria de pre-inicialización aunque la selección fuera PostgreSQL
— fail-closed, pero sin sesión duradera.

**Despliegue sólo-bearer.** Si `JUVAL_AUTH_MODE=oidc` pero no hay ninguna
variable del BFF definida, no existe flujo de navegador: `/login` y `/callback`
responden 404 y **ninguna sesión puede crearse**, así que no se exige base de
datos. No es un fallback: nombrar `JUVAL_SESSION_STORE` fuerza la comprobación
igualmente, y una configuración *parcial* del BFF aborta el arranque.

### Migración, RLS y observabilidad

`supabase/migrations/20260909000004_identity_sessions.sql` (+ `.down.sql`).
Dos índices y ninguno más: `expires_at` en cada tabla, para las barridas; la
búsqueda y la revocación usan la clave primaria.

**RLS activado con cero políticas, de forma permanente.** A diferencia de
`execution_runs`, esto no es "todavía no hay identidad contra la que escribir
una política": **ningún navegador y ninguna API key anon/authenticated de
Supabase debe leer jamás estas tablas.** El único cliente legítimo es el
backend conectando como propietario por PostgreSQL directo, que salta RLS por
diseño. **Corolario operativo, medido 2026-09-10**: `FORCE ROW LEVEL SECURITY`
queda deliberadamente sin activar y `JUVAL_SESSION_DB_URL` **debe** conectar con
el rol propietario de las tablas; un rol más estrecho recibiría cero filas y
todos los logins fallarían cerrados. Con RLS y sin políticas, la superficie PostgREST falla cerrada, de modo
que una anon key expuesta por accidente no puede convertirse en un volcado de
sesiones.

Observabilidad sin secretos: `crypto_key_id` hace visible el avance de una
rotación en SQL; `last_seen_at` da actividad; `refresh_generation` da recuento
de refrescos. Ninguno es material sensible.

## Consecuencias

- Desbloquea `JUVAL_AUTH_MODE=oidc` en un despliegue multi-instancia.
- Añade una dependencia de base de datos al camino de autenticación.
- Es una tabla nueva en una base que ya existe: sin proveedor nuevo, sin coste
  nuevo, **sin dependencia nueva**.
- Aparece una clave de cifrado que gestionar. Es un secreto de despliegue real
  con ciclo de vida propio (`docs/compliance/SECRETS.md`), y perderla equivale a
  cerrar todas las sesiones — no a perder datos del producto.

## Estado

**Aceptada.** Implementada y probada.

**Verificación reproducida 2026-09-10** (la afirmación de 36 tests de contrato
que traía este ADR quedó sin correlacionar tras la pérdida de la sesión, así que
se volvió a medir en lugar de heredarse): cluster PostgreSQL **16.15**
desechable, en espacio de usuario, sin `sudo`, sin puerto TCP (`listen_addresses`
vacío, socket unix dentro del scratchpad), creado y destruido en la misma
sesión. Resultado: **36 tests de contrato pasando** contra el adaptador real, y
la migración aplicada dos veces (idempotente) y revertida dos veces sin dejar
residuo. La base de FusionAuth y Supabase no se tocaron.

**Migración no aplicada a producción.**
