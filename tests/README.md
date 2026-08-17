# tests

- `unit/` — Processing Core en aislamiento, sin I/O.
- `integration/` — importación/exportación Excel y pipeline completo.
- `fixtures/` — archivos Excel de prueba (casos válidos, columnas
  faltantes, tipos inválidos, mezcla de estados de verificación).

Ver `docs/architecture/ARCHITECTURE.md` §9. Ningún test debe ocultar un
error para "pasar" — debe afirmar que el error se reportó correctamente.
