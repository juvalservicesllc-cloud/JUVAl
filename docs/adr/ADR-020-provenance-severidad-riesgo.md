# ADR-020: Provenance independiente para severidad de riesgo (presence vs severity)

- Estado: Aceptada — cierra el ítem que ADR-015 dejó explícitamente
  diferido ("No implementa provenance independiente para `severity`
  ... queda explícitamente diferida como mejora futura separada, sin
  ADR propio todavía"), a petición explícita del usuario 2026-08-17.
- Fecha: 2026-08-17

## Contexto

`RiskFlag` (`domain/risk.py`) tenía un único `verification_status` para
todo el flag. Para HAZMAT/BULKY, `infrastructure/excel/importer.py::_build_risk_flag`
construía cada `RiskFlag` así cuando el proveedor declaraba el riesgo
presente:

```python
RiskFlag(
    status=RiskStatus.PRESENT, verification_status=VerificationStatus.VERIFIED,
    severity=DEFAULT_RISK_SEVERITY[risk_type], ...
)
```

Esto mezclaba dos afirmaciones de naturaleza distinta bajo un solo
`VERIFIED`:

1. **Presence**: el proveedor declaró `hazmat=TRUE` en el Excel — esto
   sí está `VERIFIED` (se leyó literalmente del archivo).
2. **Severity**: `HAZMAT -> HIGH` viene de `DEFAULT_RISK_SEVERITY`
   (ADR-010), una tabla de clasificación **interna de Juval**,
   explícitamente marcada "provisional / no aprobada por negocio". Que
   el proveedor haya verificado la presencia del riesgo no significa
   que haya verificado — ni podría verificar — que la clasificación de
   severidad de Juval sea correcta.

Al no distinguirse, `RiskFlag.verification_status=VERIFIED` presentaba
implícitamente la severidad como si tuviera la misma certeza que la
presencia — exactamente el patrón que ADR-003/ADR-004 prohíben
("nunca presentar INFERRED como VERIFIED").

**Verificado en el código actual, no asumido**: el fallback silencioso
de `DEFAULT_RISK_SEVERITY.get(risk_type, Severity.MEDIUM)` que motivó
ADR-015 ya estaba resuelto (`DEFAULT_RISK_SEVERITY[risk_type]`,
`KeyError` fail-closed, sin cambios en esta ADR). HAZMAT→HIGH y
BULKY→MEDIUM siguen exactamente igual que en ADR-010 — **esta ADR no
cambia esos valores ni los aprueba comercialmente**.

## Decisión

`RiskFlag.severity` pasa de `Severity` (enum pelado) a
`FieldValue[Severity]` (`domain/provenance.py`, ya existente — no se
duplica su estructura). Dos ejes de provenance, nunca confundidos:

```
RiskFlag.status / verification_status / source / timestamp / evidence
    -> PRESENCE: ¿existe este riesgo? ¿qué tan seguros estamos?

RiskFlag.severity: FieldValue[Severity]
    -> SEVERITY: ¿qué tan severo es? ¿de dónde salió esa clasificación?
```

Reglas de construcción (`_build_risk_flag`, sin cambiar la firma
pública ni el flujo del importer):

| Caso | `status` | `verification_status` (presence) | `severity.value` | `severity.status` |
|---|---|---|---|---|
| Celda `TRUE` | PRESENT | VERIFIED | `DEFAULT_RISK_SEVERITY[risk_type]` | **INFERRED** — regla/heurística interna, nunca VERIFIED |
| Celda `FALSE` | ABSENT | VERIFIED | `Severity.NONE` | VERIFIED — consecuencia lógica cierta de una ausencia verificada, no una política |
| Celda vacía | UNKNOWN | NOT_FOUND | `None` | NOT_FOUND — si la presencia no se conoce, la severidad tampoco es evaluable |
| Booleano inválido | UNKNOWN | INVALID | `None` | INVALID (con `raw_value` preservado) |

`severity.source`/`severity.method` para el caso PRESENT quedan
explícitos: `source="DEFAULT_RISK_SEVERITY"`,
`method="ADR-010 provisional internal severity classification (not
business-approved)"`, `source_type=SourceType.CALCULATED` (mismo
`SourceType` que ya usan profit/ROI/margin — una clasificación
determinística calculada por Juval, no leída de una fuente externa).

**Nuevo invariante** en `RiskFlag.__post_init__`: un flag `PRESENT`
debe tener `severity.value` no-`None` (simétrico al invariante ya
existente "un flag `ABSENT` debe tener severity `NONE`").

## Qué NO resuelve esta decisión

- **No cambia `HAZMAT -> HIGH` ni `BULKY -> MEDIUM`.** Siguen
  exactamente igual, siguen provisionales, sin aprobación de negocio
  (ADR-010, sin modificar).
- **No expone la nueva provenance de severidad vía la API todavía.**
  `interfaces/api/models.py::RecordOut.hazmat_severity`/`bulky_severity`
  y el export Excel (`hazmat_severity`/`bulky_severity` columnas)
  siguen siendo exactamente el mismo string plano que ya eran —
  `application/record_snapshot.py`/`infrastructure/excel/exporter.py`
  desenvuelven `severity.value.value` para no cambiar el contrato que
  Codex ya consume (`API_CONTRACT.md` sin cambios, `RecordOut` sin
  cambios). Si en el futuro aparece un consumidor real que necesite
  saber que la severidad es `INFERRED`/policy-derived (ej. una columna
  "severity confidence" en el frontend), exponerla es un cambio
  aditivo pequeño (`hazmat_severity_status` nuevo, no modificar el
  campo existente) — no se construye especulativamente ahora (mismo
  criterio que ya aplicó ADR-013 al listado de runs).
- **No modifica `decision_engine.py` en su lógica de negocio** — sigue
  comparando `Severity` contra `Thresholds.maximum_risk_severity`
  exactamente igual; solo cambia cómo se llega al valor
  (`flag.severity.value` en vez de `flag.severity`).
- **No reabre el fallback fail-closed de ADR-015** — sigue exactamente
  igual (`DEFAULT_RISK_SEVERITY[risk_type]`, `KeyError` si no está
  mapeado).

## Alternativas consideradas

1. **Campo nuevo `severity_source: SourceType` junto a `severity: Severity` sin FieldValue**:
   descartado — habría duplicado parcialmente lo que `FieldValue` ya
   resuelve (value+status+source+method+retrieved_at juntos), en vez
   de reutilizarlo; el proyecto ya usa `FieldValue[Enum]` para el
   mismo propósito en otro lugar (`Dimensions.size_type: Optional[FieldValue[SizeType]]`).
2. **Dejar `RiskFlag.verification_status` cubriendo ambos ejes,
   documentando la ambigüedad solo en comentarios**: descartado — un
   comentario no impide que un consumidor futuro lea
   `verification_status=VERIFIED` y asuma que la severidad también lo
   está; el problema es estructural, la solución debe serlo también.
3. **Mover la severidad fuera de `RiskFlag` a una estructura paralela**:
   descartado — `severity` sigue siendo un atributo de "este riesgo
   específico", no tiene sentido como entidad separada; `FieldValue`
   ya resuelve el problema sin reestructurar el modelo.

## Impacto

Archivos tocados (todos dentro de dominio/infraestructura/tests, cero
cambios de `run_pipeline.py`, cero cambios de reglas comerciales,
cero cambios de `frontend/`):

- `domain/risk.py` — `RiskFlag.severity: FieldValue[Severity]`, nuevo
  invariante PRESENT, `RiskProfile.highest_severity` ajustado.
- `infrastructure/excel/importer.py::_build_risk_flag` — construye
  `FieldValue.inferred/.verified/.not_found/.invalid` según el caso
  (tabla arriba).
- `processing/decision_engine.py::rule_pass_disqualifying_risk` —
  desenvuelve `flag.severity.value` antes de comparar rangos; el
  resultado de la regla (BUY/REVIEW/PASS) es idéntico para todos los
  casos ya cubiertos por tests.
- `infrastructure/excel/exporter.py`, `application/record_snapshot.py`
  — helper `_severity_value()` (duplicado intencionalmente pequeño en
  cada capa, dos líneas, no vale una dependencia cruzada entre
  infraestructura y aplicación por esto) que desenvuelve el string
  plano sin cambiar la forma de las columnas/campos existentes.
- Tests: `tests/unit/test_risk.py`, `test_decision_engine.py`,
  `test_sourcing_record.py`, `tests/integration/test_excel_exporter.py`,
  `test_excel_importer.py` (adaptados a la nueva forma), más
  `tests/unit/test_record_snapshot.py` (nuevo) y 3 tests nuevos en
  `test_excel_importer.py` que verifican explícitamente la separación
  presence/severity.

## Consecuencias

- Positivas: cierra la brecha que ADR-015 dejó nombrada; la severidad
  de HAZMAT/BULKY ya no se presenta como más cierta de lo que es;
  reutiliza `FieldValue` existente, sin duplicar su estructura; el
  invariante nuevo (`PRESENT` requiere severidad no-`None`) atrapa en
  desarrollo cualquier construcción incorrecta de `RiskFlag`.
- Negativas: cualquier código que construya `RiskFlag` directamente
  (tests, y en el futuro un adapter de enriquecimiento externo) debe
  envolver `severity` en un `FieldValue` — no es un cambio silencioso,
  Python no fuerza el tipo en runtime, pero un `RiskFlag` mal
  construido falla rápido en el primer punto que llame `.severity.value`.
- Reversibilidad: alta — `FieldValue[Severity]` puede revertirse a
  `Severity` pelado sin tocar `domain/provenance.py` ni ningún otro
  modelo; es un cambio de forma de un solo campo.

## Relacionado

ADR-003, ADR-004 (principio "nunca INFERRED como VERIFIED"), ADR-010
(valores HAZMAT/BULKY, sin cambiar), ADR-015 (fallback fail-closed, sin
cambiar, este ADR cierra su ítem diferido), `domain/risk.py`,
`domain/provenance.py::FieldValue`,
`infrastructure/excel/importer.py::_build_risk_flag`,
`docs/architecture/DATA_PROVENANCE.md`.
