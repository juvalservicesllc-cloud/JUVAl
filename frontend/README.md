# JUVAl frontend

React + TypeScript + Vite PWA. Routes:

- `/` — dashboard summary and recent runs (typed demo data)
- `/upload` — real `.xlsx` processing; `.csv` is visibly pending backend support
- `/products` — product/provenance table (typed demo data)
- `/runs` — execution history (typed demo data)

Demo fixtures live only in `src/data/demo.ts` and are labelled `DEMO MODE` in the UI. The frontend never calculates profitability, risk, provenance, or sourcing decisions.

## Local development

```powershell
npm install
npm run dev
```

`VITE_API_BASE_URL` is a public backend URL, never a secret. See `.env.example`.

## Checks

```powershell
npm run lint
npm test
npm run build
npm run test:e2e
```

## Backend contract required

These are proposals, not implemented backend behavior:

- `GET /api/v1/dashboard` → `{ total_products, processable, excluded, hazmat, bulky, missing_asin, recent_runs }`.
- `GET /api/v1/products` → `{ items: ProductRow[], total }`. Every sensitive value must retain `VERIFIED | INFERRED | NOT_FOUND | INVALID`; pagination/filtering can wait for measured need.
- `GET /api/v1/runs` → `{ items: ExecutionRunSummary[] }`, with `execution_id`, `created_at`, `status`, `total_records`, `valid`, `excluded`, and `errors`.

Expected errors: `500` without internal paths or tracebacks. Authentication remains out of scope. CSV processing additionally requires extending `POST /api/v1/runs` to accept `.csv` or a separate documented endpoint.
