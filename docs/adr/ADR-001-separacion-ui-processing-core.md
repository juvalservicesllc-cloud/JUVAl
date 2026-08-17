# ADR-001: Separación entre UI y Processing Core

- Estado: Aceptada
- Fecha: 2026-08-16

## Contexto

Juval eventualmente necesitará más de una forma de interactuar con el
sistema: una interfaz web/PWA, una aplicación de escritorio Windows
(`.exe`), y posiblemente un CLI para automatización. Si la lógica de
negocio (validación, enriquecimiento, clasificación) se escribe dentro de
la interfaz elegida primero, cada interfaz nueva obligaría a reimplementar
o duplicar esa lógica, con el riesgo de que diverjan silenciosamente (por
ejemplo, que el CLI clasifique hazmat distinto que la PWA).

## Decisión

La lógica de negocio vive exclusivamente en el **Processing Core** y la
**Application Layer**, que no importan ni conocen ningún framework de UI
(web, desktop, CLI). Las interfaces son clientes delgados del Application
Layer: reciben input, lo traducen a una llamada de caso de uso, y
presentan el resultado. Ninguna interfaz contiene reglas de validación,
enriquecimiento o clasificación.

La comunicación Interfaz → Application Layer se hace a través de una API
de casos de uso (funciones/clases explícitas, ej. `ProcessCatalogBatch`),
no a través de acceso directo a estructuras internas del Core.

## Consecuencias

- Positivas: una PWA y un `.exe` pueden coexistir compartiendo el mismo
  comportamiento garantizado; el Core es testeable sin levantar ninguna UI;
  agregar una interfaz nueva no implica tocar reglas de negocio.
- Negativas: una capa de indirección adicional respecto a escribir todo
  junto en un script; para el MVP esto es aceptable dado que la prioridad
  del proyecto es correctitud y trazabilidad por encima de velocidad de
  desarrollo inicial.
- Reversibilidad: alta. Si en el futuro se decide que solo existirá una
  interfaz para siempre, esta separación se puede relajar sin rediseñar el
  modelo de dominio.
