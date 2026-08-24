# Juval — Testing Strategy

Estado real verificado por ejecución directa (2026-08-19, tras la
recuperación de capacidades Waves B-D): **347 tests pasando, 7 skipped**
(`.venv/Scripts/python -m pytest -q`, ~17s) — 158 en `tests/unit/` y 189
en `tests/integration/`. Los 7 skips son `SKIPPED_EXPECTED`: Supabase
contra una base real, que no existe en este entorno.

Además, fuera de `pytest`: **107 tests de frontend** (`npx vitest run`) y
**27 E2E de Playwright contra el stack real** (PWA + FastAPI + SQLite,
sin mocks) — ver `frontend/e2e/README.md`.

Este número cambia con cada tarea que agregue código — no lo tomes como
vigente sin volver a correr `pytest`; es una fotografía, no una promesa.
El inventario por archivo de la sección 1 corresponde al cierre de Fase
4A y ya no está completo; regenéralo con `pytest --collect-only` antes de
citarlo.

**Unit test coverage ≠ product validation.** Los tests confirman que
el Processing Core, el Domain, la capa Excel, el CLI y la API se
comportan como sus propios autores esperaban, con datos sintéticos
(`sample_sourcing_TEST_DATA.xlsx`, explícitamente marcado TEST DATA) y
bajo las condiciones que el propio suite decidió ejercitar. **No**
confirman: que el modelo de negocio (reglas de decisión, severidad de
riesgo, thresholds) sea correcto para el negocio real (ver
`DECISION_ENGINE.md` §7, ADR-010); que el sistema funcione con archivos
Excel reales de proveedores (fuera de la fixture); nada sobre la
interfaz gráfica (el frontend PWA existe y tiene su propia cobertura de
vitest/Playwright, que `pytest` no ejecuta; el `.exe` sigue descartado
por ADR-014); que `SupabaseExecutionRunStore` funcione
contra una base de datos real (solo 2 tests estructurales, sin instancia
disponible — ver `docs/architecture/SUPABASE.md` §1); ni que el sistema
sea seguro en producción (ver `SECURITY.md`).

## 1. Inventario real (por archivo, verificado por `pytest --collect-only`)

### `tests/unit/` — Processing Core y Domain en aislamiento, sin I/O (138 tests)

| Archivo | Tests | Qué cubre |
|---|---|---|
| `test_provenance.py` | 16 | `FieldValue`/`Provenance` invariantes, `combine_verification_status`, constructores `.verified/.inferred/.not_found/.invalid` |
| `test_product.py` | 8 | `Identification`, `ProductInfo`, `Dimensions` (normalización de unidad obligatoria), `Price` (invariante `selling_price_used`/`selling_price_source`) |
| `test_costs.py` | 6 | `CostInputs`/`FeeInputs`, no-negatividad, `total_landed_cost` |
| `test_risk.py` | 6 | `RiskFlag` invariantes (ABSENT⇒NONE, UNKNOWN⇒NOT_FOUND/INVALID), `RiskProfile.highest_severity`/`has_unknown_risk` |
| `test_identifiers.py` | 19 | `is_valid_asin/upc/ean/gtin`, checksum GS1 contra códigos de referencia publicados |
| `test_units.py` | 9 | Conversión peso/longitud a unidad canónica, `UnsupportedUnitError` |
| `test_profitability.py` | 14 | Fórmulas de `profitability.py` contra valores calculados a mano; propagación NOT_FOUND si `selling_price` no es usable |
| `test_decision_engine.py` | 12 | Precedencia PASS→REVIEW→BUY, cada regla por defecto individualmente |
| `test_decision_score.py` | 6 | `ScoreWeights` suma 1, `NOT_FOUND` si falta un componente, combinación de verification_status |
| `test_data_quality.py` | 15 | Cada `validate_*` de `processing/data_quality.py`, incluida `validate_financial_consistency` (detecta drift) |
| `test_execution_run.py` | 11 | Invariantes de `ExecutionRun`, `hash_file()` |
| `test_sourcing_record.py` | 7 | Composición/inmutabilidad (helpers `.with_*()`), invariante `record_ref` no vacío |
| `test_pipeline.py` | 7 | `process_record`/`process_batch` orquestando Data Quality → Profitability → Decision con los motores reales (no mocks) |
| `test_supabase_execution_run_store.py` | 2 | **Solo estructural** (ADR-017): importa, construye sin conectar, expone las firmas correctas de `ExecutionRunStore`. No verifica persistencia real — no hay base de datos disponible en este entorno |

### `tests/integration/` — Excel real y pipeline completo, sin mocks del Core (71 tests)

| Archivo | Tests | Qué cubre |
|---|---|---|
| `test_excel_importer.py` | 20 | Import de la fixture real: columna requerida ausente (`FATAL`), columna desconocida/duplicada (`WARNING`), ASIN/UPC/número/booleano inválido (`RECORD_ERROR`+`INVALID`), fila sin `marketplace` (fila omitida sin abortar el batch), normalización de headers; 3 nuevos (2026-08-17, ADR-015): HAZMAT/BULKY siguen HIGH/MEDIUM vía `_build_risk_flag()`, y un `RiskType` no mapeado (`FRAGILE`) levanta `KeyError` en vez de `Severity.MEDIUM` |
| `test_excel_exporter.py` | 5 | Round-trip de columnas de provenance (`<campo>`/`<campo>_status` separadas, nunca colapsadas); incluye `max_cog_target_profit`/`max_cog_target_roi` (agregado 2026-08-17) |
| `test_pipeline_end_to_end.py` | 6 | Excel de entrada → `run_pipeline` → resultado, con mezcla real de VERIFIED/NOT_FOUND/INVALID en la misma corrida |
| `test_reproducibility.py` | 2 | Mismo archivo + mismos parámetros ⇒ mismo `ExecutionRun`/resultado (ver `EXECUTION_MODEL.md` §1) |
| `test_execution_run_store.py` | 12 | Persistencia SQLite de `ExecutionRun` (ADR-013): schema init, round-trip guardar→leer, `finished_at` NULL/tz-aware, todos los `ExecutionStatus`, contadores, `execution_id` duplicado (`IntegrityError`, no sobrescribe), `execution_id` inexistente (`None`), persistencia real entre instancias de store distintas (simula fin de conexión/proceso) |
| `test_cli.py` | 7 | `interfaces/cli/main.py` (nuevo 2026-08-17): corrida exitosa escribe Excel + resumen; `execution_id` autogenerado es un UUID4 válido; `--persist-db` guarda el `ExecutionRun` solo cuando se pasa el flag (nunca por defecto); archivo de entrada inexistente ⇒ código 2 sin traceback; threshold requerido faltante ⇒ `SystemExit` no-cero (`argparse`); import fatal ⇒ código 1, no escribe salida |
| `test_api.py` | 19 | `interfaces/api/` (nuevo 2026-08-17, Fase 4A, ADR-016): `TestClient`/`httpx`, sin servidor real; camino feliz contra el Core real (fixture real, sin mocks); provenance preservada en JSON (`value`+`status`, ADR-003/ADR-004); thresholds/fees obligatorios; Excel inválido/import fatal ⇒ 422, nunca 500; `ExecutionRun` persistido solo si `persist=true`; descarga real vía `export_excel()`; `execution_id` desconocido ⇒ 404; nunca expone traceback ni rutas de servidor |

### `tests/fixtures/`

`sample_sourcing_TEST_DATA.xlsx` (generado por `generate_sample.py`) — 5
filas sintéticas cubriendo: caso válido, dato faltante (ASIN/precio en
blanco), dato inválido (ASIN mal formado, UPC con checksum incorrecto,
peso no numérico, COG faltante), riesgo presente (HazMat=TRUE), fila
malformada (marketplace en blanco). Más una columna desconocida
(`Notes`) y headers con formato variado, para ejercitar la normalización.
Detalle fila por fila en `EXCEL_PROCESSING.md` §7.

## 2. Regla dura de la suite (heredada de `CLAUDE.md` §17 / `tests/README.md`)

Ningún test oculta un error para "pasar" — un test que ejercita manejo de
errores debe afirmar que el error **se reportó correctamente**
(`ProcessingIssue` con el `level`/`code` esperado), no que desapareció o
que el batch se detuvo silenciosamente. Verificado por inspección: los
tests de `test_excel_importer.py` que cubren filas inválidas assertan
sobre el contenido de `issues`, no solo sobre "no crasheó".

## 3. Categorías presentes vs. planificadas

| Categoría | Estado | Notas |
|---|---|---|
| Unit — Domain (invariantes estructurales) | **IMPLEMENTED** | Ver tabla §1 |
| Unit — Processing Core (fórmulas, reglas, validación) | **IMPLEMENTED** | Ver tabla §1 |
| Unit — Provenance / VerificationStatus | **IMPLEMENTED** | `test_provenance.py` |
| Integration — Excel import/export | **IMPLEMENTED** | Ver tabla §1 |
| Integration — Pipeline end-to-end | **IMPLEMENTED** | `test_pipeline_end_to_end.py` |
| Integration — Reproducibilidad | **IMPLEMENTED** (para el caso sin fuentes externas) | `test_reproducibility.py`; no cubre (todavía no aplica) el caso con fuentes externas variables |
| Decision Score — tests de fórmula por subscore | **NOT IMPLEMENTED** | El score en sí está probado (`test_decision_score.py`), pero no hay fórmulas de subscore aprobadas que probar todavía (ver `DECISION_ENGINE.md` §7) |
| Enrichment adapters (fuentes externas) | **NOT IMPLEMENTED** | No existe código que probar — `infrastructure/enrichment/` está vacío |
| CLI | **IMPLEMENTED** (2026-08-17) | `test_cli.py` (7 tests), sin subprocess (invoca `main()` directamente con listas de argv) |
| API (backend) | **IMPLEMENTED** (2026-08-17, Fase 4A) | `test_api.py` (19 tests), `TestClient`/`httpx`, sin servidor real |
| Frontend PWA / desktop | **NOT IMPLEMENTED** | Frontend: framework elegido (React+Vite) pero sin Node.js/npm en este entorno. Desktop (`.exe`): descartado como interfaz principal, ADR-014 |
| AI Analyst — contract tests ("qué NO puede hacer") | **PLANNED** | Ver `PHASE_GATES.md` §Fase 7: se exige suite de contract tests al 100% antes de declarar esa fase completa, cuando exista código |
| E2E (interfaz real, navegador o `.exe`) | **NOT IMPLEMENTED** | Depende de Fase 4 (bloqueada, ver `TECHNOLOGY_DECISIONS.md`) |
| Persistencia local de `ExecutionRun` (SQLite, single-user) | **IMPLEMENTED** | `test_execution_run_store.py` (ADR-013, `Aceptada`), 12 tests de integración reales |
| Persistencia de producción (Supabase/PostgreSQL) | **IMPLEMENTED, NO VERIFICADA** (2026-08-17) | `test_supabase_execution_run_store.py` (ADR-017) — solo 2 tests estructurales; sin base de datos real disponible en este entorno |
| Persistencia compartida/remota + aislamiento de datos multiusuario | **NOT IMPLEMENTED** | Depende de Fase 8/Fase 9 (autenticación); RLS habilitado sin policies en la migración de ADR-017, ver `SUPABASE.md` §4 |
| Autenticación / autorización | **NOT IMPLEMENTED** | Depende de Fase 9 (bloqueada) |

## 4. Cómo ejecutar

```bash
.venv/Scripts/python -m pytest -q
```

`pyproject.toml` fija `pythonpath = ["src"]` y `testpaths = ["tests"]`,
así que los tests importan `juval.*` directamente desde `src/` sin
necesidad de instalar el paquete.

## 5. Relacionado

`tests/README.md` (resumen operativo corto), `PHASE_GATES.md` (criterio
universal #2 "Tests pasan", y criterios específicos de test por fase),
`PROJECT_PLAN.md` (conteo de tests por fase de cierre).
