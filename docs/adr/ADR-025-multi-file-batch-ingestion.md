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

## Security amendment — Gate B1, 2026-09-30

**APPROVED by explicit user instruction:** preserve migrations
`20260819000002_batches.sql` and `20260819000003_batch_file_counts.sql`
byte-for-byte. Independent migration
`20260928000006_batch_table_security.sql` enables RLS on `public.batches`
and `public.batch_files`, without FORCE or policies, and revokes all table
privileges from `PUBLIC`, `anon` and `authenticated`. The revocation explicitly
covers `TRUNCATE`, which RLS does not protect. Ownership, backend/owner access
and global default privileges stay unchanged. Backend access assumes the
existing direct database owner path; no new backend role or grant is introduced.

The future remote sequence must execute 000002 → 000003 → 000006 → verification
→ COMMIT in one transaction, with rollback on failure. Applying 000002/000003
alone would expose tables through inherited grants. Gate B0 is closed BLOCKED;
Gate B1 prepares and validates local artifacts only. Remote deployment and
migration-history handling require a separate review; this amendment authorizes
neither remote writes nor history repair.

Tests in `tests/integration/test_postgres_batch_security.py` use the existing
disposable PostgreSQL 16 cluster fixture with a private Unix socket and no TCP.
They apply the real migration files, reproduce permissive schema-scoped grants
only in disposable databases, connect as non-superuser roles, distinguish
privilege denial from RLS default-deny, verify backend round-trip access, and
exercise pre-COMMIT verification and failure rollback. Their migration ledger
is synthetic and local; it is not evidence of remote migration history.
Measured local results and limitations are recorded in
[the Gate B1 evidence record](../research/GATE_B1_BATCH_SECURITY_20260930.md).

## Open discrepancy — aggregate status (PENDING DECISION)

The original Decision paragraph says a `PARTIAL_SUCCESS` child without any
failed/rejected sibling yields aggregate `SUCCESS`. Current
`domain/batch.py::aggregate_batch_status` instead returns `PARTIAL_SUCCESS`
whenever a non-failed batch contains any child that is not `SUCCESS`.
For example, one `PARTIAL_SUCCESS` child alone yields `PARTIAL_SUCCESS`.
That discrepancy remains explicit and unresolved; Gate B1 changes no status
semantics. Resolving it requires a separate architectural decision. Native
financial evidence for batches, per-file persistence/export failure isolation,
additional SQL constraints for the ten-file limit and retry redesign also
remain outside this security amendment.

Persistence/export failure isolation is analysed in
[ADR-050](ADR-050-batch-persistence-atomicity-idempotency.md) (**Propuesta**,
2026-10-16, not approved); until it is decided, the behavior above stands and is
pinned by `tests/integration/test_api_batch_persistence_failures.py`.
