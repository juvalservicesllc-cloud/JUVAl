# application

Application Layer: orquesta casos de uso completos (ej.
`ProcessCatalogBatch`, `ExportResults`) coordinando `domain/`,
`processing/` e `infrastructure/`. No conoce detalles de Excel (nombres de
columnas) ni de la interfaz que la invoca (CLI/API/desktop).

Ver `docs/architecture/ARCHITECTURE.md` §3 (ADR-001).
