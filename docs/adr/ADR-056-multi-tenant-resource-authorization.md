# ADR-056 — Aislamiento multiusuario y autorización por recurso

- Estado: **Aceptada** (2026-11-10). El propietario aprobó OD-1..OD-7
  (§Decisiones del propietario) y autorizó la implementación local completa.
  Implementación en commits locales `56a3aa5`, `2517cf4`, `0859ace`,
  `2102a11`, `51f6fe1` (2026-11-10, sin push ni despliegue);
  las migraciones `20261110000008`/`09` **no se han aplicado** a ninguna base
  real. Propuesta inicial: 2026-11-10, misma fecha.
- Origen: SEC-01D. Medición del 2026-11-10 en laboratorio OIDC con dos sujetos
  sintéticos (`tests/integration/test_resource_isolation.py`).
- Relacionado: ADR-055 (modo fail-closed), ADR-028/031 (FusionAuth), ADR-034
  (BFF), ADR-036 (sesiones), ADR-017/019 (Supabase/PostgreSQL), ADR-013
  (SQLite), ADR-048 (rol `juval_backend` y RLS), ADR-050 (batches).
- No modifica `ROLE_PERMISSIONS`, el pin RS256 ni ADR-055.

## Contexto

La autenticación (ADR-055) y el RBAC (`viewer`/`operator`/`admin`) responden a
«¿quién eres?» y «¿qué tipo de operación puedes hacer?». Nada responde a
«¿sobre qué datos?»:

- `Principal` sólo tiene `subject`, `roles` y `permissions`; no hay emisor,
  organización ni membresía.
- `execution_runs`, `execution_run_records`, `*_financial_records`,
  `batches` y `batch_files` (SQLite y PostgreSQL) no tienen columna de
  propietario.
- `ExecutionRunStore` (`application/execution_run_store.py`) lee por
  `execution_id` o lista todo.
- `GET /api/v1/runs/{id}/download` sirve el archivo desde disco por
  `execution_id` sin pasar por el store.
- Las políticas RLS de ADR-048 son `USING (true)` para `juval_backend`: aíslan
  el rol de base de datos, no a los clientes.

**Medido (2026-11-10, OIDC, SQLite, dos sujetos sin relación):** el usuario B
con rol `viewer` lista el run de A y lee detalle, registros, analytics y
financieros (200). Con `operator`, B exporta y descarga el XLSX de A (200).
Es un BOLA/IDOR **alto**. Hoy no se explota porque la producción no está
activa y no hay usuarios reales (`ACCESS_CONTROL.md`); bloquea cualquier
activación con más de una persona o cliente.

En la misma revisión: `/api/v1/runs/%2E%2E/download` servía
`<storage>/output.xlsx`, fuera del directorio del run. Corregido sin esperar
este ADR (`service.run_dir` sólo acepta un componente de ruta; ver
§Implementación local).

## Principios

1. **Autenticación ≠ RBAC ≠ propiedad.** Las tres se exigen en el backend, en
   ese orden. El frontend nunca es un control.
2. **Conocer un identificador no concede acceso.** `execution_id` es un UUID
   aleatorio pero no un secreto: aparece en URLs, logs, historial y archivos
   compartidos.
3. **La consulta ya va acotada.** Un recurso se busca *dentro* del ámbito del
   llamador (`WHERE organization_id = ?`), nunca se carga y se comprueba
   después: así un olvido no se convierte en una fuga ni en un oráculo de
   tiempo.
4. **Ajeno = inexistente.** Un recurso fuera del ámbito responde 404 con el
   mismo cuerpo que uno que no existe. 403 se reserva para «tu rol no permite
   esta operación» (RBAC), que no revela nada de un recurso concreto.
5. **Sin ámbito, nada.** Una identidad autenticada sin membresía no ve datos
   (403 en rutas de datos), no «ve todo».
6. **Defensa en profundidad.** Filtro de aplicación + RLS por organización en
   PostgreSQL + partición de archivos por organización.

## Alternativas

| | A. Propiedad por usuario | B. Propiedad por organización | C. Organización + membresía + roles (recomendada) |
|---|---|---|---|
| Modelo | Cada recurso tiene `owner (iss, sub)` | Cada recurso tiene `organization_id`; la org sale de un claim | `organizations`, `memberships(org, iss, sub, role)`; recurso con `organization_id` y `created_by` |
| Ventajas | Simple; sin tablas nuevas de org | Comparte trabajo de equipo | Comparte trabajo, roles por org, auditoría completa, independiente del IdP |
| Costos | Compartir requiere un sistema de permisos aparte; reasignar al irse un empleado | Depende de que el IdP emita el claim (lambda en FusionAuth); cambiar membresía = cambiar el IdP | Dos tablas, administración de membresías, migración |
| Riesgos | Pérdida de datos al darse de baja un usuario; incentiva cuentas compartidas (contra RF-03) | Claim mal configurado = acceso cruzado; difícil de auditar desde JUVAl | Más superficie; mitigada por chokepoint único y pruebas estructurales |
| Escala | Mala para equipos | Buena | Buena; admite multi-org más adelante |
| Compatibilidad | Total con el RBAC actual | Requiere configuración nueva en FusionAuth | Total: el RBAC global del IdP se conserva como techo |

Descartada además: **un tenant de FusionAuth por cliente.** Cada tenant tiene
su propio emisor; el verificador fija uno (ADR-055 §7), y multiplicar tenants
multiplica configuración, MFA y evidencias RF-03 por cliente. Se reconsidera
sólo con una necesidad comercial demostrada.

## Decisión (opción C, fase 1 acotada)

1. **Identidad estable:** el par `(iss, sub)`. `sub` de FusionAuth es el UUID
   inmutable del usuario; nunca el email ni el nombre. `Principal` y la
   sesión BFF incorporan `issuer`.
2. **Organización:** tabla `organizations(organization_id uuid, name,
   created_at)`. Creación sólo por herramienta de operador auditada; sin
   autoservicio.
3. **Membresía:** `memberships(organization_id, issuer, subject, created_at,
   created_by)`, fuente autoritativa en la base de JUVAl (no en un claim:
   auditable, versionada, probada y sin acoplar al proveedor, ADR-021).
   **Fase 1: exactamente una membresía por identidad.** Cero → 403 en rutas
   de datos. Más de una → 403 hasta diseñar la selección de organización
   (FUTURE).
4. **Roles:** se mantiene el claim `roles` del IdP como RBAC (ADR sin
   cambios). La membresía sólo define el ámbito. Roles distintos por
   organización quedan FUTURE, sin necesidad demostrada.
5. **Propiedad de recursos:** `execution_runs` y `batches` reciben
   `organization_id` y `created_by_issuer`/`created_by_subject`. Las tablas
   hijas (`execution_run_records`, financieros, diagnósticos, `batch_files`)
   reciben `organization_id` denormalizado para RLS y se consultan sólo tras
   autorizar al padre.
6. **Autorización por recurso:** un único punto, `authorize_run(scope,
   execution_id)` / `authorize_batch(scope, batch_id)`, usado por toda ruta
   con `{execution_id}` o `{batch_id}`; los listados filtran por el mismo ámbito. El puerto `ExecutionRunStore` exige un `TenantScope` en cada
   lectura usada por la API; los métodos sin ámbito sólo existen para
   herramientas de mantenimiento, con nombre explícito. Una prueba estructural
   recorre `app.routes` (como `test_auth_mode_fail_closed.py`) y falla si una
   ruta con `{execution_id}`/`{batch_id}` no pasa por el punto único.
7. **Listados y contadores:** `list_execution_runs(scope, limit)`,
   `decision_counts` sólo sobre ids ya acotados, `total` de paginación
   calculado dentro del run autorizado.
8. **Archivos exportados:** `<storage>/<organization_id>/<execution_id>/`. La
   descarga resuelve primero el run en el store con ámbito; sin store
   configurado la descarga queda deshabilitada fuera del laboratorio. La
   exportación filtrada se genera desde lecturas ya acotadas.
9. **Laboratorio (ADR-055):** el principal de laboratorio pertenece a una
   organización sintética fija `local-lab`, para que el código sea el mismo
   (sin rama «sin tenant»).
10. **RLS PostgreSQL:** sustituir `USING (true)` por
    `USING (organization_id = nullif(current_setting('juval.organization_id', true), '')::uuid)`
    y el mismo `WITH CHECK`, con `SET LOCAL juval.organization_id` por
    transacción. Sin variable → ninguna fila. Es defensa ante un `WHERE`
    olvidado, no ante un backend comprometido (lo documenta el ADR, no se
    presenta como más).
11. **Auditoría:** cada denegación por ámbito se registra con sujeto,
    organización y tipo de recurso, sin devolver nada al cliente. `created_by`
    deja trazable quién creó cada run.

## Datos históricos

Las filas existentes no tienen propietario. Decisión (OD-3):
**cuarentena** — `organization_id` NULL las deja invisibles para toda ruta de
la API y para RLS. Ningún script las asigna automáticamente. En PostgreSQL, la
restricción `CHECK (organization_id IS NOT NULL) NOT VALID` obliga a las filas
nuevas sin reescribir las antiguas. No hay herramienta de asignación: si un
día se quiere asignar un conjunto concreto, será una decisión nueva del
propietario, explícita y registrada.

Los runs de la CLI (`--execution-id` libre) siguen siendo locales: se guardan
sin organización y, por tanto, en cuarentena para la API, salvo que se diseñe
`--organization` (FUTURE).

## Administración y soporte

`admin` significa administrador **dentro** de su organización. Decisión
(OD-4): ningún acceso entre organizaciones para ningún rol, incluido el
personal de JUVAl. La organización interna de JUVAl (OD-1) es una organización
más. Un acceso de soporte de plataforma requeriría un ADR nuevo.

## Implementación (2026-11-10, local)

Lo que se construyó difiere del texto anterior en estos puntos, por
simplicidad o corrección; el resto se implementó tal cual:

- **Vista acotada del store en lugar de un parámetro por método.**
  `store.scoped(TenantScope)` devuelve una vista en la que `load_execution_run`,
  `list_execution_runs` y `load_batch` filtran por organización (ajeno = None),
  toda lectura hija de un run ajeno lanza `OutOfScopeError` (500, nunca datos)
  y toda escritura exige un `Ownership` de esa organización. El store sin
  acotar queda para la CLI y herramientas; la API sólo usa vistas
  (`interfaces/api/main.py::tenant_access`, `run_in_scope`). En PostgreSQL la
  vista además fija `juval.organization_id` en cada transacción para RLS.
- **Punto único = dependencias FastAPI.** `tenant_access` (organización desde
  la membresía) y `run_in_scope(detalle_404)` (run dentro de la organización).
  Una prueba estructural recorre `app.routes` y exige `tenant_access` en las 14
  rutas y `run_in_scope` en toda ruta con `{execution_id}` salvo la descarga.
  El orden es autenticación → RBAC → CSRF → organización.
- **Descarga sin store.** Los archivos viven en
  `<storage>/juval_runs/<organization_id>/<execution_id>/`; la descarga sólo
  mira el directorio de la organización del llamador. También cubre runs no
  persistidos (`persist=false`).
- **RLS de tablas hijas por `EXISTS` sobre el padre**, sin denormalizar
  `organization_id` en ellas.
- **Dos migraciones.** `20261110000008_tenant_ownership` (sólo esquema: tablas
  y columnas, `CHECK … NOT VALID`) y `20261110000009_tenant_rls` (privilegios
  y políticas; exige ADR-048). Ambas con rollback. El rollback de la 09
  **restaura** las políticas `USING (true)` de ADR-048 — es volver al estado
  anterior, documentado como «sólo con el backend sin conexión», no una
  política nueva.
- **Emisor de la sesión BFF.** La sesión no guarda `iss`: se usa el emisor del
  verificador, el único que esa instancia acepta (ADR-055 §7). Consecuencia:
  **cambiar de emisor exige revocar antes todas las sesiones guardadas.**
- **OD-6 en la base**: la clave primaria de `organization_memberships` es
  `(issuer, subject)`; una segunda organización no se puede guardar.
- **Herramienta de operador**: `tools/tenancy_admin.py` crea organizaciones
  (UUID aleatorio) y membresías; DSN de PostgreSQL sólo desde una variable de
  entorno; rechaza la organización de laboratorio.
- La CLI sigue guardando runs sin propietario: quedan en cuarentena para la
  API (OD-3).

## Auditoría final (2026-11-10)

Revisión de seguridad tras la implementación; correcciones aplicadas:

- **Integridad referencial:** `organization_id` de runs y batches es FK a
  `organizations` (antes una fila podía quedar bajo una organización
  inexistente si se fijaba ese contexto). SQLite (local/laboratorio, ADR-013)
  no aplica esta FK: la organización de laboratorio no tiene fila.
- **Migración 09 más estricta:** vuelve a comprobar que `juval_backend` no es
  superuser, BYPASSRLS, INHERIT ni miembro de otro rol; la postcondición exige
  RLS y propietario distinto de `juval_backend` en las 8 tablas; `batch_files`
  sólo acepta un run de la misma organización.
- **Aprovisionamiento:** `remove-member` (bajas con efecto en la siguiente
  petición; RF-04/ADR-021 #17), `created_by` en organizaciones, nombre de
  organización único sin distinguir mayúsculas, validación de `issuer` (URL
  https sin credenciales, nunca el de laboratorio) y `subject` (sin `@` ni
  espacios).
- **Descarga:** la ruta resuelta debe seguir dentro del directorio de la
  organización (symlinks).
- **Cobertura estructural:** los routers incluidos (que `app.routes` no
  expande) sólo pueden contener `/api/v1/auth/*`.

Comprobado sin cambios: sin `USING (true)` en tablas de tenant; contexto
transaccional (`set_config(..., true)`) que desaparece con la transacción
también en una conexión reutilizada; sin contexto o con organización
inexistente no se lee ni escribe nada; el runtime no puede `UPDATE`/`DELETE`
propiedad ni membresías; la organización nunca sale de cabeceras o
parámetros; los runs son inmutables, así que no hay TOCTOU entre autorizar el
run y leer sus hijos; el propietario `postgres` no está sujeto a RLS (no
forzada, igual que ADR-048), por lo que el DSN administrativo es privilegiado.

Activación, aprovisionamiento, matriz de autorización y rollback:
[`TENANCY_ACTIVATION_RUNBOOK.md`](../architecture/TENANCY_ACTIVATION_RUNBOOK.md).

## Migración (cada paso con pruebas, ninguno en producción sin autorización)

Estado 2026-11-10: M0–M4 implementados y probados localmente (SQLite y
PostgreSQL 16 desechable); M5 no se ejecuta (OD-3: cuarentena, sin
asignación). Activar en producción requiere aplicar 08 y 09 y crear las
organizaciones y membresías reales: acciones del propietario.


- **M0 (hecho, 2026-11-10):** suite de aislamiento con la invariante en
  `xfail(strict=True)`; corrección de ruta de descarga.
- **M1:** `issuer` en `Principal` y sesión; tablas `organizations` y
  `memberships` (SQLite + migración PostgreSQL **sin aplicar**); resolución de
  ámbito fail-closed; herramienta de operador para membresías.
- **M2:** columnas de propiedad (nullable + `CHECK NOT VALID`), puerto con
  `TenantScope`, rutas por el punto único, prueba estructural. Las `xfail`
  pasan a ser pruebas normales.
- **M3:** partición de archivos por organización y descarga vía store.
- **M4:** RLS por organización, probado en PostgreSQL desechable
  (`tools/session_store_lab.py`).
- **M5:** decisión y ejecución, por el propietario, sobre los datos
  históricos.

## Consecuencias

- Cada nueva ruta de datos debe pasar por el punto único o la prueba
  estructural falla.
- Activar la producción con más de un usuario queda bloqueado hasta M2 + M3
  (M4 recomendado antes de exponer PostgreSQL con datos de más de una
  organización).
- Los runs existentes dejan de verse en la API hasta su asignación explícita.
- Nada de esto completa RF-04 ante Amazon por sí solo: falta la mitad
  organizativa (`ACCESS_CONTROL.md`).

## Decisiones del propietario (APPROVED 2026-11-10)

Todas aprobadas como se recomendaba. OD-4 se interpreta, confirmado por el
propietario, como «ningún acceso entre organizaciones para nadie, incluido el
`admin` interno de JUVAl».

| # | Decisión | Recomendación |
|---|---|---|
| OD-1 | Modelo comercial: una organización por cliente (multi-org) o una sola organización interna por ahora | El diseño sirve para ambos; la fase 1 funciona con una sola |
| OD-2 | Visibilidad dentro de la organización: todos los miembros con `runs:read` o sólo el creador | Todos los miembros (trabajo de equipo); `created_by` permite restringir después |
| OD-3 | Datos históricos: cuarentena o asignación a una organización concreta | Cuarentena; asignar sólo con un acto explícito y registrado |
| OD-4 | Soporte de plataforma entre organizaciones | Ninguno; si se necesita, rol aparte, sólo lectura, temporal y auditado |
| OD-5 | Fuente de membresía: base de JUVAl o claim del IdP | Base de JUVAl |
| OD-6 | Usuarios en varias organizaciones | No en fase 1 |
| OD-7 | Política 404 para recursos ajenos | Aceptar (técnica, sin impacto comercial) |

## Pruebas

- `tests/integration/test_resource_isolation.py` (52, SQLite, OIDC con dos
  organizaciones sintéticas, un segundo miembro y una identidad sin
  membresía): miembros comparten según RBAC; otra organización no ve listados,
  lecturas (6 rutas), exportación, descarga, batch ni runs hijos, con respuesta
  idéntica a la de un recurso inexistente; paginación y contadores; sin
  membresía → 403 en las 14 rutas; membresía bajo otro emisor no aplica;
  segunda membresía rechazada; OIDC sin store → 503; historia en cuarentena
  (también archivos de la ruta antigua); `..` codificado; identificadores
  manipulados; 404 sin datos; cobertura estructural de rutas; vista acotada del
  store. Mutaciones verificadas el 2026-11-10: ignorar el ámbito del store,
  asignar la misma organización a todos y quitar la partición de archivos hacen
  fallar 13, 27 y 10 pruebas respectivamente.
- `tests/integration/test_postgres_tenant_isolation.py` (8, PostgreSQL 16
  desechable, como `juval_backend`): sin políticas `true`; tablas de tenancy de
  sólo lectura; RLS por SQL directo (sin organización fijada, otra
  organización, la propia) en las 6 tablas; escritura en otra organización
  rechazada por RLS; filas sin propietario rechazadas; historia en cuarentena;
  membresía visible sólo para la identidad fijada; vista acotada; rollback.
- `tests/integration/test_postgres_adr050_under_adr048.py`: la API real como
  `juval_backend` con 08+09 aplicadas (lectura y escritura de laboratorio
  dentro de su organización).
- `tests/unit/test_tenancy_admin.py` (3): herramienta de operador.
- Hasta el 2026-11-10 la mitad de aislamiento era `xfail(strict=True)`. Nota:
  la marca de «run sin propietario» fallaba entonces por un error de
  preparación (`ExecutionRun` sin contadores), no por la comprobación de
  acceso; la prueba actual está corregida y verificada.
