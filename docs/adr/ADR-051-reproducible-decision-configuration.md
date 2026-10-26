# ADR-051 — Configuración de decisión reproducible por ExecutionRun

- Estado: **Propuesta** (2026-10-26). No implementada. Ningún cambio de código,
  esquema ni contrato hasta su aprobación explícita.
- Autoridad solicitada: aprobación de P1–P8 y de las decisiones D1–D7 (§6).
- Relacionados: ADR-006, ADR-007, ADR-012, ADR-013, ADR-019, ADR-020, ADR-040,
  ADR-043, ADR-044, ADR-045, ADR-047, ADR-050. GOLDEN §14, ítems 20 y 21.

## 1. Contexto — inventario medido (HEAD `78f924f`)

`ExecutionRun` guarda identidad, hash del input, `application_version` y
contadores. **No guarda ninguno de los parámetros que produjeron BUY/REVIEW/PASS**
(gap ya declarado en CLAUDE.md §15 y ADR-013). Dos runs del mismo archivo con
umbrales distintos son indistinguibles salvo por sus decisiones.

| Parámetro | Dónde vive | ¿Lo fija el usuario? | Default | ¿Se guarda? |
|---|---|---|---|---|
| `target_profit`, `target_roi` | `Thresholds` (ADR-007) | sí (API/CLI, obligatorio) | ninguno | **no** (solo aparecen dentro del texto de algunas razones) |
| `minimum_estimated_monthly_sales` | `Thresholds` | sí | API: obligatorio; **CLI: 0** | **no** |
| `maximum_risk_severity` | `Thresholds` | sí (obligatorio) | ninguno | **no** |
| `allow_restricted`, `allow_approval_required`, `allow_unknown_risk` | `Thresholds` | sí | `False` (modelo API, flags CLI) | **no** |
| `referral_fee`, `referral_fee_rate` | `FeeInputs` | sí (obligatorio) | ninguno | **no** (solo `total_fees` resultante por registro) |
| `fulfillment_fee`, `other_selling_fees` | `FeeInputs` | sí | `0` | **no** |
| Fees por registro del archivo | `record.fees` | vía archivo | — | usados **solo** si la petición no trae fees (`pipeline.py`); API y CLI siempre los traen |
| Reglas y precedencia | `DEFAULT_PASS_RULES` (4), `DEFAULT_REVIEW_RULES` (7), PASS > REVIEW > BUY | no | código | **no**; sin identificador de versión |
| Severidad por tipo de riesgo | `importer.DEFAULT_RISK_SEVERITY` HAZMAT→HIGH, BULKY→MEDIUM (ADR-044 aprobado) | no | código | parcial: la severidad resultante se guarda por registro como INFERRED (ADR-020), la tabla no |
| `DataQualityConfig` (peso 500 lb, dimensión 200 in, antigüedad 30 d) | `processing/data_quality.py` | no | código | **no**; afecta issues, no decisiones |
| Opciones ADR-047 (`native_financial_evidence`, objetivos) | petición | sí | desactivado | dentro de cada documento (`supplied_inputs`), no a nivel de run |

Hechos adicionales que condicionan el diseño:

- **No existe identificador de versión de la política de decisión.** El único
  precedente de identidad de implementación es ADR-047 (`expressions_digest`,
  `dependency_matrix_digest`, `code_revision`).
- **El input no se conserva**: la API borra el archivo subido tras procesarlo
  (`main.py`, "never keep the uploaded input"). Re-evaluar exige volver a subirlo.
- **Los snapshots de registro no bastan para re-ejecutar el motor**: no guardan
  el perfil de riesgo completo, la demanda ni el desglose de costes. Explicar una
  decisión y reproducirla son capacidades distintas (ADR-045 §10).
- **Hallazgo (fuera de alcance, requiere decisión de negocio):** el importer no
  mapea ninguna columna a `estimated_monthly_sales`, así que
  `rule_review_demand_unknown_or_below_minimum` dispara siempre y **ningún registro
  importado puede ser BUY**. Medido: el mejor registro del fixture (profit 8.99,
  ROI 150 %) es REVIEW solo por `DEMAND_UNKNOWN`. Este ADR no lo cambia; lo
  registra en el snapshot (la regla activa queda identificada).

## 2. Decisión propuesta

### P1 — Snapshot inmutable de la configuración efectiva por run

Cada `ExecutionRun` creado después de este ADR guarda **un** documento versionado
`juval.decision-configuration` v1 con:

- `thresholds`: los 7 campos tal como se usaron (Decimal como texto exacto).
- `fees`: los 4 campos de la petición y `fees_source` = `REQUEST` | `RECORD_FILE`.
- `decision_policy`: identidad y versión (P2), reglas PASS y REVIEW en orden y la
  precedencia.
- `risk_severity_policy`: la tabla `DEFAULT_RISK_SEVERITY` vigente y su autoridad
  (`ADR-044`).
- `quality_config`: valores de `DataQualityConfig` (D3).
- `financial_evidence_options`: opt-in ADR-047 y objetivos, o `null`.
- `implementation`: `application_version`, `code_revision` (o `null`) y el digest
  de la política (P2).
- `captured_at` (tz-aware) e `interface` (`juval-api` | `juval-cli`).

El documento se construye a partir de los mismos objetos `Thresholds`/`FeeInputs`
que recibe el pipeline, nunca reconstruidos después.

### P2 — Identidad versionada de la política de decisión

Constante explícita `DECISION_POLICY = ("juval.decision-rules", 1)` junto a las
reglas. La versión cambia cuando cambia el conjunto, el orden o el significado de
una regla, o la precedencia. Un test fija el digest (SHA-256 de identidad,
versión, nombres ordenados y precedencia): si se cambia la lista sin subir la
versión, falla. **Límite declarado:** el digest no detecta un cambio dentro del
cuerpo de una regla; para eso se registra `code_revision` cuando exista y la
revisión de código sigue siendo necesaria. No hay alias mutable "actual".

### P3 — Decisión histórica separada de simulación y de re-ejecución

- **Histórica:** la decisión guardada no se modifica nunca (P5).
- **Simulación:** procesar con `persist=false` ya existe; su respuesta se etiqueta
  `SIMULATION` y no crea ni toca ningún run.
- **Re-ejecución con otros umbrales (ítem 21):** es un **run nuevo**, con su propio
  snapshot, a partir de una nueva subida del archivo. Opcionalmente lleva
  `derived_from_execution_id`, aceptado solo si el `input_hash` coincide con el run
  original (prueba de mismo input sin conservar archivos). El original no cambia.

### P4 — Runs históricos sin snapshot

Sin snapshot, la configuración es `NOT_RECORDED`. **Nunca** se reconstruye con
defaults, con la política vigente ni extrayendo valores del texto de las razones.
Se muestra la decisión guardada con su límite explícito.

### P5 — Sin modificación retroactiva

Tabla de solo inserción: no hay método de actualización ni de borrado en el
puerto del store; una segunda escritura para el mismo `execution_id` falla por la
clave primaria y no sobrescribe. No hay backfill de runs anteriores.

### P6 — Reproducibilidad y determinismo

Una decisión es **reproducible** solo si coinciden: bytes del input
(`input_hash`), snapshot, versión de política y `application_version` o
`code_revision`. Entonces el resultado debe ser idéntico en decisión y razones;
`evaluated_at` se excluye de la comparación. Si falta cualquiera de esos
elementos, se puede **explicar** pero no se afirma que se pueda **reproducir**
(ADR-045 §10). Los Decimal se guardan como texto exacto, sin redondeo.

### P7 — Provenance de parámetros y separación de estados

Los parámetros son **configuración**, no datos de producto: no reciben
VERIFIED/INFERRED/NOT_FOUND/INVALID. Cada valor registra su `origin`:

- `REQUEST`: enviado explícitamente (`model_fields_set` en la API);
- `MODEL_DEFAULT`: no enviado, tomó el default del modelo (p. ej. `allow_*`);
- `CLI_ARGUMENT` / `CLI_DEFAULT`: lo mismo en la CLI;
- `CODE_POLICY`: tabla o regla del código (reglas, severidad, calidad).

Los estados de los registros (p. ej. severidad INFERRED, ADR-020) no cambian por
existir un snapshot. INFERRED nunca se promueve.

### P8 — Persistencia y contrato

- **Persistencia:** tabla aditiva `execution_run_decision_configurations`
  (`execution_id` PK/FK, `format`, `format_version`, `payload` TEXT canónico),
  igual que las tablas ADR-047. Se escribe en la misma transacción que el run y,
  en batches, dentro de la transacción única de ADR-050. Hay migración SQLite en
  el propio store y un archivo de migración PostgreSQL **no aplicado** a ningún
  Supabase real.
- **API:** `GET /api/v1/runs/{id}` añade `decision_configuration`:
  `{status: "RECORDED", format, version, payload}` o `{status: "NOT_RECORDED"}`.
  `GET /runs` no cambia (tamaño). `POST /runs` y `/batches` mantienen su cuerpo;
  aceptan `derived_from_execution_id` opcional (P3).
- **UI** (frontend-next): bandas de umbrales de solo lectura en Product Detail,
  Run Detail y Catálogo (ítem 20); con `NOT_RECORDED`, un aviso y ninguna banda.
  "Cambiar umbrales" lleva a Import con los valores prellenados como **punto de
  partida editable**, nunca como default comercial (ítem 21).

## 3. Lo que este ADR no decide

- Ningún valor comercial de umbrales ni ningún default nuevo (ADR-007 sigue igual).
- La fuente de demanda ni el cambio de la regla de demanda (hallazgo §1).
- Decision Score (ADR-045) ni sus pesos.
- Conservar archivos de input (sigue prohibido).
- Ranking, duplicado ni borrado de runs (ítems 22–24).

## 4. Compatibilidad

- **ADR-007:** refuerza que no hay defaults comerciales; el snapshot registra los
  defaults de modelo existentes como `MODEL_DEFAULT` y no crea ninguno.
- **ADR-013 / ADR-019:** cierra el gap declarado sin alterar `execution_runs` ni
  `execution_run_records`.
- **ADR-020 / ADR-043 / ADR-044:** la severidad sigue INFERRED; RISK_AT_MAXIMUM no
  cambia; la tabla aprobada se registra.
- **ADR-045:** aplica sus reglas de snapshot, versión e inmutabilidad (§6–§10) a
  BUY/REVIEW/PASS sin conectar el score.
- **ADR-047:** mismo patrón de almacenamiento y de identidad de implementación;
  no toca sus documentos.
- **ADR-050:** la configuración entra en la transacción única del batch. La
  idempotencia D5 sigue diferida; un reintento tras una respuesta perdida crea
  otro run con su propio snapshot.
- **ADR-040:** sin efecto directo previsto en las mediciones; no se cambia la
  metodología.

## 5. Plan de implementación (solo tras aprobación)

1. `domain/decision_configuration.py`: dataclass inmutable, `origin` por valor,
   invariantes en `__post_init__`.
2. `processing/decision_engine.py`: constante `DECISION_POLICY` y función pura que
   calcula el digest.
3. `application/decision_configuration.py`: construcción a partir de
   `Thresholds`/`FeeInputs`/opciones y serialización canónica v1 con lectura que
   valida formato, versión e identidad.
4. `application/run_pipeline.py`: devuelve el snapshot junto al run; sin cambiar
   decisiones.
5. Stores: `sqlite_execution_run_store.py` (tabla nueva y escritura en la misma
   transacción, incluido `save_batch_with_runs`) y
   `supabase_execution_run_store.py`; nueva migración
   `supabase/migrations/2026MMDD000007_execution_run_decision_configurations.sql`
   con su `.down.sql`, sin aplicar.
6. API: `models.py` (`DecisionConfigurationOut`), `service.py` (origen vía
   `model_fields_set`), `main.py` (`GET /runs/{id}` y `derived_from_execution_id`
   con validación de `input_hash`); `API_CONTRACT.md`.
7. CLI: registrar `CLI_DEFAULT` para `--min-monthly-sales`.
8. frontend-next: tipos, bandas de solo lectura, estado `NOT_RECORDED` y "Cambiar
   umbrales" hacia Import.
9. Documentación: `DECISION_ENGINE.md`, `PROJECT_STATUS`, matriz GOLDEN.

## 6. Decisiones que requieren aprobación

| ID | Decisión | Propuesta |
|---|---|---|
| D1 | Aprobar P1–P8 | sí |
| D2 | Formato de identidad de la política | `juval.decision-rules` + entero + digest de nombres ordenados |
| D3 | ¿Incluir `DataQualityConfig` aunque no afecta decisiones? | sí, para reproducir también los issues |
| D4 | ¿API en `GET /runs/{id}` o endpoint propio? | campo en `GET /runs/{id}` |
| D5 | Re-ejecución: ¿nueva subida + `input_hash` (sin conservar archivos)? | sí |
| D6 | Etiquetar `SIMULATION` las respuestas `persist=false` | sí, aditivo |
| D7 | Hallazgo de demanda (BUY inalcanzable): decisión de negocio aparte | fuera de este ADR |

## 7. Tests previstos

- **Run nuevo:** el snapshot existe; los valores son exactamente los enviados,
  como texto exacto; el `origin` distingue enviado y default; contiene la política
  y su digest.
- **Run histórico:** `NOT_RECORDED` en API y UI; ningún valor inferido ni
  extraído del texto de las razones.
- **Cambio posterior de configuración:** un run nuevo con otros umbrales tiene su
  propio snapshot y el anterior no cambia (lectura byte a byte).
- **Reproducción:** mismo input, snapshot y versión de política producen la misma
  decisión y razones (sin `evaluated_at`) en SQLite y en PostgreSQL desechable.
- **Inmutabilidad:** una segunda escritura falla; no hay ruta de actualización; el
  batch guarda todo o nada con su configuración (ADR-050).
- **Política:** el digest queda fijado; cambiar la lista de reglas sin subir la
  versión hace fallar el test.
- **`derived_from_execution_id`:** rechazado con 422 si el `input_hash` difiere o
  el run no existe.
- **Estados:** los estados VERIFIED/INFERRED/NOT_FOUND de los registros no cambian
  con el snapshot; la severidad sigue INFERRED; los parámetros no llevan estados
  de verificación.
- **UI:** bandas de solo lectura con origen visible; `NOT_RECORDED` sin bandas;
  "Cambiar umbrales" no modifica nada sin una subida nueva.

## 8. Riesgos

- El digest no detecta cambios internos de una regla (P2, límite declarado).
- Las migraciones aditivas no están aplicadas a ningún Supabase real (operador).
- Los runs anteriores quedan `NOT_RECORDED` para siempre; es deliberado.
- Mostrar umbrales podría leerse como recomendación comercial; la UI los rotula
  como "usados por este run", no como valores sugeridos.
- El hallazgo de demanda hace que las bandas muestren umbrales que, hoy, nunca
  llevan a BUY; debe decidirse por separado.
