# Juval — Repository / Documentation Reconciliation

Producido como tarea de reconciliación, no de implementación. Ningún
archivo de código (`src/`, `tests/`), ADR, `CLAUDE.md`, `README.md`, ni
`PROJECT_PLAN.md` fue modificado para producir este documento — ver §10
(Self-review) para la verificación explícita de esto.

Fecha de esta reconciliación: 2026-08-16.

## 1. Authority Model

Prioridad de autoridad usada para resolver cualquier discrepancia
encontrada, de mayor a menor:

1. **Código ejecutable** (`src/juval/**/*.py`) — qué existe realmente,
   verificado por lectura directa de cada módulo.
2. **Tests ejecutados** (`.venv/Scripts/python -m pytest -q`) — qué
   comportamiento está realmente probado, verificado por ejecución
   directa, no por lo que un documento dice que se probó.
3. **ADRs aceptados** (`docs/adr/*.md`, `Estado: Aceptada`) — qué
   decisiones arquitectónicas tienen respaldo formal. Un ADR en estado
   `Propuesta` **no** cuenta como decisión aceptada (ver §6, ADR-009).
4. **Documentación de arquitectura** (`docs/architecture/*.md`,
   `docs/PROJECT_PLAN.md`, `docs/DEVELOPMENT_LOOP.md`,
   `docs/PHASE_GATES.md`) — vista legible, normativa solo cuando no
   contradice 1-3.
5. **`CLAUDE.md` / `README.md`** — cuando describen estado derivado del
   repositorio (qué fase, cuántos tests, cuántos ADRs), se tratan como la
   fuente **menos** confiable de las cinco: son las que con más
   frecuencia quedan desactualizadas porque nadie las vuelve a tocar
   después de un cambio de código.

Regla aplicada de forma estricta en todo este documento: **ninguna
afirmación de fase/estado se aceptó sin verificarla contra 1 o 2**. Donde
un documento de nivel 3-5 afirmaba algo que el código o los tests
contradecían, gana el código/tests, y el documento se marca como
desactualizado (§7), nunca al revés.

## 2. Current Repository Reality

Sin `.git` inicializado (`git status` falla con "not a git repository") —
decisión pendiente explícita del usuario, no un error.

El repositorio contiene, verificado por lectura directa de cada archivo:

- **Domain** (`src/juval/domain/`) completo: `provenance.py`,
  `product.py`, `costs.py`, `risk.py`, `decision.py`, `identifiers.py`,
  `units.py`, `issues.py`, `sourcing_record.py`, `execution_run.py`.
- **Processing Core** (`src/juval/processing/`) completo:
  `profitability.py`, `decision_engine.py`, `decision_score.py`,
  `data_quality.py`, `pipeline.py`.
- **Application Layer** (`src/juval/application/`): un caso de uso real,
  `run_pipeline.py`.
- **Infrastructure — Excel** (`src/juval/infrastructure/excel/`)
  completo: `column_mapping.py`, `importer.py`, `exporter.py`.
- **Infrastructure — enrichment, logging**: solo `README.md` de
  propósito, sin código.
- **Interfaces** (`cli/`, `api/`, `desktop/`): solo `README.md` de
  propósito en cada carpeta, ningún entrypoint real.
- **Tests**: 165 tests, todos pasando (§5).
- **11 ADRs** en `docs/adr/` (ADR-001 a ADR-011), no 8 (§6).
- **Documentación de arquitectura** (`docs/architecture/*.md`) en su
  mayoría ya actualizada a Fase 2 — con excepciones puntuales
  documentadas en §7.

Esto es un **vertical slice funcional de Excel → dominio → processing →
Excel**, con datos verificados directamente del archivo de entrada
(`VERIFIED`/`NOT_FOUND`/`INVALID`), sin enriquecimiento externo, sin IA,
sin persistencia entre corridas, sin interfaz de usuario real. No es "un
producto completo" — es exactamente el alcance que Fase 2 se propuso, ya
implementado y probado, pero sin que su Completion Gate se haya evaluado
formalmente como tal en ningún documento existente (ver §3, §8).

## 3. Phase Status

| Phase | Status | Evidence |
|---|---|---|
| 0 — Foundation / docs | **COMPLETE** | Esqueleto de directorios con `README.md` por carpeta; ADR-001 a ADR-005 en `Estado: Aceptada`. |
| 1 — Domain + Processing Core | **COMPLETE** | `domain/{provenance,product,costs,risk,decision,identifiers,units,issues}.py` y `processing/{profitability,decision_engine,decision_score,data_quality}.py` implementados; 136 tests unitarios cubriéndolos, todos pasando; invariantes de `__post_init__` verificadas por tests. |
| 2 — SourcingRecord + Excel Vertical Slice | **CODE COMPLETE / GATE NOT FORMALLY EVALUATED** | `domain/sourcing_record.py`, `infrastructure/excel/{importer,exporter,column_mapping}.py`, `processing/pipeline.py`, `application/run_pipeline.py` — todos implementados y cubiertos por 29 tests de integración + 14 tests unitarios adicionales (`test_sourcing_record.py` 7, `test_pipeline.py` 7). Ningún documento del repositorio registra que el Completion Gate de `PHASE_GATES.md` §Fase 2 se haya ejecutado y declarado `PASS` explícitamente — de hecho `PHASE_GATES.md` mismo lo marca "NO EVALUADO FORMALMENTE" (aunque con hallazgos desactualizados, ver §7/§8). |
| 3 — Data Quality + ExecutionRun + Auditability | **CODE COMPLETE (parcial) / GATE NOT FORMALLY EVALUATED** | `domain/execution_run.py` implementado y probado (11 tests unitarios + 2 de integración de reproducibilidad); persistencia entre corridas **no implementada** (`infrastructure/logging/` vacío) — criterio conocido en `FAIL` si el gate se evaluara hoy. |
| 4 — Dashboard/PWA | **NOT STARTED — BLOCKED** | Cero código en `interfaces/api/` más allá del `README.md`; bloqueado por ADR-005 (PWA vs. `.exe` sin resolver) y stack frontend `PENDING`. |
| 5 — Decision Intelligence | **NOT STARTED — BLOCKED** | `decision_score.py` existe pero sus fórmulas de subscore no están aprobadas por negocio (`DECISION_ENGINE.md` §7). |
| 6 — Authorized External Data Sources | **NOT STARTED — BLOCKED** | `infrastructure/enrichment/` vacío; ninguna fuente externa concreta aprobada. |
| 7 — AI Analyst | **NOT STARTED — BLOCKED** | Cero código; solo diseño (`AI_ANALYST.md`, ADR-008). Proveedor de IA no aprobado. |
| 8 — Persistence/Supabase | **NOT STARTED — BLOCKED** | Supabase `PENDING` (`CLAUDE.md` §14); cero código de persistencia. |
| 9 — Auth | **NOT STARTED — BLOCKED** | Clerk `PENDING`; cero código. |
| 10 — Production Hardening | **NOT STARTED — BLOCKED** | Depende de todas las fases relevantes al path de deployment, ninguna resuelta. |

**Respuesta directa a "¿Phase 1 o Phase 2?"**: ninguna de las dos
etiquetas por sí sola es honesta. Phase 1 está terminada sin ambigüedad
(código + tests + gate documentado en `PASS`). El código de Phase 2 (y
parte de Phase 3) **ya existe, ya está probado, y ya funciona
end-to-end** — tratar al repositorio como si siguiera en "Phase 1" (como
hace `CLAUDE.md` hoy, ver §7) sería incorrecto y llevaría a reimplementar
trabajo que ya existe. Pero declarar Phase 2 "COMPLETE" tampoco sería
honesto, porque su Completion Gate (el proceso que el propio repositorio
define en `PHASE_GATES.md`) nunca se ejecutó y cerró formalmente. El
estado real y verificable es: **código y tests en estado de Fase 2/3,
gate de cierre pendiente de evaluación formal**.

## 4. Components

| Component | Status | Evidence |
|---|---|---|
| `SourcingRecord` | **IMPLEMENTED** | `domain/sourcing_record.py` — composición pura de `Product`/`CostInputs?`/`FeeInputs?`/`RiskProfile`/`ProfitabilityResult?`/`DecisionScoreResult?`/`DecisionResult?`/`issues` (ADR-011, `Estado: Aceptada`); inmutable vía `.with_*()`. 7 tests (`tests/unit/test_sourcing_record.py`). |
| `ExecutionRun` | **IMPLEMENTED (estructura) / NOT IMPLEMENTED (persistencia)** | `domain/execution_run.py` — invariantes de timestamps/contadores verificadas (11 tests, `test_execution_run.py`); construido por `application/run_pipeline.py`; reproducibilidad demostrada sin fuentes externas (2 tests, `test_reproducibility.py`). El propio docstring del módulo dice explícitamente "In-memory/local only in this phase". No captura `thresholds` ni `sources_used` (gap frente al diseño original de `ARCHITECTURE.md` §8). |
| Excel Importer | **IMPLEMENTED** | `infrastructure/excel/importer.py::import_excel` — columnas por nombre (nunca posición), `FieldValue.verified/not_found/invalid` según celda, `DEFAULT_RISK_SEVERITY` para HAZMAT/BULKY (provisional, ADR-010 `Estado: Aceptada`). 17 tests de integración. |
| Excel Exporter | **IMPLEMENTED** | `infrastructure/excel/exporter.py::export_excel` — `<campo>`/`<campo>_status` separados, nunca colapsados. 4 tests de integración. |
| Column Mapping | **IMPLEMENTED** | `infrastructure/excel/column_mapping.py::COLUMN_SPECS` — tabla explícita header↔campo, con alias. |
| Normalization | **IMPLEMENTED** | `importer.py::normalize_header`, `_parse_cell`, `domain/units.py::to_pounds/to_inches`. |
| Validation (Excel-level) | **IMPLEMENTED** | Por celda en `importer.py` (FATAL si falta columna requerida; INVALID por formato); re-validación estructural en `processing/data_quality.py`. |
| Fixtures | **IMPLEMENTED** | `tests/fixtures/sample_sourcing_TEST_DATA.xlsx` + `generate_sample.py` — 5 filas cubriendo válido/faltante/inválido/riesgo/malformado. |
| Integration tests (Excel) | **IMPLEMENTED** | `test_excel_importer.py` (17), `test_excel_exporter.py` (4), `test_pipeline_end_to_end.py` (6). |
| Vertical slice (Excel→Domain→Processing→Excel) | **IMPLEMENTED** | Demostrado de extremo a extremo por `test_pipeline_end_to_end.py` sin mocks del Core. |
| Processing Pipeline | **IMPLEMENTED (para el alcance actual) / PARTIALLY IMPLEMENTED en la etapa Risk** | `processing/pipeline.py::process_record/process_batch` — orquesta Data Quality → Profitability → Decision con los motores reales. La etapa "Risk" no evalúa reglas nuevas, solo lee `record.risk` ya construido en import (solo HAZMAT/BULKY cableados, 12 `RiskType` restantes sin fuente). `docs/architecture/PROCESSING_PIPELINE.md` (creado en esta sesión, a partir de lectura directa del código) coincide con el código verificado aquí. |
| Profitability | **IMPLEMENTED** | `processing/profitability.py` — funciones puras `Decimal→Decimal`, sin IA (ADR-006). 14 tests unitarios contra valores calculados a mano. |
| Decision Engine | **IMPLEMENTED (modelo extensible, reglas no definitivas)** | `processing/decision_engine.py::evaluate_decision` — PASS→REVIEW→BUY. 12 tests unitarios. Thresholds sin default exportado (ADR-007). |
| Decision Score | **IMPLEMENTED (código) / NOT WIRED en el pipeline** | `processing/decision_score.py::compute_decision_score` — 6 tests unitarios; **no** se invoca desde `process_record`/`process_batch`; fórmulas de subscore no aprobadas por negocio (`DECISION_ENGINE.md` §7). |
| Data Quality | **IMPLEMENTED** | `processing/data_quality.py` — 6 funciones `validate_*`. 15 tests unitarios. |
| Provenance | **IMPLEMENTED** | `domain/provenance.py` — `FieldValue`, `Provenance`, `VerificationStatus`, `SourceType`, `combine_verification_status`. 16 tests unitarios. |
| AI Analyst | **NOT IMPLEMENTED** | Cero código en el repositorio. Solo diseño: `docs/architecture/AI_ANALYST.md` + ADR-008 (`Estado: Aceptada` — el diseño está aceptado, no la implementación). |

## 5. Tests

Ejecutado directamente para esta reconciliación:

```
.venv/Scripts/python -m pytest -q
165 passed in 0.78s
```

- **Total**: 165
- **Failures**: 0
- **Skips**: 0
- **Duración**: 0.78s (una ejecución previa en esta misma sesión dio
  0.68s — variación normal de wall-clock, no indica flakiness; 0 fallos
  en ambas corridas)

Desglose por archivo verificado con `pytest --collect-only`: 136 tests en
`tests/unit/` (13 archivos) + 29 en `tests/integration/` (4 archivos) =
165. Detalle completo por archivo en
`docs/architecture/TESTING_STRATEGY.md` (creado en esta sesión).

**El número "111 tests" está obsoleto y no debe usarse como referencia
vigente.** Corresponde al cierre de Fase 1 (antes de que se agregaran los
54 tests de Fase 2/3: `sourcing_record`, `pipeline`, `execution_run`,
integración Excel, `reproducibility`). `docs/PROJECT_PLAN.md` §Fase 1 ya
documenta correctamente esta transición ("111 tests unitarios pasando en
el momento de cierre de esta fase — hoy son 165"). `CLAUDE.md` §17 sigue
citando 111 como si fuera el estado actual — ver §7 (Documentation
Drift).

## 6. ADR Status

| ADR | Título | Estado | Fecha |
|---|---|---|---|
| ADR-001 | Separación UI / Processing Core | Aceptada | 2026-08-16 |
| ADR-002 | Excel como formato de intercambio | Aceptada | 2026-08-16 |
| ADR-003 | Estructura de provenance | Aceptada | 2026-08-16 |
| ADR-004 | Estados VERIFIED/INFERRED/NOT_FOUND/INVALID | Aceptada | 2026-08-16 |
| ADR-005 | Independencia arquitectónica PWA vs. `.exe` | Aceptada (diseño; la elección PWA/.exe en sí sigue PENDING) | 2026-08-16 |
| ADR-006 | Cálculos financieros determinísticos, nunca IA | Aceptada | 2026-08-16 |
| ADR-007 | Thresholds/reglas configurables, no hardcodeados | Aceptada | 2026-08-16 |
| ADR-008 | Límites del AI Analyst | Aceptada (diseño; sin implementación) | 2026-08-16 |
| ADR-009 | Development Loop + Completion Gates | **Propuesta (NO Aceptada)** | 2026-08-16 |
| ADR-010 | Severidad de riesgo por defecto es provisional | Aceptada (marcada explícitamente provisional/no aprobada por negocio en su contenido) | 2026-08-16 |
| ADR-011 | `SourcingRecord` como composición | Aceptada | 2026-08-16 |

**Último ADR**: ADR-011 (`Aceptada`). El más reciente en estado no
resuelto es ADR-009 (`Propuesta`).

**Verificación específica ADR-009 / ADR-010 pedida por esta tarea** — este
es el hallazgo central de esta reconciliación:

- `docs/PROJECT_PLAN.md`, `docs/DEVELOPMENT_LOOP.md` y
  `docs/PHASE_GATES.md` afirman, los tres, que existe una "colisión de
  numeración" sin resolver: que `domain/sourcing_record.py` referencia
  "ADR-009" (que en realidad documenta el Development Loop, no la
  composición de `SourcingRecord`), y que `infrastructure/excel/importer.py`
  referencia un "ADR-010" que no existe.
- **Verificado directamente contra el código fuente** (no contra lo que
  estos documentos dicen que el código dice):
  - `src/juval/domain/sourcing_record.py:8` dice literalmente
    *"See ADR-011"* — no ADR-009.
  - `src/juval/infrastructure/excel/importer.py:46` dice literalmente
    *"See ADR-010"* — y ADR-010 **sí existe**
    (`docs/adr/ADR-010-severidad-riesgo-provisional.md`, `Estado: Aceptada`),
    y documenta exactamente la decisión que el comentario del código dice
    que documenta (severidad por defecto de HAZMAT/BULKY, provisional).
- **Conclusión**: ambas referencias del código son correctas y ya están
  resueltas por ADR-010 y ADR-011 (ambos `Estado: Aceptada`, fecha
  2026-08-16). El "conflicto" que `PROJECT_PLAN.md` §4, `PHASE_GATES.md`
  §3 y `DEVELOPMENT_LOOP.md` (Step 1 y Step 7) describen **no existe en
  el estado actual del repositorio** — existió en algún momento anterior
  de la misma sesión de trabajo (los timestamps de archivo son
  consistentes con que ADR-010/ADR-011 se crearon *después* de que
  `PROJECT_PLAN.md`/`DEVELOPMENT_LOOP.md`/`PHASE_GATES.md` se escribieran,
  dentro de la misma tarea, sin que esos tres documentos se actualizaran
  después para reflejar la corrección). Ver §7 y §8 para el detalle
  completo y la corrección recomendada.
- Esto también afecta un hallazgo derivado: `PHASE_GATES.md` §Fase 2
  marca "Universal Gate ítem 4 (sin conflictos arquitectónicos) — FAIL"
  citando exactamente estas dos referencias como evidencia. Con la
  evidencia real (ambas resueltas), ese ítem específico ya no está en
  `FAIL` por esta causa — aunque otros ítems del gate de Fase 2 siguen
  abiertos (record_ref sin aprobación formal, documentación de fases
  desactualizada, CLI ausente) y no se resuelven aquí.

## 7. Documentation Drift

| Document | Claim | Actual Reality | Correction Required |
|---|---|---|---|
| `CLAUDE.md` §1/§6/§7 | "Fase 1... `application/`, `infrastructure/*`, `interfaces/*` vacíos (solo `README.md`)"; "última verificación: 2026-08-16 (111 tests pasando)" | `application/run_pipeline.py` y `infrastructure/excel/{importer,exporter,column_mapping}.py` están implementados y probados; `interfaces/*` sigue vacío (esto sí es correcto); 165 tests pasan hoy | Actualizar `CLAUDE.md` §1, §6, §7 al estado real de Fase 2. **No ejecutado en esta tarea** (`CLAUDE.md` explícitamente no se modifica aquí). |
| `CLAUDE.md` §17 | "111 tests unitarios pasando" | 165 tests pasando (136 unit + 29 integration) | Actualizar §17. No ejecutado aquí. |
| `CLAUDE.md` §18 | "`docs/adr/` ya contiene 8 ADRs aceptados (ADR-001 a ADR-008)" | Existen 11 ADRs (001-011); ADR-009 está en `Propuesta`, no `Aceptada` | Actualizar §18 para contar 11 ADRs y aclarar que ADR-009 no está aceptada. No ejecutado aquí. |
| `docs/PROJECT_PLAN.md` §4, `docs/PHASE_GATES.md` §3 | `sourcing_record.py` referencia "ADR-009" (colisión sin resolver) | El código referencia "ADR-011" (ver §6) — ya resuelto | Actualizar la fila/tabla correspondiente en ambos documentos para reflejar que esto está resuelto. |
| `docs/PROJECT_PLAN.md` §Fase 2 (riesgo #2), `docs/PHASE_GATES.md` §3, `docs/DEVELOPMENT_LOOP.md` Step 1/Step 7 | `importer.py` referencia un "ADR-010" que no existe | ADR-010 existe (`Estado: Aceptada`) y documenta exactamente esa decisión (ver §6) | Actualizar los tres documentos para reflejar que esto está resuelto. |
| `docs/PROJECT_PLAN.md` §Fase 2, `docs/PHASE_GATES.md` §Fase 2, `docs/DEVELOPMENT_LOOP.md` Step 1 | "`README.md` raíz... sigue afirmando 'Fase 1... sin Excel Importer/Exporter'" | El `README.md` raíz actual dice explícitamente "Fase 2: primer vertical slice funcional" y describe Excel Import/Export y `SourcingRecord` como ya implementados | Corregir esta afirmación en los tres documentos — ya no es cierta contra el `README.md` actual. |
| `docs/PROJECT_PLAN.md` §Fase 2 | "`docs/architecture/DATA_MODEL.md` §1/§5 siguen afirmando... 'SourcingRecord... no está implementado todavía como clase'" | `DATA_MODEL.md` §1 dice explícitamente "Implementado en `domain/sourcing_record.py` (Fase 2) como composición pura" | Corregir esta afirmación en `PROJECT_PLAN.md`. |
| `PHASE_GATES.md` §Fase 2 | "Universal Gate ítem 4 (sin conflictos arquitectónicos) — FAIL" (citando las dos referencias de ADR de arriba) | Ambas referencias están resueltas (§6) | Re-evaluar este ítem específico — ya no aplica el motivo citado; el resto de ítems del gate de Fase 2 sigue abierto por otras razones (record_ref, CLI, staleness general de documentación de fase) que sí se mantienen. |
| `src/juval/domain/README.md` | "Entidades: `CatalogRecord`, `FieldValue[T]`, `VerificationStatus`, `ProcessingIssue`, `ExecutionRun`" | `CatalogRecord` no existe en el código; las entidades reales incluyen `Product`, `CostInputs`/`FeeInputs`, `RiskProfile`, `Decision`, `SourcingRecord`, `ExecutionRun` | Reescribir este README con las entidades reales. `CLAUDE.md` §6 ya señala esta discrepancia explícitamente como conocida y pendiente. |
| `src/juval/infrastructure/excel/README.md` | "Importador y Exportador de Excel... `RawRecord` → `CatalogRecord` en import; `CatalogRecord`/`ResultModel` → filas en export" | Ninguno de `RawRecord`/`CatalogRecord`/`ResultModel` existe en el código; el importer construye `SourcingRecord` directamente dentro de `ImportResult` | Reescribir este README con los tipos reales. |

## 8. Critical Contradictions

Solo las que afectan una decisión real (no cosméticas):

1. **`CLAUDE.md` describe un repositorio de Fase 1 con capas vacías; el
   código es de Fase 2 con esas capas implementadas y probadas.** Es la
   contradicción de mayor impacto: cualquier tarea futura que confíe en
   `CLAUDE.md` sin inspeccionar el código directamente (violando el Step
   1 de `DEVELOPMENT_LOOP.md`, que el propio repositorio define) corre el
   riesgo de reimplementar `SourcingRecord`, el Excel Importer/Exporter,
   o `ExecutionRun` desde cero, o de asumir que no existen tests que
   cubran esa funcionalidad. Resuelto por autoridad: **el código y los
   165 tests ganan**; `CLAUDE.md` queda documentado como desactualizado
   (§7), sin modificarse en esta tarea.

2. **Tres documentos de planificación (`PROJECT_PLAN.md`,
   `DEVELOPMENT_LOOP.md`, `PHASE_GATES.md`) describen como abierto un
   problema de referencias de ADR colgantes que el propio repositorio ya
   resolvió** (ADR-010 y ADR-011, ambos `Aceptada`, ambos consistentes
   con lo que el código cita). Esto es notable porque estos tres
   documentos son, según sus propios timestamps de archivo, más antiguos
   que ADR-011 — es decir, describieron el problema y luego, dentro de la
   misma tarea, alguien lo corrigió en el código y en los ADRs sin volver
   a esos tres documentos para quitar la advertencia ya resuelta. Resuelto
   por autoridad: **código + ADR-010/011 (nivel 1 y 3) ganan** sobre la
   narrativa de nivel 4 en esos tres documentos.

3. **`ADR-009` no está aceptada, pero define el proceso
   (`DEVELOPMENT_LOOP.md`/`PHASE_GATES.md`) que otros documentos citan
   como si ya fuera normativo.** `DEVELOPMENT_LOOP.md` y `PHASE_GATES.md`
   se presentan a sí mismos como "Normativo" sin calificar que la ADR que
   los formaliza sigue en `Propuesta`, pendiente de confirmación explícita
   del usuario. No es necesariamente incorrecto usarlos como guía de
   trabajo (son razonables y ya se usaron para producir este mismo
   reporte), pero tratarlos como obligatorios/aprobados sin esa
   aclaración sería inventar una aprobación que no existe — exactamente
   lo que `CLAUDE.md` §3 prohíbe.

4. **Ningún documento (ni siquiera `PHASE_GATES.md`, que es el más
   preciso) declara explícitamente si Fase 2 puede tratarse como
   "suficientemente terminada para construir sobre ella" o si un futuro
   trabajo debe primero cerrar su Completion Gate formalmente.** No es
   una contradicción entre documentos, es una ausencia de decisión — se
   deja como recomendación en §9, no resuelta aquí.

## 9. Recommended Canonical State

**Esto es una recomendación. Ninguna decisión PENDING se convierte en
aprobada por este documento.**

- Tratar el estado real del repositorio como: **Fase 0 y Fase 1
  `COMPLETE`; código y tests de Fase 2 y (parcialmente) Fase 3
  implementados y pasando, con el Completion Gate formal todavía sin
  ejecutar** — no como "Fase 1" (subestima lo que existe) ni como "Fase 2
  COMPLETE" (sobrestima el cierre de proceso).
- Antes de iniciar cualquier trabajo nuevo de Fase 2 o Fase 3, se
  recomienda ejecutar explícitamente el Completion Gate de
  `PHASE_GATES.md` §Fase 2/§Fase 3 con la evidencia corregida de este
  reporte (los dos ítems de "conflicto de ADR" ya no aplican; los
  restantes — `record_ref` sin aprobación formal, persistencia de
  `ExecutionRun`, CLI ausente — siguen abiertos).
- Se recomienda que una tarea futura (explícitamente autorizada, fuera
  del alcance de esta reconciliación) actualice:
  - `CLAUDE.md` §1/§6/§7/§17/§18, al estado real (165 tests, 11 ADRs,
    Fase 2 con capas implementadas).
  - `docs/PROJECT_PLAN.md` §4 y §Fase 2, `docs/PHASE_GATES.md` §3 y
    §Fase 2, `docs/DEVELOPMENT_LOOP.md` Step 1/Step 7, para retirar las
    dos advertencias de ADR ya resueltas y la afirmación obsoleta sobre
    `README.md`/`DATA_MODEL.md`.
  - `src/juval/domain/README.md` y
    `src/juval/infrastructure/excel/README.md`, con las entidades reales.
- Se recomienda que el usuario confirme explícitamente si ADR-009
  (Development Loop) pasa a `Aceptada` — hoy es la única pieza de proceso
  normativo del repositorio que sigue formalmente sin aprobar, a pesar de
  que ya se usó de facto (incluida esta reconciliación) como si lo
  estuviera.
- **No se recomienda** iniciar código nuevo de Fase 2/3, ni declarar
  ninguna fase `COMPLETE`, como resultado de este documento — eso
  requiere ejecutar el Completion Gate formalmente, con reporte propio,
  en una tarea separada.

## 10. Self-review

- [x] `pytest` re-ejecutado en esta tarea: 165 passed, 0 failed, 0
      skipped, 0.78s.
- [x] Ningún archivo `.py` fue modificado en esta sesión (verificado:
      todos los `.py` con mtime posterior a `pyproject.toml` corresponden
      a código preexistente de Fase 2/3, ninguno fue tocado por esta
      tarea — solo se usó `Read`, nunca `Edit`/`Write` sobre `.py`).
- [x] Ningún test fue modificado (misma verificación — solo `Read` sobre
      `tests/`).
- [x] Ningún ADR fue modificado (solo `Read` sobre `docs/adr/`).
- [x] `CLAUDE.md`, `README.md`, `docs/PROJECT_PLAN.md` no fueron
      modificados.
- [x] La conclusión de fase (§3) está respaldada por código + tests
      directamente citados, no por la narrativa de otro documento.
- [x] 165 reemplaza correctamente a 111 como baseline vigente (§5); 111
      se documenta explícitamente como el número de cierre de Fase 1, no
      el actual.
- [x] No se confundió "estructura implementada" con "persistencia
      implementada": `ExecutionRun` está marcado IMPLEMENTED como
      estructura y explícitamente NOT IMPLEMENTED en persistencia (§4).
- [x] No se confundió "vertical slice existente" con "producto completo":
      §2 aclara explícitamente que el vertical slice no equivale a un
      producto terminado (sin IA, sin enriquecimiento externo, sin
      persistencia entre corridas, sin UI).

## Archivos creados por esta tarea

Únicamente: `docs/RECONCILIATION_REPORT.md` (este documento).
