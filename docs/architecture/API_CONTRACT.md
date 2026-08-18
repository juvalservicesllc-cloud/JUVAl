# Juval — API Contract (Fase 4A, `interfaces/api/`)

Implementación normativa: `src/juval/interfaces/api/{main,models,service}.py`
(ADR-016, `Estado: Aceptada`). Este documento describe el contrato tal
como está implementado hoy — si hay discrepancia, el código gana
(mismo criterio que `EXCEL_PROCESSING.md`/`PROCESSING_PIPELINE.md`).

Versionado: prefijo `/api/v1/` desde el primer endpoint.

## 1. `POST /api/v1/runs`

`multipart/form-data`:

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `file` | archivo | Sí | El `.xlsx` de entrada |
| `thresholds` | string (JSON) | Sí | Serializa `ThresholdsIn` — ver §3 |
| `fees` | string (JSON) | Sí | Serializa `FeesIn` — ver §3 |
| `persist` | bool (`"true"`/`"false"`) | No, default `false` | Si `true`, persiste el `ExecutionRun` vía `JUVAL_EXECUTION_DB_PATH` (ver §5) |

No existe ningún default comercial para `thresholds`/`fees` — igual que
el CLI (`interfaces/cli/main.py`), el operador/cliente debe declararlos
explícitamente en cada request (ADR-007). `maximum_risk_severity`
acepta exactamente los valores de `domain.risk.Severity`
(`NONE`/`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`).

### Respuesta 200 — `RunResponse`

```json
{
  "execution_id": "uuid4 generado por el servidor",
  "status": "SUCCESS | PARTIAL_SUCCESS",
  "input_filename": "...",
  "input_hash": "sha256 del archivo subido",
  "records_total": 5,
  "records_processed": 4,
  "records_successful": 3,
  "records_with_errors": 1,
  "warnings": 2,
  "persisted": false,
  "records": [ { ... } ]
}
```

Cada elemento de `records` es un `RecordOut` — el equivalente JSON de
una fila de `exporter.py::export_excel`, con la misma regla de
provenance (ADR-003/ADR-004): **ningún** campo sensible se colapsa a un
valor pelado. Cada campo sensible es:

```json
{ "value": <valor o null>, "status": "VERIFIED|INFERRED|NOT_FOUND|INVALID|null" }
```

Campos con esta forma: `asin`, `upc`, `weight`, `selling_price`,
`profit`, `roi`, `margin`, `break_even_price`,
`max_cog_target_profit`, `max_cog_target_roi`. Campos planos (sin
provenance por diseño, igual que en `exporter.py`): `record_ref`,
`marketplace`, `supplier_sku`, `cog`, `shipping_per_unit`,
`hazmat_status`/`hazmat_severity`, `bulky_status`/`bulky_severity`,
`decision`, `decision_reasons` (lista de `"CODE: message"`),
`issue_count`, `issues` (lista de `"[LEVEL] CODE: message"`).

Valores `Decimal` viajan como **string** en el JSON (no como `float`),
para no perder precisión — decisión de serialización, no de negocio.

### Respuesta 422 — import fatal (`RunFailedResponse`)

```json
{
  "execution_id": "...",
  "status": "FAILED",
  "input_filename": "...",
  "input_hash": "...",
  "message": "import produced no usable records"
}
```

**Limitación heredada, no un defecto de esta capa**: `run_pipeline()`
no expone el detalle de los `ProcessingIssue` fatales del import (solo
los agrega en `warnings`) — el mismo límite que ya tiene
`interfaces/cli/main.py` para su camino `FAILED`. No se reimplementó
`import_excel()` en la API para evitar duplicar la orquestación que
`run_pipeline()` ya hace (regla dura de esta fase: "no duplicar lógica
que ya existe").

### Otros códigos de error

| Código | Causa |
|---|---|
| 422 | `thresholds`/`fees` no son JSON válido, no tienen los campos requeridos, o violan un invariante del dominio (ej. `referral_fee_rate` fuera de `[0,1)`, `FeeInputs.__post_init__`) |
| 422 | El archivo subido no es un `.xlsx` válido (`zipfile.BadZipFile` / `openpyxl.utils.exceptions.InvalidFileException`, verificado intentando abrirlo realmente — nunca se confía en el nombre ni el MIME type declarado por el cliente) |
| 413 | El archivo excede `JUVAL_MAX_UPLOAD_BYTES`, si está configurado (ver §4) |
| 500 | `persist=true` sin `JUVAL_EXECUTION_DB_PATH` configurado, o cualquier error interno no anticipado — nunca expone traceback ni rutas del servidor (verificado por test, `test_no_traceback_is_ever_exposed`) |

## 2. `GET /api/v1/runs/{execution_id}/download`

Devuelve el `.xlsx` generado por `export_excel()` (sin cambios, sin
segundo exportador) para el `execution_id` indicado.

- 200 + el archivo, `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- 404 si el `execution_id` no existe o el archivo temporal ya no está disponible

`execution_id` siempre lo genera el servidor (`uuid4`) — nunca se acepta
uno provisto por el cliente, a diferencia de `interfaces/cli/main.py`
(que sí permite `--execution-id` porque su modelo de amenaza es
distinto: un solo operador de confianza en su propia máquina). En la
API, permitir que el cliente elija su propio `execution_id` abriría la
puerta a colisiones/adivinar IDs ajenos.

## 2b. `GET /api/v1/runs` (ADR-019)

Lista las ejecuciones más recientes primero (`started_at DESC`).
Requiere `JUVAL_EXECUTION_STORE`/`JUVAL_EXECUTION_DB_PATH` configurado
(mismo mecanismo que §5) — sin store configurado, 500 explícito.

Query param: `limit` (entero, opcional, default `20`, mínimo `1`,
máximo `100`) — tope explícito, nunca un catálogo completo sin límite.
Un `limit` fuera de `[1, 100]` → 422 (validación de FastAPI/Pydantic,
antes de tocar el store).

### Respuesta 200 — `RunsListResponse`

```json
{ "items": [ { "execution_id": "...", "started_at": "2026-08-17T12:00:00+00:00",
  "finished_at": "2026-08-17T12:05:00+00:00", "status": "SUCCESS",
  "input_filename": "...", "input_hash": "...", "records_total": 5,
  "records_processed": 5, "records_successful": 4, "records_with_errors": 1,
  "warnings": 2 } ] }
```

Cada elemento (`RunSummaryOut`) usa exactamente los campos reales de
`domain.execution_run.ExecutionRun` — deliberadamente **no** usa el
vocabulario que el frontend de demo había anticipado
(`created_at`/`valid`/`excluded`), porque esos términos no tienen
equivalente en el dominio; inventarlos habría significado presentar
una inferencia como si fuera un dato real (ver ADR-019 "Modelo de
recurso"). Timestamps como string ISO 8601.

## 2b-2. `GET /api/v1/runs/{execution_id}` (Run Detail, 2026-08-17)

Un único run — mismo `RunSummaryOut` de §2b. Añadido para la vista Run
Detail del frontend (necesita metadata de un run conocido por
`execution_id` sin traer el listado completo) — reutiliza
`ExecutionRunStore.load_execution_run`, ya existente y ya usado por
`GET .../records` para su propio chequeo de 404; ninguna capacidad de
dominio/persistencia nueva.

- 200 + `RunSummaryOut`.
- 404 si `execution_id` no existe en el store.
- 500 si el store no está configurado (mismo mecanismo que §5).

## 2c. `GET /api/v1/runs/{execution_id}/records` (ADR-019)

Devuelve los records persistidos de una ejecución — el mismo snapshot
JSON que ya viajaba en `records[]` de `POST /api/v1/runs` en el momento
del run, ahora recuperable después. Run-scoped únicamente, nunca
cross-run (`record_ref` no es un identificador global, ADR-012).

- 200 + `RunRecordsResponse` (`{"execution_id": "...", "records": [RecordOut, ...]}`,
  mismo `RecordOut` que §1) — incluye el caso "run existe pero no tiene
  records persistidos" (`records: []`, ej. si se guardó antes de
  ADR-019, o si `persist=true` no se usó al crear ese run).
- 404 si `execution_id` no existe en el store.
- 500 si el store no está configurado (mismo mecanismo que §5).

Requiere que el run se haya guardado con `persist=true` (ver §5) — un
run nunca persistido no tiene records que recuperar, indistinguible de
un `execution_id` desconocido solo por la ausencia total del row en
`execution_runs` (404 en ambos casos).

## 3. Modelos de request (`models.py`)

Reflejan exactamente `domain.decision.Thresholds` / `domain.costs.FeeInputs`
— sin renombrar, sin inventar campos:

```json
// thresholds
{
  "target_profit": "5", "target_roi": "0.3",
  "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "LOW",
  "allow_restricted": false, "allow_approval_required": false, "allow_unknown_risk": false
}
// fees
{
  "referral_fee": "3", "referral_fee_rate": "0.15",
  "fulfillment_fee": "2", "other_selling_fees": "0"
}
```

## 4. Límites

**Tamaño máximo de archivo — PENDING (decisión de negocio, no técnica)**:
no existe un valor comercial definitivo (mismo estado que documenta
`docs/architecture/SECURITY.md` §3). El sistema soporta un límite
**técnico** configurable vía `JUVAL_MAX_UPLOAD_BYTES` (bytes); si la
variable no está definida, **no se impone ningún límite** — el mismo
comportamiento que el Core ya tiene hoy sin esta capa (`import_excel`
nunca tuvo límite), no un valor inventado para esta sesión. Si Vercel u
otra plataforma de despliegue imponen un límite técnico de payload,
**eso es un límite técnico de la plataforma, distinto de un límite
comercial de negocio** — no deben confundirse ni usarse uno para inferir
el otro.

## 5. Persistencia (`ExecutionRun`)

Selector explícito, `JUVAL_EXECUTION_STORE` (`interfaces/api/main.py::_execution_run_store`,
ADR-013/ADR-017) — cuando está definida es la única fuente de verdad,
nunca se infiere el store a partir de qué variable de conexión está
presente:

- `JUVAL_EXECUTION_STORE=sqlite` — requiere `JUVAL_EXECUTION_DB_PATH`
  (ruta a un archivo SQLite); si falta, error explícito. Usa
  `SqliteExecutionRunStore` (ADR-013) sin cambios.
- `JUVAL_EXECUTION_STORE=supabase` — requiere `JUVAL_SUPABASE_DB_URL`
  (connection string de Postgres, vía el Connection Pooler de
  Supabase); si falta, error explícito. Usa `SupabaseExecutionRunStore`
  (ADR-017), validado con integración real contra un proyecto Supabase
  (ver `docs/architecture/SUPABASE.md` §1).
- Cualquier otro valor de `JUVAL_EXECUTION_STORE` — error explícito, no
  se interpreta como "no configurado".
- **Legacy** — `JUVAL_EXECUTION_STORE` sin definir mantiene el
  comportamiento previo: `SqliteExecutionRunStore` si
  `JUVAL_EXECUTION_DB_PATH` está definida, si no, sin store configurado
  y `persist=true` devuelve 500 explícito en vez de fallar en silencio.
- **Producción** (Railway, ADR-018) no debe depender del modo legacy —
  debe fijar `JUVAL_EXECUTION_STORE=supabase` explícitamente junto con
  `JUVAL_SUPABASE_DB_URL`.

En todos los casos, `run_pipeline()` sigue sin persistir por sí mismo
(Opción B, vigente) — la selección de store vive enteramente en
`interfaces/api/`, nunca en `application/run_pipeline.py`.

**Records (ADR-019)**: cuando `persist=true`, además del
`ExecutionRun` agregado, se persiste el snapshot de cada
`record` de `records[]`, **atómicamente en la misma transacción** —
nunca un run guardado con sus records ausentes o parciales. Ver §2c
para cómo recuperarlos después.

## 6. Almacenamiento temporal de archivos

`JUVAL_RUN_STORAGE_DIR` (opcional, default: directorio temporal del
sistema) — cada corrida usa `{JUVAL_RUN_STORAGE_DIR}/juval_runs/{execution_id}/`.
El archivo de entrada (`input.xlsx`) se elimina inmediatamente después
de procesar (nunca queda en disco más de lo que dura el request). El
archivo de salida (`output.xlsx`) permanece para que `GET .../download`
pueda servirlo en un request posterior — **no hay limpieza automática
programada todavía** (implementar eso requeriría una tarea en segundo
plano, explícitamente fuera de alcance de Fase 4A, ver §"Deuda" abajo).
Nunca se trata como almacenamiento permanente — es responsabilidad de
una fase posterior decidir una política de retención/limpieza si el
volumen de uso lo justifica.

## 7. CORS

`JUVAL_CORS_ORIGINS` (opcional, orígenes separados por coma) — vacío
por defecto (ningún origen permitido), **nunca** `"*"`.

## 8. Deuda conocida de esta implementación

1. Sin limpieza automática de `output.xlsx` — archivos de salida se
   acumulan en `JUVAL_RUN_STORAGE_DIR` indefinidamente. Aceptable para
   Fase 4A (sin evidencia de volumen real); debe resolverse antes de
   cualquier despliegue de uso sostenido.
2. `RunFailedResponse` no expone el detalle de los `ProcessingIssue`
   fatales — limitación heredada de `run_pipeline()`, no de esta capa
   (ver §1).
3. `CORS_ORIGINS`/`allow_origins` se lee una sola vez al importar
   `main.py` (arranque del proceso) — cambiar la variable de entorno
   requiere reiniciar el proceso, no es un problema para el patrón de
   despliegue habitual (variables fijas por deployment).
4. **`[HECHO VERIFICADO]` incompatibilidad real con Vercel Functions
   para el backend** (investigado 2026-08-17, no implementado, no
   desplegado): Vercel Functions solo permite escritura en `/tmp`,
   límite 500 MB, **efímero entre invocaciones** — no garantiza que
   `POST /api/v1/runs` (que escribe `output.xlsx`) y el `GET .../download`
   posterior (que lo lee) se ejecuten en la misma instancia. El diseño
   actual de dos fases (procesar ahora, descargar después) depende de
   que el archivo siga en disco entre ambos requests — una garantía que
   un servidor de proceso largo cumple y una función serverless de
   Vercel no. Además, el límite de payload de Vercel (4.5 MB) y el
   límite de duración (10s free / 60s Pro, hasta 900s con configuración
   especial) son restricciones adicionales sin relación con esta capa.
   **No se cambió la arquitectura para acomodar esto** — ver
   `docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloque 5) para las
   opciones presentadas, ninguna aplicada todavía, pendientes de tu
   aprobación.

## 9. Listados persistentes — `[IMPLEMENTADO 2026-08-17, ADR-019]`

La brecha documentada en una sesión anterior (`GET /api/v1/products` y
`GET /api/v1/runs` sin fuente de datos persistida) quedó resuelta por
ADR-019: ver §2b (`GET /api/v1/runs`) y §2c
(`GET /api/v1/runs/{execution_id}/records`). Decisiones clave, ya
tomadas y no repetidas aquí en detalle (ver ADR-019 completo):

- Modelo run-scoped, nunca un `/products` global — `record_ref` no es
  identificador global (ADR-012).
- Nueva tabla `execution_run_records` (SQLite y Supabase,
  `supabase/migrations/20260817000001_execution_run_records.sql`),
  snapshot JSON/JSONB, identidad `(execution_id, record_ref)`.
- Escritura atómica de `ExecutionRun` + records
  (`ExecutionRunStore.save_execution_run(run, records=())`, misma
  transacción).
- Lectura de records vive en un port separado y pequeño
  (`application/record_snapshot_store.py::RecordSnapshotStore`).

## 10. Record pagination (2026-08-18)

`GET /api/v1/runs/{execution_id}/records` is paginated in the persistence
adapter, not in memory after loading a whole execution. The response keeps
`records` for compatibility and adds `pagination`:

```json
{"execution_id":"...","records":[{"record_ref":"row_2:SUP-001"}],"pagination":{"limit":50,"offset":0,"total":124,"has_more":true}}
```

| Parameter | Default | Accepted values |
|---|---:|---|
| `limit` | 50 | integer 1-100 |
| `offset` | 0 | integer >= 0 |
| `search` | — | maximum 200 characters; record_ref, SKU, title, brand, ASIN |
| `decision` | — | `BUY`, `REVIEW`, `PASS` |
| `sort` | `record_ref` | `record_ref`, `sku`, `decision`, `profit`, `roi`, `margin` |
| `direction` | `asc` | `asc`, `desc` |

Offset is used instead of a cursor because persisted run snapshots are
immutable, making every page deterministic and reproducible. Each adapter
uses a static SQL allow-list for sorting; no client input is interpolated as
a SQL identifier. Invalid query values receive 422 before the store is read.

## 11. Run analytics

`GET /api/v1/runs/{execution_id}/analytics` returns one database-aggregated,
run-scoped summary: record total; decision/risk/provenance counts; existing
issue counts; and verified-only profit/ROI/margin summaries. `NOT_FOUND`,
`INVALID`, and null values never participate in numeric summaries; zero does.
`INFERRED` remains visible in provenance counts but is excluded from financial
averages rather than presented as equivalent to verified data. Unknown runs
return the existing 404 `unknown execution_id`; empty runs return zero counts
and null numeric summaries. No Decision Score, quality score, or AI output is
included.
