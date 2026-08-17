# ADR-011: SourcingRecord como composición, nunca como segunda implementación

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

Juval necesita un agregado que represente "una fila/producto completo
procesable" para poder implementar el Excel Importer/Exporter y el
pipeline de procesamiento (Fase 2). El riesgo natural al crear ese
agregado es duplicar información que ya vive en `Product`, `CostInputs`,
`FeeInputs`, `RiskProfile`, `ProfitabilityResult`, `DecisionScoreResult` o
`DecisionResult` — por ejemplo, redefiniendo un campo `asin` propio en
`SourcingRecord` en vez de leerlo de `product.identification.asin`. Eso
crearía dos fuentes de verdad para el mismo dato y el riesgo de que
diverjan.

## Decisión

`domain/sourcing_record.py::SourcingRecord` es composición pura: cada uno
de sus campos es una instancia del tipo ya existente en su módulo
correspondiente, sin redefinir ningún campo interno de esos tipos.
`SourcingRecord` no tiene, por ejemplo, un campo `asin` o `weight` propio
— solo `product: Product`, y quien necesite el ASIN lee
`record.product.identification.asin`.

Es inmutable como el resto del dominio: los pasos del pipeline
(`processing/pipeline.py::process_record`) no mutan un `SourcingRecord` en
sitio, sino que producen uno nuevo vía `dataclasses.replace` a través de
los helpers `.with_costs()` / `.with_risk()` / `.with_profitability()` /
`.with_score()` / `.with_decision()` / `.with_issues()`. Esto evita que un
registro parcialmente procesado sea visible de forma inconsistente a dos
llamadores distintos.

`costs` es `Optional[CostInputs]` en vez de obligatorio: si el origen no
trae un COG usable, `SourcingRecord.costs` queda en `None` en lugar de
fabricar un `CostInputs(cog=0)` — la ausencia es la representación
correcta, no un valor inventado (ver también `CostInputs` en Fase 1 y
`EXCEL_PROCESSING.md` §4).

## Consecuencias

- Positivas: cero riesgo de que `SourcingRecord` y `Product`/
  `ProfitabilityResult`/etc. diverjan sobre el mismo dato; los tests de
  cada componente (`Product`, `CostInputs`, ...) siguen siendo la única
  fuente de verdad sobre su propio comportamiento; `SourcingRecord` en sí
  mismo casi no necesita tests de lógica, solo de composición e
  inmutabilidad.
- Negativas: acceder a un campo profundo requiere una ruta con puntos
  (`record.product.identification.asin.value`) en vez de un atajo plano —
  aceptado deliberadamente a cambio de no duplicar.
- Reversibilidad: alta — añadir un helper de conveniencia (una property de
  solo lectura que delegue, ej. `record.asin`) sería compatible con esta
  decisión siempre que siga sin *copiar* el dato.
