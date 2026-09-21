# ADR-043 — REVIEW al alcanzar el máximo de severidad de riesgo

- Estado: Aceptada
- Fecha: 2026-09-21
- Autoridad: decisión comercial explícita del usuario en esta sesión.

## Contexto

`DECISION_ENGINE.md` §7.4 dejaba abierta la igualdad de severidad. La regla
existente solo disparaba PASS por severidad superior al máximo; la igualdad
podía acabar en BUY cuando ninguna otra regla disparaba. ADR-007 permite
extender las reglas por defecto manteniendo thresholds explícitos y su contrato.

## Decisión

En el conjunto por defecto, un `RiskFlag` PRESENT cuya `severity.value` sea
exactamente `Thresholds.maximum_risk_severity` produce REVIEW con la razón
`RISK_AT_MAXIMUM`, salvo que alguna regla PASS independiente ya haya disparado.
La razón identifica tipo de riesgo, severidad, estado de verificación de esa
severidad y máximo configurado. Se conserva la evaluación PASS → REVIEW → BUY.
Severidad inferior no dispara esta regla y deja evaluar las restantes; superior
conserva `RISK_ABOVE_MAXIMUM`. No se fija ningún máximo comercial por defecto.

REVIEW conserva la oportunidad para evaluación final del usuario; no autoriza
compra, venta en Amazon ni declara ausencia de riesgos. BUY/REVIEW/PASS son
clasificaciones automáticas, distintas de la decisión final de compra humana.

Solo se comparan riesgos PRESENT con la severidad ya existente. UNKNOWN y
ABSENT no disparan la nueva regla; sus reglas y opciones actuales permanecen.
No se crean severidades ni se promueve INFERRED, INVALID o NOT_FOUND a VERIFIED.
La severidad INFERRED utilizable sigue siendo inferida al producir REVIEW.
ADR-020 conserva separados los ejes de presencia y severidad; ADR-010 mantiene
HAZMAT→HIGH y BULKY→MEDIUM como clasificación provisional, sin aprobarla aquí.

Esta decisión complementa ADR-007; no modifica retrospectivamente ADR-007,
ADR-010, ADR-015 ni ADR-020. No cambia esquema, fuentes, arquitectura, security
boundary, fórmulas de rentabilidad/score, thresholds ROI ni reglas no relacionadas.
Los callers que sustituyen explícitamente `review_rules` siguen sustituyendo el
conjunto por defecto; no se introduce un REVIEW global fuera del evaluador.

## Consecuencias y aceptación

Implementación: una regla pura en `processing/decision_engine.py`, añadida al
conjunto REVIEW existente. Retorna la primera razón de igualdad encontrada en
el orden del perfil, igual que la regla de riesgo superior; no inventa una
política de agregación de riesgos. Todos los bloqueos PASS se evalúan primero.

Pruebas: HazMat y Bulky por debajo/en/por encima del máximo, severidad VERIFIED
e INFERRED, precedencia de beneficio negativo, reglas REVIEW independientes,
UNKNOWN con NOT_FOUND/INVALID, ABSENT y reemplazo explícito de reglas. Integración
CSV → pipeline preserva la severidad provisional INFERRED y su fuente/método.
Timestamps de tests fijos permiten resultados determinísticos reproducibles.

Se cierra únicamente el subcriterio de igualdad de Fase 5. Las fórmulas de
subscore, thresholds comerciales y demás decisiones pendientes siguen abiertas;
el Decision Score sigue experimental. No hay cierre de producción ni Amazon.
