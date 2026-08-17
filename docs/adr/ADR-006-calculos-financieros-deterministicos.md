# ADR-006: Cálculos financieros determinísticos, nunca delegados a IA

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

Juval calculará profit, ROI, margin, break-even price y max COG — números
que determinan directamente decisiones de compra reales. Un modelo de
lenguaje puede producir un número plausible para cualquiera de estos
campos sin que exista garantía de que sea correcto, y sin que el error sea
evidente al leerlo. El requisito del proyecto es explícito: "Estos valores
deberán ser calculados por código determinístico. La IA no calculará estos
valores."

## Decisión

Todo el Profitability Engine (`processing/profitability.py`) y el Decision
Score (`processing/decision_score.py`) son funciones puras de `Decimal`
(o `FieldValue[Decimal]`) a `Decimal` — sin llamadas a ningún modelo de
IA, en ningún punto de la cadena. Las fórmulas están documentadas y
probadas (`tests/unit/test_profitability.py`,
`tests/unit/test_decision_score.py`) contra valores conocidos calculados a
mano.

Si en el futuro se agrega una capa de IA (`AI_ANALYST.md`), esa capa puede
**leer** `profit`/`roi`/`margin`/`score`/`decision` ya calculados para
explicarlos en texto, pero nunca puede producir un valor que sustituya o
modifique el resultado del código determinístico.

## Consecuencias

- Positivas: reproducibilidad garantizada (mismos inputs ⇒ mismo output,
  siempre); auditable con matemáticas simples, sin depender de logs de
  prompts para reconstruir un número.
- Negativas: cualquier nueva fórmula financiera requiere código y tests
  explícitos — no se puede "simplemente pedirle a la IA" un cálculo nuevo
  como atajo.
- Reversibilidad: baja de forma deliberada — esto es una línea roja del
  proyecto, no una preferencia de implementación.
