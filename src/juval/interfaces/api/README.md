# interfaces/api

Backend de la PWA (ADR-014, PWA elegida; ADR-016, FastAPI elegido).
**IMPLEMENTADO** (Fase 4A, 2026-08-17): `main.py` (endpoints),
`models.py` (contrato HTTP, Pydantic), `service.py` (traducción
HTTP↔Core, sin lógica de negocio). Cliente delgado de `application/`
(ADR-001) — no calcula profit/ROI/margin/score/decisión/severidad.

```bash
PYTHONPATH=src .venv/Scripts/python -m uvicorn juval.interfaces.api.main:app --reload
```

Contrato completo: `docs/architecture/API_CONTRACT.md`. Decisión y
comparación de framework: `docs/adr/ADR-016-backend-fastapi.md`. 19
tests de integración: `tests/integration/test_api.py`.

Persistencia de `ExecutionRun`: opt-in vía `persist=true` en el request
(`JUVAL_EXECUTION_DB_PATH`, SQLite/ADR-013 local, o
`SupabaseExecutionRunStore`/ADR-017 en producción — no cableada
automáticamente todavía, ver `docs/architecture/SUPABASE.md` §6).

Fuera de alcance de Fase 4A (pendiente de Fase 4B o posterior):
frontend React+Vite, deployment a Vercel, autenticación.
