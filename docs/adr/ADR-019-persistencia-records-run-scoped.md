# ADR-019: Persistencia run-scoped de records procesados

- Estado: Aceptada — aprobada explícitamente por el usuario 2026-08-17
  ("La necesidad de persistencia detallada YA está aprobada... Modelo
  aprobado: run-scoped").
- Fecha: 2026-08-17

## Contexto

ADR-013 introdujo `ExecutionRunStore`, deliberadamente con solo dos
métodos (`save_execution_run`/`load_execution_run`) y sin capacidad de
listado — "not needed by any caller today and would be speculative".
Esa decisión persiste `ExecutionRun` como **metadata agregada**
(contadores: `records_total`, `records_processed`,
`records_successful`, `records_with_errors`, `warnings`) — nunca las
filas individuales procesadas (`SourcingRecord`/`RecordOut`).

El contexto cambió: ahora existe un consumidor real. El frontend
(`frontend/src/pages/ProductsPage.tsx`, `RunsPage.tsx`,
`frontend/src/api/{products,runs}.ts`) ya tiene clientes preparados
para recuperar tanto el historial de runs como los resultados
detallados de un run, actualmente en modo demo explícito
(`docs/architecture/API_CONTRACT.md` §9, documentado 2026-08-17 antes
de esta ADR). Esta ADR resuelve esa brecha — **no reabre ni contradice
ADR-013**, la extiende con la capacidad que su propio texto reservaba
explícitamente para "cuando apareciera un caller real".

## Problema

Tras un `POST /api/v1/runs`, las filas procesadas (`records[]`) solo
sobreviven: (a) una vez, en el cuerpo de esa respuesta HTTP síncrona, y
(b) en `output.xlsx`, un artefacto **temporal**
(`JUVAL_RUN_STORAGE_DIR`, sin política de retención,
`API_CONTRACT.md` §6/§8.1). Ninguna de las dos es una fuente
re-consultable por HTTP después del hecho, ni sobrevive un reinicio
del proceso.

**`output.xlsx` no es persistencia** a los efectos de esta decisión:
es un artefacto de exportación de un único uso (descarga), no un
almacén consultable — no tiene esquema estable garantizado para
lectura programática (su forma la gobierna `exporter.py`, pensado para
Excel/humanos, no para round-trip de provenance), no tiene índice por
`execution_id`/`record_ref` más allá de "un archivo por
`execution_id`", y su ausencia de retención lo hace inservible como
fuente de verdad a medio plazo.

## Decisión

Persistir un **snapshot JSON-safe, run-scoped**, de cada
`SourcingRecord` procesado, junto al `ExecutionRun` agregado que ya se
persistía, en la misma transacción de base de datos.

### Identidad

`(execution_id, record_ref)` — nunca `record_ref` solo. ADR-012 ya
estableció que `record_ref` es único **solo dentro de una única
ejecución**, nunca globalmente ("Alcance de unicidad"); esta ADR no
reinterpreta esa decisión ni convierte `record_ref` en un identificador
global. Dos runs distintos pueden legítimamente compartir el mismo
`record_ref` (p. ej. la misma fila de un catálogo re-procesado) sin
colisión, porque la clave real es el par completo.

### Modelo de recurso — API

Run-scoped, no un catálogo global:

```
GET /api/v1/runs/{execution_id}/records
```

nunca `GET /api/v1/products`. Un endpoint global de "productos"
implicaría una identidad de producto cross-run que el dominio no tiene
hoy (no existe un catálogo maestro; Juval procesa lotes, no mantiene
inventario) — construirlo habría significado deformar el modelo de
dominio para que coincida con el nombre de una página del frontend
(explícitamente prohibido por esta sesión), no una decisión de datos
real.

### Snapshot — qué se persiste

La misma función de mapeo `SourcingRecord -> dict` que ya usa la
respuesta HTTP de `POST /api/v1/runs`, extraída a
`application/record_snapshot.py::record_to_snapshot` para que
`interfaces/api/service.py::record_to_json` y los adapters de
persistencia compartan una única implementación — nunca dos. El
snapshot es un dict JSON-safe con la misma forma exacta que
`RecordOut` (`interfaces/api/models.py`): cada campo sensible viaja
como `{"value": ..., "status": "VERIFIED"|"INFERRED"|"NOT_FOUND"|"INVALID"|null}`
(ADR-003/ADR-004, sin excepción), `Decimal` como string. Estructurado y
determinista — nunca `repr()`, nunca `pickle`, nunca un blob opaco.

### Esquema

Una tabla nueva, `execution_run_records`, columnas mínimas:

```sql
execution_id  TEXT/UUID NOT NULL REFERENCES execution_runs(execution_id)
ordinal       INTEGER NOT NULL   -- orden de procesamiento original, estable
record_ref    TEXT NOT NULL
snapshot      TEXT (SQLite) / JSONB (Postgres) NOT NULL
PRIMARY KEY (execution_id, record_ref)
```

No se modeló una columna por campo de `RecordOut` (serían más de 20)
— el snapshot completo es una sola columna JSON/JSONB. `ordinal` existe
para garantizar orden estable de lectura incluso si el storage
subyacente no preserva orden de inserción; `record_ref` se conserva
como columna propia (no solo dentro del JSON) porque es la mitad de la
identidad del recurso y participa en la PRIMARY KEY. La foreign key
hacia `execution_runs` hace estructuralmente imposible que existan
records "huérfanos" de un run que nunca se guardó.

### Atomicidad

**Requisito estricto**: nunca un `ExecutionRun` guardado con sus
records parcial o totalmente ausentes por un fallo a mitad de camino.

Alternativas evaluadas:

1. **Ampliar el port existente** (`ExecutionRunStore.save_execution_run`
   para aceptar `records` opcionalmente) — la escritura de ambos
   ocurre en una sola llamada, sobre la misma conexión que el adapter
   ya abre, dentro de la misma transacción.
2. **Segundo port pequeño y separado solo para escritura de records** —
   descartado: si `save_execution_run` y un hipotético
   `RecordSnapshotStore.save_records` abrieran conexiones/transacciones
   independientes, no habría forma de garantizar atomicidad real entre
   ambas escrituras sin introducir dos-fases-commit o un framework de
   Unit of Work — exactamente la complejidad que esta sesión pide
   evitar.
3. **Unit of Work genérico** — descartado explícitamente, desproporcionado
   para dos escrituras sobre la misma base de datos.

**Elegida: Opción 1.** `ExecutionRunStore.save_execution_run(run,
records=())` — parámetro opcional, retrocompatible (el CLI
`--persist-db`, que nunca pasó records, sigue funcionando sin cambios).
Cuando `records` no está vacío, el adapter concreto (que ya posee la
única conexión/transacción relevante) escribe el `ExecutionRun` y
todas las filas de `execution_run_records` dentro de la misma
transacción — `BEGIN`/`COMMIT` implícito de `sqlite3` (`with conn:`) o
transacción explícita de `psycopg`; cualquier fallo revierte ambas
escrituras.

La **lectura** de records es un concern distinto (no necesita
compartir transacción con nada) — vive en un port pequeño y separado,
`application/record_snapshot_store.py::RecordSnapshotStore`, con un
único método (`load_records`), justificado por el caller real de
`GET /api/v1/runs/{execution_id}/records`. `ExecutionRunStore` no
crece hacia un "repositorio genérico" — gana exactamente un método más
(`list_execution_runs`, ver abajo), justificado por el caller real de
`GET /api/v1/runs`.

### `GET /api/v1/runs` — listado

`ExecutionRunStore.list_execution_runs(limit=20)` — más reciente
primero (`started_at DESC`), `limit` con tope explícito (no cursor
pagination, sin necesidad demostrada de un catálogo de miles de runs
todavía). Esto **sí reabre** la parte de ADR-013 que rechazaba un
método de listado — legítimamente, porque ADR-013 lo condicionaba
explícitamente a la aparición de "any caller today", y ese caller ya
existe.

### Escalabilidad — riesgo documentado, no resuelto aquí

Un run con miles de filas produce miles de filas en
`execution_run_records`; `GET /api/v1/runs/{execution_id}/records`
devuelve la respuesta completa sin paginación. Aceptable para el MVP
actual (sin evidencia de volumen real todavía, mismo criterio que
`API_CONTRACT.md` §8.1 ya aplicó a `output.xlsx`) — paginación por
cursor queda como mejora futura si el volumen real lo demuestra, no se
diseña especulativamente ahora.

### Retención

Ninguna política de limpieza automática — mismo estado que
`execution_runs`/`output.xlsx` hoy. Los records persistidos crecen
indefinidamente con cada `persist=true`; una política de retención
queda fuera de esta ADR, a decidir cuando el volumen real lo
justifique.

## Alternativas descartadas

- **Reconstruir un `SourcingRecord` de dominio completo en la
  lectura**: descartado — el consumidor (`GET .../records`) solo
  necesita la misma forma JSON que ya expone `POST /api/v1/runs`, no
  un objeto de dominio reutilizable por el pipeline. Reconstruir
  `Product`/`CostInputs`/`RiskProfile`/etc. desde un snapshot sería
  complejidad sin consumidor real (mismo principio YAGNI que rechazó
  el listado en ADR-013 la primera vez).
- **Parsear `output.xlsx` bajo demanda en el GET** (Opción B evaluada
  en la sesión de auditoría previa): descartado — duplicaría la lógica
  de `importer.py` en la capa API, y depende de que el archivo temporal
  siga en disco (sin garantía, §6/§8.1/§8.4).
- **Endpoint `/products` global**: descartado por incompatibilidad de
  identidad con ADR-012 (ver "Modelo de recurso" arriba).

## SQLite / Supabase

Ambos backends implementan el mismo contrato ampliado
(`ExecutionRunStore` + `RecordSnapshotStore`). SQLite: tabla nueva vía
`CREATE TABLE IF NOT EXISTS` en la misma conexión que ya gestiona
`execution_runs` (mismo patrón que ADR-013), `snapshot` como `TEXT`
(`json.dumps`/`json.loads`). Supabase: migración SQL nueva versionada
(`supabase/migrations/`, nunca se modifica la ya aplicada de ADR-017),
`snapshot` como `JSONB` (tipo nativo de Postgres para el mismo dato,
sin cambiar la forma). RLS: la tabla nueva se habilita con RLS y sin
policies, exactamente la misma postura fail-closed que
`execution_runs` ya tiene (ADR-017 §4) — no se inventa una policy
nueva sin que exista todavía ningún modelo de autenticación (Clerk
sigue `PENDING`).

## Consecuencias

- Positivas: cierra la brecha documentada en `API_CONTRACT.md` §9 con
  la solución más pequeña que preserva atomicidad y provenance; una
  única función de serialización evita que la respuesta HTTP y el
  snapshot persistido diverjan con el tiempo.
- Negativas: una tabla nueva por backend, una migración nueva que
  mantener; el volumen de `execution_run_records` no tiene límite ni
  retención todavía (riesgo documentado, no bloqueante para el MVP).
- Reversibilidad: alta — es una extensión aditiva de un puerto ya
  estable (parámetro opcional, protocolo nuevo pequeño), no reemplaza
  nada de ADR-013/017.

## Relación con ADR-012, ADR-013, ADR-017

- **ADR-012**: la identidad `(execution_id, record_ref)` respeta
  exactamente su "alcance de unicidad" — no lo reinterpreta.
- **ADR-013**: extiende, no reemplaza — el listado de runs que ADR-013
  dejaba condicionado a un caller real se resuelve aquí porque ese
  caller ya existe; el resto de ADR-013 (SQLite local, sin
  auto-persistencia desde `run_pipeline()`) sigue vigente sin cambios.
- **ADR-017**: la tabla nueva de Supabase sigue el mismo patrón de
  migración versionada, RLS fail-closed y `psycopg` directo (sin SDK)
  que ADR-017 ya estableció para `execution_runs`.

## Relacionado

ADR-012, ADR-013, ADR-017,
`docs/architecture/API_CONTRACT.md` §9-§10,
`src/juval/application/record_snapshot.py`,
`src/juval/application/record_snapshot_store.py`,
`supabase/migrations/20260817000001_execution_run_records.sql`.
