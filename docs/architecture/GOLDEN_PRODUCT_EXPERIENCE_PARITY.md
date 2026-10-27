# Golden Product Experience — Whole-Application Parity Matrix

## Status and method

**2026-08-26.** Authoritative migration matrix for the **entire application**.
Supersedes the *scope* of `CATALOG_GOLDEN_UX_PARITY.md` (V1) and
`CATALOG_GOLDEN_UX_PARITY_V2.md` (V2), which remain valid and unaltered for the
Catalog surface and are referenced from here rather than duplicated.

Per ADR-029 and the user's clarification: `demo/` is the **Golden Product
Experience for the whole application** — not only its Catalog, and not only a
visual reference. It contains functionality already built. `frontend/` is the
production integration target.

**Method.** Every executable file under `demo/src` (67 files) and every
production route, page and shared component was read, then traced to the
FastAPI contract (`interfaces/api/main.py`, `models.py`), the SQLite record
store and the tabular importer. Both apps were run side by side and captured.
Golden stayed byte-identical throughout: `demo/src` SHA-256
`a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`.

**Capability ≠ data source.** A capability whose Golden data is `DEMO_FIXTURE`
is still a real capability. It may be recovered as presentation with the fixture
label intact; its *values* stay blocked until an authorized source exists.

### Classification

`PRODUCTION_ALREADY_SUPERIOR` · `PRODUCTION_EQUIVALENT` ·
`GOLDEN_CAPABILITY_MISSING` · `GOLDEN_UX_SUPERIOR` ·
`REQUIRES_PRODUCTIONIZATION` · `REQUIRES_BACKEND_CONTRACT` · `REQUIRES_ADR` ·
`FIXTURE_PRESENTATION_ONLY` · `OBSOLETE` · `UNKNOWN`

---

## 1. Route inventory

| Golden route | Golden page | Production route | Production page | Status |
|---|---|---|---|---|
| `/` | `DashboardPage` | `/` | `DashboardPage` | both |
| `/import` | `ImportPage` | `/upload` | `UploadPage` | both |
| `/process` | `ProcessPage` | — (folded into Upload) | — | Golden-only |
| `/catalog` | `CatalogPage` | `/products` | `ProductsPage` | both |
| `/compare` | `ComparePage` | — | — | **Golden-only** |
| `/favorites` | `FavoritesPage` | — (star recovered in Catalog) | — | **Golden-only** |
| `/runs` | `RunsPage` | `/runs` | `RunsPage` | both |
| `/run/:id` | `RunDetailPage` | `/runs/:executionId` | `RunDetailPage` | both |
| `/run/:id/file/:fid/product/:ref` | `ProductDetailPage` | `/runs/:executionId/records/:recordRef` | `ProductDetailPage` | both |
| `/appearance` | `AppearancePage` | `/appearance` | `AppearancePage` | both |
| `/about-demo` | `AboutDemoPage` | — | — | Golden-only (demo disclosure) |
| — | — | `/batches/:batchId` | `BatchDetailPage` | **Production-only** |
| `*` | `NotFoundPage` | — (no catch-all route) | — | **Golden-only** |

---

## 2. GLOBAL / SHELL

| Capability | Golden files | Golden behavior | Production | Backend | Status | Class | Action |
|---|---|---|---|---|---|---|---|
| Sidebar navigation | `app/App.tsx` | 9 flat items, plain buttons | `AppLayout.tsx` — 4 items + Phosphor icons, active state, **collapsible**, persisted | n/a | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Route count in nav | `app/App.tsx` | 9 destinations | 4 + Appearance via gear | n/a | Golden exposes more surfaces | `GOLDEN_UX_SUPERIOR` | revisit as Compare/Favorites land |
| Header / topbar | `app/App.tsx` | demo banner + light/dark button | breadcrumb-ish context, env badge, primary CTA, settings | n/a | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Router | `history.pushState` + regex | hand-rolled | `react-router-dom`, lazy routes, code splitting | n/a | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| **404 / catch-all** | `NotFoundPage.tsx` | explicit page + return CTA | **no catch-all `Route`** — unknown URL renders an empty shell | n/a | **missing** | `GOLDEN_CAPABILITY_MISSING` | small, safe, no backend — add a `*` route |
| Internal nav | buttons + `<a href>` | same tab | `Link`/`NavLink`, same tab | n/a | equivalent | `PRODUCTION_EQUIVALENT` | — |
| External nav | `target="_blank" rel="noopener noreferrer"` on supplier URL | new tab | none (no URL field) | none | missing with its data | `REQUIRES_BACKEND_CONTRACT` | with supplier-URL contract |
| Global notice/alert | `App.tsx` `notice` + `role="alert"` | one shared banner | per-page error states | n/a | different shape | `PRODUCTION_EQUIVALENT` | — |
| Mobile nav | CSS: sidebar becomes horizontal scroller | basic | fixed bottom nav bar, 4 items | n/a | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Dark-mode contrast | `style.css` `:root` colour leak | **headings/cells render dark-on-dark** | token system, correct in both modes | n/a | Golden defect | `OBSOLETE` | do **not** copy |

---

## 3. DASHBOARD

| Capability | Golden | Production | Backend | Status | Class | Action |
|---|---|---|---|---|---|---|
| KPI tiles | 11 (Files, Valid, Invalid, Total, BUY, REVIEW, PASS, Issues, Profit, Avg ROI, Avg margin) | 4 (Total, With issues, Avg ROI, Avg profit) + decision counts in the chart | yes | different split | `GOLDEN_UX_SUPERIOR` (density) | consider a compact KPI strip |
| Decision distribution | Bar only | **Donut + Bar toggle** | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Profitability summary | avg only | **avg / min / max / count**, VERIFIED-only | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| HazMat / Bulky charts | status only | status **+ severity** (ADR-020) | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Provenance breakdown | Amazon-match bar | per-field VERIFIED/INFERRED/NOT_FOUND/INVALID | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Brand distribution | top-8 | `brands` + distinct + `not_recorded` counted separately | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Data-quality issue types | by message string | by canonical `ProcessingIssue.code` | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Supplier price discounts | top-5 by amount | `price_spread` + avg + at-or-below-COG + % of price | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Chart text summaries (a11y) | one-line text | `ChartTextSummary` per chart | n/a | production richer | `PRODUCTION_ALREADY_SUPERIOR` | — |
| **Opportunity ranking** | top-5 by profit, each linking to Product Detail, labelled simulated | **absent** | ranking contract not approved | **missing** | `REQUIRES_ADR` | needs an approved ranking/evidence policy |
| **Multi-source analytics table** | per-file row: records, BUY/REVIEW/PASS, avg ROI, avg profit, issues, fixture/inferred/not-found | **absent** | expressible over a batch's child runs | **missing** | `REQUIRES_PRODUCTIONIZATION` | Batch Detail is the natural home |
| **Analytics source filter** | select one file inside the batch | run selector (one run = one file) | yes | superseded | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Cross-file match banner | "N exact matches → Compare" | absent | depends on Compare | missing | `REQUIRES_ADR` | with Compare |
| Empty state | hero + "RUN WEST MARINE DEMO" CTA | explicit empty + Upload CTA | yes | equivalent | `PRODUCTION_EQUIVALENT` | — |
| Recent runs list | — | 6 most recent, links | yes | production-only | `PRODUCTION_ALREADY_SUPERIOR` | — |

---

## 4. UPLOAD / IMPORT / PROCESS

| Capability | Golden | Production | Backend | Status | Class | Action |
|---|---|---|---|---|---|---|
| Multi-file queue | `MAX_FILES = 10` | `MAX_FILES = 10` | `POST /batches` | equivalent | `PRODUCTION_EQUIVALENT` | — |
| **Drag & drop zone** | `.drop-zone` with dragenter/over/leave/drop + `.dragging` state | **plain `<input type=file>` only** | n/a | **missing** | `GOLDEN_CAPABILITY_MISSING` | frontend-only, no backend — good early win |
| Per-file remove | ✓ | ✓ | n/a | equivalent | `PRODUCTION_EQUIVALENT` | — |
| Queue counter | `n / MAX_FILES` | `n of MAX_FILES queued` | n/a | equivalent | `PRODUCTION_EQUIVALENT` | — |
| Rejected-file feedback | names overflow + unsupported type | names overflow | n/a | near-equivalent | `PRODUCTION_EQUIVALENT` | — |
| CSV + XLSX | Papa Parse / `xlsx` in browser | server-side importer (ADR-026) | yes | production authoritative | `PRODUCTION_ALREADY_SUPERIOR` | — |
| **Pre-submit preview** | parses in-browser and previews rows/warnings **before** processing | absent | `POST /api/v1/runs/preview` (2026-10-26): importer verdict, rows scanned/importable, issues | **missing in UI** | `GOLDEN_CAPABILITY_MISSING` | frontend only; Golden's row preview is not copied, the server importer is the authority |
| **Column classification preview** | `classifyColumns()` — USED / OPTIONAL / IGNORED + canonical name + rationale; `detectWestMarine()` gives format + confidence % + missing columns | absent | `POST /api/v1/runs/preview` (2026-10-26) returns each header's importer decision (MAPPED/UNKNOWN/DUPLICATE/BLANK), canonical, alias, target, required, group and the missing required columns | **missing in UI** | `GOLDEN_CAPABILITY_MISSING` | frontend only; no format "confidence %" is produced -- JUVAl has one tabular contract, not detected supplier formats |
| Processing stages | 12 named stages, all flipped to COMPLETE | honest indeterminate status naming every submitted file | API has no granular progress | Golden's is decorative | `OBSOLETE` | do **not** copy fake stages |
| Per-file result / partial success | ✓ | ✓ `BatchFileOut` with per-file status, counts, errors | yes | equivalent | `PRODUCTION_EQUIVALENT` | — |
| Thresholds / fees at submit | local policy | real submitted configuration | yes | production authoritative | `PRODUCTION_ALREADY_SUPERIOR` | — |
| Navigation after processing | → `/process` | → Review run / Open batch | yes | equivalent | `PRODUCTION_EQUIVALENT` | — |

---

## 5. CATALOG

Fully covered in **`CATALOG_GOLDEN_UX_PARITY_V2.md`** (search, filters, sort,
columns, pagination, export, thumbnails, favourites, decision policy) and
closed through Wave B3. Summary only:

| | |
|---|---|
| Recovered | favourite star (run-scoped, local), profit-desc default, media slot, pill sort headers, single-line rows, readable provenance, export row count, decision-first column order |
| Production superior | confidence mode, provenance filters, server-side everything, column visibility + ordering, pagination |
| Still missing | brand filter dropdown (backend `brand` param delivered 2026-10-26; frontend pending), product image (`REQUIRES_BACKEND_CONTRACT`), decision-threshold bands (`REQUIRES_ADR`) |

---

## 6. COMPARE

| Aspect | Finding |
|---|---|
| Golden files | `pages/ComparePage.tsx`, `matching.ts` |
| Selection model | **None.** Not user selection — Compare auto-groups. There is no basket, no checkbox, no persisted selection |
| Identity logic | `identifierOf()` = the **supplier product URL**, lowercased/trimmed. ASIN is deliberately rejected ("a `DEMO_FIXTURE`, not a real identifier"). No SKU/UPC exist in this source |
| Scope | Groups only where the same URL appears in **≥2 distinct source files of the same batch**. Fuzzy matching explicitly out of scope; everything else is `NO_MATCH` |
| Comparison dimensions | Supplier cost, selling price, profit, ROI, margin (best value highlighted, `lowerIsBetter` for cost), plus decision, HazMat, Bulky, Amazon provenance, issues |
| Honesty | "arithmetic highlights are informational only, never a claim of 'better' where data is missing" |
| Persistence | None — recomputed per render |
| Navigation | Each cell links to that file's Product Detail; "Back to Catalog" |
| Production equivalent | **None** |
| Backend | Needs a **cross-run record query** (records across the child runs of one batch); no endpoint exposes it |
| Production advantage | Production has *real* ASIN, UPC and supplier SKU — **stronger** identifiers than Golden's URL |
| Classification | `REQUIRES_ADR` + `REQUIRES_BACKEND_CONTRACT` |
| What is required | (1) ADR deciding the comparable-identity rule within a batch — ADR-011/ADR-012 deliberately refuse a *global* product identity, and this must not become one; (2) a batch-scoped multi-run record query; (3) UI |

**Not dismissed. On the roadmap.**

---

## 7. FAVORITES

| Aspect | Golden | Production |
|---|---|---|
| Star toggle | Catalog row, `★`/`☆` | **recovered** (Wave B2/B3), Phosphor star |
| Key | `runId:sourceFileId:recordRef` | `executionId:recordRef` (one run per file makes the middle segment redundant) |
| Storage | `localStorage` `juval.demo.favorites.v2` | `localStorage` `juval.catalog.favorites.v1` |
| Disclosure | none | header "Favorite (local)" + "starred in this browser only" chip |
| Corrupt storage | returns `[]` | returns `[]`, catalog still renders (tested) |
| Backend calls | none | none (asserted by test) |
| **Favorites page** | grid of starred products with image, title, source file, decision, profit, ROI, remove button, **source-file filter**, empty state + "Browse Catalog" CTA | **absent** |
| Cross-run scope | iterates **all** runs, not just the active one | n/a — no page yet |

**Star: `REQUIRES_PRODUCTIONIZATION` → done.**
**Page: `REQUIRES_PRODUCTIONIZATION`** — frontend-only for a single run; a
cross-run page needs a multi-run record lookup (`REQUIRES_BACKEND_CONTRACT`),
since production stores no records client-side.

Open product question (not a blocker): whether favourites should become owned,
server-side, shareable data. Until decided they stay a labelled local preference,
consistent with column layout and theme.

---

## 8. RUNS / RUN DETAIL / BATCH

| Capability | Golden | Production | Backend | Status | Class |
|---|---|---|---|---|---|
| Run list | local runs, filename, status badge, file count, records, BUY/REVIEW/PASS, timestamp | persisted runs, sortable table, status, counts | yes | production authoritative | `PRODUCTION_ALREADY_SUPERIOR` |
| Open run | ✓ | ✓ | yes | equivalent | `PRODUCTION_EQUIVALENT` |
| **Per-run decision counts in the list** | BUY/REVIEW/PASS inline on every row | not in the list | `decisions` on every `RunSummaryOut` (2026-10-26, one grouped query) | Golden scannable at a glance | `GOLDEN_UX_SUPERIOR` — frontend only |
| **Duplicate / reprocess** | clones the stored run **without recomputing** | absent | no re-run contract | Golden's is a copy, not a reprocess — misleading | `REQUIRES_ADR` |
| **Delete / reset runs** | destructive, local, `confirm()` | absent | no retention/authorization policy | missing | `REQUIRES_ADR` |
| Batch grouping | one run holds many files (`files[]`) | **one child `ExecutionRun` per file**, grouped by `batch_id` | yes | **production architecture is stronger** (per-file provenance, per-file audit) | `PRODUCTION_ALREADY_SUPERIOR` |
| Batch detail page | inside Run Detail | dedicated `/batches/:batchId` + `BatchSummary` | yes | production-only | `PRODUCTION_ALREADY_SUPERIOR` |
| Included-files table | file, type, status, rows detected, rows processed, notes | `BatchFileOut`: ordinal, filename, type, size, status, counts, warnings, errors, link to child run | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Run → Catalog handoff | ✓ | ✓ "Continue in Catalog" | yes | equivalent | `PRODUCTION_EQUIVALENT` |
| Download / export | local CSV of the run | real full-run download + filtered export | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Combined stats | total, BUY/REVIEW/PASS, avg ROI, demo profit | run metric grid + backend-aggregated decision outcomes | yes | equivalent | `PRODUCTION_EQUIVALENT` |

---

## 9. PRODUCT DETAIL

| Capability | Golden | Production | Backend | Status | Class |
|---|---|---|---|---|---|
| Decision + reasons | panel + first reason | decision summary + reasons | yes | equivalent | `PRODUCTION_EQUIVALENT` |
| **Threshold context on the decision** | "Review from 15%, Buy from 35%" | absent | run does not record its thresholds | missing | `REQUIRES_ADR` |
| Identity | title, brand, ASIN | title, brand, SKU, ASIN, UPC, marketplace, record_ref | yes | production richer (real ASIN) | `PRODUCTION_ALREADY_SUPERIOR` |
| **Product image** | real supplier image from `img-fluid src` | explicit no-image state | **no image field in `RecordOut`** | missing | `REQUIRES_BACKEND_CONTRACT` |
| **External supplier link** | "Open supplier source", new tab | absent | **no URL field** | missing | `REQUIRES_BACKEND_CONTRACT` |
| Source panel | file, type, row number, adapter name | field-level source/source_reference | partial | Golden names the adapter and row | `GOLDEN_UX_SUPERIOR` |
| Economics | 9 cards | + break-even, max-COG target profit/ROI, total fees, seller proceeds, total cost | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| **Explainable metric cards** | every metric shows a provenance label **and** a "What does this mean?" disclosure | values + status badges, no per-metric explanation | n/a | missing | `REQUIRES_PRODUCTIONIZATION` (frontend-only) |
| Risk | status | status **+ severity** (ADR-020) | yes | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Data quality | **grouped by provenance** (`VERIFIED_SOURCE`/`DEMO_FIXTURE`/`INFERRED`/`NOT_FOUND`/`INVALID`) + coded facts with category/severity | issue list + count | yes | Golden groups more legibly | `GOLDEN_UX_SUPERIOR` |
| Field-level trace | `FieldTrace`: source column, raw value, normalized value, provenance, transformation; for calculated fields: inputs + formula | provenance panel with per-field evidence disclosure | yes | Golden names column/formula | `GOLDEN_UX_SUPERIOR` |
| **Process trace** | `SOURCE_IMPORTED → NORMALIZED → … → DECISION_CALCULATED` | absent | not persisted | missing | `REQUIRES_BACKEND_CONTRACT` |
| **Raw source row** | `<details>` with the full raw row JSON | absent | raw row not persisted | missing | `REQUIRES_BACKEND_CONTRACT` |
| Market history chart | 90-day line/bar, `DEMO_FIXTURE` | **present**, Line/Bar toggle, louder `DEMO_FIXTURE / NOT VERIFIED` banner | none either side | equivalent | `FIXTURE_PRESENTATION_ONLY` |
| **Price KPI tiles** | current / 90-day avg / low / high | absent | fixture-derived | missing | `FIXTURE_PRESENTATION_ONLY` |
| Not-found handling | run-not-found vs record-not-found, distinct copy | loading/error/404 states | yes | equivalent | `PRODUCTION_EQUIVALENT` |
| Actions | back to run summary | back to Run Detail / Catalog | yes | equivalent | `PRODUCTION_EQUIVALENT` |
| Favourite / compare from detail | — (Golden has neither here) | — | — | n/a | — |

---

## 10. APPEARANCE / PERSONALIZATION

| Capability | Golden | Production | Status | Class |
|---|---|---|---|---|
| Light / dark | class toggle, `role="switch"` | `ThemeProvider`, mode switch, token system | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Accent colour | 1 (`--accent`) | **8 tokens** (accent, sidebar, header, background, surface, text, muted, border) | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Graphite / charcoal | hard-coded dark palette | `theme/presets.ts` + full customisation | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Logo | data URL, any size | data URL + **type and 400 KB limits** | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Background image | data URL | data URL + **fit (cover/contain) + position + overlay** | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Overlay | slider 0–0.95 | slider 0–0.9 with % readout | equivalent | `PRODUCTION_EQUIVALENT` |
| Contrast safety | none | **contrast warning** when text/surface is too close | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Live preview | text + accent-coloured heading | full preview canvas (nav, card, accent, text) | production richer | `PRODUCTION_ALREADY_SUPERIOR` |
| Reset | `confirm()` → defaults | `confirm()` → defaults | equivalent | `PRODUCTION_EQUIVALENT` |
| Persistence | `localStorage` `juval.demo.brand.v1` | `localStorage` via `theme/storage.ts` + storage-error surface | production richer | `PRODUCTION_ALREADY_SUPERIOR` |

**Rendered comparison confirms production is superior on this surface** — the
only Golden element not present is its `--accent` being applied to
`document.documentElement` directly, which production does through tokens.

---

## 11. CHARTS / ANALYTICS

| Chart | Golden type | Golden data | Production type | Production data | Class |
|---|---|---|---|---|---|
| Decision distribution | Bar | demo decisions | **Donut + Bar** | real decisions | `PRODUCTION_ALREADY_SUPERIOR` |
| HazMat / Bulky | Bar | simulated | Bar + severity text summary | real status/severity | `PRODUCTION_ALREADY_SUPERIOR` |
| Amazon provenance | Bar | fixture | provenance breakdown per field | real statuses | `PRODUCTION_ALREADY_SUPERIOR` |
| Brand distribution | Bar (top 8) | supplier brand | Bar + distinct + not_recorded | supplier brand | `PRODUCTION_ALREADY_SUPERIOR` |
| Issue types | Bar | message strings | Bar | canonical codes | `PRODUCTION_ALREADY_SUPERIOR` |
| Supplier price discounts | Bar (top 5) | derived | Bar + avg + at-or-below-COG + % | VERIFIED price & recorded COG only | `PRODUCTION_ALREADY_SUPERIOR` |
| **Price history** | **Line ⇄ Bar toggle** | `DEMO_FIXTURE` | **Line ⇄ Bar toggle** | `DEMO_FIXTURE`, banner | `FIXTURE_PRESENTATION_ONLY` |
| Chart text alternative | one summary line | `ChartTextSummary` component per chart | n/a | `PRODUCTION_ALREADY_SUPERIOR` |
| Chart library | `recharts` | `recharts` | — | `PRODUCTION_EQUIVALENT` |

**No chart type exists in Golden that production lacks.** The only chart-level
gap is the price **KPI tiles**, not the chart.

---

## 12. IMAGES / THUMBNAILS

| Question | Finding |
|---|---|
| Where do Golden images come from? | The `img-fluid src` column of the supplier's own West Marine export CSV. `WestMarineCsvAdapter` maps it to canonical `image_url`, next to `position-relative href` → `supplier_url` |
| Is JUVAl scraping? | **No.** The URL is read from a file the user supplied. No marketplace is contacted by the demo |
| Provenance | `quality.ts` classifies a present image as `VERIFIED_SOURCE` (supplier-declared), absent as a `MISSING_image_url` warning |
| Where rendered | Catalog thumbnail (44px, "No image" fallback), Product Detail hero image (`onError` → hide), Favorites card |
| Production today | Fixed media slot with an explicit unavailable state; a test asserts **no `<img>`** is emitted while no canonical field exists |
| Blocker | `RecordOut` has no image field; the importer has no image column; no rights/caching/provenance policy |
| Class | `REQUIRES_BACKEND_CONTRACT` |
| Correct framing | "Preserve an image URL the supplier file already provides, **with provenance**" — a legitimate roadmap capability, not fabricated UI |

---

## 13. FILTERS / SORT / EXPORT (all screens)

| Filter | Golden screen(s) | Production | Backend | Class |
|---|---|---|---|---|
| Search | Catalog | Catalog (5 fields, server) | yes | `PRODUCTION_ALREADY_SUPERIOR` |
| Decision | Catalog | Catalog | yes | `PRODUCTION_EQUIVALENT` |
| **Brand** | Catalog | — (free-text search only) | `brand` exact match (2026-10-26) | `GOLDEN_CAPABILITY_MISSING` — frontend only |
| ROI / profit / margin | Catalog | Catalog, confidence-aware | yes | `PRODUCTION_ALREADY_SUPERIOR` |
| HazMat / Bulky | Catalog | Catalog | yes | `PRODUCTION_EQUIVALENT` |
| Amazon match | Catalog | `provenance_field` × `provenance_status` | yes | `PRODUCTION_ALREADY_SUPERIOR` |
| Confidence | — | Catalog | yes | `PRODUCTION_ALREADY_SUPERIOR` |
| **Source file** | Catalog, Dashboard, **Favorites** | run selector (1 run = 1 file) | yes | `PRODUCTION_ALREADY_SUPERIOR` for Catalog/Dashboard; **missing on a Favorites page** |
| Data-quality filter | — | — | — | neither |
| Date / run / batch | — | run selector; batch page | yes | `PRODUCTION_EQUIVALENT` |
| Default sort — Catalog | `profit:desc` | `profit:desc` (Wave B3) | yes | `PRODUCTION_EQUIVALENT` |
| Default sort — Runs | newest first | `started_at DESC` | yes | `PRODUCTION_EQUIVALENT` |
| Export — full run | ✓ | ✓ | yes | `PRODUCTION_EQUIVALENT` |
| Export — filtered view | ✓ (`shown.all`) | ✓ canonical query-equivalent | yes | `PRODUCTION_EQUIVALENT` |
| **Export columns** | 22 incl. `batch_id`, `source_filename`, `source_row_number`, `supplier_url`, `amazon_provenance` | canonical export | partial | Golden carries source-file + URL columns production has no field for | `REQUIRES_BACKEND_CONTRACT` |

---

## 14. DECISION CONFIGURATION

| Aspect | Golden | Production |
|---|---|---|
| Controls | Review ROI %, Buy ROI % — editable inline on Catalog | none |
| Model | `DemoDecisionPolicy { modelVersion, reviewRoiThreshold, buyRoiThreshold }` |`Thresholds` submitted at run creation |
| Validation | `validDecisionPolicy`: finite, ≥0, review ≤ buy | backend validates |
| Effect | `applyDecisionPolicy()` re-runs `decideDemo` over stored records and **saves the new decisions over the old ones** | decisions are immutable once persisted |
| Display | band pills `PASS < 15% / REVIEW 15–34.99% / BUY ≥ 35%`, and on Product Detail | absent |
| Risk precedence | "Risk and other blockers still take precedence" | same rule in the engine |

**Verdict.** The editor must **not** be copied. Rewriting a historical decision
from the frontend destroys reproducibility, and `ExecutionRun` does not record
the thresholds a run used (`CLAUDE.md` §15), so a changed decision would be
unattributable.

Required architecture: (1) persist `thresholds` on `ExecutionRun`; (2) display
the bands **read-only** on Catalog and Product Detail; (3) "change thresholds"
creates a **new** run. Steps 1 and 3 are model changes → `REQUIRES_ADR`.
Step 2 becomes trivial once step 1 lands.

---

## 15. STATE / PERSISTENCE MAP

| Golden state | Key | Contents | Recommended production home |
|---|---|---|---|
| Runs + records | `juval.demo.runs.v1` | whole run objects, schema-guarded, corrupt-tolerant | **SERVER_STATE** — already `ExecutionRun` + record snapshots |
| Active run | `juval.demo.active-run` | run id | **LOCAL_PREFERENCE** (production keeps it in component state) |
| Favourites | `juval.demo.favorites.v2` | `runId:sourceFileId:recordRef[]` | **LOCAL_PREFERENCE** today (recovered); candidate **USER_STATE** if ownership is ever decided |
| Appearance / brand | `juval.demo.brand.v1` | accent, logo, background, overlay | **LOCAL_PREFERENCE** — production equivalent exists |
| Dark mode | `juval.demo.dark` | boolean | **LOCAL_PREFERENCE** — production equivalent exists |
| Catalog filters | `sessionStorage juval.demo.catalog` | full `CatalogState` incl. filters, sort, page | **LOCAL_PREFERENCE** — production persists columns only; **filters are not persisted** → `GOLDEN_UX_SUPERIOR`, frontend-only recovery |
| Decision policy | on the run object | thresholds | **RUN_STATE** — must move to `ExecutionRun` (ADR) |
| Compare selections | none (recomputed) | — | **NOT_PERSISTED** |
| Column layout | — | — | production-only `LOCAL_PREFERENCE` |
| Sidebar collapsed | — | — | production-only `LOCAL_PREFERENCE` |

---

## 16. DATA / PROVENANCE AUDIT

| Field | Golden | Production | Leak risk |
|---|---|---|---|
| ASIN | generated, `DEMO_FIXTURE`/`INFERRED`/`NOT_FOUND` | real `FieldValue` + status | none |
| Selling price / fees / shipping | simulated from a hash | real `FieldValue` | none |
| Weight / dimensions | simulated | real, canonical units | none |
| HazMat / Bulky | simulated | real status + severity | none |
| Profit / ROI / margin | computed from fixtures | backend `Decimal`, weakest-link status | none |
| Supplier cost / suggested price | **real**, from the supplier CSV | cost real; **suggested price has no field** | none |
| Supplier URL / image | **real**, supplier-declared | absent | none |
| Market history | `DEMO_FIXTURE` | `DEMO_FIXTURE` + banner | none |
| Decision | demo engine, mutable | backend engine, immutable | none |

**No `DEMO_FIXTURE` has entered production as `VERIFIED`. No demo value, image
URL or market series has been copied into production.**

---

## 17. Production capabilities Golden never had

Auth/RBAC (ADR-022, inactive) · server-side query/pagination at scale ·
confidence mode · per-field provenance filters · column visibility + ordering ·
risk severity (ADR-020) · break-even / max-COG · fee breakdown · batch as a
first-class resource with per-file child runs · donut charts · min/max/count
summaries · chart text alternatives · contrast warning · asset size limits ·
lazy routes / code splitting · PWA · reproducible locale-pinned formatting ·
bottom mobile nav · collapsible sidebar.

---

## 18. Golden capabilities missing from production — consolidated

| # | Capability | Class | Blocker |
|---|---|---|---|
| 1 | 404 / catch-all route | **RECOVERED** (C1.1) | — |
| 2 | Upload drag & drop zone | **RECOVERED** (C1.2) | — |
| 3 | Catalog filter persistence across navigation | **RECOVERED** (C1.3) | — |
| 4 | Explainable metric cards on Product Detail | **RECOVERED** (C1.4) | — |
| 5 | Provenance-grouped data quality on Product Detail | **RECOVERED** (C1.5) | — |
| 6 | Per-run decision counts in the Runs list | **RECOVERED** (§22, `frontend-next/`) | — |
| 7 | Favorites page | **PARTIALLY_RECOVERED** (§24, `frontend-next/`) — one run at a time with a run selector; title, source file, decision, profit, ROI, remove, empty state + Catalog CTA | Golden's all-runs-at-once view needs a cross-run lookup; no product image (item 11) |
| 8 | Dashboard KPI density (11 vs 4) | **RECOVERED** (§23, `frontend-next/`) — all 11: file counts from the run's batch (single-file runs say why there are none), profit total = backend `sum` of verified unit profit, labelled as such; `frontend/` stays 8 of 11 (C1.6) | — |
| 9 | Price history KPI tiles | `FIXTURE_PRESENTATION_ONLY` | must keep the fixture label |
| 10 | Brand filter dropdown | **RECOVERED** (§22, `frontend-next/`) — options limited to the run's top 10 brands | listing every brand needs the analytics `brands` limit reviewed |
| 11 | Product image | `REQUIRES_BACKEND_CONTRACT` | image field + rights/caching policy |
| 12 | Supplier source URL + external link | `REQUIRES_BACKEND_CONTRACT` | URL field + rights policy |
| 13 | Raw source row disclosure | `REQUIRES_BACKEND_CONTRACT` | raw row not persisted |
| 14 | Process trace | `REQUIRES_BACKEND_CONTRACT` | trace not persisted |
| 15 | Column classification / format-detection preview | **RECOVERED** (§22, `frontend-next/`) — column classification; format detection with a confidence % deliberately not reproduced | — |
| 16 | Pre-submit file preview | **RECOVERED** (§22, `frontend-next/`) — importer verdict per file, not a browser row preview | — |
| 17 | Suggested/list price field | **RECOVERED** (§25, ADR-053) — supplier suggested price as declared evidence: Catalog column + Product Detail panel, with its declared currency and INFERRED status; not sortable | — |
| 18 | Multi-source analytics table | **RECOVERED** (§23, `frontend-next/` Batch Detail) — one row per child run from its own analytics; Golden's fixture column has no production equivalent (no fixtures) | — |
| 19 | Compare | `REQUIRES_ADR` + `REQUIRES_BACKEND_CONTRACT` | identity ADR + cross-run query |
| 20 | Decision-threshold bands (read-only) | `REQUIRES_ADR` | `ExecutionRun.thresholds` — ADR-051 **Propuesta** (2026-10-26), not approved or implemented |
| 21 | Threshold change → new run | `REQUIRES_ADR` | re-run contract — ADR-051 **Propuesta** (P3: new upload, `input_hash` link), not approved or implemented |
| 22 | Opportunity ranking | `REQUIRES_ADR` | ranking/evidence policy |
| 23 | Run duplicate / reprocess | `REQUIRES_ADR` | re-run semantics |
| 24 | Run delete / reset | `REQUIRES_ADR` | retention/authorization policy |

---

## 19. Convergence roadmap (re-derived)

The former A–H ordering was invented before this audit and is **superseded**.
Ranked by shared-dependency, Golden-readiness, backend-readiness, user impact,
blockers and regression risk.

| Unit | Scope | Depends on | Blockers | Risk | Value |
|---|---|---|---|---|---|
| **C1 — Frontend-only recovery** ✅ **DONE** | 404 route · Upload drag & drop · catalog filter persistence · explainable metric cards · provenance-grouped data quality · Dashboard KPI density | none | **none** | low | delivered 2026-08-26; 5 fully recovered, KPI density partially (see item 8) |
| **C2 — Design-system pass** | tokens, shell, density, typography applied across all screens | best after C1 so it styles the final component set | none | medium | high — but restyles everything, so it must not run before the component set settles |
| **C3 — Supplier-source contract** | image URL + supplier URL + suggested price + raw row + process trace as importer columns and `RecordOut` fields, with provenance | C1 | backend + rights/caching policy | medium | unblocks items 11–14, 17 at once |
| **C4 — Query contract** | brand filter · column-classification/dry-run preview | C3 (same contract review) | backend | low | unblocks 10, 15, 16 |
| **C5 — Reproducible thresholds** | `ExecutionRun.thresholds` · read-only bands · threshold change → new run | — | **ADR** | high | unblocks 20, 21; restores decision context |
| **C6 — Batch analytics** | multi-source analytics table · per-run decision counts in Runs list | C3 | none/low | low | 6, 18 |
| **C7 — Favorites page** | single-run page first, cross-run after | favourite star (done) | cross-run query | low | 7 |
| **C8 — Compare** | identity ADR → cross-run query → UI | C3, C7 | **ADR + backend** | high | 19 |
| **C9 — Run lifecycle** | duplicate/reprocess, delete/retention | C5 | **ADR** | high | 23, 24 |
| **C10 — Market data** | real price history + KPI tiles | authorized provider | **external** | high | 9 with real values |

**Recommended next unit: C1.** It is the only unit with zero blockers, it
recovers six functions the user already had, and it settles the component set
that C2 would otherwise have to restyle twice.

---

## 20. Cross-references

- `docs/adr/ADR-029-golden-product-experience-baseline.md` — Golden decision
- `docs/architecture/CATALOG_GOLDEN_UX_PARITY.md` — Catalog V1 (superseded classification, kept for traceability)
- `docs/architecture/CATALOG_GOLDEN_UX_PARITY_V2.md` — Catalog functional audit + Wave B3
- `docs/architecture/DEMO_PRODUCTION_PARITY_MATRIX.md` — earlier capability inventory (2026-08-19)
- `docs/architecture/PRODUCT_BEHAVIORAL_PARITY.md` — Waves B–D capability record

---

## 21. Convergence unit C1 — delivered 2026-08-26

| # | Capability | Outcome | Where | Tests |
|---|---|---|---|---|
| C1.1 | Unknown-route experience | **RECOVERED** | `pages/NotFoundPage.tsx`, `App.tsx` `path="*"` inside `AppLayout` so the shell survives | 3 |
| C1.2 | Upload drag & drop | **RECOVERED** | `components/RunForm.tsx` — the drop zone wraps the existing `<input type=file>` and routes drops through the same `selectFiles()` validation, so there is one ingestion rule | 6 |
| C1.3 | Catalog filter persistence | **RECOVERED** | `catalogQuery.ts` — `sessionStorage`, key `juval.catalog.query.v1`, field-by-field validation on read | 5 |
| C1.4 | Explainable metric cards | **RECOVERED** | `components/MetricExplainer.tsx` + `metricExplanations.ts`, applied to 8 economics fields | 3 |
| C1.5 | Provenance-grouped data quality | **RECOVERED** | `components/FieldConfidenceGroups.tsx` on Product Detail | 4+4 |
| C1.6 | Denser KPI strip | **PARTIALLY_RECOVERED** | `pages/DashboardPage.tsx` — 4 → 8 tiles | 4 |

### C1.6 — what was not recovered, and why

Golden shows 11 KPIs. Eight have true production equivalents and were
recovered: Total records, BUY, REVIEW, PASS, With issues, Average ROI,
Average profit, Average margin. Three were **not**:

- **Files / Valid files / Invalid files** — batch-level facts. Production's
  run-scoped analytics endpoint has no file counts because a run *is* one file
  (`BatchFileOut` carries this instead). Surfacing them here would mean
  inventing a per-run number that does not exist.
- **"Estimated demo profit"** (a *total*) — `profitability.profit` exposes
  `average`, `minimum`, `maximum` and `count`. Summing on the client would be a
  frontend recomputation of a backend figure, which ADR-006 forbids, and would
  silently include or exclude non-VERIFIED records depending on how it was
  written.

Both are recorded as open items rather than dropped. A run-total projection on
the analytics endpoint would unblock the profit total.

### C1.3 — scope choice worth recording

Golden persists its catalog state in `sessionStorage`, and C1 keeps that
scope deliberately. A remembered filter changes *which records an operator
sees*; letting it outlive the sitting risks a later review being silently
narrowed by a filter nobody remembers setting. The selected run and the page
offset are not persisted either — both belong to the data, not to the
operator's preference.

Nothing from Golden has been dropped from this matrix.

---

## 22. Frontend integration of C4/C6 contracts — delivered 2026-10-26

Scope authorized by the user: a limited lift of the frontend freeze, only to
consume `brand`, `POST /api/v1/runs/preview` and `decisions`, in `frontend-next/`
(the ADR-030 candidate). `demo/` and `frontend/` unchanged; no redesign.

| # | Capability | Outcome | Where | Tests |
|---|---|---|---|---|
| 6 | Per-run decision counts | **RECOVERED** | `pages/shared.tsx::DecisionCounts` on `RunsPage` and `RunDetailPage` | 3 component + 1 live |
| 10 | Brand filter | **RECOVERED** (top-10 options) | `CatalogPage` Brand select fed by the run's analytics `brands`; `brand` in records query and export | 8 component + 1 API + 1 live |
| 15–16 | Pre-submit preview with column classification | **RECOVERED** | `pages/ImportPreview.tsx`, Preview per queued file on `UploadPage`; `api/preview.ts` | 8 component + 1 live |

Rules kept, and why:

- **Null decisions are not zeros.** `decisions: null` (no stored snapshot)
  renders "Decision counts not available"; with counts present, a missing key is
  a real 0.
- **Brand is exact and server-sourced.** Options are only `brands.items[].label`
  of the selected run, so every choice matches exactly and case-sensitively;
  `Acme` and `acme` stay two options. No free text, no "no brand" filter.
  The backend lists at most 10 brands; when `distinct` is larger the page says
  so and points to search. Unbranded records are counted, not filterable.
- **Brand is not remembered.** It is a value of one run's data, so it is
  excluded from the session-stored query and cleared when the run changes.
- **Preview is not processing.** Labelled PREVIEW, sends only the file (no
  thresholds, fees or persist), creates no run (verified live: run count
  unchanged), hides when its file leaves the queue. Golden's browser-side row
  parsing and format confidence are not reproduced; the server importer is the
  authority.

Verification: `npx tsc -b --noEmit` clean; `vitest run` 82 passed, 3 skipped
(the opt-in live suite; re-validated 2026-10-26, adding loading/empty-brand and
queue-unchanged checks); `oxlint` clean; `vite build` OK. Live suite
`src/live.contract.test.tsx` passed 3/3 against a disposable local FastAPI on
SQLite. Run it with `JUVAL_LIVE_API` and `VITE_API_BASE_URL` set to the same
local URL. Its multipart shim exists only because vitest's jsdom `FormData` is
not serialized by Node's `fetch`; browsers are unaffected. No browser E2E: no
Playwright setup or browsers exist for `frontend-next/`. Not visually reviewed
by the user yet (ADR-030 milestone review pending).

## 23. Dashboard, Product Detail and per-file analytics in `frontend-next/` — delivered 2026-10-26

Scope: user instruction to resume functional development with frontend and
backend where needed. Only `frontend-next/` (ADR-030 candidate) changed;
`frontend/` and `demo/` untouched; no backend logic, formula, decision or
Decision Score change (API_CONTRACT §11 now names the existing summary fields).

| Unit | Before | Now | Contract | Tests |
|---|---|---|---|---|
| Product Detail | no route — Catalog links landed on "Page not found" | `/run/{id}/product/{ref}`: decision + reasons, identity, source file/row from stored provenance, economics with per-metric explanations (item 4), risk + severity, fields grouped by their own status (item 5), per-field evidence with raw and exact stored values, ADR-047 evidence as stored | `GET .../records/{ref}`, `.../financial` | 14 component + 1 live |
| Dashboard | not-wired placeholder | one run (latest or `?run=`): 11 Golden KPIs (item 8), decisions, verified-only profitability with coverage, risk, per-field provenance, issue types, brands, price spread linking to Product Detail | `GET .../analytics`, `GET .../runs/{id}/batch` | 13 component + 1 live |
| Per-file analytics (item 18) | absent | Batch Detail table, one row per child run | `GET .../runs/{id}/analytics` × ≤10 | 7 component + 1 live |

Rules kept: every value beside its status; financial figures VERIFIED-only and
always state how many records they cover; a missing amount reads "Not stored"
or "—", never 0; file counts only for runs that belong to a batch; files are
never merged or matched (that is Compare, item 19, `REQUIRES_ADR`); no image,
link, market series or ranking without an approved source. Golden's simulated
price chart (item 9, `FIXTURE_PRESENTATION_ONLY`) was deliberately not carried
into frontend-next. Items 4 and 5 were already RECOVERED in `frontend/` (C1)
and now exist in frontend-next too; the count does not change for them.

Verification: `tsc -b --noEmit` clean; vitest 130 passed, 6 skipped (opt-in
live); live suite 6/6 against a disposable local API; oxlint clean; build OK.
Not visually reviewed by the user yet (ADR-030 milestone review).

GOLDEN items: RECOVERED 9 → 11 of 24 (8 and 18); PARTIALLY_RECOVERED 1 → 0.

## 24. Favorites page and readable ADR-047 evidence in `frontend-next/` — delivered 2026-10-26

| Unit | Now | Contract | Tests |
|---|---|---|---|
| Favorites (item 7) | `/favorites`: runs that have stars (with counts), the selected run's starred records each resolved by `GET .../records/{ref}`; title → Product Detail (same tab), decision, SKU, source file, profit and ROI with their status; deleted/failed records stay visible and removable; removing does not refetch the rest; empty state → Catalog; stars of runs no longer listed can be forgotten; labelled "this browser only" | existing record endpoint; `localStorage` stars (unchanged key) | 12 component + 1 live |
| Product Detail — ADR-047 evidence | structured, read-only view of stored v1/v2 documents and diagnostics: calculated results (exact stored Decimal, own status, expression, blocker + evidence, preconditions, undeclared terms), selling price used, scenario and declared terms with source cells, dependency resolution (resolved/excluded/blocked), supplied inputs as supplied, capture problems, diagnostics, implementation identity, inconsistencies; unknown keys listed as stored; original JSON kept | `GET .../records/{ref}/financial` (§2e) | 10 component + 1 opt-in render of real API output |

Item 7 is **PARTIALLY_RECOVERED**, not RECOVERED: Golden iterated every run at
once and showed product images; production has neither a cross-run lookup nor
an approved image source. No backend persistence or device sync was added.
The evidence view is not a Golden item (Golden had no ADR-047), so it changes
no count.

Verification: `tsc` clean; vitest 152 passed, 7 skipped (opt-in); live suite
7/7 on a disposable local API; the opt-in real-payload test rendered all four
records of the synthetic financial flow (FULL, PARTIAL, NO_SCENARIO, INFERRED)
with every exact value and blocker and no unknown key; oxlint clean; build OK.
No browser E2E. GOLDEN: RECOVERED 11/24 (unchanged), PARTIALLY_RECOVERED 0 → 1.

## 25. Supplier suggested price (item 17) — delivered 2026-10-27

Contract: ADR-053 (an amendment to ADR-046 §20.1 limited to this one field).
The backend gained two importer columns, the snapshot document
`juval.supplier-suggested-price` v1, two `RecordOut` fields, eight export columns
and a preview group. `frontend-next/` gained a Catalog column and a Product
Detail panel. `frontend/` and `demo/` are unchanged.

| Golden | Production | Why it differs |
|---|---|---|
| "Suggested" column in Catalog, between Cost and Selling | "Suggested (supplier)" in the same place, showing `24.99 EUR` + status badge | — |
| Sortable | not sortable | amounts may be in different currencies; ordering them would invent an equivalence |
| `$` formatting | exact stored Decimal + declared ISO-form code; no `$` assumed | currency is never inferred or converted |
| Labelled `VERIFIED_SOURCE` | INFERRED, `USER_INPUT`, "Not used for this decision" | appearing in a file neither verifies it nor proves who wrote it (ADR-053 S2) |
| Product Detail card "Suggested price" | Product Detail panel with amount, raw cells, currency, source row/column, method, captured-at, diagnostics | provenance rule (ADR-003/004) |
| West Marine adapter field | two explicit columns, no aliases, `.xlsx`/`.csv` only | no new input format; `msrp`/`list_price`/… are other concepts |
| — | zero, negative, text and unknown currency are INVALID with raw cells and a WARNING | nothing is repaired |

Exports: the Catalog export and the run download carry identical
`supplier_suggested_price_*` cells, and both agree with the API. This is verified
by pytest and by the Chromium E2E.

Verification after the final audit (2026-10-27):

- pytest: 65 G17 tests, including 2 on a disposable PostgreSQL 16 cluster.
  The full suite has 1865 passed and 129 skipped with `JUVAL_POSTGRES_BIN` set.
- vitest: 177 passed, 10 skipped.
- tsc, oxlint and build: clean.
- Playwright E2E in Chromium: 17/17, twice, plus the G17 spec on its own (5/5).

**Audit verdict: RECOVERED.** Item 17's exact criterion is "Suggested/list price
field", whose blocker was "importer column + `RecordOut` field" (§16: "suggested
price has no field"). Both now exist, and the value is shown in the same places as
Golden. "List price" is deliberately *not* treated as the same concept (ADR-053
S1). That difference is documented above and is not a missing capability.

GOLDEN items: RECOVERED 11 → **12/24** (item 17). PARTIALLY_RECOVERED stays 1 (item 7).
