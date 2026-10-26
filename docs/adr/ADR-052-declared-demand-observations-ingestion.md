# ADR-052 — Enmienda acotada a ADR-046: ingestión de demanda declarada (D7-B)

- Estado: **Propuesta** (2026-10-26). No implementada. ADR-046 conserva su
  estado *Accepted* y su texto; esta enmienda solo tendrá efecto si se aprueba.
- Autoridad: dirección de diseño aprobada por el usuario (2026-10-26):
  separar las observaciones declaradas de la demanda elegible para el motor.
  Pendiente: aprobación definitiva de E1–E8 (§6).
- Relacionados: ADR-003, ADR-004, ADR-011, ADR-012, ADR-019, ADR-045,
  ADR-046, ADR-047, ADR-050, ADR-051 (Propuesta), D7-D.

## 1. Contexto

- El importer no alimenta `Demand.estimated_monthly_sales`; `DEMAND_UNKNOWN`
  hace REVIEW cualquier registro importado (D7, medido 2026-10-26).
- El motor trata INFERRED como utilizable (`FieldValue.is_usable`). Escribir
  demanda declarada en `Demand.estimated_monthly_sales` podría producir BUY:
  no autorizado.
- ADR-046 ya define `DemandObservation(ESTIMATED_SALES)`: entero ≥ 0, unidad
  `units`, estado INFERRED cuando es utilizable, ventana explícita `[start, end)`
  con `end ≤ observed_at`, `observed_at ≤ retrieved_at`, `population_definition`
  no vacía (§9). Excluye expresamente la persistencia, la serialización y la
  integración con importer, Product, snapshots, API o pipeline (§3, §16, §17).
  Prohíbe presumir que "mensual" sea un número fijo de días (§8) y sustituir
  `observed_at` por `retrieved_at` (§7).

## 2. Enmienda 1 a ADR-046 (texto propuesto)

> **§20. Enmienda 1 — Observaciones de demanda declaradas en archivos (ADR-052).**
>
> **20.1 Preservación.** §1–§19 permanecen vigentes. Esta enmienda solo
> autoriza las excepciones de 20.2–20.6 y únicamente para la métrica
> `ESTIMATED_SALES` declarada en archivos de entrada. Las demás métricas, los
> conteos de competencia, la presencia de Amazon, los precios y las series
> siguen sin ingestión ni persistencia.
>
> **20.2 Ingestión autorizada.** El importer puede construir una
> `DemandObservation(metric=ESTIMATED_SALES)` por registro a partir de
> columnas explícitas del archivo (contrato D7-B). Solo es utilizable cuando el
> archivo declara todos los elementos que §9 exige; nunca se completa contexto
> con defaults, con la fecha de importación ni con el nombre de la columna.
>
> **20.3 Prohibición de promoción.** Una observación ingerida nunca escribe en
> `Product`, `Demand` ni ningún otro campo legacy, y ningún camino de código la
> proyecta a `DecisionInputs`. Que pueda usarse para decidir requiere un ADR
> propio de proyección aprobado, con una versión de política registrada
> (ADR-051 o su sucesor). Hasta entonces la demanda elegible del motor sigue
> siendo exclusivamente `Demand.estimated_monthly_sales`, que el importer no
> rellena.
>
> **20.4 Frontera con el motor.** Las observaciones viajan en un componente
> propio de `SourcingRecord` (`market_evidence`), por composición (ADR-011),
> fuera de `Product`. `processing/` no las importa ni las lee. Data quality,
> profitability, risk y decision no cambian.
>
> **20.5 Persistencia y consulta.** Se serializan como documento versionado
> `juval.adr046.demand-evidence` v1 dentro del snapshot de registro, con la
> identidad `(execution_id, record_ref)` de ADR-012, y se guardan en la misma
> escritura que el snapshot (transacción de ADR-019 y ADR-050). La API y los
> exports las exponen en solo lectura. Esta enmienda no autoriza filtrar,
> ordenar, agregar ni puntuar por demanda declarada.
>
> **20.6 Compatibilidad histórica.** Un snapshot sin el documento significa
> "captura no existente" (`NOT_CAPTURED`), distinto de "archivo sin columnas
> de demanda" (`NOT_DECLARED`) y de una observación `NOT_FOUND`. Nunca se
> reconstruye ni se rellena.
>
> **20.7 Estados.** Utilizable solo como INFERRED. NOT_FOUND e INVALID se
> representan según §6–§7. La ausencia de contexto exigido nunca produce una
> observación utilizable; se registra como diagnóstico conservando los valores
> crudos.
>
> **20.8 §16 actualizado.** De la lista de pendientes de §16, "persistencia o
> serialización" e "integración con importador, snapshots, API" quedan
> resueltos solo para 20.2–20.6. El resto de §16 sigue pendiente.

## 3. Contrato D7-B

### 3.1 Columnas (encabezado normalizado por `normalize_header`)

| Columna canónica | Alias | Tipo | Obligatoria para un valor utilizable |
|---|---|---|---|
| `demand_estimated_sales` | `estimated_monthly_sales`, `estimated_sales` | entero ≥ 0 | — (es el valor) |
| `demand_window_start` | — | fecha-hora ISO 8601 **con zona** | sí |
| `demand_window_end` | — | fecha-hora ISO 8601 con zona | sí |
| `demand_observed_at` | — | fecha-hora ISO 8601 con zona | sí |
| `demand_population` | — | texto no vacío (p. ej. "todos los vendedores del listing, amazon.com") | sí |
| `demand_method` | — | texto no vacío (herramienta o método de la estimación) | sí |

El alias `estimated_monthly_sales` se acepta como nombre de la columna valor,
pero "monthly" no define la ventana: la ventana siempre sale de
`demand_window_start` y `demand_window_end` (ADR-046 §8). Un archivo activa la
captura si contiene al menos una columna del grupo; sin ninguna, importa
exactamente como hoy.

### 3.2 Resultado por fila

| Caso | Observación | Diagnóstico |
|---|---|---|
| El archivo no tiene columnas de demanda | ninguna (`NOT_DECLARED`) | — |
| Valor válido y contexto completo y coherente | `FieldValue.inferred(int, unit="units")`; INFERRED | — |
| Celda de valor vacía, con `demand_observed_at` y ventana válidos | `FieldValue.not_found` (valor `None`, nunca 0) | — |
| Celda de valor vacía, sin contexto válido | ninguna | `DEMAND_VALUE_EMPTY` (E4) |
| Valor no entero, decimal, negativo, booleano o texto, con contexto válido | `FieldValue.invalid(raw_value=…)` | `DEMAND_VALUE_INVALID` |
| Valor no válido, sin contexto válido | ninguna | `DEMAND_VALUE_INVALID` con valor crudo |
| Contexto ausente, sin zona horaria, `start ≥ end`, `end > observed_at`, `observed_at` > momento de importación, o población o método vacíos | ninguna utilizable | `DEMAND_CONTEXT_MISSING` o `DEMAND_CONTEXT_INVALID` con los crudos (E5) |
| Fila descartada por el importer (sin `record_ref`) | ninguna | — (como en ADR-047) |

Los diagnósticos se añaden también como `ProcessingIssue` de nivel WARNING,
para que la vista previa y los issues los muestren. No afectan a la decisión.

### 3.3 Provenance de un valor

- `source` = nombre del archivo; `source_type` = `SUPPLIER_FILE`.
- `source_reference` = `row=N;column=<encabezado original>`.
- `method` = el `demand_method` declarado.
- `evidence` = "declared in file; not verified".
- `retrieved_at` = instante de importación.

El estado es INFERRED y nunca VERIFIED, lo haya declarado el proveedor o el
operador (E6). La observación incluye además `observed_at`,
`window {start, end}`, `population_definition` y `subject` (la
`Identification` del registro).

### 3.4 Snapshot

```json
"demand_evidence": {
  "format": "juval.adr046.demand-evidence",
  "version": 1,
  "observations": [{
    "metric": "ESTIMATED_SALES",
    "value": {"value": 420, "status": "INFERRED", "unit": "units", "raw_value": null, "provenance": {}},
    "observed_at": "...", "window": {"start": "...", "end": "..."}, "population_definition": "..."
  }],
  "diagnostics": [{"code": "...", "column": "...", "row": 7, "raw_value": "...", "message": "..."}]
}
```

`provenance` lleva la forma completa de la §3.3. Valores posibles de la clave:

- `demand_evidence: null` en un snapshot nuevo: el archivo no declaraba demanda
  (`NOT_DECLARED`).
- Clave ausente: snapshot anterior a ADR-052 (`NOT_CAPTURED`).

No hace falta migración: es una clave más del JSON del snapshot (E3).

### 3.5 API

`RecordOut` añade dos campos:

- `demand_evidence`: el documento, o `null`;
- `demand_evidence_state`: `DECLARED` | `NOT_DECLARED` | `NOT_CAPTURED`,
  calculado en un solo lugar.

Ningún filtro, orden ni agregado nuevo (20.5). `/analytics` no cambia.

### 3.6 Exportación

El export filtrado y el download del run añaden las columnas
`demand_declared_units`, `demand_status`, `demand_window_start`,
`demand_window_end`, `demand_observed_at`, `demand_population`, `demand_method`,
`demand_source_reference` y `demand_evidence_state`, siempre con su estado.
Un valor ausente se exporta vacío, nunca como 0.

### 3.7 Presentación (frontend-next)

- **Product Detail:** panel "Declared demand — not used for this decision" con
  valor, badge INFERRED, ventana, `observed_at`, población, método, celda de
  origen y diagnósticos. Para `NOT_DECLARED` / `NOT_CAPTURED` muestra un texto
  explícito. El panel Decision no cambia; un REVIEW pendiente de D7-D sigue
  "demand not verified".
- **Catálogo:** columna informativa "Declared demand" con valor y badge, o "—".
  Sin orden ni filtro (E7).
- **Preview:** grupo `declared_demand` con la nota "does not affect decisions",
  igual que el grupo financiero de ADR-047.

### 3.8 Compatibilidad

- **ADR-047:** las columnas `fin_*` y `demand_*` son independientes.
- **ADR-050:** la evidencia viaja dentro del snapshot y es atómica con él.
- **ADR-051:** sin efecto ahora; una futura proyección cambiaría la política
  de decisión y exigiría una versión nueva.
- **D7-D:** sin efecto, porque la demanda elegible sigue en `None`.
- **Clientes antiguos:** ignoran los campos nuevos.

## 4. Plan de implementación (solo tras aprobación)

1. `domain/sourcing_record.py`: componente `market_evidence`, una tupla de
   `DemandObservation`, por defecto `()`.
2. `infrastructure/excel/column_mapping.py`: grupo `DEMAND_EVIDENCE_COLUMN_SPECS`.
3. `infrastructure/excel/demand_capture.py` (nuevo, análogo a
   `financial_capture.py`) y el enganche en `importer.py`: construir
   observaciones y diagnósticos sin tocar `Product`.
4. `application/demand_evidence.py` (nuevo): serialización v1, lectura validada
   y `demand_evidence_state`.
5. `application/record_snapshot.py`: añadir la clave.
6. `application/import_preview.py`: grupo nuevo.
7. `interfaces/api/models.py` (`RecordOut`), `interfaces/api/service.py`
   (`record_out`) y `interfaces/api/main.py` (columnas del export);
   `infrastructure/excel/exporter.py` (download del run).
8. frontend-next: `api/types.ts`, `pages/ProductDetailPage.tsx`,
   `pages/CatalogPage.tsx` y `pages/ImportPreview.tsx`.
9. Documentación: `EXCEL_PROCESSING.md`, `DATA_DICTIONARY.md`, `API_CONTRACT.md`.

**No se tocan** `domain/product.py`, `domain/decision.py`,
`domain/market_evidence.py`, `processing/` ni ningún umbral.

## 5. Tests previstos

- **Obligatorio, decisión inalterada.** Un archivo con
  `demand_estimated_sales = 1000000`, contexto completo y los umbrales más
  permisivos sigue en **REVIEW** con `["DEMAND_UNKNOWN"]` y en
  `PENDING_DEMAND_VERIFICATION`. Decisión, razones y códigos son idénticos al
  mismo archivo sin columnas de demanda.
- **Captura:** valor válido (INFERRED, `units`, provenance completa con
  `row=…;column=…`); 0 válido (no ausencia); celda vacía con contexto
  (NOT_FOUND, valor `None`); celda vacía sin contexto (diagnóstico); texto,
  decimal, negativo y booleano (INVALID con crudo); cada fallo de contexto
  (diagnóstico, sin valor utilizable); alias `estimated_monthly_sales`;
  archivo sin columnas (import idéntico a hoy, `NOT_DECLARED`).
- **Persistencia:** ida y vuelta en SQLite y PostgreSQL desechable; snapshot
  histórico sin la clave → `NOT_CAPTURED`; atómico con el batch (ADR-050).
- **API y export:** `RecordOut` y los estados; columnas del export filtrado y
  del download, con vacío y nunca 0.
- **Preview:** columnas MAPPED en el grupo `declared_demand`; diagnósticos
  visibles.
- **Aislamiento:** test estático de que `processing/` no importa
  `market_evidence`; `Product.demand` sigue vacío tras importar.
- **frontend-next:** panel de Product Detail en sus tres estados; columna de
  Catálogo sin orden ni filtro; grupo de preview; nada de demanda declarada se
  presenta como BUY ni como VERIFIED.

## 6. Decisiones que requieren aprobación

| ID | Decisión | Propuesta |
|---|---|---|
| E1 | Aprobar la Enmienda 1 (§2) | sí |
| E2 | Nuevo componente `SourcingRecord.market_evidence` | sí, por composición |
| E3 | Guardar la evidencia en el snapshot (sin migración) o en una tabla aparte como ADR-047 | snapshot |
| E4 | Celda vacía: NOT_FOUND solo con contexto declarado; si no, diagnóstico | sí (ADR-046 §7) |
| E5 | Contexto incompleto: diagnóstico sin valor utilizable, frente a rechazar la fila | diagnóstico; la fila se importa |
| E6 | Siempre `SUPPLIER_FILE`, o una columna opcional `demand_declared_by` (supplier/operator) | siempre `SUPPLIER_FILE` en v1 |
| E7 | Sin orden, filtro ni agregados por demanda declarada en v1 | sí |
| E8 | Nombres y alias de §3.1 | sí |

## 7. Riesgos y alternativas

- **Más columnas:** exigir contexto completo hará que muchos archivos solo
  produzcan diagnósticos. Es preferible a inventar ventanas.
- **Contexto declarado no verificable:** población y método son declaraciones
  del productor del archivo; su validación estructural no las verifica.
- **Lectura como evidencia suficiente:** se mitiga con el texto "not used for
  this decision" y el badge INFERRED.
- **Alternativa A, solo diagnóstico de columnas sin persistencia:** menos
  valor y la evidencia se pierde.
- **Alternativa B, tabla aparte como ADR-047:** más separación, pero exige
  migración y lectura separada.
- **Alternativa C, aceptar solo `estimated_monthly_sales` con mes natural
  declarado:** sigue necesitando ventana y `observed_at`, sin ganancia real.

## 8. Criterios de aceptación

- Ninguna decisión, razón ni código cambia por importar demanda declarada (test
  obligatorio).
- `Product`, `Demand`, `processing/` y los umbrales sin cambios.
- Los valores utilizables son siempre INFERRED, con provenance de archivo,
  fila y columna y sus valores crudos.
- Vacío nunca es 0; INVALID conserva el crudo; el contexto nunca se inventa.
- `NOT_CAPTURED`, `NOT_DECLARED` y `NOT_FOUND` son distinguibles en el
  snapshot, la API y el export.
- SQLite y PostgreSQL son equivalentes.
- D7-D no cambia.
- ADR-046 §1–§19 se mantiene intacto.
