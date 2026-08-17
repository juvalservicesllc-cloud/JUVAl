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

## 9. `MISSING ARCHITECTURAL CAPABILITY` — listados persistentes (2026-08-17)

El frontend (`frontend/src/api/products.ts`, `frontend/src/api/runs.ts`)
ya tiene clientes preparados para `GET /api/v1/products` y `GET
/api/v1/runs`, y ambas páginas (`ProductsPage.tsx`, `RunsPage.tsx`)
muestran explícitamente un banner "DEMO MODE" mientras tanto — Codex no
presenta esto como implementado. **Ninguno de los dos endpoints existe
en `main.py`.** Verificado, no inferido:

- **`GET /api/v1/products` — brecha arquitectónica, no solo ausencia de
  ruta.** No existe ninguna persistencia de `SourcingRecord`/`RecordOut`
  individuales, en ningún store. Lo único persistido tras un run es el
  `ExecutionRun` agregado (contadores, ADR-013/017) — nunca las filas
  procesadas. Las filas completas solo existen: (a) una vez, en el
  cuerpo de la respuesta síncrona de `POST /api/v1/runs`, y (b) en
  `output.xlsx` (almacenamiento temporal, sin política de retención,
  nunca tratado como permanente, §6). Ninguna de las dos es una fuente
  re-consultable por HTTP después de esa respuesta inicial. Además, un
  `/products` **global** (cross-run) sería incorrecto respecto al
  dominio: `record_ref` es único **solo dentro de una única ejecución**,
  nunca globalmente (ADR-012, "Por qué no es globalmente único" —
  decisión ya aceptada, no se reabre aquí). Si esta capacidad se
  aprueba, el modelo de recurso correcto es **run-scoped**:
  `GET /api/v1/runs/{execution_id}/products`, nunca `GET /api/v1/products`.
- **`GET /api/v1/runs` (listado/historial) — brecha menor, pero también
  bloqueada por diseño.** `ExecutionRunStore` (`application/execution_run_store.py`)
  expone deliberadamente solo `save_execution_run`/`load_execution_run`
  by id — su propio docstring documenta que un método de listado fue
  evaluado y rechazado como especulativo en ADR-013 ("no needed by any
  caller today"). El único caller nuevo es el frontend de demo de
  Codex, no una necesidad de negocio confirmada — añadir un método de
  listado ahora reabriría esa decisión sin la aprobación que ADR-013
  reservó explícitamente para cuando apareciera un caller real.

Ninguna de las dos capacidades se implementó en esta sesión — ver el
reporte de la sesión 2026-08-17 correspondiente para las opciones
presentadas y la decisión pendiente del usuario.
