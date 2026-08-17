# ADR-005: Arquitectura independiente de la decisión PWA vs. `.exe`

- Estado: Aceptada (decisión de *diseño*; la elección final PWA/.exe/ambos
  queda pendiente — ver `ARCHITECTURE.md` §10 y §14)
- Fecha: 2026-08-16

## Contexto

Todavía no hay suficiente información de uso real (¿una persona operando
localmente, o varias personas necesitando acceso compartido?) para elegir
entre una PWA, una aplicación Windows `.exe`, o ambas. Fijar esta decisión
ahora, sin datos, sería prematuro; pero tampoco se puede posponer
indefinidamente el diseño del resto del sistema esperando esa respuesta.

## Decisión

En vez de decidir PWA vs. `.exe` ahora, se diseña el sistema (ADR-001) de
forma que esa elección quede confinada a la capa de Interfaces, sin tocar
Application Layer, Processing Core, Domain ni Infrastructure:

- Un backend API (ej. FastAPI) detrás de una PWA y un wrapper de escritorio
  empaquetado como `.exe` (ej. vía PyInstaller) serían ambos clientes del
  mismo Application Layer.
- Ninguna decisión de dominio (validación, provenance, clasificación)
  depende de si el proceso corre en un navegador o en un ejecutable local.
- El acceso a filesystem local (para leer/escribir Excel) se modela como
  un puerto de Infrastructure, no como una asunción de "hay un navegador"
  o "hay un sistema de archivos local sin restricciones".

Esto permite implementar primero la interfaz más simple de validar el
Core end-to-end (ver recomendación de CLI en `ARCHITECTURE.md` §15) sin
comprometerse a PWA o `.exe`, y decidir con más información más adelante.

## Consecuencias

- Positivas: cero costo de cambiar de opinión sobre PWA/.exe más adelante;
  permite avanzar en la Fase 1 (vertical slice) sin bloquear en esta
  decisión de producto.
- Negativas: ninguna interfaz de usuario real existe todavía; el sistema
  no es "usable" por una persona no técnica hasta que se implemente al
  menos una interfaz.
- Reversibilidad: la decisión de *no decidir todavía* es, por diseño, de
  bajo riesgo — es justamente lo que este ADR previene tener que revertir.
