# ADR-025 — Multi-file batch ingestion

**Estado: Aceptada para Wave A**  
**Fecha: 2026-08-19**

## Contexto

The target product accepts up to ten supplier files in one visible queue.
`ExecutionRun` already represents one deterministic processing execution and
its persisted snapshot is run-scoped. Overloading that identity with several
files would weaken reproducibility and failure isolation.

## Decision

Use **one `ExecutionRun` per processable file** and an explicit `Batch` that
groups the ordered child outcomes. A batch has a stable `batch_id`, creation
timestamp, aggregate status and up to ten `BatchFile` entries. A rejected
file has no child execution; a processed file always points to its child
`execution_id`.

Production Wave A accepts XLSX only because that is the real importer
contract. CSV remains a target capability and is deferred until the importer
and validation contract support it.

> **Amendment 2026-08-19 — superseded by ADR-026.** The deferral condition
> stated above was met: the importer now reads CSV through the same header
> resolution, validation and provenance path as XLSX. A batch may mix `.csv`
> and `.xlsx` files. Nothing else in this ADR changes — one `ExecutionRun`
> per file, the ten-file limit and the aggregate status rules all stand.

Batch files are processed sequentially. Each child is persisted independently
when `persist=true`, so a bad workbook cannot invalidate successful siblings.
Aggregate status is deterministic: all children successful (including a
child `PARTIAL_SUCCESS` only when no file failed/rejected) is `SUCCESS`; at
least one success/partial plus any failure/rejection is `PARTIAL_SUCCESS`; no
successful or partial child is `FAILED`.

Retry in Wave A means submitting the failed file as a new child execution in
a new batch. No in-place mutation or ambiguous whole-batch retry is exposed.

Existing single-file `POST /api/v1/runs` and run-scoped Catalog, Detail and
exports remain unchanged. Batch export is deferred; existing exports remain
per execution run. Batch state is persisted in SQLite and Supabase tables,
never browser storage. Historical single-file runs remain readable.

## Contract

- `POST /api/v1/batches` accepts repeated `files` multipart parts, thresholds,
  fees and `persist`; more than ten files returns `422`.
- `GET /api/v1/batches/{batch_id}` returns the persisted batch summary.
- `GET /api/v1/runs/{execution_id}/batch` returns the batch a child run belongs
  to, or `404` when the run was submitted on its own. A `404` here is a normal
  outcome, not an error state.
- File names are basename-only business metadata; local paths are discarded.
- `BatchFile` preserves ordinal, filename, content type, byte size, status,
  warnings/errors, optional child execution ID, and the child run's own
  `records_total`, `records_processed`, `records_with_errors` and
  `warning_count`. A `REJECTED` file never ran, so its counts stay `0` — that
  is "never processed", not a measured zero, and the UI renders it as such.
- Child records retain the existing snapshot/provenance semantics and are
  discoverable through their `(execution_id, record_ref)` identity.

## Consequences

This keeps auditability, source-file traceability and adapter parity while
leaving room for future source-level Catalog analytics and batch Run Detail.
CSV ingestion, batch export, per-file retry UI and richer batch navigation are
explicit follow-up work, not silently implied by this contract.
