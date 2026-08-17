# Juval — Data Model (Fase 1-2: Amazon Sourcing Decision Engine)

Extiende el modelo conceptual de Fase 0 (`ARCHITECTURE.md`) con las
entidades concretas del dominio de sourcing. El código en `src/juval/domain/`,
`src/juval/processing/`, `src/juval/infrastructure/excel/` y
`src/juval/application/` es normativo; este documento describe la forma y
las relaciones. Actualizado en Fase 2 con `SourcingRecord` y
`ExecutionRun`, ya implementados (ver §1, §2).

## 1. Panorama general

```
SourcingRecord            (agregado raíz de una fila del pipeline)
├── product: Product
│   ├── identification: Identification   (ASIN, UPC, EAN, GTIN, SKU, ...)
│   ├── info: ProductInfo                (título, marca, categoría, ...)
│   ├── dimensions: Dimensions           (peso, alto/ancho/largo, volumen)
│   ├── demand: Demand                   (BSR, ventas estimadas, ...)
│   ├── price: Price                     (Buy Box, min FBA/FBM, precio usado)
│   └── competition: Competition         (ofertas, sellers, Buy Box share)
├── costs: CostInputs                    (COG y costos aterrizados, configurables)
├── fees: FeeInputs                      (fees de Amazon, configurables)
├── risk: RiskProfile                    (0..N RiskFlag, uno por RiskType)
├── profitability: ProfitabilityResult   (profit, ROI, margin, break-even, max COG)
├── score: DecisionScoreResult           (0-100, opcional)
├── decision: DecisionResult             (BUY / REVIEW / PASS + razones)
└── issues: list[ProcessingIssue]        (errores/warnings de este registro)
```

`SourcingRecord` es el equivalente, especializado a sourcing, del
`CatalogRecord` genérico esbozado en la Fase 0. Implementado en
`domain/sourcing_record.py` (Fase 2) como **composición pura**: cada campo
es una instancia del tipo ya definido en otro módulo (`Product`,
`CostInputs`, `FeeInputs`, `RiskProfile`, `ProfitabilityResult`,
`DecisionScoreResult`, `DecisionResult`) — `SourcingRecord` no redefine ni
duplica ninguno de sus campos (ver ADR-011). Es inmutable, como el resto
del dominio: los pasos de procesamiento devuelven un `SourcingRecord`
*nuevo* vía `.with_costs()` / `.with_risk()` / `.with_profitability()` /
`.with_score()` / `.with_decision()` / `.with_issues()`, nunca mutan uno
existente.

`costs` es `Optional[CostInputs]`, no obligatorio: si el Excel de origen
no trae un COG usable, no se fabrica un `CostInputs(cog=0)` — la ausencia
misma (`None`) es la representación honesta (ver
`infrastructure/excel/importer.py` y `EXCEL_PROCESSING.md` §4).

## 2. Entidades

### Product (`domain/product.py`)

| Entidad | Rol |
|---|---|
| `Identification` | Identificadores del producto (ASIN obligatorio; UPC/EAN/GTIN/parent_asin opcionales con provenance; SKU/supplier_sku/marketplace planos) |
| `ProductInfo` | Datos descriptivos (título, marca, categoría, ...) — todos opcionales, todos con provenance |
| `Dimensions` | Físicas, normalizadas a unidades canónicas (peso→lb, largo/ancho/alto→in, volumen→in³); la normalización se valida estructuralmente en `__post_init__` |
| `Demand` | Señales de demanda — BSR, caídas de rank, ventas/velocidad estimadas (casi siempre `INFERRED`), stock |
| `Price` | Precios observados + `selling_price_used`/`selling_price_source` acoplados (invariante: van juntos o ninguno) |
| `Competition` | Estructura competitiva del listado (ofertas, sellers, Buy Box) |

`Product` es el agregado que junta las seis; es puramente descriptivo — no
contiene costos, riesgo, ni decisión.

### Costs & Fees (`domain/costs.py`)

| Entidad | Rol |
|---|---|
| `CostInputs` | Costos aterrizados por unidad, configurables, todos ≥ 0; expone `total_landed_cost()` / `total_landed_cost_excl_cog()` |
| `FeeInputs` | Fees de venta de Amazon para un precio dado; `referral_fee_rate` se conserva por separado del monto absoluto para poder recalcular break-even |

### Risk (`domain/risk.py`)

| Entidad | Rol |
|---|---|
| `RiskFlag` | Un riesgo individual: tipo, status (PRESENT/ABSENT/UNKNOWN), severidad, verification_status, fuente, evidencia, timestamp |
| `RiskProfile` | Colección de `RiskFlag`; expone `highest_severity` y `has_unknown_risk` (usado por el Decision Engine para tratar lo desconocido de forma conservadora) |

### Profitability (`processing/profitability.py`)

| Entidad | Rol |
|---|---|
| `ProfitabilityResult` | profit/roi/margin/break_even_price (siempre) + max_cog_target_profit/max_cog_target_roi (si se piden objetivos) — todos `FieldValue[Decimal]` calculados de forma determinística |

### Decision & Score (`domain/decision.py`, `processing/decision_score.py`)

| Entidad | Rol |
|---|---|
| `Thresholds` | Umbrales configurables (target_profit, target_roi, minimum_estimated_monthly_sales, maximum_risk_severity, flags allow_*) |
| `DecisionInputs` | Lo que el Decision Engine lee: profit, roi, estimated_monthly_sales, risk_profile |
| `DecisionResult` | decision (BUY/REVIEW/PASS) + reasons (obligatorias si no es BUY) |
| `ScoreWeights` / `ScoreComponents` | Pesos configurables (suman 1) y subscores 0-100 con su propia provenance |
| `DecisionScoreResult` | Score 0-100 combinado, `NOT_FOUND` si falta o no es usable cualquier componente |

### Provenance (`domain/provenance.py`) — transversal

| Entidad | Rol |
|---|---|
| `VerificationStatus` | VERIFIED / INFERRED / NOT_FOUND / INVALID — enum único y excluyente |
| `SourceType` | USER_INPUT / SUPPLIER_FILE / OFFICIAL_API / AUTHORIZED_EXTERNAL_SOURCE / DATABASE / CALCULATED / INFERRED / AI_ANALYSIS / NOT_FOUND |
| `Provenance` | source, source_type, verification_status, retrieved_at (tz-aware), method, confidence?, evidence?, source_reference? |
| `FieldValue[T]` | value + unit? + provenance + raw_value? (para INVALID); invariantes estructurales impiden estados imposibles |
| `combine_verification_status` | Regla de propagación "el eslabón más débil" para campos calculados con múltiples inputs |

### SourcingRecord (`domain/sourcing_record.py`) — Fase 2

| Entidad | Rol |
|---|---|
| `SourcingRecord` | Agregado raíz de una fila procesable: `record_ref`, `product`, `costs?`, `fees?`, `risk`, `profitability?`, `score?`, `decision?`, `issues` |

### ExecutionRun (`domain/execution_run.py`) — Fase 2

| Entidad | Rol |
|---|---|
| `ExecutionStatus` | RUNNING / SUCCESS / PARTIAL_SUCCESS / FAILED |
| `ExecutionRun` | Registro de auditoría de una corrida: execution_id, started_at/finished_at (tz-aware), status, input_filename/input_hash (SHA-256, vía `hash_file`), application_version, y los 5 contadores de registros/warnings. In-memory/local en esta fase — sin persistencia (Supabase u otra) todavía. |

### Excel & Application (Fase 2)

| Módulo | Rol |
|---|---|
| `infrastructure/excel/column_mapping.py` | Tabla explícita header↔campo (`ColumnSpec`), ver `EXCEL_PROCESSING.md` |
| `infrastructure/excel/importer.py` | `import_excel(path, now)` → `ImportResult` (records, issues, fatal, rows_scanned, rows_skipped_blank) |
| `infrastructure/excel/exporter.py` | `export_excel(records, path)` — Result Model plano → `.xlsx` |
| `processing/pipeline.py` | `process_record`/`process_batch` — orquesta Data Quality → Profitability → Decision usando solo los motores existentes |
| `application/run_pipeline.py` | `run_pipeline(input_path, thresholds, ...)` — único módulo que depende tanto de `infrastructure/` como de `processing/`, produce `(ExecutionRun, tuple[SourcingRecord, ...])` |

## 3. Relaciones (cardinalidad)

```
SourcingRecord 1---1 Product
SourcingRecord 0---1 CostInputs              (ausente si COG no era usable en el origen)
SourcingRecord 0---1 FeeInputs               (ausente hasta tener datos de fee)
SourcingRecord 1---1 RiskProfile
RiskProfile    1---N RiskFlag                (0..14, uno por RiskType, no todos obligatorios)
SourcingRecord 0---1 ProfitabilityResult      (ausente hasta correr el motor, o si faltan costs/fees/precio)
SourcingRecord 0---1 DecisionScoreResult
SourcingRecord 0---1 DecisionResult
SourcingRecord 1---N ProcessingIssue
Product        1---1 Identification / ProductInfo / Dimensions / Demand / Price / Competition
ExecutionRun   0..1---N SourcingRecord        (asociación por corrida vía run_pipeline, no un campo de ExecutionRun)
```

## 4. Invariantes estructurales ya codificados (no solo documentados)

Estos son verificados por `__post_init__` y cubiertos por tests — no
dependen de que un desarrollador "se acuerde":

- `FieldValue`: `NOT_FOUND` ⇒ `value is None`; `VERIFIED`/`INFERRED` ⇒
  `value is not None`; `INVALID` ⇒ `raw_value` presente.
- `Provenance`: `retrieved_at` debe ser timezone-aware; `confidence` en
  `[0,1]` si se da; `source`/`method` no vacíos.
- `Dimensions`: cualquier valor usable de peso/alto/ancho/largo/volumen
  debe estar en la unidad canónica.
- `Price`: `selling_price_used` y `selling_price_source` van juntos o
  ninguno.
- `CostInputs` / `FeeInputs`: ningún componente negativo;
  `referral_fee_rate` en `[0,1)`.
- `RiskFlag`: `severity` es `FieldValue[Severity]`, provenance propia e
  independiente de `verification_status` (que describe solo presence —
  ver ADR-020). `ABSENT` ⇒ `severity.value=NONE`; `PRESENT` ⇒
  `severity.value` no `None`; `UNKNOWN` ⇒ `verification_status` en
  `{NOT_FOUND, INVALID}`.
- `DecisionResult`: `REVIEW`/`PASS` deben traer al menos una razón.
- `ScoreWeights`: los 6 pesos suman 1 (± 0.0001) y están en `[0,1]`.
- `SourcingRecord`: `record_ref` no vacío.
- `ExecutionRun`: `started_at`/`finished_at` tz-aware;
  `finished_at >= started_at`; `records_processed <= records_total`;
  `records_successful + records_with_errors <= records_processed`;
  `status=RUNNING` ⇔ `finished_at is None`.

## 5. Qué queda fuera de esta fase (deliberadamente)

- Adapters reales a fuentes externas (`infrastructure/enrichment/`) — el
  modelo está listo para recibirlos vía `FieldValue`, pero no se
  implementó ninguna integración (requisito explícito de no hacer scraping
  ni integraciones todavía). El Excel Importer de Fase 2 es hoy la única
  fuente de datos real.
- Persistencia de `ExecutionRun` (Supabase u otra) — in-memory/local por
  ahora.
- Conexión de los 12 `RiskType` restantes (solo HAZMAT y BULKY están
  cableados desde Excel — ver `EXCEL_PROCESSING.md` §8).
- `DecisionScoreResult` no se calcula todavía dentro de `process_record`
  (sigue experimental/sin aprobar — ver `DECISION_ENGINE.md` §5 y ADR-010).
- AI Analyst (diseño en `AI_ANALYST.md`, sin código).
- Autenticación, UI definitiva, dashboard, despliegue.
