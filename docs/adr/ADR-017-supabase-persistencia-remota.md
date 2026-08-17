# ADR-017: Supabase/PostgreSQL como persistencia remota de producción

- Estado: Aceptada (decisión arquitectónica) — aprobada explícitamente
  por el usuario 2026-08-17 ("Supabase queda APROBADO como
  infraestructura de persistencia"). La **implementación** de esta
  sesión es código preparado, no verificado contra una instancia real
  — ver `docs/architecture/SUPABASE.md` §1 para el detalle exacto de
  qué está y qué no está probado.
- Fecha: 2026-08-17

## Contexto

Fase 3 (ADR-013, `Aceptada`) resolvió la persistencia de `ExecutionRun`
para un único operador local, vía SQLite
(`infrastructure/logging/sqlite_execution_run_store.py`). Una sesión de
comparación arquitectónica previa a esta ADR (`docs/PROJECT_STATUS.md`,
sesión de diseño de Fase 4) había recomendado explícitamente **diferir**
Supabase "hasta necesidad real demostrada" — no existía, en ese momento,
evidencia de necesidad multiusuario/remota.

El usuario, en la sesión de construcción de Fase 4, decidió
explícitamente aprobar Supabase/PostgreSQL como la implementación de
persistencia de **producción**, en paralelo (no en reemplazo) de SQLite
para desarrollo local — revirtiendo la recomendación de diferimiento de
la sesión anterior de forma explícita e informada, no por inadvertencia
(el usuario reconoció la disponibilidad de herramientas al hacer esta
decisión — ver §"Limitaciones de esta sesión").

## Decisión

`ExecutionRunStore` (puerto ya definido en ADR-013,
`application/execution_run_store.py`, sin modificar) tendrá dos
implementaciones intercambiables:

```
ExecutionRunStore (Protocol, sin cambios)
       │
       ├── SqliteExecutionRunStore   (ADR-013) -- local/dev
       │
       └── SupabaseExecutionRunStore (esta ADR) -- producción
```

`SupabaseExecutionRunStore`
(`infrastructure/persistence/supabase_execution_run_store.py`) implementa
exactamente el mismo contrato, usando `psycopg` contra el connection
string de Postgres que Supabase expone — ver
`docs/architecture/SUPABASE.md` §2 para por qué `psycopg` y no el SDK
`supabase-py`.

Schema versionado por migración SQL
(`supabase/migrations/20260817000000_execution_runs.sql`), nunca por
`CREATE TABLE` implícito desde código de aplicación (a diferencia de
`SqliteExecutionRunStore`, que sí ejecuta `CREATE TABLE IF NOT EXISTS`
en cada construcción — aceptable para un archivo local de un solo
usuario, no aceptable para una base de datos compartida de producción).

## Alcance — qué NO resuelve esta decisión

- **No provisiona ningún proyecto Supabase real** — eso requiere una
  cuenta/login que solo el usuario tiene (`docs/architecture/SUPABASE.md` §6).
- **No aplica la migración a ninguna base de datos** — el archivo SQL
  existe, versionado, sin ejecutar.
- ~~No cablea `interfaces/api/` para elegir entre SQLite y Supabase~~ —
  **RESUELTO 2026-08-17**: `main.py::_execution_run_store` selecciona
  por `JUVAL_EXECUTION_STORE` (`sqlite`|`supabase`), fail-fast, sin
  fallback implícito entre modos, con compatibilidad legacy para
  despliegues existentes sin la variable definida. Ver
  `docs/architecture/API_CONTRACT.md` §5 para la semántica completa y
  `docs/architecture/SUPABASE.md` §6 punto 8. Sigue pendiente, fuera de
  esta ADR: configurar Railway con el valor real y desplegar.
- **No define política de RLS más allá de "fail-closed sin policies"**
  — no hay usuarios autenticados todavía que una policy pudiera
  distinguir (Clerk sigue `PENDING`).
- **No persiste `SourcingRecord`s** — mismo alcance que ADR-013, sin
  ampliar.
- **No resuelve backup/retención/disaster recovery** — fuera de alcance
  de esta ADR.

## Alternativas consideradas

1. **`supabase-py` (SDK completo)**: descartado por traer Auth/Storage/
   Realtime que este puerto no usa — mayor huella de dependencias sin
   beneficio para las dos operaciones (`INSERT`/`SELECT`) que
   `ExecutionRunStore` necesita.
2. **Seguir solo con SQLite, sin Supabase todavía**: era la
   recomendación de la sesión de diseño previa; descartada por decisión
   explícita del usuario en esta sesión, no por invalidación técnica de
   ese análisis — ambas conclusiones fueron razonables en su momento,
   con información distinta (el usuario decidió avanzar con Supabase
   con conocimiento de que las herramientas de verificación no estaban
   disponibles en este entorno).
3. **Introducir el ORM de Django u otro framework con persistencia
   integrada**: descartado — ya rechazado en ADR-016 por razones que
   aplican igual aquí (compromiso de stack no solicitado).

## Limitaciones de esta sesión (importante, ver `docs/architecture/SUPABASE.md`)

Sin `supabase`/`psql`/Docker disponibles en este entorno, esta ADR
aprueba la **arquitectura** (el puerto de dos implementaciones, el
schema versionado) pero la implementación concreta de
`SupabaseExecutionRunStore` queda **sin verificar contra una base de
datos real**. Esto se documenta explícitamente, no se oculta ni se
presenta como equivalente en confianza a `SqliteExecutionRunStore`
(que sí tiene 12 tests de integración reales, ADR-013).

## Consecuencias

- Positivas: el puerto `ExecutionRunStore` ya diseñado en ADR-013
  demuestra su valor — agregar un segundo backend no tocó `domain/`,
  `processing/`, `application/run_pipeline.py`, ni
  `SqliteExecutionRunStore`.
- Negativas: código sin verificar en producción hasta que exista un
  proyecto Supabase real contra el cual probarlo; una dependencia nueva
  (`psycopg`, opcional, extra `postgres`).
- Reversibilidad: alta — es una implementación adicional detrás de un
  puerto ya estable; puede descartarse sin afectar SQLite ni el resto
  del sistema.

## Relación con ADR-013

Continuación directa, no reemplazo. ADR-013 sigue vigente sin
modificación — SQLite sigue siendo la implementación de desarrollo
local recomendada; esta ADR agrega la implementación de producción sin
invalidar ninguna de las decisiones de ADR-013 (Opción B incluida:
`run_pipeline()` sigue sin persistir por sí mismo, ningún caller nuevo
cambia eso).

## Relacionado

ADR-013, ADR-016, `docs/architecture/SUPABASE.md`,
`supabase/migrations/20260817000000_execution_runs.sql`,
`src/juval/infrastructure/persistence/supabase_execution_run_store.py`.
