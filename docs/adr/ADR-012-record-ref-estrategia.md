# ADR-012: Estrategia de `record_ref` para `SourcingRecord`

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

`SourcingRecord.record_ref` es el identificador de fila que permite
rastrear cada registro procesado hasta su origen en el Excel importado,
y que viaja con cada `ProcessingIssue` generado durante import y
processing (`ARCHITECTURA.md` §14.3 dejaba abierta "la estrategia de
`record_ref` sin SKU confiable"). La estrategia ya está implementada
(`infrastructure/excel/importer.py::_build_record`) y en uso por los 165
tests actuales, pero nunca se había registrado formalmente como decisión
aprobada — esto es lo que este ADR resuelve, documentando la decisión
existente tal como está implementada, sin rediseñarla.

## Decisión

`record_ref` se construye como:

```
row_{excel_row_number}[:supplier_sku]
```

Ejemplos reales (`importer.py:388`):

```
row_2
row_3:ABC123
row_4:XYZ987
```

- `excel_row_number` es el número de fila 1-indexado de la hoja de
  origen (la fila 1 es el header; los datos empiezan en la fila 2).
- El sufijo `:{supplier_sku}` se añade únicamente si la columna
  `supplier_sku` (o su alias `sku`) trae un valor no vacío en esa fila;
  el valor se usa literal, sin normalizar ni validar formato.
- Si `supplier_sku` está vacío, `record_ref` es simplemente `row_{n}`.

### Propiedades

- **Determinístico**: para un archivo Excel y layout de columnas dados,
  la misma fila siempre produce el mismo `record_ref` en cualquier
  corrida (`run_pipeline` es una función pura de sus argumentos, ver
  `EXECUTION_MODEL.md` §4).
- **Trazable**: permite ubicar de inmediato la fila de origen de
  cualquier `ProcessingIssue` sin necesitar el archivo abierto al lado.
- **No vacío**: invariante reforzada en
  `SourcingRecord.__post_init__` (`domain/sourcing_record.py:56-57`) —
  estructuralmente imposible construir un `SourcingRecord` con
  `record_ref=""`.
- **Alcance de unicidad**: único dentro de una única ejecución de
  `import_excel` sobre un archivo dado, porque los números de fila no se
  repiten dentro de una hoja. **No es un identificador global ni
  persistente entre corridas**: reordenar filas, editar el archivo entre
  ejecuciones, o combinar registros de dos archivos distintos puede
  producir el mismo `record_ref` para productos lógicamente distintos, o
  `record_ref`s distintos para lo que un humano consideraría "el mismo"
  producto entre corridas. No sustituye a ASIN/`supplier_sku` como
  identificador de catálogo — es un identificador de *fila de
  procesamiento*, válido dentro del contexto de una importación.

### Consumo

- `SourcingRecord.record_ref` — campo obligatorio no vacío.
- `ProcessingIssue.record_ref` — cada issue generado tanto en import
  (`importer.py`) como en processing (`processing/data_quality.py`,
  `processing/pipeline.py`) referencia este mismo valor.
- `infrastructure/excel/exporter.py::HEADERS` — primera columna
  exportada (`record_ref`), siempre presente, nunca colapsada con otro
  campo.

### Por qué no es globalmente único

Depende del número de fila de la ejecución concreta de `import_excel`,
no de una clave de negocio persistente. Esto es una limitación conocida
y aceptada para el alcance de Fase 2 (sin persistencia de
`ExecutionRun` entre corridas todavía — ver `EXECUTION_MODEL.md`); no se
diseñó como clave primaria durable. Cuando exista una necesidad real de
identidad de producto persistente entre corridas (Fase 8 o posterior),
esa necesidad requerirá una estrategia adicional — no un reemplazo de
`record_ref`, que seguirá siendo válido como referencia de fila dentro
de una corrida.

### Relación con el número de fila de Excel y `supplier_sku`

El número de fila proviene directamente de `openpyxl` vía
`enumerate(rows_iter, start=2)` en `import_excel`. `supplier_sku` es un
campo opcional, de texto libre, tomado directamente del Excel de origen
sin validación de formato (a diferencia de ASIN/UPC, que sí se validan).

### Impacto en reproducibilidad

Como `run_pipeline` es una función pura de sus argumentos, dos corridas
sobre el mismo archivo (mismo hash SHA-256) producen exactamente los
mismos `record_ref` en el mismo orden — consistente con
`tests/integration/test_reproducibility.py`. Esto es reproducibilidad
*dentro de un mismo input*, no una garantía de unicidad *entre* inputs
distintos (ver limitación anterior).

## Consecuencias

- Positivas: cero configuración adicional y cero dependencia nueva (no
  UUID, no hash) para resolver trazabilidad de fila dentro de una
  corrida; suficiente para el alcance actual de issues y exportación;
  determinístico y reproducible por construcción.
- Negativas: no sirve como clave estable entre corridas o archivos
  distintos; cualquier necesidad futura de identidad de producto
  persistente (Fase 8+) requerirá una estrategia adicional explícita, no
  se resuelve extendiendo `record_ref`.
- Reversibilidad: alta — la construcción de `record_ref` vive en un
  único punto (`importer.py::_build_record`), aislado y reemplazable sin
  tocar el resto del pipeline si una fase futura necesita otra
  estrategia (ej. UUID o hash de contenido) para persistencia entre
  corridas.

## Relacionado

`docs/architecture/ARCHITECTURE.md` §14.3 (pregunta original que este
ADR cierra), `docs/architecture/EXCEL_PROCESSING.md`,
`docs/architecture/DATA_MODEL.md` §4 (invariante `record_ref` no vacío),
`docs/architecture/EXECUTION_MODEL.md` (reproducibilidad y ausencia de
persistencia entre corridas), `docs/PHASE_GATES.md` §Fase 2.
