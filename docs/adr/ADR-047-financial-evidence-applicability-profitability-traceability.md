# ADR-047 — Evidencia financiera, aplicabilidad y trazabilidad de rentabilidad

## 1. Estado y autoridad

- Estado: Aceptada.
- Fecha: 2026-09-22.
- Autoridad: aprobación explícita de Daniel de las decisiones del Financial
  Evidence Contract y de la dirección aditiva A+ el 2026-09-22.
- Estado de implementación: PARTIALLY IMPLEMENTED. El paso 1 de §22
  (contratos de dominio aditivos) existe en `src/juval/domain/financial_evidence.py`,
  probado en `tests/unit/test_financial_evidence.py`. Los pasos 2-9 de §22 siguen
  PENDING: no hay cálculo, proyección a CostInputs/FeeInputs, captura en importer,
  resolución de dependencias, snapshot, persistencia, API, consumo por Decision
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

Invariantes verificadas en tests: ausencia estructural (`amount=None`) distinta de
NOT_FOUND, INVALID, cero acreditado y exclusión; exclusión sin operando monetario;
exclusión INFERRED que conserva su estado; `referral_fee_rate` como ratio con unidad
`ratio` y límites [0, 1) coherentes con `FeeInputs` y con el denominador de
break-even, quedando un valor fuera de rango representable como INVALID; rechazo de
Decimal no finito y de `bool` como número; moneda incompatible con el escenario
rechazada sin normalización implícita; términos asignados por unidad que exigen
método de asignación explícito.

Pendiente y explícitamente no implementado aquí: proyección determinística de
operandos (§7), resolución de dependencias por resultado y propagación de estados
(§16, §17), snapshot efectivo reproducible (§19), lectura legacy sin promoción
(§20), persistencia/API aditivas (§21) y el consumo por el componente profitability
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

Los contratos de dominio de §1.1 no completan por sí solos un criterio íntegro
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
