# ADR-007: Umbrales y reglas de decisión configurables, no hardcodeados

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

El Decision Engine clasifica cada producto en BUY/REVIEW/PASS usando
umbrales comerciales (profit objetivo, ROI objetivo, demanda mínima,
severidad de riesgo máxima aceptable). Estos valores son decisiones de
negocio que cambiarán con el tiempo, por categoría, o por estrategia de
sourcing — y el requisito del proyecto prohíbe explícitamente
"hardcoded commercial thresholds".

## Decisión

`domain/decision.py::Thresholds` es un dataclass que el llamador debe
construir explícitamente en cada invocación — no existe una instancia por
defecto exportada por el módulo. `processing/decision_engine.py` no
contiene ningún número de negocio: cada regla lee sus comparaciones desde
`Thresholds`, nunca desde una constante en el módulo.

Las reglas mismas (`DEFAULT_PASS_RULES`, `DEFAULT_REVIEW_RULES`) son un
punto de partida conceptual, reemplazable pasando `pass_rules=`/
`review_rules=` a `evaluate_decision()` — de modo que ni siquiera la
*forma* de las reglas por defecto es una decisión final e irreversible.

Lo mismo aplica a `processing/decision_score.py::ScoreWeights`: los pesos
de cada componente del score son un parámetro obligatorio, validado en
tiempo de construcción (deben sumar 1), nunca una constante en código.

## Consecuencias

- Positivas: cambiar un umbral de negocio no requiere tocar ni desplegar
  código; distintos catálogos/categorías pueden usar distintos
  `Thresholds` sin bifurcar el motor.
- Negativas: cada caller (CLI, futura API, futuro batch) es responsable de
  proveer thresholds sensatos — no hay una configuración "que ya funciona
  out of the box" sin que alguien la defina primero.
- Reversibilidad: alta — la forma de las reglas puede evolucionar
  libremente mientras el contrato `Rule = Callable[[DecisionInputs,
  Thresholds], Optional[DecisionReason]]` se mantenga.
