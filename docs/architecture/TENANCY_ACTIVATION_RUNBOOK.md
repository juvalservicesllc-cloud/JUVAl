# Tenancy (ADR-056) — activation, provisioning and rollback runbook

Estado al 2026-11-10 (SEC-01E: §0 secuencia validada, §11 matriz de infraestructura):

| Etiqueta | Estado |
|---|---|
| IMPLEMENTED_LOCAL | **Sí** — commits locales `56a3aa5`, `2517cf4`, `0859ace`, `2102a11`, `51f6fe1` (+ documentación). |
| VERIFIED_LOCAL | **Sí** — SQLite, PostgreSQL 16 desechable y E2E Chromium 42/42; evidencia en `PROJECT_STATUS.md`. |
| READY_FOR_REVIEW | **Sí.** |
| PRODUCTION_DEPLOYED | **No.** Ninguna migración aplicada a Supabase; backend Railway sin conexión (SEC-01A); sin push. |

Este documento **no autoriza** ejecutar nada. Cada paso es una acción del
propietario (**OWNER**) sobre infraestructura real, en el orden indicado. Ante
cualquier comprobación fallida: **parar** y aplicar §9 (recuperación
fail-closed). Ningún paso usa credenciales en la línea de comandos ni en Git.

## 0. Plan de producción en orden de dependencias (SEC-01F)

Orden propuesto (revisión/backup → rol → TLS → migraciones → FusionAuth →
dominios/cookies → aprovisionamiento → despliegue → BOLA → operación →
GO/NO-GO) contrastado con el código y ADR-036/038/048/055/056. Ajustes
respecto a esa lista:

1. **Dominios antes que FusionAuth.** El emisor (`https://id.<dominio>`), el
   `redirect_uri` del callback, el destino post-logout, CORS y el host de las
   cookies dependen del dominio (ADR-038). Configurar FusionAuth antes
   obligaría a cambiar el emisor después, y eso exige revocar todas las
   sesiones y rehacer las membresías (claves `(iss, sub)`).
2. **Reconciliar el ledger y crear el rol antes que todo cambio de esquema.**
   La 09 exige la 07 y el rol (ADR-048: el rol se crea fuera de banda antes de
   las migraciones que lo referencian).
3. **TLS se valida dos veces:** como conexión (`verify-full` con el CA, paso 4)
   antes de migrar, y en el arranque del backend (que aborta sin
   `verify-full`), paso 9.
4. **Sesiones y RLS se verifican en dos partes:** estructura antes del
   despliegue, comportamiento después (no hay backend que las ejerza antes).

Cada paso deja el sistema **cerrado** si falla: backend sin conexión, `503`/
`401`/`403`/`404`, nunca acceso abierto (§9).

| # | Paso (OWNER salvo indicación) | Depende de | Evidencia que lo cierra | Si falla |
|---|---|---|---|---|
| 0 | Decisiones del propietario §12 (dominio, TTL/refresh FusionAuth, destino de logs y alertas, rol `juval_tenancy_admin`) | — | decisiones escritas | no empezar |
| 1 | Revisión y publicación de los commits SEC-01C/D/E/F; backup gestionado + `pg_dump` cifrado y restauración de prueba (§1); reconciliación de ledger y catálogo 00–07 | 0 | restauración con recuentos; lista de migraciones aplicadas | no tocar nada |
| 2 | Dominios: DNS y certificados de `app.`, `api.`, `id.<dominio>` (ADR-038); túnel de identidad (ADR-031) | 0 | HTTPS válido en los tres hosts | sin dominio no hay emisor estable |
| 3 | Rol `juval_backend` creado fuera de banda; migraciones 04–07 que falten según el ledger; verificación §2 | 1 | §2 = `f,f,f,f,f,f,t`, 0 membresías | la 07/09 abortan por sus precondiciones |
| 4 | TLS: CA de Supabase, DSN `verify-full` para runtime (por Supavisor) y administrativo (§11.1); conexión de prueba como `juval_backend`; `session_migration_preflight.py --check-database` | 3 | conexión OK; preflight PASS | el arranque abortaría |
| 5 | Migraciones 08 → 09 como `postgres`, backend sin conexión (§4); verificación estructural §4 | 1, 3, 4 | postcondiciones + 0 políticas `true` | rollback §8 (09 restaura ADR-048) |
| 6 | FusionAuth: emisor `https://id.<dominio>`, aplicación (client id/secret), `redirect_uri` exacto `https://api.<dominio>/api/v1/auth/callback`, logout a `https://app.<dominio>/`, roles `viewer`/`operator`/`admin`, JWT TTL corto, refresh + `offline_access` (decisión §12); `verify_oidc.py --token-env` con un usuario de prueba (§6) | 2 | todo PASS; `iss`/`sub` exactos | 401 en login; nada abierto |
| 7 | Aprovisionamiento: organización interna y miembros (§5) con el DSN administrativo; RLS de comportamiento como `juval_backend` | 5, 6 | líneas de auditoría; sin GUC → 0 filas | 403 para quien falte |
| 8 | Despliegue controlado: backend (Railway, `JUVAL_AUTH_MODE=oidc`, secretos §11, CORS exacto, `JUVAL_BFF_POST_LOGIN/LOGOUT_REDIRECT` absolutos a `app.`) y frontend (Vercel, `VITE_API_BASE_URL=https://api.<dominio>`, Codex) | 4–7 | `/healthz` 200; arranque sin `startup.failed` | el proceso no arranca (fail-closed) |
| 9 | Cookies y sesiones en navegador real: `Secure`/`HttpOnly`/`Lax`/host-only, login con `return_to`, logout + end-session, inactividad, segundo login revoca el primero | 8 | checklist anotada | backend sin conexión |
| 10 | Pruebas BOLA y de aislamiento (§7) con identidades de prueba de dos organizaciones y una sin membresía; cambio de rol y `revoke-sessions` | 8, 7 | checklist §7 completa | §9 |
| 11 | Validación operativa: eventos `juval.security` llegan al destino, reglas §11.2 disparan con un caso sintético, simulacro de `revoke-sessions --all` y de rollback leído | 8 | evidencia por regla | NO-GO |
| 12 | Decisión GO/NO-GO (abajo) | todo | firma del propietario | — |

El mismo flujo, con identidad, base y backend sintéticos, se ejecuta en local
con `tools/integration_lab.py --check` (23 comprobaciones; ver
`LOCAL_INTEGRATION_ENVIRONMENT.md`): es el ensayo de los pasos 7–10.

### Criterios GO / NO-GO de producción

GO sólo si **todo** se cumple:

- [ ] Commits ADR-055/ADR-056 revisados y publicados por el propietario.
- [ ] Copia de seguridad de Supabase verificada (§1).
- [ ] `juval_backend` conforme (§2) y DSN administrativo separado (§3).
- [ ] Ledger/catálogo remoto reconciliado; ADR-048 (07) aplicada (paso 2a).
- [ ] FusionAuth: emisor, audiencia y claim de roles verificados con
      `tools/verify_oidc.py` contra el emisor real (§6).
- [ ] Secretos y TLS conformes a §11; decisiones PENDING de §11 resueltas o
      aceptadas por escrito.
- [ ] Migración de sesiones ADR-036 aplicada o despliegue sólo-bearer
      decidido (bloqueo vigente en `IDENTITY_SECURITY_READINESS.md`).
- [ ] Migraciones 08 y 09 aplicadas y verificadas (§4).
- [ ] Organización interna JUVAl y membresías reales creadas (§5).
- [ ] Pruebas de aislamiento posteriores superadas (§7).
- [ ] Plan de rollback leído y responsable disponible (§8).

NO-GO si falta cualquiera. Hoy (2026-11-10): **NO-GO** — faltan publicación,
copia, verificación OIDC real, sesiones ADR-036 y todas las acciones reales.

## 1. Copia de seguridad (OWNER)

- [ ] Backend sin conexión (hoy ya lo está; Railway no se reactiva).
- [ ] Copia lógica completa (`pg_dump` con el DSN administrativo desde la
      variable de entorno de la sesión) **y** confirmación de que el backup
      gestionado de Supabase más reciente existe.
- [ ] Restaurar la copia en una base desechable y contar filas de
      `execution_runs`, `execution_run_records`, `batches`, `batch_files`.
- [ ] Guardar la copia fuera del repositorio, cifrada, con fecha y
      responsable anotados en el registro de cambios.

## 2. Verificar el rol de ejecución `juval_backend` (OWNER, sólo lectura)

```sql
SELECT rolsuper, rolbypassrls, rolinherit, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin
  FROM pg_roles WHERE rolname = 'juval_backend';             -- esperado: f,f,f,f,f,f,t
SELECT count(*) FROM pg_auth_members WHERE member = 'juval_backend'::regrole;   -- 0
SELECT relname FROM pg_class
 WHERE relnamespace = 'public'::regnamespace AND relowner = 'juval_backend'::regrole;  -- 0 filas
SELECT tablename, policyname, cmd FROM pg_policies WHERE schemaname = 'public' ORDER BY 1, 2;
-- antes de 09: exactamente juval_backend_select/insert (ADR-048) en las 6 tablas de datos
```

La migración 09 repite estas comprobaciones y se detiene si fallan.

## 3. Privilegios de aprovisionamiento (OWNER)

- El backend usa sólo `juval_backend` (`JUVAL_RUNTIME_DB_URL`), que **no**
  puede escribir organizaciones ni membresías.
- `tools/tenancy_admin.py` usa un DSN administrativo distinto, leído de la
  variable cuyo **nombre** se pasa en `--postgres-dsn-env`.
- Recomendado: un rol dedicado (p. ej. `juval_tenancy_admin`) con sólo
  `INSERT` en `organizations` y `organization_memberships` y `DELETE` en
  `organization_memberships`, en lugar de `postgres`. No lo crean estas
  migraciones; es una decisión de infraestructura del propietario. Si se usa
  `postgres`: es propietario de las tablas y **no** está sujeto a RLS.

## 4. Migraciones 08 y 09 (OWNER, como `postgres`)

Orden obligatorio, cada una en su transacción, backend sin conexión:

1. `supabase/migrations/20261110000008_tenant_ownership.sql` — tablas
   `organizations` (nombre único sin mayúsculas, `created_by`) y
   `organization_memberships` (clave `(issuer, subject)`); columnas de
   propietario en `execution_runs`/`batches` con FK a `organizations` y
   `CHECK … NOT VALID`. La historia queda con NULL (cuarentena, OD-3).
2. `supabase/migrations/20261110000009_tenant_rls.sql` — sustituye
   `USING (true)` por políticas por organización fijada por transacción;
   el runtime sólo lee su propia membresía.

Verificación posterior (sólo lectura):

```sql
SELECT tablename, policyname, qual, with_check FROM pg_policies
 WHERE schemaname = 'public' AND (qual = 'true' OR with_check = 'true');   -- 0 filas
SELECT count(*) FROM execution_runs WHERE organization_id IS NULL;        -- = filas históricas
SELECT has_table_privilege('juval_backend', 'public.organizations', 'SELECT');  -- f
```

Las mismas comprobaciones están automatizadas para bases desechables en
`tests/integration/test_postgres_tenant_isolation.py`; **nunca** ejecutar las
pruebas contra Supabase.

## 5. Aprovisionamiento (OWNER, DSN administrativo)

```bash
export JUVAL_TENANCY_ADMIN_DB_URL=...   # sólo en la sesión del operador
T=".venv/bin/python tools/tenancy_admin.py --postgres-dsn-env JUVAL_TENANCY_ADMIN_DB_URL"
$T create-organization --name "JUVAl" --created-by "<operador>"            # OD-1: organización interna
$T add-member --organization <uuid> --issuer "<iss exacto>" --subject "<sub FusionAuth>" --created-by "<operador>"
$T remove-member --issuer "<iss>" --subject "<sub>" --created-by "<operador>"   # baja inmediata
```

- `sub` es el id de usuario de FusionAuth (no el email); `iss` es exactamente
  el `iss` del token. Obtenerlos del panel de FusionAuth o de un token de
  prueba verificado.
- Una identidad, una organización (OD-6). Ningún comando asigna historia
  (OD-3) ni da acceso entre organizaciones (OD-4).
- Guardar cada línea de auditoría impresa en el registro de revisión de
  accesos (`docs/compliance/ACCESS_CONTROL.md`).

## 6. Identidad OIDC / FusionAuth y sesiones BFF (OWNER)

- [ ] `tools/verify_oidc.py` contra el emisor real, con los **mismos valores**
      que tendrá el backend y un token de un usuario de prueba (nunca en la
      línea de comandos; sólo el nombre de la variable):
      ```bash
      export TEST_TOKEN=...   # sólo en la sesión del operador
      .venv/bin/python tools/verify_oidc.py --issuer "$JUVAL_OIDC_ISSUER" \
          --audience "$JUVAL_OIDC_AUDIENCE" --token-env TEST_TOKEN   # + --jwks-uri si se fija
      ```
      Debe dar PASS en discovery, emisor, URI JWKS igual a la del discovery,
      RS256, `kid`, verificación del token y roles → permisos. Imprime la
      línea `--issuer … --subject …` exacta para §5. Usa el verificador de la
      API, así que lo que pasa aquí es lo que pasará en producción.
- [ ] `JUVAL_OIDC_ISSUER` igual al `iss` usado en las membresías.
- [ ] Revocación de sesiones BFF con la herramienta de operador (mismo DSN
      administrativo que §5; nunca SQL a mano):
      ```bash
      $T revoke-sessions --all --created-by "<operador>"            # ANTES de cambiar el emisor OIDC
      $T revoke-sessions --subject "<sub>" --created-by "<operador>"  # cambio de roles o baja inmediata
      ```
      Global: obligatoria antes de cambiar `JUVAL_OIDC_ISSUER` (la sesión no
      guarda `iss`; ADR-056) y ante un incidente. Por sujeto: tras cambiar los
      roles de alguien en FusionAuth o darle de baja. Borra también los tokens
      cifrados; imprime una línea de auditoría.
- [ ] Sin revocación manual, los cambios llegan solos: la membresía en la
      siguiente petición (`remove-member`), y los roles o una cuenta
      desactivada al vencer el access token (re-verificación, SEC-01E). Fijar
      en FusionAuth un **JWT TTL corto** (recomendado ≤ 15 min) y decidir los
      refresh tokens: sin `offline_access` + refresh activado en la
      aplicación, FusionAuth no emite refresh token y cada sesión dura un TTL
      (PENDING del propietario).
- [ ] Inactividad: 30 min por defecto; sólo se cambia con
      `JUVAL_SESSION_IDLE_TIMEOUT_MINUTES` (1–480) en el servidor.
- [ ] Rotación de la clave de firma en FusionAuth: una clave nueva puede
      rechazarse hasta 30 s tras la última descarga del JWKS (401, cerrado);
      una clave **retirada** deja de aceptarse en ≤ 300 s (SEC-01E E1).
- Estado actual: D-1 PARTIAL; la migración live de sesiones (ADR-036) sigue
  bloqueada (`IDENTITY_SECURITY_READINESS.md`).

## 7. Pruebas de aislamiento posteriores (OWNER, identidades de prueba)

Con dos identidades de prueba en organizaciones distintas y una sin
membresía, sobre el backend desplegado:

- [ ] A crea un run; A lo ve en `GET /api/v1/runs`.
- [ ] B no lo ve en el listado; `GET /runs/{id}` de A → 404 igual que un id
      inexistente; export y descarga → 404.
- [ ] La identidad sin membresía → 403 en `GET /api/v1/runs`.
- [ ] `remove-member` de B → su siguiente petición → 403.
- [ ] Un run histórico conocido → 404 para todos.
- Retirar después las identidades y la organización de prueba.

## 8. Despliegue y rollback

Despliegue (OWNER): backend con ADR-055 + ADR-056 y `JUVAL_AUTH_MODE=oidc`,
sólo tras §1–§6; después §7. Un backend ADR-056 **no funciona** sin la 08.

Rollback, en este orden y con el backend sin conexión:

1. Volver a un backend anterior **reabre** el hallazgo SEC-01D: no hacerlo con
   datos de más de una organización.
2. `20261110000009_tenant_rls.down.sql` — restaura `USING (true)` (ADR-048):
   sin aislamiento en la base.
3. `20261110000008_tenant_ownership.down.sql` — **borra** organizaciones,
   membresías y propietarios; exportarlos antes.
4. Restaurar la copia de §1 sólo si los datos se corrompieron.

## 9. Recuperación fail-closed

Ante cualquier fallo durante la activación:

- Dejar el backend **sin conexión** (estado seguro actual).
- Nunca usar `JUVAL_AUTH_MODE=disabled` en un despliegue (ADR-055 lo impide).
- Nunca crear políticas `USING (true)` nuevas ni conceder BYPASSRLS para
  «arreglar» un acceso: el síntoma correcto de un fallo es 403/404/503.
- Si una identidad legítima no ve sus datos: comprobar su membresía
  (`organization_ids_for`) y el `iss` exacto, no ampliar permisos.

## 10. Matriz de autorización (implementada)

| Ruta | Permiso RBAC | Organización | Recurso ajeno |
|---|---|---|---|
| `POST /api/v1/runs`, `/runs/preview`, `/batches` | `runs:create` (+CSRF con cookie) | membresía única | escribe sólo en la propia |
| `GET /api/v1/runs` | `runs:read` | membresía única | no aparece; contadores propios |
| `GET /runs/{id}`, `/records`, `/records/{ref}`, `/analytics`, `/financial`, `/records/{ref}/financial`, `/batch` | `runs:read` | run dentro de la organización | 404 idéntico a inexistente |
| `GET /runs/{id}/records/export` | `runs:export` | run dentro de la organización | 404 idéntico |
| `GET /runs/{id}/download` | `runs:export` | directorio de la organización | 404 (también symlinks fuera) |
| `GET /batches/{id}` | `runs:read` | batch dentro de la organización | 404 idéntico |
| Cualquier ruta de datos sin membresía | — | — | 403 |

| Rol de base de datos | `organizations` | `organization_memberships` | 6 tablas de datos |
|---|---|---|---|
| `juval_backend` | nada | `SELECT` de su propia fila | `SELECT`/`INSERT` de su organización; sin `UPDATE`/`DELETE` |
| `anon`, `authenticated`, `authenticator`, `service_role`, `PUBLIC` | nada | nada | nada |
| `postgres` (propietario) | todo (sin RLS: no forzada) | todo | todo |

## 11. Matriz de requisitos de infraestructura (SEC-01E)

Estado al 2026-11-10, sin inspeccionar servicios ni valores de secretos.
**Verificado** = hay una comprobación en el repositorio que lo hace cumplir;
**OWNER** = sólo verificable sobre la infraestructura real; **PENDING** =
falta una decisión.

| Área | Requisito | Estado | Cómo se comprueba |
|---|---|---|---|
| PostgreSQL/Supabase | Versión remota conocida; PG17 añade `MAINTAIN` | OWNER | ADR-048 `MAINTAIN_REMOTE_PG17`; los tests usan PG16 desechable |
| PostgreSQL/Supabase | Ledger y catálogo reconciliados (00–07) | OWNER, **bloquea** | paso 2a |
| Rol `juval_backend` | NOSUPERUSER, NOBYPASSRLS, NOINHERIT, sin membresías, no propietario | Verificado en arranque (sesiones) y en 09 | `verify_session_database`; precondiciones de la 09; §2 |
| Rol administrativo | DSN distinto del runtime para migraciones y `tenancy_admin.py` | OWNER; rol dedicado recomendado (§3) | §3 |
| Pool de conexiones | Supavisor en modo sesión; los GUC de tenant (`set_config(..., true)`) y el lock de refresh son de transacción | OWNER | prueba de conexión ADR-048; `pooler_refresh_guard` en `session_migration_preflight.py` |
| TLS | DSN remotos con `sslmode=verify-full` y CA de confianza (decisión del propietario) | **Verificado**: el arranque, `tenancy_admin.py` y el almacén abortan con cualquier otro `sslmode` hacia un host remoto | `tests/unit/test_postgres_tls.py`; configuración en §11.1 |
| TLS | Emisor y API sólo por HTTPS; cookies `Secure` (no fijar `JUVAL_BFF_INSECURE_COOKIES`) | Verificado: `Secure` por defecto; `tenancy_admin` exige emisor https | `IDENTITY_SECURITY_READINESS.md` §TLS |
| Secretos | `JUVAL_RUNTIME_DB_URL`, `JUVAL_SESSION_ENCRYPTION_KEYS`, `JUVAL_OIDC_CLIENT_SECRET` sólo en el gestor de la plataforma; DSN administrativo sólo en la sesión del operador | OWNER | `docs/compliance/SECRETS.md`; `secret_scan` del repo |
| Backups | Backup gestionado + `pg_dump` cifrado fuera del repo | OWNER, **bloquea** | §1 |
| Restauración | Ensayo en base desechable; **nunca** restaurar sesiones vivas (resucitan revocadas) | OWNER | §1; `IDENTITY_SECURITY_READINESS.md` §Session |
| Migraciones | Orden 08 → 09, como `postgres`, una transacción, backend sin conexión | Verificado en PG16 desechable | precondiciones y postcondiciones de la 09; §4 |
| Observabilidad | Liveness | **Verificado**: `GET /healthz` público, cuerpo constante, sin BD ni versión; excepción única fijada en `compliance_check.py` | `tests/integration/test_healthz.py`, `tests/unit/test_compliance_public_routes.py` |
| Observabilidad | Readiness | Por diseño no hay endpoint: una configuración o BD inválida impide arrancar (ADR-036/055) y las dependencias caídas dan 503 en las rutas que las usan | evento `startup.failed` |
| Logs | Sin tokens, cookies, DSN ni cuerpos; avisos de CSRF, denegación de tenant y 503 de sesiones | Verificado en código y tests (E3) | `test_token_value_never_appears_in_logs`, `test_an_unavailable_session_store_fails_closed_without_details` |
| Alertas | Eventos estructurados en el logger `juval.security` (§11.2) | **Verificado** (emisión); **PENDING** destino y canal (sin servicio externo aún) | `tests/integration/test_security_events.py` |
| Despliegue | Railway sin conexión hasta el paso 9; `JUVAL_AUTH_MODE=oidc`; una sola versión ADR-055/056 | OWNER | §8 |
| Rollback | Fail-closed: backend sin conexión, nunca `disabled`, nunca `USING (true)` nuevas ni BYPASSRLS | Procedimiento | §8, §9 |
| Frontend | `frontend-next` con BFF (fuera del alcance de Claude) y topología same-site (ADR-038) | OWNER/Codex, **bloquea** el login por navegador | `UNBLOCK_PLAN_20261026.md` |

### 11.1 TLS `verify-full` hacia Supabase (OWNER)

1. Descargar el certificado CA del proyecto (Supabase → Database settings →
   SSL certificate). Es público, no un secreto; verificar su huella con la
   que muestra el panel.
2. Ponerlo en el contenedor del backend en una ruta fija (p. ej. incluido en
   la imagen) y añadir al DSN, que sigue siendo secreto y sólo vive en el
   gestor de la plataforma, los parámetros
   `sslmode=verify-full&sslrootcert=/ruta/supabase-ca.crt`
   (en forma URL, tras `?`). El host del DSN debe ser el del certificado (el
   pooler o el directo), o la verificación de nombre fallará.
3. Lo mismo para el DSN administrativo de `tenancy_admin.py` (en la máquina
   del operador).
4. Probar sin imprimir el DSN: el arranque falla con
   `... without TLS verify-full` si falta `sslmode`, y con un error de
   conexión si el CA o el host no cuadran. Ambos son fallos cerrados.

### 11.2 Eventos y reglas de alerta iniciales

Una línea JSON por evento en el logger `juval.security`
(`interfaces/api/security_events.py`). Sin tokens, cookies, DSN, emails ni
`sub` en claro (`subject_fp` = huella de 12 hex).

| Evento | Campos | Alerta inicial (por instancia) |
|---|---|---|
| `auth.token_rejected` | `reason` | ≥ 50 en 5 min (fuerza bruta o desajuste de configuración) |
| `auth.jwks_unavailable` | `reason` | ≥ 5 en 5 min (JWKS caído, o `PyJWKClientError` por `kid` desconocido: posible token falsificado) |
| `session.store_unavailable` | — | cualquiera (sesiones caídas = nadie entra) |
| `membership.store_unavailable` | — | cualquiera |
| `session.ended` | `reason` | `refreshed_token_other_subject`: cualquiera; `refresh_rejected`: picos |
| `access.denied` | `kind` (`rbac`/`csrf`/`tenant`), `permission`, `reason`, `subject_fp` | ≥ 20 del mismo `subject_fp` en 10 min; `csrf` en picos |
| `startup.failed` | `stage` | cualquiera |

Migraciones: las aplica el operador con SQL (§4); un fallo aborta la
transacción (`RAISE EXCEPTION`) y se registra en el registro de cambios. Una
migración ausente o incompleta en el arranque aparece como `startup.failed`
`stage=sessions` (comprobación de esquema de ADR-036/048). Destino de logs y
canal de alertas: PENDING del propietario; no se envía nada a servicios
externos.

## 12. Matriz de dependencias de activación (SEC-01F)

Clasificación al 2026-11-10: **VERIFIED_LOCAL** = implementado y probado en
este repositorio (incluido el entorno de integración); **REQUIRES_INFRASTRUCTURE**
= sólo verificable sobre servicios reales; **REQUIRES_OWNER_DECISION** = falta
una decisión; **BLOCKED** = depende de otro elemento no resuelto.

| Área | Requisito | Estado | Evidencia / bloqueo |
|---|---|---|---|
| FusionAuth | Verificador RS256, `iss`/`aud`/`exp`, JWKS con caché acotada y rotación | VERIFIED_LOCAL | `test_verify_oidc.py`, `integration_lab.py --check` |
| FusionAuth | Emisor real `https://id.<dominio>` y aplicación configurada | BLOCKED | depende del dominio |
| FusionAuth | JWT TTL y refresh tokens (`offline_access`) | REQUIRES_OWNER_DECISION | sin refresh, sesión = 1 TTL |
| FusionAuth | `verify_oidc.py` contra el emisor real con token de prueba | BLOCKED | emisor real |
| PostgreSQL | Esquema 00–09, RLS por organización, rol runtime sin privilegios | VERIFIED_LOCAL | PG16 desechable; `test_postgres_tenant_isolation.py` |
| PostgreSQL | Ledger y catálogo de Supabase reconciliados; 04–07 aplicadas | REQUIRES_INFRASTRUCTURE | paso 1/3 |
| PostgreSQL | `juval_backend` real y conexión por Supavisor | REQUIRES_INFRASTRUCTURE | ADR-048 |
| PostgreSQL | Versión remota PG17 (`MAINTAIN`) | REQUIRES_INFRASTRUCTURE | sólo PG16 probado |
| PostgreSQL | Rol administrativo dedicado `juval_tenancy_admin` | REQUIRES_OWNER_DECISION | §3 |
| TLS | `verify-full` exigido en arranque y herramienta | VERIFIED_LOCAL | `test_postgres_tls.py` |
| TLS | CA de Supabase instalado y DSN reales | REQUIRES_INFRASTRUCTURE | §11.1 |
| TLS | Certificados de `app.`/`api.`/`id.` | BLOCKED | dominio |
| Dominios | Dominio registrable propio (ADR-038) | REQUIRES_OWNER_DECISION | `HUMAN_DOMAIN_SELECTION_PENDING` |
| Cookies | `Secure`, `HttpOnly`, `Lax`, host-only, revocación en login/logout | VERIFIED_LOCAL | tests BFF; `integration_lab.py` |
| Cookies | Comportamiento en navegador real con los hosts reales | BLOCKED | dominio |
| CSRF | Doble envío, precedencia antes de organización | VERIFIED_LOCAL | `test_bff_frontend_contract.py` |
| Sesiones | Almacén PostgreSQL cifrado, inactividad 30 min, absoluta 8 h, roles frescos | VERIFIED_LOCAL | lab de sesiones; `integration_lab.py` |
| Sesiones | Llavero `JUVAL_SESSION_ENCRYPTION_KEYS` en el gestor de secretos | REQUIRES_INFRASTRUCTURE | §11 |
| Membresías | Aislamiento por organización, 403 sin membresía, `remove-member` inmediato | VERIFIED_LOCAL | `test_resource_isolation.py` |
| Membresías | Organización interna y miembros reales | BLOCKED | `sub` reales tras configurar FusionAuth |
| Migraciones | 08/09 con pre y postcondiciones, rollback probado | VERIFIED_LOCAL | PG16 desechable |
| Migraciones | Aplicación en Supabase | REQUIRES_INFRASTRUCTURE | paso 5, tras backup |
| Backup | Backup gestionado + `pg_dump` cifrado + restauración de prueba | REQUIRES_INFRASTRUCTURE | §1 |
| Backup | Destino fuera del host | REQUIRES_OWNER_DECISION | `OFF_HOST_DESTINATION` pendiente |
| Rollback | Procedimiento fail-closed documentado | VERIFIED_LOCAL | §8–§9; down de 08/09 probado |
| Rollback | Simulacro con el responsable disponible | REQUIRES_INFRASTRUCTURE | paso 11 |
| Observabilidad | `/healthz`, eventos `juval.security` sin secretos | VERIFIED_LOCAL | `test_healthz.py`, `test_security_events.py` |
| Observabilidad | Destino de logs y canal de alertas | REQUIRES_OWNER_DECISION | §11.2 |
| Frontend | Contrato BFF verificado contra el backend | VERIFIED_LOCAL | `test_bff_frontend_contract.py` |
| Frontend | Login, logout y errores en `frontend-next` | BLOCKED | pendiente de la tarea de Codex (`CODEX_BFF_INTEGRATION_PROMPT.md`); el entorno local ya lo permite |
