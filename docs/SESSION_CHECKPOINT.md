# Juval — Session Checkpoint

## Fecha
2026-08-16

## Nota de discrepancia (leer primero)

El prompt de cierre de esta sesión pedía registrar Phase 3 como
`NOT STARTED / PENDING`. **Eso no coincide con el estado real
verificado del repositorio.** En esta misma sesión (antes de la
solicitud de cierre) el usuario aprobó explícitamente ADR-013
(persistencia de `ExecutionRun` vía SQLite) y confirmó la decisión
arquitectónica "Opción B" (`run_pipeline()` sin persistencia
automática). Con ambas decisiones tomadas, se re-evaluó formalmente el
Completion Gate completo de Fase 3 (`docs/PHASE_GATES.md` §Fase 3) y
**todos los criterios obligatorios quedaron en `PASS`** — por eso Fase 3
se declaró `COMPLETE`, no `NOT STARTED`. Este checkpoint registra el
estado real (verificado por inspección directa de `docs/adr/`, tests, y
`docs/PHASE_GATES.md`), no el estado presupuesto por el prompt de
cierre. Si Fase 3 debe tratarse como reabierta o revertida a
`PENDING` por alguna razón de negocio, esa es una decisión explícita
que el usuario debe tomar en una futura sesión — no se asume aquí.

## Estado del proyecto

| Fase | Estado |
|---|---|
| Phase 0 — Foundation | **COMPLETE** |
| Phase 1 — Domain + Processing Core | **COMPLETE** |
| Phase 2 — SourcingRecord + Excel Vertical Slice | **COMPLETE** (gate `PASS`, 2026-08-16, cerrado vía ADR-012) |
| Phase 3 — Data Quality + ExecutionRun + Auditability | **COMPLETE** (gate `PASS`, 2026-08-16, cerrado vía ADR-013 + decisión "Opción B") |
| Phase 4 — Dashboard/PWA | NOT STARTED — BLOCKED (ADR-005, stack frontend `PENDING`) |
| Phase 5 — Decision Intelligence | NOT STARTED — BLOCKED (fórmulas de negocio no aprobadas) |
| Phase 6 — Authorized External Data Sources | NOT STARTED — BLOCKED (fuente concreta no aprobada) |
| Phase 7 — AI Analyst | NOT STARTED — BLOCKED (proveedor de IA no aprobado) |
| Phase 8 — Persistence/Supabase | NOT STARTED — BLOCKED (Supabase `PENDING`) |
| Phase 9 — Auth | NOT STARTED — BLOCKED (Clerk `PENDING`) |
| Phase 10 — Production Hardening | NOT STARTED — BLOCKED |

## Estado de ADRs

| ADR | Estado |
|---|---|
| ADR-001 — Separación UI/Processing Core | Aceptada |
| ADR-002 — Excel como formato de intercambio | Aceptada |
| ADR-003 — Provenance de datos | Aceptada |
| ADR-004 — Estados de verificación | Aceptada |
| ADR-005 — Independencia PWA/.exe | Aceptada (diseño; elección PWA vs .exe sigue sin tomarse) |
| ADR-006 — Cálculos financieros determinísticos | Aceptada |
| ADR-007 — Thresholds configurables | Aceptada |
| ADR-008 — Límites del AI Analyst | Aceptada |
| ADR-009 — Development Loop + Completion Gates | **Propuesta** — no confirmada por el usuario |
| ADR-010 — Severidad de riesgo provisional | Aceptada |
| ADR-011 — SourcingRecord composición | Aceptada |
| ADR-012 — Estrategia de `record_ref` | **Aceptada** — confirmado por inspección directa de `docs/adr/ADR-012-record-ref-estrategia.md` esta sesión |
| ADR-013 — Persistencia de `ExecutionRun` vía SQLite | Aceptada — aprobada explícitamente por el usuario 2026-08-16 (fuera del alcance de ADR-009 a ADR-012 que pedía verificar el prompt de cierre, se incluye aquí porque es parte del estado real actual) |

**13 ADRs totales. Solo ADR-009 permanece en `Propuesta`.**

## Tests

```
.venv/Scripts/python -m pytest -q
........................................................................ [ 40%]
........................................................................ [ 81%]
.................................                                        [100%]
177 passed in 1.00s
```

0 failed, 0 skipped. Sin `.git` inicializado (confirmado: `git status` falla con "not a git repository").

## Trabajo completado hoy

- Reconstrucción completa de contexto del proyecto (documentación, ADRs, código, tests) desde cero.
- Ponytail Audit sobre `domain/`, `processing/`, `infrastructure/` — sin hallazgos de eliminación segura.
- ADR-012 creado y aprobado (`record_ref`, estrategia `row_{n}[:supplier_sku]` formalizada sin cambios de código).
- Phase 2 Completion Gate evaluado formalmente y cerrado — **COMPLETE**.
- Análisis arquitectónico de persistencia de `ExecutionRun` (pre-check Fase 3, comparación de alternativas).
- Implementación de persistencia local de `ExecutionRun` vía SQLite: `ExecutionRunStore` (puerto), `SqliteExecutionRunStore` (adapter), 12 tests nuevos de integración.
- ADR-013 creado (Propuesta), analizado el impacto de integrarlo en `run_pipeline()`, y decidido explícitamente por el usuario: Opción B (sin integración automática).
- ADR-013 aprobado explícitamente por el usuario → `Aceptada`.
- Phase 3 Completion Gate evaluado formalmente y cerrado — **COMPLETE**.
- Reconciliación documental completa (9 archivos) para eliminar referencias desactualizadas a `ADR-013: Propuesta` tras su aprobación.

## Decisiones aprobadas

No volver a discutir sin nueva instrucción explícita del usuario:

- `record_ref` = `row_{excel_row_number}[:supplier_sku]` (ADR-012). No global, no persistente entre corridas.
- `SourcingRecord` es composición pura (ADR-011) — nunca duplicar campos.
- `DEFAULT_RISK_SEVERITY` (HAZMAT→HIGH, BULKY→MEDIUM) es mecanismo aprobado (ADR-010); **los valores en sí siguen pendientes de aprobación de negocio** (ver Technical Debt).
- Persistencia de `ExecutionRun`: SQLite local (ADR-013, Aceptada).
- `run_pipeline()` **NO** integra persistencia automática — persistir es responsabilidad explícita del caller (Opción B, aprobada 2026-08-16). No requiere ADR-014.
- CLI ausente = deuda técnica `DEFERRED`, no bloqueante para ningún gate ya cerrado.

## Decisiones pendientes

Requieren aprobación explícita del usuario, nunca inventarlas:

- ADR-009 (Development Loop + Completion Gates) — confirmación pendiente.
- Aprobación de negocio de los valores de `DEFAULT_RISK_SEVERITY`.
- PWA vs. `.exe` (ADR-005 acepta el diseño independiente; la elección sigue sin tomarse).
- Stack frontend (Next.js/Tailwind/Vercel) — sin ADR.
- Supabase (persistencia compartida/remota, Fase 8).
- Clerk (autenticación, Fase 9).
- Fuente(s) externa(s) de enriquecimiento (Fase 6).
- Proveedor/modelo de IA para el AI Analyst (Fase 7).
- Fórmulas de subscore de Decision Score y thresholds comerciales reales (Fase 5).
- Si `ExecutionRun` debe ampliarse con `thresholds`/`sources_used` — no decidido.
- Política de invocación de `save_execution_run()` cuando exista una interfaz real (CLI/API, Fase 4) — diferida, no decidida.

## Technical Debt

1. `DecisionScoreResult` implementado pero no integrado en `pipeline.py` — asignado a Fase 5.
2. `ExecutionRun` no captura `thresholds` ni `sources_used` — gap de diseño conocido.
3. Solo 2 de 14 `RiskType` tienen fuente de datos (HAZMAT, BULKY, ambos desde Excel).
4. `DEFAULT_RISK_SEVERITY` valores sin aprobación de negocio (mecanismo sí aprobado, ADR-010).
5. CLI ausente (`interfaces/cli/` solo `README.md`) — no bloqueante, pero recomendado por `ARCHITECTURE.md` §15.
6. `run_pipeline()` no invoca `SqliteExecutionRunStore` automáticamente — decisión deliberada (Opción B), no una brecha, pero significa que la auditoría es opt-in hasta que exista una interfaz real.
7. `max_cog_target_profit`/`max_cog_target_roi` calculados pero no exportados a Excel.
8. `validate_freshness()`/`validate_source()` implementados pero no invocados desde `pipeline.py`.
9. `SourcingRecord.with_*()` helpers tienen tests pero `pipeline.py` usa `dataclasses.replace()` directamente — inconsistencia docstring/implementación sin resolver.
10. `SizeType`/`StockStatus`/`PriceDynamics`/`Identification.sku` — forward-modeling de Fase 1 sin consumidores; Fase 1 ya con gate `PASS`, no relitigar sin autorización.

## Phase 2

**COMPLETE.** Completion Gate evaluado formalmente 2026-08-16 — todos los criterios obligatorios (Universal Gate + extensiones específicas de Fase 2) en `PASS`. El único criterio que estaba en `FAIL` (`record_ref` sin decisión arquitectónica aprobada) se cerró mediante ADR-012, sin cambios de código — solo formalización de la estrategia ya implementada. Ver `docs/PHASE_GATES.md` §Fase 2.

## Phase 3

**COMPLETE** — no `NOT STARTED / PENDING` como pedía el prompt de cierre de esta sesión (ver "Nota de discrepancia" arriba). Completion Gate evaluado formalmente 2026-08-16 — todos los criterios obligatorios en `PASS`: persistencia de `ExecutionRun` implementada y probada (SQLite, ADR-013 Aceptada), reproducibilidad estructural probada, campos mínimos presentes, documentación reconciliada. La integración automática con `run_pipeline()` quedó resuelta explícitamente como "no" (Opción B) — es una decisión arquitectónica tomada, no un criterio pendiente. Ver `docs/PHASE_GATES.md` §Fase 3.

## Próximo objetivo

No hay trabajo pendiente de Fase 2 ni de Fase 3. La primera tarea de la
próxima sesión debe ser: **presentar al usuario las decisiones
bloqueantes pendientes** (lista en "Decisiones pendientes" arriba) para
que elija cuál resolver primero — ninguna fase posterior (4 en
adelante) puede avanzar sin que el usuario resuelva explícitamente al
menos una. No iniciar código de ninguna fase nueva sin esa decisión
previa.

## Archivos relevantes

Leer antes de cualquier cambio en la próxima sesión:

- `CLAUDE.md`
- `docs/SESSION_CHECKPOINT.md` (este archivo)
- `docs/PROJECT_STATUS.md`
- `docs/PROJECT_PLAN.md`
- `docs/PHASE_GATES.md`
- `docs/adr/` (los 13 ADRs, especialmente ADR-009 si se va a discutir el Development Loop)
- Código relevante a la fase/tarea específica que se vaya a abordar

## Último estado validado

- Tests: `.venv/Scripts/python -m pytest -q` → **177 passed, 0 failed, 0 skipped** (verificado 2026-08-16, última acción de esta sesión).
- Documentación: `PROJECT_STATUS.md`, `PROJECT_PLAN.md`, `PHASE_GATES.md`, `ARCHITECTURE.md`, `EXECUTION_MODEL.md`, `TESTING_STRATEGY.md`, `CLAUDE.md` reconciliados entre sí y contra el código — sin contradicciones conocidas al cierre de esta sesión.
- Git: sin `.git` inicializado (confirmado, no se ejecutó `git init`).

## Instrucciones para la próxima sesión

**NO asumir que el estado sigue siendo correcto sin verificarlo. Leer
CLAUDE.md y SESSION_CHECKPOINT.md antes de realizar cambios.**
