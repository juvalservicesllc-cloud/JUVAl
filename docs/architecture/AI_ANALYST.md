# Juval — AI Analyst (Fase 1: diseño, sin código)

Ninguna línea de código de esta capa se implementó en esta fase — el
requisito explícito era diseñar el contrato, no construirlo (§14: "NO
implementar scraping... " y el objetivo general de "no construir todavía
el dashboard final ni integraciones complejas"). Este documento fija el
contrato antes de que exista una sola línea que lo pueda violar.

## 1. Posición en la arquitectura

```
Domain (Product, RiskProfile, ProfitabilityResult, DecisionResult, ...)
        │  (solo datos estructurados, ya calculados/decididos)
        ▼
   AI Analyst layer  (futuro: interfaces/ai/ o processing/ai_analyst/)
        │
        ▼
   Texto para el usuario (explicación, resumen, comparación)
```

La IA es **downstream** de Processing Core, nunca upstream. Nunca se
invoca antes de que Validation, Profitability, Risk y Decision hayan
corrido — recibe sus resultados ya calculados, no participa en
producirlos.

## 2. Qué SÍ puede hacer

Según requisito §14, todas explícitamente de solo lectura/explicación
sobre datos ya estructurados y ya calculados:

- Explicar por qué un `SourcingRecord` recibió BUY/REVIEW/PASS, citando
  los `DecisionReason` reales que produjo el Decision Engine.
- Resumir oportunidades entre varios registros ya procesados.
- Identificar contradicciones **que ya existen como `ProcessingIssue`**
  producidas por `data_quality.py` (la IA no inventa una contradicción
  nueva a partir de intuición — señala las que el sistema ya detectó, o
  como mucho sugiere revisar algo puntual dejando claro que es una
  observación, no un hallazgo verificado).
- Explicar riesgos citando los `RiskFlag` reales (tipo, severidad,
  evidencia) del `RiskProfile`.
- Comparar productos usando sus campos ya calculados/verificados.
- Responder preguntas sobre el dataset ya procesado.
- Sugerir qué productos revisar (una sugerencia de priorización, no una
  decisión — la decisión ya la tomó el Decision Engine).
- Generar comentarios de sourcing (texto libre de apoyo).

## 3. Qué NO puede hacer (regla dura, ver ADR-008)

- Inventar ASIN, precio, peso, HazMat, ventas, o cualquier otro campo del
  Data Dictionary. Si un campo es `NOT_FOUND`, la respuesta de la IA debe
  decir explícitamente que falta — nunca rellenarlo, ni con un
  "aproximadamente" no solicitado.
- Sustituir un dato faltante por una suposición presentada como dato.
- Calcular o modificar `profit`, `roi`, `margin`, `break_even_price`,
  `max_cog_*`, el `score`, o la `decision` — estos siempre vienen de
  `processing/` (código determinístico), nunca de un modelo de lenguaje
  (ver ADR-006).
- Escribir de vuelta al modelo de dominio. La capa de IA es de solo
  lectura sobre `SourcingRecord`; cualquier output de la IA es texto de
  presentación, nunca un `FieldValue` nuevo con `source_type=AI_ANALYSIS`
  que compita con un dato real — `AI_ANALYSIS` como `SourceType` existe
  únicamente para campos explícitamente cualitativos/explicativos (ej.
  `PriceDynamics.trend`), nunca para ASIN/peso/HazMat/precio/ventas.

## 4. Contrato de entrada/salida (conceptual)

Entrada: una vista de solo lectura de uno o más `SourcingRecord` ya
procesados (Product, CostInputs/FeeInputs si aplica, RiskProfile,
ProfitabilityResult, DecisionResult, ScoreComponents si existe, e issues).

Salida: texto. Nunca un valor que se vuelva a insertar como dato de
negocio en el pipeline sin pasar de nuevo por Validation (y, en la
práctica, sin revisión humana — este proyecto no contempla que la IA
escriba directamente al dataset).

## 5. Por qué esta frontera importa aquí en particular

Los campos que este proyecto trata como especialmente sensibles (ASIN,
peso, HazMat, bulky — y por extensión, en Fase 1, todo lo que alimenta
Profitability y Decision) son exactamente los que un modelo de lenguaje
puede "alucinar" con más confianza aparente. Sin esta frontera explícita,
sería fácil que una futura iteración conectara la IA "de paso" a completar
un campo faltante para que el dashboard se vea más lleno — eso es
precisamente lo que el proyecto prohíbe (§14, ADR-004, ADR-008).

## 6. Decisiones pendientes

1. Qué modelo/proveedor de IA se usará (no evaluado en esta fase).
2. Dónde vive el código (`interfaces/` como capa de presentación vs. un
   módulo de `processing/` de solo lectura) — pendiente hasta tener un
   primer caso de uso concreto.
3. Cómo se audita/loggea cada respuesta de la IA (trazabilidad de qué
   prompt + qué datos produjeron qué texto), análogo al `ExecutionRun` de
   Fase 0.
4. Límites de costo/latencia — fuera de alcance hasta que exista
   implementación.
