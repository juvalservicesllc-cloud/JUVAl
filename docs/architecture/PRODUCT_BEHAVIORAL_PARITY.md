# JUVAl Product Behavioral Parity Contract

## Status and method

**R3 behavioral audit — 2026-08-19, independently re-verified 2026-08-20 (see "R4 independent verification" below).** This document records observable user
behavior, not merely routes or component names. `demo/` was run at
`http://127.0.0.1:5181/`; production was exercised at
`http://127.0.0.1:5180/` against FastAPI/SQLite. Demo localStorage,
sessionStorage, browser parsing, simulated enrichment, and fixture URLs are
evidence of target behavior only; they are not production data contracts.

Status meanings:

- `FULL`: current production behavior satisfies the target acceptance test.
- `PARTIAL`: the interaction exists but semantics, data, or information parity
  differ.
- `MISSING`: the target behavior is absent.
- `BLOCKED_DATA`: the behavior requires a safe canonical data contract.
- `BLOCKED_PROVIDER`: the behavior requires an authorized external provider.
- `BLOCKED_ADR`: the behavior requires an accepted product/domain decision.

## Behavioral matrix

| # | Surface | Capability | Expected user behavior | Demo evidence | Production evidence | Dependencies | Target status | Acceptance test |
|---:|---|---|---|---|---|---|---|---|
| 1 | Shell | Primary navigation | Navigate Dashboard, Upload, Catalog, Runs | `demo/src/app/App.tsx` buttons | React routes and `AppLayout` | None | FULL | Each destination opens without custom demo router |
| 2 | Shell | Appearance navigation | Open Appearance/Settings from shell | `/appearance` | Settings route | None | FULL | Theme/settings route is reachable |
| 3 | Shell | Responsive navigation | Use navigation on mobile | Demo responsive CSS | Production responsive shell | None | FULL | Four primary destinations remain usable at mobile width |
| 4 | Shell | Light/Dark | Toggle appearance and retain preference | Demo Light/Dark switch | ThemeProvider and appearance storage | None | FULL | Toggle changes semantic surfaces and survives reload |
| 5 | Upload | XLSX submission | Select one workbook and submit to backend | Import accepts CSV/XLSX locally | `RunForm` submits `.xlsx` or `.csv` to FastAPI (ADR-026) | Existing API | FULL | Valid workbook creates a real run |
| 6 | Upload | Client validation | Explain unsupported type/empty selection | Import rejects unsupported files | `RunForm` validation | None | FULL | An unsupported suffix or empty selection is rejected by name with an actionable message; `.csv` and `.xlsx` are both accepted since ADR-026 |
| 7 | Upload | Multi-file queue | Select multiple files, inspect each row, remove individual files | `ImportPage`, `parseBatch` | Ordered queue with per-file rows and individual Remove; `POST /api/v1/batches` creates one child run per file | Multi-file API/run model | FULL | Select two files and see both independently represented |
| 8 | Upload | Ten-file limit | Accept at most ten files and identify overflow | `MAX_FILES = 10`; alert names rejected files | `contract.ts::MAX_FILES` client-side and a `422` from `POST /api/v1/batches` server-side | Multi-file API/run model | FULL | Eleven files yields ten queued and one named rejection |
| 9 | Upload | Per-file validation | One invalid file can fail while valid files continue | `BatchResult.files[]` status/errors | Per-file `REJECTED`/`FAILED` that never aborts siblings; each processed file keeps its own child `ExecutionRun` | Multi-file API/run model | FULL | Mixed batch produces per-file statuses and aggregate result |
| 10 | Upload | Batch summary | Show files, rows, warnings, errors and aggregate status | Import table and Process page | Persisted per-file and aggregate rows/processed/errors/warnings, re-readable via `GET /batches/{id}` | Multi-file run contract | FULL | Completed batch shows file-level and aggregate counts |
| 11 | Upload | Configuration | Set thresholds, fees and persistence before submission | Decision threshold editor/config | Real submitted configuration | Existing API | FULL | Submitted request contains displayed settings |
| 12 | Processing | Honest progress | Show current operation without invented stages/percentages | Demo shows simulated Normalize/Enrich stages | Production shows indeterminate processing | Granular progress not available | FULL | Processing is transparent without false stage claims |
| 13 | Catalog | Run context | Know selected dataset, file, status and record count | Active demo batch/source | Selected `ExecutionRun` context | Existing API | FULL | Context identifies exactly one run |
| 14 | Catalog | Search | Search title/brand/SKU/identity across the run | Local search input | Server-side `search` query | Existing API | FULL | Search changes the canonical query, not only visible rows |
| 15 | Catalog | Decision filter | Filter BUY/REVIEW/PASS | Decision select | Server-side decision filter | Existing API | FULL | Filter persists in query and result count |
| 16 | Catalog | ROI filter | Enter a minimum percentage and filter the full dataset | `Minimum ROI filter %`, `roi * 100` | `percentInputToRatio` converts at the boundary: `30` typed issues `min_roi=0.3` | Query semantics + percentage UX | FULL | `30` means 30% in UI and `0.30` in API |
| 17 | Catalog | Profit filter | Enter minimum profit and filter globally | Minimum Profit input | Server-side `min_profit` | Existing API | FULL | Filter affects pagination and export query |
| 18 | Catalog | Margin filter | Enter minimum percentage and filter globally | Minimum Margin % input | Server-side `min_margin` | Existing API + percentage UX | FULL | Filter uses canonical ratio while UI uses percentage |
| 19 | Catalog | Economic confidence | Choose verified-only or include-inferred economics | Demo status/match labels | `VERIFIED_ONLY` / `INCLUDE_INFERRED` | Existing API | FULL | Mode is explicit in request, chips and values |
| 20 | Catalog | HazMat filter | Filter PRESENT/ABSENT/UNKNOWN without collapsing unknown | Demo Hazmat select | Server-side HazMat filter | Existing API | FULL | UNKNOWN remains distinct from ABSENT |
| 21 | Catalog | Bulky filter | Filter PRESENT/ABSENT/UNKNOWN independently | Demo Bulky select | Server-side Bulky filter | Existing API | FULL | Bulky is not merged into HazMat |
| 22 | Catalog | Provenance filter | Select field and VERIFIED/INFERRED/NOT_FOUND/INVALID | Demo Amazon match filter | Server-side field/status filter | Existing API | FULL | Status semantics remain distinct |
| 23 | Catalog | Server-side sorting | Sort every supported field ascending/descending | `selectCatalog` toggles all listed columns | Allow-listed API sort/direction | Existing API | FULL | Price, COG, profit, ROI, margin, identity, risk and decision each issue global ASC/DESC requests |
| 24 | Catalog | Column visibility | Hide/show optional columns | Demo fixed columns (no visibility control) | Local presentation preference | None | FULL | Hide/show changes only presentation, never records |
| 25 | Catalog | Column ordering | Move columns and retain order | Demo fixed order | Accessible move controls/local preference | None | FULL | Move and reload preserves order |
| 26 | Catalog | Column reset | Restore default columns | No demo reset | Production Reset columns | None | FULL | Reset restores protected defaults |
| 27 | Catalog | Pagination | Move pages and choose page size | Demo page size 20 | Production 25/50/100 server pagination | Existing API | FULL | Page navigation never loads all records |
| 28 | Catalog | Issues | Inspect row issues without losing density | Demo quality/detail views | Production disclosure | Existing API | FULL | Issue count expands to canonical issue text |
| 29 | Catalog | Product identity | Scan title, brand, SKU, ASIN/UPC and source | Title/brand/SKU/source columns | Production identity cells and provenance | Existing fields | FULL | Identity remains readable without image |
| 30 | Catalog | Product thumbnails | See compact image with intentional fallback | `ProductThumbnail`, fixture URL, “No image” fallback | No image field or thumbnails | Canonical image source/rights/provenance | BLOCKED_DATA | Valid source image renders; absent source renders deliberate fallback |
| 31 | Catalog | Full-run export | Download complete persisted run | Local CSV export | Existing complete-run download | Existing API | FULL | Export remains explicitly full-run |
| 32 | Catalog | Filtered export | Export the exact filtered/sorted dataset | Demo exports `shown.all` | Query-equivalent export endpoint | Existing API | FULL | Export request matches current query and sort |
| 33 | Dashboard | Real KPIs | See run totals, decisions, issues and profitability | Demo KPI grid | Backend analytics-backed KPIs | Existing analytics | FULL | Values come from selected persisted run |
| 34 | Dashboard | Decision chart | See decision distribution | Demo Bar | Production Donut/Bar | Existing analytics | FULL | Chart mode changes representation only |
| 35 | Dashboard | Risk charts | See HazMat and Bulky distributions | Demo Bar charts | Production risk visualization | Existing analytics | FULL | HazMat and Bulky remain separate |
| 36 | Dashboard | Provenance chart | See verification/match distribution | Demo Amazon provenance chart | Production provenance visualization | Existing analytics | FULL | VERIFIED/INFERRED/NOT_FOUND remain distinguishable |
| 37 | Dashboard | Profitability summary | See profit/ROI/margin summaries | Demo calculated analytics | Production real summaries | Existing analytics | FULL | No demo economics substitute real values |
| 38 | Dashboard | Supplier discount chart | See largest supplier-price discounts | Demo `priceAnalysis.largestDiscounts` | `price_spread` projection on `GET /runs/{id}/analytics` | Analytics projection | FULL | Chart uses canonical supplier/suggested price fields |
| 39 | Dashboard | Brand distribution chart | See brand mix | Demo `analytics.brands` | `brands` projection, `not_recorded` counted separately | Analytics projection | FULL | Chart is derived from canonical brand values |
| 40 | Dashboard | Issue-type chart | See issue categories, not only total | Demo `issueTypes` chart | `issue_types` projection grouped by canonical issue code | Analytics projection | FULL | Chart groups persisted issue codes |
| 41 | Product Detail | Decision/reasons | See BUY/REVIEW/PASS and reasons immediately | Decision panel | F2 decision panel | Snapshot decision | FULL | Reasons and risk context are visible |
| 42 | Product Detail | Identity/source | See title, brand, identifiers and source context | Image/title/source URL/file/row | Run-scoped identity and source metadata | Image/source URL contract | FULL | Canonical identifiers render; image and safe URL remain absent |
| 43 | Product Detail | Economics | See price, COG, shipping, fees, profit, ROI, margin, thresholds | Explainable metric cards | Core economics and thresholds | Fee/suggested-price fields | FULL | Every available value is formatted and status-labeled |
| 44 | Product Detail | Risks | See HazMat/Bulky and severity/unknown semantics | Separate cards | Separate risk section | Snapshot risk | FULL | UNKNOWN is not presented as safe |
| 45 | Product Detail | Data quality | See missing/invalid fields and issues | Quality facts/groups | Data-quality panel | Snapshot issues/status | FULL | NOT_FOUND/INVALID are not coerced to zero |
| 46 | Product Detail | Full provenance | Expand source, method, evidence, timestamp and raw/unit metadata | `FieldTrace` and process trace | F2 progressive evidence disclosure | F1 provenance payload | FULL | New snapshot metadata is visible without JSON dumping |
| 47 | Product Detail | Legacy provenance | Explain absent detail for historical records | Demo trace exists locally | Explicit legacy notice | Historical snapshot compatibility | FULL | `provenance: null` never fabricates metadata |
| 48 | Product Detail | Fixture market history | Show explicitly labeled illustrative history | 90-day Line/Bar fixture | Deterministic DEMO_FIXTURE Line/Bar | Fixture only | FULL | Banner says DEMO_FIXTURE, NOT VERIFIED and never affects decisions |
| 49 | Product Detail | Provider-backed market history | Show authorized real history when approved | Demo-like target, simulated source | No provider | Authorized provider/data contract | BLOCKED_PROVIDER | Provider source/freshness/provenance are visible |
| 50 | Product Detail | Explanation | Explain deterministic decision, issues and evidence limits | Decision reasons, trace, raw row | F2 reasons/issues/provenance | Existing snapshot | FULL | Explanation cites stored facts only |
| 51 | Product Detail | Actions/navigation | Return to Run/Catalog and use valid download context | Run summary/back actions | F2 Back to Run/Catalog | Existing routes | FULL | Actions do not imply Compare/Save support |
| 52 | Runs | Run history | Browse persisted runs | Demo local run list | Production persisted run list | Existing API | FULL | Runs survive navigation/reload |
| 53 | Runs | Run metadata | See status, timing, counts, warnings/errors | Batch summary | Production run metadata | ExecutionRun | FULL | Metadata matches persisted run |
| 54 | Runs | Open run | Open Run Detail | Demo route | Production route | Existing API | FULL | Route is run-scoped |
| 55 | Runs | Included-file table | Review each file/type/status/rows in a batch | Demo Run Detail file table | Run Detail batch context plus the persisted `/batches/:batch_id` page | Multi-file run model | FULL | Multi-file run exposes per-file rows |
| 56 | Runs | Decision analytics | Review aggregate outcomes | Demo combined stats | Production analytics-backed outcomes | Existing analytics | FULL | Outcomes reconcile with records |
| 57 | Runs | Record review/deep links | Open a specific record and refresh safely | Demo product route | Canonical F1 route | Existing API | FULL | Direct record route returns same snapshot |
| 58 | Runs | Download | Download run output | Demo batch export | Production full-run download | Existing API | FULL | Download preserves run scope |
| 59 | Compare | Contextual comparison | Compare records using approved comparable identity | Demo compare matched products | Not implemented | Comparable-identity ADR | BLOCKED_ADR | No route/button until identity ADR |
| 60 | Saved Opportunities | Save/ownership | Save an opportunity with isolation and persistence | Demo Favorites/localStorage | Not implemented | Auth/ownership/persistence ADR | BLOCKED_ADR | No Favorites as business state |
| 61 | Saved Opportunities | Favorites migration | Reopen saved opportunities | Demo Favorites page | Not implemented | Same as above | BLOCKED_ADR | Saved records are owned and auditable |
| 62 | Compare | Cross-run identity | Resolve comparable identity conflicts | Demo exact-match helper | Not implemented | Comparable-identity ADR | BLOCKED_ADR | ASIN/SKU/URL never silently become global identity |
| 63 | Appearance | Branding controls | Change accent/logo/background with safe local preference | Demo Appearance | Production Appearance controls | None | FULL | Preferences do not become business data |
| 64 | Responsive | Dense mobile surfaces | Use essential columns/cards and controlled overflow | Demo responsive CSS | Production responsive layouts | UI only | FULL | Desktop density is retained without mobile clipping |

## Exact multi-file contract recovered

The demo proves an exact limit of **10 files** (`MAX_FILES = 10`), not merely
“multiple files”. `ImportPage.addFiles` accepts `.csv` and `.xlsx`, slices the
queue to the remaining capacity, and reports unsupported/overflow names. The
queue displays one row per file with type, size, sheet, row counts, status,
notes and Remove. `parseBatch` processes accepted files sequentially in the
browser, aggregates records into one local demo run, preserves per-file
errors, and returns `SUCCESS`, `PARTIAL_SUCCESS`, or `FAILED`. Production
currently accepts one `.xlsx`, produces one `ExecutionRun`, and has no
multi-file API or per-file persistence model.

## Sorting and ROI verification

The demo `selectCatalog` sorts the complete in-memory filtered dataset and
toggles ASC/DESC from headers. Numeric defaults are descending for ROI, profit,
margin and ascending for other fields. Production `ProductsPage` sends
allow-listed server-side `sort` and `direction`; live request inspection
confirmed Price, COG, Profit, ROI and Margin both directions. The remaining
supported keys are Record, SKU, ASIN, Product, Decision, HazMat and Bulky.

The demo ROI input is explicitly percentage-based (`minRoi` compared with
`record.roi * 100`) and participates in filtering, pagination and export.
Production sends the canonical ratio but currently labels the input “Min ROI
(ratio)” and accepts `0.30`, so behavior is functionally present but user
semantics are not yet at parity. The same mismatch exists for margin.

## Chart inventory

| Route | Chart | Type / interaction | Source | Production status |
|---|---|---|---|---|
| Demo Dashboard | Decision distribution | Bar | Derived demo records | Real Donut/Bar preserved |
| Demo Dashboard | Supplier price discounts | Bar | Derived supplier/suggested prices | Missing |
| Demo Dashboard | HazMat distribution | Bar | Demo risk fields | Real equivalent preserved |
| Demo Dashboard | Bulky distribution | Bar | Demo risk fields | Real equivalent preserved |
| Demo Dashboard | Amazon provenance | Bar | Fixture/inferred/not-found | Real provenance equivalent preserved |
| Demo Dashboard | Brand distribution | Bar | Derived brand values | Missing |
| Demo Dashboard | Data-quality issue types | Bar | Derived issue codes | Missing |
| Demo Product Detail | 90-day price history | Line/Bar toggle | Deterministic demo market fixture plus supplier cost | Fixture-only prototype retained with explicit safety label |
| Production Dashboard | Decision distribution | Donut/Bar toggle | Persisted analytics | Implemented |
| Production Dashboard | HazMat/Bulky | Bar | Persisted analytics | Implemented |
| Production Dashboard | Provenance | Bar | Persisted analytics | Implemented |
| Production Product Detail | Price trend | Line/Bar toggle | Deterministic record-ref fixture | Implemented as DEMO_FIXTURE; not provider parity |

Internal analytics (discounts, brand distribution, issue types) are not
provider-blocked: canonical fields/issues exist, but production projections or
endpoints are missing. Only authorized provider-backed market history is
provider-blocked.

## Interaction inventory

| Interaction | Demo | Production | Target |
|---|---|---|---|
| Upload one file | Local parse | Real API | Preserve |
| Upload up to ten | Confirmed queue | Missing | Recover |
| Remove queued file | Confirmed | Missing | Recover |
| Per-file parse status | Confirmed | Missing | Recover |
| Search | Local full-array | Server-side | Preserve server semantics |
| Decision/economic/risk/provenance filters | Local | Server-side | Preserve and percentage-align |
| Sort | Header ASC/DESC | Allow-listed server ASC/DESC | Preserve |
| Column visibility/order/reset | Fixed demo / no control | Production controls | Preserve production |
| Pagination | Local 20 | Server 25/50/100 | Preserve |
| Export filtered | Local shown records | Canonical query export | Preserve |
| Full download | Local batch | Full run | Preserve separately |
| Open detail/run | Local route | Canonical run route | Preserve |
| Chart Line/Bar | Product Detail | Product Detail | Preserve fixture safety |
| Compare | Demo matched-products route | Absent | ADR-blocked |
| Favorites/save | Demo localStorage | Absent | Auth/ownership-blocked |
| Theme/branding | Local preference | Local preference | Preserve |
| Retry/error/empty | Demo state | Real API states | Preserve |

## Parity score

The 64 numbered target behaviors above deliberately keep blocked requirements
in the denominator and do not count `PARTIAL` as implemented:

| Status | Count |
|---|---:|
| FULLY_IMPLEMENTED | 58 |
| PARTIAL | 0 |
| MISSING | 0 |
| BLOCKED_DATA | 1 |
| BLOCKED_PROVIDER | 1 |
| BLOCKED_ADR | 4 |
| **TOTAL REQUIRED** | **64** |

`CURRENT_PRODUCT_PARITY = 58 / 64 = 90.63%` after Waves B-D
(2026-08-19 recovery pass).

Excluding only genuinely external blockers (image data, authorized provider,
and ADR-blocked Compare/Saved/cross-run identity: 6 behaviors),
`IMPLEMENTABLE_PARITY = 58 / 58 = 100%`. **The denominator is unchanged at 64
and 58**: nothing was reclassified to improve the percentage, and the six
blocked behaviors remain in the product contract.

### What changed, 46 -> 58 (2026-08-19)

| # | Capability | From | Evidence |
|---:|---|---|---|
| 7 | Multi-file queue | PARTIAL | CSV+XLSX queue with per-file rows, individual remove, named overflow/unsupported files (`RunForm.test.tsx`, `e2e/recovery.spec.ts`) |
| 9 | Per-file validation | PARTIAL | Unsupported type -> `REJECTED`; unreadable bytes -> `FAILED` child run; siblings keep processing (`test_api.py`) |
| 10 | Batch summary | PARTIAL | Per-file and aggregate rows/processed/errors/warnings, persisted and re-readable (`test_api.py`, `BatchDetailPage.test.tsx`) |
| 12 | Honest progress | PARTIAL | Every submitted file is named while in flight; no invented stage or percentage (`UploadPage.test.tsx`) |
| 16 | ROI filter | PARTIAL | `30` in the UI issues `min_roi=0.3`; chips, export and margin follow the same rule (`ProductsPage.test.tsx`, `e2e/recovery.spec.ts`) |
| 38 | Supplier discount chart | MISSING | `price_spread` projection: selling price minus COG, VERIFIED prices only (`test_run_analytics_projections.py`) |
| 39 | Brand distribution chart | MISSING | `brands` projection with `not_recorded` kept separate (same file) |
| 40 | Issue-type chart | MISSING | `issue_types` grouped by canonical `ProcessingIssue.code` (same file) |
| 42 | Product Detail identity/source | PARTIAL | Source file, row and source type read from stored provenance; image/URL still explicitly absent, which is what this row's acceptance test requires (`ProductDetailPage.test.tsx`) |
| 43 | Product Detail economics | PARTIAL | `total_fees`, `seller_proceeds`, `total_cost` now persisted and shown; absent stays em dash, never `$0.00` (same file) |
| 48 | Fixture market history | PARTIAL | DEMO_FIXTURE / NOT VERIFIED / NOT INFERRED banner asserted; never an input to any decision (same file) |
| 55 | Included-file table | MISSING | Run Detail batch context and the `/batches/:id` page, both from persisted data (`RunDetailPage.test.tsx`, `e2e/recovery.spec.ts`) |

Row 8 (ten-file limit) was already `FULL` in the score after Wave A; the table
cell still read `MISSING` and now matches the count it always had.

### The six that remain

| # | Capability | Status | Exact blocker | Unlock condition |
|---:|---|---|---|---|
| 30 | Catalog product thumbnails | BLOCKED_DATA | `domain.product.ProductInfo.image` exists as a declared `FieldValue[str]` but **nothing ever populates it**: no `COLUMN_SPECS` entry, no importer path, no enrichment adapter, and no approved source, rights, provenance or caching policy. A field shape is not a data source | An approved image source contract, then a populated field and an additive snapshot field |
| 49 | Provider-backed market history | BLOCKED_PROVIDER | No authorized market-data provider | A provider decision covering source, freshness, cost, provenance and failure behavior |
| 59 | Compare | BLOCKED_ADR | No accepted comparable-identity decision | Comparable-identity ADR |
| 60 | Saved Opportunities | BLOCKED_ADR | No ownership/isolation model; `interfaces/api/auth.py` exists but is inactive and has no per-user data model | Auth activation plus ownership/retention decisions |
| 61 | Favorites migration | BLOCKED_ADR | Same as 60 | Same as 60 |
| 62 | Cross-run identity | BLOCKED_ADR | `(execution_id, record_ref)` is deliberately run-scoped | Identity ADR and migration strategy |

The thumbnail *requirement* is preserved, not dropped: the Catalog renders a
fixed-size media slot with an honest unavailable state
(`components/ProductThumbnail.tsx`), so adding a canonical image later is a
data change rather than a table redesign. No image URL is invented, scraped or
copied from a fixture.

## Recovery waves

1. **Wave A — Core multi-file workflow:** approved ten-file queue contract,
   per-file validation/status, aggregate run model, persistence and API.
2. **Wave B — Catalog semantic parity:** percentage ROI/margin inputs,
   user-visible active filters, and query-faithful acceptance tests.
3. **Wave C — Catalog identity/data contract:** canonical image source,
   provenance/rights/fallback/caching, then thumbnails in Catalog and Detail.
4. **Wave D — Internal analytics parity:** supplier discounts, brand mix,
   issue-type analytics and multi-file/source analytics from canonical data.
5. **Wave E — Product Detail completion:** safe source links, richer economics
   fields, and evidence presentation gaps after data contracts are approved.
6. **Wave F — Authorized market history:** provider ADR, freshness/failure
   semantics, verified provenance, then provider-backed Line/Bar.
7. **Wave G — Compare and Saved Opportunities:** comparable identity first;
   authentication/ownership/isolation before saving.

## Git and evidence notes

The repository history contains the production Dashboard/Catalog work in
`9127c64` and the run-scoped Catalog refactor in `800af9f`. The current
`demo/` tree is untracked and has no production commit history to establish a
prior committed production implementation of the ten-file queue, thumbnails,
or demo chart set. Therefore these are `DEMO_ONLY` behavioral requirements
that were never safely migrated, not proven removals from committed
production. Current production sorting/filtering was verified against the live
UI and network requests, not documentation alone.

## R4 independent verification (2026-08-20)

A separate session re-derived this contract from the repository rather than
from this document, because a parity claim that only cites itself is not
evidence. Every capability the previous pass reported was checked in **code**
first and at **runtime** second.

Verified present, not merely documented:

- **Multi-file/batch:** `domain/batch.py` (`Batch`, `BatchFile`, per-file
  counts), the ten-file `422` in `POST /api/v1/batches`, one `ExecutionRun`
  per file, per-file `REJECTED`/`FAILED` isolation that never aborts siblings,
  and `GET /batches/{id}` + `GET /runs/{id}/batch` for durable navigation.
- **CSV:** `SUPPORTED_INPUT_SUFFIXES = {".xlsx", ".csv"}` with `import_file`
  dispatching by suffix into the shared `_import_rows`, exactly as ADR-026
  describes.
- **Catalog:** the export endpoint takes the *same* parameter list as the
  records endpoint and calls the same `list_records`, so filtered export is
  query-faithful by construction rather than by convention.
- **ROI/margin semantics:** `percentInputToRatio` is the single boundary
  conversion; domain ratio semantics are untouched.
- **Adapter parity:** SQLite and Supabase expose the same method set,
  including `save_batch`/`load_batch`/`load_batch_for_run` and the `brands`,
  `issue_types` and `price_spread` projections.
- **Thumbnails:** `ProductThumbnail` renders an honest unavailable state and
  no code path invents an image URL.

Runtime gates, all green on 2026-08-20: 347 backend passed / 7 skipped, 107
frontend, 27 Playwright E2E against real FastAPI + SQLite with the production
build served on `http://127.0.0.1:5180`, `oxlint` clean, `tsc -b` clean,
`vite build` succeeded, `compliance_check.py` PASS (1 pre-existing warning
owned by the compliance workstream), `git diff --check` clean.

**Row 30 blocker hardened by new evidence.** The only product-image source
that has ever existed in this project is `demo/src/adapters/WestMarineCsvAdapter.ts`,
whose columns (`img-fluid src`, `position-relative href`) are CSS-class names
lifted from scraped HTML. Scraping is prohibited as a data source by
`CLAUDE.md` §13 and `DATA_SOURCES.md` §2, so that source cannot be
productionized at any effort level. Row 30 is therefore blocked by the
*absence of a lawful source*, not by missing implementation work -- which is
the strongest possible form of `BLOCKED_DATA`.

Three defects were found and fixed during verification:

1. **Native controls ignored the chosen appearance** (row 4, row 64).
   `ThemeProvider` set every custom property but never declared CSS
   `color-scheme`, so UA-painted controls -- select dropdowns, scrollbars,
   focus rings, autofill -- followed the operating system instead of the
   appearance the operator picked. With the app in Dark on a Light OS, the
   Catalog's nine filter selects rendered as light panels on a dark surface.
   Fixed by `root.style.colorScheme = settings.appearanceMode`, covered by
   `theme/ThemeProvider.test.tsx`, which was confirmed to fail without it.
2. **Duplicated sort mapping.** The Catalog defined its column-to-sort-key map
   twice, risking silent divergence between the header button and the
   `aria-sort` announced on the same cell. Now one module-level
   `COLUMN_SORT_KEY`.
3. **Stale docstring.** The batch endpoint still claimed XLSX-only after
   ADR-026.

Only the first was user-visible; none changed a capability's status.

**No capability changed status in this pass.** The count stands at 58 FULL of
64, implementable 58 of 58. Nothing was reclassified, and neither denominator
moved.

## Non-regression rule

Future phases must reconcile both the current production baseline and this
behavioral target contract. A capability may be blocked, but it may not be
omitted from the target matrix or removed from the UI without an explicit
decision and acceptance test.

## Wave A status correction (2026-08-19)

Production now supports an ordered queue of up to ten XLSX files, isolated
child executions, per-file outcomes and an aggregate batch result. The
ten-file limit is FULL; queue, per-file validation and summary remain PARTIAL
because CSV ingestion, sheet/row previews and durable batch navigation are
not yet available. The denominator remains 64.

## Waves B-D status correction (2026-08-19, later the same day)

The three reasons rows 7/9/10 were held at PARTIAL are resolved:

- **CSV ingestion** is productionized (ADR-026). CSV and XLSX share one header
  resolution, validation and provenance path, verified record-for-record
  against the same fixture in both formats.
- **Durable batch navigation** exists: `GET /api/v1/runs/{id}/batch`, the
  `/batches/:batch_id` route, and links from the Upload result and Run Detail.
  A reload proves the batch is persisted, not page state.
- **Per-file row counts** are persisted on `BatchFile` and shown per file and
  in aggregate.

Sheet previews were *not* implemented and are not required by any of the 64
acceptance tests: the demo's sheet/row preview came from parsing the file in
the browser, which this architecture deliberately does not do. Row counts come
from the real child `ExecutionRun` after the server processed the file, which
is the truthful equivalent.

Sorting, column configuration, pagination, full-run export and filtered export
were re-verified unchanged; the ROI/margin work touched the query the export
issues, so the export now carries the same converted ratio the table used, and
the `query_metadata` sheet states the unit explicitly.

### Known scaling note (not a blocker)

`price_spread` and the profitability summaries stream one row per qualifying
record into Python to do exact `Decimal` arithmetic. At 100k records this is
a few hundred thousand tuples per analytics call -- the same pattern the
profitability summaries have always used, not a new class of problem. If a run
size makes it measurable, the fix is to push `count`/`average` into SQL and
keep only `ORDER BY ... LIMIT 5` in Python. Not done now: no measured problem
exists, and guessing at the threshold would be speculative optimization.

The denominator remains 64, and the implementable denominator remains 58.
