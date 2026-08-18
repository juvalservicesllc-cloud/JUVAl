# JUVAl frontend

React + TypeScript + Vite PWA. The frontend is finalized for the current
approved backend contracts (analytics + server-side catalog pagination);
see [the full handoff](../docs/FRONTEND_BACKEND_HANDOFF.md) and
[`API_CONTRACT.md`](../docs/architecture/API_CONTRACT.md).

## Routes

| Route | State |
| --- | --- |
| `/` | REAL — Dashboard, driven entirely by `GET /api/v1/runs/{id}/analytics`: KPIs, decision distribution (donut/bar toggle), HazMat/Bulky risk, per-field provenance breakdown, profitability summaries, data quality. Never fetches `RecordOut[]` to build charts. |
| `/upload` | REAL XLSX processing through FastAPI; CSV remains unsupported (no backend contract for it) |
| `/products` | REAL, server-side catalog: pagination (`limit`/`offset`), search (debounced), decision filter, sorting — all query parameters sent to the backend, never re-derived in the browser |
| `/runs` | REAL persisted `RunSummaryOut` history |
| `/runs/:executionId` | REAL run detail: metadata, records (first 100), provenance, decision reasons, issues, download |
| `/appearance` | LOCAL REAL theme and branding settings (`localStorage`) |

Route-level code splitting: `/upload`, `/runs`, `/runs/:executionId` and
`/appearance` are lazy-loaded (`React.lazy`); `/` and `/products` stay eager
as the two primary surfaces. This nets a *smaller* initial bundle than
before this pass despite the new analytics/catalog code — see `Bundle` below.

The API deliberately has no global products endpoint. Product data is a
snapshot identified by `(execution_id, record_ref)`, so the Catalog is always
run-scoped. The UI never recalculates profitability, decision, or risk
values, and never derives a `RunAnalyticsOut` client-side — it renders
exactly what the backend aggregated, keeping `VERIFIED`, `INFERRED`,
`NOT_FOUND`, and `INVALID` visible beside every provenance-aware value
(never collapsed into a single score).

## Analytics contract (`GET /api/v1/runs/{id}/analytics`)

`src/api/analytics.ts` + `src/types.ts::RunAnalyticsOut`. Semantics the UI
must never violate:

- Only `VERIFIED` values participate in `profitability` numeric summaries;
  `INFERRED` stays visible in `provenance` but is excluded from summaries;
  `NOT_FOUND`/`INVALID` are excluded from both.
- A summary with `count: 0` renders every numeric field as `null` →
  displayed as `—`, never `0`. A real numeric `0` average (e.g. all-VERIFIED
  break-even) renders as `$0.00`, distinct from "no data".
- `decisions`/`risks.*.status`/`risks.*.severity`/`provenance.*` are
  `Record<string, number>` with dynamic keys — the UI never assumes only
  `BUY`/`REVIEW`/`PASS` (an `UNKNOWN` bucket may appear) and never assumes a
  fixed severity set.
- `data_quality.records_with_issues`/`total_issue_count` are the only
  data-quality numbers rendered; `records_without_issues` is a direct
  `max(0, total - with_issues)` count derivation, not a business formula.

## Catalog query contract (`GET /api/v1/runs/{id}/records`)

`src/api/records.ts`. Query parameters: `limit` (1–100), `offset` (≥0),
`search` (≤200 chars, debounced ~300ms in the UI), `decision`
(`BUY`/`REVIEW`/`PASS` — `ALL` in the UI omits the parameter; `UNKNOWN` is
never sent, the backend filter doesn't accept it), `sort`
(`record_ref`/`sku`/`decision`/`profit`/`roi`/`margin`), `direction`
(`asc`/`desc`). Changing search/decision/sort/direction/limit resets
`offset` to `0`. Every request carries an `AbortController` so a stale
in-flight response can never overwrite a newer one.

## Known blocked future features

These have no backend field/endpoint yet and must never be simulated:

- **Decision Score** = `DOMAIN_NOT_INTEGRATED` — `processing/decision_score.py`
  exists but the pipeline does not produce a score; no score is computed,
  displayed, or inferred in the frontend.
- **AI Analyst** = `NOT_IMPLEMENTED` — no provider, endpoint, or prompt
  service exists; no AI response is faked.
- **Identity / IdP** = `BLOCKED_PENDING_AMAZON_RESPONSE` — see ADR-021/022.
  No IdP is integrated; no login exists; the API is called unauthenticated
  in local development (`JUVAL_AUTH_MODE` unset on the backend).

## Local development

Start FastAPI from the repository root:

```powershell
$env:JUVAL_CORS_ORIGINS='http://127.0.0.1:5173'
$env:JUVAL_EXECUTION_STORE='sqlite'
$env:JUVAL_EXECUTION_DB_PATH='./local_runs.db'
.venv\Scripts\python -m uvicorn juval.interfaces.api.main:app --host 127.0.0.1 --port 8000
```

`JUVAL_EXECUTION_STORE`/`JUVAL_EXECUTION_DB_PATH` are optional for `/upload`
alone, but required for `/`, `/products`, `/runs` and `/runs/:id` to work
(they all read persisted runs) — without them those routes show a safe
"store not configured" error, not a crash. `JUVAL_AUTH_MODE` is intentionally
left unset locally (`disabled`); see `docs/adr/ADR-022`.

Start Vite:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`. The public frontend API variable is
`VITE_API_BASE_URL` (`.env.local`); it must never contain a secret.

Appearance preferences use browser `localStorage`. Local logo/background
assets are PNG, JPEG, or WEBP and limited to 400 KB each.

## Checks

```powershell
npm test -- --run
npm run lint
npm run build
npm run test:e2e
```

`npm run test:e2e` requires both servers above already running (it does not
start them) — see `e2e/README.md`.
