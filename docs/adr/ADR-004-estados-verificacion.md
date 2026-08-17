# ADR-004: Estados VERIFIED / INFERRED / NOT_FOUND / INVALID

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

El proyecto exige distinguir explícitamente si un dato sensible fue
verificado, inferido, no encontrado, o encontrado pero inválido — y exige
que estos estados **nunca se confundan entre sí** ni se pierdan
silenciosamente (una inferencia no puede pasar por verificada; un dato no
encontrado no puede convertirse en un valor supuesto).

## Decisión

Se define un enum cerrado y mutuamente excluyente `VerificationStatus`:

- **`VERIFIED`**: el valor proviene de una fuente considerada confiable
  para ese campo (ej. el propio Excel de entrada para un campo que el
  usuario declara directamente, o una fuente externa autorizada).
- **`INFERRED`**: el valor se obtuvo aplicando una regla o heurística
  (ej. "si la categoría contiene X, hazmat=true"). Siempre debe incluir
  `method` describiendo la regla usada.
- **`NOT_FOUND`**: no hay evidencia suficiente. `value` es obligatoriamente
  `None`. No es un error del sistema, es un resultado legítimo que debe
  propagarse tal cual hasta el resultado final.
- **`INVALID`**: se encontró un valor pero no pasa validación de formato o
  de rango. El valor crudo se conserva por separado (`raw_value`) para
  diagnóstico; `value` normalizado es `None`.

Al ser un único campo enum (no varios booleanos independientes como
`is_verified`/`is_inferred`), es estructuralmente imposible que un mismo
`FieldValue` sea `VERIFIED` e `INFERRED` a la vez, o que un valor
`NOT_FOUND` cargue un `value` no nulo.

Cualquier transición de estado (ej. de `NOT_FOUND` a `INFERRED` tras
aplicar una regla) crea una decisión explícita en el Processing Core; no
ocurre implícitamente en el Importador ni en el Exportador.

## Consecuencias

- Positivas: contrato claro y verificable por tests; el estado de cada
  campo es auto-explicativo sin tener que leer código de negocio.
- Negativas: obliga a que toda regla de enriquecimiento declare
  explícitamente en qué estado deja el campo, incluso cuando "no encontró
  nada" (no se puede simplemente no setear el campo).
- Reversibilidad: baja para el conjunto de estados en sí (es la base de
  todo el sistema de trazabilidad), pero está abierto a que agreguen
  matices adicionales en el futuro si el negocio lo requiere (ej. un
  `INFERRED` de baja vs. alta confianza), siempre sin permitir que
  colapsen a `VERIFIED`.
