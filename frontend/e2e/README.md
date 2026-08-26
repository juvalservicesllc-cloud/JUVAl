# E2E suite

`smoke.spec.ts` (Fase 4B brief §12/§28): upload the real Excel fixture ->
real FastAPI backend -> real Core -> results shown with provenance
preserved -> real download. No mocks. `runs.spec.ts` is a responsive/routing
check for `/runs` (GET /api/v1/runs, real API since ADR-019) -- it does not
require persisted data. `dashboard-analytics.spec.ts` covers the real
`GET /analytics`-driven Dashboard (KPIs, decision chart toggle, risk,
provenance, profitability). `products.spec.ts` covers the responsive
catalog shell plus a real server-side search/filter query against
`GET /records`. `runs-persistence.spec.ts` covers the full
Upload -> Runs -> Run Detail -> refresh -> download slice.
`recovery.spec.ts` covers the Waves B-D capabilities: real CSV ingestion,
percentage ROI semantics against the live query, a mixed CSV/XLSX batch with
durable `/batches/:id` navigation and Run Detail batch context, the internal
analytics panels, and the honest no-image media slot.

These specs share one backend/database across parallel Playwright workers
-- assertions must hold regardless of which run happens to be "latest" at
the moment they run (see the state-agnostic viewport checks in
`products.spec.ts` for the pattern), except where a spec waits for its own
just-created run explicitly.

Requires both servers running first (this test does not start them):

```bash
# terminal 1 -- backend
JUVAL_EXECUTION_STORE=sqlite JUVAL_EXECUTION_DB_PATH=./e2e_runs.db \
PYTHONPATH=src .venv/Scripts/python -m uvicorn juval.interfaces.api.main:app \
  --host 127.0.0.1 --port 8000
# JUVAL_EXECUTION_STORE/JUVAL_EXECUTION_DB_PATH are only needed so
# GET /api/v1/runs doesn't show its safe 500 "store not configured"
# error during /runs -- optional for smoke.spec.ts alone.
# set JUVAL_CORS_ORIGINS=http://127.0.0.1:5173 (or http://localhost:5173,
# matching whichever host `npm run dev` binds to) so the browser isn't
# rejected by CORS -- see docs/architecture/API_CONTRACT.md §7.

# terminal 2 -- frontend
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
# .env.local: VITE_API_BASE_URL=http://127.0.0.1:8000

# terminal 3
cd frontend && npm run test:e2e
```

Verified 2026-08-26 on Linux (`juval-server`) against the real stack on
isolated ports -- backend `http://127.0.0.1:8001` (fresh SQLite db,
`JUVAL_CORS_ORIGINS=http://127.0.0.1:5180`), frontend
`http://127.0.0.1:5180` (production `vite build` served by `npm run
preview`, `VITE_API_BASE_URL` pointed at the isolated backend) -- no
mocks: **27/27 passing**, same commit and count as the Windows baseline
below. This closes the Chromium system-library blocker recorded here
since 2026-08-24: the nine missing libraries
(`libatk-1.0.so.0`, `libatk-bridge-2.0.so.0`, `libXcomposite.so.1`,
`libXdamage.so.1`, `libXfixes.so.3`, `libXrandr.so.2`, `libgbm.so.1`,
`libasound.so.2`, `libatspi.so.0`) were installed via `sudo apt-get
install` (the user exposed the existing user-scoped nvm `PATH` to
`sudo` rather than installing a second Node distribution); `ldd` on both
`chrome` and `chrome-headless-shell` now resolves cleanly. See
`docs/DEVELOPMENT_ENVIRONMENT.md` §4 and
`docs/compliance/HOST_CONTROLS_JUVAL_SERVER.md` (H-13) for full evidence.
The isolated ports (8001/5180) were used instead of the pre-existing dev
servers already running on `0.0.0.0:5173`/`0.0.0.0:8000` so this result
can't be confused with that separate, still-running LAN-bound instance;
those processes and this run's own temporary processes/files were left
in their original state afterward.

Historical: verified 2026-08-24 against the real stack on the isolated port
`http://127.0.0.1:5180` (production `vite build` served by `npm run
preview`, real FastAPI, real SQLite -- no mocks): **27/27 passing**, on the
consolidated baseline that includes multi-file batches, CSV ingestion and
the locale-pinned formatting fix. Run on Windows; Chromium could not yet
start on `juval-server` at that time (system libraries missing, resolved
2026-08-26 above).
Historical: verified 2026-08-20 against the real stack on the isolated port
`http://127.0.0.1:5180` (R4 independent parity verification, production
`vite build` served by `npm run preview`, not the dev server): **27/27
passing**. Use 5180 rather than 5173 so a stale demo server on the default
port cannot be mistaken for production.
Historical: verified 2026-08-19 (Waves B-D product-capability
recovery): 27/27 passing. Historical: verified 2026-08-18 (Opus 5
frontend finalization pass -- server-side catalog + analytics dashboard):
20/20 passing.
Historical: verified 2026-08-17 against the real stack (see
`docs/PROJECT_STATUS.md` §Sesión 2026-08-17, bloque 4): 1/1 passing.
