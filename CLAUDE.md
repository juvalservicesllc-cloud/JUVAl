# CLAUDE.md — Contrato operativo de Juval

Este archivo es el contrato operativo permanente para Claude Code/Codex
trabajando en el proyecto Juval. Se aplica a **todo** el trabajo en este
repositorio. Contiene reglas operativas; las especificaciones detalladas
viven en `docs/` (arquitectura) y `docs/adr/` (decisiones). Si algo aquí
parece contradecir `docs/`, **`docs/` y el código ganan** — reportar la
discrepancia y corregir este archivo, no al revés.

Última verificación contra el repositorio: 2026-08-17 (ver
`docs/RECONCILIATION_REPORT.md` y `docs/PROJECT_STATUS.md` §Sesión
2026-08-17, bloques 1-8; `.git` **inicializado** pero **sin commit
todavía** — falta `git config user.name`/`user.email`, que el agente
tiene prohibido configurar; **209 tests de backend + 9 de frontend + 1
E2E real**, todos en verde; **18 ADRs** en `docs/adr/` — ADR-001 a
ADR-008 y ADR-010 a ADR-018 en estado Aceptada, **solo ADR-009 en
estado Propuesta**; Fase 2/3 **COMPLETE**; `interfaces/cli/main.py`
implementado; ADR-014 — PWA; ADR-015 — fallback fail-closed de
severidad, HAZMAT→HIGH/BULKY→MEDIUM sin aprobación de negocio, sin
cambiar; ADR-016 — FastAPI, `interfaces/api/` **IMPLEMENTED** (Fase
4A); ADR-017 — Supabase/PostgreSQL aprobado como persistencia de
producción, adapter preparado pero **no verificado contra una base
real**; ADR-018 — **Railway aprobado para el backend** (Vercel Functions
descartado por incompatibilidad real con el contrato POST/GET,
`API_CONTRACT.md` §8.4), `railway.toml` preparado, **sin desplegar**
(`railway login` pendiente, interactivo). **Fase 4B (frontend
React+Vite+PWA) IMPLEMENTED** (`frontend/`, 9 tests + 1 E2E real).
Herramientas instaladas: Node.js v24.19.0, npm v11.17.0, Vercel CLI
59.1.3, Railway CLI 5.41.2 (todas verificadas); Supabase CLI utilizable
vía `npx supabase@latest`. Vercel/Supabase/Railway sin
desplegar/verificar — los tres requieren login interactivo (OAuth de
navegador) que el agente no puede completar. Fase 4 global sigue sin
`COMPLETE` — ver `docs/PHASE_GATES.md` §Fase 4. Los números históricos
de 111, 165 y 177 tests corresponden a los cierres de Fase 1, Fase 2 y
Fase 3 respectivamente — ver `docs/architecture/TESTING_STRATEGY.md`.

---

## 1. Objetivo del proyecto

Juval es una plataforma de análisis y toma de decisiones de sourcing para
Amazon/e-commerce: carga datasets (especialmente Excel), los procesa, los
enriquece mediante fuentes autorizadas, calcula rentabilidad, analiza
riesgo y produce una decisión de sourcing.

Decisiones posibles: **BUY / REVIEW / PASS**.

La IA se incorporará como analista (explicar, comparar, priorizar,
detectar problemas) — nunca como fuente primaria de datos ni como motor de
cálculo determinístico. Ver §9 y `docs/architecture/AI_ANALYST.md`.

## 2. Principio fundamental — orden de prioridad

1. **Correctitud**
2. **Trazabilidad**
3. **Reproducibilidad**
4. **Escalabilidad**
5. **Automatización**
6. **Velocidad**

Una implementación que "funciona" pero es incorrecta, no trazable o no
reproducible **no está terminada**. Fuente normativa:
`docs/architecture/ARCHITECTURE.md` §2.

## 3. Rol del agente

El agente (Claude Code/Codex) inspecciona, diseña cuando corresponde,
implementa, modifica archivos, ejecuta tests y validaciones, documenta
cambios, hace self-review y reporta riesgos.

**No decide silenciosamente** sobre: modelo de datos, arquitectura,
seguridad, persistencia, fuentes externas, lógica comercial, IA,
autenticación, deployment. Toda decisión con ese impacto debe marcarse
explícitamente:

- **APPROVED** — existe un ADR aceptado o instrucción explícita del
  usuario que la respalda.
- **PENDING** — no existe esa base; no se implementa como si estuviera
  decidida, aunque sea técnicamente fácil.

Nunca convertir una decisión PENDING en APPROVED por conveniencia de
implementación.

## 4. Regla de oro

No confundir **"puedo hacerlo"** con **"debemos hacerlo"**. No
implementar funcionalidad, abstracciones, dependencias o infraestructura
antes de que exista una necesidad real y verificable en el código o en
una instrucción del usuario.

## 5. Ponytail

Ponytail está instalado (plugin `ponytail@ponytail`) y activo. **Modo
predeterminado del proyecto: Ponytail FULL** (no hay
`ponytail/config.json` ni `PONYTAIL_DEFAULT_MODE` que lo cambien, así que
el default del propio plugin ya es `full` — consistente, no requiere
configuración adicional).

Usar Ponytail para evitar: over-engineering, abstracciones innecesarias,
duplicación, boilerplate, dependencias innecesarias, código especulativo,
capas sin valor. Preferir: soluciones simples, código existente, stdlib,
reutilización, mínima implementación necesaria.

**Pero Ponytail NO puede eliminar arquitectura necesaria.** No
simplificar ni eliminar automáticamente:

- provenance (`FieldValue`/`Provenance`, ADR-003/ADR-004);
- validación (invariantes de `__post_init__`, capa de validación);
- separación de capas (ADR-001);
- tests;
- auditabilidad / reproducibilidad;
- fronteras de dominio;
- decisiones de ADR ya aceptadas.

Regla: **minimalismo de implementación, no minimalismo de arquitectura.**
Si Ponytail propone eliminar una decisión de un ADR aceptado, se reporta
como conflicto — no se aplica automáticamente.

Workflow antes de un cambio importante: inspeccionar → implementar →
tests → Ponytail review (`/ponytail-review` en diffs grandes,
`/ponytail-audit` para auditoría de repo, `/ponytail-debt` para deuda
marcada con comentarios `ponytail:`) → self-review. No ejecutar cambios
destructivos basados únicamente en una sugerencia de Ponytail.

## 6. Arquitectura (implementada, no solo propuesta)

```
Interfaces (CLI / API / desktop)
        ↓
Application Layer
        ↓
Processing Core  ←→  Domain
        ↓
Infrastructure (Excel, enrichment, logging)
```

Regla de dependencia: las flechas de código van hacia adentro. El
Processing Core y el Domain nunca importan Excel, HTTP, un framework web
ni un proveedor de IA concreto. Infrastructure implementa puertos
definidos hacia adentro (inversión de dependencias). Normativo:
`docs/architecture/ARCHITECTURE.md` §3, ADR-001.

**Estado real de cada capa (reconciliado 2026-08-16, ver
`docs/RECONCILIATION_REPORT.md`):**

| Capa | Estado |
|---|---|
| `domain/` | Implementado y probado: `provenance.py`, `product.py`, `costs.py`, `risk.py`, `decision.py`, `identifiers.py`, `units.py`, `issues.py`, `sourcing_record.py` (§7, ADR-011), `execution_run.py` (§15) |
| `processing/` | Implementado y probado: `profitability.py`, `decision_engine.py`, `decision_score.py`, `data_quality.py`, `pipeline.py` (`process_record`/`process_batch`, ver `docs/architecture/PROCESSING_PIPELINE.md`) |
| `application/` | Implementado: `run_pipeline.py` — único módulo que conecta `infrastructure/` y `processing/` (§3.2 de `ARCHITECTURE.md`) |
| `infrastructure/excel` | Implementado y probado: `column_mapping.py`, `importer.py`, `exporter.py` (§8, ver `docs/architecture/EXCEL_PROCESSING.md`) |
| `infrastructure/enrichment` | Vacío (solo `README.md`) — no implementado |
| `infrastructure/logging` | Implementado (parcial): `sqlite_execution_run_store.py` (persistencia local de `ExecutionRun`, ADR-013). Logging técnico operacional (stdout/archivo) sigue sin implementar |
| `infrastructure/persistence` | Implementado, **no verificado contra una base real** (2026-08-17): `supabase_execution_run_store.py` (ADR-017) — sin `supabase`/`psql` disponibles en este entorno, ver `docs/architecture/SUPABASE.md` §1 |
| `interfaces/cli` | Implementado (2026-08-17): `main.py`, entrypoint real que invoca `run_pipeline()` + `export_excel()` |
| `interfaces/api` | Implementado (2026-08-17, Fase 4A): `main.py`/`models.py`/`service.py` (ADR-016, FastAPI), 19 tests. Ver `docs/architecture/API_CONTRACT.md` |
| `interfaces/desktop` | Vacío (solo `README.md`) — `.exe` no se construirá como interfaz principal (ADR-014); sin trabajo planeado |

No implementar contenido de las capas todavía vacías
(`infrastructure/enrichment`, `interfaces/desktop`) sin que exista un
caso de uso concreto que lo requiera (§22 "Fases"). `interfaces/cli`,
`interfaces/api`, `infrastructure/logging` (parcial) e
`infrastructure/persistence` ya no están vacías — ver tabla arriba.

## 7. Modelo de dominio — SourcingRecord

Objetivo arquitectónico: cada fila procesable termina representada como
un `SourcingRecord` que integra `Product` (identificación, info, precio,
demanda, competencia, dimensiones), `CostInputs`, `FeeInputs`,
`RiskProfile`, `ProfitabilityResult`, `DecisionScoreResult`,
`DecisionResult`, `ProcessingIssue[]`.

**Estado real: IMPLEMENTED.** Todos los componentes están implementados y
probados (`domain/product.py`, `domain/costs.py`, `domain/risk.py`,
`domain/decision.py`, `processing/profitability.py`,
`processing/decision_score.py`, `processing/decision_engine.py`), y
`SourcingRecord` como clase ensambladora **ya existe**
(`domain/sourcing_record.py`), como **composición pura** de esos tipos —
nunca redefine ni duplica ninguno de sus campos (ADR-011, `Estado:
Aceptada`). Probado en `tests/unit/test_sourcing_record.py` (7 tests).
Ver `docs/architecture/DATA_MODEL.md` §1-§2. No duplicar ninguno de estos
modelos al construir nuevas features — cualquier acceso a un dato del
registro pasa por composición (`record.product.identification.asin`,
nunca un campo `asin` propio de `SourcingRecord`).

## 8. Excel

Excel es formato de **intercambio** (input/output), nunca el modelo de
dominio (ADR-002). Flujo **IMPLEMENTED**
(`infrastructure/excel/{column_mapping,importer,exporter}.py`, ver
`docs/architecture/EXCEL_PROCESSING.md` para el detalle columna por
columna):

```
Excel → Importer → Parse → Normalize → Validate → SourcingRecord
      → Processing → Result → Exporter → Excel
```

Columnas identificadas siempre **por nombre de encabezado**, nunca por
posición (verificado: `importer.py::normalize_header` +
`column_mapping.py::COLUMN_SPECS`). Los mappings son explícitos. Ninguna
regla de negocio opera directamente sobre celdas/posiciones de Excel —
`processing/pipeline.py` no importa `openpyxl` ni conoce nombres de
columna. Esto es un vertical slice funcional, no el producto completo:
sin enriquecimiento externo, sin IA, sin persistencia entre corridas, sin
interfaz de usuario (ver `docs/PROJECT_STATUS.md`).

## 9. Provenance y estados de verificación

Todo campo sensible (ASIN, weight, dimensions, HazMat, bulky, price, BSR,
sales, competition, fees, profit, ROI, y en general cualquier dato que
alimente Profitability/Decision) se representa como `FieldValue[T]`
(`domain/provenance.py`) — nunca como valor pelado. Implementado,
probado, con invariantes reforzadas en `__post_init__` (no dependen de
disciplina del desarrollador).

Estados (`VerificationStatus`, enum único y excluyente — ADR-004):

- **VERIFIED** — evidencia suficiente de una fuente confiable.
- **INFERRED** — derivado por regla/heurística; siempre con `method`.
- **NOT_FOUND** — sin evidencia suficiente; `value` es obligatoriamente
  `None`. Nunca se convierte en `0` ni en un valor por defecto si eso
  puede alterar un cálculo.
- **INVALID** — hay un valor pero no pasa validación; se conserva
  `raw_value` para diagnóstico.

Nunca presentar INFERRED como VERIFIED. `confidence` es opcional e
informativo — nunca sustituye a `verification_status`
(`docs/architecture/DATA_PROVENANCE.md` §5).

Campos calculados (profit, ROI, margin, score, ...) siguen la regla del
eslabón más débil vía `combine_verification_status`: cualquier insumo
NOT_FOUND/INVALID → resultado NOT_FOUND; algún INFERRED sin missing →
INFERRED; todos VERIFIED → VERIFIED. No reimplementar esta lógica en
otro sitio — reutilizar `domain/provenance.py::combine_verification_status`.

Estructura de `Provenance`: `source`, `source_type`, `verification_status`,
`retrieved_at` (tz-aware, obligatorio), `method`, `confidence?`,
`evidence?`, `source_reference?`. Normativo: ADR-003, ADR-004,
`docs/architecture/DATA_PROVENANCE.md`.

## 10. Cálculos determinísticos

Amazon fees, referral fee, FBA fee, profit, ROI, margin, break-even, max
COG, score, thresholds, decisión: **siempre código determinístico**,
nunca IA (ADR-006). Implementado en `processing/profitability.py`
(funciones puras `Decimal → Decimal`, sin llamadas a ningún modelo) y
`processing/decision_score.py`. Reutilizar el Profitability Engine
existente — no duplicar fórmulas. Si una fórmula es provisional o
simplificada (ej. break-even asume referral fee proporcional al precio),
debe quedar documentada como tal en el propio docstring/`docs/`, no
presentarse como fórmula comercial oficial sin validación.

## 11. Decision Engine y Decision Score

Implementado en `processing/decision_engine.py` sobre
`domain/decision.py`. Precedencia: `pass_rules` (descalificación dura) se
evalúan antes que `review_rules`; si ninguna dispara, BUY. `Thresholds`
no tiene instancia por defecto exportada — el llamador siempre los declara
explícitamente (ADR-007); no crear thresholds comerciales como default en
el motor.

El set de reglas actual (`DEFAULT_PASS_RULES`, `DEFAULT_REVIEW_RULES`) es
un **modelo extensible de reglas, no el conjunto definitivo de negocio**
(`docs/architecture/DECISION_ENGINE.md` §1). No tratarlo como reglas de
negocio finales sin validación explícita.

El **Decision Score** (`processing/decision_score.py`) es experimental:
la fórmula de cada subscore individual (cómo mapear ROI a 0-100, por
ejemplo) no está definida como decisión de negocio
(`DECISION_ENGINE.md` §7). No presentarlo como métrica validada solo
porque los tests pasen — separar "implementación técnica" de "modelo de
scoring aprobado por negocio".

## 12. AI Analyst

Diseño aceptado (ADR-008, `docs/architecture/AI_ANALYST.md`), **sin
código implementado todavía**.

La IA puede: explicar decisiones ya tomadas citando `DecisionReason`
reales, resumir/comparar productos ya procesados, señalar
`ProcessingIssue`s ya detectadas, explicar riesgo citando `RiskFlag`
reales, sugerir priorización, responder preguntas sobre el dataset ya
procesado. Siempre downstream, siempre de solo lectura sobre datos ya
estructurados/calculados.

La IA NO puede: inventar ASIN/peso/HazMat/BSR/ventas/precio/fees,
sustituir `NOT_FOUND`, presentar una inferencia como verificada,
calcular o modificar profit/ROI/margin/break-even/max-COG/score/decisión.
El único `SourceType` que puede producir es `AI_ANALYSIS`, solo para
campos cualitativos explícitos (ej. `PriceDynamics.trend`) — nunca para
un campo del Data Dictionary marcado como sensible.

## 13. Fuentes externas de datos

Seller Assistant y SellerAmp son referencias funcionales, no fuentes
integrables por scraping, API privada, bypass de autenticación o
evasión de rate limits/CAPTCHAs — explícitamente prohibido
(`docs/architecture/DATA_SOURCES.md` §2).

Ninguna integración externa concreta existe todavía
(`infrastructure/enrichment/` solo tiene `README.md`). Antes de
incorporar una fuente externa, documentar en `docs/architecture/DATA_SOURCES.md`:
fuente, método, autorización, campos obtenidos, frecuencia, freshness,
limitaciones, coste, fallback — y el adapter debe vivir en
`infrastructure/enrichment/` implementando un puerto que define
`processing/`, nunca al revés.

**Control de costes**: primero datos propios / Excel / cálculos propios /
fuentes autorizadas ya aprobadas; recién después servicios externos de
pago, y solo evaluando necesidad, coste, volumen, alternativa y ROI. No
introducir una API de pago sin esa evaluación explícita.

## 14. Frontend / Deployment / Persistencia / Auth — mayormente PENDING

⚠️ No asumir Next.js/Tailwind/Vercel/GitHub, framework de backend,
Supabase, ni Clerk como stack ya decidido. **Actualizado 2026-08-17**:
ADR-014 (`Aceptada`) resolvió la elección PWA vs. `.exe` que ADR-005
dejaba pendiente — **PWA elegida** como interfaz principal. ADR-016
aprobó FastAPI como backend (`interfaces/api/` **IMPLEMENTED**, Fase
4A). ADR-017 aprobó Supabase/PostgreSQL como persistencia de
producción (adapter preparado, **no verificado** contra una base real).
React+Vite fue elegido por el usuario para el frontend pero sigue **sin
implementar** (sin Node.js/npm en este entorno) y sin ADR propio.
Vercel fue aprobado como plataforma de deployment objetivo, sin
verificar sus restricciones técnicas reales todavía. Clerk sigue sin
aprobar.

Estado por componente:

| Componente | Estado | Referencia |
|---|---|---|
| PWA como interfaz principal | **APPROVED**, implementado (interfaz elegida) | ADR-014 (`Estado: Aceptada`, 2026-08-17) |
| FastAPI (backend `interfaces/api/`) | **APPROVED**, `interfaces/api/` **IMPLEMENTED** (Fase 4A, 19 tests) | ADR-016 (`Estado: Aceptada`, 2026-08-17) |
| React + Vite (frontend) | **APPROVED** (elección de framework), `interfaces/` frontend **NOT STARTED** — bloqueado por Node.js/npm ausentes, no por decisión pendiente | `docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloque 3) |
| Vercel (deployment) | **APPROVED** como plataforma objetivo, restricciones técnicas reales sin investigar (sin Vercel CLI) | `docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloque 3) |
| Supabase/PostgreSQL | **APPROVED** como persistencia de producción; adapter preparado, **NO verificado contra una base real** — no tratar como equivalente en confianza a SQLite/ADR-013 | ADR-017 (`Estado: Aceptada`, 2026-08-17), `docs/architecture/SUPABASE.md` §1 |
| Clerk | **PENDING** — no implementar mientras el producto funcione sin autenticación; cuando se introduzca, documentar users/sessions/organizations/roles/permissions/data isolation | sin ADR |
| Recomendación técnica de backend (Python 3.11+, `pytest`, `openpyxl`) | Ya en uso (`pyproject.toml`) | `ARCHITECTURE.md` §15 (recomendación, no ADR) |

Cada tecnología de esta lista necesita una razón concreta antes de
instalarse — no instalar solo porque aparece aquí como candidata. Si el
usuario decide fijar alguna de estas piezas, la decisión debe registrarse
como ADR (o al menos como APPROVED explícito en una conversación) antes
de que el agente la trate como base para nuevo código.

## 15. Reproducibilidad — ExecutionRun

**Estructura: IMPLEMENTED** (`domain/execution_run.py::ExecutionRun`,
`ExecutionStatus`, `hash_file`), construida por
`application/run_pipeline.py`. Contiene: `execution_id`, `started_at`/
`finished_at` (tz-aware), `status` (`RUNNING`/`SUCCESS`/
`PARTIAL_SUCCESS`/`FAILED`), `input_filename`, `input_hash` (SHA-256),
`application_version`, y contadores de registros/warnings. Probado en
`tests/unit/test_execution_run.py` (11) y
`tests/integration/test_reproducibility.py` (2, reproducibilidad
demostrada para el caso sin fuentes externas).

**Persistencia entre corridas: NOT IMPLEMENTED.** `ExecutionRun` es
in-memory/local por corrida — no hay historial consultable entre
ejecuciones (`infrastructure/logging/` sigue vacío). No confundir "el
objeto existe y es correcto" con "hay un historial persistido de
corridas pasadas": son afirmaciones distintas (ver
`docs/architecture/EXECUTION_MODEL.md`).

**Gap conocido**: la estructura actual **no** captura `thresholds`
usados ni `sources_used`, a diferencia del diseño original de
`ARCHITECTURE.md` §8/§4.1 — dos corridas con distintos `Thresholds`
producen `ExecutionRun`s indistinguibles salvo por sus decisiones. No se
resuelve automáticamente; requiere una decisión de diseño explícita antes
de ampliar la estructura.

## 16. Seguridad

Nunca: hardcodear secrets, guardar API keys en Git, imprimir tokens en
logs, incluir credenciales en código, confiar ciegamente en archivos
Excel del usuario, ejecutar contenido del usuario como código. Usar
variables de entorno y mecanismos apropiados de secrets. Validar todo
upload. `.gitignore` actual ya excluye `.venv/`, `__pycache__/`, `*.pyc`,
`.pytest_cache/`, `*.egg-info/` — revisar que se mantenga así al agregar
`.env`/credenciales cuando corresponda.

## 17. Testing

Estado real: **209 tests pasando, 0 fallos, 0 skips**
(`.venv/Scripts/python -m pytest -q`) — 138 en `tests/unit/` (14
archivos, sin I/O; incluye 2 tests puramente estructurales de
`SupabaseExecutionRunStore`, ADR-017, sin verificación contra una base
real) + 71 en `tests/integration/` (7 archivos: import/export Excel,
pipeline end-to-end, reproducibilidad, persistencia SQLite de
`ExecutionRun`, CLI, API — `interfaces/api/`, 19 tests, Fase 4A).
`tests/fixtures/` contiene `sample_sourcing_TEST_DATA.xlsx`, ya
poblado. Desglose completo por archivo en
`docs/architecture/TESTING_STRATEGY.md`.

**Nota histórica**: 111 era el número de tests unitarios al cierre de
Fase 1; 165 al cierre de Fase 2 (ADR-012); 177 al cierre de Fase 3
(ADR-013); 188 tras agregar el CLI, el export gap, y el fallback
fail-closed de severidad (ADR-015), antes de Fase 4A (2026-08-17). No
usar ninguno como referencia del estado actual — quedan documentados
aquí solo como datos históricos de cierre de fase.

Ejecutar antes de cerrar cualquier cambio en `domain/`/`processing/`:

```bash
.venv/Scripts/python -m pytest -q
```

Nunca eliminar un test únicamente para reducir código. Un test puede
simplificarse si es redundante, pero debe existir cobertura real de
comportamiento. Ningún test debe ocultar un error para pasar — debe
afirmar que el error se reportó correctamente (`tests/README.md`).

## 18. Documentación y ADR

`docs/adr/` contiene **18 ADRs** (ADR-001 a ADR-018), la mayoría
fechados 2026-08-16, ADR-014 a ADR-018 fechadas 2026-08-17. ADR-001 a
ADR-008 y ADR-010 a ADR-018 están en `Estado: Aceptada`: separación
UI/Core, Excel como intercambio, provenance, estados de verificación,
independencia de diseño PWA/.exe, cálculos determinísticos, thresholds
configurables, límites del AI Analyst, severidad de riesgo por defecto
(provisional, no aprobada por negocio), `SourcingRecord` como
composición, estrategia de `record_ref`, persistencia local de
`ExecutionRun` vía SQLite, **elección de PWA como interfaz principal**
(ADR-014 — no aprueba framework/hosting concreto), **fallback
fail-closed para severidad de riesgo no mapeada** (ADR-015 — decisión
técnica; NO aprueba HAZMAT→HIGH/BULKY→MEDIUM como política comercial,
esos siguen `PENDING`), **FastAPI como backend, `interfaces/api/`
IMPLEMENTED** (ADR-016), **Supabase/PostgreSQL como persistencia de
producción** (ADR-017 — decisión arquitectónica aprobada; el adapter
está preparado pero **no verificado contra una base real**, ver
`docs/architecture/SUPABASE.md` §1 — no tratar como equivalente en
confianza a `SqliteExecutionRunStore`), **Railway como hosting del
backend** (ADR-018 — `railway.toml` preparado, **sin desplegar**, ver
`docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloque 8) para el comando
exacto pendiente). **Solo ADR-009 (Development Loop + Completion Gates)
permanece en `Estado: Propuesta`** — no tratarla como proceso
obligatorio hasta que el usuario la confirme explícitamente (ver
`docs/DEVELOPMENT_LOOP.md`, `docs/PHASE_GATES.md`). **Respetar los ADRs
Aceptados** — si una nueva implementación contradice uno, no ignorarlo:
reportar el conflicto.

Antes de una decisión arquitectónica importante: comprobar si ya existe
documentación en `docs/architecture/` o un ADR en `docs/adr/`; actualizar
la documentación existente o crear un ADR nuevo si corresponde. No
duplicar información entre este archivo y `docs/` — aquí van reglas
operativas, en `docs/` las especificaciones detalladas. Ante discrepancia
entre `docs/` y el código, el código gana y `docs/` se actualiza en el
mismo cambio (regla explícita de `DATA_DICTIONARY.md`).

## 19. Git

No hay `.git` inicializado todavía (decisión pendiente explícita,
`ARCHITECTURE.md` §14.7) — no ejecutar `git init` ni ningún comando Git
destructivo sin autorización explícita del usuario. Cuando exista
repositorio: no commits destructivos, no borrar historial, revisar estado
antes de cambios grandes, nunca incluir `.env`/secrets/credenciales/
archivos temporales/datasets privados grandes.

## 20. Dependencias

Dependencias actuales (`pyproject.toml`): `openpyxl>=3.1` (runtime),
`pytest>=7` (dev). Antes de agregar una dependencia nueva, preguntar en
este orden: ¿código existente? ¿stdlib? ¿una dependencia ya instalada?
¿una solución más simple? Si se agrega, documentar por qué. Evitar
dependencias pequeñas para problemas triviales.

## 21. Code style

Preferir: funciones pequeñas, nombres explícitos, tipos claros
(`Decimal` para dinero, `datetime` tz-aware para timestamps),
responsabilidades únicas, composición, código legible. Evitar:
abstracciones prematuras, factories innecesarias, wrappers sin valor,
interfaces "por si acaso", patrones enterprise sin necesidad. El código
actual (`domain/`, `processing/`) ya sigue este estilo — mantenerlo como
referencia de tono al escribir código nuevo.

## 22. Fases

No implementar funcionalidad de fases futuras solo porque sea fácil de
añadir (ver capas todavía vacías en §6: `infrastructure/enrichment`,
`interfaces/desktop`). Si aparece una mejora fuera de alcance durante
una tarea, registrarla como **FUTURE / PENDING** en el reporte final,
no implementarla automáticamente. Excepciones ya evaluadas y
ejecutadas: `interfaces/cli` (2026-08-17, ver `docs/PROJECT_STATUS.md`
§Sesión 2026-08-17) e `interfaces/api` (2026-08-17, Fase 4A —
framework backend explícitamente aprobado por el usuario, ADR-016,
antes de implementar).

## 23. Workflow obligatorio

1. Inspect
2. Understand
3. Plan
4. Implement
5. Test
6. Review
7. Ponytail review cuando corresponda
8. Self-review
9. Document
10. Report

## 24. Self-review obligatorio (antes de cerrar tarea importante)

- **Correctness** — ¿el comportamiento es correcto?
- **Traceability** — ¿se puede saber de dónde salió cada dato relevante?
- **Reproducibility** — ¿se puede repetir la ejecución?
- **Architecture** — ¿se respetan las capas (§6, ADR-001)?
- **Security** — ¿hay secretos o vulnerabilidades?
- **Tests** — ¿hay pruebas suficientes? ¿pasa `pytest`?
- **Simplicity** — ¿hay código innecesario?
- **Ponytail** — ¿hay sobreingeniería?
- **Documentation** — ¿`docs/`/ADR reflejan el estado real?

## 25. No confundir — flujo de datos

```
DATA → CALCULATION → RISK → DECISION → AI EXPLANATION
```

Nunca: `DATA → AI → "parece buen producto"`. La IA nunca sustituye
`CALCULATION`, `RISK` ni `DECISION` — solo explica lo que esas capas ya
produjeron (§12, ADR-006, ADR-008).

## 26. Estados de trabajo

Toda tarea importante termina indicando uno de:

- **IMPLEMENTED**
- **PARTIALLY IMPLEMENTED**
- **BLOCKED**
- **PENDING DECISION**

No declarar "complete" si existe una dependencia crítica pendiente.

## 27. Reporte final obligatorio

Al terminar una tarea importante, reportar: **Estado**, **Archivos**
(creados/modificados), **Tests** (qué se ejecutó y resultado),
**Decisiones** (tomadas, con APPROVED/PENDING), **Riesgos**,
**Pendientes**, **Ponytail** (si se ejecutó revisión y qué halló),
**Próximo paso**.

## 28. Principio final

Juval debe ser SIMPLE + CORRECTO + TRAZABLE + REPRODUCIBLE + AUDITABLE +
ESCALABLE. No buscamos más código ni menos código — buscamos exactamente
la complejidad necesaria para resolver correctamente el problema.
