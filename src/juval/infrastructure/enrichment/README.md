# infrastructure/enrichment

Adapters a fuentes externas de verificación (ASIN, peso, hazmat, bulky).
Vacío por ahora — no se implementa scraping ni integraciones externas
hasta que haya una fuente concreta definida (ver decisión pendiente #2 en
`docs/architecture/ARCHITECTURE.md` §14). Cada adapter debe producir
`FieldValue` con `status=VERIFIED` solo si la fuente es confiable para ese
campo; de lo contrario `INFERRED` o `NOT_FOUND`, nunca un valor supuesto.
