# ADR-015: Fallback fail-closed para severidad de riesgo no mapeada

- Estado: Aceptada — aprobada explícitamente por el usuario 2026-08-17,
  como conclusión técnica de dos sesiones de análisis arquitectónico de
  `DEFAULT_RISK_SEVERITY` (ver `docs/PROJECT_STATUS.md`).
- Fecha: 2026-08-17

## Contexto

`infrastructure/excel/importer.py::DEFAULT_RISK_SEVERITY` (ADR-010,
`Estado: Aceptada`, marcada explícitamente provisional) mapea
`RiskType.HAZMAT -> Severity.HIGH` y `RiskType.BULKY -> Severity.MEDIUM`.
`_build_risk_flag()` construía la severidad de un `RiskFlag` con:

```python
severity=DEFAULT_RISK_SEVERITY.get(risk_type, Severity.MEDIUM)
```

Un análisis arquitectónico (sesión previa, ver `docs/PROJECT_STATUS.md`)
encontró que este `.get(risk_type, Severity.MEDIUM)` es un **fallback
silencioso** no documentado por ADR-010: si en el futuro se conecta un
`RiskType` distinto de HAZMAT/BULKY (de los 12 restantes, hoy sin fuente
de datos — ver `docs/architecture/EXCEL_PROCESSING.md` §8) sin agregar
su entrada correspondiente a `DEFAULT_RISK_SEVERITY`, el sistema le
asignaría `Severity.MEDIUM` sin ninguna advertencia, error, ni registro
de que se usó un valor no revisado para ese tipo específico. Esa
severidad asumida podría entonces disparar una decisión `PASS` real vía
`processing/decision_engine.py::rule_pass_disqualifying_risk`, exactamente
el patrón de "inventar/asumir un valor de negocio" que el proyecto
prohíbe (`ARCHITECTURE.md` §2, `CLAUDE.md` §4).

En el estado del código anterior a esta decisión, este fallback era
código inalcanzable: `_build_risk_flag()` solo se invocaba con
`RiskType.HAZMAT` y `RiskType.BULKY` (`importer.py`, líneas 460-461 en
ese momento), ambos presentes en el diccionario. El riesgo era
prospectivo, no un bug activo — pero real para cualquier extensión
futura (ej. Fase 6, fuentes externas de enriquecimiento) que reutilizara
esta función.

## Decisión

**Un `RiskType` sin severidad explícitamente mapeada en
`DEFAULT_RISK_SEVERITY` debe producir un error explícito (fail-closed).
Juval no asignará una severidad por defecto a un `RiskType`
desconocido/no mapeado.**

Implementación: `DEFAULT_RISK_SEVERITY.get(risk_type, Severity.MEDIUM)`
se reemplaza por `DEFAULT_RISK_SEVERITY[risk_type]` — un `KeyError`
determinista y no capturado en ningún punto de la cadena de llamadas
(`_build_risk_flag` → `_build_record` → `import_excel`), por lo que se
propaga hasta el llamador sin transformarse silenciosamente en ningún
otro valor ni en una decisión `PASS`.

Consecuencia directa: **conectar un `RiskType` nuevo a
`_build_risk_flag()` en el futuro exige, por diseño, agregar su entrada
a `DEFAULT_RISK_SEVERITY` primero** — el sistema ya no permite omitir
esa decisión sin que el pipeline falle de inmediato y de forma
observable.

## Qué esta decisión NO aprueba

- **No aprueba `HAZMAT -> HIGH` ni `BULKY -> MEDIUM` como política
  comercial definitiva.** Ambos valores permanecen exactamente como
  estaban, sin cambio de código, y siguen marcados **provisionales /
  sin aprobación de negocio** (ADR-010, sin modificar). Esta decisión
  es puramente técnica (cómo debe fallar el sistema ante un caso no
  mapeado), no una aprobación retroactiva de los valores existentes.
- **No decide la severidad de fallback "correcta"** (ej. `CRITICAL`
  como postura conservadora) — se descarta explícitamente cualquier
  valor de reemplazo, incluido uno conservador, porque seguiría siendo
  un valor de negocio no aprobado, solo que asumido en la dirección
  opuesta.
- ~~No implementa provenance independiente para `severity`~~ —
  **RESUELTO 2026-08-17 por ADR-020**
  (`RiskFlag.severity -> FieldValue[Severity]`, con
  `severity.status=INFERRED` para HAZMAT/BULKY en vez de heredar el
  `VERIFIED` de presence). Esta ADR-015 sigue igual de vigente sin
  modificarse — ADR-020 solo cierra el ítem que aquí quedaba diferido.
- **No modifica `RiskFlag`, `decision_engine.py`, `decision_score.py`,
  el esquema de Excel, ni ninguna columna** — el cambio vive
  enteramente dentro de `_build_risk_flag()` en
  `infrastructure/excel/importer.py`.

## Consecuencias

- Positivas: elimina el único fallback silencioso de valor de negocio
  encontrado en el repositorio (`src/juval` no contiene ningún otro
  patrón `.get(clave, valor_por_defecto)` equivalente, verificado por
  inspección); cualquier extensión futura que conecte un `RiskType`
  nuevo sin decidir su severidad falla de inmediato en vez de producir
  una decisión de negocio silenciosamente incorrecta; el error
  (`KeyError`) es determinista, reproducible, y no requiere lógica
  adicional para ser "observable" — es una excepción de Python estándar
  no capturada.
- Negativas: si en el futuro se conecta un `RiskType` nuevo sin agregar
  su severidad primero, el `import_excel()` completo falla para ese
  archivo (no solo esa fila) — es el comportamiento fail-closed
  deliberado, no un defecto; se acepta conscientemente a cambio de
  nunca decidir en silencio.
- Reversibilidad: alta — es una decisión de manejo de errores, aislada
  a una función; puede ajustarse (ej. degradar a nivel de fila en vez
  de abortar el archivo completo) sin tocar `domain/` ni
  `decision_engine.py`.

## Relacionado

`docs/adr/ADR-010-severidad-riesgo-provisional.md` (documenta los
valores HAZMAT/BULKY en sí, sin modificar por esta decisión),
`docs/adr/ADR-004-estados-verificacion.md` (principio de no inventar/
asumir valores), `docs/architecture/DECISION_ENGINE.md` §"Decisiones
pendientes específicas" (aprobación de negocio de HAZMAT/BULKY sigue
pendiente, sin relación con esta decisión técnica),
`src/juval/infrastructure/excel/importer.py::DEFAULT_RISK_SEVERITY`/
`_build_risk_flag`, `tests/integration/test_excel_importer.py`
(cobertura de este comportamiento).
