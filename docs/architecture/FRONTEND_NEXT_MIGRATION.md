# frontend-next — Golden data-layer migration matrix

**2026-08-26.** Companion to ADR-030. Tracks, module by module, how the Golden
application's data layer is replaced by real backend contracts in
`frontend-next/`.

`demo/` stays byte-identical (`demo/src` SHA-256
`a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`) and remains
the reference for every Golden UI not yet migrated. Nothing below is deleted
from the product — only from the production candidate's runtime.

## Milestone 1 status — Catalog

| | |
|---|---|
| Golden shell / navigation | **DONE** — Golden's `aside` + `main`, light/dark, same-tab routing |
| Catalog on the real API | **DONE** — server-side search, filters, sort, pagination, export |
| Favourites | **DONE** — browser-local, run-scoped, labelled, no request |
| Provenance | **DONE** — every economic value renders with its verification status |
| Everything else | **NOT WIRED** — honest placeholder, no fixture data |

---

## Golden module → production replacement

| Golden module | Purpose in Golden | Production replacement | Endpoint / contract | Provenance requirement | State model | Status |
|---|---|---|---|---|---|---|
| `demo-engine/index.ts` | generates ASIN, price, fees, weight, risk from a hash; computes profit/ROI/margin; decides BUY/REVIEW/PASS | backend Profitability + Decision Engine | values arrive on `RecordOut` | every field carries `FieldValueOut.status`; nothing derived in the browser | server | **REMOVED** from candidate |
| `engine.ts` | barrel re-export of the fixture engine | — | — | — | — | **REMOVED** |
| `catalog/select.ts` | client-side filter + sort + paginate over an in-memory array | `GET /api/v1/runs/{id}/records` query parameters | `search`, `decision`, `sort`, `direction`, `min_roi/profit/margin`, `confidence`, `hazmat`, `bulky`, `provenance_field/status`, `limit`, `offset` | thresholds are confidence-aware server-side | server | **REPLACED** by `src/api/catalog.ts` |
| `storage.ts` | whole runs + records in `localStorage` | persisted `ExecutionRun` + record snapshots | `GET /api/v1/runs` | run-scoped snapshots (ADR-019) | server | **REPLACED** |
| `batch.ts` | browser batching, `MAX_FILES = 10` | `POST /api/v1/batches`, one child run per file | `BatchResponse` / `BatchFileOut` | per-file status and counts | server | **PENDING** (milestone 2) |
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

## Next milestones

| # | Scope | Depends on | Blockers |
|---|---|---|---|
| 2 | Upload + Batch + Runs on the real API | milestone 1 accepted | none |
| 3 | Product Detail, data quality, field trace, price-history UX with fixture label | 2 | raw row / process trace need backend fields |
| 4 | Dashboard analytics | 2 | none |
| 5 | Appearance | — | none |
| 6 | Favorites page | 3 | cross-run record lookup |
| 7 | Compare | 3 | ADR + batch-scoped cross-run query |
| 8 | Supplier image / URL contract | — | backend contract + rights policy |
| 9 | `ExecutionRun.thresholds` + read-only bands + re-run | — | ADR |
| 10 | Cutover `frontend-next/` → `frontend/` | full parity + user approval | user decision |
