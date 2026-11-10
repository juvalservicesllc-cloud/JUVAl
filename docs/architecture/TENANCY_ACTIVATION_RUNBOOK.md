# Tenancy (ADR-056) — activation, provisioning and rollback runbook

Estado al 2026-11-10:

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

## 0. Criterios GO / NO-GO de producción

GO sólo si **todo** se cumple:

- [ ] Commits ADR-055/ADR-056 revisados y publicados por el propietario.
- [ ] Copia de seguridad de Supabase verificada (§1).
- [ ] `juval_backend` conforme (§2) y DSN administrativo separado (§3).
- [ ] FusionAuth: emisor, audiencia y claim de roles verificados con
      `tools/verify_oidc.py` contra el emisor real (§6).
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

- [ ] `tools/verify_oidc.py` contra el emisor real: emisor, audiencia, JWKS
      RS256 y claim de roles.
- [ ] `JUVAL_OIDC_ISSUER` igual al `iss` usado en las membresías.
- [ ] Revocación masiva de sesiones BFF **si el emisor cambia** o ante un
      incidente (la sesión no guarda `iss`; ADR-056):
      ```sql
      UPDATE identity_sessions SET revoked_at = now() WHERE revoked_at IS NULL;
      ```
      `SessionStore.load` rechaza toda sesión revocada; los usuarios vuelven
      a iniciar sesión.
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
