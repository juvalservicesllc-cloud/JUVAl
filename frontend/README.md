# JUVAl frontend

React + TypeScript + Vite PWA.

- `/` — dashboard with typed demo data.
- `/upload` — real `.xlsx` processing through FastAPI; CSV remains unsupported.
- `/products` — typed demo product/provenance rows; the historical global client is disconnected because backend records are run-scoped.
- `/runs` — typed demo execution history; `GET /api/v1/runs` exists, but the page remains disconnected until its historical DTO is reconciled with the backend contract.
- `/appearance` — local browser-only visual customization: presets, CSS tokens, logo, and background image.

Appearance has a persisted Light/Dark mode switch. It changes the structural palette while retaining the chosen accent and local logo/background assets.

Fixtures live only in `src/data/demo.ts` and are visibly marked `DEMO MODE`. The frontend never calculates profitability, risk, provenance, or sourcing decisions.

## Local development

```powershell
npm install
npm run dev
```

`VITE_API_BASE_URL` is the only public frontend connection variable. It contains the FastAPI base URL and never a secret.

Appearance preferences use browser `localStorage`; local logo/background assets are limited to PNG, JPEG, or WEBP at 400 KB each. Remote brand asset storage is intentionally deferred.

## Checks

```powershell
npm run lint
npm test
npm run build
npm run test:e2e
```

For the real API contract, CORS/local demo setup, provenance rules, and backend handoff, read [`../docs/FRONTEND_BACKEND_HANDOFF.md`](../docs/FRONTEND_BACKEND_HANDOFF.md).
