# frontend-next — Golden data-layer migration matrix

**2026-08-26.** Companion to ADR-030. Tracks, module by module, how the Golden
application's data layer is replaced by real backend contracts in
`frontend-next/`.

`demo/` stays byte-identical (`demo/src` SHA-256
`a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`) and remains
the reference for every Golden UI not yet migrated. Nothing below is deleted
from the product — only from the production candidate's runtime.

## Status

**2026-11-03 — Owner acceptance / cutover preparation:** walkthrough and
[acceptance checklist](FRONTEND_NEXT_VISUAL_ACCEPTANCE.md) prepared. Source
comparison against `frontend/` found protected capability gaps (Dashboard
controls, Catalog identity/issues/provenance controls, Runs sorting, Run Detail
batch/preview, legacy customization, PWA and compatibility). **Full parity is
not certified and cutover remains unapproved.** The complete-run download was
restored; named navigation and native color-scheme added with unit coverage.
Eight new visual/responsive scenarios ran externally: 2 passed / 6 failed on
mobile/768 overflow (D1 Run select, D2 Run Detail hash); retained suite 30/30.
Current unit result: 218 passed / 10 conditional skips; see PROJECT_STATUS for
current checks versus the historical B/C browser evidence below.

**2026-11-03 — B/C recovery (frontend-only, no push/deploy).** Overall
**PARTIAL**. Browser E2E, run outside the Codex sandbox (whose Node
`spawnSync` returns EPERM) against disposable local services only:
first 29/1 (`recovery-c1` selector), then, after Codex's selector and
readability fixes, **30 passed / 0 failed** with no `LocalProtocolError`.
Unit 209 / 0 / 10 skipped; typecheck, lint, build pass. Details, commands and
the C1 analysis: PROJECT_STATUS's 2026-11-03 entries. B1-B4, C1, C2 and C3 are
committed locally.

| Block | Current status | Evidence |
|---|---|---|
| B2 ROI percentage | **VERIFIED** | E2E: 30% → `min_roi=0.3`, XLSX metadata/rows = API; unit |
| B3 BUY | **VERIFIED** | E2E on a synthetic seeded snapshot (INFERRED, empty reasons); unit |
| C2 Catalog columns | **VERIFIED** | E2E both themes, query/export unchanged; unit |
| C1 Appearance | **VERIFIED** | E2E: WCAG contrast from computed CSS (white/black accents, light/dark/checker backgrounds, both themes, 390 px), persistence, reset; 12 screenshots reviewed |
| C3 Methodology | **VERIFIED** | E2E both themes, same tab; unit |
| B1 batches | **VERIFIED** | E2E 2 and 10 files, 11-file overflow sends no request; unit |
| B4 browser exports | **VERIFIED** | E2E consecutive/concurrent = `/records`; captured server log has no `LocalProtocolError` |

**Re-inventoried 2026-10-28 from the code** (`src/app/App.tsx` routes) at
master `46a5c9a`. The previous table (2026-08-26) still listed Dashboard,
Product Detail and the Favorites page as not wired; the code wires them.

Evidence of the 2026-10-28 operator run (logs kept privately outside APP):
`npm ci` from the lockfile, `typecheck` 0 errors, `lint` 0, `vitest` 190 passed
/ 10 skipped (9 need `JUVAL_LIVE_API`, 1 needs `JUVAL_FINANCIAL_JSON`: by
design, not verified), `build` OK, Playwright E2E 21/21 against a disposable
API (temporary SQLite, auth disabled, loopback, synthetic fixtures).

Legend: **VERIFIED** = exercised in a real browser (E2E and/or its
screenshots) plus unit tests; **IMPLEMENTED** = wired and unit-tested, not
exercised in a browser; **PARTIAL** = part of the target is missing;
**PENDING** = not built, no external blocker; **BLOCKED** = needs a decision,
contract or authorized source first.

| Surface | State | Evidence / blocker |
|---|---|---|
| Shell, navigation (same tab, Back) | **VERIFIED** | E2E d7 tests 4–5 and 14 |
| Light/Dark (shell toggle, browser-local) | **VERIFIED** | E2E screenshots dark/light, desktop/phone; `App.test` |
| Dashboard on the run analytics endpoint | **VERIFIED** | E2E d7 test 4 + screenshot; `DashboardPage.test` (13) |
| Catalog: server-side search, filters, sort, pagination, filter persistence | **VERIFIED** | E2E (d7, g17, severity); `CatalogPage` (14), `CatalogBrandFilter` (8), `catalogQuery` (11) |
| Catalog: ROI/profit/margin entered as percentages | **VERIFIED** | E2E `recovery-b2` (2026-11-03); unit `percentInputToRatio` |
| Filtered export | **VERIFIED** | E2E (export = run download = API); concurrency fixed in backend `46a5c9a` |
| Import with preview (XLSX and CSV, one tabular contract, ADR-026) | **VERIFIED** | E2E preview + upload of single synthetic files; `UploadPage` (11), `ImportPreview` (8) |
| Batch of up to 10 files, Batch Detail, per-file analytics | **VERIFIED** | E2E `recovery-b1` (2 and 10 files, overflow); `UploadPage`, `BatchAnalytics` |
| Runs list, Run Detail | **IMPLEMENTED** | `RunsFlow` (16); E2E only passes through "Open run" |
| Product Detail (decision, reasons, economics with status, financial evidence, declared demand, suggested price, severity source) | **VERIFIED** | E2E + screenshots; `ProductDetailPage` (17), `FinancialEvidence` (10) |
| Provenance badges (VERIFIED / INFERRED / NOT_FOUND / INVALID) and severity source | **VERIFIED** | E2E + screenshots; `SeverityProvenance` (9) |
| BUY rendering | **VERIFIED** | E2E `recovery-b3` on a synthetic seeded snapshot (not a pipeline BUY); unit |
| Favorites page (browser-local, run-scoped) | **IMPLEMENTED** | `FavoritesPage` (12); no E2E |
| Appearance page (accent, logo, background) | **VERIFIED** | E2E `recovery-c1` (2026-11-03); unit `appearance`, `AppearancePage` |
| Catalog column visibility and order | **VERIFIED** | E2E `recovery-c2` both themes; unit |
| Methodology page | **VERIFIED** | E2E `recovery-c3` both themes; unit |
| Images / thumbnails | **BLOCKED** | Thumbnail slot always shows "No image" (`src=""`): no image contract, rights or provenance |
| Market history chart | **BLOCKED** | No authorized provider. Golden's simulated series deliberately not carried (`ProductDetailPage.tsx` header); whether to show a `DEMO_FIXTURE`-labelled series is an open decision |
| Compare | **BLOCKED** | Placeholder; needs a comparable-identity ADR (ADR-011/012) and a batch-scoped cross-run query |
| External supplier/marketplace links | **BLOCKED** | No approved URL field or rights policy |
| Threshold editor / read-only bands | **BLOCKED** | ADR-051 is still Propuesta |
| Server-side saved favorites | **BLOCKED** | Needs auth, ownership and isolation |
| Dependency reproducibility | **VERIFIED** | Lockfile + `npm ci`; `npm audit` reports 5 dev-only advisories (vite, undici, source-map-js high; vitest, @vitest/mocker moderate), not remediated |

## Dependency reproducibility (milestone 2)

Milestone 1 assembled `node_modules` by copying from `demo/` and `frontend/`
and dropped the inherited lockfile because it no longer described the app.
That runs but is not reproducible.

Corrected by auditing what the source actually imports rather than trusting the
manifest: `react`, `react-dom` and the test/build toolchain. `recharts` was
declared but never imported — milestone 1 removed every chart along with the
fixture engine — so it was dropped and returns with Dashboard. `node_modules`
was then deleted outright and reinstalled with `npm ci` from the generated
lockfile, which is the clean-checkout case rather than a reconciliation of
whatever happened to be on disk.

| | |
|---|---|
| Node | v24.19.0 |
| npm | 11.17.0 |
| lockfileVersion | 3 |
| packages from `npm ci` | 123 |
| After clean install | 52 tests, lint, typecheck, build all pass |

---

## Golden module → production replacement

| Golden module | Purpose in Golden | Production replacement | Endpoint / contract | Provenance requirement | State model | Status |
|---|---|---|---|---|---|---|
| `demo-engine/index.ts` | generates ASIN, price, fees, weight, risk from a hash; computes profit/ROI/margin; decides BUY/REVIEW/PASS | backend Profitability + Decision Engine | values arrive on `RecordOut` | every field carries `FieldValueOut.status`; nothing derived in the browser | server | **REMOVED** from candidate |
| `engine.ts` | barrel re-export of the fixture engine | — | — | — | — | **REMOVED** |
| `catalog/select.ts` | client-side filter + sort + paginate over an in-memory array | `GET /api/v1/runs/{id}/records` query parameters | `search`, `decision`, `sort`, `direction`, `min_roi/profit/margin`, `confidence`, `hazmat`, `bulky`, `provenance_field/status`, `limit`, `offset` | thresholds are confidence-aware server-side | server | **REPLACED** by `src/api/catalog.ts` |
| `storage.ts` | whole runs + records in `localStorage` | persisted `ExecutionRun` + record snapshots | `GET /api/v1/runs` | run-scoped snapshots (ADR-019) | server | **REPLACED** |
| `batch.ts` | browser batching, `MAX_FILES = 10` | `POST /api/v1/batches`, one child run per file | `BatchResponse` / `BatchFileOut` | per-file status and counts | server | **REPLACED** (m2) by `src/api/batches.ts` |
| `csv/parseCsv.ts` | Papa Parse in the browser | backend importer (ADR-026) | `POST /api/v1/runs` | import provenance recorded server-side | server | **REMOVED** |
| `xlsx/parseXlsx.ts` | `xlsx` in the browser | backend importer | same | same | server | **REMOVED** |
| `adapters/WestMarineCsvAdapter.ts` | detects supplier columns; classifies USED / OPTIONAL / IGNORED with canonical names | `infrastructure/excel/column_mapping.py` | none exposed yet | mapping is real audit evidence | server | **REMOVED** — capability blocked on exposing the mapping (see below) |
| `price-history.ts` | deterministic 90-day series from a hash | none | none | `DEMO_FIXTURE` only | — | **REMOVED** — chart UX returns in milestone 3 with the fixture label |
| `quality.ts` | groups fields by provenance; coded quality facts | `RecordOut.issues` + per-field `status` | `RecordOut` | grouping is real, derived from real statuses | server | **PENDING** (milestone 3) |
| `trace.ts` | per-field source column, raw value, transformation, formula | field `Provenance` on the record endpoint | `GET …/records/{ref}` | partial: source/reference exist, raw row and formula do not | server | **PENDING / partly blocked** |
| `matching.ts` | groups records sharing a supplier URL across source files | none | none | needs a comparable-identity decision | — | **BLOCKED** — ADR + cross-run query |
| `product-route.ts` | `/run/:run/file/:file/product/:ref` | `/run/:executionId/product/:recordRef` (one run = one file) | `GET …/records/{ref}` | run-scoped | server | **PENDING** (milestone 3) |
| `favorites.ts` | `runId:sourceFileId:recordRef` in `localStorage` | same idea, `executionId:recordRef` | none, by design | none — carries no data | **LOCAL_PREFERENCE** | **DONE** |
| `app/context.tsx` | demo app context: runs, records, decision policy, notice | per-page state against the API | — | — | component | **REPLACED** |
| Decision policy editor | edits ROI bands and **rewrites stored decisions** | none — must not exist | — | would misstate a historical decision | **RUN_STATE**, not client | **REJECTED** — needs `ExecutionRun.thresholds` (ADR) |
| Supplier image (`img-fluid src`) | real URL from the supplier export | none | no image field on `RecordOut` | would need source, rights, caching and provenance | server | **BLOCKED** — slot kept, no image invented |
| Supplier URL (`position-relative href`) | real URL from the supplier export | none | no URL field | same | server | **BLOCKED** |

---

## What `frontend-next/` deliberately does not contain

No fixture engine, no browser CSV/XLSX parsing, no simulated enrichment, no
generated ASIN, no client-side decision policy, no local run store, and no
automatic demo bootstrap. Golden's `ImportPage` could load a bundled CSV and
produce a full run without touching a server; inside a production candidate
that is precisely the failure this pivot exists to prevent, so the whole path
is gone rather than disabled.

Routes that are not yet wired render `NotWiredPage`, which states the
capability, names its blocker where there is one, and shows **nothing** rather
than demonstration data.

---

## Provenance firewall — milestone 1 audit

| Field on screen | Source | Status shown | Fabricated? |
|---|---|---|---|
| Brand, title | `RecordOut` | inherited from the field | no |
| Cost (COG) | `RecordOut.cog` | plain Decimal, no status field on the contract | no |
| Selling price, profit, ROI, margin | `RecordOut` `FieldValueOut` | **yes** — `VER` / `INF` / `N/F` / `INV` beside every value | no |
| HazMat, Bulky | `RecordOut` status fields | value is the status | no |
| Decision | backend Decision Engine | rendered as-is | no |
| Product image | — | slot renders "No image" | **no image invented** |
| Decision bands | — | "Not recorded for this run" | **not guessed** |
| Market history | — | not present in milestone 1 | n/a |

ROI and margin are stored as ratios and displayed as percentages; the
conversion lives in one place (`api/contract.ts`) and the domain's ratio
semantics are unchanged.

---

## Milestone 2 — Upload / Batch / Runs

### Golden UX kept, Golden engine gone

| Golden Import behaviour | frontend-next |
|---|---|
| drop zone with a dragging state | kept |
| file cards with size and type | kept |
| per-file remove, clear all | kept |
| `n / MAX_FILES` counter | kept |
| single submit action | kept |
| unsupported / overflow files named individually | kept |
| browser CSV/XLSX parsing, local preview | **removed** — the backend importer is the authority |
| twelve named progress stages, all flipped to COMPLETE | **not carried over** — decorative. The API reports a completed batch, not progress, so the in-flight state is honestly indeterminate and names every submitted file |
| "Add included West Marine demo file" | **removed** — a bundled fixture has no place in a production candidate |

### Batch: production's model wins

Golden modelled one run holding many files. Production creates one
`ExecutionRun` **per file**, grouped under a batch. That keeps per-file
provenance and makes each file independently auditable, so it is the model that
survives; what it borrows from Golden is the presentation.

- aggregate status, file counts, record counts, warnings
- per-file row: status, counts, errors/warnings, link to its child run
- a `REJECTED` file never ran: it has no `execution_id` and its counts read
  "—" / "never ran", not `0`
- **retry creates a new batch.** A batch and its runs are an immutable record,
  so the UI says so rather than offering an in-place re-run

### Runs

Real `GET /api/v1/runs`. Golden's row hierarchy kept — filename, status badge,
counts, timestamp, drill-down. Golden also showed BUY/REVIEW/PASS per row,
which it could do with every record in memory; the runs endpoint returns no
decision counts and deriving them would mean one analytics request per row, so
they are **absent rather than invented**. Duplicate/Delete not implemented:
both need run lifecycle semantics no ADR covers.

### Run detail

Minimum needed to close the loop. ExecutionRun's own persisted fields only. An
unknown id is a real 404 with no "Retry", because the request was fine and the
id was not.

### Route and state map

| Route | Resource | Notes |
|---|---|---|
| `/` | — | not wired |
| `/import` | `POST /api/v1/batches` | Golden's route name kept |
| `/batch/:batchId` | `GET /api/v1/batches/{id}` | production resource Golden lacked |
| `/runs` | `GET /api/v1/runs` | |
| `/runs/:executionId` | `GET /api/v1/runs/{id}` | |
| `/catalog?run=…` | `GET /api/v1/runs/{id}/records` | run preselection from the URL is what makes the hand-off work |
| `*` | — | explicit not-found, keeps the shell |

| State | Classification |
|---|---|
| queued files, drag state, submit state | `EPHEMERAL_UI` |
| catalog filters / sort / page size | `SESSION_PREFERENCE` (m2B) — `sessionStorage`, validated on restore |
| catalog page offset | `EPHEMERAL_UI` — never persisted |
| selected run id | `EPHEMERAL_UI`, seeded from the URL |
| favourites | `LOCAL_PREFERENCE` |
| appearance (dark) | `LOCAL_PREFERENCE` |
| batch id, per-file status, execution ids | `SERVER_BATCH_STATE` |
| run status, counts, hashes, records | `SERVER_RUN_STATE` |

No server truth is held in `localStorage`.

## Milestone 2B — Catalog filter persistence

Milestone 2 closed with one regression: the filter persistence recovered in the
legacy app (unit C1) had not been ported. Restored natively in
`src/catalogQuery.ts`, key `juval.next.catalog.query.v1`.

**Scope is `sessionStorage`, deliberately.** A remembered filter changes *which
records an operator sees*, so it should survive moving between screens in this
tab but must not silently narrow an unrelated sourcing session tomorrow.

| Persisted | Not persisted |
|---|---|
| search, decision, min ROI / profit / margin, HazMat, Bulky, provenance field + status, confidence mode, sort, direction, page size | **selected ExecutionRun** — that is which dataset is on screen, not a preference; restoring a stale id would point Catalog at a different run than the one the operator opened |
| | **page offset** — a stored page against a run whose contents may have changed opens on a page that no longer means the same thing |
| | **anything from the server** — no records, no totals, no error or loading state |

Every field is validated against the current query contract on read. An
obsolete `sort` from an older build degrades to the default instead of reaching
FastAPI as an out-of-contract value and returning a 422 the operator cannot
explain. The key is versioned so a future shape change cannot be misread as the
current one.

Reset clears the active filters, returns sort to `profit desc`, clears the
stored copy and issues the canonical unfiltered query. (The persist effect then
writes the defaults back, so the key holds the default state rather than being
absent — nothing stale can restore either way.)

Filtering, sorting, pagination and export all remain server-side; the export
still issues the same effective query as the table, minus pagination.
Favourites are untouched: still `localStorage`, run-scoped, labelled, no
request.

## Next milestones

State as of 2026-11-03 (see Status above).

| # | Scope | Depends on | Blockers / state |
|---|---|---|---|
| 3 | Product Detail, data quality, field trace, price-history UX with fixture label | 2 | **Done** except price history: blocked by provider; `DEMO_FIXTURE` label is an open decision |
| 4 | Dashboard analytics | 2 | **Done** |
| 5 | Appearance (accent, logo, background) | — | **Done** — C1 E2E passed 2026-11-03 |
| 6 | Favorites page | 3 | **Done**, browser-local and run-scoped |
| 7 | Compare | 3 | Blocked: ADR + batch-scoped cross-run query |
| 8 | Supplier image / URL contract | — | Blocked: backend contract + rights policy |
| 9 | `ExecutionRun.thresholds` + read-only bands + re-run | — | Blocked: ADR-051 Propuesta |
| 10 | Cutover `frontend-next/` → `frontend/` | full parity + user approval | user decision |
| 11 | E2E coverage of batch ≤10, ROI percent, BUY, consecutive/concurrent exports | — | **Done** — B1–B4 E2E passed 2026-11-03 |
| 12 | Catalog column visibility/order; Methodology page | — | **Done** — C2/C3 E2E passed 2026-11-03; human visual review pending |
