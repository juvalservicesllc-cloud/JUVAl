# ADR-003: Estructura de provenance para datos sensibles

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

ASIN, peso, hazmat y bulky influyen directamente en decisiones comerciales
(costos de envío, elegibilidad de venta, cumplimiento regulatorio). Si el
sistema guarda estos campos como valores simples (`str`, `float`, `bool`),
se pierde para siempre la información de si el dato vino directo del
Excel del usuario, de una fuente externa verificada, o de una regla de
inferencia — y esa distinción es exactamente lo que el proyecto pide
preservar.

## Decisión

Todo campo sensible se representa con un envoltorio `FieldValue[T]` que
incluye: `value`, `unit` (cuando aplica), `status`, `source`, `method`,
`retrieved_at`, `evidence` (opcional), `confidence` (opcional). El detalle
completo de estos campos está en `docs/architecture/ARCHITECTURE.md` §5.

Ningún campo sensible se almacena ni se serializa fuera de este envoltorio
en ningún punto del pipeline (import → processing → export). El Excel de
salida expone las columnas de provenance relevantes (al menos `status` y
`source`) junto al valor, no solo el valor final.

## Consecuencias

- Positivas: cualquier valor de ASIN/peso/hazmat/bulky en el resultado
  final puede explicarse sin tener que rastrear logs externos; permite
  auditoría posterior y detectar si una fuente externa empezó a fallar o a
  degradar calidad.
- Negativas: más verboso que guardar valores simples; el modelo de datos y
  el exportador de Excel son más complejos que un mapeo 1:1 columna-campo.
- Reversibilidad: baja una vez que haya datos reales acumulados con este
  formato (cambiarlo después implicaría migrar historial), pero el diseño
  en sí (usar un envoltorio) es estándar y de bajo riesgo técnico.

## Relacionado

Ver ADR-004 para la definición cerrada de los valores posibles de `status`.
