# E2E smoke test

One happy-path test (`smoke.spec.ts`, Fase 4B brief §12/§28): upload the
real Excel fixture -> real FastAPI backend -> real Core -> results shown
with provenance preserved -> real download. No mocks.

Requires both servers running first (this test does not start them):

```bash
# terminal 1 -- backend
PYTHONPATH=src .venv/Scripts/python -m uvicorn juval.interfaces.api.main:app \
  --host 127.0.0.1 --port 8000
# set JUVAL_CORS_ORIGINS=http://127.0.0.1:5173 (or http://localhost:5173,
# matching whichever host `npm run dev` binds to) so the browser isn't
# rejected by CORS -- see docs/architecture/API_CONTRACT.md §7.

# terminal 2 -- frontend
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
# .env.local: VITE_API_BASE_URL=http://127.0.0.1:8000

# terminal 3
cd frontend && npm run test:e2e
```

Verified 2026-08-17 against the real stack (see
`docs/PROJECT_STATUS.md` §Sesión 2026-08-17, bloque 4): 1/1 passing.
