# JUVAl — Frontend → Backend Handoff

## Frontend Status: INTEGRATION IN PROGRESS

Frontend implementation was complete for the MVP scope and ready for backend API integration. This does **not** mean that every view consumes real backend data: Dashboard and Products deliberately retain their clearly labelled demo fixtures until their real contracts are reconciled. **Runs is now REAL** (`GET /api/v1/runs`, wired 2026-08-17 — see §15 Priority 1, now closed). Current frontend checkpoint: `ffe2a36` (`feat(frontend): refine light and dark appearance modes`); Runs integration is a Claude Code change on top of it (commit to follow this doc update).

Starting this session, Claude Code owns integrating the approved visual system with the real JUVAl backend end-to-end (not just documenting the gap) — see project instructions for the "Product Integration Phase". This handoff doc remains the shared reconciliation record; sections below are updated in place as each capability moves from DEMO to REAL, not duplicated.

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
  |- Dashboard   frontend/src/pages/DashboardPage.tsx
  |- Upload      frontend/src/pages/UploadPage.tsx
  |- Products    frontend/src/pages/ProductsPage.tsx
  |- Runs        frontend/src/pages/RunsPage.tsx
  |- Run Detail  frontend/src/pages/RunDetailPage.tsx  (/runs/:executionId)
  `- Appearance  frontend/src/pages/AppearancePage.tsx
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
| `/` | `DashboardPage.tsx` | Real analytics for one selected persisted run (latest by default, switchable) | **REAL**, FastAPI (2026-08-17) | `GET /api/v1/runs` (run selector), `GET /api/v1/runs/{execution_id}/records` (analytics source). No new endpoint -- see §15 Priority 3. |
| `/upload` | `UploadPage.tsx` | Submit XLSX, render result, download Excel | **REAL**, FastAPI | `POST /api/v1/runs`, `GET /api/v1/runs/{execution_id}/download`. |
| `/products` | `ProductsPage.tsx` | Current product table | **DEMO**, `src/data/demo.ts` | Historical global-client proposal is disconnected. Records are backend run-scoped. |
| `/runs` | `RunsPage.tsx` | Execution-history table | **REAL**, FastAPI (2026-08-17) | `GET /api/v1/runs`. Loading/empty/error states; retry on error; no demo fallback. Execution IDs link to Run Detail. |
| `/runs/:executionId` | `RunDetailPage.tsx` | Run metadata + run-scoped records + download | **REAL**, FastAPI (2026-08-17) | `GET /api/v1/runs/{execution_id}` (new), `GET /api/v1/runs/{execution_id}/records`, `GET /api/v1/runs/{execution_id}/download`. Loading/not-found/error(+retry)/ready states; stable URL (refresh/back/forward work, no in-memory-only state). |
| `/appearance` | `AppearancePage.tsx` | Local workspace appearance and branding | **LOCAL REAL**, `ThemeProvider` / browser `localStorage` | None. |

Dashboard and Products visibly render `DEMO MODE`; Runs renders a `LIVE API` marker instead. Upload renders the contextual `Live processing` marker. Dashboard/Products fixtures live only in `frontend/src/data/demo.ts`; API failure never becomes fixture data anywhere, including Runs.

| View | State | Data source |
| --- | --- | --- |
| Dashboard | **REAL** | FastAPI (single-run analytics, client-aggregated -- see §15 Priority 3) |
| Upload | **REAL** | FastAPI |
| Products | **DEMO / API-ready** | Frontend fixtures |
| Runs | **REAL** | FastAPI |
| Appearance | **LOCAL REAL** | `ThemeProvider` and `localStorage` |

`RunForm.tsx` now exposes "Persist this run" (previously hardcoded `persist: false`) — a run only appears under `/runs` when this is checked, matching the backend's own opt-in persistence model (ADR-013 "Option B").

## 4. Frontend API Boundary

| File | Responsibility | Current use |
| --- | --- | --- |
| `frontend/src/api/client.ts` | Reads public `VITE_API_BASE_URL`, constructs URLs, uses `fetch`, parses JSON, and throws `ApiError` for non-2xx responses. | Used by all API modules. |
| `frontend/src/api.ts` | Upload multipart request and download URL. | Connected to Upload. |
| `frontend/src/api/runs.ts` | `getRuns({limit?, signal?})` and `getRun(executionId, signal?)`, runtime shape checks against real `RunSummaryOut`. | **Connected** — used by `RunsPage.tsx`, `RunDetailPage.tsx` (2026-08-17). |
| `frontend/src/api/records.ts` | `getRunRecords(executionId, signal?)` — top-level shape check only (see file comment for why: `RecordOut` is already the trusted POST-response shape `api.ts` uses uncast, not a stale demo shape needing deep reconciliation like `products.ts`/`runs.ts` originally did). | **Connected** — used by `RunDetailPage.tsx` (2026-08-17). |
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
- **Frontend state:** connected (2026-08-17) — `RunsPage.tsx` fetches on mount, renders loading/empty/error/success states, no demo fallback. `RunForm.tsx` now exposes the `persist` checkbox needed to produce listable runs.

### IMPLEMENTED — `GET /api/v1/runs/{execution_id}` (added 2026-08-17)

- **Success:** `200 RunSummaryOut` — same shape as one item of `GET /api/v1/runs`.
- **Errors:** `404 { "detail": "unknown execution_id" }`; safe `500` when no execution-run store is configured.
- **Why it was added:** Run Detail needs a single run's metadata by ID without fetching the full list and searching client-side (doesn't scale, and the run may fall outside the list's `limit` window). Domain/persistence support already existed (`ExecutionRunStore.load_execution_run`, the same method `GET .../records` already used for its own 404 check) — no new capability, just a second thin HTTP route over it.
- **Frontend state:** connected — `RunDetailPage.tsx` (`/runs/:executionId`).

### IMPLEMENTED — `GET /api/v1/runs/{execution_id}/records`

- **Success:** `200 { "execution_id": "...", "records": RecordOut[] }` from persisted run-scoped snapshots.
- **Errors:** `404 { "detail": "unknown execution_id" }`; safe `500` when no execution-run store is configured.
- **Frontend state:** connected (2026-08-17) — `RunDetailPage.tsx` via `api/records.ts::getRunRecords`, rendered with the existing `ResultsTable.tsx` (reused unchanged, no second table component). ADR-019 defines this as the record boundary, not a global Products API; `ProductsPage.tsx` itself remains demo (see §15 Priority 2 — title/brand still not in the contract, unchanged).

## 6. Contracts Pending or Requiring Reconciliation

There is no missing approved Runs list endpoint: `GET /api/v1/runs` is implemented. `GET /api/v1/products` is **NOT IMPLEMENTED / NOT APPROVED** because the domain currently has no cross-run product identity. `GET /api/v1/dashboard` is **NOT IMPLEMENTED / NO FRONTEND CONTRACT**; Dashboard remains a demo until a concrete UI need exists.

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

The real E2E verifies `PARTIAL_SUCCESS`, `4` processed records, a real `B0TESTAAA1` ASIN with visible `[VERIFIED]` provenance, and an `.xlsx` download. This is evidence for the existing fixture and thresholds, not a promise for arbitrary catalogs.

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

Last verified at frontend checkpoint `ffe2a36`: **29 frontend tests** and **16 Playwright tests** passed; lint and production build passed. Re-verified 2026-08-17 after the Runs integration (Claude Code): **34 frontend tests** and **17 Playwright tests**. Re-verified again 2026-08-17 after Run Detail (Claude Code): **41 frontend tests** and **18 Playwright tests**. Re-verified again 2026-08-17 after Dashboard analytics (Claude Code): **54 frontend tests** and **19 Playwright tests** passed (adds `runAnalytics.test.ts`, `DashboardPage.test.tsx`, a Dashboard-through-App integration test, and `dashboard-analytics.spec.ts` -- a real-browser E2E for Upload-with-persist → Dashboard KPIs/charts → Run Detail), lint and production build still passing. The real Upload/download E2E is included in the Playwright suite. Automated screenshots were reviewed; integrated interactive browser inspection was not available, so this is not claimed as complete manual visual QA.

## 14. Mobile and PWA Contract

- Desktop: persistent sidebar; narrow viewports: labelled bottom navigation (`AppLayout.tsx`).
- Products/Runs tables preserve columns with horizontal scrolling instead of silently hiding fields.
- Backend does not vary domain schema by viewport.
- `frontend/vite.config.ts` configures manifest plus `generateSW` precache. The last production build generated `manifest.webmanifest`, `registerSW.js`, `sw.js`, and a six-entry precache. Backend must not depend on service-worker state.

## 14.1 Non-blocking frontend technical debt

- Vite reports one production JavaScript chunk above 500 kB. This is **NON-BLOCKING**; measure before introducing code splitting or changing bundle architecture.

## 15. WHAT CLAUDE CODE OWNS NEXT

### Priority 1 — CLOSED 2026-08-17: Runs resource connected

`frontend/src/types.ts` (`RunSummaryOut`/`RunsListResponse`), `frontend/src/api/runs.ts`, and `frontend/src/pages/RunsPage.tsx` now match the real backend contract exactly — no new backend endpoint, no backend change. `RunForm.tsx` exposes "Persist this run" so the slice is demonstrable end to end. Verified with a real browser E2E (`frontend/e2e/runs-persistence.spec.ts`): Upload with persist checked → run appears in `/runs` with its real `execution_id`/status/counters. 34 frontend unit tests + 17 Playwright E2E passing.

### Priority 2 — PARTIALLY CLOSED 2026-08-17: Run Detail connected; Products still blocked

Run-scoped records are now consumed for real by **Run Detail** (`/runs/:executionId`, `RunDetailPage.tsx`), not by Products: `(execution_id, record_ref)` identity preserved, `GET /api/v1/runs/{execution_id}/records` reused unchanged, `ResultsTable.tsx` reused unchanged (no second records table built). One new endpoint added, `GET /api/v1/runs/{execution_id}` (single-run metadata by ID) — justified because Run Detail needs it and `ExecutionRunStore.load_execution_run` already backs it; see §5.

**`ProductsPage.tsx` itself remains demo, unchanged.** `title`/`brand` are confirmed **NOT AVAILABLE IN CURRENT CONTRACT** (`RecordOut` has no such fields, verified directly against `models.py` 2026-08-17) — not derived, not invented, not added to the backend just to fill a visual column. Risk verification_status (`RiskFlag.verification_status`/`severity.status`, ADR-020) is also **NOT EXPOSED** by `RecordOut` today — same treatment: reported, not invented. Remaining steps, still pending a real decision:
1. Decide whether `RecordOut`/snapshot gain `title`/`brand` (would need `_build_record`/`record_to_snapshot` to carry `ProductInfo.title`/`.brand`, which the domain already has — not a domain gap, a snapshot/DTO scope decision).
2. Decide whether to expose `severity.status` (ADR-020 already flagged this as a deliberately deferred, additive-only change).
3. Only then adapt `ProductsPage.tsx` to the run-scoped resource (likely: list of runs → pick one → its records, i.e. reuse Run Detail's own records view rather than inventing a separate "Products" concept at all).

### Priority 3 — CLOSED 2026-08-17 (single-run scope): Dashboard connected

`DashboardPage.tsx` now shows real analytics for **one selected persisted run** (latest by default via `GET /api/v1/runs`, switchable via a `<select>`, records fetched per selection via `GET /api/v1/runs/{execution_id}/records`) — no dashboard/aggregation endpoint was added; both calls already existed. Cross-run/historical analytics remain explicitly out of scope (table below).

Aggregation lives in `frontend/src/runAnalytics.ts::deriveRunAnalytics(records)` — a pure, unit-tested function, no JSX, no recalculation of anything the backend already computed (profit/ROI/margin/decision/risk severity all pass through unchanged). Per-metric definition (kept here so backend aggregation can replace this later without changing semantics):

| NAME | SOURCE | FORMULA | MISSING POLICY |
| --- | --- | --- | --- |
| Total / Successful / With errors records | `RunSummaryOut.records_total/records_successful/records_with_errors` | Direct, no aggregation | n/a -- always present on a persisted run |
| Records with issues | `RecordOut.issue_count` per record | Count where `issue_count > 0` | n/a -- `issue_count` is always a number, never missing |
| Decision distribution | `RecordOut.decision` per record | Count by exact value (`BUY`/`REVIEW`/`PASS`); a `null` decision counts as its own `UNKNOWN` bucket, never dropped or folded into an existing one | n/a |
| Risk overview (HAZMAT/BULKY present) | `RecordOut.hazmat_status`/`bulky_status` per record | Count where `status === "PRESENT"` (RiskStatus/presence only, ADR-020 -- **not** `severity`, never treated as externally verified) | `ABSENT` and `UNKNOWN` both count as "neither present" -- `RecordOut` doesn't expose enough to distinguish confirmed-absent from unknown-presence today (same gap as risk `verification_status`, §9) |
| Average ROI / Profit / Margin | `RecordOut.roi`/`profit`/`margin` (`FieldValueOut`) per record | Arithmetic mean over records where `status` is `VERIFIED` or `INFERRED` only (mirrors `FieldValue.is_usable` in `domain/provenance.py`) | `NOT_FOUND`/`INVALID` records are excluded from both the numerator and the sample-size denominator -- **never coerced to 0**. Sample size is always displayed next to the average; the average shows "No usable data" (not `0%`/`$0`) when sample size is 0. |

**Explicitly not implemented, and why (NEEDS BUSINESS DEFINITION / NEEDS BACKEND AGGREGATION / NOT USEFUL YET):**

| Candidate | Classification | Why |
| --- | --- | --- |
| Cross-run aggregates (e.g. "BUY rate this week") | **NEEDS BACKEND AGGREGATION** | Would require fetching and summing records across many runs -- not fetched together today; backend aggregation vs. many-request client aggregation is an open scaling question, not decided here (§19 of this session's brief). |
| Average ROI/profit across a whole catalog (not one run) | **NEEDS BACKEND AGGREGATION + BUSINESS DEFINITION** | Same fetching problem, plus which runs to include (latest only? all time? a date range?) is a business question, not a technical one. |
| HAZMAT/BULKY prevalence across a catalog | **NEEDS BACKEND AGGREGATION + BUSINESS DEFINITION** | Same as above. |
| Profit/ROI histogram with buckets (e.g. low/medium/high) | **NEEDS BUSINESS DEFINITION** | Bucket boundaries would be an invented commercial threshold with no approval -- deferred exactly as instructed, not built with arbitrary buckets. |
| Overall VERIFIED/INFERRED/NOT_FOUND/INVALID rollup across all fields | **NOT USEFUL YET (no unambiguous formula)** | Summing statuses across heterogeneous fields (ASIN vs. weight vs. profit) without a precise definition of what's being counted would be a misleading single number; "records with issues" was implemented instead as the one data-quality metric with an unambiguous formula. |
| Run outcome history chart (SUCCESS/PARTIAL_SUCCESS/FAILED over time) | **NOT USEFUL YET** | `GET /api/v1/runs` already has everything needed technically, but the current dev dataset has too few persisted runs to be meaningful -- not fabricated now. |

Decision distribution and risk overview charts (identified as candidates in the previous session's handoff update) **are now implemented** -- see `AnalyticsChart.tsx`, extended (not replaced) to accept an optional per-bar `color`, reusing the same fixed semantic tokens `StatusBadge`'s CSS already uses (`var(--success)`/`var(--warning)`/`var(--danger)`, never the personalizable `var(--accent)`) so BUY/REVIEW/PASS/HAZMAT/BULKY stay visually distinct regardless of accent customization. No second chart library, no chart engine built.

## 16. WHAT CODEX OWNS / FRONTEND-BACKEND OWNERSHIP

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
10. `frontend/src/pages/UploadPage.tsx`
11. `frontend/src/theme/types.ts`
12. `src/juval/interfaces/api/main.py`
13. `src/juval/interfaces/api/models.py`
14. `src/juval/interfaces/api/service.py`
15. `src/juval/domain/execution_run.py`
16. `src/juval/domain/sourcing_record.py`
17. `src/juval/domain/provenance.py`
18. `src/juval/domain/risk.py`
19. `docs/adr/ADR-003-provenance-datos.md`
20. `docs/adr/ADR-004-estados-verificacion.md`
21. `docs/adr/ADR-012-record-ref-estrategia.md`
22. `docs/adr/ADR-019-persistencia-records-run-scoped.md`

## 18. Known Blockers

- Products UI is demo; its global endpoint proposal is not registered and does not match ADR-019's run-scoped record model. Blocked on a title/brand-in-`RecordOut` decision (§15 Priority 2), not started.
- Upload's "Persist this run" checkbox defaults to unchecked (`persist=false`), matching the backend's opt-in model — the operator must explicitly opt in for a run to be listable/queryable later.
- Manual interactive browser visual inspection is pending; automated responsive E2E exists and was run against a real local backend+frontend for the Runs integration (2026-08-17).

## 19. Approved Decisions and ADR Candidates

Already approved: PWA (ADR-014), FastAPI boundary (ADR-016), explicit provenance (ADR-003/004), run-scoped identity (ADR-012/019), no direct Supabase browser access, no frontend business-logic duplication, and no silent API-to-demo fallback.

No new ADR is required. **ADR_CANDIDATE only if a durable cross-run product identity is later requested**; it would extend—not reinterpret—ADR-012/019.

## 20. Documentation Validation

This handoff was reconciled against current frontend modules, actual FastAPI route decorators, API models/service, `ExecutionRun`, `SourcingRecord`, `RiskFlag`, provenance, ADR-003/004/012/019, test layout, and the sample XLSX path. It intentionally distinguishes implemented routes from historical frontend proposals. No secret, password, service-role key, or connection string is documented.

## 21. Definition of Frontend Ready

| Capability | State |
| --- | --- |
| PWA shell, routing, responsive layout, and mobile navigation | **READY** |
| Theme, Light/Dark mode, and local branding | **READY** |
| Upload API and download | **READY / REAL** |
| Runs consumer | **READY / REAL** |
| Run Detail consumer | **READY / REAL** |
| Products consumer | **READY / WAITING FOR RUN-SCOPED CONTRACT RECONCILIATION** (title/brand, risk provenance -- both confirmed NOT AVAILABLE in current `RecordOut`) |
| Dashboard | **READY / REAL** (single-run analytics; cross-run analytics remain a future slice) |
| Frontend tests, E2E, and production PWA build | **READY** |

## 22. Local Appearance / Branding

`frontend/src/theme/ThemeProvider.tsx` is the frontend-only source of truth for `ThemeSettings`. `appearanceMode` is `light` or `dark`; it controls the complete structural palette (charcoal/graphite in Dark, never OLED black) through CSS custom properties while retaining the selected accent and local assets. The provider persists preferences through `frontend/src/theme/storage.ts`, including a safe migration of the prior Light/Dark preset representation.

- Route: `/appearance` (`frontend/src/pages/AppearancePage.tsx`).
- Appearance: `/appearance` provides a keyboard-accessible smartphone-style Light/Dark switch. Reset restores the JUVAl default Dark appearance together with default branding.
- `frontend/src/components/AppearanceModeSwitch.tsx` is a semantic `role="switch"` control with `aria-checked`, native keyboard activation, focus-visible feedback, immediate CSS-token updates, and local persistence.
- Dark is the default, but never mandatory: it uses charcoal/graphite structural tokens (`background #181a1f`, `sidebar #121419`, `header #1d2026`), not pure black. Light is a full mode that updates background, sidebar, header, cards, text, muted text, borders, and elevated surfaces.
- Branding controls are separate from appearance mode: custom accent/structural tokens, live preview, logo replacement/removal, and background-image replacement/removal. Switching mode preserves logo, background image, fit/position, overlay, and accent.
- Local assets: PNG/JPEG/WEBP only, 400 KB per logo/background asset, stored as browser data URLs. Invalid/corrupt settings fall back to JUVAl defaults; storage quota errors preserve the live preview and show a safe message.
- Background options: cover/contain, center/top/bottom, and overlay opacity. Panels remain opaque to protect operational readability.
- Status/provenance badge colors remain semantic and are not redefined by customer accent selections.

**Future debt:** authenticated workspace assets should move from `localStorage` to Supabase Storage only after authentication/workspaces are approved. No remote storage is part of the current PWA contract.
