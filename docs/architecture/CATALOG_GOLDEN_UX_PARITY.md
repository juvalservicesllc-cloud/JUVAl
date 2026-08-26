# Golden UX → Production Convergence Parity Matrix

## Status and method

**Established 2026-08-26** under ADR-029, after the user visually confirmed
`demo/` (`http://127.0.0.1:5181/catalog`) as the Golden Product Experience
Baseline.

This matrix compares `demo/src` (golden UX reference) against `frontend/src`
(production integration base), component by component. It complements
`DEMO_PRODUCTION_PARITY_MATRIX.md`, which inventories *product capabilities*;
this one tracks the *visual/interaction convergence* and its migration state.

Classification used per capability:

| Class | Meaning |
|---|---|
| `BOTH_EQUIVALENT` | Present in both, no meaningful difference |
| `BOTH_DIFFERENT` | Present in both, materially different treatment |
| `DEMO_ONLY` | Only in the golden reference |
| `FRONTEND_ONLY` | Only in production (usually a real-data capability the demo never had) |
| `PRODUCTIONIZED` | Was demo-only; now implemented in production against real contracts |
| `FIXTURE_ONLY` | Exists in the demo but is powered by fixture/simulated data |
| `MISSING` | In neither |

**Important finding:** production is *functionally richer* than the golden
reference in almost every Catalog capability (server-side querying, confidence
mode, provenance filters, column ordering, pagination, filtered export). What
the golden reference holds is the **visual and interaction language**. This is
therefore a visual convergence, not a functional rewrite.

---

## Wave A–H scope (order of convergence)

| Wave | Scope | State |
|---|---|---|
| A | Design tokens, shell, navigation, global visual language | NOT STARTED |
| **B** | **Catalog visual parity** | **IMPLEMENTED 2026-08-26 — awaiting user visual approval** |
| C | Dashboard visual parity + charts | NOT STARTED |
| D | Product Detail + price-history presentation | NOT STARTED |
| E | Upload / multi-file experience | NOT STARTED |
| F | Appearance / personalization | NOT STARTED |
| G | Compare / Favorites production design | BLOCKED — needs ADR (ownership, persistence, comparable identity) |
| H | Responsive / accessibility / final polish | NOT STARTED |

---

## Matrix

| Capability | Demo source | Frontend target | Class | Backend dependency | Provenance implication | Complexity | Regression risk | Wave / state |
|---|---|---|---|---|---|---|---|---|
| App shell | `app/App.tsx` | `components/AppLayout.tsx` | `BOTH_DIFFERENT` | none | none | M | Low | A — not started |
| Sidebar | `app/App.tsx` (`aside`) | `components/AppLayout.tsx` | `BOTH_DIFFERENT` | none | none | S | Low | A — not started |
| Header / topbar | `app/App.tsx` (`header`) | `components/AppLayout.tsx` | `BOTH_DIFFERENT` | none | none | S | Low | A — not started |
| Dashboard | `pages/DashboardPage.tsx` | `pages/DashboardPage.tsx` | `BOTH_DIFFERENT` | analytics endpoint | real analytics only | M | Med | C — not started |
| Upload | `pages/ImportPage.tsx` | `pages/UploadPage.tsx` | `BOTH_DIFFERENT` | POST runs/batches | input provenance | M | Med | E — not started |
| Multi-file experience | `batch.ts` (`MAX_FILES = 10`) | `api/batches.ts`, `BatchDetailPage` | `BOTH_EQUIVALENT` | batches endpoint | per-file status | — | — | already productionized (ADR-025) |
| **Catalog page** | `pages/CatalogPage.tsx` | `pages/ProductsPage.tsx` | `BOTH_DIFFERENT` | records endpoint | run-scoped snapshot | L | Med | **B — implemented** |
| **Catalog table** | `pages/CatalogPage.tsx` | `pages/ProductsPage.tsx` + `App.css` | `BOTH_DIFFERENT` | records endpoint | status per field | M | Med | **B — implemented (single-line rows)** |
| **Thumbnails** | `pages/ProductThumbnail.tsx` (supplier fixture URL) | `components/ProductThumbnail.tsx` | `FIXTURE_ONLY` → slot productionized | **none — `RecordOut` has no image field** | demo images are `DEMO_FIXTURE` | S | Low | **B — slot only; no image fabricated** |
| Search | local text filter | server-side `search` | `FRONTEND_ONLY` (server-side) | yes | n/a | — | — | preserved |
| Decision filter | local select | server-side `decision` | `BOTH_EQUIVALENT` | yes | decision output | — | — | preserved |
| ROI filter | `minRoi` (%) local | `min_roi` ratio, entered as % | `BOTH_EQUIVALENT` | yes | confidence-aware | — | — | preserved |
| Profit filter | `minProfit` local | `min_profit` server-side | `BOTH_EQUIVALENT` | yes | confidence-aware | — | — | preserved |
| Margin filter | `minMargin` (%) local | `min_margin` ratio, entered as % | `BOTH_EQUIVALENT` | yes | confidence-aware | — | — | preserved |
| HazMat filter | local status select | server-side `hazmat` | `BOTH_EQUIVALENT` | yes | risk semantics | — | — | preserved + test added |
| Bulky filter | local status select | server-side `bulky` | `BOTH_EQUIVALENT` | yes | risk semantics | — | — | preserved + test added |
| **Confidence mode** | — | `confidence=VERIFIED_ONLY / INCLUDE_INFERRED` | `FRONTEND_ONLY` | yes | **core** | — | — | preserved |
| **Provenance filters** | — | `provenance_field` + `provenance_status` | `FRONTEND_ONLY` | yes | **core** | — | — | preserved |
| Sorting | local, all columns | server-side allow-listed sort | `BOTH_DIFFERENT` | yes | n/a | S | Low | **B — golden pill headers + always-visible affordance** |
| Column visibility | fixed columns | configurable, persisted | `FRONTEND_ONLY` | none | preference only | — | — | preserved |
| Column order | fixed columns | reorderable, persisted | `FRONTEND_ONLY` | none | preference only | — | — | preserved (storage key `v2`) |
| Pagination | local arrays | server-side 25/50/100 | `FRONTEND_ONLY` (server-side) | yes | n/a | — | — | preserved |
| **Filtered export** | local CSV of filtered rows | canonical query-equivalent export | `BOTH_EQUIVALENT` | yes | query metadata | S | Low | **B — button now names the row count** |
| Decision visualization | colored `Badge` | `StatusBadge` + traffic-light palette | `BOTH_EQUIVALENT` | yes | decision output | S | Low | **B — shape glyph added (●/▲/■)** |
| Product detail | `pages/ProductDetailPage.tsx` | `pages/ProductDetailPage.tsx` | `BOTH_DIFFERENT` | record endpoint | full provenance | L | Med | D — not started |
| Price history | `pages/PriceHistory.tsx` | — | `FIXTURE_ONLY` | **no authorized provider** | `DEMO_FIXTURE` only | L | High | D — blocked, presentation only |
| Line/Bar toggle | `pages/PriceHistory.tsx` | — | `DEMO_ONLY` | tied to price history | `DEMO_FIXTURE` | S | Low | D — blocked with price history |
| Compare | `pages/ComparePage.tsx` | — | `DEMO_ONLY` | no comparable identity | cross-run unresolved | L | High | G — **ADR required** |
| Favorites | `pages/FavoritesPage.tsx`, `favorites.ts` | — | `DEMO_ONLY` (localStorage) | no ownership model | local only | M | High | G — **ADR required** |
| Decision thresholds editor | `CatalogPage.tsx` (`setDecisionPolicy`) | — | `DEMO_ONLY` | **`ExecutionRun` does not record thresholds** | would change decisions | L | **High** | **not migrated — see below** |
| Runs list | `pages/RunsPage.tsx` | `pages/RunsPage.tsx` | `BOTH_EQUIVALENT` | yes | ExecutionRun | — | — | preserved |
| Run detail | `pages/RunDetailPage.tsx` | `pages/RunDetailPage.tsx` | `BOTH_DIFFERENT` | yes | ExecutionRun | M | Med | C/D — not started |
| Appearance | `pages/AppearancePage.tsx` | `pages/AppearancePage.tsx` | `BOTH_DIFFERENT` | none | preference | M | Low | F — not started |
| Light/dark | `dark` class toggle | `ThemeProvider` + tokens | `FRONTEND_ONLY` (richer) | none | preference | — | — | preserved |
| Graphite/charcoal theme | `--bg:#181b21` etc. | `theme/presets.ts` | `BOTH_DIFFERENT` | none | preference | S | Low | F — not started |
| Color customization | — | `ColorControl.tsx` | `FRONTEND_ONLY` | none | preference | — | — | preserved |
| Background image | — | — | `MISSING` | none | preference | — | — | F — not started |
| Logo customization | — | `BrandAssetControl.tsx` | `FRONTEND_ONLY` | none | preference | — | — | preserved |
| Responsive behavior | demo CSS media query | production media queries + bottom nav | `FRONTEND_ONLY` (richer) | none | n/a | — | — | preserved, re-verified at 430px |
| Accessibility | partial (`aria-sort`, `aria-pressed`) | `aria-sort`, `aria-label`, `aria-live`, roles | `FRONTEND_ONLY` (richer) | none | n/a | — | — | preserved + strengthened |

---

## Not migrated, and why

### Decision thresholds editor — `DEFER_BLOCKED`
The golden Catalog lets the operator edit the Review/Buy ROI bands and
**recomputes decisions locally**. Production must not: the decision comes from
the backend rule set (ADR-006, ADR-007), and `ExecutionRun` does **not** record
the thresholds a run used (`CLAUDE.md` §15, known gap). Rendering bands in
production would require inventing values that no persisted run carries.
Migrating the editor would let the UI silently change a sourcing decision.
Requires an ADR plus an `ExecutionRun` structure change first.

### Favorites and Compare — `DEFER_BLOCKED`
No ownership, authentication-scoped persistence, or comparable-identity
contract exists. The demo stores both in `localStorage`. Shipping the visual
without the contract would imply a persistence guarantee production cannot
keep. Requires an ADR (Wave G).

### Product images — slot only
`RecordOut` carries no canonical image field, and no source, rights,
provenance or caching policy is approved. The golden reference uses supplier
fixture URLs. Production keeps a **fixed, correctly-sized media slot** with an
explicit unavailable state, so that adding `RecordOut.image` later is a data
change and not a table redesign. **No image URL is scraped, fabricated, or
borrowed.** A regression test asserts no `<img>` is emitted in the table.

### Price history — `DEFER_BLOCKED`
The demo's 90-day series is deterministic simulation (`DEMO_FIXTURE`) and its
own disclosure says it is not Keepa or verified marketplace history. Migrating
the presentation is allowed in Wave D; migrating the *values* is not, until an
authorized provider exists.

---

## Wave B — what actually changed

| Change | File | Preserves |
|---|---|---|
| Leading media column with the golden's fixed slot | `pages/ProductsPage.tsx`, `App.css` | no fabricated image; slot is an explicit unavailable state |
| Sortable headers as accent pills, sort affordance always visible | `App.css` | server-side sort keys, `aria-sort`, `aria-pressed` unchanged |
| Single-line rows: status sits beside its value, not under it | `App.css`, `pages/ProductsPage.tsx` | status still attached to every sensitive value (ADR-003/004) |
| Compact status marker inside the table only | `components/StatusBadge.tsx`, `App.css` | full status announced via `aria-label` + `title`; detail views stay spelled out |
| Redundant "No value" caption dropped in table cells | `pages/ProductsPage.tsx` | the badge already states NOT FOUND / INVALID |
| Decision badge gains a shape glyph (● BUY / ▲ REVIEW / ■ PASS) | `App.css` | decision still comes from backend rules; shape aids colour-blind readers |
| Export button names the exact row count | `pages/ProductsPage.tsx` | identical canonical export query |
| Column widths rebalanced so Decision stays in viewport | `App.css` | all columns still present and configurable |
| Column preference key bumped to `v2` | `pages/ProductsPage.tsx` | returning users actually receive the new default |

ROI and margin were **already** displayed as percentages via `format.ts::percent`
(`0.30` → `30.00%`) while the API contract keeps ratios. No change needed; a
regression test now pins it.
