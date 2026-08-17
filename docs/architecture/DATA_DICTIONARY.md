# Juval — Data Dictionary (Fase 1)

Fuente de verdad canónica de campos. El código en `src/juval/domain/` es la
implementación normativa; este documento es la vista legible/consultable.
Si hay discrepancia entre este documento y el código, **el código gana** —
actualizar este documento en el mismo cambio que se toque el modelo.

Columnas: `field_name` (nombre en código) · `display_name` · `description`
· `data_type` · `unit` · `required` (¿el registro siempre lleva este campo,
aunque sea `NOT_FOUND`?) · `nullable` (¿puede el valor ser `None` vía
`NOT_FOUND`/`INVALID`?) · `source` (típico, no exhaustivo) · `source_type`
· `calculation` (fórmula si es un campo calculado) · `verification_status`
(estados posibles realistas para ese campo) · `freshness` (expectativa de
antigüedad máxima razonable) · `confidence` (¿aplica score de confianza?)
· `notes`.

## Identification (`domain/product.py::Identification`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| asin | ASIN | Identificador Amazon del listado | FieldValue[str] | — | sí | sí | supplier_file, official_api | SUPPLIER_FILE, OFFICIAL_API | — | VERIFIED/NOT_FOUND/INVALID | baja rotación | no | formato validado en `domain/identifiers.py::is_valid_asin` |
| upc | UPC | Código de barras UPC-A | FieldValue[str] | — | no | sí | supplier_file | SUPPLIER_FILE, USER_INPUT | — | VERIFIED/NOT_FOUND/INVALID | baja rotación | no | checksum GS1 |
| ean | EAN | Código de barras EAN-8/13 | FieldValue[str] | — | no | sí | supplier_file | SUPPLIER_FILE, USER_INPUT | — | VERIFIED/NOT_FOUND/INVALID | baja rotación | no | checksum GS1 |
| gtin | GTIN | Identificador GTIN genérico | FieldValue[str] | — | no | sí | supplier_file | SUPPLIER_FILE, USER_INPUT | — | VERIFIED/NOT_FOUND/INVALID | baja rotación | no | checksum GS1, longitud 8/12/13/14 |
| sku | SKU | SKU interno del usuario | str | — | no | sí | user_input | USER_INPUT | — | n/a | n/a | no | identificador plano, no requiere provenance completa |
| supplier_sku | Supplier SKU | SKU del proveedor | str | — | no | sí | supplier_file | SUPPLIER_FILE | — | n/a | n/a | no | idem |
| parent_asin | Parent ASIN | ASIN del producto padre (variaciones) | FieldValue[str] | — | no | sí | official_api | OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | relevante para `RiskType.VARIATION` |
| marketplace | Marketplace | Marketplace de Amazon (ej. `US`, `MX`) | str | — | sí | no | user_input | USER_INPUT | — | n/a | n/a | no | fija el contexto de todos los demás campos |

## Product Info (`domain/product.py::ProductInfo`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| title | Título | Título del listado | FieldValue[str] | — | no | sí | official_api, supplier_file | OFFICIAL_API, SUPPLIER_FILE | — | VERIFIED/NOT_FOUND | media | no | |
| brand | Marca | Marca declarada | FieldValue[str] | — | no | sí | official_api, supplier_file | OFFICIAL_API, SUPPLIER_FILE | — | VERIFIED/NOT_FOUND | media | no | |
| category | Categoría | Categoría Amazon | FieldValue[str] | — | no | sí | official_api | OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | insumo de fee rate (externo al sistema) |
| model | Modelo | Modelo del fabricante | FieldValue[str] | — | no | sí | supplier_file, official_api | SUPPLIER_FILE, OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | |
| manufacturer | Fabricante | Fabricante | FieldValue[str] | — | no | sí | supplier_file, official_api | SUPPLIER_FILE, OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | |
| part_number | Part Number | Número de parte del fabricante | FieldValue[str] | — | no | sí | supplier_file | SUPPLIER_FILE | — | VERIFIED/NOT_FOUND | media | no | |
| description | Descripción | Descripción larga | FieldValue[str] | — | no | sí | official_api | OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | |
| features | Features | Bullet points del listado | FieldValue[tuple[str,...]] | — | no | sí | official_api | OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | |
| image | Imagen | URL de imagen principal | FieldValue[str] | — | no | sí | official_api | OFFICIAL_API | — | VERIFIED/NOT_FOUND | media | no | nunca se descarga automáticamente sin aprobación |
| package_quantity | Cantidad por paquete | Unidades por empaque | FieldValue[int] | unidades | no | sí | supplier_file, official_api | SUPPLIER_FILE, OFFICIAL_API | — | VERIFIED/INFERRED/NOT_FOUND | media | opcional | afecta cálculo de costo por unidad |

## Dimensions (`domain/product.py::Dimensions`) — unidades normalizadas

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| height | Altura | Altura del paquete | FieldValue[Decimal] | in (canónico) | no | sí | official_api, supplier_file | OFFICIAL_API, SUPPLIER_FILE | — | VERIFIED/INFERRED/NOT_FOUND/INVALID | baja rotación | no | normalización en `domain/units.py::to_inches` antes de construir el FieldValue |
| width | Ancho | Ancho del paquete | FieldValue[Decimal] | in (canónico) | no | sí | official_api, supplier_file | OFFICIAL_API, SUPPLIER_FILE | — | VERIFIED/INFERRED/NOT_FOUND/INVALID | baja rotación | no | idem |
| length | Largo | Largo del paquete | FieldValue[Decimal] | in (canónico) | no | sí | official_api, supplier_file | OFFICIAL_API, SUPPLIER_FILE | — | VERIFIED/INFERRED/NOT_FOUND/INVALID | baja rotación | no | idem |
| weight | Peso | Peso del paquete | FieldValue[Decimal] | lb (canónico) | sí | sí | official_api, supplier_file | OFFICIAL_API, SUPPLIER_FILE | — | VERIFIED/INFERRED/NOT_FOUND/INVALID | baja rotación | no | campo especialmente sensible; normalización en `domain/units.py::to_pounds` |
| volume | Volumen | Volumen del paquete | FieldValue[Decimal] | in³ (canónico) | no | sí | calculated | CALCULATED | `length_in * width_in * height_in` | VERIFIED/INFERRED/NOT_FOUND | baja rotación | no | `domain/units.py::cubic_inches` |
| size_info | Info de tamaño | Texto libre de tamaño (talla/variante) | FieldValue[str] | — | no | sí | supplier_file | SUPPLIER_FILE | — | VERIFIED/NOT_FOUND | media | no | |
| size_type | Tipo de tamaño | STANDARD / OVERSIZE / UNKNOWN | FieldValue[SizeType] | — | no | sí | official_api, calculated | OFFICIAL_API, CALCULATED | regla de tamaño Amazon (externa, no hardcodeada) | VERIFIED/INFERRED/NOT_FOUND | media | no | insumo de `RiskType.OVERSIZE` |

## Demand (`domain/product.py::Demand`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current_bsr | BSR actual | Best Sellers Rank actual | FieldValue[int] | rango | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta (cambia a diario) | no | |
| average_bsr_30d/90d/180d | BSR promedio 30/90/180d | Promedio de BSR en la ventana | FieldValue[int] | rango | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | promedio provisto por la fuente | VERIFIED/INFERRED/NOT_FOUND | alta | sí (recomendado) | 3 campos, mismo patrón |
| sales_rank_drops_30d/90d/180d | Caídas de rank 30/90/180d | Nº de caídas de BSR (proxy de ventas) en la ventana | FieldValue[int] | conteo | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | 3 campos, mismo patrón |
| estimated_monthly_sales | Ventas mensuales estimadas | Estimación de unidades vendidas/mes | FieldValue[int] | unidades/mes | no | sí | authorized_external_source, calculated | AUTHORIZED_EXTERNAL_SOURCE, INFERRED | modelo de estimación de la fuente (externo) | **casi siempre INFERRED**, nunca VERIFIED salvo garantía explícita de la fuente | alta | sí (obligatorio si INFERRED) | ver §6 Phase 1: "no asumir que sales estimates son exactos" |
| sales_velocity | Velocidad de venta | Tasa de venta reciente | FieldValue[Decimal] | unidades/día | no | sí | authorized_external_source, calculated | AUTHORIZED_EXTERNAL_SOURCE, INFERRED | — | INFERRED en la práctica | alta | sí | idem |
| stock_status | Estado de stock | IN_STOCK / LOW_STOCK / OUT_OF_STOCK / UNKNOWN | FieldValue[StockStatus] | — | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |

## Price (`domain/product.py::Price`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current_buy_box | Buy Box actual | Precio actual del Buy Box | FieldValue[Decimal] | moneda (marketplace) | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| average_buy_box_30d/90d/180d | Buy Box promedio 30/90/180d | Promedio del Buy Box en la ventana | FieldValue[Decimal] | moneda | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | promedio de la fuente | VERIFIED/INFERRED/NOT_FOUND | alta | no | 3 campos |
| min_fba_price | Precio mínimo FBA | Precio FBA más bajo entre ofertas | FieldValue[Decimal] | moneda | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| min_fbm_price | Precio mínimo FBM | Precio FBM más bajo entre ofertas | FieldValue[Decimal] | moneda | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| price_dynamics.trend | Tendencia de precio | Señal cualitativa de estabilidad | FieldValue[str] | — | no | sí | calculated, ai_analysis | CALCULATED, AI_ANALYSIS | regla o resumen de la IA | INFERRED (nunca VERIFIED) | alta | sí | ver ADR-006/ADR-008: nunca es input numérico de Profitability |
| selling_price_used | Precio usado para el cálculo | Precio efectivamente usado por Profitability Engine | FieldValue[Decimal] | moneda | sí (si hay cálculo de rentabilidad) | sí | calculated (copia de uno de los precios de arriba) | igual al campo copiado | selección explícita, no un default | igual al campo copiado | igual | no | ver `selling_price_source` — invariante validado en `Price.__post_init__` |
| selling_price_source | Fuente del precio usado | Enum: qué precio se usó | SellingPriceSource | — | sí | no (default NOT_FOUND) | n/a | n/a | — | n/a | n/a | no | debe ser consistente con `selling_price_used` (ambos o ninguno) |

## Competition (`domain/product.py::Competition`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| total_offers | Ofertas totales | Nº total de ofertas activas | FieldValue[int] | conteo | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| fba_sellers | Sellers FBA | Nº de sellers FBA | FieldValue[int] | conteo | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| fbm_sellers | Sellers FBM | Nº de sellers FBM | FieldValue[int] | conteo | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| buy_box_eligible_fba | Elegibles Buy Box FBA | Nº de sellers FBA elegibles a Buy Box | FieldValue[int] | conteo | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | debe ser ≤ total_offers, validado en data_quality |
| buy_box_eligible_fbm | Elegibles Buy Box FBM | Nº de sellers FBM elegibles a Buy Box | FieldValue[int] | conteo | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | idem |
| amazon_in_buy_box | Amazon en Buy Box | ¿Amazon compite en el Buy Box? | FieldValue[bool] | — | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | riesgo relevante: Amazon como competidor directo |
| amazon_buy_box_share | Share de Amazon en Buy Box | % de tiempo con Amazon en Buy Box | FieldValue[Decimal] | % (0-1) | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/INFERRED/NOT_FOUND | alta | sí | |
| top_seller_fba | Top seller FBA | Seller dominante FBA | FieldValue[str] | — | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| top_seller_fbm | Top seller FBM | Seller dominante FBM | FieldValue[str] | — | no | sí | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | VERIFIED/NOT_FOUND | alta | no | |
| buy_box_concentration | Concentración de Buy Box | Medida de concentración entre sellers | FieldValue[Decimal] | índice | no | sí | calculated | CALCULATED | fórmula pendiente de definir (ver decisiones pendientes) | INFERRED/NOT_FOUND | alta | sí | no implementado en Fase 1 |

## Costs (`domain/costs.py::CostInputs`) — configurables, no hardcodeados

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cog | COG | Costo de la mercancía | Decimal | moneda | sí | no (obligatorio en `CostInputs`) | user_input, supplier_file | USER_INPUT, SUPPLIER_FILE | — | n/a (config, no dato "verificado") | n/a | no | sin provenance de tipo FieldValue — es configuración explícita del usuario, no un hecho a verificar |
| vat, inbound_shipping, shipping_per_unit, shipping_per_pound, prep, labeling, fragile_prep, storage, inbound_placement, taxes, other_costs | (varios) | Componentes de costo aterrizado | Decimal | moneda (o moneda/lb para shipping_per_pound) | no (default 0) | no | user_input | USER_INPUT | — | n/a | n/a | no | validados ≥ 0 en `CostInputs.__post_init__`; nunca constantes en código |

## Fees (`domain/costs.py::FeeInputs`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| referral_fee | Fee de referencia | Monto de referral fee a este precio | Decimal | moneda | sí | no | authorized_external_source, user_input | AUTHORIZED_EXTERNAL_SOURCE, USER_INPUT | — | n/a | alta | no | nunca calculado desde una tabla hardcodeada |
| referral_fee_rate | Tasa de referral | % de referral fee de la categoría | Decimal | ratio [0,1) | sí | no | authorized_external_source | AUTHORIZED_EXTERNAL_SOURCE | — | n/a | media | no | necesaria para `break_even_price` |
| fulfillment_fee | Fee de fulfillment | FBA fee o costo de fulfillment FBM | Decimal | moneda | no (default 0) | no | authorized_external_source, user_input | AUTHORIZED_EXTERNAL_SOURCE, USER_INPUT | — | n/a | alta | no | |
| other_selling_fees | Otros fees de venta | Fees adicionales (closing fee, etc.) | Decimal | moneda | no (default 0) | no | authorized_external_source, user_input | AUTHORIZED_EXTERNAL_SOURCE, USER_INPUT | — | n/a | alta | no | |

## Profitability (calculado — `processing/profitability.py`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| profit | Ganancia | Ganancia neta por unidad | FieldValue[Decimal] | moneda | sí (si hay `selling_price_used`) | sí | processing_core | CALCULATED | `seller_proceeds - total_cost` | VERIFIED/INFERRED/NOT_FOUND | = freshness del input más débil | no | nunca calculado por IA (ADR-006) |
| roi | ROI | Retorno sobre costo | FieldValue[Decimal] | ratio | sí | sí | processing_core | CALCULATED | `profit / total_cost` | VERIFIED/INFERRED/NOT_FOUND | idem | no | NOT_FOUND si `total_cost <= 0` |
| margin | Margen | Margen sobre precio de venta | FieldValue[Decimal] | ratio | sí | sí | processing_core | CALCULATED | `profit / selling_price` | VERIFIED/INFERRED/NOT_FOUND | idem | no | NOT_FOUND si `selling_price <= 0` |
| break_even_price | Precio de equilibrio | Precio al que profit = 0 | FieldValue[Decimal] | moneda | sí | sí | processing_core | CALCULATED | `(total_cost + fulfillment_fee + other_selling_fees) / (1 - referral_fee_rate)` | VERIFIED/INFERRED/NOT_FOUND | idem | no | asume referral fee proporcional al precio |
| max_cog_target_profit | COG máximo (por profit objetivo) | COG máximo para alcanzar `target_profit` | FieldValue[Decimal] | moneda | no (solo si se pide) | sí | processing_core | CALCULATED | `seller_proceeds - landed_cost_excl_cog - target_profit` | igual que profit | idem | no | `target_profit` es parámetro configurable, no constante |
| max_cog_target_roi | COG máximo (por ROI objetivo) | COG máximo para alcanzar `target_roi` | FieldValue[Decimal] | moneda | no (solo si se pide) | sí | processing_core | CALCULATED | `(seller_proceeds - landed_cost_excl_cog*(1+target_roi)) / (1+target_roi)` | igual que profit | idem | no | idem |

## Risk (`domain/risk.py::RiskFlag`, uno por `RiskType`)

Un `RiskFlag` por cada uno de: `HAZMAT`, `OVERSIZE`, `BULKY`, `MELTABLE`,
`FRAGILE`, `IP_COMPLAINTS`, `VARIATION`, `SET_OR_BUNDLE`, `GENERIC`,
`RESTRICTED`, `APPROVAL_REQUIRED`, `NO_BUY_BOX`, `NO_FBA_FEES`,
`ASIN_NOT_FOUND`.

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| status | Estado del riesgo | PRESENT / ABSENT / UNKNOWN | RiskStatus | — | sí | no | authorized_external_source, calculated | AUTHORIZED_EXTERNAL_SOURCE, INFERRED, CALCULATED | regla o dato de fuente | n/a (campo propio, ver verification_status) | media-alta según tipo | no | UNKNOWN exige `verification_status` NOT_FOUND/INVALID (invariante de código) |
| severity | Severidad | NONE/LOW/MEDIUM/HIGH/CRITICAL | FieldValue[Severity] | — | sí | no | juval_internal_policy (PRESENT) / lógica de ausencia (ABSENT) | CALCULATED (PRESENT, ADR-010) / n/a (ABSENT/UNKNOWN) | `DEFAULT_RISK_SEVERITY[risk_type]` si PRESENT | **independiente de `status`.verification_status (ADR-020)**: INFERRED si PRESENT (política interna, no aprobada por negocio), VERIFIED si ABSENT, NOT_FOUND/INVALID si UNKNOWN | idem status | no | ABSENT ⇒ `severity.value=NONE`; PRESENT ⇒ `severity.value` no `None` (invariantes); nunca hereda el `VERIFIED` de presence |
| verification_status | Estado de verificación del riesgo | VERIFIED/INFERRED/NOT_FOUND/INVALID | VerificationStatus | — | sí | no | — | — | — | — | — | — | — |
| source | Fuente | De dónde vino la determinación de este riesgo | str | — | sí | no | — | — | — | — | — | — | — |
| evidence | Evidencia | Texto/URL que soporta la determinación | str | — | no | sí | — | — | — | — | — | — | requerido en la práctica para HAZMAT/RESTRICTED por su impacto |
| timestamp | Timestamp | Cuándo se determinó | datetime (tz-aware) | — | sí | no | — | — | — | — | — | — | — |

## Decision / Score (calculado — `domain/decision.py`, `processing/decision_score.py`)

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| decision | Decisión | BUY / REVIEW / PASS | Decision | — | sí | no | processing_core | CALCULATED | reglas configurables, ver `DECISION_ENGINE.md` | n/a (no es un FieldValue, es una clasificación con `reasons` trazables) | por corrida | no | nunca decidido por IA |
| reasons | Razones | Lista de razones que motivaron la decisión | tuple[DecisionReason,...] | — | sí si no es BUY | no | processing_core | CALCULATED | una por regla disparada | n/a | por corrida | no | — |
| score | Decision Score | Score 0-100 | FieldValue[Decimal] | puntos (0-100) | no | sí | processing_core | CALCULATED | suma ponderada de 6 componentes | VERIFIED/INFERRED/NOT_FOUND | por corrida | no | **EXPERIMENTAL / NOT BUSINESS-APPROVED** — NOT_FOUND si falta cualquier componente (v1); no se calcula todavía dentro de `process_record` (Fase 2), ver decisiones pendientes |

## SourcingRecord (`domain/sourcing_record.py`) — Fase 2

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| record_ref | Referencia de registro | Identificador lógico y estable de la fila de origen | str | — | sí | no | infrastructure_excel | — | `f"row_{n}"` + `:sku` si hay supplier_sku | n/a | n/a | no | no depende de la posición física de la fila |
| product | Producto | Ver sección Product | Product | — | sí | no | — | — | — | — | — | — | composición, no duplicación |
| costs | Costos | Ver sección Costs | Optional[CostInputs] | — | no | sí | — | — | — | — | — | — | `None` si COG no era usable en el origen |
| fees | Fees | Ver sección Fees | Optional[FeeInputs] | — | no | sí | — | — | — | — | — | — | `None` hasta tener datos de fee |
| risk | Riesgo | Ver sección Risk | RiskProfile | — | sí (puede estar vacío) | no | — | — | — | — | — | — | — |
| profitability | Rentabilidad | Ver sección Profitability | Optional[ProfitabilityResult] | — | no | sí | — | — | — | — | — | — | `None` si faltan costs/fees/precio |
| score | Score | Ver Decision/Score | Optional[DecisionScoreResult] | — | no | sí | — | — | — | — | — | — | no cableado en el pipeline por defecto (Fase 2) |
| decision | Decisión | Ver Decision/Score | Optional[DecisionResult] | — | no | sí | — | — | — | — | — | — | `None` hasta correr `process_record` |
| issues | Issues | Errores/warnings acumulados de este registro | tuple[ProcessingIssue,...] | — | sí (puede ser vacío) | no | — | — | acumulado de import + processing | — | — | — | nunca se descartan issues previos al reprocesar |

## ExecutionRun (`domain/execution_run.py`) — Fase 2

| field_name | display_name | description | data_type | unit | required | nullable | source | source_type | calculation | verification_status | freshness | confidence | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| execution_id | ID de ejecución | Identificador de la corrida | str | — | sí | no | caller | USER_INPUT | suministrado por el llamador, no autogenerado | n/a | — | no | necesario para reproducibilidad determinística |
| started_at / finished_at | Inicio / fin | Instantes de la corrida (tz-aware) | datetime | — | sí / condicional | no / sí si RUNNING | caller | USER_INPUT | — | n/a | — | no | `finished_at=None` ⇔ `status=RUNNING` |
| status | Estado | RUNNING/SUCCESS/PARTIAL_SUCCESS/FAILED | ExecutionStatus | — | sí | no | processing_core | CALCULATED | derivado de conteos de error | n/a | — | no | — |
| input_filename / input_hash | Archivo de entrada | Nombre + SHA-256 del contenido | str | — | sí | no | infrastructure_excel | CALCULATED | `hash_file()` | n/a | — | no | permite confirmar que dos corridas usaron el mismo archivo exacto |
| application_version | Versión | Versión de Juval usada | str | — | sí | no | caller | USER_INPUT | típicamente `juval.__version__` | n/a | — | no | — |
| records_total/processed/successful/with_errors/warnings | Contadores | Ver `ExecutionRun` | int | conteo | sí | no | processing_core | CALCULATED | ver invariantes en `DATA_MODEL.md` §4 | n/a | — | no | — |
