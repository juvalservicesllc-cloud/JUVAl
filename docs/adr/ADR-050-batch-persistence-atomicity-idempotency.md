# ADR-050 — Persistencia atómica e idempotente de batches

- Estado: **Parcialmente aceptada** (2026-10-16), por decisión explícita del
  usuario:
  - Aceptado: persistencia todo o nada de un batch, cuya transacción abarca
    batch, runs hijos, records, documentos financieros, diagnósticos y
    relación batch–runs (D2); sin borrados compensatorios (alternativa D
    rechazada); un archivo `REJECTED` no invalida el batch; ADR-025 se
    conserva (un run por archivo procesado, batch como agrupador). La
    idempotencia (D5) se hará en una unidad posterior.
  - Sigue **Propuesta**: D1 aplicado al endpoint, D3, D4, el detalle de D5
    (cabecera, tabla, retención) y el texto de D6. Hasta su aprobación, el
    contrato HTTP no cambia.
- Estado de implementación: unidad 1 IMPLEMENTED (§10); el endpoint no la usa.
- Fecha: 2026-10-16.
- Autoridad solicitada para lo pendiente: decisión explícita del usuario sobre
  D1 (endpoint), D3, D4, D5 y D6.
- Relacionados: ADR-025 (batches, Aceptada para Wave A; deja abierto el
  aislamiento de fallos de persistencia/exportación por archivo), ADR-047
  (evidencia financiera, opt-in en batches desde 2026-10-16), ADR-013/017/019
  (persistencia de runs y records), ADR-026 (CSV).
- Numeración: ADR-048 no existe en este repositorio y ADR-049 identifica el
  aislamiento del agente fuera de él; se usa 050 para no colisionar.

## 1. Contexto y problema

`POST /api/v1/batches` procesa hasta diez archivos de forma secuencial. Con
`persist=true`, cada hijo se guarda en su propia transacción **al terminar de
procesarse**, se exporta a XLSX y, solo al final, se guarda el batch
(`batches` + `batch_files`). Con el opt-in de ADR-047, la transacción de cada
hijo incluye sus documentos financieros y diagnósticos.

Comportamiento actual medido en
`tests/integration/test_api_batch_persistence_failures.py` (SQLite temporal,
datos sintéticos):

| Escenario | Resultado actual |
|---|---|
| Todos los archivos correctos | 200; batch y todos los hijos guardados y enlazados |
| Archivo rechazado | 200; `REJECTED` sin run, guardado como resultado del batch |
| Fallo al guardar el 2.º archivo | 500 genérico; el 1.º queda guardado con sus documentos, el 2.º no guarda nada, no hay fila de batch; `GET /runs/{1.º}/batch` da 404, como si se hubiera enviado solo; la respuesta no menciona el `execution_id` guardado |
| Reintento tras ese fallo | crea runs nuevos: el 1.º archivo queda guardado dos veces (mismo `input_hash`) |
| Fallo global de base de datos | 500 genérico; nada guardado; la respuesta no dice que reintentar sea seguro |
| Fallo de exportación XLSX tras guardar un hijo | 500; el hijo queda guardado y sin batch |

Lo que no ocurre: documentos financieros huérfanos (la transacción por hijo los
guarda o descarta con su run) ni mezcla entre `execution_id`.

El problema no es la transacción por hijo, sino que el **conjunto** no es
atómico ni identificable: un fallo deja hijos sin batch, el cliente no puede
saber qué quedó guardado y un reintento duplica lo que sí se guardó.

## 2. Requisitos

1. Una `ExecutionRun` por archivo procesado; el batch solo agrupa (ADR-025).
2. El fallo de importación de un archivo (`FAILED`/`REJECTED`) no invalida a
   sus hermanos (ADR-025, sin cambios).
3. Ningún estado parcial tras un fallo de persistencia: o se guarda el batch
   completo con todos sus hijos, documentos y diagnósticos, o no se guarda nada.
4. El cliente sabe, por la respuesta, si se guardó algo y si reintentar es seguro.
5. Un reintento de la misma petición no duplica datos cuando el cliente lo pide.
6. Sin documentos financieros huérfanos ni mezcla entre ejecuciones; provenance,
   INVALID y NOT_FOUND intactos (ADR-003/004/047).
7. `POST /api/v1/runs` y la respuesta 200 de batches no cambian.

## 3. Alternativas

**A. Mantener el comportamiento actual.** Sin coste. Rechazada: deja hijos sin
batch, oculta qué se guardó y hace ambiguo el reintento (§1).

**B. Persistencia atómica del batch.** Procesar todos los archivos sin escribir
y guardar después, en **una** transacción, todos los runs, snapshots,
documentos, diagnósticos, `batches` y `batch_files`. Un fallo de escritura no
deja nada. No requiere estados nuevos ni cambios de `CHECK`/FK. La separación de
importación por archivo se mantiene: un archivo ilegible sigue siendo un hijo
`FAILED` guardado dentro del mismo batch.

**C. Aislamiento por archivo con estado nuevo (`PERSISTENCE_FAILED`).** Guardar
primero el batch y después cada hijo en su transacción, marcando los que fallen.
Exige: ampliar el `CHECK` de `batch_files.status` y del dominio; guardar el
`execution_id` intentado de un run inexistente, incompatible con la FK de
`batch_files.execution_id` (columna nueva o `null`); actualizar el batch en
sitio, contrario a "no in-place mutation" de ADR-025; y decidir cómo se
reintenta un único archivo de un batch ya guardado. Además, los fallos de
escritura realmente aislables a un archivo son raros: con documentos validados
antes de escribir, un fallo de un hijo suele ser de infraestructura y afecta
también a los demás. Rechazada por ahora: más esquema y semántica para un caso
que B cubre sin estado parcial.

**D. Compensación (borrar los hijos ya guardados si falla otro).** Rechazada:
borra registros de auditoría y una caída entre la escritura y la compensación
deja el mismo estado parcial que A.

**E. Clave de idempotencia.** Ortogonal a B/C: sin ella, una respuesta perdida
*después* del commit sigue provocando un duplicado al reintentar, incluso con B.

## 4. Decisión propuesta: B + E

- **D1 — Procesar y luego guardar.** Importación, pipeline, documentos y
  diagnósticos de todos los archivos se construyen en memoria, sin escrituras;
  cada archivo conserva su resultado (`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`,
  `REJECTED`) como hoy.
- **D2 — Una transacción por batch.** Nuevo método aditivo del store,
  `save_batch_with_runs(batch, children)`, donde cada hijo aporta su run,
  snapshots, documentos y diagnósticos. Se implementa en SQLite y PostgreSQL
  reutilizando las sentencias e helpers de fila existentes (inserts de run, de
  `execution_run_records` y de batch; `_financial_row`, `_diagnostics_row`) y
  las validaciones previas de
  `save_run_with_financial_records`. `save_execution_run` y `save_batch` no
  cambian; `POST /api/v1/runs` tampoco.
- **D3 — Exportar después del commit.** La exportación XLSX por hijo ocurre tras
  el commit. Su fallo no deshace datos ya guardados: el archivo se reporta con un
  aviso `"download unavailable: export failed"` y la respuesta sigue siendo 200.
- **D4 — Semántica HTTP.**
  - 200: batch guardado. Cuerpo actual sin cambios (`persisted: true`).
  - 422: validación de la petición, como hoy.
  - 503: fallo operacional de la base de datos (conexión, bloqueo, tabla
    ausente). Cuerpo
    `{"detail": "batch not stored; nothing from this request was persisted", "persisted": false, "retry_safe": true}`.
  - 500: fallo de integridad o de programación (por ejemplo, una restricción
    violada por datos que debían haberse validado). Mismo cuerpo con
    `"retry_safe": false`: no queda nada guardado, pero repetir la petición
    fallaría igual.
  - En ambos, si el store puede atribuir el fallo a un archivo, se añade
    `"failed_ordinal"` como diagnóstico. Nunca se devuelven `execution_id` de
    algo que no se guardó.
- **D5 — Idempotencia opcional.** Cabecera `Idempotency-Key` (texto opaco del
  cliente, p. ej. un UUID). Se guarda en una tabla nueva
  `batch_submissions(idempotency_key PK, request_digest, batch_id FK, created_at)`
  **en la misma transacción** que el batch. `request_digest` = SHA-256 de los
  archivos en orden (nombre y SHA-256 del contenido), `thresholds`, `fees`,
  `persist` y las opciones financieras.
  - La misma clave con el mismo digest devuelve 200 con el batch guardado (en
    el formato de `GET /api/v1/batches/{id}`) y la cabecera
    `Idempotent-Replay: true`, sin reprocesar.
  - La misma clave con otro digest devuelve 409.
  - Dos peticiones concurrentes con la misma clave: la segunda choca con la PK
    al hacer commit y recibe 409; ninguna deja estado parcial.
  - Sin cabecera, el comportamiento es el de hoy: cada POST es un batch nuevo.
    Reprocesar el mismo archivo es legítimo, así que no se deduplica por
    `input_hash`.
- **D6 — Enmienda de ADR-025.** "Each child is persisted independently" pasa a
  ser "cada hijo conserva su propia `ExecutionRun`; el batch y sus hijos se
  guardan juntos o no se guardan". La independencia ante fallos de importación
  no cambia. Esto también cierra el pendiente de aislamiento de
  persistencia/exportación de ADR-025.

## 5. Los cuatro casos con la decisión propuesta

| Caso | Respuesta | Estado guardado |
|---|---|---|
| Archivo procesado y guardado | 200; archivo `SUCCESS`/`PARTIAL_SUCCESS` con `execution_id` | run, snapshots, documentos, diagnósticos y fila de batch |
| Archivo rechazado antes de guardar | 200; archivo `REJECTED`, sin `execution_id` | fila `batch_files` sin run |
| Archivo cuyo guardado falló | 500 o 503 según D4, con `failed_ordinal` si se conoce | **nada** de la petición |
| Fallo global de infraestructura | 503, `retry_safe: true` | **nada** de la petición |

La identidad y el resultado de cada archivo se conservan: en la respuesta 200 y
en `batch_files` cuando el batch se guarda; en la respuesta de error, solo como
`failed_ordinal`, porque no se guardó ningún run al que referirse.

## 6. Consecuencias

- Se eliminan los hijos sin batch y los duplicados por reintento con clave.
- No hay documentos financieros huérfanos: viven en la transacción del batch.
- Memoria: hasta diez archivos procesados se mantienen en memoria antes del
  commit. El límite efectivo depende de `JUVAL_MAX_UPLOAD_BYTES`, cuyo valor de
  negocio sigue PENDING.
- La transacción crece con el batch (diez runs con sus records); es aceptable en
  SQLite y PostgreSQL para el volumen actual, pero conviene medirlo antes de
  activar en producción.
- La respuesta de error cambia de 500 genérico a 500/503 con cuerpo. Es aditivo
  para clientes que tratan cualquier no-200 como fallo; el frontend no se toca
  en esta decisión.
- La exportación deja de convertir un batch guardado en 500.

## 7. Riesgos

- Clasificar mal un error como operacional (503, `retry_safe`) haría reintentar
  algo que fallará igual; la clasificación se limita a tipos de error
  explícitos del driver y, ante duda, se usa 500 con `retry_safe: false`.
- Las claves de idempotencia necesitan política de retención; sin ella, la
  tabla crece sin límite. Retención: **PENDING**.
- Un replay devuelve el batch guardado, no la respuesta original byte a byte
  (no incluye `records`; batches tampoco los incluye hoy).

## 8. Plan de migración (tras aprobación)

1. Método `save_batch_with_runs` en SQLite y PostgreSQL, con tests de
   atomicidad (fallo en cualquier hijo o en `batch_files` ⇒ 0 filas).
2. Endpoint: procesar-luego-guardar, exportar tras el commit y D4. Los tests de
   caracterización `CURRENT` pasan a afirmar el contrato nuevo.
3. Solo si se aprueba D5: migración aditiva
   `supabase/migrations/<fecha>_batch_submissions.sql` con su `.down.sql`, RLS
   habilitada sin políticas (postura de Gate B1) y creación en SQLite con
   `CREATE TABLE IF NOT EXISTS`. Verificación en PostgreSQL desechable;
   aplicarla a Supabase es un paso humano.
4. Actualizar `API_CONTRACT.md` §12, ADR-025 (D6) y ADR-047.

## 9. Decisiones que requieren aprobación

- D1–D3: cambio de la semántica transaccional de batches (enmienda ADR-025).
- D4: códigos y cuerpo de error nuevos.
- D5: cabecera, tabla nueva y su retención.
- D6: texto de la enmienda.

Se pueden aprobar D1–D4 + D6 sin D5; en ese caso el reintento tras una
respuesta perdida seguirá pudiendo duplicar.

## 10. Implementación — unidad 1 (2026-10-16)

- Puerto: `application/batch_store.py::AtomicBatchStore.save_batch_with_runs`
  y `RunWrite` (los mismos argumentos que `save_execution_run`).
- Aplicación: `application/batch_persistence.py::save_batch_with_runs(store,
  batch, children)`. Antes de escribir comprueba que cada archivo con
  `execution_id` tiene exactamente un hijo, que cada hijo está nombrado por
  exactamente un archivo y que un `REJECTED` no nombra ninguno
  (`BatchIntegrityError`). Documentos y diagnósticos se validan y serializan con
  `financial_persistence.financial_payloads`, extraído sin cambios de
  `save_run_with_financial_records`.
- Stores: SQLite y PostgreSQL escriben todos los runs (con records, documentos y
  diagnósticos) y el batch en una sola transacción con las mismas funciones que
  `save_execution_run` y `save_batch`, ahora extraídas a `_write_run` y
  `_write_batch` sobre la conexión del llamador. Sin esquema, estados ni
  restricciones nuevos.
- No conectado al endpoint: `POST /api/v1/batches` sigue guardando hijo por hijo,
  y los tests de caracterización de `test_api_batch_persistence_failures.py`
  siguen afirmando el comportamiento actual.
- Verificado con los mismos 7 escenarios en SQLite
  (`tests/integration/test_batch_atomic_persistence.py`) y en PostgreSQL 16
  desechable (`test_postgres_financial_persistence.py`): todo guardado y
  enlazado; `REJECTED` sin run; fallo real de PK en el 2.º hijo; fallo en un
  documento financiero; fallo real de PK en el batch tras escribir todos los
  hijos; hijo con `execution_id` ya existente (no se sobrescribe); mismo
  `record_ref` en dos archivos como documentos separados. En los fallos no queda
  ninguna fila nueva en ninguna de las seis tablas. Validación previa probada
  sin escrituras. Partir la transacción por hijo hace fallar 4 escenarios en
  cada motor.
