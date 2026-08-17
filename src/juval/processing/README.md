# processing

Processing Core: validación, enriquecimiento y clasificación sobre el
modelo de dominio (`domain/`). Reglas puras y testeables sin I/O — no lee
archivos, no llama a APIs externas directamente (usa puertos definidos
hacia `infrastructure/`), no conoce Excel ni ninguna interfaz de usuario.

Ver `docs/architecture/ARCHITECTURE.md` §3 y §7.
