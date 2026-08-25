# Juval — Plan Maestro de Desarrollo (PROJECT_PLAN)

Fuente de verdad canónica del plan de fases del proyecto. Normativo junto
con `CLAUDE.md` (reglas operativas), `docs/adr/` (decisiones),
`docs/DEVELOPMENT_LOOP.md` (proceso de ejecución obligatorio) y
`docs/PHASE_GATES.md` (checklist de cierre de fase).

Última verificación contra el repositorio real: 2026-08-17. Sin `.git`
inicializado. 185 tests pasando (`pytest`) — 177 al cierre de Fase 3
(2026-08-16) + 8 nuevos el 2026-08-17: `interfaces/cli/main.py` (7,
CLI recomendado por ADR-005 §15, implementado como trabajo de categoría
A tras el cierre de Fase 3, sin abrir Fase 4 — ver
`docs/PROJECT_STATUS.md` §Sesión 2026-08-17) + 1 en
`test_excel_exporter.py` (columnas `max_cog_target_profit`/
`max_cog_target_roi`, previamente calculadas pero no exportadas).

**Actualización documental 2026-08-17 (misma fecha, sesión posterior)**:
el usuario aprobó explícitamente ADR-014 (`Estado: Aceptada`) —
**PWA elegida como interfaz principal**, resolviendo la incertidumbre
PWA vs. `.exe` que ADR-005 dejaba abierta. Ningún código de Fase 4 se
implementó como parte de esta decisión — sigue `BLOCKED` hasta que se
resuelvan framework backend/frontend y deployment (ver §4 y §Fase 4
abajo, actualizados en este mismo cambio).

**Actualización 2026-08-17 (tercera sesión del día)**: ADR-015
(`Estado: Aceptada`) — el fallback `.get(risk_type, Severity.MEDIUM)`
de `DEFAULT_RISK_SEVERITY` (importer.py) ahora es fail-closed
(`KeyError` para cualquier `RiskType` no mapeado), cerrando un hueco de
correctitud identificado en un análisis arquitectónico previo. Decisión
puramente técnica — **no** aprueba HAZMAT→HIGH/BULKY→MEDIUM como
política comercial (siguen `PENDING`, fila §4 actualizada). 188 tests
pasando (185 + 3 nuevos, `test_excel_importer.py`).

**Actualización 2026-08-17 (cuarta sesión del día) — Fase 4A**: el
usuario aprobó FastAPI (backend), React+Vite (frontend, framework
elegido pero no implementado — sin Node/npm en este entorno), Vercel,
Git/GitHub, y Supabase. Se implementó y probó `interfaces/api/`
(ADR-016, FastAPI — `POST /api/v1/runs`, `GET /api/v1/runs/{id}/download`,
19 tests) y se preparó (sin verificar contra una base real, sin
`supabase`/`vercel`/`node` disponibles en este entorno) el adapter
`SupabaseExecutionRunStore` + migración SQL (ADR-017). Se corrigió de
paso un bug real de recurso (Windows) en
`infrastructure/excel/importer.py::import_excel` — el `Workbook` nunca
se cerraba. **209 tests pasando** (188 + 19 API + 2 estructurales de
Supabase). Fase 4 pasa a **`IMPLEMENTED` parcial (solo backend) /
Completion Gate `PENDING`** — no `COMPLETE`, ver §Fase 4 actualizada
abajo.

## 0. Cómo leer este documento

Cada fase documenta: **Objetivo**, **Alcance**, **Fuera de alcance**,
**Dependencias**, **Entradas**, **Salidas**, **Componentes**,
**Documentación**, **Tests**, **Criterios de aceptación**, **Riesgos**,
**Completion Gate**.

Ninguna fase se declara `COMPLETE` solo porque exista código — el cierre
real lo determina `docs/PHASE_GATES.md` (Universal Gate + gate
específico de la fase), ejecutado explícitamente como parte del
Development Loop (`docs/DEVELOPMENT_LOOP.md`).

**IMPORTANTE — decisiones tecnológicas no aprobadas**: Next.js,
Tailwind CSS, Vercel, Supabase y Clerk siguen siendo **decisiones
PENDING**. Ningún ADR las aprueba. Aparecen en este plan únicamente como
opciones candidatas de fases futuras — su mención aquí no constituye
aprobación.

**Actualizado 2026-08-17**: PWA vs. `.exe` **ya no está PENDING** — el
usuario eligió explícitamente PWA como interfaz principal (ADR-014,
`Estado: Aceptada`). `.exe` no se construirá como interfaz principal.
Esto no aprueba ningún framework/hosting concreto para esa PWA — ver §4.

## 1. Regla de dependencia entre fases

No se inicia una fase si las dependencias críticas de la fase anterior
no están satisfechas. Una fase no se considera completa solo porque
exista código — debe pasar su Completion Gate explícitamente.

## 2. Hallazgo de inspección — el repositorio ya avanzó más allá de lo documentado en este plan

⚠️ Al inspeccionar el estado real del repositorio para esta tarea se
encontró que **Fase 2 y parte de Fase 3 ya tienen código implementado**
(`domain/sourcing_record.py`, `domain/execution_run.py`,
`processing/pipeline.py`, `infrastructure/excel/{importer,exporter,
column_mapping}.py`, `application/run_pipeline.py`, más 54 tests nuevos
entre `tests/unit/` y `tests/integration/`, 165 en total). Esto ocurrió
fuera de esta conversación — no se implementó nada de Fase 2 en esta
tarea ni en la anterior. Se documenta el estado real tal como se
encontró, en vez de mantener el plan como si Fase 2 no hubiera
comenzado. Ver detalle de estado y gate pendiente en la ficha de cada
fase (§Fase 2, §Fase 3) y contradicciones documentales en
`docs/PHASE_GATES.md` §3.

## 3. Mapa de dependencias (resumen)

```
Fase 0 (repo + docs) — COMPLETE
   └─ Fase 1 (domain + processing core) — COMPLETE
        └─ Fase 2 (SourcingRecord + Excel vertical slice) — COMPLETE (gate PASS, 2026-08-16)
             ├─ Fase 3 (data quality + ExecutionRun + auditability) — COMPLETE (gate PASS, 2026-08-16, ADR-013 Aceptada)
             │     ├─ Fase 4 (dashboard PWA)                 [BLOCKED: interfaz elegida (ADR-014, PWA), pero stack frontend/backend/deployment sin aprobar]
             │     │     └─ Fase 9 (auth)                    [BLOCKED: Clerk PENDING]
             │     ├─ Fase 6 (fuentes externas autorizadas)   [BLOCKED: fuente concreta no aprobada]
             │     └─ Fase 8 (persistencia/Supabase)          [BLOCKED: Supabase PENDING]
             │           └─ Fase 9 (también depende de Fase 8)
             └─ Fase 5 (decision intelligence)                [BLOCKED: fórmulas de negocio no aprobadas]
                   └─ Fase 7 (AI Analyst)                     [BLOCKED: proveedor de IA no aprobado]
Fase 10 (production hardening) — depende de todas las fases relevantes al path de deployment elegido
```

## 4. Decisiones bloqueantes activas (actualizado 2026-08-17)

| Decisión pendiente | Bloquea | Estado | Referencia |
|---|---|---|---|
| ~~PWA vs. `.exe` vs. ambos~~ | Fase 4, Fase 10 | **RESUELTO 2026-08-17**: PWA elegida explícitamente por el usuario | ADR-014 (`Estado: Aceptada`); ADR-005 sigue vigente para la independencia de diseño, no se modifica |
| ~~Framework frontend (React + Vite)~~ | Fase 4B | **RESUELTO 2026-08-18**: implementado y finalizado — Dashboard analítico, catálogo server-side (paginación/búsqueda/filtro/orden), Run Detail, Upload, Export, Appearance/branding; 59/59 tests unitarios, 20/20 E2E reales, build/PWA verificados, visibilidad local verificada contra backend/frontend reales | `frontend/README.md`; commit `9127c64` |
| Vercel (deployment) | Fase 4, Fase 10 | **APROBADO como plataforma objetivo 2026-08-17**, restricciones reales (runtime Python, tamaño de payload, tiempo de ejecución) sin investigar todavía (sin Vercel CLI) | `docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloque 3) |
| ~~Framework backend de `interfaces/api/`~~ | Fase 4A | **RESUELTO 2026-08-17**: FastAPI, implementado (ADR-016, `Estado: Aceptada`, 19 tests) | `docs/adr/ADR-016-backend-fastapi.md` |
| Supabase | Fase 8 (persistencia compartida) — **y ahora también persistencia de producción de `ExecutionRun`, adelantado a Fase 4A** | **APROBADO como decisión arquitectónica 2026-08-17** (ADR-017, `Estado: Aceptada`); implementación preparada, **no verificada contra un proyecto real** (sin CLI, sin credenciales) | `docs/adr/ADR-017-supabase-persistencia-remota.md`, `docs/architecture/SUPABASE.md` |
| Identity Provider (**FusionAuth = dirección aprobada**, ADR-028; Okta **RECHAZADO** 2026-08-19; Clerk y el resto de candidatos CIAM descartados en ADR-021) | Fase 9 | **PROVIDER_SELECTED / NOT_IMPLEMENTED** — la dirección de proveedor está decidida (ADR-028), pero no hay tenant, despliegue ni configuración, el runtime sigue inactivo (`JUVAL_AUTH_MODE` sin definir) y **Amazon RF-03/RF-04 siguen `NOT_VERIFIED`**. Gap abierto: control 6 (exclusión del nombre) `B — PARTIALLY_SATISFIED` en FusionAuth 1.63.0+; la aclaración a Amazon Developer Support sigue pendiente de respuesta (ver `SP_API_REGISTRATION_REMEDIATION.md` §30) | `docs/adr/ADR-028-*.md`, `docs/adr/ADR-021-*.md`, `docs/adr/ADR-022-*.md`, `docs/compliance/SP_API_REGISTRATION_REMEDIATION.md` §30 |
| Fuente(s) externa(s) autorizada(s) concreta(s) | Fase 6 | **PENDING** | `DATA_SOURCES.md` §5 |
| Proveedor/modelo de IA | Fase 7 | **PENDING** | `AI_ANALYST.md` §6 |
| Fórmulas de negocio de Decision Score / thresholds reales | Fase 5 | **PENDING** | `DECISION_ENGINE.md` §7 |
| Severidad por defecto de riesgo declarado por proveedor (`DEFAULT_RISK_SEVERITY` en `importer.py`) — valores HAZMAT→HIGH/BULKY→MEDIUM | Cierre de Fase 2 | **PENDING** (aprobación de negocio de los valores en sí), pero ya **documentada formalmente** por ADR-010 (`Estado: Aceptada`, marcada explícitamente provisional) — el código referencia "ADR-010" y ese ADR existe con exactamente ese contenido. **Resuelto** (ver `docs/RECONCILIATION_REPORT.md` §6): no hay referencia colgante. Decisión técnica **distinta y separada**, ya resuelta 2026-08-17: el fallback silencioso para `RiskType` no mapeado ahora es fail-closed (`KeyError`) — ver ADR-015, `Estado: Aceptada` — sin aprobar HAZMAT/BULKY en sí. | `infrastructure/excel/importer.py` línea 47, `docs/adr/ADR-010-severidad-riesgo-provisional.md`, `docs/adr/ADR-015-fallback-severidad-riesgo-fail-closed.md` |
| Decisión de composición `SourcingRecord` (no duplicar campos) | Cierre de Fase 2 | Implementada y documentada por ADR-011 (`Estado: Aceptada`); el código referencia "ADR-011", no "ADR-009" — **no hay colisión de numeración** en el estado actual del código. **Resuelto** (ver `docs/RECONCILIATION_REPORT.md` §6). | `domain/sourcing_record.py` línea 8, `docs/adr/ADR-011-sourcing-record-composicion.md` |

Ambas filas se documentaron en una versión anterior de esta tarea como
referencias de ADR colgantes/en colisión; una reconciliación posterior
(`docs/RECONCILIATION_REPORT.md`, verificación directa contra el código
fuente) encontró que ambas ya estaban resueltas por ADR-010 y ADR-011,
creados en la misma sesión de trabajo después de que esta tabla se
escribiera por primera vez. Se deja la fila con el estado corregido, no
se elimina, para no perder el registro histórico de que este fue un
hallazgo real en su momento.

---

## FASE 0 — Foundation / Repository / Documentation

**Estado: COMPLETE**

- **Objetivo**: establecer el esqueleto del repositorio y la
  documentación arquitectónica base antes de cualquier lógica de
  negocio.
- **Alcance**: `docs/architecture/ARCHITECTURE.md`, ADR-001 a ADR-005,
  esqueleto de directorios (`domain/`, `processing/`, `application/`,
  `infrastructure/*`, `interfaces/*`, `tests/*`) con `README.md` de
  propósito por carpeta, `pyproject.toml`, `.gitignore`, `README.md`
  raíz.
- **Fuera de alcance**: lógica de negocio, modelo de dominio, I/O de
  Excel, integraciones externas, dashboard, IA, `git init`.
- **Dependencias**: ninguna (fase inicial, repositorio greenfield).
- **Entradas**: brief inicial del proyecto.
- **Salidas**: documento de arquitectura + 5 ADRs aceptados + esqueleto
  de directorios.
- **Componentes**: `src/juval/*/README.md`, `pyproject.toml`,
  `.gitignore`.
- **Documentación**: `docs/architecture/ARCHITECTURE.md` (normativo de
  esta fase).
- **Tests**: no aplica (sin código de negocio todavía).
- **Criterios de aceptación**: esqueleto de directorios con propósito
  documentado por carpeta; `ARCHITECTURE.md` documenta principios,
  capas, regla de dependencia, estrategias de provenance/Excel/tests;
  ADR-001 a ADR-005 en estado Aceptada.
- **Riesgos**: ninguno abierto propio de esta fase.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 0 — **PASS**
  (verificado por inspección directa del repositorio).

---

## FASE 1 — Domain + Processing Core

**Estado: COMPLETE**

- **Objetivo**: implementar y probar el modelo de dominio puro
  (`Product`, `CostInputs`/`FeeInputs`, `RiskProfile`, `Decision`,
  `Provenance`/`FieldValue`) y el Processing Core (`profitability`,
  `decision_engine`, `decision_score`, `data_quality`), sin I/O.
- **Alcance**: `src/juval/domain/{provenance,product,costs,risk,decision,
  identifiers,units,issues}.py`, `src/juval/processing/{profitability,
  decision_engine,decision_score,data_quality}.py`.
- **Fuera de alcance**: clase ensambladora `SourcingRecord`, Excel
  Importer/Exporter, adapters externos, código de AI Analyst, dashboard,
  auth, persistencia. (Nota: parte de este "fuera de alcance" ya se
  implementó en Fase 2, ver §2 arriba — no se relitiga aquí, se deja
  constancia para que el lector no interprete esta lista como vigente
  hoy sin cruzarla con el estado real de Fase 2.)
- **Dependencias**: Fase 0 completa.
- **Entradas**: `ARCHITECTURE.md` + ADR-001 a ADR-005.
- **Salidas**: módulos de dominio y processing probados.
- **Componentes**: los listados en Alcance, más
  `tests/unit/test_{costs,data_quality,decision_engine,decision_score,
  identifiers,product,profitability,provenance,risk,units}.py`.
- **Documentación**: `DATA_MODEL.md`, `DATA_DICTIONARY.md`,
  `DATA_PROVENANCE.md`, `DATA_SOURCES.md`, `DECISION_ENGINE.md`,
  `AI_ANALYST.md` (diseño), ADR-006, ADR-007, ADR-008.
- **Tests**: 111 tests unitarios pasando en el momento de cierre de esta
  fase (hoy son 177 en el repo, con los añadidos de Fase 2/3, incluida
  la persistencia SQLite de ADR-013).
- **Criterios de aceptación**: invariantes estructurales reforzadas en
  `__post_init__`; `VerificationStatus` mutuamente excluyente; fórmulas
  de `profitability.py` verificadas contra valores calculados a mano;
  `decision_engine` respeta precedencia PASS→REVIEW→BUY; `Thresholds`
  sin default exportado (ADR-007).
- **Riesgos**: Decision Score sigue siendo experimental — heredado
  explícitamente a Fase 5, no resuelto aquí.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 1 — **PASS**.

---

## FASE 2 — SourcingRecord + Excel Vertical Slice

**Estado: COMPLETE** (Completion Gate evaluado formalmente 2026-08-16,
todos los criterios obligatorios en `PASS` — ver `docs/PHASE_GATES.md`
§Fase 2)

El código de esta fase existía en el repositorio antes de que se
evaluara formalmente su Completion Gate. El único criterio que seguía en
`FAIL` (`record_ref` sin decisión arquitectónica aprobada) se resolvió
mediante ADR-012 (`Estado: Aceptada`, 2026-08-16), que documenta la
estrategia ya implementada (`row_{n}[:supplier_sku]`) sin modificarla.
No se cambió código de producción para cerrar este gate — solo se
formalizó una decisión ya tomada implícitamente por la implementación.

- **Objetivo**: ensamblar `SourcingRecord` como agregado real e
  implementar el primer vertical slice completo Excel → dominio →
  processing → Excel, con datos verificados directamente del Excel
  (`VERIFIED`/`NOT_FOUND`/`INVALID`), sin enriquecimiento externo ni
  reglas de inferencia todavía.
- **Alcance**: `domain/sourcing_record.py`, `application/run_pipeline.py`,
  `infrastructure/excel/{importer,exporter,column_mapping}.py`,
  `processing/pipeline.py`.
- **Fuera de alcance**: adapters de enriquecimiento externo (Fase 6),
  reglas de inferencia más allá de lo trivial/estructural, dashboard/PWA
  (Fase 4), persistencia más allá de archivos/memoria, autenticación.
- **Dependencias**: Fase 1 completa (satisfecho).
- **Entradas**: `tests/fixtures/sample_sourcing_TEST_DATA.xlsx`
  (generado por `tests/fixtures/generate_sample.py`, datos sintéticos
  marcados explícitamente como TEST DATA).
- **Salidas** (encontradas en el repo): `SourcingRecord` implementado
  (`domain/sourcing_record.py`); Excel Importer/Exporter implementados
  con columnas identificadas por nombre normalizado, nunca por posición;
  `run_pipeline()` en `application/` como único módulo que conoce tanto
  `infrastructure/` como `processing/`.
- **Componentes implementados**: `domain/sourcing_record.py`,
  `infrastructure/excel/importer.py`, `infrastructure/excel/exporter.py`,
  `infrastructure/excel/column_mapping.py`,
  `processing/pipeline.py` (`process_record`/`process_batch`),
  `application/run_pipeline.py`.
- **Componentes pendientes**: ninguno — el único ítem que quedaba
  (`interfaces/cli/` sin entrypoint real, `ARCHITECTURE.md` §15) se
  implementó el 2026-08-17 como trabajo de categoría A posterior al
  cierre de esta fase (`src/juval/interfaces/cli/main.py`, ver
  `docs/PROJECT_STATUS.md` §Sesión 2026-08-17). No se reabre el gate de
  Fase 2 por esto — ya estaba `PASS` con el CLI anotado como deuda no
  bloqueante; esta nota solo actualiza el estado real del componente.
- **Documentación**: **corregida** (`docs/RECONCILIATION_REPORT.md`
  §7-§8). Una versión anterior de esta sección afirmaba que `README.md`
  raíz y `docs/architecture/DATA_MODEL.md` §1/§5 seguían describiendo
  "Fase 1... sin Excel Importer/Exporter" y "`SourcingRecord`... no está
  implementado todavía como clase" — verificado directamente contra el
  contenido actual de ambos archivos, esa afirmación ya no es cierta:
  `README.md` dice explícitamente "Fase 2: primer vertical slice
  funcional" y `DATA_MODEL.md` §1 dice explícitamente "Implementado en
  `domain/sourcing_record.py` (Fase 2)". El ítem universal 6 de
  `PHASE_GATES.md` (documentación actualizada) ya no falla por esta
  causa específica — sigue habiendo otra deuda documental real (CLI
  ausente, `record_ref` sin aprobación formal, ver más abajo) que no se
  resuelve aquí.
- **Tests**: `tests/unit/test_sourcing_record.py` (7),
  `tests/unit/test_pipeline.py` (7),
  `tests/integration/test_excel_importer.py` (13),
  `tests/integration/test_excel_exporter.py` (4),
  `tests/integration/test_pipeline_end_to_end.py` (6) — 37 tests nuevos
  de esta fase, todos pasando.
- **Criterios de aceptación**: columnas identificadas solo por nombre de
  encabezado (verificado en `importer.py::normalize_header` +
  `column_mapping.py`) — cumplido; Excel exportado muestra columnas de
  provenance separadas (`<campo>` + `<campo>_status`) — cumplido,
  verificado en `exporter.py::HEADERS`; taxonomía
  `FATAL`/`RECORD_ERROR`/`WARNING` aplicada — cumplido; Processing Core
  (`pipeline.py`) no importa `openpyxl` ni conoce nombres de columna —
  cumplido (verificado por inspección de imports).
- **Riesgos**:
  1. ~~`record_ref` se construye como `row_{n}[:supplier_sku]` sin
     decisión formalmente APPROVED~~ — **RESUELTO 2026-08-16** por
     ADR-012 (`Estado: Aceptada`): la estrategia ya implementada queda
     documentada y aprobada tal cual, sin cambio de código.
     `ARCHITECTURE.md` §14.3 queda cerrada.
  2. `DEFAULT_RISK_SEVERITY` en `importer.py` asigna severidad por
     defecto a HazMat/Bulky declarados por el proveedor — el propio
     código dice explícitamente que es un placeholder "NOT
     reviewed/approved by the business", y referencia ADR-010, que
     **sí existe** (`Estado: Aceptada`, contenido consistente con la
     cita del código — ver `docs/RECONCILIATION_REPORT.md` §6). La
     referencia en sí ya no es un problema de documentación; lo que
     sigue pendiente es la **aprobación de negocio de los valores en sí**
     (HAZMAT→HIGH, BULKY→MEDIUM), que ADR-010 marca explícitamente como
     no aprobada — eso no se resuelve en esta tarea.
  3. `domain/sourcing_record.py` referencia "ADR-011" (no "ADR-009") para
     la decisión de "composición, no duplicación", y ADR-011 documenta
     exactamente esa decisión (`Estado: Aceptada`). No hay colisión de
     numeración en el estado actual del código — ver
     `docs/RECONCILIATION_REPORT.md` §6 (`PHASE_GATES.md` §3 queda
     corregido en el mismo cambio que esta fila).
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 2 — **PASS**,
  evaluado formalmente 2026-08-16 (código y tests existen y pasan; las
  dos referencias de ADR ya estaban resueltas; `record_ref` quedó
  formalmente aprobado por ADR-012; CLI sigue ausente pero queda anotado
  como deuda técnica no bloqueante, no como criterio de cierre de esta
  fase). **Fase 2 declarada `COMPLETE`.**

---

## FASE 3 — Data Quality + ExecutionRun + Auditability

**Estado: COMPLETE** (Completion Gate evaluado formalmente 2026-08-16,
todos los criterios obligatorios en `PASS` — ver `docs/PHASE_GATES.md`
§Fase 3)

Fase 2 (de la que depende) ya había cerrado su Completion Gate (`PASS`,
2026-08-16). Persistencia local de `ExecutionRun` fue implementada esa
misma fecha vía SQLite (ADR-013), a petición explícita del usuario tras
el pre-check de Fase 3. El usuario resolvió explícitamente (Opción B)
que `run_pipeline()` **no** debe integrar persistencia automática —
permanece puro/determinista; persistir es responsabilidad explícita del
caller. Finalmente, el usuario aprobó explícitamente ADR-013
(`Estado: Aceptada`, 2026-08-16), cerrando el único ítem que quedaba
pendiente para el gate de esta fase (ver `docs/PHASE_GATES.md` §Fase 3).

- **Objetivo**: registrar `ExecutionRun` para trazabilidad/
  reproducibilidad de corridas, y ampliar las validaciones de
  `data_quality.py`.
- **Alcance**: `domain/execution_run.py`, integración con
  `application/run_pipeline.py`, validaciones ampliadas de
  `processing/data_quality.py` (`validate_identification`,
  `validate_dimensions`, `validate_price`,
  `validate_competition_consistency`, `validate_financial_consistency`,
  ya usadas por `processing/pipeline.py`).
- **Fuera de alcance**: persistencia en base de datos **compartida/remota**
  (Fase 8, Supabase); UI para navegar corridas históricas (Fase 4+).
  Nota de reconciliación: una versión anterior de esta línea decía
  simplemente "persistencia en base de datos (Fase 8)" sin distinguir
  local de remota — la persistencia **local** de un solo usuario (SQLite,
  ADR-013) se implementó dentro de Fase 3 por decisión explícita del
  usuario; Fase 8 sigue refiriéndose específicamente a persistencia
  compartida/remota (Supabase), que sigue `BLOCKED`.
- **Dependencias**: Fase 2 — **satisfecho** (gate `PASS`, 2026-08-16).
- **Entradas**: pipeline de Fase 2.
- **Salidas** (encontradas en el repo): `ExecutionRun` implementado y
  probado (`domain/execution_run.py`), construido por
  `application/run_pipeline.py::run_pipeline()` con `input_hash`
  (SHA-256 vía `hash_file()`), conteos, y `status`
  (`SUCCESS`/`PARTIAL_SUCCESS`/`FAILED`/`RUNNING`). Persistencia local vía
  `infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore`,
  detrás del puerto `application/execution_run_store.py::ExecutionRunStore`.
- **Componentes implementados**: `domain/execution_run.py`
  (`ExecutionRun`, `ExecutionStatus`, `hash_file`), wiring en
  `run_pipeline()`, `application/execution_run_store.py`
  (`ExecutionRunStore`, puerto), `infrastructure/logging/sqlite_execution_run_store.py`
  (`SqliteExecutionRunStore`, adapter SQLite, ADR-013 `Aceptada`).
- **Componentes pendientes**: `run_pipeline()` no invoca el store
  automáticamente — persistir una corrida requiere que el llamador
  invoque `store.save_execution_run(run)` explícitamente. **Esto es una
  decisión arquitectónica confirmada (Opción B, 2026-08-16), no una
  brecha por resolver** — ver ADR-013 §"Qué NO resuelve esta decisión".
  No existe `list_execution_runs()` ni consulta de historial más allá de
  `load_execution_run(execution_id)`. Logging técnico operacional
  (stdout/archivo, distinto del registro de auditoría `ExecutionRun`)
  sigue sin implementar. La política de cuándo invocar el store queda
  diferida a la primera interfaz operativa real (CLI/API, Fase 4).
- **Documentación**: **actualizada 2026-08-16** — `ARCHITECTURE.md` §8 y
  `EXECUTION_MODEL.md` §5 ya no describen persistencia en JSON como
  diseño no implementado; describen el estado real (SQLite, ADR-013,
  alcance y limitaciones).
- **Tests**: `tests/unit/test_execution_run.py` (11),
  `tests/integration/test_reproducibility.py` (2),
  `tests/integration/test_execution_run_store.py` (12, nuevo
  2026-08-16) — 25 tests de esta fase, todos pasando.
- **Criterios de aceptación**: contenido mínimo de `ExecutionRun`
  presente — cumplido; reproducibilidad demostrada
  (`test_reproducibility.py`) — cumplido para el caso sin fuentes
  externas; persistencia entre corridas — **cumplido** (mecanismo
  implementado y probado con round-trip entre conexiones/instancias de
  store distintas; no automática dentro de `run_pipeline()` por decisión
  arquitectónica deliberada, Opción B, no por una brecha de
  implementación).
- **Riesgos**: la persistencia es opt-in por diseño deliberado (Opción
  B) — sigue existiendo el riesgo de que un usuario final asuma que toda
  corrida queda auditada automáticamente cuando en realidad requiere una
  llamada explícita adicional; este riesgo queda documentado aquí y en
  ADR-013, aceptado conscientemente en vez de resolverse cambiando
  `run_pipeline()`, y quedará mitigado cuando la primera interfaz
  operativa real (Fase 4) defina su propia política de invocación.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 3 — **PASS**,
  evaluado formalmente 2026-08-16. Todos los criterios obligatorios
  (Universal Gate + específicos de Fase 3) en `PASS`. **Fase 3 declarada
  `COMPLETE`.**

---

## FASE 4 — Dashboard PWA

**Estado: IMPLEMENTED (backend + frontend), sin desplegar — Completion
Gate PENDING** (actualizado 2026-08-17, bloque 4)

Fase 4 se divide en dos sub-fases desde 2026-08-17, por decisión
operativa (no arquitectónica) tomada al ejecutar la implementación:

- **Fase 4A — Backend FastAPI**: **IMPLEMENTED**. `interfaces/api/`
  (`main.py`/`models.py`/`service.py`), FastAPI (ADR-016, `Estado:
  Aceptada`), `POST /api/v1/runs` + `GET /api/v1/runs/{execution_id}/download`,
  19 tests de integración contra el Core real. Ver
  `docs/architecture/API_CONTRACT.md`.
- **Fase 4B — Frontend PWA**: **COMPLETE para el alcance actual aprobado**
  (finalizado 2026-08-18, commit `9127c64`). `frontend/` (React 19 +
  TypeScript + Vite 8 + `vite-plugin-pwa`): Dashboard dirigido por
  `GET /analytics` (KPIs, decisión, HazMat/Bulky, provenance, profitability,
  data quality), catálogo server-side (paginación/búsqueda/filtro/orden vía
  `GET /records`), Run Detail, Upload, Export, Appearance/branding. 59/59
  tests de componente/integración (Vitest + Testing Library), 20/20 tests
  E2E reales (Playwright) contra backend real en ejecución (no mock), lint
  limpio, TypeScript limpio, `npm run build` exitoso, artefactos PWA
  generados, visibilidad local verificada (FastAPI + Vite reales,
  0 errores de consola en las 6 rutas) — ver `frontend/README.md`.
  Decision Score (`DOMAIN_NOT_INTEGRATED`), AI Analyst
  (`NOT_IMPLEMENTED`) e identidad/IdP
  (`BLOCKED_PENDING_AMAZON_RESPONSE`) permanecen fuera de alcance por
  diseño — no bloquean este estado `COMPLETE`.

Decisiones que quedaban `PENDING` en la versión anterior de esta
sección, actualizadas:
- Framework backend: **RESUELTO** (FastAPI, ADR-016).
- Framework frontend: **RESUELTO e IMPLEMENTED** (React + Vite).
- Deployment del frontend (Vercel): **DESPLEGADO EN PRODUCCIÓN
  2026-08-18**. Proyecto `juval1/juval-frontend`, URL real
  `https://juval-frontend.vercel.app`. `frontend/vercel.json` requirió
  una corrección real (rewrite SPA a `index.html` — sin ella, `/upload`,
  `/products`, `/runs`, `/appearance` devolvían 404 real en navegación
  directa, verificado por HTTP antes y después). Variable de entorno de
  producción: únicamente `VITE_API_BASE_URL` (pública, sin secretos).
  Confirmado en el bundle servido: apunta al backend real de Railway, sin
  URL local ni DSN embebidos. Verificado con navegador real (Playwright)
  contra la URL de producción: carga, sin errores de CORS en consola,
  llama al backend real.
- Hosting del backend: **DESPLEGADO EN PRODUCCIÓN 2026-08-18** (Railway,
  ADR-018). Proyecto `juval-backend`, servicio `juval-backend`, URL real
  `https://juval-backend-production.up.railway.app`. `railway.toml`
  requirió una corrección real: el builder `RAILPACK` completaba
  `pip install .[postgres]` en el build pero el contenedor de runtime no
  heredaba los paquetes instalados (`uvicorn: command not found`, luego
  `No module named uvicorn` con `python -m uvicorn`) — dos despliegues
  reales lo probaron. Cambiado a `NIXPACKS`; despliegue posterior
  exitoso, `/docs` y `/api/v1/runs` responden 200. Variables de
  producción configuradas (nombres, nunca valores):
  `JUVAL_EXECUTION_STORE=supabase`, `JUVAL_SUPABASE_DB_URL` (secreto,
  vía stdin, nunca impreso ni commiteado), `JUVAL_CORS_ORIGINS` (fijado
  al origin exacto de Vercel, sin wildcard). `JUVAL_AUTH_MODE` no está
  configurada — auth permanece desactivada intencionalmente. Persistencia
  Supabase de producción verificada con un ciclo real
  write→read→cleanup a través de la API desplegada (no solo variables de
  entorno): subida real con `persist=true`, lectura confirmada en
  `/runs`, `/runs/{id}`, `/runs/{id}/analytics`, `/runs/{id}/records`, y
  limpieza posterior verificada con `SELECT COUNT(*) = 0`.
- `PRODUCTION_UI_E2E = VERIFIED` (2026-08-18): el flujo completo de
  usuario se ejercitó con navegador real (Playwright) contra
  `https://juval-frontend.vercel.app` — Upload (fixture determinista) →
  persistencia real → Dashboard (`GET /analytics`, confirmado que
  `GET /records` **no** se llama para construir las gráficas) →
  Catalog (búsqueda/filtro/orden server-side confirmados por request de
  red real) → Run Detail (navegación dura a la ruta anidada,
  reconfirma el rewrite SPA de Vercel en carga de página fresca;
  provenance VERIFIED/INFERRED/NOT_FOUND/INVALID distinguibles) →
  Export (descarga de archivo real confirmada). Responsive verificado en
  desktop/tablet/mobile. Service worker confirmado `registered: activated`
  en producción. Cero errores de CORS, cero 401/403/500 inesperados, cero
  llamadas a `localhost`. Dato sintético limpiado tras la verificación
  (mismo mecanismo de `DELETE` acotado por `execution_id`, verificado con
  `SELECT COUNT(*) = 0` y confirmado además vía `GET /runs` real).
- Supabase: **aprobado como persistencia de producción** (ADR-017), y
  **verificado contra un proyecto real 2026-08-17/18** — proyecto
  `twrgzsbpazcjhhfolaju` (`ACTIVE_HEALTHY`), migración aplicada,
  `SupabaseExecutionRunStore` probado end-to-end vía la API real
  (`tests/integration/test_api_supabase.py`, commit `d5d0035`). Lo que
  sigue sin verificar es su uso en producción real (Railway no está
  desplegado, así que nadie ha confirmado el store `supabase` operando
  fuera del entorno de desarrollo local).
- Git: **repositorio local inicializado** (`git init`), 146 archivos
  staged y verificados sin secretos; **commit sin ejecutar** — requiere
  `git config user.name`/`user.email`, que el agente tiene prohibido
  configurar (Git Safety Protocol). GitHub (remoto) sigue sin
  configurar — requiere que el usuario cree el repositorio y provea la
  URL/credenciales.

`interfaces/cli/main.py` sigue sin ser parte de esta fase (es la
interfaz previa, ADR-005, sin relación con PWA).

- **Objetivo**: primera UI real para ver `SourcingRecord`s, decisiones y
  provenance — cliente delgado (ADR-001, ADR-014, ADR-016) que llama al
  Application Layer.
- **Alcance**: `interfaces/api/` (backend PWA, **IMPLEMENTED**) +
  frontend PWA (`frontend/`, React + Vite, **IMPLEMENTED**, sin
  desplegar).
- **Fuera de alcance**: autenticación (Fase 9), UI del AI Analyst (Fase
  7) — persistencia de `ExecutionRun` ya no está estrictamente fuera de
  alcance (ver ADR-017, adelantada a esta fase para el caso de
  producción vía Supabase, además del caso local vía SQLite ya
  existente).
- **Dependencias**: Fase 2/3 con Completion Gate en `PASS` —
  **satisfecho**; elección de interfaz — **satisfecho** (ADR-014);
  framework backend — **satisfecho** (ADR-016). **BLOCKED además**
  hasta que exista Node.js/npm (Fase 4B) y, para el gate global de
  Fase 4, hasta completar frontend + E2E + seguridad + documentación
  (ver Completion Gate abajo).
- **Entradas**: `SourcingRecord`s procesados + `ExecutionRun` de Fase 3.
- **Salidas**: Fase 4A — API JSON con decisión, razones, y provenance
  por campo (`API_CONTRACT.md`). Fase 4B — UI que consume esa API.
- **Componentes**: `src/juval/interfaces/api/*.py` (**IMPLEMENTED**);
  `src/juval/infrastructure/persistence/supabase_execution_run_store.py`
  (**IMPLEMENTED, no verificado**); `frontend/` (**IMPLEMENTED**, React
  + Vite + PWA, sin desplegar).
- **Documentación**: `docs/architecture/API_CONTRACT.md` (creado),
  `docs/architecture/SUPABASE.md` (creado); `frontend/e2e/README.md`
  (creado, cómo correr el E2E). `docs/architecture/UI.md` dedicado no
  se creó — el contrato del frontend ya queda cubierto por
  `API_CONTRACT.md` + los propios componentes tipados
  (`frontend/src/types.ts`).
- **Tests**: backend — 19 tests de integración (**hecho**). Frontend —
  9 tests (**hecho**). E2E del camino feliz completo (upload →
  procesamiento → resultado → descarga, vía navegador real) — **hecho**,
  1/1 pasando contra el backend real (`frontend/e2e/smoke.spec.ts`).
- **Criterios de aceptación**: la API no duplica ninguna regla de
  negocio (verificado — `interfaces/api/service.py` solo traduce, no
  calcula); el frontend tampoco (verificado por inspección —
  `frontend/src/` no calcula profit/ROI/severidad/decisión); provenance
  visible por campo, no colapsada, en backend y frontend (verificado
  por test en ambos); decisión + razones mostradas literalmente como
  las produjo el Decision Engine (verificado).
- **Riesgos**: ninguno técnico nuevo. Riesgo documentado:
  `SupabaseExecutionRunStore` no está verificado contra una base real
  — no tratarlo con la misma confianza que `SqliteExecutionRunStore`
  hasta que lo esté. Ningún commit de Git existe todavía (bloqueo de
  configuración, ver arriba) — el trabajo de esta sesión vive solo en
  el filesystem local hasta que el usuario complete `git config` y se
  ejecute el commit.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 4 — **PENDING**
  (backend y frontend cumplen sus criterios propios; Fase 4 global no
  se declara `COMPLETE` hasta deployment real + Supabase verificado +
  seguridad + el resto del gate).

---

## FASE 5 — Decision Intelligence

**Estado: NOT STARTED — BLOCKED**

⚠️ Bloqueada: fórmulas de subscore y thresholds comerciales reales no
aprobados por negocio (`DECISION_ENGINE.md` §7).

- **Objetivo**: formalizar las fórmulas de cada subscore del Decision
  Score (hoy experimental) y los `Thresholds` comerciales reales, con
  aprobación de negocio explícita — sin dejar de ser código
  determinístico.
- **Alcance**: `processing/decision_score.py` (fórmulas de subscore),
  refinamiento de reglas (ej. caso límite
  `severity == maximum_risk_severity`, abierto en `DECISION_ENGINE.md`
  §7.4).
- **Fuera de alcance**: scoring basado en IA (prohibido, ADR-006/
  ADR-008); cambios de UI (Fase 4).
- **Dependencias**: Fase 1 (el motor ya existe). Requiere decisión de
  negocio documentada por fórmula — si no existe, es STOP de Step 2 del
  Development Loop, no algo que el agente decida.
- **Entradas**: reglas de negocio aprobadas (externas al código).
- **Salidas**: Decision Score v2 documentado, probado y aprobado.
- **Componentes**: cambios en `processing/decision_score.py`.
- **Documentación**: `DECISION_ENGINE.md` actualizado para retirar la
  advertencia de "experimental" una vez aprobado.
- **Tests**: una prueba unitaria por fórmula de subscore contra valores
  calculados a mano.
- **Criterios de aceptación**: cada fórmula trazable a una decisión de
  negocio aprobada, no inventada por el agente.
- **Riesgos**: riesgo central es que el agente "rellene" una fórmula
  razonable sin aprobación — explícitamente prohibido.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 5 — **BLOCKED**.

---

## FASE 6 — Authorized External Data Sources

**Estado: NOT STARTED — BLOCKED**

⚠️ Bloqueada: ninguna fuente externa concreta está aprobada hoy
(`DATA_SOURCES.md` §5).

- **Objetivo**: implementar el primer adapter en
  `infrastructure/enrichment/` para verificar ASIN/BSR/precio/
  competencia, sobre una fuente autorizada y documentada — nunca
  scraping ni bypass.
- **Alcance**: adapter detrás de un puerto definido en `processing/`;
  produce `FieldValue` con `source_type`/`verification_status`
  correctos.
- **Fuera de alcance**: cualquier método no autorizado; enriquecimiento
  vía IA.
- **Dependencias**: Fase 2 con gate en `PASS` — **satisfecho**
  (2026-08-16); Fase 3 con gate en `PASS` — **satisfecho** (2026-08-16).
  **BLOCKED además** hasta que una fuente concreta esté aprobada.
- **Entradas**: contrato de fuente aprobado (checklist
  `DATA_SOURCES.md` §4).
- **Salidas**: adapter con tests, `DATA_SOURCES.md` actualizado.
- **Componentes**: `src/juval/infrastructure/enrichment/<fuente>.py`.
- **Documentación**: `DATA_SOURCES.md` actualizado con la integración
  concreta; posible ADR nuevo.
- **Tests**: unit tests con respuestas mockeadas; tests de corrección de
  `verification_status`.
- **Criterios de aceptación**: nunca `VERIFIED` para un dato no
  garantizado; "no encontrado" nunca se traduce en valor por defecto.
- **Riesgos**: mayor riesgo de violar la regla de "no scraping" — gate
  exige autorización documentada antes de escribir código.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 6 — **BLOCKED**.

---

## FASE 7 — AI Analyst

**Estado: NOT STARTED — BLOCKED**

⚠️ Bloqueada: proveedor/modelo de IA no aprobado (`AI_ANALYST.md` §6).

- **Objetivo**: implementar la capa de IA Analyst según el contrato de
  ADR-008/`AI_ANALYST.md` — explicación/resumen/comparación,
  estrictamente downstream y de solo lectura.
- **Alcance**: nuevo módulo (`processing/ai_analyst/` o
  `interfaces/ai/`, ubicación pendiente), manejo de prompt/respuesta,
  logging de auditoría.
- **Fuera de alcance**: cualquier modificación de
  profit/roi/margin/score/decision.
- **Dependencias**: Fase 2 (`SourcingRecord`); se recomienda Fase 5
  cerrada primero. **BLOCKED además** hasta proveedor de IA aprobado y
  diseño de auditoría decidido.
- **Entradas**: `SourcingRecord`s ya procesados.
- **Salidas**: texto de explicación/resumen/comparación + log de
  auditoría por llamada.
- **Componentes**: módulo de IA (ubicación TBD).
- **Documentación**: `AI_ANALYST.md` (ya existe el contrato; se
  actualiza con detalles de implementación al aprobarse).
- **Tests**: tests de contrato ("qué NO puede hacer" de ADR-008).
- **Criterios de aceptación**: 100% solo-lectura verificado por tests;
  cada llamada auditable.
- **Riesgos**: alucinación de campos sensibles.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 7 — **BLOCKED**.

---

## FASE 8 — Persistence / Supabase

**Estado: NOT STARTED — BLOCKED**

⚠️ Bloqueada: introducir Supabase no está aprobado (`CLAUDE.md` §14).

- **Objetivo**: introducir persistencia durable (histórico de
  `SourcingRecord`/`ExecutionRun`) solo cuando exista necesidad real
  demostrada.
- **Alcance**: `infrastructure/persistence/` (nuevo) implementando un
  puerto definido por `processing/`/`application/`.
- **Fuera de alcance**: autenticación (Fase 9).
- **Dependencias**: Fase 3 con gate en `PASS` — **satisfecho**
  (2026-08-16; la persistencia local de Fase 3 es SQLite/single-user,
  ADR-013 — no sustituye ni resuelve la persistencia compartida/remota
  que es el objeto de esta fase). **BLOCKED además** hasta aprobación
  explícita de Supabase + necesidad real demostrada.
- **Entradas**: decisión aprobada de usar Supabase + caso de uso real.
- **Salidas**: esquema/migraciones, adapter de persistencia.
- **Componentes**: `src/juval/infrastructure/persistence/*.py`,
  migraciones SQL.
- **Documentación**: `docs/architecture/PERSISTENCE.md` (nuevo, a
  crear).
- **Tests**: tests de migración, round-trip, aislamiento de datos si
  aplica.
- **Criterios de aceptación**: ninguna tabla creada "para estar
  preparados"; cada tabla mapea a un concepto de dominio ya
  implementado.
- **Riesgos**: fijar el esquema antes de que el dominio termine de
  estabilizarse.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 8 — **BLOCKED**.

---

## FASE 9 — Authentication / Authorization

**Estado: NOT STARTED — BLOCKED**

⚠️ Bloqueada: introducir Clerk no está aprobado (`CLAUDE.md` §14).

- **Objetivo**: introducir autenticación solo cuando el producto ya no
  pueda funcionar razonablemente sin ella.
- **Alcance**: users, sessions, organizations/workspaces, roles,
  permissions, data isolation.
- **Fuera de alcance**: rediseño del modelo de dominio.
- **Dependencias**: Fase 4 (UI) y Fase 8 (persistencia). **BLOCKED
  además** hasta aprobación explícita de Clerk + diseño documentado.
- **Entradas**: documento de diseño de auth aprobado.
- **Salidas**: middleware/wiring de auth, aislamiento de datos
  reforzado.
- **Componentes**: wiring de auth en `src/juval/interfaces/api/`.
- **Documentación**: `docs/architecture/AUTH.md` (nuevo, a crear antes
  de implementar).
- **Tests**: aislamiento de datos por usuario, permisos por rol.
- **Criterios de aceptación**: ninguna ruta/dato accesible sin pasar por
  el límite de auth documentado.
- **Riesgos**: retrofitting de auth después de UI/datos ya existentes es
  más invasivo.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 9 — **BLOCKED**.

---

## FASE 10 — Production Hardening

**Estado: NOT STARTED — BLOCKED**

⚠️ Alcance de Vercel bloqueado por ADR-005 (solo aplica si el path
elegido incluye PWA/web).

- **Objetivo**: endurecimiento final para uso productivo real —
  deployment, monitoreo, revisión de seguridad, rendimiento bajo volumen
  esperado.
- **Alcance**: CI/CD, configuración de deployment (Vercel si aplica),
  revisión de seguridad, prueba de carga/volumen.
- **Fuera de alcance**: funcionalidad de negocio nueva.
- **Dependencias**: todas las fases relevantes al path de deployment
  elegido, completas. **BLOCKED además** hasta que ADR-005 se resuelva.
- **Entradas**: sistema funcionalmente completo para el alcance de
  negocio de v1.
- **Salidas**: sistema en producción, desplegado y monitoreado.
- **Componentes**: configuración CI/CD, configuración de deployment.
- **Documentación**: checklist de seguridad ejecutado, plan de rollback.
- **Tests**: regresión completa (unit + integration + E2E).
- **Criterios de aceptación**: reglas de seguridad de `CLAUDE.md` §16
  verificadas; sin hallazgos críticos/altos sin resolver.
- **Riesgos**: ninguno específico más allá del riesgo genérico de
  producción.
- **Completion Gate**: ver `docs/PHASE_GATES.md` §Fase 10 — **BLOCKED**.
