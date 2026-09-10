# AGENTS.md — Contrato operativo de Juval

Este archivo es el contrato operativo permanente para Codex/Codex
trabajando en el proyecto Juval. Se aplica a **todo** el trabajo en este
repositorio. Contiene reglas operativas; las especificaciones detalladas
viven en `docs/` (arquitectura) y `docs/adr/` (decisiones). Si algo aquí
parece contradecir `docs/`, **`docs/` y el código ganan** — reportar la
discrepancia y corregir este archivo, no al revés.

Estado operativo actualizado 2026-09-10: el workspace autoritativo es
`/home/juval/JUVAl/APP`, con Git e historial en `master`. El estado actual,
evidencia, bloqueos y procedimiento humano están centralizados en
[`docs/IDENTITY_SECURITY_READINESS.md`](docs/IDENTITY_SECURITY_READINESS.md).
Fase activa: identidad/seguridad, PARTIALLY IMPLEMENTED, producción no activada.
Tenant y aplicación exactos existen; nombres/roles no re-verificados. No recrear.
N-1 corregido en plantilla/lab; real login y D-1 siguen NOT_VERIFIED.
Frontend existente y congelado (`frontend/`, `frontend-next/`, `demo/`), con
excepción autorizada solo para remediación mínima de vulnerabilidades confirmadas.
No usar recuentos históricos de tests, estados de instalación o marcadores
literales como evidencia actual. Ver mediciones fechadas en PROJECT_STATUS.

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

El agente (Codex/Codex) inspecciona, diseña cuando corresponde,
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

El proyecto declara Ponytail (`ponytail@ponytail`); verificar su disponibilidad
en cada entorno. No afirmar revisión ejecutada si no hay herramienta/skill;
registrar la limitación y hacer revisión manual de simplicidad. **Modo
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

**Estado actual:** el código vive bajo `src/juval/`. Domain y processing
implementan modelos, cálculos y decisiones determinísticos. Application conecta
puertos y adaptadores; infraestructura implementa Excel/CSV, SQLite,
Supabase/PostgreSQL y sesiones cifradas; interfaces CLI y FastAPI/BFF existen.
React/Vite PWA existe. Enrichment e IA no se implementan sin fuente/caso aprobado;
desktop no es la interfaz principal. Los detalles de archivos y verificación se
consultan en `docs/` y código, no en un inventario duplicado aquí.

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
sin enriquecimiento externo ni IA; la persistencia y la interfaz ya existen
(ver `docs/PROJECT_STATUS.md`).

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

## 14. Stack aprobado y activación

PWA (ADR-014), FastAPI (ADR-016), React/Vite, Supabase/PostgreSQL
(ADR-017/019), Railway backend (ADR-018), Vercel frontend y FusionAuth
(ADR-028/031) son decisiones aprobadas. BFF (ADR-034), Control 6 con residual
(ADR-035), sesiones duraderas (ADR-036) y endurecimiento nginx (ADR-037)
están implementados/probados con el alcance de cada ADR. No equiparar esto
con producción activa. Clerk/Okta no son trabajo pendiente a implementar.

Topología same-site app/api/id aprobada (ADR-038). Dominio concreto, túnel/TLS,
migración live de sesiones, pruebas humanas RF03 y envío Amazon
siguen bloqueados. No desplegar ni migrar producción implícitamente. Frontend
permanece congelado hasta autorización o cierre del gate aplicable.

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

**Persistencia entre corridas: IMPLEMENTED.** SQLite (ADR-013) y
Supabase/PostgreSQL para runs/records (ADR-017/019); no confundir esta
persistencia con la migración de sesiones (ADR-036), todavía no aplicada a
producción. Las verificaciones reales históricas viven en `docs/`.

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

Ejecutar `.venv/bin/python -m pytest -q` antes de cerrar cambios en Domain o
Processing y en milestones. Informar resultados medidos y razones de skips;
no convertir skips en evidencia. Usar focused tests por cambio y gate amplio
antes de commit/push según alcance. Nunca ocultar fallos o eliminar un test
para reducir código; simplificar redundancia conservando cobertura real.

Sesiones: `tools/session_store_lab.py` usa PostgreSQL desechable;
`JUVAL_TEST_SESSION_DB_URL` es exclusivo para sus tests, nunca DSNs de runtime.
No aplicar migraciones live mediante tests. Nginx: lab desechable con
`JUVAL_NGINX_BIN`; sin él, tests behaviorales se saltan y no están verificados.

## 18. Documentación y ADR

Consultar el estado explícito del ADR antes de usarlo como autoridad. ADR-009,
ADR-021 y ADR-033 siguen Propuesta; ADR-038/039/040 Aceptadas; ADR-022 RECHAZADA/SUPERSEDED;
ADR-027 enmendada por ADR-031. Respetar alcance/enmiendas de los Aceptados;
no convertir una propuesta en aprobación porque resulte conveniente.
Estado/evidencia central en `docs/IDENTITY_SECURITY_READINESS.md`; snapshots
fechados son históricos, no una autorización de producción.

Antes de una decisión arquitectónica importante: comprobar si ya existe
documentación en `docs/architecture/` o un ADR en `docs/adr/`; actualizar
la documentación existente o crear un ADR nuevo si corresponde. No
duplicar información entre este archivo y `docs/` — aquí van reglas
operativas, en `docs/` las especificaciones detalladas. Ante discrepancia
entre `docs/` y el código, el código gana y `docs/` se actualiza en el
mismo cambio (regla explícita de `DATA_DICTIONARY.md`).

## 19. Git

Git inicializado con historial y remoto GitHub. Verificar estado antes de
cambiar. Commits atómicos; sin reescritura, rebase, force-push ni secretos.
Durante el accelerator el usuario autoriza commits y push fast-forward desde
Linux tras tests/compliance/secret scan y fetch que pruebe remote-only=0.
La autenticación SSH del operador es una acción local; nunca pedir su clave o
passphrase. Un fallo de fetch impide afirmar sincronización con el remoto.

## 20. Dependencias

Dependencias vigentes: `pyproject.toml` y lockfiles de cada frontend;
no duplicar versiones aquí. FastAPI/uvicorn/multipart, PyJWT/cryptography y el
extra PostgreSQL ya existen además de openpyxl y herramientas de tests.
Antes de agregar una dependencia nueva, preguntar en
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
