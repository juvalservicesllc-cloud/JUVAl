# ADR-010: Severidad por defecto para riesgos declarados por el proveedor es provisional

- Estado: Aceptada (marcada explícitamente como provisional)
- Fecha: 2026-08-16

## Contexto

`RiskFlag` exige siempre una `severity` (invariante de Fase 1: un riesgo
`PRESENT` no puede existir sin severidad). Cuando el Excel Importer lee
`hazmat=TRUE` o `bulky=TRUE` de un archivo de proveedor, tiene que asignar
alguna severidad para poder construir un `RiskFlag` válido — el proveedor
declara *que* el riesgo existe, no *qué tan severo* es.

Esto no es lo mismo que un "umbral comercial hardcodeado" (que la Fase 2
prohíbe explícitamente): un umbral comercial es una decisión de negocio
sobre qué resultado se acepta (ej. "ROI mínimo 30%"); una clasificación de
severidad por tipo de riesgo es más cercana a una taxonomía de seguridad/
cumplimiento. Aun así, el proyecto no ha recibido aprobación de negocio
sobre estos valores concretos, así que deben tratarse con la misma
honestidad que cualquier default no aprobado.

## Decisión

`infrastructure/excel/importer.py::DEFAULT_RISK_SEVERITY` fija
`HAZMAT -> Severity.HIGH` y `BULKY -> Severity.MEDIUM` como clasificación
explícita, nombrada, documentada en el código y en
`EXCEL_PROCESSING.md` §5 — nunca implícita ni enterrada en lógica
condicional. Se marca **provisional / no aprobada por negocio** hasta que
alguien con autoridad de negocio la revise (ver decisión pendiente en
`DECISION_ENGINE.md`).

No se usa para ningún otro `RiskType` — los 12 tipos restantes no están
conectados desde Excel en esta fase (`EXCEL_PROCESSING.md` §8), así que no
había necesidad de decidir su severidad todavía.

## Consecuencias

- Positivas: el pipeline puede funcionar de extremo a extremo sin bloquear
  en una decisión de negocio no resuelta; el valor provisional es
  auditable (aparece en el código, en la documentación y, vía
  `RiskFlag.evidence="declared by supplier"`, en cada registro exportado).
- Negativas: hasta que se apruebe formalmente, ninguna decisión BUY/PASS
  basada en HazMat/Bulky debería tratarse como definitiva sin que un
  humano confirme que la severidad asumida es razonable para ese caso.
- Reversibilidad: alta — es un diccionario de dos entradas, aislado y
  fácil de reemplazar por una fuente de configuración real cuando exista.
