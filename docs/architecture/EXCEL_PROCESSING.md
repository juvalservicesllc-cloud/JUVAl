# Juval — Excel Processing (Fase 2)

Implementación normativa: `src/juval/infrastructure/excel/`
(`column_mapping.py`, `importer.py`, `exporter.py`). Este documento es la
vista legible de esa capa — si hay discrepancia, el código gana.

## 1. Flujo

```
Excel Input (.xlsx)
   │  openpyxl.load_workbook
   ▼
Parse            (fila 1 = headers; filas 2..N = datos; celdas en bruto)
   │
   ▼
Normalize        (normalize_header: minúsculas, espacios/guiones -> "_",
   │               solo [a-z0-9_]; alias -> nombre canónico)
   ▼
Validate         (columnas requeridas ausentes -> FATAL; columnas
   │               desconocidas -> WARNING; por celda: número/booleano/
   │               ASIN/UPC inválido -> INVALID + ProcessingIssue; celda
   │               vacía -> NOT_FOUND, nunca 0 ni un valor supuesto)
   ▼
Build SourcingRecord   (uno por fila válida; una fila puede fallar por
                         completo — hoy solo si falta `marketplace` — sin
                         detener el resto del batch)
```

Salida (Fase 2, ya con el pipeline corrido):

```
SourcingRecord (procesado)
   │
   ▼
Result Model     (una fila plana por SourcingRecord — exporter.py)
   │  openpyxl.Workbook
   ▼
Excel Output (.xlsx)
```

## 2. Column Mapping (`column_mapping.py::COLUMN_SPECS`)

El orden de columnas en el archivo de entrada **nunca se asume** — cada
header se resuelve por nombre (tras normalizar) a un índice de columna, y
ese índice es el que se usa para leer cada fila de datos. Reordenar
columnas no rompe nada; un header no reconocido genera un `WARNING`
(`UNKNOWN_COLUMN`), nunca un error silencioso.

| Header canónico | Alias aceptados | Destino en el dominio | Requerido | Tipo |
|---|---|---|---|---|
| `supplier_sku` | `sku` | `product.identification.supplier_sku` | no | str |
| `marketplace` | — | `product.identification.marketplace` | **sí** | str |
| `asin` | — | `product.identification.asin` | **sí** | asin (formato validado) |
| `upc` | — | `product.identification.upc` | no | upc (checksum GS1) |
| `title` | `product_title` | `product.info.title` | no | str |
| `brand` | — | `product.info.brand` | no | str |
| `category` | — | `product.info.category` | no | str |
| `weight` | `weight_lb` | `product.dimensions.weight` | no | decimal (par con `weight_unit`) |
| `weight_unit` | — | unidad de `weight` | no* | str |
| `height` | — | `product.dimensions.height` | no | decimal (par con `dimension_unit`) |
| `width` | — | `product.dimensions.width` | no | decimal (par con `dimension_unit`) |
| `length` | — | `product.dimensions.length` | no | decimal (par con `dimension_unit`) |
| `dimension_unit` | — | unidad de height/width/length | no* | str |
| `cost` | `cog` | `costs.cog` | **sí** | decimal, ≥ 0 |
| `shipping_per_unit` | — | `costs.shipping_per_unit` | no | decimal, ≥ 0 (blanco ⇒ 0, ver §4) |
| `selling_price` | `price`, `buy_box` | `product.price.selling_price_used` + `current_buy_box` (`selling_price_source=CURRENT_BUY_BOX`) | no | decimal |
| `hazmat` | — | `risk[HAZMAT]` | no | bool |
| `bulky` | — | `risk[BULKY]` | no | bool |

`*` `weight_unit`/`dimension_unit` no son columnas "requeridas" a nivel de
header, pero si la columna de valor (`weight`/`height`/...) trae un
número en una fila y la columna de unidad está vacía **para esa fila**,
se genera un `RECORD_ERROR` (`MISSING_UNIT`) — no se asume una unidad por
defecto.

Campos requeridos son a nivel de **columna** (si el header falta del
archivo, es `FATAL` y se aborta todo el import). Una celda vacía en una
columna presente es un caso normal (`NOT_FOUND`), excepto:

- `marketplace`: una celda vacía hace que **esa fila específica** no pueda
  construirse en absoluto (no hay forma válida de tener un `Identification`
  sin marketplace) — se reporta `RECORD_ERROR` (`MISSING_REQUIRED_FIELD`)
  y la fila se omite del resultado, sin abortar el resto del batch.
- `cost`: una celda vacía o inválida hace que `SourcingRecord.costs` quede
  en `None` (no se fabrica un `CostInputs(cog=0)`) — la fila sí se
  construye, pero sin poder calcular rentabilidad.

## 3. `selling_price`: qué representa realmente

**No hay integración con Amazon en esta fase.** La columna `selling_price`
representa un precio de Buy Box observado/investigado manualmente por el
usuario y escrito en su archivo — se importa con
`source_type=SUPPLIER_FILE` y `method="manual_price_observation"`, nunca
como si viniera de una API. `selling_price_source` se fija a
`CURRENT_BUY_BOX` porque conceptualmente ese es el precio que representa,
independientemente de cómo se obtuvo. Cuando exista una fuente autorizada
real (Fase futura, sujeta a aprobación explícita — ver `DATA_SOURCES.md`),
esto pasará a `source_type=AUTHORIZED_EXTERNAL_SOURCE`.

## 4. Reglas de "no inventar datos" aplicadas literalmente

| Situación | Resultado | Por qué |
|---|---|---|
| Celda de `asin`/`upc`/`title`/... vacía | `FieldValue.not_found(...)` | dato ausente, no un valor |
| Celda con texto no parseable (`"abc"` en `weight`) | `FieldValue.invalid(...)` con `raw_value` preservado + `ProcessingIssue` | dato presente pero incorrecto, se conserva para diagnóstico |
| `cost` vacío | `SourcingRecord.costs = None` + `RECORD_ERROR` | requerido matemáticamente para poder costear; **nunca** se asume 0 |
| `shipping_per_unit` vacío | `CostInputs.shipping_per_unit = 0` | 0 es el valor documentado de "no aplica" para un costo opcional configurable (ver `domain/costs.py`), no una invención |
| `hazmat`/`bulky` vacío | `RiskFlag(status=UNKNOWN, verification_status=NOT_FOUND)` | ausencia de dato, nunca se asume `ABSENT` (sería asumir que un producto no es peligroso sin evidencia) |
| `weight` con número pero sin `weight_unit` | `FieldValue.invalid(...)` + `RECORD_ERROR` (`MISSING_UNIT`) | no se asume una unidad (ej. "seguro es lb") |

## 5. Severidad por defecto para riesgos declarados por el proveedor

Cuando `hazmat`/`bulky` = `TRUE`, el importador debe asignarle una
severidad para poder construir un `RiskFlag` válido (`RiskFlag` exige
severidad siempre). `DEFAULT_RISK_SEVERITY` en `importer.py` fija
`HAZMAT -> HIGH`, `BULKY -> MEDIUM` como clasificación **provisional**, no
aprobada por negocio — ver ADR-010 y la decisión pendiente correspondiente.

**Fallback fail-closed (ADR-015, `Estado: Aceptada`, 2026-08-17)**: un
`RiskType` sin entrada en `DEFAULT_RISK_SEVERITY` (hoy, cualquiera de
los 12 distintos de HAZMAT/BULKY, ver §8) hace que `_build_risk_flag()`
levante `KeyError` en vez de asignar una severidad asumida — nunca se
inventa un valor por defecto para un tipo de riesgo sin política
explícita. Esto es una decisión técnica (cómo debe fallar el sistema),
distinta de la aprobación de negocio de HAZMAT/BULKY en sí, que sigue
pendiente.

**Provenance de severidad separada de presence (ADR-020, `Estado:
Aceptada`, 2026-08-17)**: `RiskFlag.severity` es un
`FieldValue[Severity]` propio, no un `Severity` pelado. Que el
proveedor haya verificado `hazmat=TRUE` (presence, `VERIFIED`) no
verifica la clasificación `HIGH` de Juval (severity,
**`INFERRED`** — regla/heurística interna, ADR-010). Un `RiskFlag`
`ABSENT` sí tiene `severity.status=VERIFIED` (consecuencia lógica
cierta de una ausencia verificada, no una política). El contrato de
`RecordOut`/columnas Excel (`hazmat_severity`/`bulky_severity` como
string plano) no cambió — ver ADR-020 "Qué NO resuelve".

## 6. Excel Exporter (`exporter.py`)

Una fila por `SourcingRecord`, columnas fijas (`HEADERS`). Ningún
`FieldValue` se colapsa a una sola celda: todo campo sensible exportado
trae su columna `<campo>` y su columna `<campo>_status` por separado (ej.
`asin` / `asin_status`). Incluye como mínimo lo pedido en la Fase 2:
identificación, costos, profitability (incluye `max_cog_target_profit`/
`max_cog_target_roi`, agregados 2026-08-17 — ya se calculaban en
`profitability.py` pero no se exportaban, era deuda técnica registrada en
`PROJECT_STATUS.md`), riesgos (HazMat/Bulky por ahora), decisión,
verification status, e issues (conteo + texto). Nada del input se
descarta silenciosamente: `record_ref`, `marketplace` y `supplier_sku`
viajan siempre, e `issues` incluye tanto los generados en import como en
processing.

## 7. Fixture de pruebas

`tests/fixtures/sample_sourcing_TEST_DATA.xlsx` (generado por
`tests/fixtures/generate_sample.py`, TEST DATA explícito — SKUs/ASINs
sintéticos tipo `B0TESTAAA1` / `JUVAL TEST WIDGET ...`, nunca datos que
parezcan reales de Amazon):

| Fila | SKU | Escenario |
|---|---|---|
| 2 | SUP-001 | válido — todos los datos requeridos presentes y bien formados |
| 3 | SUP-002 | dato faltante — ASIN y precio en blanco |
| 4 | SUP-003 | dato inválido — ASIN mal formado, UPC con checksum incorrecto, peso no numérico, COG faltante, precio no numérico, HazMat con valor no reconocido |
| 5 | SUP-004 | riesgo presente — HazMat = TRUE |
| 6 | SUP-005 | fila malformada — marketplace en blanco, la fila no se construye |

También incluye una columna `Notes` (desconocida, genera `WARNING`) y
headers con mayúsculas/espacios variados para ejercitar la normalización.

## 8. Limitación explícita de esta fase

Solo `HAZMAT` y `BULKY` están conectados desde Excel hacia `RiskProfile`.
Los otros 12 tipos de `RiskType` (OVERSIZE, MELTABLE, FRAGILE,
IP_COMPLAINTS, VARIATION, SET_OR_BUNDLE, GENERIC, RESTRICTED,
APPROVAL_REQUIRED, NO_BUY_BOX, NO_FBA_FEES, ASIN_NOT_FOUND) no tienen
columna de origen todavía — quedan simplemente ausentes de `RiskProfile`
(no se fabrican como `UNKNOWN`), ya que esta fase no tiene una fuente de
datos para ellos. Se conectarán cuando exista una fuente real y aprobada.
