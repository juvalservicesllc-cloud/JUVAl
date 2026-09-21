# ADR-044 — Cobertura del score y política comercial de riesgos

- Estado: Aceptada
- Fecha: 2026-09-21
- Autoridad: aprobación explícita de Daniel E. Liendo de D4, D5 y D6.

## D4 — Decision Score completo

Se ratifica el comportamiento existente: el score completo requiere
profitability, demand, competition, price_stability, risk y
operational_complexity utilizables.

Si cualquiera está ausente, NOT_FOUND o INVALID, el score permanece
NOT_FOUND, incluso si ese componente tiene peso cero. No se reponderan
los restantes ni se sustituye ausencia por cero.

Un componente INFERRED utilizable puede participar conservando su
provenance; el resultado no se promueve a VERIFIED. No se crea un
Partial Opportunity Score.

## D5 — Mapping interno de severidad aprobado

HAZMAT → HIGH y BULKY → MEDIUM quedan comercialmente aprobados.

Esta decisión sustituye exclusivamente la provisionalidad comercial
de ADR-010. No cambia los valores ni el fallback fail-closed de ADR-015.

ADR-020 permanece vigente: presencia y severidad tienen provenance
independiente. La severidad derivada de esta política sigue INFERRED;
aprobar el mapping no verifica la severidad del producto.

Las nuevas importaciones referenciarán ADR-044 en el método de
provenance. No se reescriben registros históricos.

## D6 — Sin gate acumulativo

Se ratifica el comportamiento existente: no se añade PASS ni REVIEW
únicamente por cantidad o combinación de riesgos. Cada RiskFlag PRESENT
continúa evaluándose individualmente mediante las reglas existentes.

No se inventa severidad combinada. Se conserva la precedencia
PASS → REVIEW → BUY y ADR-043 sin modificaciones.

La cantidad/combinación podrá considerarse posteriormente dentro del
subscore risk cuando D2 sea aprobada. Esa definición deberá evitar doble
penalización accidental entre risk, operational_complexity,
profitability y Decision Engine.

## Alcance y pendientes

D4 y D6 no requieren reimplementar reglas. D5 conserva valores y estados;
solo requiere actualizar el lenguaje vigente de política y provenance.

D1 (thresholds), D2 (fórmulas) y D3 (pesos comerciales) siguen pendientes.
El score sigue experimental y separado de BUY/REVIEW/PASS.

No se modifican fórmulas financieras, thresholds ni pesos.
Fase 5 sigue BLOCKED: estas decisiones no completan un criterio íntegro
de ADR-040. Sus numeradores permanecen 44/68, 17/68, 0/12, 5/16 y 0/18.
