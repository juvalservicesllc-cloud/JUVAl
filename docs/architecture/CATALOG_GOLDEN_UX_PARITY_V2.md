# Golden ↔ Production Functional Parity Audit (V2)

## Status and method

**Wave B2 — 2026-08-26.** Supersedes the *classification* in
`CATALOG_GOLDEN_UX_PARITY.md`, which is kept unaltered for traceability. V1
treated `demo/` as a visual reference; the user has since clarified that
`demo/` is also the **functional recovery baseline** — it contains work
already done. V1's conclusion ("production is functionally richer, therefore
visual convergence only") was **not sufficient** to close Wave B.

Method: every executable file under `demo/src` was read (not the docs), and
each capability was traced to the production frontend, the FastAPI contract
(`interfaces/api/main.py`, `models.py`) and the SQLite record store. Golden
remained byte-identical throughout (`demo/src` SHA-256
`a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`).

### Three V1 errors this audit corrects

| V1 said | Truth |
|---|---|
| Price history + Line/Bar are `DEMO_ONLY`, not implemented in production | **Already implemented** in `ProductDetailPage` with a Line/Bar segmented control and an explicit `DEMO_FIXTURE / NOT VERIFIED` banner |
| Background image is `MISSING` in production | **Present and richer**: background image + fit + position + overlay opacity, plus 8 themeable tokens and a contrast warning |
| Compare needs a "comparable-identity ADR" (implied unbounded) | Golden matches on **shared supplier URL across source files inside one batch** — a bounded, run-scoped rule, not a global product identity |

### Classification key

`A` PRODUCTION_ALREADY_SUPERIOR · `B` PRODUCTION_EQUIVALENT ·
`C` GOLDEN_CAPABILITY_MISSING_IN_PRODUCTION · `D` GOLDEN_UX_SUPERIOR ·
`E` REQUIRES_PRODUCTIONIZATION · `F` REQUIRES_BACKEND_CONTRACT ·
`G` REQUIRES_ADR · `H` DEMO_FIXTURE_PRESENTATION_ONLY · `I` INVALID/OBSOLETE ·
`J` UNKNOWN

---

## 1. Catalog — search, filter, query

| Capability | Golden location | Golden behavior | Golden data source | Production location | Production behavior | Backend support | Provenance impact | Status | Class | Recovery plan | Blocker | Tests | User-visible difference |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Text search | `catalog/select.ts` | client-side substring over `title+brand` | in-memory records | `ProductsPage.tsx` | debounced server-side `search` | `record_ref, supplier_sku, title, brand, asin` LIKE | none | PRESERVED | A | — | — | yes | production searches 5 fields, not 2 |
| Decision filter | `select.ts` | local `decision` equality | demo decisions | `ProductsPage.tsx` | server `decision` | yes | decision output | PRESERVED | B | — | — | yes | none |
| **Brand filter (dropdown)** | `CatalogPage.tsx` `filters[brand]` | select populated from records in view | in-memory | — | **absent**; brand only reachable through free-text search | **no `brand` query param** | none | **MISSING** | **C + F** | add `brand` filter param to `RecordSnapshotQuery`, store clause and export; populate the select from a distinct-brand projection | backend param + `API_CONTRACT.md` update | to add | Golden offers one-click brand narrowing; production requires typing |
| **Source-file filter** | `select.ts` `sourceFileId` | narrows a multi-file batch to one file | `sourceFileId` per record | — | not applicable in this shape | production stores **one child `ExecutionRun` per file** (`BatchFileOut.execution_id`) | per-run | SUPERSEDED | A | none — selecting the run *is* selecting the file | — | existing | equivalent outcome via the Run selector |
| Min ROI / profit / margin | `select.ts` | local numeric, ROI+margin as % | in-memory | `ProductsPage.tsx` | server thresholds, % → ratio | yes | **confidence-aware** | PRESERVED | A | — | — | yes | production won't silently count INFERRED values |
| HazMat / Bulky filter | `select.ts` | local status equality | simulated risk | `ProductsPage.tsx` | server `hazmat` / `bulky` | yes | risk semantics | PRESERVED | B | — | — | yes (added W-B) | production also carries severity (ADR-020) |
| Amazon match filter | `select.ts` `match` | `DEMO_FIXTURE / INFERRED / NOT_FOUND` | fixture | `ProductsPage.tsx` | `provenance_field` × `provenance_status` | yes | **core** | SUPERSEDED | A | — | — | yes | production filters *any* sensitive field by *any* status |
| Confidence mode | — | absent | — | `ProductsPage.tsx` | `VERIFIED_ONLY` / `INCLUDE_INFERRED` | yes | **core** | PRODUCTION-ONLY | A | — | — | yes | Golden cannot express it |
| Reset filters | `CatalogPage.tsx` | resets to defaults | — | `ProductsPage.tsx` | `resetQuery()` | n/a | none | PRESERVED | B | — | — | yes | none |

## 2. Catalog — table, sort, columns, export

| Capability | Golden location | Golden behavior | Golden data source | Production location | Production behavior | Backend support | Provenance impact | Status | Class | Recovery plan | Blocker | Tests | User-visible difference |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Sortable columns | `select.ts` `fields` | 11 fields, client sort, stable `recordRef` tiebreak | in-memory | `ProductsPage.tsx` | 12 allow-listed server sort keys | yes | none | PRESERVED | A | — | — | yes | production sorts the whole result set, not the page |
| **Default sort** | `defaultCatalogState` | **`profit:desc`** — best opportunities first | — | `ProductsPage.tsx` | `record_ref:asc` — neutral/stable | yes | none | **DIFFERENT** | **D** | one-line default change; **not applied unilaterally** — it changes what the operator sees first | user decision | n/a | Golden opens on the most profitable rows |
| Column visibility | — | fixed columns | — | `ProductsPage.tsx` | toggleable, persisted | n/a | preference | PRODUCTION-ONLY | A | — | — | yes | Golden cannot hide a column |
| Column ordering | — | fixed | — | `ProductsPage.tsx` | reorderable, persisted | n/a | preference | PRODUCTION-ONLY | A | — | — | yes | — |
| Pagination | `select.ts` | client slice, page size 20 | in-memory | `ProductsPage.tsx` | server 25/50/100 + range label | yes | none | PRESERVED | A | — | — | yes | production scales past one page of memory |
| Filtered export | `CatalogPage.tsx` → `exportCsv` | exports the **filtered set** (`shown.all`), 22 columns incl. `amazon_provenance` | in-memory | `ProductsPage.tsx` | canonical query-equivalent server export | yes | query metadata | PRESERVED | B | — | — | yes | button now names the row count (Wave B) |
| Row → Product Detail | `productPath()` | `/run/:run/file/:file/product/:ref` | local | `ProductsPage.tsx` | `Link` to `/runs/:id/records/:ref`, same tab | yes | run-scoped | PRESERVED | B | — | — | yes | none |
| **Favourite star per row** | `CatalogPage.tsx` + `favorites.ts` | star toggle, `runId:sourceFileId:recordRef`, localStorage | browser | `ProductsPage.tsx` + `src/favorites.ts` | star toggle, `executionId:recordRef`, localStorage, labelled local-only | **none (by design)** | none | **RECOVERED (Wave B2)** | **E → done** | — | — | **4 new tests** | restored |
| Thumbnail slot | `ProductThumbnail.tsx` | 44px slot, `img` or "No image" | **real supplier URL from the source CSV** | `components/ProductThumbnail.tsx` | 40px slot, explicit unavailable state | **`RecordOut` has no image field** | image would need provenance | PARTIAL | **C + F** | add an optional image column to the tabular contract so a supplier file that carries one is preserved *with* provenance | backend contract + rights/caching policy | yes (asserts no `<img>`) | Golden shows supplier pictures; production shows an empty slot |

## 3. Catalog — decision policy

| Capability | Golden location | Golden behavior | Golden data source | Production location | Production behavior | Backend support | Provenance impact | Status | Class | Recovery plan | Blocker | Tests | User-visible difference |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Decision band display | `CatalogPage.tsx` | PASS/REVIEW/BUY pills from the active policy | local policy | — | absent | run does not record its thresholds | would be invented | MISSING | **C + F + G** | persist `thresholds` on `ExecutionRun`, then display read-only | **`ExecutionRun` gap (`CLAUDE.md` §15)** | n/a | Golden states the bands; production does not |
| **Threshold editor** | `CatalogPage.tsx` `applyPolicy` → `applyDecisionPolicy` | edits Review/Buy ROI and **rewrites stored decisions client-side** | local | — | absent | backend accepts thresholds only at run creation | **would rewrite a historical decision** | **MUST NOT MIGRATE AS-IS** | **G** | correct shape = *re-run* with new thresholds producing a **new** `ExecutionRun`, never mutating an existing one | ADR + `ExecutionRun.thresholds` | n/a | Golden can retro-change a past decision — production must not |

## 4. Product Detail

| Capability | Golden location | Production location | Backend | Status | Class | Notes |
|---|---|---|---|---|---|---|
| Decision + reasons | `ProductDetailPage.tsx` | `ProductDetailPage.tsx` | yes | PRESERVED | B | — |
| Identity / ASIN / UPC / SKU | ✓ | ✓ | yes | PRESERVED | A | production ASIN is real; Golden's is a fixture |
| Economics | 9 metric cards | ✓ | yes | PRESERVED | A | production adds break-even, max-COG, total fees, seller proceeds |
| Risk | status only | status **+ severity** (ADR-020) | yes | SUPERSEDED | A | — |
| Data quality | grouped by provenance + coded facts | issue list + count | yes | PARTIAL | **D** | Golden groups fields by `VERIFIED/DEMO_FIXTURE/INFERRED/NOT_FOUND/INVALID` — clearer at a glance |
| Field-level trace | `FieldTrace.tsx` + `trace.ts` | provenance panel with per-field disclosure | yes | PRESERVED | B | Golden also names source column, raw value, transformation, formula |
| "What does this mean?" per metric | `ExplainableMetricCard.tsx` | — | n/a | MISSING | **D + E** | pure presentation, no backend needed — good Wave D candidate |
| **Price history + Line/Bar** | `PriceHistory.tsx` | `ProductDetailPage.tsx` MARKET panel | none | **ALREADY PRESENT** | **H** | both are `DEMO_FIXTURE`; production labels it more loudly. **V1 was wrong.** |
| Price KPIs (current/avg/low/high) | ✓ | — | none | MISSING | **H** | fixture-derived; migrate only with the fixture label |
| **Supplier source link** | `<a target="_blank" rel="noopener noreferrer">` | — | **no URL field** | MISSING | **C + F** | this is the *legitimate* new-tab case; needs a source-URL contract |
| Raw source row | `<details><pre>{raw}</pre>` | — | raw row not persisted | MISSING | **C + F** | strong auditability capability |
| Process trace | `SOURCE_IMPORTED → … → DECISION_CALCULATED` | — | not persisted | MISSING | **C + F** | — |

## 5. Dashboard

| Capability | Golden | Production | Status | Class | Notes |
|---|---|---|---|---|---|
| Decision distribution | Bar | ✓ | PRESERVED | B | — |
| HazMat / Bulky charts | Bar | ✓ | PRESERVED | B | — |
| Provenance breakdown | Bar | ✓ | PRESERVED | B | — |
| Brand distribution | top-8 | `brands` projection | PRESERVED | A | production counts `not_recorded` separately |
| Issue types | ✓ | `issue_types` by canonical code | PRESERVED | A | — |
| Supplier price discounts | ✓ | `price_spread` | PRESERVED | A | — |
| **Opportunity ranking** | top-5 by profit, links to detail | — | MISSING | **C + G** | Golden labels it "simulated"; production needs an approved ranking contract |
| **Multi-source analytics table** | per-file rows | — | MISSING | **C** | expressible over a batch's child runs (`GET /runs/{id}/batch`) |
| Analytics source filter | select per file | run selector | SUPERSEDED | A | — |
| Cross-file match banner | "N exact matches → Compare" | — | MISSING | **C + G** | depends on Compare |

## 6. Compare / Favorites / Runs / Appearance

| Capability | Golden | Production | Status | Class | Notes |
|---|---|---|---|---|---|
| **Compare** | `ComparePage.tsx` + `matching.ts` | — | MISSING | **C + G** | see §Findings |
| **Favorites page** | `FavoritesPage.tsx`, grid + source filter | star only (Wave B2) | PARTIAL | **E** | the *page* is Wave G; the star is recovered |
| Runs list / status / counts | ✓ | ✓ | PRESERVED | B | — |
| Run detail + included files | ✓ | ✓ | PRESERVED | B | — |
| **Duplicate / reprocess run** | clones the stored run | — | MISSING | **G** | Golden's clone copies results **without recomputing** — not a reprocess. Production needs a real re-run contract |
| **Delete / reset runs** | destructive, local | — | MISSING | **G** | needs retention/authorization policy |
| Light / dark | class toggle | `ThemeProvider` + tokens | SUPERSEDED | A | — |
| Accent colour | 1 colour | **8 tokens** + contrast warning | SUPERSEDED | A | — |
| Logo | data URL | ✓ + size limits | SUPERSEDED | A | — |
| **Background image + overlay** | image + overlay slider | image + **fit + position + overlay** | SUPERSEDED | A | **V1 wrongly said MISSING** |
| Live preview | text block | full canvas preview | SUPERSEDED | A | — |
| Responsive / mobile nav | media query | media queries + bottom nav | SUPERSEDED | A | — |
| Accessibility | `aria-sort`, `aria-pressed` | + `aria-live`, roles, labels | SUPERSEDED | A | Golden has a real dark-mode contrast bug (`:root` colour leak) — deliberately not copied |

---

## Findings

### Favorites — RECOVERED
Golden stores `runId:sourceFileId:recordRef` in `localStorage`
(`juval.demo.favorites.v2`). It is **UI-only**: no ownership, no server, no
effect on any value or decision. Production already persists column layout,
sidebar state and the whole theme the same way, so a run-scoped star is
consistent with existing practice and needs **no auth and no ADR**.
Recovered in `src/favorites.ts` keyed `executionId:recordRef` (production has
one run per file, so Golden's middle segment is redundant), labelled
"starred in this browser only" in the UI. **Open product question, not a
blocker:** whether favourites should later become owned, shared, server-side
data. The Favorites *page* remains Wave G.

### Compare — BLOCKED_BY_ADR (bounded, not unbounded)
`matching.ts` matches on the **supplier product URL**, deliberately *not* on
ASIN (a fixture in the demo), grouping only records whose URL appears in
**≥2 source files of the same batch**. Fuzzy matching is explicitly out of
scope. This is a bounded, run-scoped rule. Production's equivalent would
group across the **child runs of one batch**, and could match on real ASIN,
UPC or supplier SKU — stronger identifiers than Golden's URL. It still needs
an ADR because ADR-011/ADR-012 deliberately refuse a global product identity,
and it needs a cross-run record query the API does not expose. **Stays on the
roadmap.**

### Decision thresholds — BLOCKED_BY_ADR, must not be copied
`applyDecisionPolicy` re-runs `decideDemo` over stored records and **saves the
new decisions over the old ones**. Reproducibility forbids this in production:
`ExecutionRun` does not record the thresholds a run used, so a changed
decision would be unattributable and unreproducible. Correct architecture:
(1) persist `thresholds` on `ExecutionRun`, (2) display the bands read-only,
(3) make "change thresholds" create a **new** run. Steps 1 and 3 are model
changes → **ADR proposed, not implemented**.

### Product images — REQUIRES_BACKEND_CONTRACT (capability is real)
Golden's images are **not fabricated and not scraped by JUVAl**: they come
from the `img-fluid src` column of the supplier's own export file, alongside
`position-relative href` (the supplier URL). So the capability is "preserve
an image/URL the supplier file already provides, with provenance" — legitimate
and squarely on the roadmap. Production's importer has no such column, and
`RecordOut` no such field. Until it does, production keeps the sized slot and
its explicit unavailable state. **No URL is invented, borrowed or scraped.**

### Market history / Line-Bar — ALREADY PRESENT, fixture-labelled
Golden's series is a deterministic hash of `recordRef` (`price-history.ts`),
declared `provenance: "DEMO_FIXTURE"`, and its own copy says it is not Keepa.
Production already ships the equivalent panel *with* a Line/Bar segmented
control and a louder `DEMO_FIXTURE / NOT VERIFIED` banner. The remaining gap
is only the four KPI tiles (current / 90-day average / low / high), which are
fixture-derived and must carry the same label. Real values stay blocked on an
authorized provider.

---

## Provenance audit

| Sensitive field | Golden | Production | Leak? |
|---|---|---|---|
| ASIN | `DEMO_FIXTURE` / `INFERRED` / `NOT_FOUND` (generated) | real `FieldValue` with status | no |
| Weight / dimensions | demo fixture | real, canonical units | no |
| HazMat / Bulky | simulated | real status **+ severity** | no |
| Selling price / fees / shipping | simulated | real `FieldValue` | no |
| Profit / ROI / margin | computed from fixtures | backend `Decimal`, weakest-link status | no |
| Product image | supplier URL from the source file | **absent by design** | no |
| Market history | `DEMO_FIXTURE` | `DEMO_FIXTURE`, banner | no |
| Favourite star | localStorage | localStorage, labelled | no — carries no data |

**No `DEMO_FIXTURE` became `VERIFIED`. No demo value entered production.**

---

## Outstanding work, by blocker

| Blocker | Capabilities |
|---|---|
| **Backend contract** | brand filter · product image field · supplier source URL · raw source row · process trace · price KPIs |
| **ADR required** | Compare · decision-threshold bands and re-run semantics · `ExecutionRun.thresholds` · opportunity ranking · run duplicate/delete |
| **Frontend only (no blocker)** | Favorites page · explainable metric cards · provenance-grouped data quality · default-sort change · multi-source analytics table |
| **Fixture-only, presentation may migrate** | price KPIs (with the `DEMO_FIXTURE` label) |

Nothing from Golden has been dropped from this matrix.
