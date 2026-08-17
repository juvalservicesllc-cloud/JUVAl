# JUVAl — Frontend → Backend Handoff

## 1. Purpose

This is the operational handoff for the actual PWA state and its HTTP boundary. It separates implemented code from historical frontend proposals.

- **Codex:** React, TypeScript, PWA, UX, API consumers, frontend tests.
- **Claude Code:** FastAPI, application/domain, persistence, backend security and backend tests.

The PWA consumes FastAPI only. It never reads Supabase tables directly and never receives a connection string, password, service-role key, or other credential.

## 2. Current System Architecture

```text
Browser
  |
  v
React / TypeScript PWA (frontend/src)
  |- Dashboard  frontend/src/pages/DashboardPage.tsx
  |- Upload     frontend/src/pages/UploadPage.tsx
  |- Products   frontend/src/pages/ProductsPage.tsx
  `- Runs       frontend/src/pages/RunsPage.tsx
  |
  v
API boundary (frontend/src/api/client.ts + resource modules)
  |
  v
FastAPI (src/juval/interfaces/api/main.py)
  |
  v
application / domain / persistence
```

`frontend/src/App.tsx` owns route registration and `frontend/src/components/AppLayout.tsx` owns the shell.

## 3. Frontend Routes and REAL vs DEMO

| Route | Page | Purpose | State / source | Backend dependency |
| --- | --- | --- | --- | --- |
| `/` | `DashboardPage.tsx` | Metrics and recent-run display | **DEMO**, `src/data/demo.ts` | None; no Dashboard API is designed. |
| `/upload` | `UploadPage.tsx` | Submit XLSX, render result, download Excel | **REAL**, FastAPI | `POST /api/v1/runs`, `GET /api/v1/runs/{execution_id}/download`. |
| `/products` | `ProductsPage.tsx` | Current product table | **DEMO**, `src/data/demo.ts` | Historical global-client proposal is disconnected. Records are backend run-scoped. |
| `/runs` | `RunsPage.tsx` | Execution-history table | **DEMO**, `src/data/demo.ts` | List endpoint exists, but the prepared DTO is stale. |

Dashboard, Products, and Runs visibly render `DEMO MODE`. Upload renders the contextual `Live processing` marker. Fixtures live only in `frontend/src/data/demo.ts`; API failure never becomes fixture data.

## 4. Frontend API Boundary

| File | Responsibility | Current use |
| --- | --- | --- |
| `frontend/src/api/client.ts` | Reads public `VITE_API_BASE_URL`, constructs URLs, uses `fetch`, parses JSON, and throws `ApiError` for non-2xx responses. | Used by all API modules. |
| `frontend/src/api.ts` | Upload multipart request and download URL. | Connected to Upload. |
| `frontend/src/api/runs.ts` | Historical `getRuns(signal?)` consumer with runtime response checks. | Disconnected: it expects older demo vocabulary, not `RunSummaryOut`. |
| `frontend/src/api/products.ts` | Historical `getProducts(signal?)` consumer with runtime checks. | Disconnected: global Products is not registered and conflicts with the run-scoped records model. |

There is no frontend SDK, repository/service layer, direct Supabase client, state manager, or silent API-to-demo fallback.

## 5. API Endpoints That Exist Today

The actual decorators in `src/juval/interfaces/api/main.py` register these PWA-facing routes.

### IMPLEMENTED — `POST /api/v1/runs`

- **Consumer:** `frontend/src/api.ts` → `UploadPage.tsx`.
- **Request:** multipart `file`, JSON strings `thresholds` and `fees`, and `persist` boolean.
- **Success:** `200 RunResponse` with execution identity/counters and `records: RecordOut[]`.
- **Errors:** `422` invalid request/import/failed run; `413` configured upload size exceeded; sanitized `500` for unexpected failures.
- **Evidence:** `tests/integration/test_api.py`; real Upload E2E: `frontend/e2e/smoke.spec.ts`.

### IMPLEMENTED — `GET /api/v1/runs/{execution_id}/download`

- **Consumer:** `downloadUrl()` in `frontend/src/api.ts`.
- **Success:** generated `.xlsx` attachment.
- **Error:** `404 { "detail": "unknown or expired execution_id" }` when output is unavailable.
- **Evidence:** `tests/integration/test_api.py`, `frontend/e2e/smoke.spec.ts`.

### IMPLEMENTED — `GET /api/v1/runs`

- **Query:** `limit`, default `20`, inclusive range `1..100`.
- **Success:** `200 RunsListResponse` with `items: RunSummaryOut[]`: `execution_id`, `started_at`, nullable `finished_at`, `status`, `input_filename`, `input_hash`, `records_total`, `records_processed`, `records_successful`, `records_with_errors`, `warnings`.
- **Ordering:** newest first, from `ExecutionRunStore.list_execution_runs(limit=...)`.
- **Empty:** `200 { "items": [] }`.
- **Error:** safe `500` when no execution-run store is configured.
- **Frontend state:** route exists but Runs remains demo until Codex reconciles its DTO/page.

### IMPLEMENTED — `GET /api/v1/runs/{execution_id}/records`

- **Success:** `200 { "execution_id": "...", "records": RecordOut[] }` from persisted run-scoped snapshots.
- **Errors:** `404 { "detail": "unknown execution_id" }`; safe `500` when no execution-run store is configured.
- **Frontend state:** no consumer yet. ADR-019 defines this as the record boundary, not a global Products API.

## 6. Contracts Pending or Requiring Reconciliation

### Runs — frontend reconciliation, not a missing endpoint

`frontend/src/api/runs.ts` still expects this older consumer proposal:

```json
{
  "items": [{
    "execution_id": "string",
    "created_at": "ISO-8601 timestamp",
    "status": "SUCCESS | PARTIAL_SUCCESS | FAILED",
    "total_records": 0,
    "valid": 0,
    "excluded": 0,
    "errors": 0
  }]
}
```

This is **not the implemented backend contract**. `ExecutionRun` and `RunSummaryOut` use `started_at`/`finished_at`, `records_total`, `records_processed`, `records_successful`, `records_with_errors`, and `warnings`. The UI must adapt deliberately; backend must not invent `created_at`, `valid`, or `excluded` to match demo fixtures.

Counter semantics remain owned by `ExecutionRun`. Do not assume `valid + excluded + errors == total_records`: the domain does not guarantee it. The list is newest-first. A run is listable only when persisted; Upload currently sends `persist=false` for the demo flow.

### Products — historical proposal; global endpoint is BACKEND_PENDING and not approved

`frontend/src/api/products.ts` expects a historical global `GET /api/v1/products` response of `{ "items": ProductListItem[] }`. Its current minimal item is:

```text
record_ref: string
supplier_sku: string | null
title: { value, status }
brand: { value, status }
cog: string | null
asin: { value, status }
hazmat_status: string | null
bulky_status: string | null
decision: string | null
```

### REQUIRED BY CURRENT UI

- run-scoped record reference and supplier SKU;
- title, brand, cost/COG, and ASIN display;
- explicit ASIN provenance status;
- Hazmat status, Bulky status, and backend decision.

### OPTIONAL / FUTURE

- title/brand provenance, marketplace, UPC, weight, risk severity, profitability, decision reasons, issues, and execution reference.

### NOT REQUIRED

- global catalog identity, pagination, filtering, sorting, search, product-detail routes, direct Supabase data, or browser business logic.

> This is a frontend consumer expectation, not a FastAPI design mandate. ADR-019 approves `GET /api/v1/runs/{execution_id}/records`, never a global `GET /api/v1/products`, because Juval has no cross-run product identity.

The current `RecordOut` lacks title and brand. Claude must not create a global endpoint merely to fit the demo table. Instead, reconcile whether run-scoped snapshots need these fields; Codex will then adapt Products to the approved resource.

## 7. Product Identity: `record_ref`

ADR-012 defines `record_ref` as `row_{excel_row_number}[:supplier_sku]`. It is deterministic, traceable, non-empty, and unique **inside one import run**. It is not a permanent global product ID: row edits/reordering or a different input can change/collide references. The persisted identity is `(execution_id, record_ref)` (ADR-019). Do not add `GET /products/{record_ref}` or treat `record_ref` as a global primary key.

## 8. Provenance Contract

Provenance is data, not presentation inference.

- Domain: `src/juval/domain/provenance.py`; decisions: ADR-003 and ADR-004.
- Existing FastAPI shape: `FieldValueOut` in `src/juval/interfaces/api/models.py`.
- Frontend type: `FieldValueOut` in `frontend/src/types.ts`.
- Renderers: `frontend/src/components/ResultsTable.tsx` and `frontend/src/components/StatusBadge.tsx`.

| Technical state | Meaning |
| --- | --- |
| `VERIFIED` | Sufficient evidence from a trusted source. |
| `INFERRED` | Explicit rule/heuristic result; never promoted by the UI. |
| `NOT_FOUND` | No sufficient evidence; the domain requires `value=None`. |
| `INVALID` | Raw value failed validation; it stays distinct for diagnosis. |

Forbidden transformations:

```text
value present  -> VERIFIED
null           -> NOT_FOUND
INVALID        -> NOT_FOUND
confidence     -> VERIFIED
```

For provenance-aware fields, transport `value` and `status` together. A nullable status is not permission for React to invent one.

## 9. Hazmat, Bulky, and Decision

React calculates none of ASIN, Hazmat, Bulky, profitability, decision, or provenance. It renders backend values.

Do not collapse these concepts:

1. `RiskFlag.status`: `PRESENT`, `ABSENT`, or `UNKNOWN`.
2. `RiskFlag.verification_status`: `VERIFIED`, `INFERRED`, `NOT_FOUND`, or `INVALID`.

Current `RecordOut` exposes risk status/severity (`hazmat_status`, `hazmat_severity`, `bulky_status`, `bulky_severity`) but no separate risk verification status. Before Products claims Hazmat/Bulky provenance, the backend contract needs an explicit decision on whether to expose it. `BUY`/`REVIEW`/`PASS` remains an application/domain result, never a React classification.

## 10. Error Contract

- Non-2xx is an explicit UI error; a short safe `{ "detail": "..." }` is supported.
- Responses must not expose tracebacks, filesystem paths, queries, secrets, or credentials.
- Connected list UIs may offer retry.
- `API ERROR != USE DEMO DATA`.

## 11. Local Development Connection

```powershell
# Repository root — FastAPI
$env:JUVAL_CORS_ORIGINS='http://127.0.0.1:5173'
.venv\Scripts\python -m uvicorn juval.interfaces.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Repository root — Vite
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

| Item | Value |
| --- | --- |
| Frontend | `http://127.0.0.1:5173/` |
| Backend | `http://127.0.0.1:8000/` |
| CORS origin | `http://127.0.0.1:5173` |
| Frontend API variable | `VITE_API_BASE_URL` |

`frontend/src/api/client.ts` defaults the public base URL to `http://localhost:8000`. `frontend/.env.example` documents `VITE_API_BASE_URL`. `service.cors_origins()` reads comma-separated `JUVAL_CORS_ORIGINS` and FastAPI does not permit wildcard origins.

Only `VITE_API_BASE_URL` is relevant public frontend connection config. Never put backend credentials or a database connection string in `VITE_*` or an HTTP response.

## 12. Demo Local v1

Fixture: `tests/fixtures/sample_sourcing_TEST_DATA.xlsx`. It is a technical test fixture, not production commercial data.

1. Start FastAPI and Vite with section 11 commands.
2. Open `http://127.0.0.1:5173/upload`.
3. Select `tests/fixtures/sample_sourcing_TEST_DATA.xlsx`.
4. Enter the already-required thresholds/fees and process the XLSX.
5. Verify the real `POST /api/v1/runs` summary/records and their statuses.
6. Use the download action; it calls the implemented Excel download endpoint.

CSV remains visibly unsupported/pending and is not a real alternative to XLSX.

## 13. Tests and Validation

| Scope | Location | Command |
| --- | --- | --- |
| Unit/component/API modules | `frontend/src/**/*.test.tsx`, `frontend/src/api/*.test.ts` | `npm test` |
| Responsive/routing E2E | `frontend/e2e/products.spec.ts`, `runs.spec.ts`, `shell.spec.ts` | `npm run test:e2e` |
| Real XLSX upload/download E2E | `frontend/e2e/smoke.spec.ts` | `npm run test:e2e` with both local servers |
| Lint / production PWA build | `frontend/package.json`, `frontend/vite.config.ts` | `npm run lint`; `npm run build` |

Last verified Demo Local v1 evidence for this source tree: **20 frontend tests**, **13 Playwright tests**, lint, and production build passed. Rerun after changes. Automated Playwright is not human visual QA; manual browser inspection remains pending where an integrated browser is unavailable.

## 14. Mobile and PWA Contract

- Desktop: persistent sidebar; narrow viewports: labelled bottom navigation (`AppLayout.tsx`).
- Products/Runs tables preserve columns with horizontal scrolling instead of silently hiding fields.
- Backend does not vary domain schema by viewport.
- `frontend/vite.config.ts` configures manifest plus `generateSW` precache. Backend must not depend on service-worker state.

## 15. BACKEND NEXT STEPS

### Priority 1 — Finalize handoff of implemented Runs resource

1. Preserve `RunsListResponse`, newest-first ordering, limit behavior, and configured-store failure semantics.
2. Confirm/document counter semantics from `ExecutionRun`.
3. Retain backend tests for empty list, ordering, limit, and missing store.
4. Give Codex the final contract. Codex then replaces the historical Runs DTO and connects the page. No new Runs endpoint is required.

### Priority 2 — Complete run-scoped records, not global Products

1. Preserve `(execution_id, record_ref)` identity and `GET /api/v1/runs/{execution_id}/records`.
2. Decide title/brand availability and explicit risk provenance before adding UI-needed fields to snapshots/`RecordOut`.
3. Keep the endpoint application/domain-backed; never expose Supabase tables.
4. Give Codex the updated records DTO. Codex will adapt Products to a selected run-scoped resource.

### Priority 3 — Dashboard

Do not design a dashboard endpoint before the two resources are used by the frontend and there is a concrete UI requirement.

## 16. FRONTEND/BACKEND OWNERSHIP

| Claude Code owns | Codex owns |
| --- | --- |
| FastAPI endpoints, application services, domain, persistence, Supabase, migrations, backend validation/security/tests | React, TypeScript, routing, pages, components, consumers, loading/error/empty UX, PWA, responsive behavior, frontend tests |

Shared boundary: HTTP DTOs, status/counter semantics, safe errors, and provenance representation. Reconcile changes explicitly.

## 17. Files Claude Code Should Read First

1. `docs/FRONTEND_BACKEND_HANDOFF.md`
2. `frontend/README.md`
3. `docs/architecture/API_CONTRACT.md` (its historical list-endpoint section is superseded by current router/ADR-019)
4. `frontend/src/api/client.ts`
5. `frontend/src/api/runs.ts`
6. `frontend/src/api/products.ts`
7. `frontend/src/types.ts`
8. `frontend/src/pages/RunsPage.tsx`
9. `frontend/src/pages/ProductsPage.tsx`
10. `src/juval/interfaces/api/main.py`
11. `src/juval/interfaces/api/models.py`
12. `src/juval/interfaces/api/service.py`
13. `src/juval/domain/execution_run.py`
14. `src/juval/domain/sourcing_record.py`
15. `src/juval/domain/provenance.py`
16. `src/juval/domain/risk.py`
17. `docs/adr/ADR-003-provenance-datos.md`
18. `docs/adr/ADR-004-estados-verificacion.md`
19. `docs/adr/ADR-012-record-ref-estrategia.md`
20. `docs/adr/ADR-019-persistencia-records-run-scoped.md`

## 18. Known Blockers

- Runs UI is demo because its prepared frontend DTO predates the implemented list contract.
- Products UI is demo; its global endpoint proposal is not registered and does not match ADR-019's run-scoped record model.
- Upload defaults to `persist=false`, so a persisted/configured run is needed to demonstrate real list/records data.
- Manual browser visual inspection is pending; automated responsive E2E exists.

## 19. Approved Decisions and ADR Candidates

Already approved: PWA (ADR-014), FastAPI boundary (ADR-016), explicit provenance (ADR-003/004), run-scoped identity (ADR-012/019), no direct Supabase browser access, no frontend business-logic duplication, and no silent API-to-demo fallback.

No new ADR is required. **ADR_CANDIDATE only if a durable cross-run product identity is later requested**; it would extend—not reinterpret—ADR-012/019.

## 20. Documentation Validation

This handoff was reconciled against current frontend modules, actual FastAPI route decorators, API models/service, `ExecutionRun`, `SourcingRecord`, `RiskFlag`, provenance, ADR-003/004/012/019, test layout, and the sample XLSX path. It intentionally distinguishes implemented routes from historical frontend proposals. No secret, password, service-role key, or connection string is documented.

## 21. Local Appearance / Branding

`frontend/src/theme/ThemeProvider.tsx` is the frontend-only source of truth for `ThemeSettings`. `appearanceMode` is `light` or `dark`; it controls the complete structural palette (charcoal/graphite in Dark, never OLED black) through CSS custom properties while retaining the selected accent and local assets. The provider persists preferences through `frontend/src/theme/storage.ts`, including a safe migration of the prior Light/Dark preset representation.

- Route: `/appearance` (`frontend/src/pages/AppearancePage.tsx`).
- Appearance: `/appearance` provides a keyboard-accessible smartphone-style Light/Dark switch. Reset restores the JUVAl default Dark appearance together with default branding.
- Local assets: PNG/JPEG/WEBP only, 400 KB per logo/background asset, stored as browser data URLs. Invalid/corrupt settings fall back to JUVAl defaults; storage quota errors preserve the live preview and show a safe message.
- Background options: cover/contain, center/top/bottom, and overlay opacity. Panels remain opaque to protect operational readability.
- Status/provenance badge colors remain semantic and are not redefined by customer accent selections.

**Future debt:** authenticated workspace assets should move from `localStorage` to Supabase Storage only after authentication/workspaces are approved. No remote storage is part of the current PWA contract.
