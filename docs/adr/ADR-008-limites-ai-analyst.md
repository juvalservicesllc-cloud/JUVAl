# ADR-008: Límites y responsabilidades del AI Analyst

- Estado: Aceptada (diseño; sin implementación en esta fase)
- Fecha: 2026-08-16

## Contexto

Juval planea una capa de IA que explique decisiones, resuma oportunidades
y compare productos (requisito §14). El riesgo central: un modelo de
lenguaje puede, sin mala intención, "completar" un campo faltante (un
ASIN, un peso, un HazMat) de forma plausible pero no verificada,
convirtiéndose de facto en una fuente de datos — exactamente lo que el
resto de esta arquitectura (FieldValue, VerificationStatus, Decision
Engine determinístico) existe para prevenir.

## Decisión

La capa de IA es estrictamente downstream y de solo lectura:

- Recibe únicamente datos ya estructurados y ya calculados/decididos
  (`Product`, `RiskProfile`, `ProfitabilityResult`, `DecisionResult`,
  `ScoreComponents`, `ProcessingIssue`s de un `SourcingRecord` ya
  procesado).
- Produce únicamente texto de presentación (explicaciones, resúmenes,
  comparaciones, sugerencias de priorización) — nunca un `FieldValue` que
  compita con un dato real, y nunca una modificación de `profit`, `roi`,
  `margin`, `score` o `decision` (ver ADR-006).
- Si un dato de entrada es `NOT_FOUND`, la salida de la IA debe decirlo
  explícitamente, nunca inventarlo ni suavizarlo con una estimación no
  solicitada.
- El único `SourceType` que la IA puede producir es `AI_ANALYSIS`, y solo
  para campos explícitamente cualitativos/explicativos (ej.
  `PriceDynamics.trend`) — nunca para ASIN, peso, HazMat, precio, ventas,
  ni ningún campo del Data Dictionary marcado como sensible.

Detalle completo del contrato en `docs/architecture/AI_ANALYST.md`.

## Consecuencias

- Positivas: la IA puede aportar valor real (explicar, resumir, priorizar)
  sin poder degradar silenciosamente la confiabilidad del dataset; un
  ASIN o peso en el sistema siempre proviene de una fuente auditable, sea
  cual sea la sofisticación de la capa de IA que se agregue después.
- Negativas: la IA no puede "rellenar huecos" del dataset aunque eso sea
  técnicamente posible y a veces conveniente — el hueco se queda visible
  como `NOT_FOUND` hasta que una fuente real lo resuelva.
- Reversibilidad: baja de forma deliberada, es una frontera de
  confiabilidad del proyecto, no un detalle de implementación.
