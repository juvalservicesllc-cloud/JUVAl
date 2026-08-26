# frontend-next — Golden data-layer migration matrix

**2026-08-26.** Companion to ADR-030. Tracks, module by module, how the Golden
application's data layer is replaced by real backend contracts in
`frontend-next/`.

`demo/` stays byte-identical (`demo/src` SHA-256
`a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`) and remains
the reference for every Golden UI not yet migrated. Nothing below is deleted
from the product — only from the production candidate's runtime.

## Status

| Surface | State |
|---|---|
| Golden shell / navigation | **DONE** (m1) |
| Catalog on the real API | **DONE** (m1) — server-side search, filters, sort, pagination, export |
| Favourites | **DONE** (m1) — browser-local, run-scoped, labelled, no request |
| Provenance | **DONE** (m1) — every economic value renders with its verification status |
| Dependency reproducibility | **DONE** (m2) — lockfile + verified `npm ci` |
| Upload → real batch | **DONE** (m2) |
| Batch detail | **DONE** (m2) |
| Runs list | **DONE** (m2) |
| Run detail (minimum) | **DONE** (m2) |
| Dashboard, Product Detail, Appearance, Compare, Favorites page | **NOT WIRED** — honest placeholder, no fixture data |

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
| catalog filters / sort / page | `EPHEMERAL_UI` (session persistence is a later step) |
| selected run id | `EPHEMERAL_UI`, seeded from the URL |
| favourites | `LOCAL_PREFERENCE` |
| appearance (dark) | `LOCAL_PREFERENCE` |
| batch id, per-file status, execution ids | `SERVER_BATCH_STATE` |
| run status, counts, hashes, records | `SERVER_RUN_STATE` |

No server truth is held in `localStorage`.

## Next milestones

| # | Scope | Depends on | Blockers |
|---|---|---|---|
| 3 | Product Detail, data quality, field trace, price-history UX with fixture label | 2 | raw row / process trace need backend fields |
| 4 | Dashboard analytics | 2 | none |
| 5 | Appearance | — | none |
| 6 | Favorites page | 3 | cross-run record lookup |
| 7 | Compare | 3 | ADR + batch-scoped cross-run query |
| 8 | Supplier image / URL contract | — | backend contract + rights policy |
| 9 | `ExecutionRun.thresholds` + read-only bands + re-run | — | ADR |
| 10 | Cutover `frontend-next/` → `frontend/` | full parity + user approval | user decision |
