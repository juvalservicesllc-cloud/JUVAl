# infrastructure/excel

**IMPLEMENTED** (`column_mapping.py`, `importer.py`, `exporter.py`).
Importador y Exportador de Excel. Traduce entre archivos `.xlsx` y el
modelo interno de dominio: `import_excel()` construye un
`SourcingRecord` (`domain/sourcing_record.py`) directamente por fila,
devuelto dentro de un `ImportResult`; `export_excel()` aplana una
secuencia de `SourcingRecord` ya procesados a filas planas de `.xlsx`.
Identifica columnas por nombre de encabezado (`column_mapping.py::COLUMN_SPECS`
+ `importer.py::normalize_header`), nunca por posición. No contiene
reglas de negocio (fees, profit, decisión) — solo parseo, normalización
de unidades/formatos y mapeo de columnas.

`RawRecord`, `CatalogRecord` y `ResultModel` **no existen** en este
código — eran nombres conceptuales del diseño original de Fase 0
(`ARCHITECTURE.md` §6); no reintroducirlos como alias de `ImportResult`/
`SourcingRecord`.

Ver `docs/architecture/EXCEL_PROCESSING.md` (contrato columna por
columna) y `docs/architecture/ARCHITECTURE.md` §6 (ADR-002).
