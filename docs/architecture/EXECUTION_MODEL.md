# Juval — Execution Model (Reproducibilidad)

Estado: `ExecutionRun` está **IMPLEMENTED** como estructura de dominio
(`domain/execution_run.py`), probada
(`tests/unit/test_execution_run.py`, 11 tests;
`tests/integration/test_reproducibility.py`, 2 tests), y construida por
`application/run_pipeline.py::run_pipeline`. Su **persistencia entre
corridas** está **IMPLEMENTED** vía SQLite local (ADR-013, `Estado:
Aceptada`, aprobada explícitamente por el usuario 2026-08-16) —
`infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore`,
probada con 12 tests de integración (`tests/integration/test_execution_run_store.py`)
incluyendo round-trip entre conexiones/instancias de store distintas.
**No** está invocada automáticamente por `run_pipeline()` — persistir
una corrida requiere que el llamador invoque
`store.save_execution_run(run)` explícitamente (decisión deliberada, ver
ADR-013 §"Qué NO resuelve esta decisión"). Este documento sigue
describiendo ambas partes por separado (reproducibilidad estructural vs.
auditoría persistente) porque siguen siendo propiedades distintas, ahora
ambas cubiertas por código real.

## 1. Por qué existe

Mismo input + misma versión de la aplicación + mismos parámetros ⇒ mismo
resultado, cuando el procesamiento es determinístico (sin fuentes
externas variables — hoy no hay ninguna integrada, ver `DATA_SOURCES.md`).
`ExecutionRun` es el registro que permite *demostrar* esa propiedad
después del hecho, no solo asumirla: guarda el hash del archivo de
entrada, la versión de la aplicación y los contadores del resultado, para
que dos corridas puedan compararse sin volver a ejecutar nada.

## 2. Estructura actual (`domain/execution_run.py`)

| Campo | Tipo | Descripción |
|---|---|---|
| `execution_id` | `str` | Suministrado por el llamador (no autogenerado) — necesario para que la reproducibilidad sea determinística: dos llamadas con el mismo `execution_id` explícito son comparables sin depender de un reloj o un contador interno. |
| `started_at` / `finished_at` | `datetime` (tz-aware) | `finished_at` es `None` si `status == RUNNING`; obligatorio en cualquier otro estado. |
| `status` | `ExecutionStatus` | `RUNNING` / `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED` |
| `input_filename` | `str` | Nombre del archivo de entrada (no la ruta completa). |
| `input_hash` | `str` | SHA-256 del contenido del archivo (`hash_file()`) — confirma que "el mismo archivo" lo es realmente, no solo que tiene el mismo nombre. |
| `application_version` | `str` | Típicamente `juval.__version__`. |
| `records_total` | `int` | Filas escaneadas por el importer (`ImportResult.rows_scanned`). |
| `records_processed` | `int` | Filas que llegaron a construir un `SourcingRecord` y pasaron por `process_batch`. |
| `records_successful` / `records_with_errors` | `int` | Partición de `records_processed` según `SourcingRecord.has_record_errors`. |
| `warnings` | `int` | Suma de `WARNING`s del import + de cada registro procesado. |

Invariantes reforzadas en `__post_init__` (ver también `DATA_MODEL.md`
§4): timestamps tz-aware; `finished_at >= started_at`;
`records_processed <= records_total`;
`records_successful + records_with_errors <= records_processed`;
`status == RUNNING` ⇔ `finished_at is None`.

## 3. Qué NO contiene hoy (gap frente al diseño original)

El diseño conceptual original (`ARCHITECTURE.md` §8, heredado de la Fase
0) proponía que `ExecutionRun` incluyera también `thresholds` usados y
`sources_used` (fuentes externas efectivamente consultadas en esa
corrida). La implementación actual **no tiene ninguno de los dos
campos**:

- **`thresholds`**: `Thresholds` se pasa como parámetro a `run_pipeline`
  y a `evaluate_decision`, pero no se copia ni se referencia dentro del
  `ExecutionRun` resultante. Dos corridas con el mismo archivo pero
  distintos `Thresholds` producen `ExecutionRun`s indistinguibles entre
  sí salvo por sus decisiones — el propio objeto no deja constancia de
  qué umbrales se usaron.
- **`sources_used`**: no aplica todavía en la práctica (no hay fuentes
  externas integradas, ver `DATA_SOURCES.md` §5), pero tampoco existe el
  campo para cuando exista una.

Esto es un **PENDING** de diseño, no un error de implementación: no se
resuelve en esta tarea (documentación únicamente). Cualquier futura tarea
que amplíe `ExecutionRun` para incluir `thresholds`/`sources_used` debe
actualizar este documento y `DATA_MODEL.md` §4 en el mismo cambio.

## 4. Cómo se construye (`application/run_pipeline.py::run_pipeline`)

```
run_pipeline(input_path, thresholds, *, fees, application_version, execution_id, now, quality_config)
  → import_excel(input_path, now=now)
      → si fatal: ExecutionRun(status=FAILED, records_total=0, ...), records=()
      → si no fatal: process_batch(records, thresholds, fees=fees, ...)
          → ExecutionRun(status=SUCCESS|PARTIAL_SUCCESS|FAILED, ...), records procesados
```

`now` y `execution_id` son parámetros del llamador, no generados dentro
de la función — `run_pipeline` es una función pura de sus argumentos,
propiedad necesaria para que "mismo input ⇒ mismo output" sea verificable
en un test sin depender del reloj real (ver
`tests/integration/test_reproducibility.py`).

`status` se deriva así:
- `FAILED` si el import fue fatal, o si terminó con cero registros
  procesados.
- `PARTIAL_SUCCESS` si al menos un registro tiene `RECORD_ERROR`.
- `SUCCESS` en cualquier otro caso.

## 5. Persistencia — IMPLEMENTED (SQLite local, alcance limitado)

El dataclass `ExecutionRun` no sabe persistirse a sí mismo, por diseño
(ADR-001, `domain/` no puede depender de infraestructura) — su docstring
(`domain/execution_run.py`, actualizado 2026-08-17) ya no dice "in-memory
only" (afirmación desactualizada desde ADR-013) y en su lugar apunta
directamente al puerto/adapter reales. El "caller" que serializa/almacena
el objeto es `infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore`,
que implementa el puerto `application/execution_run_store.py::ExecutionRunStore`
(ADR-013, `Estado: Aceptada`), probado con 12 tests
(`tests/integration/test_execution_run_store.py`), incluyendo
persistencia demostrada explícitamente **a través de conexiones/
instancias de store distintas** — no solo dentro de un mismo objeto
Python en memoria. Desde 2026-08-17, `interfaces/cli/main.py` es el
primer caller real que puede invocar `save_execution_run()` — vía el
flag opt-in `--persist-db`, nunca automáticamente (ver §5.1 abajo).

Limitaciones explícitas de este estado (ver ADR-013 §"Qué NO resuelve
esta decisión" para el detalle completo):

- **No está invocado automáticamente por `run_pipeline()`** — persistir
  una corrida requiere que el llamador invoque
  `store.save_execution_run(run)` explícitamente después de recibir el
  resultado. `run_pipeline()` no cambió de comportamiento.
- **No hay `list_execution_runs()`** ni ninguna forma de consultar el
  historial completo — solo `load_execution_run(execution_id)`
  conociendo el id exacto.
- **Alcance single-user, local** — no resuelve acceso concurrente
  multiusuario/remoto (eso sigue correspondiendo a Fase 8, `Supabase`,
  `BLOCKED`).
- `docs/PHASE_GATES.md` §Fase 3 refleja el Completion Gate actualizado
  (`PASS`, evaluado formalmente 2026-08-16) — la integración con
  `run_pipeline()` ya no es un ítem abierto, quedó resuelta
  explícitamente (Opción B: no se integra, por diseño).

### 5.1 Primer caller real: `interfaces/cli/main.py` (2026-08-17)

`ARCHITECTURE.md` §14/§16 dejaba pendiente "la política de invocación
automática... diferida a la primera interfaz operativa real (CLI/API,
Fase 4)". El CLI implementado en `interfaces/cli/main.py` (ver
`docs/architecture/ARCHITECTURE.md` §16 y `interfaces/cli/README.md`) es
esa primera interfaz operativa real, y su política es la más simple
posible consistente con Opción B: nunca persiste por defecto; solo lo
hace si el operador pasa explícitamente `--persist-db <path>`. Esto no
reabre la decisión de Opción B ni la reemplaza — es la continuación
directa de "persistir sigue siendo una acción explícita del llamador",
ahora con un llamador real además de los tests.

## 6. Por qué era necesario tener la estructura antes de persistirla

Antes de que existiera persistencia real, tener la estructura y las
invariantes de `ExecutionRun` ya implementadas evitó dos problemas
comunes: (a) que la capa de persistencia (`SqliteExecutionRunStore`)
tuviera que re-derivar qué campos son mínimos para auditoría/
reproducibilidad — ya estaban decididos y probados de antemano; (b) que
el pipeline se ejecutara "a ciegas" sin producir ningún resumen
verificable de lo que hizo mientras se diseñaba la persistencia. Ambos
problemas ya no aplican — se documentan aquí como razón histórica del
orden de implementación (estructura primero, persistencia después).

## 7. Relacionado

`ARCHITECTURE.md` §8 (diseño original, parcialmente superado por esta
sección — ver nota de `ARCHITECTURE.md` §16), `PROCESSING_PIPELINE.md`
(dónde encaja `run_pipeline` en el flujo completo), `PROJECT_PLAN.md`
Fase 3, `PHASE_GATES.md` §Fase 3.
