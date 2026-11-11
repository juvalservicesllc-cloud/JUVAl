# infrastructure/enrichment

Adapters a fuentes externas de verificación (ASIN, peso, hazmat, bulky).
`connector.py` contiene solo la maquinaria reutilizable de ADR-057/ADR-058:
contrato autorizado (D3.2/D3.3), transporte inyectable, validación estricta,
clasificación de errores y reintentos acotados. **No hay ningún adapter de
proveedor ni transporte HTTP real.** No se implementa scraping ni
integraciones externas hasta que haya una fuente concreta autorizada (ver
decisión pendiente #2 en `docs/architecture/ARCHITECTURE.md` §14). Cada adapter debe producir
`FieldValue` con `status=VERIFIED` solo si la fuente es confiable para ese
campo; de lo contrario `INFERRED` o `NOT_FOUND`, nunca un valor supuesto.
