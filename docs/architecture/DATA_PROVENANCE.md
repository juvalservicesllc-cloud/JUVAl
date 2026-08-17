# Juval — Data Provenance (Fase 1)

Normativo para cómo Juval responde "¿de dónde salió este dato?" en
cualquier punto del sistema. Implementado en `domain/provenance.py`
(`Provenance`, `FieldValue`, `VerificationStatus`, `SourceType`,
`combine_verification_status`) — ver también ADR-003/ADR-004 (Fase 0) de
los que esto es la continuación directa, y `DATA_SOURCES.md` para la
taxonomía de `SourceType`.

## 1. Estructura (requisito §15)

Todo dato importante es un `FieldValue[T]`:

| Campo | Presente cuando | Descripción |
|---|---|---|
| `value` | siempre (puede ser `None`) | el dato tipado |
| `unit` | cuando aplica (peso, dimensiones) | unidad canónica — ver `domain/units.py` |
| `raw_value` | `status == INVALID` | valor crudo preservado para diagnóstico |
| `provenance.source` | siempre | identificador de la fuente concreta |
| `provenance.source_type` | siempre | categoría de la fuente (`DATA_SOURCES.md`) |
| `provenance.verification_status` | siempre | VERIFIED / INFERRED / NOT_FOUND / INVALID |
| `provenance.retrieved_at` | siempre, tz-aware | instante de obtención |
| `provenance.method` | siempre | cómo se obtuvo (regla, lectura directa, endpoint) |
| `provenance.confidence` | opcional, `[0,1]` | nunca sustituye a `verification_status` |
| `provenance.evidence` | opcional | texto/URL que respalda el valor |
| `provenance.source_reference` | opcional | ID de consulta/fila/documento para auditoría |

## 2. Por qué value y provenance nunca se separan

`FieldValue` es el único punto de entrada para construir un dato sensible
(`FieldValue.verified/.inferred/.not_found/.invalid` — no hay forma de
crear un valor "pelado"). Cualquier función que reciba o devuelva un ASIN,
peso, HazMat, precio, BSR, etc. en el código de Juval lo hace como
`FieldValue`, nunca como `str`/`Decimal`/`bool` suelto — así que el código
no puede "olvidarse" de la procedencia a mitad de un pipeline.

## 3. Campos calculados: la regla del eslabón más débil

Un campo `CALCULATED` (profit, ROI, margin, break-even, decision score...)
no puede ser más certero que sus insumos. `combine_verification_status`
formaliza esto:

```
NOT_FOUND o INVALID en cualquier insumo  → resultado NOT_FOUND
(ningún insumo missing) y algún INFERRED → resultado INFERRED
todos VERIFIED                            → resultado VERIFIED
```

Ejemplo real en `processing/profitability.py`: si `selling_price` es
`NOT_FOUND`, `profit`/`roi`/`margin`/`break_even_price` son todos
`NOT_FOUND` también — el motor nunca calcula "como si" el precio fuera 0
o cualquier otro valor por defecto.

## 4. Freshness (frescura)

No hay un campo `freshness` separado en `FieldValue` — se deriva de
`retrieved_at` en el momento de la consulta (`processing/data_quality.py
::validate_freshness`, comparado contra `DataQualityConfig.max_data_age`,
configurable). Esto evita que un timestamp "de frescura" divergiera de
`retrieved_at` con el tiempo.

## 5. Confidence vs. verification_status

`confidence` (0-1) es informativo y opcional — típicamente presente en
campos `INFERRED` que vienen de un modelo estadístico externo (ej.
estimación de ventas). **Nunca** se usa para decidir si algo es `VERIFIED`;
esa es una decisión binaria de estado, no de umbral de confianza. Un valor
con `confidence=0.99` sigue siendo `INFERRED` si su método es una
inferencia, nunca se "asciende" automáticamente a `VERIFIED`.

## 6. Ejemplo de trazabilidad completa

```
FieldValue(
  value=Decimal("2.4"),
  unit="lb",
  raw_value=None,
  provenance=Provenance(
    source="supplier_catalog_2026_08.xlsx",
    source_type=SourceType.SUPPLIER_FILE,
    verification_status=VerificationStatus.VERIFIED,
    retrieved_at=2026-08-10T14:03:00Z,
    method="direct_read",
    confidence=None,
    evidence=None,
    source_reference="row=482",
  ),
)
```

Cualquier consumidor (Decision Engine, exportador Excel, AI Analyst) puede
responder "¿de dónde salió este peso?" sin tocar ningún log externo.

## 7. Decisiones pendientes

1. ¿Se persiste el historial completo de `FieldValue`s por campo a través
   del tiempo (para ver cómo cambió un precio corrida a corrida), o solo
   el último valor por `ExecutionRun`? (relacionado con Fase 0 §14.5).
2. Formato exacto de `source_reference` por tipo de fuente (fila de Excel,
   ID de consulta de API, ...) — hoy es un `str` libre.
3. Política de retención de `evidence` cuando es un payload grande (ej. un
   snapshot JSON completo de una respuesta de API).
