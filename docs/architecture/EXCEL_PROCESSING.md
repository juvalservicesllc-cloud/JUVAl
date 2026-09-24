# Juval — Excel Processing (Fase 2)

Implementación normativa: `src/juval/infrastructure/excel/`
(`column_mapping.py`, `importer.py`, `exporter.py`). Este documento es la
vista legible de esa capa — si hay discrepancia, el código gana.

## 1. Flujo

Desde ADR-026 hay **dos formatos de entrada y un solo contrato tabular**:
`.xlsx` (vía `openpyxl`) y `.csv` (vía el módulo `csv` de la stdlib).
`import_file()` despacha por sufijo; cualquier otro sufijo levanta
`UnsupportedInputFormat`, nunca se adivina el formato. Todo lo que está por
debajo del iterador de filas —resolución de encabezados, mapeo de columnas,
validación, provenance y construcción del `SourcingRecord`— es
`_import_rows()`, **idéntico para ambos**, así que un CSV y un XLSX con los
mismos encabezados producen exactamente los mismos registros.

Diferencias reales entre los dos lectores, y solo estas:

- Un workbook reporta la celda vacía como `None`; un CSV como `""`. Ambos se
  normalizan al mismo `NOT_FOUND` — nunca a `0`.
- Una fila completamente vacía se salta como blanca en ambos (la comprobación
  es agnóstica del formato), en vez de convertirse en un registro lleno de
  errores de campo faltante.
- El CSV se lee con `utf-8-sig` para descartar el BOM que Excel escribe al
  exportar; sin eso el primer encabezado quedaría corrupto.
- Coma como único delimitador. No hay sniffing: adivinar mal el delimitador
  parte la fila en columnas equivocadas y produce números incorrectos.

La **salida** sigue siendo `.xlsx` únicamente; no existe export CSV.

La exportación completa y la filtrada escriben todas las cadenas como **texto
XLSX explícito**, incluidas las que empiezan por `=` o coinciden con errores
como `#N/A`. `exporter.py::append_literal_row` conserva el contenido sin prefijos
ni fórmulas ejecutables; los números y celdas vacías mantienen sus tipos. También
se aplica a los metadatos de exportación. No altera `FieldValue`, estados de
verificación, snapshots ni cálculos. Este control protege la serialización de
salida, no certifica cualquier comportamiento de un cliente Excel externo.


```
Input (.xlsx | .csv)
   │  openpyxl.load_workbook  |  csv.reader (utf-8-sig)
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

Los decimales de entrada deben ser finitos: `NaN`, `sNaN`, `Infinity` y
`-Infinity` se tratan como números inválidos, no como valores VERIFIED. Se
conservan los mecanismos existentes de diagnóstico: `INVALID_NUMBER`/`INVALID_PRICE`
y valor original en el mensaje; para peso/dimensiones, `FieldValue.INVALID`
con `raw_value` y referencia de fila. El import continúa con las demás filas.
Si `shipping_per_unit` está presente pero es inválido o negativo, `costs=None`:
no se calcula rentabilidad a partir de un shipping ficticio de cero. El cero
por celda opcional vacía/columna ausente se mantiene según §4. No cambian las
fórmulas ni los estados de ASIN/HazMat/Bulky.

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
`HAZMAT -> HIGH`, `BULKY -> MEDIUM` como mapping interno **aprobado**
por ADR-044 D5, que sustituye la provisionalidad comercial de ADR-010.
La severidad derivada sigue INFERRED; no verifica el producto.

**Fallback fail-closed (ADR-015, `Estado: Aceptada`, 2026-08-17)**: un
`RiskType` sin entrada en `DEFAULT_RISK_SEVERITY` (hoy, cualquiera de
los 12 distintos de HAZMAT/BULKY, ver §8) hace que `_build_risk_flag()`
levante `KeyError` en vez de asignar una severidad asumida — nunca se
inventa un valor por defecto para un tipo de riesgo sin política
explícita. Esto es una decisión técnica (cómo debe fallar el sistema),
distinta de la aprobación comercial de HAZMAT/BULKY registrada en ADR-044.

**Provenance de severidad separada de presence (ADR-020, `Estado:
Aceptada`, 2026-08-17)**: `RiskFlag.severity` es un
`FieldValue[Severity]` propio, no un `Severity` pelado. Que el
proveedor haya verificado `hazmat=TRUE` (presence, `VERIFIED`) no
verifica la clasificación `HIGH` de Juval (severity,
**`INFERRED`** — política interna aprobada, ADR-044; provenance ADR-020). Un `RiskFlag`
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

## 9. Evidencia financiera nativa (ADR-047 §22 paso 3)

Columnas **opcionales y aditivas** (`column_mapping.py::FINANCIAL_EVIDENCE_COLUMN_SPECS`,
captura en `financial_capture.py`) con las que un archivo *declara* evidencia
financiera. Es la ruta NATIVA: no lee ni escribe `CostInputs`/`FeeInputs`, no
reutiliza la proyección legacy (`application/legacy_financial_projection.py`)
y no alimenta profitability, Decision Engine, scoring, persistencia ni API. Un
archivo sin ninguna columna `fin_*` se importa exactamente igual que antes y
`ImportResult.financial_captures` queda vacío.

### 9.1 Escenario (por fila)

| Header | Destino | Obligatorio para el escenario |
|---|---|---|
| `fin_scenario_id` | `FinancialScenario.scenario_id` | sí |
| `fin_scenario_version` | `scenario_version` | sí |
| `fin_currency` | `currency` (3 letras mayúsculas ASCII) | sí |
| `fin_sellable_unit` | `sellable_unit_definition` | sí |
| `fin_policy_identity` | `policy_identity` | sí |
| `fin_required_terms` | `required_terms`, nombres de `FinancialTerm` separados por `;` o `,` | sí |
| `fin_context_requirements` | `context_requirements`, separados por `;` | no |

Si falta cualquiera de los obligatorios, o uno es inválido, no se construye un
escenario: `scenario=None` y el motivo queda en `problems`. Nunca se usa la fecha
actual, la de importación, una moneda por defecto, la de otra ejecución ni la del
precio.

### 9.2 Términos (`fin_<term>_<sufijo>`, para cada uno de los 16 `FinancialTerm`)

| Sufijo | Significado |
|---|---|
| `amount` | Importe **por unidad vendible** (por lb en `shipping_per_pound`; ratio en `referral_fee_rate`) |
| `currency` | Moneda del importe; solo términos monetarios (no existe `fin_referral_fee_rate_currency`) |
| `applies` | Aplicabilidad declarada (`yes`/`no`/…, mismo parser bool) |
| `applies_method` | Si existe, el proveedor declara que *infirió* la aplicabilidad con ese método → `INFERRED` |
| `justification` | Justificación obligatoria de una aplicabilidad declarada (sí o no) |
| `effective_at` | Instante efectivo ISO 8601 **con offset**; una fecha Excel sin zona horaria se rechaza |
| `basis` | Base económica del importe (`EffectiveContext.basis_definition`) |
| `allocation` | Método de asignación hacia unidad vendible |
| `source_basis` | Origen declarado del importe: `sellable_unit` o `pack` |

Reglas (sin inferencias):

- Un término sin ninguna celda no vacía en la fila no se representa (ausencia estructural).
- Columna `amount` ausente → `amount=None` (ausencia estructural). Celda vacía en
  columna presente → `NOT_FOUND` con `source_type=SUPPLIER_FILE`, `evidence`
  "blank cell in a present supplier-file column; no value declared" y fila/columna:
  la celda se leyó y no declaró nada. No es una consulta a Amazon ni prueba de que
  el término no exista (a diferencia de `SourceType.NOT_FOUND`, "ninguna fuente
  consultada", que la convención legacy del importer sigue usando para sus columnas). Cero explícito → cero declarado `VERIFIED`, con
  su aplicabilidad como declaración aparte. Texto no numérico, `NaN`, `Infinity`,
  negativo o ratio fuera de [0, 1) → `INVALID` conservando el valor original.
- Aplicabilidad: columna `applies` ausente → el término no se captura (nunca se
  infiere de que exista un importe); celda vacía o inválida → aplicabilidad no
  resuelta (`NOT_FOUND`/`INVALID`). `no` → exclusión sin importe; una exclusión con
  importe, incluso 0, se rechaza.
- Un importe monetario sin su `currency`, o con una moneda distinta de
  `fin_currency`, no se captura; no hay conversión.
- `effective_at` o `basis` ausentes, o `effective_at` sin offset, → el término no se
  captura. `retrieved_at` es el instante de importación y nunca sustituye a `effective_at`.
- COG por unidad vendible no exige `allocation`. `source_basis=pack` exige
  `allocation`; el importer nunca divide ni inventa unidades por pack: el importe
  declarado ya es por unidad vendible. `inbound_shipping`, `shipping_per_unit`,
  `inbound_placement` y `storage` siempre exigen `allocation` (contrato de dominio).
- Provenance por observación: `source`=nombre de archivo, `SUPPLIER_FILE`,
  `method=direct_read` y `source_reference="row=N;column=<header>"`. `VERIFIED`
  significa "declarado por este archivo", no verificación independiente de Amazon.
- Las celdas numéricas XLSX son dobles binarios por formato; se leen por su
  representación mínima (igual que toda columna decimal legacy), sin aritmética.
  Para conservar exactamente escala y dígitos, declarar el importe como texto.

### 9.2b Precio de venta declarado (`fin_selling_price_*`)

El precio no es un `FinancialTerm` (ADR-047 §9). Se declara por fila con
columnas propias y se captura como `DeclaredSellingPrice(amount, context)` en
`NativeFinancialCapture.selling_price`. Nunca lee ni modifica la columna legacy
`selling_price` y nunca es una `PriceObservation` de mercado (ADR-046).

| Header | Significado |
|---|---|
| `fin_selling_price_amount` | Importe por unidad vendible |
| `fin_selling_price_currency` | Moneda (3 letras mayúsculas); obligatoria para un importe utilizable |
| `fin_selling_price_effective_at` | Instante efectivo ISO 8601 con offset |
| `fin_selling_price_basis` | Base del precio (qué representa) |
| `fin_selling_price_method` | Si existe, el proveedor declara que lo *infirió* con ese método → `INFERRED` |

Si ninguna celda está informada, no hay precio (ausencia estructural). Si falta la
columna de importe, la moneda (para un importe utilizable), `effective_at` o
`basis`, o si la moneda está mal formada (`usd`, `USD/lb`, `ratio`, `$`), no se
captura el precio y el motivo queda en `problems`. Una celda de importe vacía da
NOT_FOUND (`SUPPLIER_FILE`, evidencia de celda en blanco). Un valor no numérico,
NaN, Infinity o negativo da INVALID con el valor original. Un `0` es un cero
declarado. Una moneda distinta de la del escenario no se rechaza en la captura:
el resolvedor la informa como `CURRENCY_INCOMPATIBLE`, sin conversión.

### 9.2c Peso financiero nativo (`fin_weight_*`)

| Header | Significado |
|---|---|
| `fin_weight_amount` | Peso de la unidad vendible, tal como se declara |
| `fin_weight_unit` | Unidad declarada; nunca se asume ni se convierte |
| `fin_weight_method` | Si existe, el proveedor declara que lo *infirió* con ese método → `INFERRED` |

- Se captura en `NativeFinancialCapture.weight` como `FieldValue` de
  `SUPPLIER_FILE`, con fila y columna.
- Estados:
  - si ninguna celda está informada, no hay peso (ausencia estructural);
  - un importe vacío da NOT_FOUND;
  - un valor no numérico, NaN, Infinity o negativo da INVALID con el valor
    original;
  - un `0` es un cero declarado.
- Una unidad vacía deja `unit=None` y emite `UNIT_UNDECLARED`.
- Nunca se lee la columna legacy `weight`/`weight_unit`, y nada del peso nativo
  llega a los registros comerciales.
- Es el único origen del input `WEIGHT` del resolvedor, que solo lo usa si
  `SHIPPING_PER_POUND` aplica con una tarifa utilizable y la unidad es
  exactamente `lb`. `kg` queda bloqueado como `UNIT_INCOMPATIBLE`, sin conversión.

### 9.2d Diagnósticos estructurados

Cada problema se emite donde se detecta como
`CaptureDiagnostic(subject, code, message, row, column?, raw_value?)`, con `code`
de `CaptureCode`.
- `column` y `raw_value` solo existen cuando una celda concreta causó el problema;
  nunca se extraen del texto.
- Un rechazo del contrato de dominio usa `CONTRACT_REJECTED` sin columna.
- `NativeFinancialCapture.problems` conserva el mismo contenido como texto legacy
  `"<subject>: <message>"`.

### 9.3 Entrega del resultado

`ImportResult.financial_captures` tiene un `NativeFinancialCapture` por registro
construido, en el mismo orden que `records`, solo si el archivo contiene al menos
una columna `fin_*`. Contiene `record_ref`, `scenario`, los `FinancialTermEvidence`
capturados y `problems` (motivos deterministas de lo no capturado).
`capture.bind(execution_id)` devuelve el `FinancialEvidenceSet` del registro; el
`execution_id` lo aporta quien llama, como `now`. Los problemas no se añaden a
`issues` ni a los registros, para no cambiar conteos, estados ni decisiones legacy.
`run_pipeline` no cambia. `application/run_pipeline.py::run_pipeline_with_financial_evidence`
comparte su misma ruta de ejecución y devuelve además, por registro procesado,
un `RecordFinancialEvidence` (`execution_id`, `record_ref`, `capture`, `evidence`
= `bind(execution_id)` o `None` sin escenario completo, `problems`). La
vinculación es por `record_ref` (incluye el número de fila), nunca por posición
ni por ASIN/UPC; cualquier desajuste de cardinalidad u orden entre registros
importados, capturas y registros procesados falla explícitamente. La evidencia
no alimenta cálculos, riesgo, score ni decisiones, y no se persiste ni se expone
por API. `application/native_financial_resolution.py::resolve_record_financial_dependencies`
entrega al resolvedor de ADR-047 §16 esa evidencia junto con el precio nativo
declarado. Nunca recurre al precio legacy ni a `FeeInputs`.
