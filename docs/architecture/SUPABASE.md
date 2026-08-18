# Juval — Supabase / PostgreSQL (persistencia de producción, ADR-017)

Implementación normativa:
`src/juval/infrastructure/persistence/supabase_execution_run_store.py`,
`supabase/migrations/20260817000000_execution_runs.sql`. Este documento
describe el estado real — si hay discrepancia, el código gana.

## 1. Estado — `[HECHO VERIFICADO]`

- **Código implementado**: sí — `SupabaseExecutionRunStore` implementa
  el mismo puerto que `SqliteExecutionRunStore` (`application/execution_run_store.py::ExecutionRunStore`).
- **Proyecto Supabase real**: **existe**, un único proyecto en la cuenta
  (sin ambigüedad) — `[VERIFICADO 2026-08-17]` vía
  `npx supabase projects list`: nombre `juvalservicesllc-cloud's
  Project`, `ref twrgzsbpazcjhhfolaju`, región `us-east-1`, Postgres
  `17.6.1.155`, estado `ACTIVE_HEALTHY`, creado `2026-08-17T15:32:29Z`.
  Repositorio vinculado (`npx supabase link --project-ref
  twrgzsbpazcjhhfolaju`, confirmado por `supabase/.temp/project-ref`).
- **Migración aplicada**: **SÍ** — `[VERIFICADO 2026-08-17]`.
  `npx supabase db push` aplicó `20260817000000_execution_runs.sql` sin
  errores; `npx supabase migration list` confirma `remote:
  "20260817000000"` igual al local. Verificado además por consulta
  directa contra `information_schema.tables`: `public.execution_runs`
  existe con las 12 columnas exactas de la migración (nombre, tipo,
  nullability). Primary key `execution_runs_pkey` sobre `execution_id`
  (único constraint e índice existente — coincide con la migración, sin
  índices adicionales). `rowsecurity = true` (RLS habilitado,
  `pg_tables`). `pg_policies` devuelve cero filas — **NO HAY POLICIES
  DESPLEGADAS**, comportamiento fail-closed, coincide con el diseño de
  §4.
- **Verificado contra una base de datos real (operaciones del Store)**:
  **SÍ.** `[VERIFICADO 2026-08-17]`: `tests/integration/test_supabase_execution_run_store.py`
  (nuevo, gated con `pytest.mark.skipif` cuando `JUVAL_SUPABASE_DB_URL`
  no está definida) ejecuta `SupabaseExecutionRunStore.save_execution_run`
  seguido de `.load_execution_run` contra el proyecto real, con
  assertions sobre el `ExecutionRun` completo (igualdad, `execution_id`,
  `status`, timestamps), y limpia el registro de prueba con un `DELETE`
  acotado a su propio `execution_id` en un bloque `finally` (el Store no
  expone método de borrado — coherente con ADR-017, cambios de schema
  solo por migración — así que un `DELETE` puntual sobre el dato que la
  misma prueba creó es la única excepción justificada). Resultado:
  `1 passed`. Verificado además con `select count(*) from
  execution_runs` vía la CLI tras el test: `0` filas — sin datos
  residuales. Los 2 tests de `tests/unit/test_supabase_execution_run_store.py`
  siguen pasando (siguen siendo solo estructurales, complementan pero no
  sustituyen a la prueba de integración).
- **Verificado de extremo a extremo desde la API (Fase D₀) — `[VERIFICADO
  2026-08-18]`**: `tests/integration/test_api_supabase.py` (nuevo, gated por
  `JUVAL_SUPABASE_DB_URL` igual que el test del Store) ejercita el camino
  completo **FastAPI → composition root → `SupabaseExecutionRunStore` →
  PostgreSQL**, sin mocks y sin SQLite: `POST /api/v1/runs` con
  `persist=true` sobre el fixture real, y luego
  `GET /api/v1/runs/{id}`, `GET /api/v1/runs/{id}/records` y
  `GET /api/v1/runs`, comprobando coherencia de `status`, `records_total`,
  `input_hash` y número de records. La presencia de las filas se confirma
  además con un `select count(*)` directo (confirmación independiente, no
  sustituto de la operación de aplicación). Para que la prueba no pueda
  aprobar por el motivo equivocado, el fixture **borra**
  `JUVAL_EXECUTION_DB_PATH` y afirma
  `isinstance(_execution_run_store(), SupabaseExecutionRunStore)` — si el
  selector se ignorara, SQLite no tendría dónde escribir y el test fallaría
  en vez de pasar contra el store equivocado. Limpieza en `finally`, acotada
  al propio `execution_id`, borrando primero `execution_run_records` (la FK
  no tiene `on delete cascade`) y después `execution_runs`; verificado
  posteriormente con `select count(*)` sobre ambas tablas: **0 filas**.
  Resultado: `4 passed`. Suite completa con DSN: **310 passed, 0 skipped**;
  sin DSN: **303 passed, 7 skipped** (`SKIPPED_EXPECTED`).
- **Selección del store — `[VERIFICADO 2026-08-18]`, sin cambio de código**:
  el composition root (`interfaces/api/main.py::_execution_run_store`) ya
  soportaba la selección explícita exigida por ADR-017; D₀ no necesitó
  modificarlo. `JUVAL_EXECUTION_STORE ∈ {"sqlite","supabase"}` es la única
  fuente de verdad cuando está definida, una variable de conexión ausente
  para el modo elegido es `RuntimeError`, y un valor desconocido también —
  nunca hay fallback silencioso. Cubierto por los 9 tests de
  `tests/unit/test_execution_store_selection.py`. **Lo que faltaba no era
  código sino configuración**: `JUVAL_EXECUTION_STORE` no está definida en
  el `.env` local, por lo que hoy la API no resuelve ningún store y los
  endpoints que lo requieren devuelven HTTP 500. Fijarla es una decisión de
  entorno del operador, no un cambio de repositorio.
- **Detalle de conectividad — `[VERIFICADO 2026-08-17]`, no documentado
  antes**: el host de conexión directa que Supabase muestra por defecto
  (`db.<ref>.supabase.co:5432`) resuelve **solo a una dirección IPv6**
  para proyectos nuevos (política de Supabase desde 2024, salvo add-on
  de IPv4 de pago). Este entorno no tiene ruta IPv6 (`getaddrinfo`/
  conexión directa fallan con "network unreachable"). La conexión real
  se logró usando el **Connection Pooler (Supavisor)** de Supabase —
  host `aws-0-us-east-1.pooler.supabase.com:5432`, usuario
  `postgres.twrgzsbpazcjhhfolaju` — que sí resuelve por IPv4. Cualquier
  entorno de despliegue (Railway, ADR-018) que también carezca de ruta
  IPv6 deberá usar este mismo mecanismo de pooler, no el host directo.
  `JUVAL_SUPABASE_DB_URL` vive únicamente en `.env` local (gitignored),
  nunca se imprimió ni se versionó.

## 2. Por qué `psycopg` y no `supabase-py`

`[RECOMENDACIÓN aplicada]`: Supabase es, en el fondo, PostgreSQL — las
dos únicas operaciones que este puerto necesita (`INSERT`, `SELECT`) no
requieren las capas de Auth/Storage/Realtime/REST del SDK
`supabase-py`. Usar `psycopg` directamente (declarado como extra
opcional `postgres` en `pyproject.toml`, no instalado por defecto)
mantiene la huella de dependencias mínima — coherente con `CLAUDE.md`
§20 y con el mismo criterio que ya se aplicó al elegir `argparse` sobre
`typer` para el CLI.

## 3. Schema

`supabase/migrations/20260817000000_execution_runs.sql` — tabla
`execution_runs`, columnas idénticas a `domain/execution_run.py::ExecutionRun`
y al schema SQLite ya aceptado (ADR-013). **Ninguna columna comercial
inventada**.

`supabase/migrations/20260817000001_execution_run_records.sql`
(ADR-019, `[APLICADA Y VERIFICADA 2026-08-17]`) — tabla
`execution_run_records`, snapshot JSON-safe (`JSONB`) de cada
`SourcingRecord` procesado, run-scoped: PK `(execution_id,
record_ref)`, `record_ref` único solo dentro de una ejecución
(ADR-012, nunca global), FK a `execution_runs(execution_id)`. Esquema
real verificado por consulta directa
(`information_schema.columns`): `execution_id text`, `ordinal
integer`, `record_ref text`, `snapshot jsonb`. RLS habilitado, 0
policies (`pg_tables.rowsecurity=true`, `pg_policies` vacío), mismo
comportamiento fail-closed que `execution_runs`. Prueba de integración
real (`tests/integration/test_supabase_execution_run_store.py`):
INSERT+SELECT+cleanup de records con round-trip de provenance
(`NOT_FOUND`), y `list_execution_runs` — las 3 pasan (`3 passed`).

## 4. Row Level Security — `[DESPLEGADO, VERIFICADO 2026-08-17]`

Migración aplicada al proyecto real (§1). `select rowsecurity from
pg_tables where schemaname='public' and tablename='execution_runs'`
contra el proyecto vinculado devuelve `rowsecurity = true` — RLS
**habilitado de verdad**, no solo declarado en el `.sql`. `select
policyname from pg_policies where schemaname='public' and
tablename='execution_runs'` devuelve **cero filas** — **NO HAY
POLICIES DESPLEGADAS**. Efecto real y ya verificado (no inferido): la
tabla es inaccesible vía la API pública (`anon`/`authenticated` key) —
fail-closed, coincide exactamente con el diseño de la migración. Esto
es deliberado: Juval no tiene todavía ningún usuario autenticado (Clerk
sigue `PENDING`, ADR-005/ADR-014) — escribir una policy por-usuario
sin que exista ningún concepto de usuario sería inventar un modelo de
autorización antes de tener autenticación real. El acceso hasta que
exista autenticación pasa exclusivamente por el `service_role` key /
connection string directo desde el backend (§5) — nunca desde el
navegador. No se creó ninguna policy en esta sesión (fuera de alcance,
no autorizado).

`[DECISIÓN PENDIENTE]`: qué policy de RLS exacta corresponde una vez
que exista autenticación (Fase 9) — no se decide aquí.

## 5. Secrets — variables de entorno

| Variable | Dónde vive | Nunca en |
|---|---|---|
| `SUPABASE_URL` | Backend (y frontend, es pública por diseño de Supabase) | — |
| `SUPABASE_ANON_KEY` | Backend y frontend — es la clave pública, protegida por RLS | — |
| `SUPABASE_SERVICE_ROLE_KEY` | **Solo backend**, nunca el proceso del navegador | Frontend, `VITE_*`, Git, logs |
| `JUVAL_SUPABASE_DB_URL` (o el connection string que `SupabaseExecutionRunStore` reciba) | Solo backend | Frontend, Git |

Regla dura, sin excepción: ninguna variable prefijada `VITE_` (o
equivalente de build-time del frontend) debe contener
`SUPABASE_SERVICE_ROLE_KEY` — cualquier variable con prefijo `VITE_`
termina embebida en el bundle JavaScript servido al navegador,
públicamente legible.

Ver `.env.example` (creado en esta sesión) para el nombre exacto de
cada variable, sin valores reales.

## 6. Qué falta para que esto sea real

1. ~~El usuario ejecuta `supabase login`~~ — **RESUELTO 2026-08-17**:
   sesión autenticada, verificado vía `supabase projects list`.
2. ~~Instalar el Supabase CLI localmente~~ — **RESUELTO 2026-08-17
   (bloque 4)**: utilizable vía `npx supabase <comando>` (2.114.0).
3. ~~Identificar el proyecto real~~ — **RESUELTO 2026-08-17**: proyecto
   único `juvalservicesllc-cloud's Project`, ref `twrgzsbpazcjhhfolaju`.
4. ~~`supabase link` al proyecto real~~ — **RESUELTO 2026-08-17**:
   `supabase/.temp/project-ref` confirma el vínculo.
5. ~~`supabase db push` para aplicar la migración~~ — **RESUELTO
   2026-08-17**: migración `20260817000000` aplicada y verificada
   (`migration list`, `information_schema.tables/columns`,
   `pg_constraint`, `pg_indexes`, `pg_tables.rowsecurity`,
   `pg_policies` — ver §1 y §4).
6. ~~Configurar `JUVAL_SUPABASE_DB_URL` real~~ — **RESUELTO 2026-08-17**:
   configurada en `.env` local (gitignored, nunca versionada ni
   impresa). Usa el **Connection Pooler** (`aws-0-us-east-1.pooler.supabase.co`),
   no el host directo — ver nota de conectividad en §1.
   `SUPABASE_URL`/`SUPABASE_ANON_KEY`/`SUPABASE_SERVICE_ROLE_KEY` siguen
   sin configurarse — no son necesarias para este adapter (usa
   `psycopg` + connection string, no el SDK REST), quedan `[PENDIENTE]`
   para cuando se cablee producción (punto 8).
7. ~~Ejecutar integración real (INSERT + SELECT) del Store~~ —
   **RESUELTO 2026-08-17**: `tests/integration/test_supabase_execution_run_store.py`
   (nuevo), `1 passed`, contra el proyecto real, con cleanup verificado.
   Ver §1.
8. ~~Decidir en `interfaces/api/` cómo se elige entre `SqliteExecutionRunStore`
   y `SupabaseExecutionRunStore`~~ — **RESUELTO 2026-08-17**:
   `JUVAL_EXECUTION_STORE` (`sqlite`|`supabase`) en
   `main.py::_execution_run_store` — ver `API_CONTRACT.md` §5 para la
   semántica completa (selector explícito, fail-fast, legacy). 9 tests
   nuevos en `tests/unit/test_execution_store_selection.py` cubren la
   matriz de configuración. Sigue **pendiente, fuera de alcance**:
   configurar Railway con `JUVAL_EXECUTION_STORE=supabase` real y
   desplegar — eso es trabajo de despliegue, no de esta sesión.

## 7. Relacionado

ADR-013 (SQLite, ya verificada), ADR-017 (esta decisión),
`docs/architecture/API_CONTRACT.md` §5, `.env.example`.
