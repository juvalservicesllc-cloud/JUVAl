# Product Capability Preservation Baseline

## Status

**RECORDED — R1, 2026-08-19.** This baseline protects approved production
capabilities while the premium design system evolves. It does not make the
partial Product Detail, product images, or a market-data provider implemented
capabilities.

## Protected production capabilities

| Surface | Minimum capability that future frontend work must preserve |
|---|---|
| App shell | Dashboard, Upload, Catalog, Runs, Settings/Appearance; responsive navigation; light/dark themes. |
| Upload / processing | Real backend submission, client validation, honest indeterminate processing that names every submitted file, success, PARTIAL_SUCCESS, failure, review action, Catalog handoff, and the ordered up-to-10 CSV/XLSX batch queue (ADR-025/ADR-026) with per-file outcomes, per-file record counts and child-run traceability. |
| Catalog | Immutable run-scoped records; server-side search, BUY/REVIEW/PASS filter, sorting, 25/50/100 pagination; percentage ROI/margin inputs that issue canonical ratios; configurable columns; identity with its media slot; profit/ROI/margin; HazMat/Bulky; field verification status; issues; loading/empty/error/retry states; responsive table behavior; complete-run download and query-equivalent filtered export. |
| Dashboard | Real analytics only; decision distribution with supported Donut/Bar controls; HazMat/Bulky and provenance visualizations; profitability summary; sourcing spread, brand mix and issue-type projections; Recent Runs. No demo analytics fallback. |
| Runs | Real persisted runs; loading, row, empty, error/retry, sorting, status, timing, record totals, warnings/errors, and Run Detail navigation. |
| Run Detail | Real `ExecutionRun` identity/status/filename/timing/totals/warnings; PARTIAL_SUCCESS treatment; analytics-backed outcomes; batch context with the included-file table when the run came from a batch; record review; download; Catalog handoff. |
| Batch Detail | Persisted `/batches/:batch_id` route: aggregate status and counts plus the included-file table, each processed file linking to its own independent run. |

## Reserved and contract-blocked capabilities

- **Product Detail:** now a protected baseline, not a partial route. It
  preserves canonical `(execution_id, record_ref)` lookup, decision and
  reasons, identity, source file/row/type from stored provenance, economics
  including fees/seller proceeds/total landed cost, risks, data quality, full
  field provenance with explicit legacy handling, the labeled market fixture,
  and back-navigation.
- **Product images:** not a current production capability. An approved image
  contract must define source, verification/provenance status, rights/safety,
  fallback, and caching policy. Demo URLs are not production truth. The
  *thumbnail slot* is nonetheless protected: Catalog and Product Detail both
  render a deliberate no-image state, so the requirement cannot be lost by
  omission and adding a canonical image later needs no redesign.
- **Market history:** desired product capability. Until an authorized provider
  exists, it may only be a visibly labeled `DEMO_FIXTURE`; never `VERIFIED`.
  A final presentation should support Line and Bar where appropriate, without
  influencing BUY/REVIEW/PASS, ranking, or filtering.

## Mandatory non-regression gate

Every frontend migration phase must record: what changed; protected
capabilities before the change; proof that they remain; tests that exercise
them; and visual states reviewed. A phase passes only when all three are
complete:

1. Functional tests pass.
2. Relevant light/dark, desktop/mobile visual QA passes.
3. A capability-regression check confirms no protected capability was removed,
   degraded, or silently replaced with demo/fake data.

Green tests alone do not satisfy this gate. A removed test must be replaced by
an equivalent or stronger user-visible behavioral test, or its intentional
supersession must be documented.

## Related

`PRODUCT_EXPERIENCE.md`, ADR-024, and `docs/PRODUCT_CAPABILITY_MATRIX.md`.
