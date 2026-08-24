# ADR-026 — CSV como formato de entrada de producción

**Estado: Aceptada**
**Fecha: 2026-08-19**
**Relacionada con:** ADR-002 (Excel como formato de intercambio), ADR-025
(ingesta multi-archivo), que dejó CSV explícitamente diferido.

## Contexto

ADR-025 aceptó la cola de hasta diez archivos pero limitó producción a XLSX
«porque ese es el contrato real del importer». La condición para levantar ese
diferimiento era explícita: que el importer y la capa de validación soportaran
CSV.

La experiencia previa aceptaba CSV y XLSX indistintamente
(`PRODUCT_BEHAVIORAL_PARITY.md` #7/#9). Mantener CSV fuera de producción
obligaba al operador a convertir manualmente cada archivo de proveedor, con
el riesgo de alterar los datos antes de que JUVAl los vea — exactamente lo
contrario de la trazabilidad que el proyecto exige.

## Decisión

**CSV es un formato de entrada de producción aceptado, al mismo nivel que
XLSX.** El conjunto de sufijos aceptados es explícito y único:
`infrastructure/excel/importer.py::SUPPORTED_INPUT_SUFFIXES = {".xlsx", ".csv"}`.

La decisión clave es que **CSV y XLSX son dos codificaciones del mismo
contrato tabular, no dos contratos**. Solo cambia el origen de las filas:

- `import_excel()` obtiene filas de `openpyxl`.
- `import_csv()` obtiene filas del módulo `csv` de la stdlib.
- `_import_rows()` — resolución de encabezados, mapeo de columnas,
  validación, provenance y construcción de `SourcingRecord` — es **idéntico
  para ambos** y no sabe de qué formato vino la fila.
- `import_file()` despacha por sufijo; cualquier otro sufijo es
  `UnsupportedInputFormat`, nunca un intento de adivinar el formato.

Consecuencias semánticas que se preservan sin excepción (ADR-003/ADR-004):

- Una celda vacía es `NOT_FOUND`, jamás `0`. Un CSV reporta la ausencia como
  `""` y un workbook como `None`; ambos se normalizan al mismo estado.
- Una fila completamente vacía se salta como blanca en ambos formatos, en vez
  de convertirse en un registro lleno de errores de campo faltante.
- Un valor presente pero no parseable sigue siendo `INVALID` con su
  `raw_value` conservado.
- `Provenance.source` es el nombre real del archivo y `source_reference` es
  `row=N`, igual que en XLSX.

Se lee con `utf-8-sig` para descartar el BOM que Excel escribe al exportar
CSV; sin eso el primer encabezado quedaría corrupto y el archivo entero
fallaría con `MISSING_REQUIRED_COLUMN`.

No se implementa sniffing de delimitador: la coma es el único delimitador
soportado hasta que exista un archivo real que requiera otro. Adivinar el
delimitador puede partir una fila en columnas equivocadas y producir números
incorrectos, que es precisamente el tipo de error silencioso que este
proyecto no acepta.

## Qué NO decide este ADR

- No cambia el modelo de dominio: CSV sigue siendo intercambio, nunca el
  modelo (ADR-002 intacto).
- No aprueba ningún otro formato (JSON, XLS, XLSM, TSV).
- No aprueba delimitadores alternativos ni codificaciones distintas de UTF-8.
- No cambia qué columnas son obligatorias ni su mapeo (`COLUMN_SPECS`).
- El límite de diez archivos por batch (ADR-025) no cambia.

## Consecuencias

`POST /api/v1/runs` y `POST /api/v1/batches` aceptan `.csv` y `.xlsx`; un
sufijo no soportado es `422` en el endpoint de un archivo y `REJECTED`
por archivo en un batch, sin abortar los hermanos válidos. La extensión
selecciona el lector, nunca se toma como prueba del contenido: el lector
valida los bytes y un archivo ilegible es error del solicitante (422), no
del servidor.

La exportación sigue siendo XLSX únicamente. No existe exportación CSV y este
ADR no la introduce.

Verificado por `tests/integration/test_csv_importer.py` (paridad registro a
registro contra el mismo fixture en ambos formatos) y por
`tests/integration/test_api.py::test_csv_upload_produces_the_same_records_as_the_workbook`.
