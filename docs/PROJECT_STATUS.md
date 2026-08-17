# Juval — Project Status

Fotografía oficial del estado real del proyecto. Producida a partir de
`docs/RECONCILIATION_REPORT.md` (reconciliación código/tests/ADRs/docs,
2026-08-16) — ese documento contiene la evidencia línea por línea; este
documento es el resumen operativo que se mantiene actualizado con más
frecuencia.

**Regla de lectura de este documento**: "implemented" y "complete" **no
son sinónimos**. "Implemented" significa que el código existe y está
probado. "Complete" significa que, además, pasó formalmente el
Completion Gate de su fase (`docs/PHASE_GATES.md`) — criterios de
aceptación, documentación actualizada, sin conflictos arquitectónicos
abiertos, sin decisiones de negocio pendientes sin resolver. Un
componente puede estar `IMPLEMENTED` sin que su fase esté `COMPLETE`.

## Current Phase

**Fase 2 (SourcingRecord + Excel Vertical Slice): COMPLETE** (Completion
Gate evaluado formalmente 2026-08-16, todos los criterios obligatorios
en `PASS` — ver `docs/PHASE_GATES.md` §Fase 2 y ADR-012 para el cierre
del único ítem que quedaba en `FAIL`, `record_ref`).

**Fase 3 (Data Quality + ExecutionRun + Auditability): COMPLETE**
(Completion Gate evaluado formalmente 2026-08-16, todos los criterios
obligatorios en `PASS` — ver `docs/PHASE_GATES.md` §Fase 3). Persistencia
de `ExecutionRun` implementada vía SQLite local (ADR-013, `Estado:
Aceptada`, aprobada explícitamente por el usuario 2026-08-16).
`run_pipeline()` permanece puro/determinista por decisión arquitectónica
deliberada (Opción B, 2026-08-16) — no invoca el store automáticamente;
persistir es responsabilidad explícita del caller.

## Completed Phases

| Phase | Status |
|---|---|
| Phase 0 — Foundation / Repository / Documentation | **COMPLETE** |
| Phase 1 — Domain + Processing Core | **COMPLETE** |
| Phase 2 — SourcingRecord + Excel Vertical Slice | **COMPLETE** |
| Phase 3 — Data Quality + ExecutionRun + Auditability | **COMPLETE** |

Ninguna fase posterior a la 3 está `COMPLETE` hoy. Fase 2 se declaró
completa el 2026-08-16 tras evaluar formalmente su Completion Gate
(`docs/PHASE_GATES.md` §Fase 2) y cerrar el único criterio en `FAIL`
(`record_ref` sin aprobación formal) mediante ADR-012. Fase 3 se declaró
completa la misma fecha tras implementar persistencia local de
`ExecutionRun` (SQLite, ADR-013 `Aceptada`), resolver
explícitamente que `run_pipeline()` no la integra automáticamente
(Opción B), y re-evaluar el Completion Gate completo — sin cambios de
código en esta última sesión, solo la aprobación formal y la
reconciliación documental correspondiente.

## Implementation Status

| Componente | Estado |
|---|---|
| `domain/` (provenance, product, costs, risk, decision, identifiers, units, issues) | **IMPLEMENTED** |
| `domain/sourcing_record.py` (`SourcingRecord`) | **IMPLEMENTED** — composición pura (ADR-011), 7 tests |
| `domain/execution_run.py` (`ExecutionRun`) | **IMPLEMENTED** (estructura) — 11 tests unitarios + 2 de integración de reproducibilidad. **Persistencia entre corridas: IMPLEMENTED** vía SQLite local (`infrastructure/logging/sqlite_execution_run_store.py`, ADR-013 `Aceptada`, 12 tests) — no invocada automáticamente por `run_pipeline()` (decisión deliberada, Opción B) |
| `processing/` (profitability, decision_engine, decision_score, data_quality) | **IMPLEMENTED** |
| `processing/pipeline.py` (`process_record`/`process_batch`) | **IMPLEMENTED** — orquesta Data Quality → Profitability → Decision; la etapa "Risk" solo **lee** `RiskFlag`s ya construidos en import, no evalúa reglas nuevas — hoy solo HAZMAT/BULKY tienen fuente de datos (Excel), los otros 12 `RiskType` no están cableados. No se inventan fuentes nuevas para ellos. |
| `application/run_pipeline.py` | **IMPLEMENTED** — único módulo que conecta `infrastructure/` y `processing/` |
| `infrastructure/excel/` (importer, exporter, column_mapping) | **IMPLEMENTED** — columnas por nombre, normalización, validación por celda, fixtures, 21 tests de integración (import+export) |
| `infrastructure/enrichment/` | **NOT IMPLEMENTED** — solo `README.md` |
| `infrastructure/logging/` | **IMPLEMENTED** (parcial) — `sqlite_execution_run_store.py` (persistencia de `ExecutionRun`, ADR-013 `Aceptada`); logging técnico operacional (stdout/archivo) sigue sin implementar |
| `interfaces/cli` | **IMPLEMENTED** (2026-08-17) — `src/juval/interfaces/cli/main.py`, `argparse` (stdlib) sobre `run_pipeline()`/`export_excel()`, thresholds/fees siempre explícitos por flag (ADR-007), persistencia opt-in vía `--persist-db` (ADR-013 Opción B), 7 tests de integración |
| `interfaces/api` | **IMPLEMENTED** (Fase 4A, 2026-08-17) — `main.py`/`models.py`/`service.py`, FastAPI (ADR-016), 19 tests de integración. Frontend/deployment/auth siguen sin implementar |
| `interfaces/desktop` | **NOT IMPLEMENTED** — solo `README.md`; `.exe` no se construirá como interfaz principal (ADR-014); no se planea trabajo aquí |
| `processing/decision_score.py` (`DecisionScoreResult`) | **IMPLEMENTED** (código, 6 tests) / **NOT FULLY INTEGRATED** en el pipeline — `process_record`/`process_batch` no lo invocan. Fórmulas de subscore no aprobadas por negocio. Pendiente técnico registrado en §Technical Debt; su resolución corresponde a Fase 5 (Decision Intelligence), no a esta fase. |
| AI Analyst | **NOT IMPLEMENTED** — solo diseño (`AI_ANALYST.md`, ADR-008) |
| Persistencia (Supabase) / Auth (Clerk) / Framework frontend+backend PWA (Next.js, FastAPI u otros) | **NOT IMPLEMENTED** — todas `PENDING` de aprobación (`CLAUDE.md` §14, `docs/architecture/TECHNOLOGY_DECISIONS.md`). La elección de *interfaz* (PWA) ya no es `PENDING` — ver ADR-014 |

El **vertical slice Excel → dominio → processing → Excel** funciona de
extremo a extremo (`tests/integration/test_pipeline_end_to_end.py`) —
esto es exactamente el alcance de Fase 2, **no** un producto completo:
sin enriquecimiento externo, sin IA, sin persistencia entre corridas, sin
interfaz de usuario real.

## Completion Gate Status

| Phase | Gate | Detalle |
|---|---|---|
| Phase 0 | **PASS** | `docs/PHASE_GATES.md` §Fase 0 |
| Phase 1 | **PASS** | `docs/PHASE_GATES.md` §Fase 1 |
| Phase 2 | **PASS** | `docs/PHASE_GATES.md` §Fase 2, evaluado formalmente 2026-08-16. Todos los criterios obligatorios (Universal Gate + extensiones de Fase 2) en `PASS`. `record_ref` quedó formalmente documentado y aprobado por ADR-012. CLI ausente queda anotado como deuda técnica no bloqueante (no es criterio de cierre de esta fase). **Declarado `COMPLETE`.** |
| Phase 3 | **PASS** | `docs/PHASE_GATES.md` §Fase 3, evaluado formalmente 2026-08-16. Todos los criterios obligatorios (Universal Gate + específicos de Fase 3) en `PASS`. Persistencia de `ExecutionRun` implementada vía SQLite (ADR-013 `Aceptada`). Integración con `run_pipeline()` resuelta explícitamente (Opción B): no se integra, por diseño deliberado. **Declarado `COMPLETE`.** |
| Phase 4-10 | **BLOCKED** | Todas dependen de al menos una decisión `PENDING` (ver `docs/architecture/TECHNOLOGY_DECISIONS.md` y `docs/PROJECT_PLAN.md` §4). Sin cambio de estado respecto a versiones anteriores de este documento — no hay evidencia nueva que lo justifique. |

## Tests

```
.venv/Scripts/python -m pytest -q
209 passed, 0 failed, 0 skipped, ~2s
```

138 en `tests/unit/` (14 archivos: +`test_supabase_execution_run_store.py`,
2 tests estructurales, ADR-017, sin verificación contra una base real —
ver `docs/architecture/SUPABASE.md` §1) + 71 en `tests/integration/`
(7 archivos: `test_execution_run_store.py` (12, ADR-013), `test_cli.py`
(7, `interfaces/cli/main.py`), `test_excel_exporter.py` (5),
`test_excel_importer.py` (20, incluye fallback fail-closed de
`DEFAULT_RISK_SEVERITY`, ADR-015), `test_api.py` nuevo 2026-08-17 (19,
`interfaces/api/`, Fase 4A, ADR-016)). Desglose completo por archivo:
`docs/architecture/TESTING_STRATEGY.md`.

**111 tests** es el número histórico de cierre de Fase 1, **165** el de
cierre de Fase 2, y **177** el estado del repositorio inmediatamente
después de cerrar Fase 3 (2026-08-16, antes del CLI) — ninguno es el
estado actual, no citarlos como tal. Los tres se conservan como
referencia histórica en `docs/architecture/TESTING_STRATEGY.md` y en
`CLAUDE.md` §17, no se borran.

**Unit test coverage ≠ product validation** (`TESTING_STRATEGY.md` §0):
209 tests en verde confirman que el código se comporta como sus autores
esperaban con datos sintéticos — no confirman que el modelo de negocio
(thresholds, severidad de riesgo) sea correcto para el negocio real, ni
que el sistema funcione con archivos de proveedores reales, ni que el
CLI se haya usado con datos reales de un usuario final (solo con la
fixture sintética y con argv construidos a mano en los tests).

## Documentation

Documentación de arquitectura (`docs/architecture/*.md`) — 12 documentos,
todos verificados contra código en esta reconciliación:
`ARCHITECTURE.md`, `DATA_MODEL.md`, `DATA_DICTIONARY.md`,
`DATA_PROVENANCE.md`, `DATA_SOURCES.md`, `DECISION_ENGINE.md`,
`AI_ANALYST.md`, `EXCEL_PROCESSING.md`, `PROCESSING_PIPELINE.md`,
`EXECUTION_MODEL.md`, `TESTING_STRATEGY.md`, `SECURITY.md`,
`TECHNOLOGY_DECISIONS.md`.

Documentación de proceso (`docs/*.md`): `PROJECT_PLAN.md`,
`DEVELOPMENT_LOOP.md`, `PHASE_GATES.md`, `DEVELOPMENT_ENVIRONMENT.md`
(nota de entorno de desarrollo, no del producto),
`RECONCILIATION_REPORT.md`, este documento.

17 ADRs en `docs/adr/` (ADR-001 a ADR-017; solo ADR-009 en estado
Propuesta, el resto Aceptada — incluido ADR-014 (PWA), ADR-015
(fallback fail-closed de severidad), ADR-016 (FastAPI backend, Fase
4A) y ADR-017 (Supabase/PostgreSQL como persistencia de producción —
código preparado, no verificado contra una base real), las cuatro
últimas aprobadas 2026-08-17).

## Known Technical Debt

1. **`DecisionScoreResult` implementado pero no integrado en el
   pipeline.** El código y los tests existen (`processing/decision_score.py`,
   6 tests); `process_record`/`process_batch` no lo invocan. Razón: las
   fórmulas de cada subscore no están aprobadas por negocio
   (`docs/architecture/DECISION_ENGINE.md` §7). **Fase que debería
   resolverlo**: Fase 5 (Decision Intelligence) — no antes, porque
   requiere una decisión de negocio externa que no le corresponde
   inventar al agente.
2. **`ExecutionRun` no captura `thresholds` ni `sources_used`** —
   gap frente al diseño original (`ARCHITECTURE.md` §8). Ver
   `docs/architecture/EXECUTION_MODEL.md` §3.
3. ~~`record_ref` (`row_{n}[:supplier_sku]`) sin decisión arquitectónica
   `APPROVED`~~ — **RESUELTO 2026-08-16** por ADR-012 (`Estado:
   Aceptada`): la estrategia ya implementada queda formalmente
   documentada y aprobada, sin cambio de código. `ARCHITECTURE.md`
   §14.3 queda cerrada por esta decisión.
4. **Solo 2 de 14 `RiskType` tienen fuente de datos** (HAZMAT, BULKY,
   ambos desde Excel). Los 12 restantes quedan simplemente ausentes de
   `RiskProfile.flags` — no se fabrican como `UNKNOWN`, lo cual es
   correcto (no inventar datos), pero limita la cobertura real de riesgo
   hasta que existan fuentes para ellos.
5. **`DEFAULT_RISK_SEVERITY`** (HAZMAT→HIGH, BULKY→MEDIUM) está
   correctamente documentado (ADR-010) pero los valores en sí siguen sin
   aprobación de negocio. ~~Fallback silencioso `.get(risk_type,
   Severity.MEDIUM)` para cualquier `RiskType` no mapeado~~ —
   **RESUELTO 2026-08-17** vía ADR-015 (`Estado: Aceptada`): ahora
   produce `KeyError` (fail-closed) en vez de asumir `MEDIUM`. Esto no
   aprueba HAZMAT/BULKY en sí — sigue pendiente la aprobación de
   negocio de esos dos valores concretos.
6. ~~Persistencia de `ExecutionRun` entre corridas: no implementada~~ —
   **RESUELTO 2026-08-16** vía SQLite local
   (`infrastructure/logging/sqlite_execution_run_store.py`, ADR-013
   `Estado: Aceptada`, aprobada explícitamente por el usuario).
   `run_pipeline()` no invoca el store automáticamente por decisión
   arquitectónica deliberada (Opción B, también aprobada explícitamente)
   — persistir una corrida es una acción explícita del llamador, no una
   deuda pendiente. La política de invocación automática queda diferida
   a la primera interfaz operativa real (CLI/API, Fase 4).
7. ~~**CLI ausente**~~ — **RESUELTO 2026-08-17**: `interfaces/cli/main.py`
   implementado (`argparse`, stdlib, sin dependencia nueva), cerrando la
   recomendación de `ARCHITECTURE.md` §15/ADR-005. Ver
   §Sesión 2026-08-17 abajo para el detalle.
8. **`max_cog_target_profit`/`max_cog_target_roi` no se exportaban a
   Excel** — **RESUELTO 2026-08-17**: `exporter.py::HEADERS` ahora incluye
   ambas columnas (`<campo>`/`<campo>_status`), ya se calculaban en
   `profitability.py` desde antes, solo faltaba exponerlas.
9. **`validate_freshness()`/`validate_source()` no conectadas al
   pipeline** — **evaluado y diferido conscientemente, no resuelto**: hoy
   todo dato viene del Excel en el mismo instante de import (`now` es el
   único `retrieved_at` que existe), así que "freshness"/"placeholder
   source" no tienen ninguna variación real que detectar todavía — conectar
   estas validaciones ahora sería código sin capacidad de fallar un test
   con datos reales. Ambas funciones ya existen, están probadas
   individualmente (`test_data_quality.py`) y no se tocan (`CLAUDE.md`
   "no eliminar código sin consumidores actuales" — tampoco se fuerza su
   uso sin uno). Se activan de forma natural cuando exista una fuente con
   `retrieved_at` distinto del import (Fase 6, `BLOCKED`).
10. **`SourcingRecord.with_*()` sin uso en `src/`** — evaluado, sin
    acción: `pipeline.py::process_record` hace un único
    `dataclasses.replace(record, profitability=..., decision=...,
    issues=...)` en vez de encadenar tres `with_*()`; ambas formas son
    equivalentes en comportamiento y el código actual ya pasa 185 tests.
    Migrar sería puro churn estético sin corregir un defecto — no se
    hace (Ponytail: no refactorizar sin valor real). Los métodos
    `with_*()` se conservan (están probados en `test_sourcing_record.py`
    y documentados como la forma pública de mutar-vía-copia un
    `SourcingRecord`) para cuando un consumidor futuro (ej. un caso de
    uso que solo necesite cambiar un campo) los necesite.

## Sesión 2026-08-17 — CLI + cierre de deuda técnica menor

Continuación de trabajo tras el cierre de Fase 3 (2026-08-16). Fase 2 y
Fase 3 seguían `COMPLETE`; Fases 4-10 seguían `BLOCKED` por decisiones
`PENDING` que el agente no puede tomar (§Pending Decisions). En vez de
detenerse ahí, se identificó trabajo de categoría A (ejecutable sin
ninguna decisión de negocio/arquitectura pendiente) y se ejecutó:

1. **`interfaces/cli/main.py`** — CLI real, recomendado explícitamente
   por ADR-005 (`Estado: Aceptada`) y `ARCHITECTURE.md` §15 como la
   primera interfaz para validar el Core end-to-end, deliberadamente
   *antes* de decidir PWA vs. `.exe` (ADR-005 dice textualmente que
   permite "implementar primero la interfaz más simple... sin
   comprometerse a PWA o `.exe`"). No requirió ninguna decisión bloqueada:
   usa `argparse` (stdlib, cero dependencia nueva, evita la pregunta
   abierta `typer` vs. `argparse` de `ARCHITECTURE.md` §15), exige que el
   operador declare thresholds/fees por flag (nunca un default comercial
   inventado, ADR-007), y solo persiste el `ExecutionRun` si el operador
   pasa `--persist-db` explícitamente (continuación directa de Opción B/
   ADR-013, no una decisión nueva). 7 tests de integración
   (`tests/integration/test_cli.py`), probado también manualmente contra
   la fixture real. Esto resuelve la deuda técnica #7 (histórica) y dota
   al proyecto de su primer entrypoint real — antes, todo el valor de
   Juval solo era accesible escribiendo Python directamente (ver
   `README.md`).
2. **Excel export gap** — `max_cog_target_profit`/`max_cog_target_roi`
   ya se calculaban en `processing/profitability.py` (con
   `target_profit`/`target_roi` de `Thresholds`) pero nunca se exportaban;
   `exporter.py::HEADERS` ahora incluye ambas columnas con su
   `<campo>_status` correspondiente, siguiendo el mismo patrón que el
   resto de campos sensibles. 1 test nuevo
   (`test_excel_exporter.py::test_export_includes_max_cog_targets`).
3. **Docstring desactualizado en `domain/execution_run.py`** — seguía
   diciendo "in-memory/local only... no persistence layer", una
   afirmación que ADR-013 dejó obsoleta el 2026-08-16 pero que nadie
   había corregido en el propio código fuente (aunque sí en `docs/`).
   Corregido para apuntar al puerto/adapter reales
   (`ExecutionRunStore`/`SqliteExecutionRunStore`).
4. **`validate_freshness()`/`validate_source()` y `SourcingRecord.with_*()`**
   — evaluados y **diferidos conscientemente** con justificación explícita
   (ver Known Technical Debt #9/#10 arriba) en vez de forzarlos sin valor
   real o borrarlos sin necesidad.

Nada de esto tocó una decisión de `§Pending Decisions` — ninguna fue
aprobada, inventada ni asumida. Fase 2 y Fase 3 siguen `COMPLETE` sin
cambios en sus Completion Gates (`docs/PHASE_GATES.md`); este trabajo no
abre ni cierra ninguna fase nueva del `PROJECT_PLAN.md` (el CLI no tiene
un número de fase propio — ver nota en `PROJECT_PLAN.md` sobre esto).

## Sesión 2026-08-17 (bloque 2) — ADR-014: elección de PWA

Sesión puramente documental/arquitectónica, sin código. El usuario tomó
explícitamente la decisión que la sesión de planificación anterior
(§Sesión 2026-08-17 arriba) había dejado como la más urgente para
desbloquear Fase 4: **PWA como interfaz principal** ("PWA definitivamente").

Se creó `docs/adr/ADR-014-eleccion-pwa-interfaz-principal.md`
(`Estado: Aceptada`), y se actualizaron en el mismo cambio:
`docs/PROJECT_PLAN.md` (mapa de dependencias §3, tabla de decisiones
bloqueantes §4, sección Fase 4), este documento (§Implementation Status,
§Pending Decisions, §Next Recommended Action), `CLAUDE.md` §14,
`docs/architecture/ARCHITECTURE.md` (§10, §14, §16),
`docs/architecture/TECHNOLOGY_DECISIONS.md` (filas PWA/`.exe`/Vercel/
FastAPI), y `src/juval/interfaces/api/README.md` /
`src/juval/interfaces/desktop/README.md`.

**Lo que este ADR aprueba**: únicamente "PWA como interfaz principal".
**Lo que NO aprueba** (permanece explícitamente `PENDING`, ver ADR-014
§"Límites explícitos de esta decisión"): framework de backend concreto,
framework de frontend concreto, Vercel/hosting, Supabase, Clerk, Docker,
proveedor cloud. Fase 4 sigue `BLOCKED` — esta decisión resuelve
únicamente el bloqueo de *elección de interfaz*, no los demás bloqueos
de la fase (ver `PROJECT_PLAN.md` §Fase 4 actualizado).

`.exe` no se descarta como imposible para siempre (ADR-005 sigue
garantizando la independencia de diseño), pero no es el camino que se
construirá — no hay trabajo planeado en esa dirección.

Ningún código de `interfaces/api/` ni de ningún frontend se implementó
en esta sesión, por instrucción explícita. `interfaces/cli/main.py`
sigue siendo la única interfaz operativa real hoy.

## Sesión 2026-08-17 (bloque 3) — Fase 4A: backend FastAPI + preparación Supabase

El usuario aprobó FastAPI (backend), React+Vite (frontend, no
implementado esta sesión), Vercel, Git/GitHub, y Supabase en un mismo
prompt de alcance muy amplio. Antes de ejecutar, se verificó
disponibilidad de herramientas: `git` disponible (2.55.0); `node`,
`npm`, `supabase` CLI, y `vercel` CLI — **ninguno disponible**
(`[HECHO VERIFICADO]`, `--version` de cada uno falla). Se preguntó
explícitamente al usuario cómo priorizar dado ese bloqueo; eligió
completar primero el backend FastAPI + preparar (sin desplegar) el
adapter de Supabase.

**Implementado y probado** (209 tests, +21 sobre el baseline de 188):

1. `interfaces/api/{main,models,service}.py` — backend FastAPI
   (ADR-016), `POST /api/v1/runs` + `GET /api/v1/runs/{execution_id}/download`,
   cliente delgado sobre `application.run_pipeline`. 19 tests de
   integración (`test_api.py`) contra el Core real (fixture real, sin
   mocks en el camino principal), incluyendo persistencia opt-in de
   `ExecutionRun`, descarga real, provenance preservada en JSON
   (`value`+`status` juntos, ADR-003/ADR-004), y verificación explícita
   de que ningún traceback/ruta de servidor se expone nunca.
2. **Fix de un bug real de Windows, descubierto probando el flujo
   completo**: `infrastructure/excel/importer.py::import_excel` nunca
   cerraba el `Workbook` (`read_only=True` de `openpyxl` mantiene el
   archivo bloqueado). El CLI nunca lo notó porque nunca intenta borrar
   su archivo de entrada; la API sí (limpieza de temporales, §12 del
   brief), y el intento de borrar el archivo recién procesado fallaba
   con `PermissionError`. Corregido con un `try/finally: workbook.close()`
   — cambio mínimo, fuera de `domain/`/`processing/`/`run_pipeline()`
   (no restringido explícitamente), los 188 tests previos siguen en
   verde sin cambios.
3. `docs/architecture/API_CONTRACT.md` — contrato completo, derivado
   del código real, distingue explícitamente límite técnico (`JUVAL_MAX_UPLOAD_BYTES`,
   configurable, sin límite si no se define) de límite comercial
   (sigue `PENDING`, no inventado).
4. `SupabaseExecutionRunStore` (`infrastructure/persistence/`, ADR-017)
   + migración SQL versionada (`supabase/migrations/`) + `docs/architecture/SUPABASE.md`
   — **preparado, NO verificado contra un proyecto real** (sin CLI, sin
   credenciales, sin proyecto Supabase creado). 2 tests puramente
   estructurales, explícitamente distinguidos de los 12 tests de
   integración reales que sí tiene `SqliteExecutionRunStore` (ADR-013).
5. `.env.example` + `.gitignore` ampliado (`.env`, `node_modules/`) —
   ninguna credencial real en ningún archivo.

**No ejecutado esta sesión** (bloqueado por herramientas/credenciales
ausentes, reportado explícitamente, no inventado):
frontend React+Vite (sin Node/npm), `supabase init`/`db push` reales
(sin Supabase CLI ni proyecto), deployment a Vercel (sin Vercel CLI ni
cuenta), `git init`/push a GitHub (sin remoto ni credenciales — y no
solicitado en el alcance finalmente elegido por el usuario).

## Sesión 2026-08-17 (bloque 4) — Fase 4B: frontend React+Vite+PWA, git init, tooling

El usuario reafirmó explícitamente el alcance completo (PWA, FastAPI,
React+Vite, Vercel, Supabase, Git/GitHub) y autorizó instalar
herramientas si el entorno lo permite de forma segura.

**Herramientas instaladas esta sesión** (todas por canal oficial,
verificadas después de instalar):
- Node.js LTS v24.19.0 — via `winget install OpenJS.NodeJS.LTS` (fuente
  `winget`, hash verificado por winget).
- npm v11.17.0 — incluido con Node.
- Vercel CLI 59.1.3 — via `npm install -g vercel`.
- Supabase CLI 2.114.0 — **no instalable como binario persistente**
  (sin paquete winget/scoop disponible en este entorno); usable vía
  `npx supabase@latest <comando>`, que es el mecanismo que la propia
  documentación de Supabase soporta para Windows sin Scoop.
- `git` ya estaba disponible (2.55.0), sin cambios.

Nota práctica: `node`/`npm`/`vercel` solo resuelven directamente en
shells nuevos — los procesos de shell ya abiertos en la sesión anterior
no heredan el PATH actualizado por el instalador hasta reiniciarse (
comportamiento normal de Windows, no un defecto de la instalación).

**Implementado y verificado**:
1. `frontend/` — React 19 + TypeScript + Vite 8, scaffolded con
   `npm create vite@latest -- --template react-ts`. Sin router (una sola
   pantalla), sin librería de estado global, sin librería de UI — nada
   de eso tiene necesidad demostrada todavía.
2. PWA — `vite-plugin-pwa`, manifest (`name: "JUVAl"`, ícono placeholder
   propio en `public/icon.svg`), service worker autogenerado
   (`generateSW`). Sin offline processing, sin background sync, sin
   push notifications (explícitamente fuera de alcance de esta sesión).
3. `src/types.ts`/`src/api.ts`/`src/components/{RunForm,ResultsTable}.tsx`/`src/App.tsx`
   — cliente delgado puro sobre `docs/architecture/API_CONTRACT.md`, sin
   ningún cálculo de negocio (revisado línea por línea: no hay profit,
   ROI, severidad, decisión, ni thresholds calculados en TypeScript).
   Cada campo sensible se renderiza como `value` + `status` juntos,
   nunca colapsado (ADR-003/ADR-004) — verificado por test.
4. Ningún campo obligatorio del Core (`target_profit`, `target_roi`,
   `minimum_estimated_monthly_sales`, `maximum_risk_severity`,
   `referral_fee`, `referral_fee_rate`) tiene valor prellenado — el
   formulario fuerza input explícito, sin inventar defaults comerciales
   (ADR-007). Los dos campos de `FeeInputs` que sí tienen default en el
   propio dominio (`fulfillment_fee`/`other_selling_fees` = 0) reflejan
   ese mismo default, no uno nuevo.
5. **9 tests de frontend** (Vitest + Testing Library): formulario
   (renderiza, bloquea submit sin archivo, bloquea submit con
   parámetros vacíos sin inventar default, arma el payload exacto que
   el backend espera), tabla de resultados (nunca colapsa
   `FieldValue`, muestra `NOT_FOUND` explícitamente, muestra razones de
   decisión e issues), App (éxito muestra resultados + link de
   descarga real, error de API se muestra como estado, no como crash).
6. `npm run build` — **exitoso**, genera `dist/` + service worker.
7. **1 test E2E real** (Playwright, Chromium): arrancó el backend
   FastAPI real y el frontend real (`npm run dev`), subió el fixture
   real (`tests/fixtures/sample_sourcing_TEST_DATA.xlsx`), confirmó
   `PARTIAL_SUCCESS`, el ASIN real (`B0TESTAAA1`), provenance
   `[VERIFIED]` visible, y una descarga real de `.xlsx` — **no un
   mock**. Durante esta verificación se encontró y corrigió un bug real
   de configuración (CORS solo permitía `localhost:5173`, el dev server
   respondía en `127.0.0.1:5173` — orígenes distintos para el
   navegador); corregido documentando ambos orígenes en el ejemplo de
   `frontend/e2e/README.md`, sin tocar el mecanismo de CORS en sí
   (ya era correctamente configurable, `API_CONTRACT.md` §7).
8. `git init` — repositorio local inicializado, `146` archivos
   staged (`git add -A`), verificados sin secretos/credenciales/
   `node_modules`/`.venv`/archivos temporales (`git status --ignored`
   confirma que todo lo sensible está excluido). **Commit NO
   ejecutado**: `git commit` requiere `user.name`/`user.email`, que
   este agente tiene prohibido configurar (`Git Safety Protocol: NEVER
   update the git config`) — bloqueo real reportado, no una decisión
   silenciosa. Ver §"Qué falta" del reporte de esta sesión para el
   comando exacto.
9. `frontend/vercel.json` preparado (`buildCommand`, `outputDirectory:
   dist`, `framework: vite`) — sin desplegar (`vercel whoami` confirma
   sesión no iniciada, requiere `vercel login` interactivo).
10. Supabase: `npx supabase@latest projects list` confirma sesión no
    iniciada (`LegacyPlatformAuthRequiredError`) — requiere `supabase
    login` interactivo (OAuth de navegador). La migración
    (`supabase/migrations/20260817000000_execution_runs.sql`) sigue sin
    aplicarse a ningún proyecto real.

**Backend**: sin cambios de lógica — 209 tests siguen en verde.
Confirmado end-to-end real contra el frontend (no solo `TestClient`).

## Sesión 2026-08-17 (bloque 5) — cierre de infraestructura: Git/Supabase/Vercel

Re-verificación completa de INSPECT (no se asumió el estado del bloque
4). Sin cambios de código de negocio. Resultado idéntico al bloque 4 en
los tres bloqueos externos, más un hallazgo nuevo de investigación:

1. **Git**: `git status`/`git remote -v`/`git branch`/`git log` — sin
   commits, sin remoto, sin rama con historial. `git config user.name`/
   `user.email` — **ambos vacíos** (confirmado, no asumido). **STOP** en
   este punto exacto, tal como se instruyó — no se inventó identidad,
   no se ejecutó commit. 146 archivos siguen staged, re-verificados sin
   secretos (`git diff --cached --check` sin errores; scan de patrones
   de secretos sin resultados).
2. **Supabase**: `npx supabase@latest projects list` →
   `LegacyPlatformAuthRequiredError`. **STOP** — "Supabase requiere
   login interactivo del usuario", tal como se instruyó reportar
   literalmente. Nada más de Fase 3/4/5 del brief se ejecutó (dependían
   de esto).
3. **Vercel**: `vercel whoami` → `Logged out`. **STOP** — "Vercel
   requiere login interactivo del usuario". No se usó
   `vercel deploy --temporary` (publicaría el frontend en un dominio
   público de Vercel sin tu cuenta; no estaba instruido y decidí no
   improvisarlo sin tu confirmación explícita).
4. **`[HECHO VERIFICADO]` hallazgo nuevo — Vercel Functions no es
   compatible con el backend tal como está diseñado hoy**: investigado
   (no implementado, ver `docs/architecture/API_CONTRACT.md` §8.4).
   `/tmp` en Vercel Functions es efímero entre invocaciones (hasta
   500 MB) — el diseño actual de dos fases (`POST` escribe
   `output.xlsx`, `GET` posterior lo lee) no puede garantizar que ambas
   lleguen a la misma instancia. Además: límite de payload 4.5 MB,
   duración 10s(free)/60s(Pro). **Opciones presentadas, ninguna
   aplicada** (requieren tu aprobación, cambian la arquitectura o el
   contrato):
   - **Opción A** (recomendada, consistente con la sesión de diseño de
     Fase 4 previa): desplegar el backend en un host de proceso largo
     (Render/Railway/Fly.io/VPS), **no** en Vercel Functions. Frontend
     sigue en Vercel sin cambios. Cero cambio de código.
   - **Opción B**: rediseñar el contrato para que `POST /api/v1/runs`
     devuelva el Excel directamente en la misma respuesta (sin `GET`
     separado) — viable en Vercel Functions solo si el archivo entra en
     el límite de payload/duración; cambia `API_CONTRACT.md`.
   - **Opción C**: introducir un almacenamiento de objetos persistente
     (ej. Vercel Blob) para que ambas fases puedan leer el mismo
     archivo sin importar la instancia — introduce una dependencia/
     servicio nuevo, no aprobado todavía.
5. **Validación local re-confirmada** (no asumida): backend 209
   passed; frontend 9 passed; `npm run build` exitoso; **E2E
   re-ejecutado desde cero** (backend + frontend reiniciados) — 1
   passed, contra el stack real, sin mocks.
6. **Deployment real**: **NO ejecutado** — ninguno de los tres
   bloqueos (Git, Supabase, Vercel) se resolvió, y el hallazgo del
   punto 4 significa que, aunque Vercel tuviera sesión, el backend no
   debería desplegarse allí sin que tú elijas una de las opciones A/B/C
   primero.

## Sesión 2026-08-17 (bloque 6) — Deployment Architecture Gate: Opción A aprobada

El usuario aprobó explícitamente **Opción A** (§Sesión bloque 5): Vercel
solo para el frontend; backend en un servicio Python de proceso largo
(proveedor concreto todavía sin elegir); Supabase como persistencia de
producción. **Ningún cambio de código de negocio.**

Re-verificación completa de INSPECT (no asumida): `git config
user.name`/`user.email` siguen vacíos; `npx supabase@latest projects list`
sigue devolviendo `LegacyPlatformAuthRequiredError`; `vercel whoami`
sigue devolviendo `Logged out`. **Los tres bloqueos externos son
idénticos a los de la sesión anterior** — cero cambio de estado, porque
ninguno depende de nada que el agente pueda resolver por sí mismo.
`frontend/vercel.json` re-inspeccionado, correcto y sin cambios
(`buildCommand: npm run build`, `outputDirectory: dist`, `framework: vite`).
Validación local re-confirmada: 209 backend + 9 frontend + build
exitoso.

**PRIORIDAD 3 (selección SQLite/Supabase por entorno) deliberadamente
NO implementada esta sesión** — el propio brief la condiciona
explícitamente a "después de verificar Supabase real", precondición
que sigue sin cumplirse (Supabase sigue sin sesión). Implementarla
ahora habría sido ejecutar fuera de orden.

**PRIORIDAD 5 (proveedor de backend)**: sigue sin decidir un proveedor
concreto (Render/Railway/Fly.io/VPS u otro) — no se inventó ninguno,
se reporta como decisión pendiente del usuario.

## Sesión 2026-08-17 (bloque 7) — comparación de proveedores de backend

Los tres bloqueos externos (Git, Supabase, Vercel) se re-verificaron
de nuevo — **idénticos**, cero cambio de estado. Como el propio brief
de esta sesión indica "no repetir indefinidamente las mismas
validaciones... avanzar únicamente con trabajo que no dependa del
bloqueo", el trabajo real de esta sesión fue la comparación de
proveedores de backend pedida explícitamente, investigada con
información real (no memoria sin verificar) — ver fuentes citadas en
esta misma sesión de chat.

### Comparación Render vs. Railway vs. Fly.io vs. VPS

| Criterio | Render | Railway | Fly.io | VPS genérico |
|---|---|---|---|---|
| Soporte FastAPI | Nativo (Python detectado) | Nativo (Nixpacks detecta Python) | Vía Docker (requiere Dockerfile) | Total (tú controlas todo) |
| Proceso persistente | Sí | Sí | Sí (microVMs Firecracker) | Sí |
| Filesystem temporal | Ephemeral **entre deploys/restarts**; **estable entre requests dentro de la misma instancia corriendo** (no es el caso de Vercel Functions) — compatible con el diseño POST/GET actual sin Persistent Disk | Igual — proceso único de larga duración, filesystem estable mientras la instancia corre | Igual — VM de larga duración | Total control |
| Duración de requests | Sin límite agresivo documentado para Starter+ (no es serverless) | Sin límite agresivo (no es serverless) | Sin límite agresivo (no es serverless) | Sin límite (tú decides) |
| Memoria/CPU | Starter: recursos limitados; escala en tiers pagos hasta 32GB/8 CPU (Pro Ultra) | Escala por uso (vCPU/RAM medidos) | `shared-cpu-1x`/1GB por defecto, escalable | Tú eliges el tamaño |
| HTTPS | Automático | Automático | Automático | Manual (Let's Encrypt/certbot) |
| Variables de entorno | Dashboard, simple | Dashboard/CLI, simple | `fly secrets`, simple | Manual (`.env`, systemd) |
| Integración con Supabase | Trivial — solo connection string | Trivial | Trivial | Trivial |
| **Despliegue sin GitHub** (relevante ahora mismo — GitHub bloqueado) | **No** — el flujo estándar de Render requiere GitHub/GitLab/Bitbucket conectado; no hay `git push render` directo | **Sí** — `railway up` sube y despliega el directorio local directamente, sin Git en absoluto | **Sí** — `flyctl deploy` construye y despliega desde el Dockerfile/código local, sin Git | **Sí** — control total, sin dependencia de ningún proveedor de Git |
| Facilidad de operación | Alta (más simple, más opinionado) | Alta | Media (requiere Dockerfile, más control = más configuración) | Baja (todo manual: SO, systemd, proxy, TLS, updates de seguridad) |
| Coste (uso bajo, un operador) | Free tier real pero con cold-start de ~1 min tras 15 min inactivo; Starter pago $7/mes sin cold-start | Sin free tier real (crédito de prueba de $5, luego ~$1/mes de crédito); Hobby $5/mes | Sin free tier real (solo 2h de prueba); pago por segundo | Variable, desde ~$4-6/mes (proveedor genérico) |
| Escalabilidad | Vertical simple, tiers fijos | Vertical + medido por uso | Multi-región nativo (edge), la más flexible | Manual, tú decides |
| Logs | Nativos, dashboard | Nativos, dashboard/CLI | Nativos, `fly logs` | Manual (journald, etc.) |
| Health checks | Nativo (`healthCheckPath`) | Nativo (`healthcheckPath`) | Nativo, requiere endpoint propio | Manual |
| Compatibilidad con el contrato POST/GET actual | Sí, sin cambios | Sí, sin cambios | Sí, sin cambios | Sí, sin cambios |

`[HECHO VERIFICADO]`: ninguno de los cuatro requiere cambiar el
contrato de API ni convertir el backend a serverless — los cuatro son
procesos de larga duración, exactamente lo que la Opción A ya aprobada
requiere.

`[HECHO VERIFICADO]`, hallazgo más relevante dado el bloqueo actual de
GitHub: **Render está efectivamente bloqueado hoy** (su flujo estándar
de deploy depende de un repositorio Git conectado, que no existe
todavía); **Railway y Fly.io sí son desplegables ahora mismo** sin
GitHub, vía sus respectivos CLIs (`railway up` / `flyctl deploy`)
subiendo el código local directamente.

`[RECOMENDACIÓN]`, no aplicada, esperando tu aprobación: **Railway**
— es desplegable ya mismo pese al bloqueo de GitHub, no requiere
Dockerfile (detecta Python automáticamente vía Nixpacks, aunque
`interfaces/api/` ya podría llevar uno si se prefiere control
explícito), y tiene la curva de configuración más baja de los tres
proveedores gestionados. Fly.io es la alternativa más fuerte si más
adelante importa control multi-región; Render sigue siendo válido
cuando GitHub vuelva a estar disponible; un VPS se descarta para un
MVP de un solo operador por la carga operativa que añade sin necesidad
demostrada (Ponytail).

**No se implementó nada de esto** — es una comparación, a la espera de
tu aprobación explícita antes de tocar cualquier configuración de
despliegue.

Sources:
- [Render vs Railway vs Fly.io: 2026 Pricing Showdown](https://expresstech.io/render-vs-railway-vs-fly-io-2026-pricing-showdown/)
- [Persistent Disks – Render Docs](https://render.com/docs/disks)
- [Web Services – Render Docs](https://render.com/docs/web-services)
- [Deploy without GitHub/GitLab | Feature Requests | Render](https://feedback.render.com/features/p/deploy-without-githubgitlab)
- [Deploying with the CLI | Railway Docs](https://docs.railway.com/cli/deploying)
- [railway up | Railway Docs](https://docs.railway.com/cli/up)
- [Deploy a FastAPI App | Railway Guides](https://docs.railway.com/guides/fastapi)
- [Run a FastAPI app · Fly Docs](https://fly.io/docs/python/frameworks/fastapi/)

## Sesión 2026-08-17 (bloque 8) — Railway aprobado: preparación (sin deploy)

El usuario aprobó explícitamente **Railway** como proveedor del backend
(ADR-018, `Estado: Aceptada`). Re-verificación de INSPECT: Git
(identidad vacía), Supabase (sin sesión) — **idénticos** a sesiones
anteriores. Railway CLI instalada (`npm install -g @railway/cli`,
5.41.2) — `railway whoami` → `Unauthorized` (sin sesión, esperado, no
se intentó login).

**Preparado, sin desplegar**:
1. `railway.toml` (raíz del repo) — `buildCommand: pip install .[postgres]`,
   `startCommand: uvicorn juval.interfaces.api.main:app --host 0.0.0.0 --port $PORT`.
   Sin `healthcheckPath` (Railway usa TCP check por defecto; un
   `GET /health` dedicado queda como `[RECOMENDACIÓN]` explícita, no
   implementada — habría sido tocar `interfaces/api/main.py` sin que el
   usuario lo pidiera).
2. **Hallazgo verificado, no asumido**: `pip install -e .` (probado
   localmente) hace que `import juval` funcione **sin** la variable
   `PYTHONPATH=src` que usan los tests — confirmado arrancando
   `uvicorn juval.interfaces.api.main:app` sin esa variable y
   confirmando `GET /openapi.json` → 200. Esto es más correcto para
   producción que replicar la convención de `pytest`.
3. `.env.example` (raíz) ampliado con nota sobre `JUVAL_CORS_ORIGINS`
   (deberá apuntar a la URL real de Vercel, todavía inexistente — no
   inventada) y `PORT` (gestionado por Railway, no configurar
   manualmente).
4. `ADR-018-railway-backend-hosting.md` creado — documenta la elección,
   la configuración, y explícitamente qué NO resuelve (deploy real,
   `/health`, CORS con URL real, integración con Supabase en `main.py`).

**No ejecutado, ni parcialmente**: `railway login`, `railway link`,
`railway up`, ni ningún deploy real. Comando exacto que el usuario
deberá ejecutar cuando quiera desplegar:
```bash
railway login          # abre el navegador
railway link            # o `railway init` si el proyecto Railway no existe todavía
railway up
```
Después del primer deploy, configurar en el dashboard/CLI de Railway
la variable `JUVAL_CORS_ORIGINS` con la URL real del frontend en
Vercel (todavía no existe).

**Validaciones re-confirmadas** (no asumidas): backend 209 passed;
frontend 9 passed; `npm run build` exitoso. Ningún test nuevo — no se
tocó código de aplicación, solo configuración de deployment +
`pyproject.toml` sin cambios (la instalación editable no modificó
ningún archivo versionado, `src/juval.egg-info/` generado ya estaba
cubierto por `.gitignore::*.egg-info/`).

## Sesión 2026-08-17 (bloque 9) — verificación sin cambios

Los cuatro bloqueos externos (Git, Supabase, Vercel, Railway) se
re-verificaron con los comandos reales al inicio de la sesión —
**idénticos a la sesión anterior, sexta vez consecutiva sin cambio**:
`git config user.name`/`user.email` vacíos; `npx supabase@latest projects list`
→ `LegacyPlatformAuthRequiredError`; `vercel whoami` → `Logged out`;
`railway whoami` → `Unauthorized`. Validación local re-confirmada: 209
backend + 9 frontend + build, sin cambios.

Como los cuatro bloqueos son idénticos y **cada** prioridad 2-7 del
brief de esta sesión depende explícitamente de al menos uno de ellos,
no existe trabajo de infraestructura independiente que ejecutar esta
vez (a diferencia del bloque 7, donde la comparación de proveedores sí
era independiente de los bloqueos). No se fabricó ninguna tarea
sustituta — en particular, `GET /health` seguía explícitamente
prohibida esta sesión salvo aprobación, y no se tocó. Sesión de
verificación, no de ejecución.

## Sesión 2026-08-17 (bloque 10) — Supabase e2e + Git/GitHub baseline resueltos; Railway sigue bloqueado

De los cuatro bloqueos externos re-verificados sin cambio en los
bloques 5-9, **dos quedaron resueltos** en sesiones posteriores (no
detalladas bloque a bloque aquí, ver commits/ADRs para el detalle
exacto):

- **Supabase**: el usuario ejecutó `supabase login` fuera de la sesión
  del agente. Proyecto real identificado sin ambigüedad
  (`juvalservicesllc-cloud's Project`, ref `twrgzsbpazcjhhfolaju`),
  repositorio vinculado, migración `20260817000000_execution_runs.sql`
  aplicada y verificada contra el esquema remoto real (columnas, PK,
  índices, RLS habilitado, 0 policies desplegadas — fail-closed
  esperado). `SupabaseExecutionRunStore` probado con una prueba de
  integración real (INSERT + SELECT + cleanup,
  `tests/integration/test_supabase_execution_run_store.py`) — requirió
  el **Connection Pooler** de Supabase, no el host directo (que resuelve
  solo IPv6, sin ruta IPv6 en este entorno). Selector
  `JUVAL_EXECUTION_STORE` (`sqlite`|`supabase`) implementado en
  `main.py::_execution_run_store`, fail-fast, sin fallback implícito
  entre modos — ver `docs/architecture/SUPABASE.md` y
  `docs/architecture/API_CONTRACT.md` §5. ADR-017 actualizado, sin ADR
  nuevo.
- **Git/GitHub**: identidad Git configurada por el usuario. Primer
  commit del repositorio creado (`ee412f4 — chore: establish Juval
  project baseline`, 157 archivos, incluye backend/docs/frontend hasta
  ese punto). `origin` configurado a
  `https://github.com/juvalservicesllc-cloud/JUVAl.git` y publicado
  (`master` → `origin/master`), verificado con `git ls-remote`.

**Railway sigue bloqueado, re-verificado en esta sesión**: `railway
--version` → `5.41.2` (CLI instalada globalmente, sin cambios),
`railway whoami` → `Unauthorized` (idéntico a bloques 5-9). `railway.toml`
ya estaba correctamente preparado (`buildCommand: pip install
.[postgres]`, `startCommand` con `$PORT`/`0.0.0.0`, entrypoint real
`juval.interfaces.api.main:app`) — no requirió ningún cambio esta
sesión. `main.py` ya soporta seleccionar `SupabaseExecutionRunStore`
vía `JUVAL_EXECUTION_STORE=supabase` (bloque anterior), así que el
único paso pendiente para desplegar es que el usuario ejecute `railway
login` (interactivo, no completable por el agente) y, tras eso, vincule
o cree el proyecto/servicio Railway.

## Pending Decisions

Todas `PENDING`, ninguna se resuelve en este documento (ver
`docs/architecture/TECHNOLOGY_DECISIONS.md` para el detalle completo):

- ADR-009 (Development Loop + Completion Gates) — `Estado: Propuesta`,
  no confirmada por el usuario.
- ~~PWA vs. `.exe`~~ — **RESUELTO 2026-08-17**: el usuario eligió
  explícitamente PWA (ADR-014, `Estado: Aceptada`). ADR-005 sigue vigente
  para la independencia de diseño (no modificado). Se conserva aquí como
  registro histórico — ya no es un ítem `PENDING`.
- ~~Framework de backend para `interfaces/api/`~~ — **RESUELTO
  2026-08-17**: FastAPI (ADR-016, `Estado: Aceptada`), implementado y
  probado (19 tests).
- ~~Framework frontend (React + Vite)~~ — **RESUELTO/IMPLEMENTED
  2026-08-17 (bloque 4)**: `frontend/` (React 19 + TypeScript + Vite 8 +
  PWA), 9 tests + 1 E2E real contra el backend, `npm run build`
  exitoso. Sin ADR propio todavía (no se creó uno nuevo esta sesión —
  el usuario ya había elegido el framework explícitamente, no había una
  decisión de "cuál" que documentar).
- Vercel (deployment, **solo frontend**) — aprobado como plataforma
  objetivo; CLI instalada (59.1.3) y `frontend/vercel.json` preparado,
  **sin desplegar**: `vercel whoami` confirma sesión no iniciada
  (`vercel login` requiere interacción del usuario, OAuth de
  navegador).
- ~~Proveedor de hosting del backend~~ — **RESUELTO 2026-08-17 (bloque
  8)**: Railway (ADR-018, `Estado: Aceptada`), tras comparación
  explícita con Render/Fly.io/VPS (bloque 7). `railway.toml` preparado,
  **sin desplegar**: `railway whoami` confirma sesión no iniciada
  (`railway login` requiere interacción del usuario). Vercel Functions
  descartado explícitamente para el backend por incompatibilidad real
  verificada (`API_CONTRACT.md` §8.4).
- Supabase — aprobado como persistencia de producción (ADR-017,
  `Estado: Aceptada`), CLI utilizable vía `npx supabase@latest`, **sin
  verificar contra un proyecto real**: `supabase projects list` confirma
  sesión no iniciada (`supabase login` requiere interacción del
  usuario, OAuth de navegador). No confundir "decisión aprobada" con
  "implementación verificada" (ver `docs/architecture/SUPABASE.md` §1).
- Clerk — autenticación, sin aprobación.
- Fuente(s) externa(s) de enriquecimiento (Amazon SP-API, datos de
  mercado tipo Keepa) — ninguna aprobada.
- Proveedor/modelo de IA para el AI Analyst — no evaluado.
- Fórmulas de subscore del Decision Score y thresholds comerciales
  reales — no aprobados.
- Aprobación de negocio de `DEFAULT_RISK_SEVERITY` (los valores, no la
  documentación — ver Technical Debt #5).
- ~~ADR-013 (Persistencia de `ExecutionRun` vía SQLite) — `Estado:
  Propuesta`~~ — **RESUELTO 2026-08-16**: aprobada explícitamente por el
  usuario, `Estado: Aceptada`. Se conserva aquí como registro histórico.
- ~~Si `run_pipeline()` debe invocar `SqliteExecutionRunStore`
  automáticamente~~ — **RESUELTO 2026-08-16 (Opción B)**: NO.
  `run_pipeline()` permanece puro/determinista por diseño; persistir
  sigue siendo una acción explícita del llamador. En su momento (sesión
  2026-08-16) esta nota decía "no requirió un ADR nuevo" sin asignarle
  número — **corrección 2026-08-17**: esa referencia numérica ya no se
  usa aquí porque ADR-014 fue asignado después a una decisión distinta
  (elección de PWA, ver arriba); esta decisión de Opción B nunca tuvo
  ni necesitó ADR propio, confirmado explícitamente por el usuario en su
  momento. Ya no es un ítem `PENDING` — se conserva como registro
  histórico.

## Architecture Risks

- **Confiar en `CLAUDE.md`/documentación de proceso sin verificar contra
  código** es el riesgo que esta misma tarea existió para mitigar — ya
  ocurrió una vez en este repositorio (ver
  `docs/RECONCILIATION_REPORT.md` §8, hallazgo #1/#2). Mitigación:
  `docs/DEVELOPMENT_LOOP.md` Step 1 (Inspect) exige verificar código
  directamente, no solo documentación — pero ese mismo proceso (ADR-009)
  sigue sin aceptación formal.
- **Declarar una fase `COMPLETE` sin ejecutar su Completion Gate** —
  el riesgo que motivó ADR-009. Fase 2 y Fase 3 se declararon `COMPLETE`
  en este documento solo después de evaluar formalmente su Completion
  Gate criterio por criterio (`docs/PHASE_GATES.md` §Fase 2/§Fase 3,
  ambas 2026-08-16) — el riesgo permanece vigente para cualquier fase
  futura que se declare completa sin ese mismo proceso explícito.
- **Persistencia ahora existe (SQLite, ADR-013) pero no es automática,
  por decisión arquitectónica deliberada (Opción B, 2026-08-16)** — un
  `ExecutionRun` puede sobrevivir al fin del proceso que lo generó solo
  si el llamador invoca `store.save_execution_run(run)` explícitamente;
  `run_pipeline()` no lo hace por sí mismo, y no lo hará hasta que una
  interfaz operativa real (Fase 4) defina su propia política. La
  promesa de "auditabilidad" del nombre de Fase 3 sigue siendo parcial
  mientras no exista esa interfaz — esto ya no es una decisión abierta,
  es una consecuencia aceptada de la decisión ya tomada.
- ~~Ninguna interfaz de usuario existe~~ — **parcialmente mitigado
  2026-08-17**: `interfaces/cli/main.py` es un entrypoint real (línea de
  comandos), pero sigue sin ser una interfaz gráfica utilizable por un
  usuario no técnico — requiere conocer flags y ejecutar Python desde una
  terminal. Cualquier demostración a un usuario no técnico real sigue
  requiriendo Fase 4 (bloqueada).

## Next Recommended Action

Fase 2 y Fase 3 están `COMPLETE` (ambas 2026-08-16, ver §Current Phase).
El único trabajo de categoría A identificado y ejecutable sin ninguna
decisión `PENDING` (CLI, export gap, docstring desactualizado) se
completó el 2026-08-17 (ver §Sesión 2026-08-17 arriba). Tras esa
sesión, se auditó de nuevo la lista de deuda técnica conocida
completa y no queda ningún ítem restante de categoría A: todo lo que
sigue (Decision Score en el pipeline, ampliar `ExecutionRun` con
thresholds/sources_used, `DEFAULT_RISK_SEVERITY`, cobertura de los 12
`RiskType` restantes) requiere una decisión de negocio o de diseño
explícita que no le corresponde inventar al agente.

**Actualizado 2026-08-17**: el usuario resolvió explícitamente la
elección de interfaz (ADR-014, PWA) — ver §Pending Decisions. Esto
**no** desbloquea código de Fase 4 todavía: sigue `BLOCKED` por
framework de backend, framework de frontend, y deployment, ninguno
aprobado. El siguiente trabajo de código solo puede avanzar sobre fases
posteriores (Fase 4+), y todas siguen `BLOCKED` por decisiones `PENDING`
ajenas a esta tarea (framework backend/frontend/deployment de la PWA,
Supabase, Clerk, fuente externa, proveedor de IA, fórmulas de negocio de
Decision Score — ver §Pending Decisions). No se recomienda ninguna
acción de código adicional hasta que el usuario resuelva explícitamente
al menos una de esas decisiones bloqueantes.

No iniciar código de Fase 4 en adelante (dashboard/PWA/API HTTP) ni
resolver ninguna decisión `PENDING` de la lista de arriba como parte de
ese siguiente paso — ambos requieren aprobación explícita del usuario
primero. El CLI ya construido puede seguir usándose y extendiéndose con
ajustes menores (más flags, mejor mensaje de error) sin que eso cuente
como "iniciar Fase 4" — pero un backend HTTP, una PWA, o un empaquetado
`.exe` sí lo harían y quedan fuera de alcance hasta esa aprobación.

**Actualizado 2026-08-17 (bloque 3)**: el usuario aprobó explícitamente
FastAPI, React+Vite, Vercel, Git/GitHub, y Supabase — Fase 4A (backend
FastAPI) quedó **IMPLEMENTED** (ver §Sesión 2026-08-17 (bloque 3)), no
`COMPLETE` (Fase 4 global sigue sin cerrar su Completion Gate). El
siguiente trabajo recomendado, en orden, es: (1) instalar Node.js/npm
para poder iniciar el scaffold de React+Vite (Fase 4B, framework ya
elegido, no requiere nueva decisión); (2) que el usuario provisione un
proyecto Supabase real para poder verificar `SupabaseExecutionRunStore`
contra una base de datos de verdad; (3) investigar restricciones reales
de Vercel para Python/uploads/tiempo de ejecución antes de configurar
el deployment. Ninguno de los tres requiere una decisión de arquitectura
nueva — son pasos de ejecución de decisiones ya tomadas, bloqueados
únicamente por herramientas/credenciales que solo el usuario puede
proveer.

## Relacionado

`docs/RECONCILIATION_REPORT.md` (evidencia completa de esta fotografía),
`docs/PROJECT_PLAN.md` (plan de fases completo), `docs/PHASE_GATES.md`
(checklist de cierre normativa), `docs/DEVELOPMENT_LOOP.md` (proceso,
ADR-009 `Propuesta`), `docs/architecture/TECHNOLOGY_DECISIONS.md`
(matriz de tecnologías).
