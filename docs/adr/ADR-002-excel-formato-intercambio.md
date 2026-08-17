# ADR-002: Excel como formato de intercambio, no como modelo de dominio

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

La entrada y (probablemente) la salida del sistema serán archivos Excel,
porque es el formato con el que el negocio ya trabaja. Existe el riesgo
natural de que, por conveniencia, las reglas de negocio terminen operando
directamente sobre filas/celdas de Excel (por posición de columna, por
tipos de celda de `openpyxl`, etc.), acoplando el Core a un formato de
archivo concreto.

## Decisión

Excel se trata como **formato de intercambio**: existe una capa
`infrastructure/excel/` con un Importador y un Exportador. El Importador
traduce filas de Excel a un modelo interno (`CatalogRecord`, con campos
`FieldValue`) identificando columnas **por nombre de encabezado**, nunca
por posición. El Exportador hace la traducción inversa. El Processing
Core y la Application Layer nunca importan una librería de Excel ni saben
que existen "columnas" — solo conocen el modelo de dominio.

Si en el futuro se necesita otra fuente de entrada (CSV, API, base de
datos), solo se añade otro Importador que produzca el mismo modelo
interno; el Core no cambia.

## Consecuencias

- Positivas: el negocio no queda atado al layout exacto de un Excel
  (reordenar columnas no rompe nada); es posible agregar otros formatos de
  entrada/salida sin tocar reglas; el Core se testea con datos en memoria,
  sin necesidad de generar archivos `.xlsx` para cada test unitario.
- Negativas: exige mantener explícitamente un mapeo columna↔campo y validar
  columnas requeridas, en vez de leer "lo que venga".
- Reversibilidad: alta, es una decisión de aislamiento, no compromete
  ninguna otra parte del sistema si cambiara el formato de intercambio.
