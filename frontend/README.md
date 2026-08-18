# JUVAl frontend

React + TypeScript + Vite PWA. The current MVP frontend is ready for backend API integration; see [the full handoff](../docs/FRONTEND_BACKEND_HANDOFF.md).

## Current view state

| Route | State |
| --- | --- |
| `/` | REAL persisted-run analytics; empty/error states when the API has no history or is unavailable |
| `/upload` | REAL XLSX processing through FastAPI; CSV remains unsupported |
| `/products` | REAL run-scoped record catalog with search, decision filter, sorting, and explicit provenance |
| `/runs` | REAL persisted `RunSummaryOut` history and run detail/download |
| `/appearance` | LOCAL REAL theme and branding settings |

The API deliberately has no global products endpoint. Product data is a
snapshot identified by `(execution_id, record_ref)`, so the Catalog is always
run-scoped. The UI never recalculates profitability, decision, or risk values;
it renders the backend result and keeps `VERIFIED`, `INFERRED`, `NOT_FOUND`,
and `INVALID` visible beside provenance-aware values.

Decision Score and AI Analyst have no API fields/endpoints yet, so neither is
presented as a production capability. Authentication remains provider-neutral
at the frontend boundary; no IdP integration or browser secret is included.

## Local development

Start FastAPI from the repository root:

```powershell
$env:JUVAL_CORS_ORIGINS='http://127.0.0.1:5173'
.venv\Scripts\python -m uvicorn juval.interfaces.api.main:app --host 127.0.0.1 --port 8000
```

Start Vite:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`. The public frontend API variable is `VITE_API_BASE_URL`; it must never contain a secret.

Appearance preferences use browser `localStorage`. Local logo/background assets are PNG, JPEG, or WEBP and limited to 400 KB each.

## Checks

```powershell
npm test -- --run
npm run lint
npm run build
npm run test:e2e
```
