# Juval — Phase Completion Gates

Normativo. Checklist de cierre que determina si una fase (o una tarea
importante dentro de una fase) puede declararse `COMPLETE`, según el
Development Loop (`docs/DEVELOPMENT_LOOP.md`, Step 9). Ninguna fase se
declara completa solo porque exista código — debe pasar este gate
explícitamente y quedar reportado (Step 10 del loop).

## 1. Universal Completion Gate

Aplica a **toda** fase y a toda tarea importante dentro de una fase.
Cada ítem se reporta individualmente como `PASS` / `FAIL` / `BLOCKED` en
el reporte final — no como un veredicto único agregado.

| # | Criterio | Cómo se verifica |
|---|---|---|
| 1 | Criterios de aceptación de la fase (`PROJECT_PLAN.md`) | Comparación explícita, criterio por criterio |
| 2 | Tests pasan | `pytest` (u otro runner aplicable) sin fallos |
| 3 | Build pasa | Build/typecheck/lint sin errores, cuando aplique |
| 4 | Sin conflictos arquitectónicos críticos | Step 7 (Architectural Review) del Development Loop, sin hallazgos sin resolver |
| 5 | Sin hallazgos de seguridad críticos sin resolver | Revisión de secrets/uploads/dependencias (`CLAUDE.md` §16) |
| 6 | Documentación actualizada | `docs/` y `CLAUDE.md` reflejan el código real, no una versión anterior |
| 7 | Provenance preservada | Ningún dato sensible perdió su `FieldValue`/`Provenance` en el cambio |
| 8 | Sin dependencias externas no autorizadas | Ninguna librería, API o fuente de datos nueva sin justificación documentada |
| 9 | Revisión Ponytail completada donde corresponda | `/ponytail-review` ejecutado en diffs grandes; sin hallazgo de sobreingeniería sin resolver o reportado como excepción justificada |

Si **cualquier** ítem es `FAIL` o `BLOCKED`, el estado de la fase/tarea
es `PARTIALLY IMPLEMENTED` o `BLOCKED` (nunca `COMPLETE`).

## 2. Gates específicos por fase

Extienden (no reemplazan) el Universal Gate de §1. Incluyen, cuando
aplica, el resultado real de haber evaluado el gate contra el estado
actual del repositorio (2026-08-16) — no son solo criterios futuros.

### Fase 0 — Foundation / Repository / Documentation
**Estado del gate: PASS**
- Esqueleto de directorios con `README.md` de propósito en cada carpeta — verificado.
- ADR-001 a ADR-005 en estado Aceptada — verificado.

### Fase 1 — Domain + Processing Core
**Estado del gate: PASS**
- Todas las invariantes estructurales de `DATA_MODEL.md` §4 verificadas por `__post_init__` y cubiertas por al menos un test — verificado.
- `combine_verification_status` es la única implementación de la regla del eslabón más débil — verificado.

### Fase 2 — SourcingRecord + Excel Vertical Slice
**Estado del gate: PASS** (evaluado formalmente 2026-08-16; todos los
criterios obligatorios en `PASS`, ver `docs/RECONCILIATION_REPORT.md`
para la evidencia de reconciliación previa y ADR-012 para el cierre del
único ítem que quedaba en `FAIL`)

Extensiones específicas de esta fase:
- Round-trip test Excel → `SourcingRecord` → Excel — **PASS**
  (`tests/integration/test_pipeline_end_to_end.py`, `test_excel_importer.py`, `test_excel_exporter.py`, 23 tests entre las tres).
- Columnas identificadas por nombre, no posición — **PASS**
  (`importer.py::normalize_header` + `column_mapping.py`).
- Al menos un caso de test por nivel de `ProcessingIssue` — **PASS**
  (`test_excel_importer.py` cubre `MISSING_REQUIRED_COLUMN` FATAL, varios `RECORD_ERROR`, `UNKNOWN_COLUMN`/`DUPLICATE_COLUMN` WARNING).
- Excel exportado expone columnas de provenance (`<campo>`/`<campo>_status`) separadas del valor — **PASS**
  (`exporter.py::HEADERS`).
- `record_ref` tiene una estrategia documentada y **aprobada** para el caso sin SKU confiable — **PASS**: la estrategia implementada (`row_{n}[:supplier_sku]`) queda formalmente documentada y aprobada por ADR-012 (`Estado: Aceptada`, 2026-08-16) — sin cambio de código, solo formalización de la decisión existente.
- Universal Gate ítem 6 (documentación actualizada) — **PASS** (re-evaluado en `docs/RECONCILIATION_REPORT.md`): `README.md` raíz y `DATA_MODEL.md` §1/§5 describen correctamente esta fase como implementada; una versión anterior de este documento afirmaba lo contrario, verificado como incorrecto contra el contenido real de ambos archivos.
- Universal Gate ítem 4 (sin conflictos arquitectónicos) — **PASS** (re-evaluado en `docs/RECONCILIATION_REPORT.md` §6): las dos referencias de ADR que este ítem marcaba como colisionadas/inexistentes (`sourcing_record.py` → "ADR-009", `importer.py` → "ADR-010") ya están resueltas — el código actual cita "ADR-011" y "ADR-010" respectivamente, y ambos ADRs existen con `Estado: Aceptada` y el contenido correcto. Ver §3 abajo (histórico).
- CLI entrypoint (`interfaces/cli/`) — no era un criterio universal ni un criterio específico de Fase 2 (`ARCHITECTURE.md` §15 lo recomendaba, sin ser bloqueante para este gate). Implementado 2026-08-17, después del cierre de este gate, como trabajo de categoría A independiente (ver `docs/PROJECT_STATUS.md` §Sesión 2026-08-17) — no reabre ni modifica el veredicto `PASS` ya emitido para Fase 2.

### Fase 3 — Data Quality + ExecutionRun + Auditability
**Estado del gate: PASS — evaluado formalmente 2026-08-16.** Las dos
decisiones que quedaban abiertas están ambas resueltas explícitamente
por el usuario: (a) mecanismo de persistencia = SQLite local, ADR-013
**Aceptada** 2026-08-16; (b) `run_pipeline()` no integra persistencia
automática (Opción B, 2026-08-16) — decisión arquitectónica deliberada,
no una brecha. Todos los criterios obligatorios (Universal Gate + los
específicos de esta fase, listados abajo) están en `PASS`. **Fase 3
declarada `COMPLETE`.**

Universal Gate (§1), re-evaluado completo para esta fase:
1. Criterios de aceptación (`PROJECT_PLAN.md` §Fase 3) — **PASS**.
2. Tests pasan — **PASS** (177 passed, 0 failed, 0 skipped).
3. Build/typecheck — **PASS** (N/A, sin configuración de build en el repo).
4. Sin conflictos arquitectónicos críticos — **PASS** (`domain/` libre de `sqlite3`/SQL/filesystem; `processing/` libre de imports de `infrastructure/`; dirección de dependencia respetada — ADR-001).
5. Sin hallazgos de seguridad críticos — **PASS** (sin secrets; consultas SQL parametrizadas, sin concatenación).
6. Documentación actualizada — **PASS** (`ARCHITECTURE.md`, `EXECUTION_MODEL.md`, `PROJECT_STATUS.md`, `PROJECT_PLAN.md`, `TESTING_STRATEGY.md`, `CLAUDE.md` reconciliados con ADR-013 `Aceptada` en este mismo cambio).
7. Provenance preservada — **PASS** (N/A — `ExecutionRun` no maneja `FieldValue`).
8. Sin dependencias externas no autorizadas — **PASS** (`sqlite3` stdlib, cero dependencia nueva).
9. Revisión Ponytail completada — **PASS** (`/ponytail-review` ejecutado sobre el diff de persistencia en la sesión de implementación — "Lean already. Ship."; sin código nuevo desde entonces que requiera repetirla).

Criterios específicos de Fase 3:
- Test de reproducibilidad explícito (mismo input + misma versión + sin fuentes externas ⇒ resultado idéntico) — **PASS**
  (`tests/integration/test_reproducibility.py`).
- `ExecutionRun` contiene los campos mínimos (`execution_id`, `started_at`, `finished_at`, `status`, `input_filename`, `input_hash`, `application_version`, conteos) — **PASS**
  (`domain/execution_run.py`).
- Persistencia de `ExecutionRun` a través de corridas — **PASS**: `infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore` implementa el puerto `ExecutionRunStore` (ADR-013, `Aceptada`), probado con 12 tests de integración incluyendo round-trip entre conexiones/instancias de store distintas (`tests/integration/test_execution_run_store.py`). `run_pipeline()` no la invoca automáticamente por decisión arquitectónica deliberada (Opción B) — una interfaz operativa real (CLI/API, Fase 4) será responsable de su propia política de invocación cuando exista.
- Universal Gate ítem 6 (documentación actualizada) — **PASS**: `ARCHITECTURE.md` §8 y `EXECUTION_MODEL.md` §5 actualizados 2026-08-16 para describir el estado real (SQLite implementado, alcance y limitaciones explícitas), reemplazando la descripción de persistencia en JSON que el código nunca implementó.

### Fase 4 — Dashboard PWA
**Estado del gate: PENDING** (backend y frontend implementados y
probados, 2026-08-17 bloque 4; Fase 4 global no se declara `COMPLETE`
hasta deployment real + Supabase verificado + resto del gate)
- Elección de interfaz (PWA vs. `.exe`) — **RESUELTO** 2026-08-17 vía
  ADR-014 (`Estado: Aceptada`): PWA.
- Framework de backend — **RESUELTO** 2026-08-17 vía ADR-016
  (`Estado: Aceptada`): FastAPI, implementado, 19 tests.
- Framework de frontend — **RESUELTO e IMPLEMENTED** 2026-08-17
  (bloque 4): React + Vite + PWA (`frontend/`), 9 tests, `npm run build`
  exitoso.
- Deployment del frontend (Vercel) — **aprobado como plataforma
  objetivo**, CLI instalada, `frontend/vercel.json` preparado; **sin
  desplegar** (`vercel login` requiere interacción del usuario). Sigue
  bloqueando el cierre del gate global.
- Hosting del backend (Railway) — **RESUELTO/aprobado** 2026-08-17
  (bloque 8) vía ADR-018 (`Estado: Aceptada`): Railway, tras
  comparación explícita con Render/Fly.io/VPS. CLI instalada,
  `railway.toml` preparado; **sin desplegar** (`railway login` requiere
  interacción del usuario). Vercel Functions descartado explícitamente
  para el backend (incompatibilidad real verificada, `API_CONTRACT.md`
  §8.4). Sigue bloqueando el cierre del gate global.
- Persistencia de producción (Supabase) — **aprobada** (ADR-017),
  adapter preparado; **sin verificar contra un proyecto real**
  (`supabase login` requiere interacción del usuario). Sigue
  bloqueando el cierre del gate global.
- Git/GitHub — repositorio local inicializado, sin commit (bloqueo de
  `git config`, ver `docs/PROJECT_STATUS.md` §Sesión 2026-08-17
  (bloque 4)); sin remoto GitHub configurado. Sigue bloqueando el
  cierre del gate global.
- Ningún componente de UI debe contener una regla de negocio —
  **verificado para backend y frontend** (`interfaces/api/service.py` y
  `frontend/src/` revisados línea por línea: sin cálculos de negocio en
  ninguno de los dos).
- Test E2E del camino feliz contra un `ExecutionRun` real de Fase 3 —
  **PASS**, `frontend/e2e/smoke.spec.ts`, contra el backend real (no
  mock), 1/1.

### Fase 5 — Decision Intelligence
**Estado del gate: BLOCKED**
- Gate previo bloqueante: cada fórmula de subscore tiene una aprobación de negocio documentada.
- `DECISION_ENGINE.md` deja de marcar el Decision Score como experimental, actualizado en el mismo cambio que el código.
- Caso límite `severity == maximum_risk_severity` con comportamiento definido y probado.

### Fase 6 — Authorized External Data Sources
**Estado del gate: BLOCKED**
- Gate previo bloqueante: checklist de `DATA_SOURCES.md` §4 documentado *antes* de que exista código del adapter.
- Test explícito: el adapter nunca marca `VERIFIED` un dato no garantizado por la fuente.
- Test explícito: un "no encontrado" de la fuente nunca se traduce en un valor por defecto.

### Fase 7 — AI Analyst
**Estado del gate: BLOCKED**
- Gate previo bloqueante: proveedor de IA aprobado; diseño de auditoría de llamadas aprobado.
- Suite de "contract tests" al 100%: la IA nunca produce un valor numérico que sustituya profit/roi/margin/score/decision; nunca inventa un campo `NOT_FOUND`.
- Cada llamada de IA queda registrada de forma auditable (verificado por un test).

### Fase 8 — Persistence / Supabase
**Estado del gate: BLOCKED**
- Gate previo bloqueante: aprobación explícita de Supabase + necesidad real (no especulativa) documentada.
- Ninguna tabla del esquema corresponde a un concepto no implementado en el dominio.
- Test de aislamiento de datos si aplica; si no, explícitamente fuera de scope y anotado como tal.

### Fase 9 — Authentication / Authorization
**Estado del gate: BLOCKED_PENDING_AMAZON_RESPONSE**
- Gate previo bloqueante: Clerk fue descartado (ver ADR-022); ningún IdP está
  aprobado. Aclaración enviada a Amazon Developer Support sobre passwordless/
  MFA/enforcement de contraseña — respuesta pendiente (`docs/compliance/SP_API_REGISTRATION_REMEDIATION.md`
  §21). El gate se mantiene bloqueado hasta que exista respuesta de Amazon y
  un proveedor aprobado + documento de diseño de auth antes del código.
- Test de aislamiento de datos: usuario A no puede acceder a datos de usuario B bajo ninguna ruta.
- Test de permisos por rol.

### Fase 10 — Production Hardening
**Estado del gate: BLOCKED**
- Regresión completa (unit + integration + E2E) sin fallos nuevos.
- Revisión de seguridad completada sin hallazgos críticos/altos sin resolver.
- Plan de rollback documentado.
- Todos los Completion Gates de fases anteriores siguen en `PASS` (sin regresión de un gate ya cerrado).

## 3. Contradicción de numeración de ADR — RESUELTA (histórico)

Una versión anterior de este documento, al evaluar el gate de Fase 2,
encontró dos referencias en código a ADRs que en ese momento no
documentaban la decisión que decían documentar:

| Referencia en código (en ese momento) | Archivo | Decisión que debería documentar | Estado en ese momento |
|---|---|---|---|
| "See ADR-009" | `src/juval/domain/sourcing_record.py:8` | Composición de `SourcingRecord` (no duplicar campos de `Product`/`CostInputs`/etc.) | ADR-009 documentaba el Development Loop — colisión de numeración |
| "See ADR-010" | `src/juval/infrastructure/excel/importer.py:46` | Severidad por defecto (`DEFAULT_RISK_SEVERITY`) para riesgos declarados por el proveedor sin severidad propia | ADR-010 no existía — referencia colgante |

**Estado actual (verificado en `docs/RECONCILIATION_REPORT.md` §6,
directamente contra el código fuente): ambas referencias están
resueltas.** `domain/sourcing_record.py:8` cita "ADR-011", que existe
(`Estado: Aceptada`) y documenta exactamente la decisión de composición.
`infrastructure/excel/importer.py:46` cita "ADR-010", que también existe
(`Estado: Aceptada`) y documenta exactamente la severidad por defecto
provisional. ADR-010 y ADR-011 se crearon dentro de la misma sesión de
trabajo en que se detectó originalmente este problema, corrigiendo tanto
los ADRs faltantes como los comentarios de código — pero esta sección no
se había actualizado para reflejarlo hasta ahora. No queda ninguna
acción de código pendiente por este motivo; la aprobación de negocio de
los *valores* de `DEFAULT_RISK_SEVERITY` en sí (no la referencia de ADR)
sigue pendiente, ver `PROJECT_PLAN.md` §Fase 2.

## 4. Qué hacer si un gate falla

Ver Development Loop Step 8 (Fix Loop): volver a
`FIX → TEST → PONYTAIL REVIEW → SELF-REVIEW → ARCHITECTURAL REVIEW`
hasta resolver el ítem que falló, y volver a evaluar el gate completo —
no solo el ítem que falló, porque una corrección puede introducir una
regresión en otro ítem ya `PASS`.

Si un ítem depende de una decisión PENDING que el agente no puede tomar,
el gate se reporta como `BLOCKED`, no `FAIL` — la diferencia importa:
`FAIL` implica que el trabajo está mal hecho, `BLOCKED` implica que falta
una decisión externa antes de poder intentarlo correctamente. Los
hallazgos de Fase 2/3 en este documento son, en su mayoría, `FAIL` de
proceso (documentación no actualizada, decisión implementada sin
aprobación registrada) más que `BLOCKED` — el trabajo técnico existe y
funciona, lo que falta es cerrar el loop correctamente sobre él.
