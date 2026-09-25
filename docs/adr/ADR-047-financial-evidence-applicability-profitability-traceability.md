# ADR-047 — Evidencia financiera, aplicabilidad y trazabilidad de rentabilidad

## 1. Estado y autoridad

- Estado: Aceptada.
- Fecha: 2026-09-22.
- Autoridad: aprobación explícita de Daniel de las decisiones del Financial
  Evidence Contract y de la dirección aditiva A+ el 2026-09-22.
- Estado de implementación: PARTIALLY IMPLEMENTED. El paso 1 de §22
  (contratos de dominio aditivos) existe en `src/juval/domain/financial_evidence.py`,
  probado en `tests/unit/test_financial_evidence.py`. El paso 2 de §22 está
  IMPLEMENTED: la frontera de dominio evalúa operandos legacy como gaps sin
  promoción (`assess_legacy_financial_operands`) y
  `application/legacy_financial_projection.py` proyecta read-only hacia ella las
  dos fuentes legacy existentes, `CostInputs`/`FeeInputs` en memoria y los record
  snapshots persistidos. Ningún consumidor (API, UI, exportación) la usa todavía;
  exponerla es parte del paso 7. El paso 3 está IMPLEMENTED en la frontera
  del importer: columnas nativas opcionales `fin_*` producen, por registro, un
  `NativeFinancialCapture` en `ImportResult.financial_captures` cuyo
  `bind(execution_id)` devuelve el `FinancialEvidenceSet` (contrato en
  `docs/architecture/EXCEL_PROCESSING.md` §9). Avance fuera de la numeración de
  §22 (no completa el paso 4): `run_pipeline_with_financial_evidence` transporta
  esa evidencia, ya vinculada al `execution_id` real y al `record_ref` de cada
  registro, junto al resultado intacto de `run_pipeline`. El paso 4 es PARTIAL: `domain/financial_fees.py`
  construye la vista acreditada de fees por registro desde la evidencia nativa,
  sin derivación referral fee↔rate, porque §15 no aprueba ningún método; la
  construcción desde tarifas o fuentes de fees sigue pendiente (H-02). El paso 5 es PARTIAL:
  `domain/financial_dependencies.py` resuelve por resultado las dependencias de
  evidencia de §16 y `application/financial_calculation.py` evalúa las
  precondiciones matemáticas y calcula los seis resultados con las expresiones
  existentes. Falta un único criterio literal: la propagación transitiva de estados
  de operandos derivados (§16, §29.11), que hoy no pueden existir porque §15 no
  aprueba ningún método de derivación. El paso 6 (round-trip de persistencia)
  es PARTIAL. El formato `juval.adr047.financial-record` v1
  (`application/financial_serialization.py`) se persiste y recupera en SQLite
  (`application/financial_persistence.py` y la tabla
  `execution_run_financial_records`), en la misma transacción que el run y sus
  snapshots. La CLI local lo persiste con el opt-in `--native-financial-evidence`.
  Falta el backend Supabase/PostgreSQL, que la API no usa todavía. Los pasos 7-9 siguen
  PENDING: no hay cálculo, proyección a CostInputs/FeeInputs, snapshot, persistencia, API, consumo por Decision
  Score ni activación de pipeline.

### 1.1 Contratos implementados y pendientes

Implementado como contrato de dominio, sin acreditar dato alguno por sí mismo:

| Contrato | Responsabilidad declarada |
|---|---|
| `FinancialTerm` / `TermNature` | Los 16 términos de §9 con naturaleza explícita: importe por unidad vendible, tarifa monetaria por lb y ratio adimensional |
| `Applicability` | Aplicabilidad como evidencia separada del valor (§12); exclusión acreditada distinta de aplicabilidad no resuelta |
| `EffectiveContext` | Tiempo efectivo separado de `retrieved_at` y base declarada del importe (§8, §10) |
| `FinancialDependency` | Vínculo resoluble a la evidencia realmente utilizada (§15, §18) |
| `FinancialTermEvidence` | Une término, aplicabilidad, contexto, importe opcional, método de asignación y dependencias |
| `FinancialScenario` | Identidad, versión, moneda única, unidad vendible, identidad de política y universo de términos requeridos (§8, §11) |
| `FinancialEvidenceSet` | Vinculación escenario/ejecución/registro y resolución inequívoca de moneda y dependencias |
| `LegacyGap` / `LegacyTermGap` / `LegacyFinancialCompatibility` / `assess_legacy_financial_operands` | Evaluación determinista de compatibilidad legacy (§20): informa qué le falta a cada ubicación legacy para satisfacer el contrato; nunca produce evidencia |
| `LEGACY_COST_TERMS` / `LEGACY_FEE_TERMS` / `legacy_financial_operands` (application) | Correspondencia explícita campo legacy → término y proyección read-only de los valores tal como están almacenados; declara el slot, no acredita el valor |
| `LEGACY_SNAPSHOT_TERMS` / `legacy_snapshot_financial_operands` (application) | Proyección read-only de un record snapshot persistido: solo los slots que el snapshot conserva; el resto queda en ausencia estructural |
| `FinancialResult` / `DEPENDENCY_MATRIX` / `resolve_financial_dependencies` / `ResultResolution` (domain) | Resolución pura por resultado de §16: dependencias exigidas, operandos utilizables sin copiar, exclusiones, bloqueos con motivo (`ResolutionBlocker`, no un VerificationStatus) y estado de eslabón más débil solo con dependencias resueltas |
| `calculate_financial_results` / `FinancialCalculation` (application) | Cálculo acreditado por resultado: precondiciones matemáticas evaluadas, valor `CALCULATED` VERIFIED/INFERRED o NOT_FOUND con diagnóstico, operandos y evidencia originales enlazados, exactitud Decimal informada |
| `FinancialRecordDocument` / `serialize_financial_record` / `deserialize_financial_record` (application) | Formato `juval.adr047.financial-record` v1: serialización pura, JSON-compatible, determinista y reversible de evidencia, precio declarado, resolución y cálculos; sin I/O ni persistencia |
| `save_run_with_financial_records` / `load_financial_record` (application) + `execution_run_financial_records` (SQLite) | Persistencia aditiva del payload v1 por `(execution_id, record_ref)`, atómica con run y snapshots; lectura que distingue ausencia, payload corrupto o versión desconocida, e identidad incoherente |
| `FinancialRecordDocumentV2` / `serialize_financial_record_v2` / `deserialize_financial_record_v2` / `read_financial_record` / `assess_reproducibility` (application) | Formato v2 puro: núcleo v1 idéntico más inputs suministrados, problemas de captura e identidad de implementación; lectura v1/v2 discriminada por versión; evaluación separada de las garantías A/B/C de §19; sin I/O ni consumidores |
| `FeeEvidenceState` / `accredited_fee_evidence` (domain) | Vista acreditada por registro de los cuatro términos de fee: DECLARED/OBSERVED/INFERRED/DERIVED frente a ausente, NOT_FOUND, INVALID, excluido o aplicabilidad no resuelta; sin derivación ni defaults |
| `DeclaredSellingPrice` (domain) | Precio declarado por registro con moneda propia en `amount.unit` y `EffectiveContext`; no es `PriceObservation` |
| `FINANCIAL_EVIDENCE_COLUMN_SPECS` / `NativeFinancialCapture` / `capture_native_financial_evidence` (infrastructure/excel) | Captura nativa (§22 paso 3): lo que una fila declara explícitamente se convierte en `FinancialScenario`/`FinancialTermEvidence`; lo no representable se omite con motivo, nunca se completa con defaults |

Invariantes verificadas en tests: ausencia estructural (`amount=None`) distinta de
NOT_FOUND, INVALID, cero acreditado y exclusión; exclusión sin operando monetario;
exclusión INFERRED que conserva su estado; `referral_fee_rate` como ratio con unidad
`ratio` y límites [0, 1) coherentes con `FeeInputs` y con el denominador de
break-even, quedando un valor fuera de rango representable como INVALID; rechazo de
Decimal no finito y de `bool` como número; moneda incompatible con el escenario
rechazada sin normalización implícita; términos asignados por unidad que exigen
método de asignación explícito.

Frontera legacy (§5, §13, §20, §22 paso 2): la evaluación recorre los 16 términos
en orden fijo, solo lee su entrada y devuelve un informe de gaps sin valores,
`FieldValue`, `FinancialTermEvidence`, `FinancialEvidenceSet` ni `PriceObservation`.
Un `None` o término ausente es `STRUCTURALLY_ABSENT` (no NOT_FOUND, cero ni
exclusión); un Decimal desnudo carece de provenance y un cero desnudo es
indistinguible del default de `CostInputs`/`FeeInputs`; todo operando legacy,
incluido un `FieldValue` VERIFIED de proveedor, conserva aplicabilidad no resuelta,
contexto efectivo no declarado y, si es monetario, moneda no vinculada al escenario
(nunca para `referral_fee_rate`). La asignación se exige solo para los términos
asignados de §9, nunca para COG. `LegacyGap` es un diagnóstico, no un
VerificationStatus. La correspondencia campo legacy → término se prueba con
fixtures sintéticos.

Proyección legacy (ruta LEGACY, no la de nuevas importaciones): la correspondencia
de los 12 campos de `CostInputs` y los 4 de `FeeInputs` con los 16 términos vive
en `application/legacy_financial_projection.py`, cubre cada campo y cada término
una sola vez y no la usa el dominio. Los valores pasan tal cual, incluidos los
`Decimal("0")` por default; un `CostInputs`/`FeeInputs` ausente deja sus términos
en ausencia estructural, nunca en cero. Qué `FeeInputs` se evalúa lo decide el
llamador, porque el pipeline puede usar el argumento de batch en lugar de
`record.fees` (§5). El precio de venta no tiene término (§9) y no se proyecta ni
se convierte en `PriceObservation`. Probado con tipos legacy reales y con un
registro importado desde un CSV sintético; la evidencia financiera nativa de
nuevas importaciones (§22 paso 3 en adelante) es una ruta separada.

Snapshots persistidos (§5, §20): `record_to_snapshot` no tiene identificador de
versión y, desde que existe el formato, conserva de los 16 términos solo `cog` y
`shipping_per_unit`, como `str(Decimal)` o `null`; `total_fees`,
`seller_proceeds` y `total_cost` son resultados, no términos, y no se proyectan.
Los otros 14 términos quedan en ausencia estructural aunque el registro original
tuviera `CostInputs`/`FeeInputs`: no se reconstruyen desde defaults actuales, el
registro runtime ni reglas del importer. Parsear es sintaxis, no acreditación: el
Decimal resultante sigue siendo un operando legacy sin provenance, y un `"0"`
persistido conserva `ZERO_INDISTINGUISHABLE_FROM_DEFAULT`. El parseo es
`Decimal(str)` exacto (sin float) y exige que el string sea exactamente el que el
escritor produce: un valor no string, no parseable, no canónico, NaN o negativo, o
un snapshot sin alguna de las dos claves, se rechaza con error explícito en lugar
de leerse como cero, ausencia o NOT_FOUND. Probado con dicts de `record_to_snapshot`
y con una lectura desde `SqliteExecutionRunStore`, que produce el mismo
diagnóstico que el dict escrito. El store de Supabase devuelve el mismo formato de
snapshot, pero no se probó contra una base real.

Captura nativa (§22 paso 3, ruta NATIVA separada de la legacy): moneda,
aplicabilidad, `effective_at`, base y asignación se toman solo de columnas
declaradas; columna ausente es ausencia estructural, celda vacía NOT_FOUND,
valor no finito/negativo/fuera de rango INVALID con raw, y cero explícito un cero
declarado cuya aplicabilidad es una declaración aparte. Un importe sin moneda, con
moneda distinta del escenario, sin aplicabilidad declarable, sin contexto efectivo
o de origen `pack` sin asignación no se captura y su motivo queda en `problems`.
Provenance `SUPPLIER_FILE` por celda; VERIFIED es declaración del archivo, no
verificación de Amazon. Sin `PriceObservation`. Registros, issues, profitability y
decisiones legacy quedan idénticos (probado), y un archivo sin columnas `fin_*` no
produce capturas. Una celda vacía produce NOT_FOUND con fuente `SUPPLIER_FILE` y
evidencia de celda en blanco: la celda se leyó y no declaró nada; no es una
consulta a Amazon ni prueba de inexistencia del término.

Transporte por ejecución (sin paso propio en §22): `application/run_pipeline.py`
añade `run_pipeline_with_financial_evidence`, que comparte la ruta de ejecución de
`run_pipeline` (cuya firma y tupla no cambian) y devuelve por registro procesado
un `RecordFinancialEvidence` con `execution_id`, `record_ref`, la captura, sus
`problems` y el `FinancialEvidenceSet` vinculado cuando la fila declaró un
escenario completo. La identidad es `record_ref`, que incluye el número de fila:
una fila descartada no desplaza capturas y un ASIN/UPC duplicado es irrelevante;
un desajuste de cardinalidad u orden falla explícitamente. Los problemas de
captura no se convierten en issues legacy. No hay cálculo acreditado, fees
efectivos, snapshot reproducible, persistencia ni API: esto no satisface el paso 4
ni la reproducibilidad financiera de §19.

Resolución de dependencias (§16, §17; avance PARTIAL del paso 5; el paso 4 de §22
es la construcción acreditada de fees y sigue PENDING):
`resolve_financial_dependencies(evidence_set, selling_price=, weight=, target_profit=, target_roi=)`
es una función pura de dominio que aplica literalmente la matriz de §16 a cada
uno de los seis resultados existentes. P y los objetivos no son `FinancialTerm`
(§9, §10) y entran como `FieldValue` explícitos. Un término de la fórmula es
dependencia si el escenario lo requiere o el set lo representa; un requerido no
representado bloquea (§8), y uno ni requerido ni representado queda fuera del
universo declarado. Cada dependencia informa el `FieldValue` original como
operando, la aserción de aplicabilidad y si fue excluida, o bien un bloqueo:
ausencia estructural, aplicabilidad no resuelta, NOT_FOUND, INVALID, moneda no
declarada o incompatible, o unidad incompatible (peso distinto de `lb`, objetivo
ROI sin `ratio`). Nada se convierte a cero y nada se convierte de unidad o moneda.
Una exclusión acreditada no tiene operando, pero su aplicabilidad sigue siendo
dependencia, de modo que una exclusión INFERRED deja el resultado INFERRED.
`dependency_status` aplica `combine_verification_status` solo cuando todas las
precondiciones de evidencia se cumplen.

Límites documentados:
- Los `context_requirements` del escenario bloquean todos los resultados, porque
  no existe método aprobado para resolverlos (§28).
- Las precondiciones matemáticas (C > 0, P > 0, 1 + tr > 0) se listan, no se
  evalúan, porque exigen el cálculo.
- El precio legacy importado no declara moneda, así que profit, ROI, margin y
  max-COG quedan bloqueados por `CURRENCY_UNDECLARED` hasta que exista una
  declaración de moneda del precio (vínculo con ADR-046). Break-even no depende
  de P y sí puede resolverse.
- La profitability y las decisiones legacy no cambian, y nada se persiste.

Fees acreditados (§12, §15, avance PARTIAL del paso 4):
- `accredited_fee_evidence(evidence_set)` clasifica, para REFERRAL_FEE,
  FULFILLMENT_FEE, OTHER_SELLING_FEES y REFERRAL_FEE_RATE, la evidencia del propio
  registro. Posibles clasificaciones: DECLARED (VERIFIED de `SUPPLIER_FILE`/`USER_INPUT`),
  OBSERVED (VERIFIED de `OFFICIAL_API`/`AUTHORIZED_EXTERNAL_SOURCE`; hoy no existe
  ninguna fuente así, H-02), INFERRED, DERIVED (VERIFIED `CALCULATED`), ausencia
  estructural, aplicabilidad no resuelta, exclusión (sin importe), importe ausente,
  NOT_FOUND o INVALID.
- Un VERIFIED de `DATABASE` o de otro origen que no acredita quién lo declaró
  se rechaza en lugar de etiquetarse.
- Referral fee y referral rate siguen independientes: §15 no aprueba ningún método
  de derivación, así que no existe ninguno.
- Nuevas invariantes de dominio:
  - un importe utilizable `CALCULATED` exige `depends_on` (§15, §18);
  - ningún importe, precio declarado ni aplicabilidad puede proceder de
    `AI_ANALYSIS` (ADR-006/ADR-008).
- Un `FeeInputs` de batch nunca se usa como evidencia de fee.

Pendiente del paso 4:
- construcción desde tarifas o fuentes de fees autorizadas (H-02);
- cualquier método aprobado de derivación (§15).
- Mientras se aprueba un método de derivación, el resolvedor tampoco expande
  dependencias transitivas de fees derivados.

Cálculo acreditado (§7, §16, §17; paso 5):
`calculate_financial_results(resolution, calculated_at=, requested=)` vive en
`application/` porque reutiliza sin cambios las funciones puras Decimal de
`processing/profitability.py`: `compute_profit`, `compute_roi`, `compute_margin`,
`compute_break_even_price` y `compute_max_cog_for_target_*`. Las expresiones son,
por tanto, exactamente las existentes, y un test lo comprueba contra el motor
legacy con operandos equivalentes.

Reglas:
- Neutros: un término de la fórmula aporta su operando, o 0 solo si su exclusión
  está resuelta (§7). `SHIPPING_PER_POUND` aporta tasa × peso en lb.
- Tensión §8/§7, resuelta de forma conservadora: un término que el escenario no
  requiere ni representa no es dependencia para la resolución, pero tampoco tiene
  un neutro acreditado. Por eso el cálculo se bloquea con
  `FORMULA_TERM_UNDECLARED` en lugar de sumarlo como cero (§13). En la práctica,
  un escenario calculable declara cada término de la fórmula, como operando o
  como exclusión.
- Precondiciones: las mismas cadenas que el resolvedor (C = COG + C0 > 0, P > 0,
  1 - r > 0, 1 + tr > 0), evaluadas sin tolerancias. Si alguna falla, el resultado
  es un NOT_FOUND `CALCULATED` con el diagnóstico en `evidence`, nunca cero.
- Estado: VERIFIED o INFERRED según `combine_verification_status`, con
  `source_type=CALCULATED`, `retrieved_at=calculated_at` (instante del cálculo),
  el método con la expresión y la referencia al escenario.
- Moneda: la del escenario, o `ratio` para ROI y margin.
- Un resultado no solicitado queda ausente del conjunto, no como cálculo fallido.
- Decimal: un contexto nuevo por llamada con la precisión y el redondeo por
  defecto de Python (prec=28, ROUND_HALF_EVEN), que es la política efectiva del
  motor legacy; no es una política nueva. El contexto global del llamador no
  altera el resultado, y `exact=False` indica que una división tuvo que redondear.
- Cada dependencia enlaza su `FinancialTermEvidence` completo (contexto,
  asignación, `depends_on`).
- No hay persistencia, snapshot reproducible, API ni cambios de profitability o
  decisiones. Reproducibilidad financiera histórica (§19): PENDING.

Serialización (§19, §21; avance hacia el paso 6, que sigue PENDING porque exige
persistencia):
- Formato `FORMAT="juval.adr047.financial-record"`, `VERSION=1`. La versión
  identifica solo este contrato de serialización. Se conservan por separado la
  identidad y versión del escenario, `policy_identity`, `execution_id`,
  `record_reference` y el método de cálculo (`provenance.method` con la expresión).
- Un formato o versión desconocidos se rechazan, y también cualquier versión no
  entera.
- Un `FinancialRecordDocument` agrupa `FinancialEvidenceSet`, `DeclaredSellingPrice`,
  `FinancialDependencyResolution` y `FinancialCalculationSet`. Las partes opcionales
  deben pertenecer a la misma ejecución, registro y escenario, y los cálculos deben
  proceder de esa resolución.
- Codificación:
  - Decimal como `{"decimal": str(value)}`, exacto con signo y escala. Solo se
    acepta de vuelta la forma canónica, parseada con el constructor `Decimal`, que
    no redondea ni depende del contexto del llamador.
  - Ningún valor financiero se codifica como float JSON.
  - Instantes ISO 8601 canónicos con offset.
  - Enums por valor.
  - Claves exactas: una clave faltante o desconocida se rechaza.
  - Los constructores de dominio revalidan sus invariantes al reconstruir.
- Política decimal: `FinancialCalculationSet` registra ahora, como campos
  aditivos, `decimal_precision=28` y `decimal_rounding="ROUND_HALF_EVEN"`, la
  política efectiva ya descrita, junto con `exact` por resultado.
- Referencias: cada dependencia de término se escribe con su operando y
  aplicabilidad en línea y un `evidence_ref`. Al reconstruir, los valores en línea
  deben coincidir con la evidencia referenciada y se restauran como los mismos
  objetos del set. Los inputs explícitos (precio, peso, objetivos) vuelven como
  objetos iguales, no idénticos. Cada cálculo se enlaza por nombre de resultado a su
  `ResultResolution`.
- Determinismo: `serialize(deserialize(p)) == p` y el JSON canónico
  (`sort_keys=True`) es idéntico byte a byte. Lo probado es igualdad semántica
  completa tras atravesar JSON real.
- Resultados:
  - un bloqueado se reconstruye como NOT_FOUND `CALCULATED` con su código y detalle;
  - un no solicitado sigue ausente;
  - una exclusión sigue sin importe.
- Límites:
  - no hay identidad de versión del algoritmo o implementación, así que un
    payload no basta para afirmar recalculación histórica;
  - un input explícito bloqueado (por ejemplo, un precio NOT_FOUND) no se conserva
    como valor, porque la resolución solo guarda su bloqueo y detalle;
  - no hay persistencia, snapshot referenciado inmutable ni enlace de
    recalculación, y la reproducibilidad financiera histórica (§19) sigue PENDING.

Persistencia SQLite (paso 6, PARTIAL):
- Tabla aditiva `execution_run_financial_records`, con columnas `execution_id`,
  `record_ref`, `format`, `format_version` y `payload`.
- PK `(execution_id, record_ref)` y FK compuesta a
  `execution_run_records(execution_id, record_ref)`: un documento solo puede existir
  para un snapshot del mismo run. ASIN y UPC no participan en la identidad.
- La tabla se crea con `CREATE TABLE IF NOT EXISTS` al abrir el store, la misma
  convención local de ADR-013/019.
- `SqliteExecutionRunStore.save_execution_run` acepta el argumento aditivo
  `financial_records`, que se escribe dentro del mismo `with conn:` que el run y
  los snapshots. Un fallo financiero (FK, PK duplicada, payload de otro run)
  revierte el run y los snapshots. Esta atomicidad conjunta está probada en el
  store.
- El `Protocol` `ExecutionRunStore` y el store de Supabase no cambian.
- `save_run_with_financial_records` valida antes de escribir que cada documento
  pertenece al run y a uno de sus snapshots, una sola vez.
- Un documento guardado no se sobrescribe.
- `load_financial_record` devuelve:
  - `None` si no hay documento;
  - `FinancialSerializationError` si el payload está corrupto o es de formato o
    versión desconocidos;
  - `FinancialRecordIntegrityError` si las columnas o la identidad contradicen la
    ubicación;
  - errores de SQLite sin alterar.
- Los runs legacy se leen igual, sin documento y sin backfill, y los snapshots
  comerciales no cambian.

Integración CLI (opt-in, paso 6 PARTIAL):
- `--native-financial-evidence` (requiere `--persist-db`) usa
  `run_pipeline_with_financial_evidence`, que es el mismo `_execute` que la ruta
  legacy.
- `application/native_financial_documents.py::build_financial_documents` construye
  un `FinancialRecordDocument` por registro con escenario completo: evidencia,
  precio declarado, resolución y los seis cálculos. `save_run_with_financial_records`
  guarda run, snapshots y documentos en una transacción. Si falla, la CLI sale con
  código 3 y no queda nada persistido.
- Registros sin escenario completo o descartados por el importer no tienen
  documento. Sus problemas de captura se imprimen, porque el formato v1 no tiene
  dónde guardarlos.
- Inputs explícitos, siempre `USER_INPUT` VERIFIED con su unidad:
  - `--financial-target-profit` junto con `--financial-target-profit-currency`;
  - `--financial-target-roi` como ratio.
  - Nunca se reutilizan los umbrales comerciales `--target-*`.
- No existe input de peso por registro, así que el peso legacy no se usa y los
  resultados que dependen de un `SHIPPING_PER_POUND` aplicable quedan bloqueados.
- Paridad probada: run, Excel de salida, snapshots, profitability, decisiones,
  riesgos e issues son idénticos con y sin el flag.
- Diferencia de persistencia: la ruta legacy de la CLI guarda solo el run; la
  nativa guarda además los snapshots, necesarios para la FK de los documentos.

Garantías y límites del documento persistido:
- Recuperación: exacta del estado serializado. Está probada con igualdad semántica
  y texto canónico idéntico.
- Reconstrucción de entradas: parcial.
  - Se conserva toda la evidencia del set, el precio declarado y los operandos
    utilizados.
  - Un input explícito bloqueado (por ejemplo, un precio o un peso NOT_FOUND) solo
    queda como bloqueo y detalle, y no se reconstruye desde el texto del
    diagnóstico.
  - Los inputs explícitos no suministrados no existen en el documento.
- Reproducción histórica: no garantizada.
  - El run guarda `application_version` (`juval.__version__`), pero eso no
    identifica por sí solo las funciones de `processing/profitability.py`, la
    política de dependencias ni el entorno.
  - El formato v1 no se modificó para añadir identidades.
  - Contrato mínimo propuesto para un formato v2 o un snapshot reproducible:
    identidad del calculador (módulo y versión del contrato de cálculo), commit o
    digest de la implementación, `application_version` del run y los inputs
    explícitos tal como se suministraron, incluidos los inutilizables.
  - §19 sigue PENDING.

Formato v2 (§19; serialización pura, sin persistencia ni consumidores):
- Misma identidad de formato, `VERSION=2`, en `application/financial_serialization_v2.py`.
- El núcleo (`evidence`, `selling_price`, `resolution`, `calculations`) es
  byte-idéntico a v1 (probado). v2 añade tres bloques:
  - `supplied_inputs`: precio, peso, `target_profit` y `target_roi` tal como se
    entregaron al resolvedor, incluidos NOT_FOUND, INVALID con su valor original,
    y moneda o unidad incompatibles. `null` significa no suministrado. Debe
    coincidir exactamente con lo que vio la resolución guardada; en caso
    contrario, se rechaza.
  - `capture_problems`: los diagnósticos del capturador tal cual. El capturador
    actual solo produce texto `"<subject>: <message>"`, sin código, fila ni
    columna. v2 conserva el texto y admite `subject`, `row`, `column` y
    `raw_value` estructurados, que quedan `null` mientras el capturador no los
    emita; no se obtienen analizando el texto.
  - `implementation`: `calculator`, un SHA-256 de la tabla de expresiones y otro
    de la matriz de dependencias que contiene el código, y `application_version`,
    `code_revision` y `configuration` opcionales. Estos últimos son `null` si se
    desconocen; nunca se inventan ni se calcula un digest ficticio.
    `derivation_methods` está vacío, porque §15 no aprueba ninguno.
- v1 no cambia:
  - `deserialize_financial_record` sigue aceptando solo v1 y rechaza v2;
  - `deserialize_financial_record_v2` rechaza v1 sin convertirlo;
  - `read_financial_record` elige lector según la versión y rechaza cualquier
    otra;
  - los lectores comprueban formato y versión antes que la estructura.
- `assess_reproducibility` informa por separado los criterios no cumplidos de:
  - A, recuperación exacta del estado serializado: se cumple para cualquier
    documento válido;
  - B, reconstrucción de las entradas: se cumple en v2 y no en v1;
  - C, reproducción histórica: nunca se afirma. Enumera lo que falta (versión o
    revisión desconocidas, tablas distintas de las del código actual, requisitos
    de contexto sin método, ausencia de cálculo) y siempre incluye que el código
    y el runtime nombrados no son verificables desde el documento.
- Integración de v2 con la CLI y SQLite:
  - `build_financial_documents` produce ahora `FinancialRecordDocumentV2`:
    - `supplied_inputs` con el precio declarado, los `--financial-target-*` y el
      peso como no suministrado, porque no existe input de peso por registro;
    - un `CaptureProblem(text)` por cada problema del registro, sin estructura
      inventada;
    - `ImplementationIdentity.current(application_version=<la del run>)`, con
      `code_revision` y `configuration` en `null`, porque no hay fuente
      verificable y no se añadió un flag para rellenarlos.
  - `save_run_with_financial_records` acepta documentos v1 y v2 y guarda cada uno
    con su serialización canónica y su `format_version`, en la misma tabla y
    transacción.
  - `load_financial_record` usa `read_financial_record` y devuelve
    `FinancialRecordDocument` para filas v1 o `FinancialRecordDocumentV2` para
    filas v2. Las filas v1 existentes no se convierten ni se rellenan.
  - Probado con la CLI: A y B se cumplen; C no, porque falta `code_revision` y
    porque el código y el runtime nombrados no se pueden verificar.
- Captura estructurada y peso nativo:
  - El capturador emite `CaptureDiagnostic` en origen: `subject`, `CaptureCode`,
    mensaje, fila, y columna y valor original solo cuando una celda concreta es la
    causa. Mantiene el texto legacy en `problems`.
  - Los documentos v2 guardan `subject`, `row`, `column` y `raw_value` en
    `CaptureProblem`.
  - `code` no tiene campo en v2: queda en la captura y no se persiste. Guardarlo
    exigiría añadir `code` a `CaptureProblem` en un v3, no modificar v2.
  - `fin_weight_*` aporta un peso nativo por registro (valor, unidad declarada,
    estado y provenance `SUPPLIER_FILE`) que llega como input `WEIGHT` del
    resolvedor y a `supplied_inputs.weight`.
  - No hay conversión kg→lb ni se usa el peso legacy. Una exclusión acreditada
    de `SHIPPING_PER_POUND` no exige peso.
- Persistencia independiente de diagnósticos:
  - Formato propio `juval.adr047.capture-diagnostics` v1
    (`application/capture_diagnostics.py`), distinto de los formatos financieros.
    Contiene `execution_id`, `record_ref` y, en orden, cada `CaptureDiagnostic`
    con `subject`, `code`, `message`, `row`, y `column`/`raw_value` solo cuando el
    capturador los fijó.
  - Tabla SQLite aditiva `execution_run_capture_diagnostics`, con PK
    `(execution_id, record_ref)` y FK compuesta a `execution_run_records`.
  - Se escribe con `capture_diagnostics=` en la misma transacción que el run, los
    snapshots y los documentos financieros; la atomicidad conjunta está probada
    en el store.
  - La CLI opt-in guarda un conjunto por registro capturado, tenga escenario
    completo, parcial o ninguno; un conjunto vacío significa "sin diagnósticos".
    No se fabrica ningún escenario ni `FinancialEvidenceSet`.
  - `load_capture_diagnostics` distingue:
    - `None`: no se guardó ningún conjunto (run legacy o registro no capturado);
    - un conjunto válido;
    - payload corrupto o formato/versión desconocidos
      (`FinancialSerializationError`);
    - identidad o columnas incoherentes (`FinancialRecordIntegrityError`).
  - Este almacenamiento es la fuente completa de diagnósticos para ejecuciones
    nuevas, incluido `code`. Los `capture_problems` de v2 no cambian y coinciden
    con él (probado).
  - Los documentos históricos con solo texto no reciben códigos, y v1/v2 no
    cambian.
- Pendiente:
  - las filas descartadas por el importer no tienen `record_ref`, así que quedan
    fuera. Necesitarían una identidad por `(execution_id, número de fila de
    origen)` en un contrato aparte;
  - una fuente verificable de `code_revision`.
- §19 sigue PENDING.

Precio declarado: `DeclaredSellingPrice(amount, context)` conserva la moneda en
`amount.unit`, validada como código de 3 letras. No la toma del escenario, del
marketplace, de símbolos ni del precio legacy. Exige `EffectiveContext`, no es
una `PriceObservation` y se captura con las columnas `fin_selling_price_*`.
`application/native_financial_resolution.py` lo entrega al resolvedor sin recurrir
al precio legacy.

Pendiente y explícitamente no implementado aquí: proyección determinística de
operandos (§7), resolución de dependencias por resultado y propagación de estados
(§16, §17), snapshot efectivo reproducible (§19), persistencia/API aditivas (§21) y el consumo por el componente profitability
(§23). Los criterios de §29 relativos a esos pasos no quedan satisfechos por esta
implementación de contratos.

## 2. Contexto y problema

Un ROI matemáticamente válido no acredita por sí mismo todos sus inputs.
CostInputs y FeeInputs contienen Decimal sin VerificationStatus/provenance
individual suficiente. El estado actual de ProfitabilityResult deriva del
precio y no certifica COG, shipping, referral ni los demás costes utilizados.

Se requiere evidencia financiera autoritativa antes de que el componente
profitability del Decision Score pueda consumir resultados acreditados.
Campo, valor disponible y evidencia verificada son conceptos distintos.
VERIFIED conserva el ámbito de la fuente; no significa automáticamente
verificación independiente por Amazon.

## 3. Alcance

Se formalizan autoridad de la evidencia, escenario financiero versionado,
aplicabilidad, importes/tasas, moneda, dependencias por resultado,
propagación de estados, conservación reproducible y transición aditiva.

El contrato reutiliza FieldValue, Provenance y VerificationStatus. Las
funciones financieras determinísticas existentes siguen siendo la base
aritmética; este ADR no cambia sus fórmulas.

## 4. No objetivos

No se implementan clases, importer, adapters, fee construction, profitability,
persistencia, API, pipeline, migraciones ni subscores. No se calibran ni
aprueban D1, D2 o D3; no se eligen valores comerciales ni políticas numéricas
concretas. No se implementa FX ni se autorizan fuentes externas o credenciales.

No se modifican frontend/, frontend-next/, demo/ ni project-portal/.
MFA permanece FROZEN; SP-API permanece NOT_APPROVED. No se autorizan
infraestructura, deployment, cambios de gates ni activación de producción.

## 5. Limitaciones legacy existentes

- CostInputs/FeeInputs conservan operandos, no evidencia individual completa.
- Defaults cero de costes o fees no distinguen omisión de cero acreditado.
- Moneda, aplicabilidad y contexto efectivo no están acreditados por esos
  contratos numéricos; marketplace no resuelve moneda.
- El snapshot actual conserva precio con provenance, COG/shipping por unidad
  como valores desnudos y resultados/totales, no todo el desglose financiero
  ni la configuración efectiva necesaria para reproducirlo.
- Fees efectivos pueden proceder del argumento del caller y no del campo
  record.fees. Conservar un registro no demuestra conservar esos operandos.
- El pipeline no pasa weight_lb al motor. Un peso presente en Product no
  demuestra su uso en un coste por libra.
- La API elimina el archivo subido tras procesarlo. Su hash no conserva
  los operandos omitidos del snapshot.

Estas limitaciones se documentan sin cambiar código ni reinterpretar estados
históricos. Un VERIFIED legacy no prueba satisfacción del nuevo contrato.

## 6. Decisión

Se adopta A+: evidencia financiera basada en FieldValue, introducida de forma
aditiva y autoritativa. Applicability y valor son hechos separados, cada uno
con el estado/provenance que corresponda. No habrá un sistema paralelo de
verificación ni nuevos miembros NOT_APPLICABLE o LEGACY en VerificationStatus.

La acreditación requiere resolver todas las dependencias efectivas del
resultado, no solo comprobar que existen números o que el precio es VERIFIED.

## 7. Modelo de autoridad — A+ aditiva

La evidencia financiera es la representación autoritativa. CostInputs y
FeeInputs numéricos permanecen temporalmente como contratos legacy y operandos
de compatibilidad para cálculo; no se reemplazan inmediatamente.

En la nueva ruta acreditada, los operandos numéricos DEBEN proyectarse
determinísticamente desde la evidencia autoritativa ya resuelta. NO puede
haber dos representaciones autoritativas editables independientemente del
mismo valor. Editar un operando no puede modificar ni sustituir su evidencia.

La proyección conserva el vínculo exacto a valor, unidad, aplicabilidad,
contexto y método de origen. No rellena ausencias con defaults. Si una
representación aritmética necesita un elemento neutro para un término
explícitamente excluido, este solo puede proceder de esa exclusión resuelta:
no es una observación monetaria de cero y debe conservar su dependencia de
aplicabilidad. Una exclusión no resuelta no permite esa proyección.

La ruta legacy no se convierte en acreditada por adjuntarle metadata o por
envolver automáticamente sus Decimal. Conservar operandos proyectados para
compatibilidad no equivale a seleccionar la alternativa C como autoridad.

## 8. Escenario financiero

Un escenario financiero versionado debe identificar, como mínimo:

- identidad y versión del escenario;
- moneda explícita;
- base económica y unidad de cálculo;
- universo de términos cuya aplicabilidad debe resolverse;
- requisitos de contexto/tiempo efectivo;
- identidad de cálculo/política necesaria para reproducirlo.

El escenario se vincula inequívocamente al registro/run evaluado. Su versión
no cambia silenciosamente de significado. No se selecciona una configuración
comercial implícita ni se define aquí un formato final de identidad o clase.

El universo no se deduce de los términos presentes: si falta representación
de un concepto requerido, su ausencia no lo excluye. Un concepto necesario
pero estructuralmente no soportado impide el resultado que dependa de él.
El contexto debe distinguir conceptos incluidos en otros importes para evitar
doble conteo, sin inventar nuevos cargos.

El tiempo efectivo y la adquisición se conservan separados cuando sean
relevantes. No se sustituye contexto efectivo desconocido por retrieved_at.
Una declaración temporal no acredita por sí sola vigencia o suficiencia;
los requisitos aplicables deben resolverse antes del cálculo.

## 9. Términos financieros soportados

El contrato debe poder representar los términos existentes siguientes; esta
lista no declara que todos apliquen a todos los escenarios.

| Categoría | Términos existentes | Naturaleza económica |
|---|---|---|
| Adquisición | cog | Importe de adquisición por unidad |
| Shipping/inbound | inbound_shipping, shipping_per_unit, inbound_placement | Importes asignados por unidad |
| Shipping por peso | shipping_per_pound | Tarifa monetaria por lb |
| Preparación | prep, labeling, fragile_prep | Importes por unidad |
| Almacenamiento | storage | Importe asignado por unidad; no acredita período por sí solo |
| Impuestos/otros | vat, taxes, other_costs | Importes; vat no es una tasa en el contrato actual |
| Fees monetarios | referral_fee, fulfillment_fee, other_selling_fees | Importes aplicables al escenario |
| Referral ratio | referral_fee_rate | Ratio adimensional con base explícita |

No se añaden otros campos monetarios. El precio de venta existente participa
como dependencia cuando corresponda. Peso y objetivos efectivamente usados
son dependencias auxiliares/contexto de cálculo, no cargos nuevos.

## 10. Semántica de importe, tasa y unidad

Se distinguen importe monetario, ratio adimensional y tarifa monetaria con
denominador, por ejemplo moneda/lb. Unidad, denominador y base económica
deben impedir aritmética entre magnitudes incompatibles.

Un importe por pack no es automáticamente un importe por unidad vendible.
Los repartos o asignaciones necesarios deben conservar método y dependencias.
Un coste storage no acredita duración ni asignación temporal por su nombre.
No se infiere contenido económico desde un nombre como other_costs.

La configuración/objetivos realmente utilizados se conserva con su identidad
y base; registrar configuración no acredita aprobación comercial ni evidencia
de mercado. target_profit debe tener base monetaria compatible y target_roi
conservar su naturaleza de ratio.

## 11. Moneda

La ruta acreditada inicial calcula en una única moneda explícita por escenario.
No se asume USD ni se infiere moneda desde marketplace. Todo importe o tarifa
monetaria participante debe estar inequívocamente vinculado a esa moneda.
Un ratio adimensional conserva su base; no recibe una unidad monetaria falsa.

Moneda desconocida o incompatible bloquea los resultados dependientes. No se
permite aritmética de monedas mezcladas ni normalización monetaria implícita.
El lugar concreto donde se almacena el vínculo a la moneda queda para el diseño
de implementación, sin debilitar su resolución inequívoca.

FX queda fuera de alcance. Una conversión futura requeriría monedas original
y destino, tasa, fuente, tiempo efectivo, método, provenance y redondeo
explícitos, conservando el vínculo entre importes originales y convertidos.

## 12. Aplicabilidad

Aplicabilidad y valor se acreditan por separado. Una afirmación explícita de
aplicabilidad puede reutilizar FieldValue[bool]; el esquema final no se fija
aquí. Applicability=False requiere su propio status/provenance y justificación.

| Situación | Semántica requerida |
|---|---|
| Aplica y el valor es cero | Aplicabilidad y cero acreditados por la evidencia requerida |
| Aplica y hay valor no cero usable | Aplicabilidad resuelta y valor/provenance utilizables |
| Aplica pero importe/tasa desconocido | No se calcula la dependencia con un sustituto |
| No aplica explícitamente | Exclusión acreditada; no observación monetaria cero |
| Aplicabilidad no resuelta | Bloquea el resultado que necesita resolverla |
| Obtención intentada sin valor usable | NOT_FOUND con contexto auténtico y causa |
| Valor fuente inválido | INVALID conservando raw/diagnóstico |
| Ausente/no soportado estructuralmente | No hay evidencia representada; no equivale a exclusión |

Si la política permite una exclusión INFERRED, los resultados que dependen
de ella permanecen INFERRED. No se descarta esa dependencia porque el término
no aparezca como sumando. No se acredita aplicabilidad de un fee para cada
producto por haber pasado un único objeto fees a todo un batch.

## 13. Cero, None y ausencia estructural

Cero es un valor económico válido únicamente con la evidencia requerida.
Omisión no significa cero; default cero no se convierte en cero acreditado.
No recibir un fee no significa que su importe sea cero o que no aplique.

None significa ausencia de representación en esa ubicación. No significa
silenciosamente cero, no aplicable ni NOT_FOUND. La ausencia estructural no
acredita una consulta o evaluación, y no debe convertirse en una observación
ficticia para completar el escenario.

## 14. NOT_FOUND e INVALID

Se conservan los significados de FieldValue/VerificationStatus:

- NOT_FOUND: una evaluación/obtención auténticamente intentada no produjo
  valor utilizable; value permanece None y se conserva causa/contexto.
- INVALID: existió un valor fuente/raw pero falló la validación; se conserva
  información raw/diagnóstica y no se expone como operando utilizable.

Un fallo técnico de obtención no se presenta como prueba de ausencia de cargo.
No se inventa un intento para etiquetar ausencia estructural como NOT_FOUND.
El NOT_FOUND de un resultado evaluado por precondición incumplida describe
ese cálculo fallido, no una consulta ficticia a una fuente de inputs.

## 15. Importe y tasa de referral

referral_fee y referral_fee_rate son evidencias distintas. No se deriva uno
del otro salvo método explícitamente aprobado que conserve base, supuestos,
provenance, redondeo y contexto efectivo.

No se impone universalmente referral_fee = selling_price * referral_fee_rate.
El importe observado puede alimentar una fórmula sin que esta use la tasa.
Si un importe fue derivado de una tasa/precio, sus dependencias sí deben
conservarse transitivamente. La coherencia se evalúa dentro del método
declarado, no inventando una relación universal.

## 16. Dependencias específicas por resultado

Esta sección describe la matemática existente, sin cambiarla. Sean P el
precio, C0 los costes aplicables distintos de COG, C = COG + C0, R el importe
de referral, F fulfillment, O otros fees, r la tasa de referral, tp el objetivo
de profit y tr el objetivo de ROI.

| Resultado | Expresión existente | Dependencias/precondiciones |
|---|---|---|
| profit | P - (R + F + O) - C | Precio, costes y fees monetarios aplicables |
| ROI | profit / C | Dependencias de profit; C positivo |
| margin | profit / P | Dependencias de profit; P positivo |
| break-even | (C + F + O) / (1 - r) | Costes, fulfillment/otros fees y tasa según el modelo proporcional actual; denominador válido |
| max-COG target profit | P - (R + F + O) - C0 - tp | Precio, fees monetarios, costes no COG y objetivo efectivo |
| max-COG target ROI | (P - (R + F + O) - C0 * (1 + tr)) / (1 + tr) | Precio, fees monetarios, costes no COG y objetivo efectivo; denominador válido |

max-COG no depende matemáticamente del COG actual. La tasa no es dependencia
automática de profit cuando se suministra el importe de referral. P y R no
son operandos de la expresión de break-even, aunque el contexto efectivo de
sus fees/tasa pueda referenciarlos y deba conservarse cuando corresponda.

El modelo proporcional de break-even mantiene sus supuestos; documentarlo
no lo convierte en una fórmula universal de fees ni en evidencia comercial.
El precio usable exigido globalmente por la función legacy no se convierte
en una dependencia matemática de todos los resultados. Cambiar ese gate
requiere la activación separada de §24.

El término por peso necesita tarifa y peso efectivos cuando se utiliza.
No se omite un coste requerido porque falte peso. Las afirmaciones de
exclusión/aplicabilidad son dependencias de evidencia aunque no sean
operandos. No se exigen inputs ajenos al resultado; sí se conservan todas
las dependencias transitivas realmente utilizadas para obtener sus inputs.

## 17. Propagación de estados

Antes de calcular se resuelven presencia estructural, aplicabilidad, unidades,
moneda, base económica, contexto/tiempo efectivo y precondiciones matemáticas.
Después se combinan estados de las dependencias realmente requeridas.

| Condición | Resultado acreditado |
|---|---|
| Todas las dependencias requeridas VERIFIED | Puede ser VERIFIED dentro de ese ámbito declarado |
| Alguna usable INFERRED y ninguna requerida inutilizable | INFERRED |
| Input requerido NOT_FOUND o INVALID | NOT_FOUND/no usable, conservando causas e inputs originales |
| Ausencia estructural, aplicabilidad sin resolver, moneda desconocida/incompatible o unidad/base inválida | NOT_FOUND por precondición no resuelta |
| Contexto/tiempo efectivo requerido no resuelto | NOT_FOUND por precondición no resuelta |
| Denominador matemático inválido | NOT_FOUND con diagnóstico matemático |
| Resultado no solicitado | Ausencia estructural del resultado, no cálculo fallido |

No hay promoción. Un cálculo determinístico o una política aprobada no
acreditan sus inputs. El VERIFIED del precio no sustituye la evaluación de
costes, fees, exclusiones o supuestos requeridos.

Se mantiene combine_verification_status para combinar estados ya resueltos.
No descubre dependencias faltantes ni resuelve aplicabilidad, moneda, unidades,
base económica, freshness/contexto efectivo, exclusiones, dominios matemáticos
o construcción del grafo de dependencias. Estas son responsabilidades de la
resolución financiera, sin añadir estados a VerificationStatus.

## 18. Provenance

Se reutilizan FieldValue y Provenance conservando source, source_type,
verification_status, retrieved_at, method y, cuando existan, evidence,
source_reference, confidence y raw_value. Confidence no reemplaza al estado.

El resultado debe identificar la operación y permitir rastrear inputs,
transformaciones, asignaciones y exclusiones. Un método textual genérico no
sustituye los vínculos resolubles a las dependencias efectivas. La provenance
del resultado no reemplaza ni elimina la de sus inputs.

Se respetan los principios de
[ADR-046](ADR-046-market-evidence-observation-contracts.md): evidencia
explícita, tiempo efectivo distinto de adquisición, ausencia estructural
distinta de NOT_FOUND y no promoción. No se duplica ni redefine PriceObservation.
Una observación de precio podrá participar mediante vínculo/proyección
explícitos que preserven su significado. No se convierten precios legacy en
observaciones ADR-046 por su nombre ni se inventa su contexto faltante.

## 19. Snapshot efectivo reproducible

El futuro snapshot financiero debe conservar o referenciar inmutablemente
información suficiente para reproducir exactamente el resultado:

- identidad de run/registro y escenario financiero/versionado;
- operandos efectivos: importes, tasas, unidades, denominadores y moneda;
- afirmaciones de aplicabilidad y evidencia de inclusiones/exclusiones;
- VerificationStatus/provenance de todas las dependencias;
- tiempo efectivo separado de adquisición cuando corresponda;
- base de fees/tasas y métodos de asignación cuando se utilicen;
- configuración y objetivos realmente usados, sin completar los omitidos;
- identidad de fórmula/implementación y política de precisión/redondeo;
- outputs solicitados, valores, estados y diagnósticos;
- vínculos de dependencia y enlace de recalculación al resultado anterior.

La política numérica efectiva debe permitir reproducir operaciones Decimal
sin pérdida de precisión; su elección concreta queda pendiente. Un hash o
URL mutable por sí solos no conservan los inputs ni la implementación.
La referencia inmutable debe seguir siendo resoluble para reproducir.

Explicar un resultado almacenado y reproducir su cálculo no son equivalentes.
No se afirmará reproducción exacta si falta información necesaria.

## 20. Legacy y compatibilidad histórica

Runs y snapshots históricos no se reescriben. Sus valores/estados originales
se conservan como registros de lo almacenado, no como acreditación automática
del contrato nuevo. Decimal legacy no se transforma automáticamente en
FieldValue VERIFIED ni INFERRED.

No se inventan moneda, aplicabilidad, provenance de fees, tiempo efectivo,
objetivos ni defaults históricos. Legacy/incomplete describe la imposibilidad
de satisfacer el nuevo contrato; no es un VerificationStatus.

Nueva evidencia o recalculación genera un nuevo resultado/escenario enlazado
sin mutar el anterior. La lectura histórica sigue disponible con sus límites
explícitos; ausencia de evidencia no se disimula mediante backfill.

## 21. Evolución de persistencia y API

La migración es aditiva. No se reemplazan inmediatamente scalars existentes.
La persistencia futura podrá incorporar un bloque financiero versionado o
una referencia a un resultado financiero inmutable/versionado. Este ADR no
decide tablas frente a JSON ni crea migraciones físicas.

Ausencia del nuevo bloque no se rellena ni se interpreta como evidencia
acreditada. La API evoluciona de forma aditiva/versionada: defaults actuales
no satisfacen automáticamente el contrato nuevo. Los consumidores deben
distinguir garantías legacy y acreditadas, incluidos filtros por estado.

## 22. Migración y activación incremental

El orden previsto es:

1. Contratos de dominio aditivos.
2. Compatibilidad legacy y semántica de lectura sin promoción.
3. Captura de evidencia en importer.
4. Construcción acreditada de fees.
5. Resolución de dependencias de profitability.
6. Round-trip de persistencia.
7. API aditiva/versionada.
8. Consumo por profitability del Decision Score, sujeto a su fórmula aprobada.
9. Activación del pipeline aprobada y revisada separadamente.

Es una secuencia arquitectónica, no una instrucción para implementar ahora.
Los primeros contratos pueden añadirse sin reemplazar contratos numéricos.
Ningún paso convierte automáticamente el tráfico o los registros legacy en
acreditados. Las pruebas futuras no aplican migraciones live ni presentan
fixtures como evidencia real.

## 23. Relación con Decision Score y ADR-045

La evidencia financiera aporta los inputs efectivos acreditados necesarios
para el futuro snapshot reproducible de
[ADR-045](ADR-045-versioned-decision-score-policy.md). No reemplaza su perfil,
versionado, configuración efectiva ni vínculos de recalculación.

El componente profitability deberá consumir solamente un resultado que
satisfaga este contrato. Un ROI legacy marcado VERIFIED no basta. No se
aprueban thresholds D1, fórmula D2 ni pesos D3; no se implementa scoring.

ADR-044 D4 permanece vigente: seis componentes requeridos; cualquier componente
ausente/NOT_FOUND/INVALID deja el total NOT_FOUND incluso con peso cero;
sin reponderación ni missing-to-zero. INFERRED usable conserva estado.
D5/D6 y ADR-043 no se modifican; no se añade doble penalización.

## 24. Aislamiento del Decision Engine

Decision Score permanece separado de BUY/REVIEW/PASS. No se cambian fórmulas
financieras, gates existentes ni reglas del Decision Engine mediante este ADR.

Cualquier activación futura que cambie estados actuales de profitability o
decisiones downstream requiere un paso explícito, separado y revisado. No
se introduce ese efecto como consecuencia silenciosa de la migración.

## 25. Alternativas consideradas

- A, evidencia basada en FieldValue: seleccionada como A+ aditiva. Reutiliza
  semánticas existentes, reduce divergencia valor/evidencia, amplía menos el
  modelo conceptual que B y evita reemplazar inmediatamente los operandos.
- B, FinancialValue/MonetaryEvidence especializado: no seleccionado y diferido
  para la implementación inicial por riesgo de abstracción monetaria prematura
  y duplicación de FieldValue. No se autoriza un sistema paralelo de estados.
- C, CostInputs/FeeInputs puros con evidencia separada editable: no seleccionado
  como autoridad porque valores y evidencia pueden divergir. Conservar
  operandos como proyecciones determinísticas de A+ no equivale a C.

## 26. Consecuencias

La ruta acreditada podrá distinguir cálculo numérico de evidencia suficiente,
explicar dependencias por resultado y conservar reproducibilidad sin promover
históricos. Exige más contexto de entrada y conservación; datos antes
calculables numéricamente pueden no satisfacer el contrato acreditado.

Los contratos de dominio, la frontera legacy y su proyección read-only de §1.1
no completan por sí solos un criterio íntegro
de ADR-040: no hay resolución, integración, persistencia ni activación. Se
mantienen Implementation 44/68, Verification 17/68, Production 0/12,
Security 5/16 y Amazon 0/18, sin porcentaje agregado.

## 27. Riesgos

- Divergencia si se permite editar proyecciones como otra autoridad.
- Acreditación falsa por defaults, moneda supuesta o exclusiones sin evidencia.
- Doble conteo por bases ambiguas de shipping, impuestos u otros cargos.
- Pérdida de dependencias transitivas, incluida aplicabilidad INFERRED.
- Reproducción incompleta por guardar solo totales, hashes o referencias mutables.
- Cambios indirectos de decisiones si se activa una ruta nueva sin revisar
  efectos de estados; §24 exige activación separada.

Las invariantes anteriores limitan estos riesgos; no prueban por sí mismas
veracidad de las fuentes ni suficiencia comercial de un escenario concreto.

## 28. Decisiones diferidas

Quedan para el diseño/implementación concreta nombres de clases, formato de
identidades, estructura exacta del escenario y de los vínculos, serialización,
almacenamiento físico, idempotencia y detalles de evolución API.

Permanecen pendientes políticas numéricas concretas, requisitos efectivos
de vigencia/suficiencia por escenario y métodos adicionales de derivación o
asignación que necesiten aprobación. No se seleccionan valores comerciales,
D1/D2/D3, fuentes, FX ni activación del pipeline. Diferir un detalle no permite
debilitar las invariantes de autoridad, evidencia y conservación ya aceptadas.

## 29. Criterios de aceptación de una futura implementación

1. Reutilizar FieldValue/Provenance/VerificationStatus sin estados paralelos.
2. Mantener evidencia autoritativa y proyectar operandos determinísticamente;
   impedir representaciones autoritativas editables independientemente.
3. Conservar inicialmente contratos numéricos legacy sin acreditarlos por defecto.
4. Representar todos los términos existentes de §9 con naturaleza/unidad explícitas.
5. Distinguir cero acreditado, no aplicable, ausencia estructural, NOT_FOUND e INVALID.
6. Conservar estado/provenance de exclusiones; una exclusión INFERRED no se pierde.
7. Rechazar cálculo dependiente de moneda desconocida/incompatible o base inválida.
8. Mantener escenario/versionado y contexto efectivo separados de adquisición.
9. Mantener referral amount/rate independientes salvo método aprobado y trazado.
10. Resolver dependencias por resultado, sin exigir COG actual para max-COG ni
    tasa de referral para profit cuando no se usan directa o transitivamente.
11. Preservar todas las dependencias utilizadas, incluidas asignaciones y exclusiones.
12. Reutilizar combine_verification_status solo después de resolver precondiciones;
    conservar motivos NOT_FOUND/INVALID y ausencia de resultados no solicitados.
13. Conservar snapshot efectivo y round-trip exacto de valores/contexto numérico,
    con vínculos resolubles suficientes para reproducir el cálculo.
14. Leer históricos sin reescritura, backfill ni promoción a VERIFIED/INFERRED.
15. Crear resultado enlazado nuevo al aportar evidencia o recalcular.
16. Evolucionar persistencia/API aditivamente sin acreditar defaults existentes.
17. Respetar ADR-046 sin duplicar PriceObservation ni reinterpretar precios legacy.
18. No cambiar fórmulas, Decision Engine ni activar pipeline sin el paso separado.
19. No presentar esta implementación como aprobación D1/D2/D3 o cierre de ADR-040.
20. Verificar estas propiedades con pruebas futuras identificadas como fixtures,
    sin fuentes externas, migraciones live ni evidencia comercial inventada.
