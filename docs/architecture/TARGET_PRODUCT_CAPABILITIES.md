# Target Product Capabilities

## Purpose

This is the product target contract created by R2. It is intentionally broader
than the current production preservation baseline. The baseline protects what
exists; this document protects what the finished JUVAl product must recover or
build without silently losing maturity during future UI migration.

Authoritative inventory and evidence: [DEMO_PRODUCTION_PARITY_MATRIX.md](DEMO_PRODUCTION_PARITY_MATRIX.md).
Current implemented minimum: [PRODUCT_CAPABILITY_BASELINE.md](PRODUCT_CAPABILITY_BASELINE.md).

## MUST HAVE

Wave A implementation note (2026-08-19): multi-file ingestion is productionized
with a persisted Batch and one child `ExecutionRun` per file.

Waves B-D note (2026-08-19): **CSV is no longer deferred** — ADR-026 accepts it
as a production input format sharing one validation and provenance path with
XLSX. Percentage ROI/margin semantics, the internal analytics projections
(sourcing spread, brand mix, issue types), batch navigation and the Product
Detail source/economics gaps are all closed. See
`PRODUCT_BEHAVIORAL_PARITY.md` for the per-capability evidence.

These capabilities are required for a complete production product and must be
preserved in every later phase:

1. **Operational shell:** Dashboard, Upload, Catalog, Runs, and contextual
   Settings/Appearance; responsive navigation; Light/Dark themes and accessible
   keyboard/focus behavior.
2. **Truthful ingestion workflow:** real XLSX submission, client validation,
   explicit configuration, honest indeterminate processing, SUCCESS,
   PARTIAL_SUCCESS and FAILED states, warnings/issues, retry, review and
   Catalog handoff. No simulated pipeline stages.
3. **Multi-file supplier ingestion:** accept up to ten CSV/XLSX files in one
   visible queue, with per-file validation/status, individual failure handling,
   aggregate result and file-to-run provenance. **Implemented** (ADR-025,
   ADR-026): `POST /api/v1/batches`, one child `ExecutionRun` per file,
   per-file counts, and a persisted `/batches/:batch_id` view.
4. **Run-scoped Catalog:** selected ExecutionRun context; server-side search,
   BUY/REVIEW/PASS filtering, economics filters with explicit confidence mode,
   HazMat/Bulky and provenance filters, allow-listed server sorting, 25/50/100
   pagination, configurable presentation columns, issues, full-run download,
   query-equivalent filtered export, record drill-down, loading/empty/error
   states and responsive dense data presentation.
5. **Decision-grade data:** controlled currency/percentage formatting; profit,
   ROI, margin, break-even and max COG; exact BUY/REVIEW/PASS semantics; risk
   and issue visibility; no raw precision or confidence collapse.
6. **Verification integrity:** VERIFIED, INFERRED, NOT_FOUND and INVALID remain
   distinct in API, filters, exports, Dashboard, Catalog and Detail. Calculated
   values follow the weakest-input rule and are never silently upgraded.
7. **Auditable runs:** real persisted ExecutionRun identity, status, timing,
   counts, warnings/errors, analytics-backed outcomes, record review, download
   and Catalog navigation.
8. **Stable Product Detail:** run-scoped `(execution_id, record_ref)` identity,
   canonical persisted snapshot lookup, deep-link/refresh safety, 404/error
   handling, and the hierarchy Decision → Identity → Economics → Risks → Data
   Quality → Provenance → Market → Explanation → Actions. F1 establishes the
   lookup and payload foundation; F2 presents the decision-oriented surface with
   progressive evidence disclosure and explicit legacy-snapshot handling.
9. **Accessible responsive quality:** WCAG AA labels/status announcements,
   keyboard table/filter controls, desktop density, tablet/mobile usability,
   controlled overflow, and intentional Light/Dark semantic colors.

## SHOULD HAVE

These are valid product capabilities represented by the prior experience and
should be productionized when their contracts are ready:

- **Canonical product identity enrichment:** title, brand, SKU, ASIN/UPC,
  supplier/source metadata, source row and safe external links. Product images
  may appear only after the image contract below is approved.
- **Catalog product thumbnails:** compact thumbnail support with a deliberate
  no-image fallback remains required independently of the unresolved image
  source contract.
- **Image pipeline:** run-scoped image URL/value, source, verification/status,
  rights/safety classification, fallback and caching policy. No demo URL may be
  used as production truth.
- **Richer Product Detail evidence:** full persisted domain provenance
  (`source`, `source_type`, `retrieved_at`, `method`, optional confidence,
  evidence and source reference), field traces, raw-source context where safe,
  and explanation grounded in real reasons/issues. F1 now preserves this
  payload for new snapshots; F2 exposes it in the approved hierarchy. Historical
  snapshots explicitly disclose when detailed provenance was not stored.
- **Authorized market history:** visibly labeled provider-backed history with
  explicit source/freshness/provenance, Line and Bar views where appropriate,
  and no influence on decision until business approval says otherwise.
- **Dashboard enrichment:** **implemented** — `price_spread` (selling price
  minus COG, VERIFIED prices only), `brands` (with `not_recorded` kept
  separate) and `issue_types` (by canonical `ProcessingIssue.code`), all
  aggregated in the persistence layer from canonical fields. Source/batch
  analytics are served by the Batch view and Run Detail's batch context rather
  than duplicated on the Dashboard. No opportunity ranking exists: that still
  needs an approved decision model.
- **Intentional no-image identity state:** Catalog and Detail remain strong
  when no image exists; absence must not imply a fake product photo.
- **Advanced source/batch grouping:** only if multi-file ingestion and
  provenance semantics are approved; one upload currently maps to one run.

## FUTURE / BLOCKED

Each item remains in the target contract and is not deleted because its current
dependency is missing:

| Capability | Exact dependency | Safe interim rule |
|---|---|---|
| Compare | Accepted comparable-identity ADR, including exact identity, conflict handling and cross-run semantics | Do not add route or button; contextual Catalog/Detail later |
| Saved Opportunities | Authentication, ownership, persistence, organization isolation and retention policy | Do not use Favorites/localStorage as business state |
| Cross-run/global product identity | Separate identity ADR and migration strategy | Keep `(execution_id, record_ref)` only |
| Market history | Authorized provider/data-source decision, freshness, cost, provenance and failure behavior | `DEMO_FIXTURE` only, visibly not verified, never decision input |
| Product images | Canonical source field, source/provider authorization, rights, verification/status, fallback and cache policy | No demo thumbnails or silent external URLs |
| “Top opportunities” ranking | Business ADR combining decision, economics, risk, confidence and data quality | Safe first query is “REVIEW requiring attention,” not highest ROI |
| ~~Multi-file batch analytics~~ | **Unblocked and implemented** (ADR-025/ADR-026): the ingestion/run model and file-level provenance now exist | Files submitted/processed/succeeded/failed and per-file records, warnings and errors are shown on the Batch view and in Run Detail's batch context |
| Reprocess/delete run actions | Explicit lifecycle, retention, authorization and audit policy | Preserve immutable run history |
| AI Analyst | Approved implementation phase and read-only citation contract | May explain structured results only; never calculate or invent |

## Protection model

Future phase gates require all of the following:

1. Functional tests for current baseline and newly recovered target behavior.
2. Rendered visual QA in Light/Dark and desktop/mobile states.
3. A parity comparison against the matrix, identifying preserved,
   improved, moved, deferred-with-reason, or rejected-with-reason capabilities.

No implementation may remove a target capability merely because the current
backend lacks it. It must either add the required contract in its dependency
phase, or record an explicit `DEFER_BLOCKED` decision with the exact blocker.

## Dependency-aware recovery sequence

1. **R2 contract (complete):** maintain this matrix and target contract.
2. **Data/API foundation (F1):** canonical single-record lookup, additive full
   provenance snapshot payload, source metadata, and any approved query/export
   projections. This is the recommended immediate implementation phase; it is
   implemented by F1; it does not authorize F2 UI work.
3. **Product Detail completion (F2):** consume F1 lookup/provenance, stabilize
   evidence/source presentation, and preserve labeled market fixture behavior.
4. **Catalog completion:** keep M2/M2R query/filter/export behavior, then close
   any remaining target identity, image-slot and analytics gaps only when their
   contracts are real. No visual redesign without rendered proof.
5. **Dashboard and Run enrichment:** add only real analytics projections,
   source/batch context and review-oriented actions; do not introduce ranking
   or simulated charts.
6. **Image pipeline:** after source/rights/provenance/caching approval, add
   additive image data to snapshots and both persistence adapters.
7. **Market history:** after authorized provider approval, add provider-backed
   history and Line/Bar presentation with explicit freshness and provenance.
8. **Compare:** after comparable-identity ADR and tests.
9. **Saved Opportunities:** after authentication/ownership/persistence and
   isolation approval.
10. **Final parity/polish gate:** full demo-to-target matrix, capability tests,
    accessibility, responsive Light/Dark visual review and user acceptance.

R2 does not authorize any of steps 2–10; it only establishes the order and the
dependencies so future work cannot trade a cleaner redesign for silent product
feature loss.
