# domain

Modelo interno de dominio, independiente de Excel y de cualquier
framework de UI. Entidades reales (verificadas contra el código,
2026-08-16 — ver `docs/RECONCILIATION_REPORT.md`):

- `provenance.py` — `FieldValue[T]`, `Provenance`, `VerificationStatus`,
  `SourceType`, `combine_verification_status`.
- `product.py` — `Product`, `Identification`, `ProductInfo`,
  `Dimensions`, `Demand`, `Price`, `Competition`.
- `costs.py` — `CostInputs`, `FeeInputs`.
- `risk.py` — `RiskFlag`, `RiskProfile`, `RiskType`, `Severity`.
- `decision.py` — `Decision`, `Thresholds`, `DecisionInputs`,
  `DecisionReason`, `DecisionResult`.
- `identifiers.py` — validación de formato ASIN/UPC/EAN/GTIN.
- `units.py` — normalización de peso/longitud a unidad canónica.
- `issues.py` — `ProcessingIssue`, `IssueLevel`.
- `sourcing_record.py` — `SourcingRecord`, agregado raíz que compone los
  tipos de arriba sin duplicarlos (ADR-011).
- `execution_run.py` — `ExecutionRun`, `ExecutionStatus`, `hash_file`
  (estructura de auditoría/reproducibilidad; sin persistencia entre
  corridas, ver `docs/architecture/EXECUTION_MODEL.md`).

`CatalogRecord` **no existe** en este código — era el nombre conceptual
usado en el diseño original de Fase 0 (`ARCHITECTURE.md` §4.1); el
modelo real de sourcing es `Product`/`SourcingRecord` como se documenta
arriba. No reintroducir `CatalogRecord` como alias de ninguno de estos
tipos.

No debe importar librerías de Excel, HTTP, ni frameworks de interfaz.
Ver `docs/architecture/DATA_MODEL.md` y `docs/architecture/ARCHITECTURE.md` §4.
