# Demo → Production Product Parity Matrix

## Status and method

**R2 audit — 2026-08-19.** This is an inventory and target contract, not an
implementation plan disguised as code. `frontend/` and the FastAPI/domain
contracts are the production sources of truth. `demo/` is evidence of the
previous product experience and its intended interaction model; its local
storage, fixtures, simulated enrichment, browser processing and router are
not production architecture.

`CURRENT_PRODUCTION_BASELINE` means implemented and protected today. `TARGET`
means the capability remains part of the finished-product contract even when
it is currently blocked. Demo data is never evidence for a production value.

## Matrix

| Surface | Capability | Demo state / interaction | Demo data source | Production state | Backend support | Data available | Provenance | Target state | Blocker | Required phase | Decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Shell | Dashboard, Upload, Catalog, Runs navigation | Custom demo router | Local demo state | Real React routes and shell | Yes | Yes | N/A | Preserve | None | Current | PRESERVE |
| Shell | Settings / Appearance | Theme, accent, logo, background controls | Browser localStorage/data URLs | Production theme/branding controls | UI only | Preference only | Preference | Preserve | None | Current | PRESERVE |
| Shell | Light/dark and responsive navigation | Responsive demo shell | Local preference | Production Light/Dark and mobile shell | UI only | Yes | N/A | Preserve | None | Current | PRESERVE |
| Upload | CSV/XLSX multi-file queue | Drag/drop, add/remove, preview; exact `MAX_FILES = 10` | Browser parsing and fixtures | One real XLSX upload | POST run supports one file | XLSX | Input provenance | Recover as a required target behavior | Multi-file API/run model, per-file persistence and aggregate status | Wave A / Data API foundation | PRODUCTIONIZE |
| Upload | Client file validation | Type, size and parse feedback | Browser parser | Client validation and clear errors | N/A | Selected file | Input | Preserve | None | Current | PRESERVE |
| Upload | Thresholds, fees, persistence settings | Editable processing configuration | Local demo policy | Real submitted configuration | POST run | Yes | Submitted config | Preserve | None | Current | PRESERVE |
| Upload | Backend validation and processing result | Simulated stages | Demo engine | Real success, partial success and failure | Yes | Yes | ExecutionRun | Preserve | None | Current | PRESERVE |
| Processing | Visible stage progression | Many simulated stages | Demo fixtures/simulation | Honest indeterminate processing | API status supports coarse states | Yes | Execution status | Preserve honestly | Granular progress not available | Current | IMPROVE |
| Result | File/batch summary | Files, rows, warnings, errors | Local demo run | Filename, execution ID, counts, warnings/issues, persisted status | Yes | Yes | Snapshot/run | Preserve | None | Current | PRESERVE |
| Result | Review run / Catalog handoff | Open run, catalog CTA | Local demo state | Real Run Detail and Catalog links | Yes | Yes | Run-scoped | Preserve | None | Current | PRESERVE |
| Catalog | Run-scoped dataset context | Active batch and source filters | Demo run state | Selected ExecutionRun context | Yes | Yes | ExecutionRun | Preserve | None | Current | PRESERVE |
| Catalog | Search | Local text filtering | Fixture records | Server-side query | Yes | Canonical fields | Field status preserved | Preserve | None | M2R | PRESERVE |
| Catalog | Decision filter | BUY/REVIEW/PASS select | Simulated decisions | Server-side decision filter | Yes | Yes | Decision output | Preserve | None | M2R | PRESERVE |
| Catalog | ROI/profit/margin filters | Minimum thresholds; ROI and margin entered as percentages | Simulated/calculated demo values | Server-side thresholds and confidence mode; ROI/margin UI currently exposes ratios | Yes | Canonical economics | Status-aware | Preserve with percentage semantics | Frontend conversion/acceptance tests | Wave B / M2R.1 | IMPROVE |
| Catalog | HazMat/Bulky filters | Status filters | Simulated risk | Server-side risk filters | Yes | Status/severity | Risk semantics | Preserve | Severity confidence gap | M2R/M4 | PRESERVE |
| Catalog | Provenance filters | Amazon match status | Demo fixture/inferred/not-found | Field provenance filter | Yes | Field statuses | VERIFIED/INFERRED/NOT_FOUND/INVALID | Preserve | None | M2R/M4 | PRESERVE |
| Catalog | Sort | All listed columns, toggled direction | Local records | Allow-listed server-side sort | Yes | Sort fields | Snapshot | Preserve | Scale indexes later | M2R | PRESERVE |
| Catalog | Column visibility/order | Fixed demo columns | Local UI state | Configurable columns in localStorage | N/A | Preference only | N/A | Preserve | None | M2R | PRESERVE |
| Catalog | Pagination | Page size and pages | Local arrays | 25/50/100 server pagination | Yes | Canonical query | N/A | Preserve | None | M2R | PRESERVE |
| Catalog | Density and responsive table | Dense image table | Demo CSS/fixtures | Dense production grid and controlled overflow | UI | Yes | N/A | Improve | No image contract for thumbnail | M2R.1/final polish | IMPROVE |
| Catalog | Product identity | Image, source, brand, title, SKU | Fixture image/URL fields | Title, brand, SKU, ASIN/UPC, record_ref | Partial | No canonical image | Identity status | Recover identity; image separately | Image contract | Image pipeline | RECOVER |
| Catalog | Images / thumbnails | `ProductThumbnail`, fixed thumbnail slot and “No image” fallback | Relative supplier fixture image URLs | No images | No image in RecordOut | No | Unknown/demo only | **Required target behavior; productionize safely** | Canonical source, rights, provenance, caching | Wave C / Image pipeline | PRODUCTIONIZE |
| Catalog | Issues disclosure | Row issue count/details | Demo validation/engine | Row issue disclosure | Yes | Issues | Issue provenance | Preserve | None | Current | PRESERVE |
| Catalog | Full export | Export filtered local records | Local CSV generation | Existing complete-run download | Yes | Snapshot | Snapshot | Preserve separately | None | Current | PRESERVE |
| Catalog | Filtered export | Export current filtered view | Local demo CSV | Canonical query-equivalent export | Yes | Snapshot | Query metadata | Preserve | Scale/streaming at high volume | M2R/M4 | PRESERVE |
| Catalog | Favorites | Toggle star in rows | localStorage | Not implemented | No ownership | No | Local only | Future saved opportunities | Auth, ownership, persistence, isolation | Saved Opportunities | DEFER_BLOCKED |
| Catalog | Compare affordance | Favorites/compare route from catalog | Exact URL matches | Not implemented | No comparable identity | No | Cross-run unresolved | Future contextual Compare | Comparable-identity ADR | Compare | DEFER_BLOCKED |
| Catalog | Decision thresholds editor | Edit review/buy ROI policy | Local demo policy | Submitted thresholds only; no UI editor | Backend accepts config | Yes | Configuration | Future only if approved | Business decision/contract | ADR required | DEFER_BLOCKED |
| Product Detail | Run-scoped route | Run/source/record route | Local run storage | Canonical run/record route with direct lookup | Yes | Persisted snapshot | Run scoped | Stable deep link | None for lookup; presentation completed in F2 | F2 | IMPROVE |
| Product Detail | Not-found handling | Run/record not found states | Local demo state | API loading/error/404 states | Yes | Yes | Run scope | Preserve and stabilize | F2 presentation | F1/F2 | PRESERVE |
| Product Detail | Decision and reasons | Decision panel and reasons | Demo engine | Decision/reasons from snapshot | Yes | Yes | Decision/provenance | Preserve | None | Current/M3 | PRESERVE |
| Product Detail | Identity / ASIN / UPC / SKU / brand | Rich title and identifiers | Demo record | Canonical snapshot fields with run context and intentional no-image state | Yes | Canonical fields | Field status + provenance | Improve | Image contract remains blocked | F2 | IMPROVE |
| Product Detail | Supplier/source metadata | Source file, row, adapter, URL | Demo raw row and URL | Field-level source/source_reference preserved; run filename remains run metadata | Partial | Source and row reference available; URL absent | Domain provenance | Recover safe metadata | Canonical URL/source contract still absent | F1/F2 | RECOVER |
| Product Detail | External marketplace/supplier links | Supplier URL link | External URL from fixture | Not available canonically | No approved URL field | No | Unknown | Future safe links | Source URL contract/rights | Image/data pipeline | DEFER_BLOCKED |
| Product Detail | Economics | Cost, suggested/selling price, fees, shipping, profit, ROI, margin | Demo simulated/calculated | Profitability fields and statuses | Yes | Yes | FieldValue status | Preserve | None | M3 | PRESERVE |
| Product Detail | Break-even / max COG | Not prominent in demo cards | N/A | Current production fields | Yes | Yes | Calculated status | Preserve | None | M3 | PRESERVE |
| Product Detail | HazMat / Bulky | Status cards | Simulated demo risk | Status/severity fields | Yes | Yes | Risk status | Preserve | Severity provenance gap | M3/M4 | PRESERVE |
| Product Detail | Data quality / issues | Facts and grouped quality | Demo engine | Issues/data quality present with explicit missing/invalid semantics | Yes | Yes | Issue/status | Improve | None | F2 | IMPROVE |
| Product Detail | Full provenance / field trace | FieldTrace and process trace | Demo trace arrays | Progressive per-field evidence disclosure; legacy snapshots explicitly explain absent detail | Yes | New snapshots complete; legacy detail absent | Domain Provenance | Recover | None for current presentation; provider/image gaps remain separate | F2 | IMPROVE |
| Product Detail | Images | Detail image with fallback | Demo fixture URL | Not implemented | No canonical image | No | Demo only | Productionize safely | Image contract | Image pipeline | PRODUCTIONIZE |
| Product Detail | Market history | 90-day line/bar chart | Deterministic simulated series | Illustrative-only prototype | No provider | Fixture only | DEMO_FIXTURE | Preserve as labeled, then productionize | Authorized provider/data contract | Market data | DEFER_BLOCKED |
| Product Detail | Explanation | Reasons, quality, trace, raw row | Demo engine | Decision reasons, issue context, and persisted field evidence | Yes | Yes for new snapshots | Provenance/issue | Improve | None | F2 | IMPROVE |
| Product Detail | Compare action | Back to compare context | Exact matches | None | No | No | Identity unresolved | Future | Comparable identity ADR | Compare | DEFER_BLOCKED |
| Dashboard | Empty state / upload CTA | No active demo run guidance | Local state | Real empty/retry states | Yes | Yes | Run state | Preserve | None | Current | PRESERVE |
| Dashboard | Run/source filter | Select source file | Local multi-file demo | Selected persisted run | One file/run | Yes | ExecutionRun | Preserve run scope | Multi-file only if approved | Current | PRESERVE |
| Dashboard | KPIs | Files, records, decisions, issues, avg ROI/margin, demo profit | Demo analytics | Real totals, avg ROI/profit, issues | Yes | Yes | Snapshot analytics | Preserve real subset | No multi-file KPI contract | Current | PRESERVE |
| Dashboard | Decision distribution | Bar chart | Demo engine decisions | Donut/Bar real analytics | Yes | Yes | Decision output | Preserve | None | Current | PRESERVE |
| Dashboard | HazMat/Bulky charts | Bar charts | Simulated risk | Status/severity visualizations | Yes | Yes | Risk fields | Preserve | None | Current | PRESERVE |
| Dashboard | Provenance visualization | Amazon match chart | Demo fixture/inferred/not-found | Provenance breakdown | Yes | Yes | Field statuses | Preserve | None | Current | PRESERVE |
| Dashboard | Profitability summary | Avg/total demo economics | Demo calculations | Real profitability summary | Yes | Yes | Calculated status | Preserve | None | Current | PRESERVE |
| Dashboard | Supplier price discounts | Bar chart | Demo derived prices | `price_spread` projection on the analytics endpoint; VERIFIED selling price and recorded COG only | Yes | Yes | Excludes records lacking either side, never assumes | Done (Wave D) | None | Wave D / Dashboard analytics | PRODUCTIONIZED |
| Dashboard | Brand distribution | Bar chart | Demo records | `brands` projection with `not_recorded` counted separately | Yes | Yes | Unbranded never merged into a brand | Done (Wave D) | None | Wave D / Dashboard analytics | PRODUCTIONIZED |
| Dashboard | Data-quality issue types | Bar chart | Demo engine | `issue_types` grouped by canonical `ProcessingIssue.code` | Yes | Yes | Snapshots predating `issue_codes` are dropped, not guessed | Done (Wave D) | None | Wave D / Dashboard analytics | PRODUCTIONIZED |
| Dashboard | Opportunity ranking | Top profit list, explicitly simulated | Demo engine | Absent | Ranking not approved | No safe ranking contract | Mixed/simulated | Future review query, no ranking yet | Opportunity ADR and evidence policy | Opportunity query | DEFER_BLOCKED |
| Dashboard | Multi-source analytics table | Per-file analytics | Local multi-file state | Absent one-file production model | No | No | Demo only | Future if multi-file approved | Multi-file run model | Data/API foundation | DEFER_BLOCKED |
| Runs | Run history | Local runs list | localStorage | Real persisted run list | Yes | Yes | ExecutionRun | Preserve | None | Current | PRESERVE |
| Runs | Status/timing/counts/warnings | Batch summaries | Demo run object | Real run metadata | Yes | Yes | ExecutionRun | Preserve | None | Current | PRESERVE |
| Runs | Open run | Route to detail | Local router | Run Detail route | Yes | Yes | Run scope | Preserve | None | Current | PRESERVE |
| Runs | Duplicate/reprocess | Local clone action | localStorage | Not implemented | No approved semantics | No | Local demo | Reject as current behavior | Requires explicit reprocess contract | ADR required | REJECT_WITH_REASON |
| Runs | Delete/reset demo runs | Local destructive controls | localStorage | Not implemented | Persistence ownership policy absent | N/A | Local only | Reject demo behavior | Retention/authorization policy | ADR required | REJECT_WITH_REASON |
| Run Detail | Batch/file summary | Included files table, rows, warnings/errors | Local demo run | Single ExecutionRun summary and records | Yes | Yes | ExecutionRun | Preserve single-file; future grouping | Multi-file model | Current | PRESERVE |
| Run Detail | Decision analytics | Combined BUY/REVIEW/PASS | Demo derived analytics | Backend analytics-backed outcomes | Yes | Yes | Snapshot | Preserve | None | Current | PRESERVE |
| Run Detail | Record review | Table and links | Local records | Real record review and Catalog handoff | Yes | Yes | Snapshot | Preserve | Contract A for deep links | M3 | PRESERVE |
| Run Detail | Download | Batch export | Local CSV | Real full-run download | Yes | Yes | Snapshot | Preserve | None | Current | PRESERVE |
| Run Detail | Reprocess/delete actions | Demo controls | localStorage | Absent | No | No | Local only | Reject/defer | Explicit run lifecycle policy | ADR required | REJECT_WITH_REASON |
| Appearance | Theme | Light/dark | local preference | Light/dark token system | UI | Preference | N/A | Preserve | None | Current | PRESERVE |
| Appearance | Accent/logo/background | Local uploads and preview | Data URLs/localStorage | Production controls and contrast warning | UI | Preference | N/A | Preserve with safety limits | None for local preference | Current | PRESERVE |
| Appearance | Global custom brand persistence | Browser-only | localStorage | Browser-only preference | No server ownership | Preference | N/A | Preserve locally; not business data | Auth/profile contract if shared | Future | DEFER_BLOCKED |
| Mobile | Catalog responsive table | Dense horizontal table | Demo CSS | Controlled production overflow/responsive layout | UI | Yes | N/A | Improve | Image/column contracts for richer identity | Catalog polish | IMPROVE |
| Mobile | Product detail responsive cards | Stacked panels | Demo CSS | Responsive production detail | UI | Partial | N/A | Preserve/improve | Complete detail contract | M3 | IMPROVE |
| Architecture | Record identity | Run/source/record composite | Demo keys | `(execution_id, record_ref)` | Yes | Yes | Run scoped | Preserve; no global Product | None | Current/M3 | PRESERVE |
| Architecture | Exact comparison identity | Shared supplier URL | Demo exact-match helper | Not approved | No | No | Unverified URL | Future only | Comparable-identity ADR | Compare | DEFER_BLOCKED |
| Architecture | Saved ownership | Run/source/record local key | Demo localStorage | Not implemented | No auth/ownership | No | Local only | Future Saved Opportunities | Auth, ownership, persistence, isolation | Saved Opportunities | DEFER_BLOCKED |
| Architecture | AI explanations | Not implemented; demo trace only | Demo traces | AI Analyst design only | No implementation | Structured data only | Must cite source | Future | AI ADR already design-only; implementation approval | AI phase | DEFER_BLOCKED |

## Classification summary

The matrix deliberately keeps demo-only capabilities in the target contract
when they express a valid product need, while marking simulated or unsafe
behaviour as rejected rather than silently promoting it. “PRODUCTIONIZE” does
not mean “copy the fixture”: it means create an approved source, contract and
provenance path first.

### Current baseline versus target

- `docs/architecture/PRODUCT_CAPABILITY_BASELINE.md` protects implemented
  production behavior only.
- This matrix and `TARGET_PRODUCT_CAPABILITIES.md` protect the broader target
  product, including blocked images, provider-backed market history, richer
  evidence, and future identity/ownership decisions.
- Every later phase must report both checks; a green test suite is not proof of
  product parity.

## Git-history findings

## R3 behavioral corrections

R3 independently exercised the demo and current production instead of relying
on route/component inventory alone:

- Demo `ImportPage` and `batch.ts` prove an exact **10-file** queue, mixed CSV/XLSX
  acceptance, individual remove/status/error rows, sequential parsing and one
  aggregate batch result. Wave A productionized the queue and aggregate
  child-run model; **ADR-026 then lifted the CSV deferral** -- CSV and XLSX now
  share one tabular contract through `_import_rows`, so a batch may mix both
  and the per-file run contract is unchanged.
- Demo Catalog ROI and margin inputs are percentage semantics (`roi * 100`).
  Production reached the same semantics in Wave B: `percentInputToRatio` is the
  single boundary conversion, so `30` typed by the operator issues `min_roi=0.3`
  to the canonical query, the chips read `30%`, and the export carries the same
  converted ratio with an explicit units row. Domain ratio semantics unchanged.
- Demo `ProductThumbnail` is a real interaction with a no-image fallback, not
  decorative styling. Its fixture URL is unsafe production data, but the
  thumbnail behavior remains a required target capability.
- Demo Dashboard contains internal supplier-discount, brand-distribution and
  issue-type charts. These are not Keepa/Amazon capabilities and are not
  provider-blocked; production currently lacks their analytics projections.
- Demo Catalog header sorting was exercised as full-dataset in-memory ASC/DESC.
  Production sorting was exercised through live network requests and is
  server-side for Price, COG, Profit, ROI and Margin (and the allow-listed
  identity/risk/decision fields). This is parity-confirmed behavior, not merely
  a documented claim.

The production history shows the premium shell, real Dashboard, server-side
Catalog and Run/Run Detail were introduced in the commits leading to
`8ea0cb6` (notably `9127c64`, `800af9f`, `b1b2af2`, `587bfac`, `bf7169d`).
The committed production baseline did **not** contain the demo's committed
product-image pipeline, Product Detail fixture market-history implementation,
multi-file demo engine, Compare, or Favorites. Those are parity targets that
were never safely migrated, not proven removals from committed production.
R1 recovered the Runs loading/real-data/empty/error-retry behavioral coverage;
the later 61-test count must not be read as proof of demo parity.

## Waves B-D reconciliation (2026-08-19)

Rows previously marked `PRODUCTIONIZE`/`RECOVER`/`DEFER_BLOCKED` whose blocker
is now genuinely gone:

| Row | Was | Now | What actually changed |
|---|---|---|---|
| Upload — CSV/XLSX multi-file queue | PRODUCTIONIZE | **Done** | ADR-026 accepts CSV; a batch may mix `.csv` and `.xlsx` |
| Catalog — ROI/profit/margin filters | IMPROVE | **Done** | UI takes percentages, query carries canonical ratios, export metadata states the unit |
| Dashboard — supplier price discounts | PRODUCTIONIZE | **Done** as `price_spread` | No supplier *suggested retail* column exists in production, so the spread is measured against the selling price the Profitability Engine used. Semantic mapping recorded here rather than assumed |
| Dashboard — brand distribution | PRODUCTIONIZE | **Done** | `brands` projection; records with no brand stay in `not_recorded` |
| Dashboard — data-quality issue types | PRODUCTIONIZE | **Done** | `issue_types` grouped by canonical code, via a new additive `issue_codes` snapshot field |
| Dashboard — multi-source analytics table | DEFER_BLOCKED | **Unblocked** | The multi-file run model now exists; per-source counts live on the Batch view and Run Detail's batch context |
| Run Detail — batch/file summary | PRESERVE (single-file) | **Extended** | Included-file table when the run belongs to a batch, with each file's own counts |
| Product Detail — supplier/source metadata | RECOVER | **Done for what is canonical** | Source file, row and source type read from stored provenance. A supplier *URL* is still absent: no approved link field exists |
| Product Detail — economics | PRESERVE | **Extended** | `total_fees`, `seller_proceeds`, `total_cost` persisted and shown. A supplier *suggested price* remains absent for the same reason as above |

Rows deliberately unchanged, with the reason restated so they cannot be lost:

- **Images / thumbnails** stay `PRODUCTIONIZE`. No canonical image field
  exists. A fixed media slot with an honest unavailable state was added so the
  requirement survives, but no URL is invented, scraped or copied.
- **Market history** stays `DEFER_BLOCKED`. The Product Detail fixture remains
  labeled `DEMO_FIXTURE` / `NOT VERIFIED` / `NOT INFERRED FROM PRODUCTION
  DATA` and is not an input to any decision.
- **Favorites, Compare, cross-run identity, saved ownership** stay
  `DEFER_BLOCKED`. `interfaces/api/auth.py` exists but is inactive and carries
  no per-user data model, so nothing here became implementable.
- **Opportunity ranking, reprocess/delete run actions** stay blocked/rejected:
  each needs a business decision, not code.

## No-silent-feature-loss rule

Before any implementation phase, compare the phase diff to this matrix and the
current baseline. A capability may only become `DEFER_BLOCKED` or
`REJECT_WITH_REASON` with its blocker and decision recorded here or in an
accepted ADR. Demo fixtures, localStorage business state, simulated stages,
simulated marketplace data and unknown image URLs may never be promoted by
omission.
