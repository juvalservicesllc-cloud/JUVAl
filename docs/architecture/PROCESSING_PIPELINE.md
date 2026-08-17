# Juval — Processing Pipeline

Vista conceptual, de extremo a extremo, del pipeline de procesamiento.
Complementa `ARCHITECTURE.md` §16.1 (que muestra el mismo flujo de forma
más breve) con el detalle de qué hace cada etapa, en qué módulo vive, y
qué estado tiene hoy. El código en `src/juval/processing/pipeline.py` y
`src/juval/application/run_pipeline.py` es normativo; este documento es
la vista legible. Si hay discrepancia, el código gana.

## 1. Pipeline conceptual completo

```
INPUT
  ↓
INGESTION
  ↓
NORMALIZATION
  ↓
VALIDATION
  ↓
DOMAIN MODEL
  ↓
PROFITABILITY
  ↓
RISK
  ↓
DECISION
  ↓
OUTPUT
  ↓
AI ANALYST
```

## 2. Estado de cada etapa

| Etapa | Estado | Módulo | Descripción |
|---|---|---|---|
| INPUT | **IMPLEMENTED** | `infrastructure/excel/importer.py::import_excel` | Lee un `.xlsx` vía `openpyxl`. Única fuente de input real hoy (ver `DATA_SOURCES.md`). |
| INGESTION | **IMPLEMENTED** | `importer.py::import_excel` | Resuelve headers por nombre (`normalize_header` + `column_mapping.py`), fila por fila. Columnas requeridas ausentes → `FATAL`, aborta el import completo. |
| NORMALIZATION | **IMPLEMENTED** | `importer.py::_parse_cell`, `domain/units.py` | Parseo sintáctico (texto → `Decimal`/`int`/`bool`/ASIN/UPC) y normalización de unidades (peso→lb, dimensiones→in). No es una decisión de negocio, es conversión mecánica. |
| VALIDATION | **IMPLEMENTED** | `importer.py` (por celda, al construir cada `FieldValue`) + `processing/data_quality.py` (re-validación estructural, "defense in depth") | Dos pasadas: la del importer decide VERIFIED/NOT_FOUND/INVALID celda a celda; `data_quality.py` vuelve a auditar el `SourcingRecord` ya construido (formato de identificadores, rangos razonables de dimensiones, consistencia de precio/competencia/financieros). |
| DOMAIN MODEL | **IMPLEMENTED** | `domain/sourcing_record.py`, `domain/product.py`, y el resto de `domain/*.py` | Cada fila válida se materializa como un `SourcingRecord` (composición de `Product`, `CostInputs?`, `RiskProfile`, ver ADR-011). |
| PROFITABILITY | **IMPLEMENTED** | `processing/profitability.py::compute_profitability`, invocado desde `processing/pipeline.py::process_record` | Solo corre si el registro tiene `costs`, `selling_price_used` y `fees` usables; si falta cualquiera, se registra un `WARNING` y `profitability` queda `None` (ver §3). |
| RISK | **PARTIALLY IMPLEMENTED** | `processing/pipeline.py::process_record` (lee `record.risk`, ya construido en import) | El pipeline no re-evalúa riesgo — lo consume tal como llegó del importer. Hoy el importer solo cablea `HAZMAT`/`BULKY` desde Excel (`DEFAULT_RISK_SEVERITY`, ADR-010, severidad provisional no aprobada). Los otros 12 `RiskType` no tienen fuente de datos todavía (`EXCEL_PROCESSING.md` §8) — quedan simplemente ausentes de `RiskProfile.flags`, no se fabrican como `UNKNOWN`. |
| DECISION | **IMPLEMENTED** | `processing/decision_engine.py::evaluate_decision`, invocado desde `pipeline.py::process_record` | BUY/REVIEW/PASS con precedencia PASS → REVIEW → BUY (ver `DECISION_ENGINE.md`). Si `profitability` es `None`, `profit`/`roi` se pasan como `NOT_FOUND` explícito, nunca se omite la decisión. |
| OUTPUT | **IMPLEMENTED** | `infrastructure/excel/exporter.py::export_excel` | Un `.xlsx` con una fila por `SourcingRecord`, columnas de provenance separadas del valor (`<campo>` / `<campo>_status`). |
| AI ANALYST | **NOT IMPLEMENTED** (diseño únicamente) | — | Ver `AI_ANALYST.md` y ADR-008. No forma parte del pipeline ejecutable hoy; ningún módulo de `processing/` o `application/` lo invoca. Cuando exista, se conecta estrictamente después de OUTPUT, nunca entre DOMAIN MODEL y DECISION. |

`DecisionScoreResult` (`processing/decision_score.py`) existe y está
probado, pero **no** está cableado dentro de `process_record`/
`process_batch` — es una etapa adicional disponible, no parte del
pipeline por defecto de Fase 2 (ver `DECISION_ENGINE.md` §5).

## 3. Orquestación real (`process_record`)

`processing/pipeline.py::process_record(record, thresholds, *, fees, quality_config, now)`
ejecuta, en este orden, sobre un único `SourcingRecord`:

1. **Data Quality** — `validate_identification`, `validate_dimensions`,
   `validate_price`, `validate_competition_consistency` sobre
   `record.product`; issues acumuladas, nunca detienen el registro.
2. **Profitability** — solo si `record.costs`, `selling_price_used` y
   `fees` (parámetro o `record.fees`) están presentes; si no, se agrega
   un `WARNING` (`MISSING_SELLING_PRICE` / `MISSING_FEES`) y
   `profitability` queda `None`. Reusa `compute_profitability` — ninguna
   fórmula se reimplementa aquí.
3. **Risk** — se lee `record.risk` tal como fue construido en import; esta
   etapa no evalúa reglas nuevas en Fase 2.
4. **Decision** — construye `DecisionInputs` (con `profit`/`roi`
   `NOT_FOUND` explícito si no hubo Profitability) y llama
   `evaluate_decision`.
5. **Issues aggregation** — todas las issues de los pasos 1-4 más las que
   ya traía el registro desde el import se acumulan en
   `record.issues` (nunca se descartan).

`process_batch` aplica `process_record` a cada registro de la lista,
independientemente — un fallo o `RECORD_ERROR` en una fila no detiene el
resto del lote (consistente con `ARCHITECTURE.md` §7).

`application/run_pipeline.py::run_pipeline` es la orquestación de más
alto nivel: `import_excel` → `process_batch` → construye un
`ExecutionRun` (ver `EXECUTION_MODEL.md`). Es el único módulo permitido a
depender tanto de `infrastructure/` como de `processing/` (regla de
dependencia, ver `ARCHITECTURE.md` §3.2). No hay una etapa de OUTPUT
(exportar a Excel) dentro de `run_pipeline` mismo — el llamador invoca
`export_excel(records, path)` por separado; `run_pipeline` no asume que
el resultado siempre se exporta a Excel.

## 4. Qué NO hace este pipeline (deliberadamente, en esta fase)

- No re-evalúa ni genera `RiskFlag`s nuevos — solo consume los que ya
  trae el `SourcingRecord`.
- No calcula `DecisionScoreResult`.
- No persiste nada entre corridas (ver `EXECUTION_MODEL.md`).
- No invoca ninguna fuente externa de enriquecimiento — el único input de
  datos es el Excel del usuario.
- No invoca IA en ningún punto.

## 5. Relacionado

`ARCHITECTURE.md` §16.1 (versión resumida de este flujo),
`EXCEL_PROCESSING.md` (detalle de INPUT/INGESTION/NORMALIZATION/VALIDATION
a nivel de columna), `DECISION_ENGINE.md` (detalle de la etapa DECISION),
`EXECUTION_MODEL.md` (qué produce `run_pipeline` para reproducibilidad),
`AI_ANALYST.md` (contrato de la etapa AI ANALYST, sin código).
