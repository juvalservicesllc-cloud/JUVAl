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
| **Pre-submit preview** | parses in-browser and previews rows/warnings **before** processing | absent | would need a dry-run endpoint | **missing** | `REQUIRES_BACKEND_CONTRACT` | a `validate-only` mode |
| **Column classification preview** | `classifyColumns()` — USED / OPTIONAL / IGNORED + canonical name + rationale; `detectWestMarine()` gives format + confidence % + missing columns | absent | `column_mapping.py` has the specs but nothing surfaces them | **missing** | `REQUIRES_BACKEND_CONTRACT` | high audit value; expose the mapping the importer already computes |
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
| Still missing | brand filter dropdown (`REQUIRES_BACKEND_CONTRACT`), product image (`REQUIRES_BACKEND_CONTRACT`), decision-threshold bands (`REQUIRES_ADR`) |

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
| **Per-run decision counts in the list** | BUY/REVIEW/PASS inline on every row | not in the list | analytics is per-run endpoint | Golden scannable at a glance | `GOLDEN_UX_SUPERIOR` |
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
| **Brand** | Catalog | — (free-text search only) | no param | `REQUIRES_BACKEND_CONTRACT` |
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
| 1 | 404 / catch-all route | `GOLDEN_CAPABILITY_MISSING` | none — frontend-only |
| 2 | Upload drag & drop zone | `GOLDEN_CAPABILITY_MISSING` | none — frontend-only |
| 3 | Catalog filter persistence across navigation | `GOLDEN_UX_SUPERIOR` | none — frontend-only |
| 4 | Explainable metric cards on Product Detail | `REQUIRES_PRODUCTIONIZATION` | none — frontend-only |
| 5 | Provenance-grouped data quality on Product Detail | `GOLDEN_UX_SUPERIOR` | none — frontend-only |
| 6 | Per-run decision counts in the Runs list | `GOLDEN_UX_SUPERIOR` | one analytics call per row, or a list projection |
| 7 | Favorites page | `REQUIRES_PRODUCTIONIZATION` | cross-run record lookup for the multi-run view |
| 8 | Dashboard KPI density (11 vs 4) | `GOLDEN_UX_SUPERIOR` | none — frontend-only |
| 9 | Price history KPI tiles | `FIXTURE_PRESENTATION_ONLY` | must keep the fixture label |
| 10 | Brand filter dropdown | `REQUIRES_BACKEND_CONTRACT` | `brand` query param |
| 11 | Product image | `REQUIRES_BACKEND_CONTRACT` | image field + rights/caching policy |
| 12 | Supplier source URL + external link | `REQUIRES_BACKEND_CONTRACT` | URL field + rights policy |
| 13 | Raw source row disclosure | `REQUIRES_BACKEND_CONTRACT` | raw row not persisted |
| 14 | Process trace | `REQUIRES_BACKEND_CONTRACT` | trace not persisted |
| 15 | Column classification / format-detection preview | `REQUIRES_BACKEND_CONTRACT` | expose importer mapping + a dry-run endpoint |
| 16 | Pre-submit file preview | `REQUIRES_BACKEND_CONTRACT` | validate-only mode |
| 17 | Suggested/list price field | `REQUIRES_BACKEND_CONTRACT` | importer column + `RecordOut` field |
| 18 | Multi-source analytics table | `REQUIRES_PRODUCTIONIZATION` | batch-scoped aggregation |
| 19 | Compare | `REQUIRES_ADR` + `REQUIRES_BACKEND_CONTRACT` | identity ADR + cross-run query |
| 20 | Decision-threshold bands (read-only) | `REQUIRES_ADR` | `ExecutionRun.thresholds` |
| 21 | Threshold change → new run | `REQUIRES_ADR` | re-run contract |
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
| **C1 — Frontend-only recovery** | 404 route · Upload drag & drop · catalog filter persistence · explainable metric cards · provenance-grouped data quality · Dashboard KPI density | none | **none** | low | high — 6 real Golden functions, no contract work |
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

Nothing from Golden has been dropped from this matrix.
