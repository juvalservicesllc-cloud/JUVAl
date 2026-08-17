# JUVAl frontend

React + TypeScript + Vite PWA. The current MVP frontend is ready for backend API integration; see [the full handoff](../docs/FRONTEND_BACKEND_HANDOFF.md).

## Current view state

| Route | State |
| --- | --- |
| `/` | DEMO dashboard fixtures |
| `/upload` | REAL XLSX processing through FastAPI; CSV remains unsupported |
| `/products` | DEMO / API-ready; awaits run-scoped records reconciliation |
| `/runs` | DEMO / API-ready; awaits `RunSummaryOut` DTO reconciliation |
| `/appearance` | LOCAL REAL theme and branding settings |

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
