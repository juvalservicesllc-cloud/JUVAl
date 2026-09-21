# ADR-045 — Política versionada y reproducibilidad del Decision Score

- Estado: Aceptada
- Fecha: 2026-09-21
- Autoridad: aprobación explícita de Daniel de A1, A2 y A3.
- Estado de implementación: no implementada por este ADR.

## 1. Contexto y problema

El agregador del Decision Score recibe seis componentes y seis pesos.
Las fórmulas comerciales de los componentes, los valores de thresholds
y la distribución comercial de pesos siguen pendientes.

El pipeline predeterminado calcula rentabilidad y BUY/REVIEW/PASS;
no calcula el Decision Score. ExecutionRun conserva identificación,
hash del input, versión de aplicación y contadores, pero no contiene
la configuración efectiva de thresholds, pesos y fórmulas.

Los snapshots actuales conservan resultados y parte de su provenance,
pero no constituyen un registro completo para reconstruir un scoring
histórico. Una versión de aplicación o un identificador de política
no sustituyen los inputs y la configuración efectiva utilizados.

Se necesita una arquitectura que permita explicar resultados después
de cambiar la política, sin sobrescribirlos ni completar información
histórica por inferencia.

## 2. A1 — Perfil inicial versionado y selección explícita

JUVAl comenzará con un único Decision Score Policy Profile versionado,
seleccionado explícitamente por el llamador.

No habrá un default comercial silencioso. La ausencia de una selección
explícita no autoriza escoger el perfil disponible automáticamente.

La arquitectura permitirá incorporar otros perfiles versionados sin
alterar la identidad, interpretación ni resultados de perfiles anteriores.

Esta decisión no proporciona valores comerciales ni crea ahora un perfil
ejecutable completo. D1 y D3 siguen pendientes de calibración concreta.

## 3. A2 — Contrato y evidencia antes de fórmulas definitivas

Antes de aprobar las seis fórmulas definitivas deben existir contratos
claros para las entradas de demand, competition y price_stability.

Estos contratos deberán identificar campos, tipos, unidades, períodos,
rango válido, fuente, evidencia, cobertura y provenance/status, además
del tratamiento de datos ausentes o inválidos.

Los modelos actuales contienen campos para estas señales, pero el flujo
de importación inspeccionado no los proporciona. La existencia de un campo
no demuestra disponibilidad de datos.

No se inferirá demanda desde precio o categoría, no se inventará
competencia y no se presentarán promedios como prueba de volatilidad.
No se sustituirá ausencia por cero.

Las fórmulas concretas D2 permanecen pendientes.

## 4. Separación de responsabilidades

- Decision Score: cálculo determinístico independiente, con sus componentes,
  pesos y provenance.
- BUY/REVIEW/PASS: clasificación del Decision Engine mediante sus reglas
  y thresholds; no consume el score por esta decisión.
- Calibración comercial: aprobación humana de valores, fórmulas y pesos.
- Provenance/evidencia: describe el origen y estado de los inputs y
  resultados; no es reemplazada por la aprobación comercial.

El score no autoriza una compra ni demuestra elegibilidad para vender
en Amazon. No se conecta al pipeline predeterminado ni modifica fórmulas
financieras o reglas de decisión mediante este ADR.

## 5. Modelo conceptual de Score Policy

Una política identifica una definición versionada que puede representar:

- identidad del perfil y score_policy_version;
- ámbito de aplicación y configuración comercial aprobada;
- thresholds y flags relevantes;
- seis pesos;
- definición, parámetros y versiones de las seis fórmulas;
- contratos de entrada referenciados;
- política de cobertura;
- política de precisión y redondeo.

Estos elementos son responsabilidades conceptuales, no un esquema SQL
ni una definición definitiva de clases.

Registrar thresholds como contexto no los convierte automáticamente en
inputs de las fórmulas del score. Cada fórmula deberá declarar sus
dependencias efectivas cuando sea aprobada.

No se seleccionan valores, pesos, fórmulas ni un modo de redondeo en este ADR.
Una política incompleta no debe presentarse como calibración aprobada.

## 6. Identidad y versionado

La identidad del perfil distinguirá estrategias; la versión distinguirá
definiciones inmutables de una misma estrategia.

Una versión publicada no cambiará de significado. Cambios en pesos,
fórmulas, parámetros o políticas que afecten la interpretación del
resultado requerirán una nueva versión.

Cada versión deberá resolver inequívocamente las fórmulas y parámetros
que utiliza. Pueden referenciarse definiciones inmutables, sin depender
de un alias mutable como "actual" para explicar una ejecución histórica.

El formato de los identificadores y su almacenamiento quedan para el
diseño de implementación. No se impone aquí SemVer ni un registro externo.

## 7. A3 — Snapshot efectivo por ejecución explícita de scoring

Cada ejecución explícita deberá conservar un snapshot inmutable capaz
de representar, como mínimo:

- identidad de la ejecución y del producto/run evaluado;
- identidad del perfil y score_policy_version seleccionados;
- configuración efectiva del perfil;
- thresholds utilizados y flags relevantes;
- los seis pesos efectivos;
- parámetros y versiones de las fórmulas;
- política de cobertura y de precisión/redondeo;
- inputs efectivos necesarios para explicar el cálculo, con unidades,
  períodos y provenance/status;
- los seis componentes calculados, incluidos sus estados no utilizables;
- score final y su provenance/status;
- identificación de la implementación utilizada y momento de ejecución;
- vínculo al resultado anterior cuando exista una recalculación.

Una referencia de versión no sustituye este snapshot.

La configuración efectiva debe distinguir valores realmente utilizados
de datos no registrados o no aplicables. No se inventarán valores para
rellenar el snapshot.

La representación deberá conservar los valores Decimal sin pérdida de
precisión que impida explicar el cálculo.

## 8. Inmutabilidad y recalculación

Los resultados históricos y sus snapshots no se modificarán
silenciosamente al cambiar una política o configuración.

Recalcular un producto/run con otra política producirá una nueva
identidad de resultado y un vínculo explícito al resultado anterior.
El resultado original seguirá siendo consultable con su configuración.

Una corrección de inputs que origine un nuevo cálculo deberá conservar
igualmente el resultado anterior y distinguir los inputs nuevos.

Los detalles de reintentos e idempotencia se definirán en la
implementación sin debilitar estas reglas de conservación.

## 9. Históricos anteriores a esta arquitectura

Los registros sin configuración efectiva conservada seguirán siendo
históricos con configuración no registrada.

No se reconstruirán thresholds, pesos, fórmulas o provenance mediante
defaults actuales ni mediante el perfil vigente.

Podrá mostrarse el resultado almacenado y la evidencia que realmente
exista, indicando los límites para explicarlo o reproducirlo.

Si se efectúa un nuevo cálculo con inputs disponibles y una política
explícita, será un resultado nuevo, no un backfill supuesto del anterior.

## 10. Provenance y reproducibilidad

Se reutilizarán los contratos FieldValue/Provenance existentes.
INFERRED no se promoverá a VERIFIED por aprobar una política.

La ejecución deberá poder explicar qué inputs y configuración produjeron
cada componente y el total. La reproducibilidad requiere conservar
también las definiciones/versiones de cálculo y los inputs efectivos;
un hash de archivo por sí solo no conserva su contenido.

Explicar un resultado almacenado y reproducir exactamente su cálculo
son capacidades distintas. No se afirmará la segunda si faltan inputs,
configuración o implementación histórica identificable.

Cuando un cálculo no pueda producir un score completo, se conservarán
sus estados y motivos, sin rellenar datos para lograr un número.

## 11. Compatibilidad con ADR-043 y ADR-044

ADR-043 permanece vigente: un riesgo PRESENT igual al máximo configurado
produce REVIEW salvo un PASS independiente de mayor precedencia.

D4 permanece cerrada: los seis componentes deben ser utilizables.
Ausente/NOT_FOUND/INVALID implica score NOT_FOUND incluso con peso cero.
No hay reponderación, missing-to-zero ni Partial Opportunity Score.
INFERRED utilizable puede participar preservando su estado.

D5 permanece cerrada: HAZMAT → HIGH y BULKY → MEDIUM son mapping interno
aprobado. La severidad derivada sigue INFERRED y conserva su provenance
separada de la presencia conforme a ADR-020.

D6 permanece cerrada: no hay un gate acumulativo por cantidad/combinación
de riesgos ni severidad combinada. Cada PRESENT conserva su evaluación
individual mediante las reglas existentes.

Este ADR no modifica ni reabre esas decisiones.

## 12. Riesgos de doble penalización

Las futuras fórmulas deberán declarar qué aspecto mide cada componente.

Deberá evitarse contar accidentalmente varias veces la misma economía
mediante profit, ROI y margen; costes ya descontados en rentabilidad;
o HazMat/Bulky en risk, operational_complexity y Decision Engine.

Usar una señal tanto como gate independiente como para ordenar productos
requiere una justificación comercial explícita de sus funciones distintas.
No se implementa una penalización nueva mediante este ADR.

## 13. Persistencia y compatibilidad futura

La implementación requerirá evaluar cambios aditivos en modelos,
serialización y almacenes existentes para conservar configuración,
inputs, componentes, resultados y vínculos de recalculación.

Se preservará la lectura de ejecuciones anteriores sin exigirles campos
que nunca fueron registrados. La ausencia histórica no recibirá defaults
comerciales al deserializar.

La elección entre columnas, documentos o tablas vinculadas queda para
el diseño concreto. Podrán requerirse migraciones de esquema y adaptación
de contratos, pero este ADR no las diseña definitivamente ni las ejecuta.

La futura incorporación de varios perfiles reutilizará identidad,
versionado y snapshots; no reinterpretará resultados anteriores.

## 14. Consecuencias y pendientes

Beneficios: trazabilidad de la configuración efectiva, separación de
aprobación y evidencia, y conservación de resultados al evolucionar políticas.

Costes: mayor volumen de evidencia persistida, compatibilidad de esquemas
y necesidad de conservar definiciones históricas de cálculo.

Siguen pendientes:
- D1: calibración concreta de los cuatro thresholds.
- D2: contratos de entradas faltantes y seis fórmulas concretas.
- D3: distribución concreta de los seis pesos.
- Modelos, integración explícita, persistencia y migraciones futuras.
- Detalles técnicos de identidad, serialización, precisión e idempotencia.

No se aprueban fuentes externas, credenciales, deployment ni migraciones
live. No se acredita preparación para producción o cumplimiento Amazon.

## 15. Criterios de aceptación de una futura implementación

1. La ejecución exige selección explícita de perfil/versionado; no usa
   un default comercial silencioso.
2. Conserva la configuración efectiva, inputs, componentes y resultado
   con la provenance necesaria para explicar el cálculo.
3. Identifica inequívocamente fórmulas, parámetros y política de redondeo.
4. Mantiene D4, D5, D6 y ADR-043 sin cambios.
5. No incorpora el score a BUY/REVIEW/PASS ni al pipeline predeterminado.
6. Una nueva política genera un nuevo resultado vinculado, sin sobrescribir
   el anterior ni alterar su interpretación.
7. Los históricos sin configuración siguen legibles y explícitamente
   incompletos; no reciben backfill inferido.
8. La configuración/los inputs guardados permiten reproducir el resultado
   cuando se dispone de la implementación histórica correspondiente.
9. Las pruebas distinguen fixtures de datos reales y aprobación comercial
   de verificación del producto.
10. Los cambios de persistencia son aditivos y su compatibilidad se verifica
    sin aplicar migraciones live como parte de las pruebas.
11. No se presentan fórmulas, pesos o thresholds pendientes como aprobados.

## 16. Alcance de esta formalización

Este ADR formaliza A1/A2/A3; no implementa scoring, modelos ni persistencia.
El Decision Score sigue experimental y Fase 5 continúa BLOCKED.

No se completa un criterio íntegro de ADR-040:
Implementation 44/68, Verification 17/68, Production 0/12,
Security 5/16 y Amazon 0/18 permanecen sin cambios.

## Relacionados

ADR-003, ADR-004, ADR-006, ADR-007, ADR-013, ADR-019, ADR-020,
ADR-040, ADR-043 y ADR-044.
docs/architecture/DECISION_ENGINE.md.
