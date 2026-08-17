# Juval — Decision Engine (Fase 1)

## 1. Alcance de esta fase

El motor de reglas implementado (`processing/decision_engine.py`) es un
**modelo extensible de reglas**, no el conjunto de reglas definitivo del
negocio (requisito explícito §12: "no implementar reglas definitivas").
Los umbrales y las reglas exactas deben revisarse con el negocio antes de
usarse para decisiones reales.

## 2. Estructura

```
DecisionInputs (profit, roi, estimated_monthly_sales, risk_profile)
        │
        ▼
  pass_rules (evaluadas primero, precedencia alta)
        │  alguna dispara → PASS, con sus DecisionReason
        ▼ (ninguna dispara)
  review_rules
        │  alguna dispara → REVIEW, con sus DecisionReason
        ▼ (ninguna dispara)
       BUY
```

Una regla es cualquier callable `(DecisionInputs, Thresholds) ->
Optional[DecisionReason]`. `evaluate_decision()` acepta `pass_rules=` /
`review_rules=` para sustituir el set por defecto sin tocar este módulo —
así es "extensible" sin necesitar un framework de plugins completo (que
sería sobre-ingeniería para el volumen actual de reglas).

## 3. Reglas por defecto (conceptuales, no definitivas)

**PASS (descalificación dura)** — cualquiera dispara PASS:

| Regla | Dispara cuando |
|---|---|
| `rule_pass_negative_profit` | `profit` es usable y `< 0` (pérdida real) |
| `rule_pass_disqualifying_risk` | Algún `RiskFlag` PRESENT con severidad por encima de `Thresholds.maximum_risk_severity` |
| `rule_pass_restricted` | `RESTRICTED` está PRESENT y `allow_restricted=False` |
| `rule_pass_asin_not_found` | `ASIN_NOT_FOUND` está PRESENT |

**REVIEW (necesita revisión humana)** — cualquiera dispara REVIEW (si no
disparó ya PASS):

| Regla | Dispara cuando |
|---|---|
| `rule_review_profit_unknown` | `profit` no es usable (NOT_FOUND/INVALID) |
| `rule_review_profit_below_target` | `profit` usable pero `< Thresholds.target_profit` |
| `rule_review_roi_unknown_or_below_target` | `roi` no usable, o usable pero `< Thresholds.target_roi` |
| `rule_review_demand_unknown_or_below_minimum` | `estimated_monthly_sales` ausente/no usable, o `< Thresholds.minimum_estimated_monthly_sales` |
| `rule_review_unknown_risk` | `risk_profile.has_unknown_risk` y `allow_unknown_risk=False` |
| `rule_review_approval_required` | `APPROVAL_REQUIRED` PRESENT y `allow_approval_required=False` |

Racional de PASS vs. REVIEW: PASS se reserva para resultados confirmados
malos (pérdida real, riesgo descalificante confirmado) — nunca para un
dato faltante. Un dato faltante o un valor apenas por debajo del umbral es
REVIEW: el sistema no sabe lo suficiente o el caso es limítrofe, así que
un humano decide. Esto respeta "nunca asumir que un ASIN/peso/hazmat es
correcto sin evidencia" extendido a "nunca convertir incertidumbre en
rechazo automático ni en aprobación automática".

## 4. Thresholds — configurables, nunca hardcodeados

`domain/decision.py::Thresholds` no exporta una instancia por defecto: el
llamador siempre debe declarar explícitamente `target_profit`,
`target_roi`, `minimum_estimated_monthly_sales`,
`maximum_risk_severity`, y opcionalmente los flags `allow_restricted` /
`allow_approval_required` / `allow_unknown_risk` (todos `False` si se
omiten, la postura más conservadora). Ver ADR-007.

## 5. Decision Score (0-100) — EXPERIMENTAL / NOT BUSINESS-APPROVED

Independiente de BUY/REVIEW/PASS. Ningún modelo comercial definitivo ha
sido aprobado para el score todavía — se mantiene como componente
experimental (requisito Fase 2 §9): implementado y probado
(`processing/decision_score.py`), pero **no** se invoca dentro de
`process_record`/`process_batch` en el pipeline por defecto de Fase 2, y
ningún resultado de Juval debe presentarse como si el score fuera una
métrica de negocio validada hasta que esta nota se retire explícitamente.

`processing/decision_score.py::compute_decision_score` combina 6
subscores (`profitability`, `demand`, `competition`, `price_stability`,
`risk`, `operational_complexity`), cada uno un `FieldValue[Decimal]` en
`[0,100]`, con `ScoreWeights` configurables que deben sumar 1.

Reglas duras:
- Si falta o no es usable cualquier componente, el score completo es
  `NOT_FOUND` (v1 no rellena con "asunciones razonables" — ver §7).
- El score resultante nunca es `VERIFIED` si algún componente es
  `INFERRED` (`combine_verification_status`).
- El cálculo de cada subscore (cómo pasar de "ROI=35%" a "profitability
  subscore=72/100", por ejemplo) **no se definió en esta fase** — es una
  decisión de negocio, ver §7.

## 6. Frontera con la IA

El Decision Engine y el Decision Score son 100% código determinístico. La
IA nunca calcula `profit`, `roi`, `margin`, ni el score ni la decisión
misma — puede, como mucho, **explicar** una decisión ya tomada (ver
`AI_ANALYST.md`, ADR-006, ADR-008).

## 7. Decisiones pendientes específicas del Decision Engine

1. Umbrales de negocio reales para `Thresholds` (los usados en tests son
   ilustrativos).
2. Fórmula de cada subscore individual de `ScoreComponents` (ej. cómo
   mapear ROI a un 0-100).
3. Política de score parcial: ¿se permitirá alguna vez calcular un score
   con componentes faltantes (reponderando), o se mantiene la regla
   estricta actual de "falta uno ⇒ NOT_FOUND"?
4. Si `severity == maximum_risk_severity` exactamente (el límite, no por
   encima) debe ser BUY, REVIEW o PASS — hoy solo ">" dispara PASS.
5. Cómo interactúan múltiples riesgos simultáneos con distinta severidad
   más allá de `highest_severity` (¿el conteo de riesgos importa, no solo
   el máximo?).
