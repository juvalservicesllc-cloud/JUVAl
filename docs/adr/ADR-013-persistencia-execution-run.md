# ADR-013: Persistencia local de `ExecutionRun` mediante SQLite

- Estado: **Aceptada** — aprobada explícitamente por el usuario
  2026-08-16, tras el pre-check de Fase 3 y el análisis arquitectónico
  de integración con `run_pipeline()` (ver Opción B, sesión posterior).
- Fecha: 2026-08-16 (propuesta); aprobada 2026-08-16

## Contexto

`ExecutionRun` (`domain/execution_run.py`) es correcto y probado como
estructura, pero es puramente in-memory: ningún código en el repositorio
lo escribe a disco o a una base de datos, y `infrastructure/logging/`
contenía únicamente un `README.md` (ver `EXECUTION_MODEL.md` §5,
`PHASE_GATES.md` §Fase 3). Esto deja la "auditabilidad" de Fase 3 como
una promesa estructural, no operacional: una corrida no se puede
consultar después de que el proceso que la ejecutó termina.

El usuario evaluó las alternativas presentadas en el pre-check de Fase 3
(persistencia basada en archivos/JSON, SQLite local, otra arquitectura,
o redefinir el alcance de Fase 3 sin persistencia) y eligió
explícitamente **SQLite local** como mecanismo técnico.

## Decisión

Se implementa `infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore`,
que implementa el puerto `application/execution_run_store.py::ExecutionRunStore`
(`Protocol` con `save_execution_run(run)` / `load_execution_run(execution_id)`).

### Por qué SQLite (frente a JSON plano)

- Transacciones ACID nativas (vía `sqlite3`, stdlib) evitan tener que
  implementar a mano el patrón atomic-write (escribir a archivo
  temporal + rename) que un store basado en JSON plano necesitaría para
  garantizar que una escritura interrumpida no deje un archivo
  corrupto.
- `execution_id` como `PRIMARY KEY` obtiene su restricción de unicidad
  gratis del motor, en vez de tener que implementarla a mano
  comprobando la existencia de un archivo antes de escribir (con el
  riesgo de una condición de carrera entre el chequeo y la escritura
  que un archivo plano no evita por sí solo).
- Sigue siendo stdlib (`sqlite3`), cero dependencia nueva — mismo costo
  de dependencia que la opción JSON.

### Esquema

Una sola tabla, `execution_runs`, `execution_id` como `PRIMARY KEY`:

```sql
CREATE TABLE IF NOT EXISTS execution_runs (
    execution_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    input_filename TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    application_version TEXT NOT NULL,
    records_total INTEGER NOT NULL,
    records_processed INTEGER NOT NULL,
    records_successful INTEGER NOT NULL,
    records_with_errors INTEGER NOT NULL,
    warnings INTEGER NOT NULL
)
```

- **Identidad**: `execution_id`, no `record_ref`. Son conceptos
  distintos — `record_ref` (ADR-012) identifica una fila dentro de una
  importación; `execution_id` identifica una corrida completa del
  pipeline. Este store nunca almacena `record_ref`.
- **Timestamps**: serializados con `datetime.isoformat()` /
  reconstruidos con `datetime.fromisoformat()` — preserva el offset de
  zona horaria exactamente, confirmado por test
  (`test_finished_at_timezone_aware_round_trips_exactly`).
- **`status`**: se almacena como `status.value` (string); se reconstruye
  con `ExecutionStatus(value)`.
- **`finished_at` NULL**: cuando `ExecutionRun.finished_at is None`
  (status `RUNNING`), se almacena `NULL` en SQLite; al leer, `NULL` se
  reconstruye como `None`. Probado explícitamente
  (`test_finished_at_none_round_trips_for_running_status`).
- **`execution_id` duplicado**: `save_execution_run` usa `INSERT` (no
  `INSERT OR REPLACE`). Un segundo intento de guardar el mismo
  `execution_id` levanta `sqlite3.IntegrityError` y **no** sobrescribe
  el registro existente — un `ExecutionRun` es un registro de auditoría;
  sobrescribirlo silenciosamente destruiría exactamente el rastro que
  este store existe para preservar. Probado
  (`test_duplicate_execution_id_raises_instead_of_overwriting`).
- **`execution_id` inexistente**: `load_execution_run` retorna `None`,
  no lanza excepción — consistente con la convención ya establecida en
  el proyecto de representar "ausencia" como `None`
  (`SourcingRecord.costs`, `FieldValue.not_found`), no como un error.
  Probado (`test_load_nonexistent_execution_id_returns_none`).

### Migraciones / versionado de schema

La estrategia actual es únicamente `CREATE TABLE IF NOT EXISTS`,
ejecutada en cada construcción de `SqliteExecutionRunStore` — suficiente
porque hay una sola tabla y ninguna versión previa de la que migrar.
**Esto no es un framework de migraciones.** Cualquier cambio estructural
futuro de `ExecutionRun` (ej. agregar `thresholds`/`sources_used`, ver
"Qué NO resuelve esta decisión" abajo) requerirá diseñar explícitamente
una estrategia de migración/versionado en ese momento — no está
resuelto aquí.

### Atomicidad y concurrencia

Cada operación (`save_execution_run`, `load_execution_run`) abre y
cierra su propia conexión de corta duración
(`contextlib.closing(sqlite3.connect(...))`), con la conexión usada
además como context manager de transacción (`with conn:` — commit si no
hay excepción, rollback si la hay). No se activa modo WAL ni se
configuran timeouts especiales: el alcance declarado es **single-user,
local**, no concurrente/multiusuario — activar WAL sin esa necesidad
sería complejidad sin propósito (Ponytail).

## Alternativas consideradas

1. **JSON plano** (archivo por `execution_id`, o log append-only): cero
   dependencia nueva, legible directamente, pero exige implementar a
   mano el patrón atomic-write para evitar corrupción y no ofrece una
   restricción de unicidad nativa para `execution_id`. Descartada en
   favor de SQLite por decisión explícita del usuario tras comparar
   ambas en el pre-check de Fase 3.
2. **Cloud / base de datos remota** (ej. Supabase): descartada — fuera
   de alcance mientras Supabase siga `PENDING` (`CLAUDE.md` §14, Fase 8
   `BLOCKED`); introduciría red, credenciales y una dependencia externa
   sin justificación para el volumen actual (un usuario local).
3. **Redefinir el alcance de Fase 3 sin persistencia real**: descartada
   por decisión explícita del usuario, que optó por implementar
   persistencia ahora en vez de diferirla.

## Consecuencias

- Positivas: `ExecutionRun` ahora puede sobrevivir al fin del proceso
  que lo generó — probado explícitamente a través de dos conexiones/
  instancias de store distintas
  (`test_persistence_survives_across_separate_store_instances`), no
  solo dentro de un mismo objeto Python en memoria. Cero dependencia
  nueva. El puerto (`ExecutionRunStore`) mantiene `domain/` libre de
  `sqlite3`/SQL/filesystem, respetando ADR-001.
- Negativas: alcance deliberadamente reducido — ver "Qué NO resuelve
  esta decisión" abajo. Un archivo `.db` de SQLite es binario, no se
  puede inspeccionar con un editor de texto plano como un JSON.
- Reversibilidad: alta — `ExecutionRunStore` es un `Protocol` pequeño;
  un backend distinto (JSON, u otro) puede implementarse detrás del
  mismo contrato sin tocar `domain/`, `processing/`, ni el resto de
  `application/`.

## Alcance: single-user, local

Esta decisión cubre explícitamente un usuario único ejecutando el
pipeline localmente. No resuelve, ni pretende resolver, acceso
concurrente multiusuario o remoto — eso corresponde a Fase 8
(persistencia compartida, `Supabase`, `BLOCKED`) si y cuando se
apruebe. Un futuro adapter de Fase 8 implementaría el mismo puerto
`ExecutionRunStore` sin que `application/run_pipeline.py` o `domain/`
necesiten cambiar.

## Qué NO resuelve esta decisión

- **No integra el store en `application/run_pipeline.py`**. `run_pipeline()`
  no cambió — sigue devolviendo `(ExecutionRun, tuple[SourcingRecord, ...])`
  sin persistir nada por sí mismo. Un llamador que quiera conservar la
  corrida debe invocar `store.save_execution_run(run)` explícitamente
  después de recibir el resultado. Justificación: `run_pipeline()` ya es
  una función pura, testeada, y su contrato no debía cambiar sin
  necesidad (restricción explícita de esta tarea); forzar la
  persistencia como efecto colateral obligatorio de ejecutar el pipeline
  mezclaría dos responsabilidades (ejecutar vs. persistir) que hoy
  pueden mantenerse separadas sin costo. Si se decide que
  `run_pipeline()` debe persistir automáticamente, es una decisión de
  diseño separada y explícita, no incluida aquí.
- No agrega `thresholds` ni `sources_used` a `ExecutionRun` — el modelo
  persistido es exactamente el modelo actual, campo por campo.
- No agrega persistencia de los `SourcingRecord`s procesados — solo el
  resumen agregado (`ExecutionRun`).
- No provee un mecanismo de listado/consulta de corridas históricas más
  allá de `load_execution_run(execution_id)` — no hay
  `list_execution_runs()` ni filtros por fecha/estado en esta decisión.
- No resuelve acceso concurrente multiusuario ni remoto (ver "Alcance"
  arriba).
- No implica que el Completion Gate de Fase 3 se cierre automáticamente
  — eso requiere una re-evaluación explícita separada de esta ADR.

## Relacionado

`docs/architecture/EXECUTION_MODEL.md` (estado de `ExecutionRun` antes
de esta decisión), `docs/architecture/ARCHITECTURE.md` §8 (a
reconciliar con esta decisión en el mismo cambio), `docs/PHASE_GATES.md`
§Fase 3, ADR-001 (dirección de dependencias), ADR-012 (`record_ref`,
concepto distinto de `execution_id`).
