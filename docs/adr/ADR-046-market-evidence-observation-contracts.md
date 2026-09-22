# ADR-046 — Contratos de observaciones de evidencia de mercado

- Estado: Accepted.
- Fecha: 2026-09-21
- Autoridad: Daniel aprobó explícitamente ADR-046 el 2026-09-21.
- Estado de implementación: IMPLEMENTED. Evidencia: commit `afa267af8d7ff6da2ea9e235d3e12e1a4ff80325`.

## 1. Contexto y problema

Product contiene modelos de Demand, Competition y Price con campos para
demanda, competencia y precios. Su existencia no demuestra que haya
evidencia disponible ni que el importador actual los proporcione.

Los campos escalares existentes no expresan completamente las ventanas
temporales, poblaciones, instantes efectivos de observación y series
necesarios para interpretar evidencia de mercado sin ambigüedad.

Algunos campos legacy tampoco fijan unidades o escalas suficientes para
su uso automático: sales_velocity, share y concentration son ejemplos.

Se necesitan contratos provider-neutral que representen evidencia futura
sin inventar datos, reinterpretar históricos ni anticipar fórmulas
comerciales.

## 2. Relación con ADR-045

Esta decisión concreta A2 de ADR-045: contrato y evidencia antes de
aprobar las fórmulas definitivas de demand, competition y price_stability.

Definir una estructura válida no acredita disponibilidad de datos,
autorización de una fuente, calibración comercial ni suficiencia de
evidencia para calcular un subscore.

ADR-045 permanece vigente. No se implementan sus snapshots de ejecución,
versionado de políticas ni persistencia mediante este contrato.

## 3. Arquitectura y separación de responsabilidades

Se introducirán value objects de observaciones en Domain, independientes
de proveedores y de las proyecciones legacy.

Se distinguen:

- Observaciones: valores y contexto explícito de la evidencia.
- Proyecciones legacy de Product: representación existente, sin cambios.
- Scoring: consumidor futuro sujeto a fórmulas aprobadas; no implementado.
- Persistencia: responsabilidad futura separada; no implementada.
- Adapters: responsables futuros de traducir evidencia autorizada al
  dominio sin inventar contexto ni promover estados.

No se incorporan observaciones al pipeline predeterminado ni al Decision
Engine. No se modifican Product, Demand, Competition o Price existentes.

No habrá proyección automática de los nuevos objetos a campos legacy.

## 4. Identidad del sujeto

Las observaciones reutilizarán Identification mediante un campo subject.

Esto conserva la identificación y el marketplace existentes, evitando
duplicar ASIN o crear una identidad de producto paralela.

Reutilizar Identification no verifica por sí mismo la identidad del
producto. Su provenance y sus estados conservan su significado.

Las series exigirán el mismo subject explícito en todas sus observaciones.
No se resolverán automáticamente equivalencias entre identificaciones.

## 5. FieldValue y Provenance

Los valores de producto reutilizarán FieldValue y Provenance.

Se conservarán source, source_type, verification_status, retrieved_at,
method y, cuando existan, evidence, source_reference y confidence.

No se crearán estados paralelos de verificación ni se inferirá confianza
desde la mera presencia de un campo.

La aprobación de un contrato o de una política comercial no constituye
verificación de un valor del producto.

## 6. Estados y ausencia estructural

VERIFIED:
La fuente declarada acredita el valor dentro de su ámbito y método.
No implica automáticamente verificación independiente por Amazon.

INFERRED:
El valor procede de estimación o inferencia y conserva ese estado,
su fuente y su método. Una fórmula no lo promueve a VERIFIED.

NOT_FOUND:
Una búsqueda, consulta o evaluación declarada no obtuvo evidencia
suficiente para un valor. value permanece None; no significa cero.

INVALID:
Se recibió un dato inválido. Se conserva raw_value para diagnóstico
y no se expone un valor utilizable. No significa cero.

Ausencia estructural:
No existe una observación representada. No acredita que se haya
consultado una fuente ni equivale a una observación NOT_FOUND.

Los contratos rechazarán valores utilizables que incumplan tipo,
unidad o rango. No los corregirán, estimarán ni convertirán
silenciosamente a cero o a otro estado.

Un adapter futuro podrá representar un dato inválido mediante
FieldValue.invalid, conservando el diagnóstico y su provenance.

## 7. Tiempo de observación y adquisición

observed_at identifica el instante efectivo al que corresponde la
observación, distinto de retrieved_at, que identifica cuándo se adquirió.

Para NOT_FOUND o INVALID, observed_at corresponde al instante de la
consulta u observación fallida que se está representando. No afirma
que se haya observado un valor utilizable.

Si observed_at no se conoce, no se sustituirá por retrieved_at para
satisfacer el contrato. La evidencia incompleta no se presentará
como una observación temporal completa.

Todos los timestamps deben ser timezone-aware con offset efectivo.
No se presupone la zona local ni se exige una representación textual
única en UTC.

Se exige observed_at <= retrieved_at. Estos objetos representan
observaciones, no forecasts. Un dato histórico puede recuperarse
posteriormente; no puede declararse observado después de adquirirlo.

No se corrigen desfases de reloj automáticamente.

No se define un freshness TTL. La antigüedad de la observación y la de
su adquisición permanecen distinguibles.

## 8. EvidenceWindow y cobertura

EvidenceWindow contiene start y end timezone-aware, con start < end,
y representa el intervalo semiabierto [start, end).

La inclusión de start y exclusión de end permite ventanas consecutivas
sin contar dos veces una observación en su límite compartido.

La ventana representa únicamente el ámbito temporal declarado o
solicitado de una observación o agregado.

Su existencia NO acredita:
- cobertura completa;
- continuidad del muestreo;
- ausencia de gaps;
- número suficiente de observaciones.

No se presume una duración predeterminada ni que "mensual" signifique
un número fijo de días. Se registran los límites efectivos.

## 9. DemandObservation

Cada observación contiene:
- subject: Identification;
- metric: DemandMetric;
- value: FieldValue[int | Decimal];
- observed_at: datetime;
- population_definition: str;
- window: EvidenceWindow | None;
- rank_category: str | None.

population_definition no puede estar vacío y describe qué población
representa el dato. No se equiparan ventas de un vendedor concreto
con ventas del listing completo sin evidencia.

DemandMetric admite:

| Métrica | Tipo usable | Unidad | Rango | Tiempo |
|---|---|---|---|---|
| ESTIMATED_SALES | int | units | >= 0 | Ventana explícita |
| SALES_VELOCITY | Decimal | units/day | Finito, >= 0 | Ventana explícita |
| CURRENT_BSR | int | rank | >= 1 | Observación puntual |
| AVERAGE_BSR | Decimal | rank | Finito, >= 1 | Ventana explícita |
| RANK_DROPS | int | drops | >= 0 | Ventana explícita |

CURRENT_BSR no acepta una ventana agregada. Las demás métricas
requieren una ventana cuyo end no sea posterior a observed_at.

CURRENT_BSR, AVERAGE_BSR y RANK_DROPS requieren rank_category no vacío
para identificar la categoría o ámbito del ranking.

ESTIMATED_SALES usable exige INFERRED. No se presenta una estimación
como ventas observadas VERIFIED. Un contrato de ventas reales
observadas sería un concepto diferente, fuera de este scope.

SALES_VELOCITY declara units/day como unidad del nuevo contrato.
No reinterpreta la unidad del campo legacy ni convierte valores
automáticamente.

AVERAGE_BSR permite Decimal porque un promedio puede ser fraccionario.
No redefine los campos legacy de promedio declarados como int.

El método debe identificar la estimación, agregación o detección
aplicada por la fuente. No se implementa BSR→sales.

BSR, rank drops y estimated sales pueden estar causalmente relacionados.
Representarlos por separado no los convierte en señales independientes.

## 10. CompetitionCount

Cada conteo contiene:
- subject: Identification;
- value: FieldValue[int];
- observed_at: datetime;
- population: CountPopulation;
- fulfillment: FulfillmentScope;
- eligible_only: bool;
- population_definition: str.

CountPopulation distingue:
- OFFERS;
- DISTINCT_SELLERS.

FulfillmentScope distingue:
- ALL;
- FBA;
- FBM.

OFFERS usa unidad offers. DISTINCT_SELLERS usa unidad sellers.
El valor usable debe ser un entero >= 0; bool no es un conteo válido.

eligible_only declara explícitamente si el conteo está filtrado a
la población elegible para Buy Box según la fuente.
False significa que no se aplica ese filtro, no que todos sean inelegibles.

population_definition debe describir el ámbito de enumeración,
incluyendo condición, geografía y filtros pertinentes.

No se reinterpretan automáticamente buy_box_eligible_fba/fbm legacy
como conteos de ofertas o vendedores.

Cero es un conteo válido cuando está acreditado por la observación.
NOT_FOUND, INVALID y ausencia estructural no se convierten en cero.

No se suman poblaciones automáticamente. Los vendedores FBA y FBM
pueden solaparse; ofertas y vendedores son unidades diferentes.

No se comparan totales y subconjuntos como si compartieran contexto
cuando sujeto, fuente, instante o definición de población difieren.

## 11. AmazonPresenceObservation

Cada observación contiene:
- subject: Identification;
- value: FieldValue[bool];
- observed_at: datetime;
- scope: AmazonPresenceScope;
- population_definition: str.

AmazonPresenceScope distingue:
- OFFER_POPULATION;
- BUY_BOX.

La presencia de Amazon en una población de ofertas no equivale a
su presencia en Buy Box. Ninguna acredita la elegibilidad de JUVAl
para vender.

Un valor usable debe ser bool. False es una observación válida
cuando la fuente acredita ausencia en el ámbito declarado.

Una ausencia de observación, NOT_FOUND o INVALID no se convierte
en False.

Share y concentration permanecen DIFERIDOS. No se asigna escala
0–1 o 0–100, denominador, ventana ni definición de concentración
a los campos legacy ambiguos.

## 12. PriceObservation

Cada observación contiene:
- subject: Identification;
- amount: FieldValue[Decimal];
- observed_at: datetime;
- kind: PriceKind;
- currency: str;
- price_basis: str.

PriceKind distingue:
- SUPPLIER_QUOTE;
- BUY_BOX;
- FBA_OFFER;
- FBM_OFFER.

amount usable debe ser Decimal finito >= 0, con unit igual a currency.

currency debe ser un código explícito de tres letras ASCII mayúsculas.
Esta validación comprueba formato, no certifica pertenencia a un
catálogo monetario ni realiza conversión de moneda.

price_basis no puede estar vacío. Debe describir condición del producto,
tratamiento de envío e impuestos y alcance de la oferta cuando corresponda.
La validación de texto no certifica la veracidad ni completitud de
esa declaración; el productor de evidencia debe suministrarla fielmente.

No se infiere BUY_BOX desde un precio de proveedor ni desde el nombre
de un campo legacy.

NOT_FOUND e INVALID permanecen representables sin importe utilizable.

## 13. PriceSeries

Una serie contiene:
- subject: Identification;
- kind: PriceKind;
- currency: str;
- price_basis: str;
- window: EvidenceWindow;
- observations: tuple[PriceObservation, ...];
- expected_interval: timedelta | None.

La serie es homogénea por subject, currency, kind y price_basis.
No mezcla monedas, tipos de precio o bases económicas distintas.

Los puntos deben tener timestamps estrictamente crecientes, únicos
y dentro de [window.start, window.end).

La comparación de price_basis es explícita; no se deduce equivalencia
semántica entre textos diferentes.

expected_interval, cuando existe, debe ser positivo y representa
cadencia esperada de muestreo. None significa que no se declara esa
cadencia, no que el muestreo haya sido continuo.

La ventana, los puntos presentes y la cadencia esperada no certifican
cobertura completa. No se generan puntos para rellenar gaps ni se calcula
un porcentaje de cobertura.

Una serie vacía representa cero observaciones registradas, no una
consulta exitosa. Una observación aislada no demuestra estabilidad.

Los promedios legacy de 30/90/180 días no se convierten en series
ficticias ni constituyen por sí solos evidencia de volatilidad.

## 14. Tipos, unidades e invariantes

Las unidades de este contrato son explícitas, no valores comerciales:
units, units/day, rank, drops, offers, sellers y código de moneda.

Los valores enteros utilizables deben ser int y no bool.
Los valores Decimal utilizables deben ser finitos.
Los enums deben pertenecer al tipo declarado.

NOT_FOUND/INVALID no requieren una unidad numérica utilizable;
conservan su estado y diagnóstico sin recibir un valor sustituto.

Los objetos serán frozen y las colecciones de PriceSeries serán tuplas.
Esto evita mutación directa de esos contenedores, pero no equivale a
persistencia inmutable ni garantiza deep immutability de raw diagnostics
arbitrarios contenidos en FieldValue.

No se impone un umbral comercial, un TTL ni un mínimo de puntos para
declarar estabilidad.

## 15. Compatibilidad histórica y proveedores

No se modifican ni reinterpretan los modelos legacy, sus snapshots,
sus valores históricos o sus nombres de campo.

Los nuevos objetos no sustituyen automáticamente campos antiguos.
Una futura proyección requerirá preservar significado, unidades,
ventanas y provenance; no se implementa ahora.

Keepa, Amazon SP-API u otros proveedores serían adapters futuros
fuera del dominio. No se añaden dependencias, SDKs, credenciales,
scraping, llamadas externas ni adapters ficticios.

La validez estructural de un objeto no acredita autorización de la
fuente ni veracidad independiente de su contenido.

## 16. Decisiones deliberadamente pendientes

Este ADR no define:
- fórmulas D2 ni algoritmos BSR→sales;
- thresholds D1 ni pesos D3;
- share o concentration;
- métricas de volatilidad o estabilidad;
- freshness TTL;
- cobertura porcentual o suficiencia del muestreo;
- scoring, agregación o penalización de señales;
- persistencia o serialización;
- adapters, fuentes externas o su autorización;
- integración con importador, Product, snapshots, API o pipeline.

No se promueve INFERRED a VERIFIED ni se convierte missing en cero.

D1/D2/D3 continúan pendientes. Este contrato solo representa una parte
de la preparación técnica de entradas para D2.

D4/D5/D6 permanecen cerradas mediante ADR-044. ADR-043 y ADR-045
permanecen vigentes sin modificaciones.

## 17. Scope exacto de implementación posterior

La implementación se limitará a crear:

- src/juval/domain/market_evidence.py
- tests/unit/test_market_evidence.py

El módulo expondrá:
EvidenceWindow, DemandMetric, DemandObservation, CountPopulation,
FulfillmentScope, CompetitionCount, AmazonPresenceScope,
AmazonPresenceObservation, PriceKind, PriceObservation y PriceSeries.

No se modificarán archivos existentes como parte de ese scope.
Este ADR no es por sí mismo evidencia de implementación o tests ejecutados.

## 18. Criterios de aceptación de implementación

1. Reutilizar Identification y FieldValue/Provenance sin modelos paralelos.
2. Preservar valores, estados, fuente y método sin promoción ni relleno.
3. Distinguir ausencia estructural de observación NOT_FOUND/INVALID.
4. Validar tipos, unidades, rangos y números finitos según este contrato.
5. Rechazar timestamps sin zona efectiva y observed_at posterior a retrieval.
6. Validar ventanas positivas y límites semiabiertos sin afirmar cobertura.
7. Exigir ventanas y categoría de ranking cuando corresponda.
8. Mantener estimated sales usable como INFERRED.
9. Distinguir ofertas, vendedores y población elegible sin sumar
   automáticamente poblaciones ni afirmar elegibilidad propia.
10. Mantener cero y False como datos distintos de ausencia o error.
11. Validar homogeneidad, orden y pertenencia temporal de las series.
12. Admitir series vacías o de un punto sin declarar estabilidad.
13. No transformar promedios legacy en observaciones ficticias.
14. Verificar preservación de provenance y diagnóstico en tests específicos.
15. No modificar contratos legacy, persistencia, importación o scoring.
16. No introducir dependencia de proveedor ni llamadas externas.
17. Usar fixtures identificables como tales; no presentarlos como evidencia
    comercial o datos Amazon reales.

## 19. Consecuencias y límites

Los nuevos objetos permiten representar evidencia temporal y poblaciones
explícitas sin imponer una fórmula comercial.

La representación exige contexto que algunos proveedores o archivos
pueden no aportar. En ese caso no se inventa metadata para construir
una observación aparentemente completa.

Las definiciones textuales de población y base de precio son declaraciones
del productor de evidencia; su validación estructural no demuestra
comparabilidad económica ni equivalencia entre fuentes.

No se cierra Fase 5 ni se completa un criterio íntegro de ADR-040.
Permanecen:
Implementation 44/68, Verification 17/68, Production 0/12,
Security 5/16 y Amazon 0/18.

No se modifican frontend/, frontend-next/, demo/ ni project-portal/.
MFA permanece FROZEN. SP-API permanece NOT_APPROVED.
Sin infraestructura, deployment ni push.

## Relacionados

ADR-003, ADR-004, ADR-020, ADR-043, ADR-044 y ADR-045.
src/juval/domain/product.py.
src/juval/domain/provenance.py.
docs/architecture/DECISION_ENGINE.md.
