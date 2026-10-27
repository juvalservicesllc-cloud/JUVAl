# Juval — Project Status

## 2026-10-27 — GOLDEN 17 final audit

**IMPLEMENTED (audit fixes only; no decision, formula or threshold change).**

Two defects were found and fixed:

1. **Source type.** The suggested price was marked `SUPPLIER_FILE`, which
   attributes to the supplier a value whose author is not accredited. It is now
   `USER_INPUT`, as ADR-052 §3.6 decided for declared demand, with evidence
   "author not accredited". The Catalog tooltip no longer says "declared by the
   supplier".
2. **Raw values.** `raw_value`, `currency_raw` and the diagnostics were trimmed.
   They now keep the cell text as received.

**ADR-053** is now "Aceptada con condiciones". The ADR-046 §20.1 amendment, S5
and S6 remain PENDING user ratification.

**New tests:**
- exact long decimals;
- raw whitespace;
- a currency-only file;
- a duplicate currency column;
- BUY unchanged on an engine-built record (the importer cannot reach BUY);
- a round trip on a disposable PostgreSQL 16 cluster, including NOT_CAPTURED.

**Gates:**
- pytest: 1865 passed, 129 skipped, with `JUVAL_POSTGRES_BIN`. The skips are the
  session-DB lab, nginx, live Supabase (deliberately unused) and 2 skipped by
  design.
- vitest: 177 passed, 10 skipped.
- tsc, oxlint and build: clean.
- E2E Chromium: 17/17 twice, and 5/5 for the G17 spec alone.

**GOLDEN 17 ratified RECOVERED (12/24).** ADR-040 is unchanged: the measurement
scripts were not re-run and no criterion moved.

## 2026-10-27 — GOLDEN 17: supplier suggested price (ADR-053)

**IMPLEMENTED (evidence only; no decision, formula or threshold change).**

- **What a file can declare.** Two optional columns,
  `supplier_suggested_price` and `supplier_suggested_price_currency`. They have
  no aliases.
- **Where it is stored.** `SourcingRecord.supplier_suggested_price`, outside
  `Product`.
- **Status.** A usable value is INFERRED (never VERIFIED), with the declared
  currency as its unit (source type corrected to USER_INPUT by the final audit).
- **Unusable values.** Zero, negative, non-numeric and unknown currency are
  INVALID. They keep their raw cells and raise a WARNING.
- **Empty cell.** NOT_FOUND, never 0.
- **Where it appears.** In the snapshot, the API, both exports, the preview
  group, a Catalog column and a Product Detail panel in `frontend-next/`.
- **No effect on decisions.** Decisions, reasons, profit and ROI are identical
  with and without the columns (test). `processing/` never references the field
  (test).
- **Storage.** No migration: the snapshot is JSON in SQLite and JSONB in
  Supabase.
- **ADR-053** amends ADR-046 §20.1 for this single field. S5 (zero is invalid)
  and S6 (no currency case folding) await user review.

**GOLDEN:** 11/24 → 12/24 RECOVERED (item 17; see the parity matrix §25).
ADR-040 (44/68, 17/68) is not re-measured here.

**Git integration.** Bundle
`/srv/juval-exchange/outbox/juval-a174825..b820d5a.bundle`
(`a174825..master`, head `b820d5a`, 34 commits), with SHA-256
`5140c535f378874718f1acf33677689d549376defcbf56f8a4115063ce7b4b33`.
`git bundle verify` passed, and a fast-forward of a disposable clone of the seed
passed too. It was not imported into the operational repository and nothing was
pushed. The GOLDEN 17 commits came after the bundle and are not in it.

## 2026-10-26 — frontend-next shell overflow and favicon fixed

**IMPLEMENTED (UX stabilization; no functional change).** Both shell findings
from the E2E validation are fixed.

**Overflow.** The shell rule was `main{max-width:1560px;width:100%;margin:auto;padding:0 36px 48px}`
with `content-box`: the 1184px grid cell plus 72px of padding made a 1256px box,
so every page was 64px wider than a 1440px viewport and clipped the Light/Dark
switch. The fix adds `box-sizing:border-box` to that rule. `overflow` is not
hidden, and the layout, tokens and navigation are unchanged.

**Favicon.** `public/icon.svg` is a byte-identical copy of the project icon
`frontend/public/icon.svg`, linked from `index.html`. `public/favicon.ico` holds
the same SVG rasterized by Chromium at 16, 32 and 48px. `/favicon.ico` now
answers 200.

The E2E suite now asserts zero page overflow, an unclipped theme switch and no
HTTP errors at all (the favicon allowance is removed).

Gates: Playwright 12/12 in two runs; vitest 169 passed + 10 skipped; tsc,
oxlint and build clean. `demo/` keeps the original Golden CSS as the protected
reference.

## 2026-10-26 — frontend-next real-browser E2E for D7-D and D7-B

**IMPLEMENTED (validation; no decision rule changed).** `frontend-next/e2e/`
uses Playwright 1.62.1, the version `frontend/` already locks, as a dev
dependency. It runs headless Chromium against a disposable API, Vite and SQLite
on loopback ports 18771 and 18772; `npm run e2e`, see `e2e/README.md`. There are
12 tests, covering all 14 D7 scenarios, empty, loading and error states,
console and HTTP error monitoring, and desktop screenshots. Two consecutive runs
passed 12/12 with no flaky tests.

**Defect found and fixed.** `POST /api/v1/runs/preview` answered **500** for any
file with demand columns. `ImportPreviewColumnOut.group` did not admit
`declared_demand`, and the browser reported it as a CORS failure. Earlier tests
had missed it: the backend tests called `preview_import()` directly and the
frontend test mocked the response. The fix adds the value to the literal, plus
an API-level regression test.

**Reported, not fixed (pre-D7, Golden shell CSS identical in `demo/`).** Every
page is 64px wider than the viewport, because `main` has `width:100%` plus
padding with no border-box. `/favicon.ico` returns 404.

Gates: backend 1744 passed / 185 skipped (infrastructure-gated); PostgreSQL
parity 43/43; vitest 169 passed + 10 skipped; tsc, oxlint and build clean.
GOLDEN and ADR-040 unchanged.

## 2026-10-26 — D7-B: declared demand observations captured as evidence (ADR-052)

**IMPLEMENTED (ADR-052 Aceptada con condiciones; informative scope only).**
Optional `demand_*` columns become one ADR-046 `DemandObservation` per record on
`SourcingRecord.market_evidence` -- never on `Product.demand` or any decision
input. Strict whole numbers; INFERRED with USER_INPUT provenance (file, row,
column, method, captured instant); NOT_FOUND only with valid declared context;
INVALID keeps raw text; explicit window or declared month with explicit
timezone; naive instants need `demand_timezone`; DST gaps/folds refused; every
gap becomes a WARNING diagnostic. Snapshot document
`juval.adr046.demand-evidence` v1 (no migration), RecordOut fields and
DECLARED / NOT_DECLARED / NOT_CAPTURED, both exports, preview group, Product
Detail panel and a non-sortable Catalog column. One million declared units
still give REVIEW with DEMAND_UNKNOWN (mandatory test). `processing/`,
`product.py`, `decision.py`, `market_evidence.py` untouched. Tests: backend 40
new + 1 PostgreSQL parity; 674 affected backend tests passed / 7 live-Supabase
skips; frontend tsc clean, vitest 169 passed + 10 skipped (opt-in), live 9/9,
oxlint clean, build OK. Projection to the engine NOT authorized. GOLDEN and
ADR-040 unchanged.

## 2026-10-26 — ADR-052 proposed: declared demand observations (D7-B)

**PENDING DECISION.** `docs/adr/ADR-052-declared-demand-observations-ingestion.md`
(Propuesta) drafts an additive Amendment 1 to ADR-046 (ADR-046 itself unchanged)
and the D7-B import contract: explicit `demand_*` columns with mandatory window,
`observed_at`, population and method; INFERRED-only usable values with
file/row/column provenance; NOT_CAPTURED / NOT_DECLARED / NOT_FOUND kept
distinct; a `SourcingRecord.market_evidence` component the engine never reads;
snapshot key `demand_evidence` v1; read-only API/export/UI. Includes the
mandatory test that high declared demand leaves REVIEW unchanged. Decisions
E1–E8 await approval. No code changed; GOLDEN and ADR-040 unchanged.

## 2026-10-26 — D7-D: informative "pending demand verification" for REVIEW

**IMPLEMENTED (approved D7-D).** New snapshots store `decision_reason_codes`
beside the unchanged reason text; one definition
(`application/review_classification.py`) marks REVIEW records whose only code
is DEMAND_UNKNOWN as PENDING_DEMAND_VERIFICATION and REVIEW snapshots without
codes as NOT_CLASSIFIABLE (never parsed from text). Filter on `/records` and
`/records/export` (same SQL on SQLite and PostgreSQL, export column + metadata),
analytics count, Catalog filter, Dashboard panel and Product Detail note in
frontend-next. Decision engine, thresholds and stored decisions untouched
(`processing/`, `domain/` diff empty); demand is still never imported, so BUY
remains unreachable for imported files. No migration (JSON key). Tests:
backend 10 new + 1 PostgreSQL parity (disposable cluster), 260 affected backend
tests passed / 3 live-Supabase skips; frontend tsc clean, vitest 160 passed +
8 skipped (opt-in), live 8/8, oxlint clean, build OK. ADR-051 still Propuesta;
GOLDEN unchanged (not a Golden item). ADR-040 unchanged.

## 2026-10-26 — ADR-051 proposed: reproducible decision configuration

**PENDING DECISION.** `docs/adr/ADR-051-reproducible-decision-configuration.md`
(Propuesta) inventories every BUY/REVIEW/PASS parameter (none is stored on
`ExecutionRun`), and proposes an immutable per-run `juval.decision-configuration`
v1 snapshot, a versioned rule-set identity, NOT_RECORDED for historical runs,
re-run as a new upload linked by `input_hash`, and an additive table/API field.
Decisions D1–D7 await approval. Finding recorded for a separate business
decision: no column feeds `estimated_monthly_sales`, so `DEMAND_UNKNOWN` makes
BUY unreachable for imported files. No code, schema or contract changed; GOLDEN
20/21 stay `REQUIRES_ADR`.

## 2026-10-26 — frontend-next: Favorites (one run) and readable ADR-047 evidence

**IMPLEMENTED in `frontend-next/`.** Favorites page for the selected run on the
existing record endpoint and browser-local stars; structured, read-only view of
stored ADR-047 documents on Product Detail with the original JSON kept. GOLDEN
item 7 PARTIALLY_RECOVERED (single run, no images); RECOVERED stays 11/24.
Details GOLDEN_PRODUCT_EXPERIENCE_PARITY.md §24. Tests: tsc clean; vitest 152
passed + 7 skipped (opt-in); live 7/7; real-payload render PASS; oxlint clean;
build OK. ADR-040 unchanged. `frontend/`, `demo/`, backend untouched.

## 2026-10-26 — frontend-next: Product Detail, Dashboard and per-file batch analytics

**IMPLEMENTED in `frontend-next/`.** HEAD before `f64d1cd`. Three units on
existing contracts, no backend logic change: Product Detail (Catalog links no
longer 404), Dashboard on `/analytics` with the 11 Golden KPIs, and Golden's
multi-source analytics table on Batch Detail. GOLDEN 9 → 11/24 (items 8, 18);
details GOLDEN_PRODUCT_EXPERIENCE_PARITY.md §23. Tests: tsc clean; vitest 130
passed + 6 skipped (opt-in live); live 6/6 on a disposable API; oxlint clean;
build OK. `frontend/`, `demo/` untouched. ADR-040 unchanged (no criterion
measures these screens).

## 2026-10-26 — Security, identity and Dependabot unblock plan

**PLAN (no activation).** HEAD `4bb5764`. `docs/compliance/UNBLOCK_PLAN_20261026.md`
separates confirmed local facts, historical claims and what cannot be verified
from the clone (current Railway exposure), lists decisions D0–D8, the Dependabot
export format/command and an ordered 11-step plan with proofs and the ADR-040
criteria each step could affect. Dependency re-check appended to
DEPENDENCY_THIRD_WAVE_RECONCILIATION.md: dev-only npm advisories in all four
lockfiles (runtime 0); Python runtime deps clean. ADR-040 unchanged.

## 2026-10-26 — frontend-next uses the BFF session cookie and CSRF contract (ADR-034)

**IMPLEMENTED in `frontend-next/` (client side only); auth activation still
PENDING.** Starting HEAD `928b91a`, clean. One shared client
(`src/api/client.ts::apiFetch`) now carries every request: `credentials:
"include"`, `X-JUVAL-CSRF` on POST (preview, batches) from
`GET /api/v1/auth/session`, memory only, one retry on a CSRF rejection; 401
raises a shell "Sign in" link (no auto-redirect), 403 distinguishes permission
from CSRF, network failures and 422 lists are reported distinctly. `batches.ts`
and `preview.ts` no longer call `fetch` directly. No backend, formula, decision
or dependency change; `frontend/` and `demo/` untouched.

Measured contract (disposable API, `JUVAL_AUTH_MODE=oidc`, seeded in-memory
sessions, no IdP): no cookie → 401; cookie without/with wrong CSRF → 403; with
CSRF → 200; viewer → 403 on preview/export, 200 on reads; preflight allows
`x-juval-csrf` with credentials for the listed origin only; preview creates no
run. In `disabled` mode `/auth/session` answers `authenticated: false` (not
404). Tests: tsc clean; vitest 96 passed + 3 skipped (opt-in live); live suite
3/3 (disabled mode); oxlint clean; build OK. Not verified: real FusionAuth
login, logout UI (not built), browser E2E. Visual-review guide (SSH tunnel,
loopback only): `frontend-next/README.md`.

## 2026-10-26 — frontend-next consumes brand, import preview and decision counts (GOLDEN 6, 10, 15-16)

**IMPLEMENTED in `frontend-next/` under a user-authorized, limited lift of the
frontend freeze (only these three contracts).** Starting HEAD `8709b2b`, clean.
`demo/` and `frontend/` unchanged; freeze otherwise retained. Runs and Run Detail
show stored BUY/REVIEW/PASS counts, with an explicit "not available" state for
`null`. Catalog has an exact Brand select fed by the run's analytics: not
stored, reset on run change, carried into the records query and the export.
Upload offers a per-file PREVIEW (server importer verdict: recognized, unknown,
duplicate and blank columns, missing required columns, rows read and
importable, issue counts and details) that creates no run. No formula, decision
rule, Decision Score, backend or dependency change. Details and limits:
GOLDEN_PRODUCT_EXPERIENCE_PARITY.md §22.

Tests: tsc clean; vitest 80 passed + 3 skipped (opt-in live); oxlint clean;
build OK; live suite 3/3 against a disposable local API. No browser E2E (no
Playwright for frontend-next). ADR-040 unchanged: `catalog` was already COMPLETE
by code presence and `pwa-gate` requires Fase 4 recertification.


## 2026-10-26 — Per-run decision counts on the Runs list (GOLDEN C6, item 6)

**IMPLEMENTED (backend projection); GOLDEN item 6 still `GOLDEN_UX_SUPERIOR`
until the Runs page renders it (frontend frozen, untouched).** Starting HEAD
`f0dc9b1`, clean. `RunSummaryOut` gains optional `decisions`, filled on
`GET /api/v1/runs` (one grouped query for the whole page via the new
`decision_counts` of both stores) and `GET /api/v1/runs/{id}`. Same grouping as
analytics `decisions` (shared helper `run_analytics.decision_counts_by_run`);
`null` = no stored snapshot, never zero counts. Counts what is stored; no
decision is recomputed. No schema, formula or frontend change; existing fields
unchanged. ADR-040 unchanged (44/68, 17/68).

Tests: 2 API (list and detail equal the posted records and the analytics; null
for a run without snapshots), 1 SQLite store (per run, UNKNOWN, absent, empty
input), 1 SQLite/PostgreSQL 16 parity on the disposable cluster.


## 2026-10-26 — Validate-only import preview: POST /api/v1/runs/preview (GOLDEN C4, items 15-16)

**IMPLEMENTED (backend contract); GOLDEN items 15-16 still missing in the UI
(frontend frozen, untouched).** Starting HEAD `b9651c9`, clean. The importer now
records how it resolved each header (`importer.py::classify_headers`,
`ImportResult.columns`, additive); `_resolve_headers` derives the column index
and the same issues from that record, so there is one header rule.
`application/import_preview.py::preview_import` runs the real `import_file` and
reports columns (MAPPED/UNKNOWN/DUPLICATE/BLANK, canonical, alias, target,
required, core vs native financial evidence), missing required columns (from the
importer's own issues), rows scanned/importable, issue counts and the first 100
issues. The endpoint has the upload rules of POST /runs, `runs:create` + CSRF,
and a temporary directory removed before responding. No processing, decision,
ExecutionRun, persistence, schema, formula, dependency or frontend change.
ADR-040 unchanged (44/68, 17/68).

Tests: `tests/integration/test_api_import_preview.py`, 14 (classification of
every header kind, same verdict as `import_file`, CSV = XLSX, fatal headers as
200, empty file, bounded issue list with complete counts, nothing stored and no
upload left behind, 422/413, filename sanitizing, 401/403/200). Existing
importer tests unchanged and passing. Full backend: **1740 passed, 129 skipped,
0 failed** with the disposable PostgreSQL 16 cluster.


## 2026-10-26 — Exact brand filter on run records and filtered export (GOLDEN C4, item 10)

**IMPLEMENTED (backend contract); GOLDEN item 10 still missing in the product
until the frontend consumes it (frontend frozen, untouched).** Starting HEAD
`6f4ecd7`, clean. `GET /api/v1/runs/{id}/records` and `/records/export` accept
`brand` (1-200 chars): exact, case-sensitive equality on the stored brand value,
the same value analytics reports as `brands.items[].label`, applied in SQL in
both stores and recorded in the export's `filters`. Records without a brand
never match; unknown brand = empty page. No status gating, no normalization, no
schema, formula, Decision Score or frontend change. ADR-040 unchanged (44/68,
17/68): `api` was already COMPLETE by code presence.

Tests: 6 new in `test_record_snapshot_pagination.py` (store exactness and
combination, analytics-label round trip in records and export, unknown brand,
422 bounds) and a SQLite/PostgreSQL 16 parity test on the disposable cluster.
Removing the SQLite clause fails 3 tests. Related suites: 318 passed, 26 skipped
(live Supabase / session DB not configured).


## 2026-10-16 — ADR-050 unit 2: POST /api/v1/batches persists atomically

**IMPLEMENTED; ADR-050 partially accepted (D1, D2, D3, D4 provisional, D6; D5
deferred).** Starting HEAD `9e9cb4d`, clean. The endpoint now processes every
file without writing, stores the batch with every child run, records, financial
documents and diagnostics through one `save_batch_with_runs` call, and exports
XLSX only after the commit. A write failure is still the generic 500 but leaves
no row (no unlinked child runs; a retry of the same request stores each file
once). A failed export keeps the committed batch, answers 200 and adds the D3
warning to that file in the POST response only. Success body, limits, statuses,
schema, formulas, Decision Score and frontend unchanged; no idempotency.
The former characterization tests now assert the approved contract.

Tests: 11 endpoint scenarios on SQLite and on disposable PostgreSQL 16, plus a
test that the endpoint calls `save_batch_with_runs` once and never the per-child
or separate batch saves; restoring per-child saving fails 5 tests.
Full backend: **1718 passed, 129 skipped, 0 failed** with the disposable cluster
(1666 passed, 181 skipped without it).


## 2026-10-16 — ADR-050 unit 1: atomic batch persistence (store level)

**IMPLEMENTED (unit 1); ADR-050 partially accepted; endpoint unchanged.** Starting
HEAD `08c9ba1`, clean. Approved: all-or-nothing persistence of a batch with its
child runs, records, financial documents, diagnostics and batch–run relation; no
compensating deletes; a REJECTED file does not invalidate the batch; ADR-025
kept. Implemented `application/batch_persistence.py::save_batch_with_runs`
(validates that batch files and child runs name the same executions, reuses the
extracted `financial_payloads`) and `save_batch_with_runs` in the SQLite and
PostgreSQL stores (one transaction over the extracted `_write_run` /
`_write_batch`, shared with `save_execution_run` / `save_batch`). No schema,
status, HTTP, idempotency, frontend or formula change; `POST /api/v1/batches`
does not call it yet.

Tests: 7 shared scenarios on SQLite and on disposable PostgreSQL 16, plus
validation and unchanged-writes tests (SQLite 9 passed; PostgreSQL suite 28
passed). Splitting the transaction per child fails 4 scenarios on each engine.
Full backend: **1701 passed, 129 skipped, 0 failed** with the disposable cluster
(1660 passed, 170 skipped without it). Compliance 8 PASS / 2 WARN / 0 FAIL.


## 2026-10-16 — ADR-050 proposed: batch persistence atomicity and idempotency

**PENDING DECISION.** Starting HEAD `8d53f37`, clean. ADR-025 leaves per-file
persistence/export failure isolation open. New characterization tests
(`tests/integration/test_api_batch_persistence_failures.py`, 6 passed) pin the
current behavior: a failing second child leaves the first stored but in no batch
and unknown to the client (generic 500); a retry stores that file twice; a global
database failure and an export failure are generic 500s. No orphan financial
documents and no cross-run mixing were observed. ADR-050 (Propuesta) recommends
process-then-save in one batch transaction, export after commit, 503/500 bodies
with `persisted`/`retry_safe`, and an optional `Idempotency-Key`. Nothing of it is
implemented; no contract, schema, migration or frontend change. ADR-050 is
numbered 050 because ADR-049 is used outside this repository.


## 2026-10-16 — ADR-047 financial opt-in on POST /api/v1/batches

**IMPLEMENTED; ADR-047 remains PARTIALLY IMPLEMENTED.** Starting HEAD `9b5ffb5`,
clean. `POST /api/v1/batches` accepts the approved single-file opt-in
(`native_financial_evidence`, `financial_target_*`; ADR-047 §22 step 7, which
listed batches as PENDING) with the same validation (`_check_financial_options`)
and the same write (`_persist_native_financial`): each child stores its own run,
snapshots, documents and diagnostics in one transaction keyed by its own
`execution_id` (ADR-025: one ExecutionRun per file, Batch as grouping). Without
the opt-in the response and records are unchanged (tested). No response field,
formula, migration, Decision Score, frontend or server change.

Not decided, so not implemented: per-file isolation of *persistence* failures
(ADR-025 leaves it open; a failing child write keeps today's generic `500`, the
child stores nothing, earlier children stay, no batch row) and a per-file
financial summary in the response (`BatchFileOut` is shared with the GET).

Tests: new `tests/integration/test_api_batch_financial.py` 11 passed (disabling
the financial write made 5 fail); one new disposable-PostgreSQL test, and the
whole `test_postgres_financial_persistence.py` 21 passed with
`JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin` (initdb in a temp dir, Unix
socket only; no real Supabase). The declared `postgres` extra (`psycopg`) was
installed into the clone's `.venv` for this; no new dependency.
Full backend: **1679 passed, 129 skipped, 0 failed** with the disposable cluster;
1645 passed, 163 skipped without it (with `psycopg` installed the PostgreSQL tests
skip one by one). Remaining skips: no live Supabase, no disposable session
database, no nginx binary. Compliance 8 PASS / 2 WARN / 0 FAIL, secret scan clean.


## 2026-10-16 — Recalculation check in the financial report CLI

**IMPLEMENTED; ADR-047 remains PARTIALLY IMPLEMENTED.** Starting HEAD `e321f42`,
clean. `python -m juval.interfaces.cli.financial_report` gains the opt-in
`--check-recalculation`, which adds one `recalculation:` line under each stored
document (MATCHES / DIFFERS / NOT CHECKED with reasons) by calling the existing
`check_recalculation`. Without the flag the output is unchanged (tested), the
documented "nothing is recalculated" default holds, and the exit codes are the
same with or without it. Shown values remain the stored ones. Only the CLI
interface layer changed; `application/financial_report.py`, the HTTP API,
formulas, persistence, frontend and servers did not. APPROVED scope: the
operator's 2026-10-16 authorization of an additive financial-report CLI output.

Tests: `tests/integration/test_financial_report_cli.py` 26 passed (7 new);
forcing the line to always read MATCHES made 4 of them fail. Full backend
`pytest -q`: **1634 passed, 126 skipped, 0 failed** (same skip causes as the
previous unit: no disposable PostgreSQL, nginx binary or `psycopg`).


## 2026-10-16 — ADR-047 §19: recalculation check of stored financial records

**IMPLEMENTED (one §19 unit); ADR-047 remains PARTIALLY IMPLEMENTED.** Starting
HEAD `a174825`, clean, isolated clone. Steps 8-9 were inspected and remain
BLOCKED: step 8 needs business approval of Decision Score D1/D2/D3 (ADR-045,
ADR-047 §23), step 9 a separate reviewed activation (§24). The independent unit
implemented is `application/financial_recalculation.py::check_recalculation`:
it re-runs the existing resolver and calculator on what a stored format-v2
document recorded and reports, part by part, whether the current code produces
the stored resolution and results; it refuses v1, missing calculations,
different tables or decimal policy, and mixed calculation instants. It is pure
and read-only, has no CLI/API/persistence consumer, and does not assert
historical reproduction (guarantee C). No formula, contract, migration,
dependency, frontend or server change. APPROVED scope: ADR-047 §19 (Aceptada)
and the operator's 2026-10-16 instruction.

Tests (new `.venv` in the clone with the declared `.[dev]` extra only):
baseline financial selection 315 passed; new unit file 17 passed; CLI v2 file
15 passed; full backend `pytest -q`: **1627 passed, 126 skipped, 0 failed**.
Skips: no disposable session PostgreSQL, no nginx binary, no `psycopg`; the
PostgreSQL financial persistence tests were therefore not run (persistence is
unchanged). Mutating the comparison or the calculation instant made 2 and 9 of
the new tests fail. ADR-040 metrics were not re-measured; the last recorded
values (44/68, 17/68, 0/12, 5/16, 0/18) are historical.


## 2026-09-21 — Risk severity equality policy

**IMPLEMENTED, APPROVED by explicit user decision (ADR-043).** Starting HEAD
`28a8fef0a72b02cd7ca5c68f77e59b0f9e3a3fa7`, clean. A PRESENT risk at the
configured maximum now triggers REVIEW / `RISK_AT_MAXIMUM`, unless an independent
PASS rule fires first. Below/above behavior, explicit custom rule replacement,
financial formulas and provenance remain unchanged. HazMat/Bulky supplier presence
stays VERIFIED and provisional severity INFERRED; REVIEW is not purchase approval.

Before implementation: 6 policy regressions reproduced the missing behavior;
2 additional failures were new INVALID fixtures missing required source_type
(corrected without product changes), 37 tests passed. After implementation:
**76 passed**, no skips, in decision/risk/provenance/pipeline unit tests and
`test_pipeline_end_to_end.py` / `test_reproducibility.py`. No unrelated backend,
frontend, export, callback, MFA or network suites repeated.

Only the Phase 5 risk-equality subcriterion is PASS. ADR-040 `scoring` remains
BLOCKED / NOT_VERIFIED: commercial subscore formulas and thresholds are still
unapproved. All metrics unchanged: implementation 44/68, verification 17/68,
production 0/12, security 5/16, Amazon 0/18. No whole criterion completed.
Frontend/MFA frozen; SP-API NOT_APPROVED; no infrastructure or identity change,
no dependency added, no push. Next gate requires business approval of scoring
formulas/thresholds; no further autonomous policy is inferred from this decision.


## 2026-09-21 — Finite supplier numbers and invalid shipping

**IMPLEMENTED.** After `a4e34b4`, a second bounded input-correctness defect was
confirmed: nonfinite Decimal text could abort an import or enter verified fields;
invalid/negative shipping silently became zero. The shared CSV/XLSX importer
now rejects nonfinite decimals through existing invalid-value paths and returns
no CostInputs for invalid shipping. Blank optional shipping keeps its documented
zero default. Weight INVALID retains raw text/source/row; unaffected rows proceed.
No Domain/Processing formula, business threshold, dependency or boundary change.
APPROVED scope: existing invalid-data/no-fabricated-cost rules and operator task.

New input regressions before fix: 32 failed / 2 passed. After fix:
**73 passed, 45 deselected**, one existing Starlette/httpx deprecation, using
`pytest -q tests/integration/test_csv_importer.py tests/integration/test_excel_importer.py tests/integration/test_api.py -k 'importer or nonfinite'`.
CSV/XLSX parity, row survival, weight provenance and API missing profitability
were exercised. Existing green export tests were not repeated. Scope is supplier
file ingestion, not all possible direct Python construction of domain objects.

Gates affected: input validation/provenance (Phase 2 and universal correctness /
security criteria); global production readiness remains blocked. ADR-040 unchanged
at 44/68 implementation, 17/68 verification, 0/12 production, 5/16 security,
0/18 Amazon: no whole roadmap criterion newly completed. No frozen-directory,
MFA, RF-02, infrastructure or external-provider work. No push.


## 2026-09-21 — XLSX literal text export correction

**IMPLEMENTED.** From baseline `8ed13cd73530d07a75555ddba2f8ee958d1def58`,
CSV supplier text beginning with `=` was reproducibly exported as an XLSX
formula by both normal download and filtered export; `#N/A` became an error
cell. Shared `append_literal_row` now emits strings explicitly as text without
changing their values, numeric cells, missing values or provenance. Filtered
query metadata uses the same writer. No dependency or architecture change;
APPROVED scope: existing data-as-data rule and operator-authorized technical
security corrections. This resolves a concrete export finding relevant to
PHASE_GATES universal item 5 / Phase 10, not the whole production gate.

Regression before fix: 4 failures / 3 passes (new literal-text cases). After
fix and correction of a new test's mistaken UNKNOWN expectation for absent risk
columns: **15 passed, 52 deselected**, 1 existing Starlette/httpx deprecation,
using `pytest -q tests/integration/test_excel_exporter.py tests/integration/test_api.py tests/integration/test_record_snapshot_pagination.py -k 'export or download'`.
No full backend/frontend/E2E rerun. No external spreadsheet client executed;
evidence is serialized XLSX round-trip with formula and data-only reads.

ADR-040 unchanged: implementation 44/68, verification 17/68, production 0/12,
security 5/16, Amazon 0/18. No new whole criterion completed; no portal mutation.
MFA/frontend frozen, SP-API NOT_APPROVED, identity/network/provider configuration
unchanged. No push. Session/public activation, business scoring, external sources
and AI provider work retain their human/external/decision gates.


Fotografía oficial del estado real del proyecto. Producida a partir de
`docs/RECONCILIATION_REPORT.md` (reconciliación código/tests/ADRs/docs,
2026-08-16) — ese documento contiene la evidencia línea por línea; este
documento es el resumen operativo que se mantiene actualizado con más
frecuencia.

**Regla de lectura de este documento**: "implemented" y "complete" **no
son sinónimos**. "Implemented" significa que el código existe y está
probado. "Complete" significa que, además, pasó formalmente el
Completion Gate de su fase (`docs/PHASE_GATES.md`) — criterios de
aceptación, documentación actualizada, sin conflictos arquitectónicos
abiertos, sin decisiones de negocio pendientes sin resolver. Un
componente puede estar `IMPLEMENTED` sin que su fase esté `COMPLETE`.

## Authorized real MFA preparation — 2026-09-18 (current)

**REAL_MFA_PREFLIGHT = PASS; experiment awaiting human identity creation/readback.**
Explicit operator authorization covers one new Marcus identity, two controlled real
cycles and mandatory human cleanup. Prior viewer-risk acceptance remains valid;
architecture unchanged. Current runtime prerequisites passed read-only checks.
[Evidence classifications, prepared runner and exact pending action](research/REAL_MFA_EXECUTION_20260918.md).

The real entry point is now explicitly wired to the same protocol boundary and
FlowPolicy; default synthetic mode still rejects real policies. Fixed provider/client/
callback, private pipe, human-only secrets, no token exchange or production auth.
Because shared wiring changed, the existing direct/302 regression ran once and
passed with 0 receiver bytes/sentinel. No real provider contact or MFA yet.
Latest identity baseline remains Marcus absent / tenant 0 (HUMAN_ADMIN_READBACK).
Await new identity ID/registration/count 1 before launching the dedicated viewer.
ADR-041/042 Proposed, Control 6 separate/PARTIAL, ADR-040 unchanged. This entry
supersedes the prior authorization-blocked status without changing its history.

## Callback protocol gate CLOSED — 2026-09-18 (current)

**IMPLEMENTED / INTEGRATION_VERIFIED in bounded synthetic scope.** Corrective
execution of the existing laboratory passed both actual direct and HTTP 302
navigation with active private-pipe interception and finite callback completion.
Receiver: direct 1 TCP / 0 bytes / 0 HTTP; 302 0 TCP / 0 bytes / 0 HTTP; no sentinel.
Corrections: explicit automation flag required for private command-line verification,
and destruction of pre-existing auxiliary targets before navigation. Runtime
unknown-target abort and the unchanged FlowPolicy remain enforced.
[Correction history, exact evidence and human checkpoint](research/HTTP_REDIRECT_CONTAINMENT_20260916.md).

CALLBACK_CONTAINMENT = SYNTHETICALLY_VERIFIED_AT_HTTP_OAUTH_MATERIAL_BOUNDARY.
Cleanup/listeners/Admin metadata verified; 9222 absent. No further callback test due.
REAL_MFA_PREFLIGHT remains BLOCKED_BY_HUMAN_AUTHORIZATION: future single disposable
identity/real experiment and its human cleanup scope need explicit authorization.
Marcus absent / JUVAl 0 and redirect Exact remain HUMAN_ADMIN_READBACK; prior viewer
risk acceptance is retained, not requested again. No provider state changed.
Real transport disabled; MFA not executed; ADR-041/042 Proposed, ADR-040 unchanged.
This supersedes the operational blockers below, preserving their historical evidence.

## Protocol-pipe callback adapter — 2026-09-18 (historical)

**PARTIALLY IMPLEMENTED; integration INCONCLUSIVE, callback gate NOT CLOSED.**
Operator approved private-pipe protocol interception delegating to FlowPolicy.
Adapter and targeted unit tests implemented. The single bounded browser run stopped
during adapter installation, before direct or 302 navigation; no OAuth-material
exposure observed, but no containment credit. Exact failing setup operation was
not captured. Cleanup/listeners/Admin metadata verified; 9222 absent during polling.
The existing harness now has finite setup-failure diagnostics, unit-tested only;
no second integration run. [Implementation, measured result and checkpoint](research/HTTP_REDIRECT_CONTAINMENT_20260916.md).

REAL_MFA_PREFLIGHT BLOCKED by incomplete integration. Next human action: authorize
one corrective execution of the same synthetic harness with those diagnostics.
No new architecture approval requested. No real provider/MFA/identity/configuration
change. Marcus absent and JUVAl 0 remain HUMAN_ADMIN_READBACK; prior viewer-risk
acceptance retained. ADR-041/042 Proposed, ADR-040 unchanged. Earlier sections below
are historical and do not describe this adapter as either verified or disproven.

## Callback HTTP/OAuth boundary — 2026-09-18

**BLOCKED by measured synthetic HTTP redirect bypass.** Operator approved an
HTTP/OAuth-material boundary; zero TCP is not required. One final bounded run:
direct callback 1 TCP / 0 bytes / finite callback reached; actual 302 callback
1 TCP / 753 bytes / 1 HTTP request / synthetic code marker received / 0 handler
invocations. Cleanup restored listeners and Admin metadata and removed owned
runtime resources. No real provider/MFA/user/configuration changes.
[Decision, measurements and next architectural checkpoint](research/HTTP_REDIRECT_CONTAINMENT_20260916.md).

REAL_MFA_PREFLIGHT remains BLOCKED by transport containment, not merely the old
three human gates. Marcus absent and tenant count 0 remain HUMAN_ADMIN_READBACK;
existing redirect/Exact match preserved. Prior viewer-risk acceptance is recorded;
a future new identity/cleanup scope requires authorization after technical closure.
ADR-041/042 Proposed; ADR-040 unchanged. This section supersedes the earlier
present-tense blockers and pre-network wording; historical results retain scope.

## Synthetic HTTP redirect containment review — 2026-09-16

BLOCKED. The new isolated reproducer stopped at its direct-navigation control:
1 callback route-handler invocation, 1 accepted TCP connection, 0 HTTP requests,
no code sentinel observed at the sink. No HTTP 302 was emitted; that branch was
not reached. This is SYNTHETIC_TEST evidence of a direct TCP connection, not a
code leak or behavioral verification of HTTP redirect containment. Failure cleanup
restored listeners/Admin process metadata and removed private runtime resources.
[Measurements, design options and unexecuted matrix](research/HTTP_REDIRECT_CONTAINMENT_20260916.md).

No fix selected or live transport enabled. Real MFA remains blocked, Marcus remains
deleted per prior HUMAN_ADMIN_READBACK; no IdP/configuration/frontend change.
ADR-041/042 Proposed, whole-tree sandbox PARTIAL, ADR-040 unchanged. Architectural
review is required before further containment experiments; no real MFA authorized.
This entry supersedes earlier operational next steps, preserving historical evidence.
Closeout: reproducer exit 1 / INCONCLUSIVE; focused regressions 47 PASS; broader
compliance tests 181 PASS / 86 SKIP (nginx unavailable). Offline compliance/scan
8 PASS / 1 historical-marker WARN / 0 FAIL, 516 files without pattern findings.
Diff-check and frontend/backend no-diff from 2714dbf pass. Six pending files;
HEAD unchanged, no commit/fetch/push. No dependency network audit.

## Synthetic real-flow technical closeout — 2026-09-16 UTC

Finite route/transition adapter and fulfilled-response callback interception passed the
synthetic gate (8 runtime cases, clean independent browser cycles, no callback
server, no real provider contact). [Evidence and resume checkpoint](research/REAL_MFA_TECHNICAL_SYNTHETIC_20260916.md).
REAL_MFA_PREFLIGHT remains BLOCKED by HUMAN_CLEANUP_COMMITMENT, FRESH_BASELINES,
and VIEWER_RISK_ACCEPTANCE. Real MFA not executed; transport disabled; Marcus and
Admin untouched. ADR-042 Proposed; Control 6 and ADR-040 metrics unchanged.

## Real MFA preflight — 2026-09-15

Documentation-only preflight completed; real execution **BLOCKED** pending fresh
human Admin baseline/cleanup commitment and a synthetically tested real-flow
adapter/callback boundary. No real MFA executed; Marcus untouched; Admin preserved.
[Plan and exact prerequisites](research/REAL_MFA_PREFLIGHT_20260915.md).
ADR-042 remains Proposed; Control 6/RF-03/readiness metrics unchanged.

## Private human viewer synthetic gate — 2026-09-15

Temporary authenticated :100 with loopback-only VNC/noVNC passed human visual
confirmation, synthetic interaction and cleanup. Admin preserved, frontend
unchanged. [Evidence and limitations](research/PRIVATE_VIEWER_LAB_20260915.md).
MFA remains unauthorized; ADR-042 remains Proposed; no ADR-040 metric credit.

## Restricted authentication evidence lab — 2026-09-15

JUVAl-owned finite evidence controller and authenticated temporary Xvfb :100
passed synthetic sentinel tests. This is synthetic verification only, not RF-03
completion or permission for MFA. Admin remained untouched; frontend frozen.
See [measured scope and limitations](research/RESTRICTED_AUTH_EVIDENCE_LAB_20260915.md)
and [ADR-042 (Proposed)](adr/ADR-042-restricted-auth-evidence-controller.md).
ADR-040 criteria/weights are unchanged; no readiness credit is asserted.

## Current Phase

**2026-09-10: Identity/Security production readiness — PARTIALLY IMPLEMENTED.**
Current evidence and operator queue: [IDENTITY_SECURITY_READINESS.md](IDENTITY_SECURITY_READINESS.md).
The phase closures below are historical and remain valid; they do not mean
identity is active or that Amazon remediation is complete.

**Fase 2 (SourcingRecord + Excel Vertical Slice): COMPLETE** (Completion
Gate evaluado formalmente 2026-08-16, todos los criterios obligatorios
en `PASS` — ver `docs/PHASE_GATES.md` §Fase 2 y ADR-012 para el cierre
del único ítem que quedaba en `FAIL`, `record_ref`).

**Fase 3 (Data Quality + ExecutionRun + Auditability): COMPLETE**
(Completion Gate evaluado formalmente 2026-08-16, todos los criterios
obligatorios en `PASS` — ver `docs/PHASE_GATES.md` §Fase 3). Persistencia
de `ExecutionRun` implementada vía SQLite local (ADR-013, `Estado:
Aceptada`, aprobada explícitamente por el usuario 2026-08-16).
`run_pipeline()` permanece puro/determinista por decisión arquitectónica
deliberada (Opción B, 2026-08-16) — no invoca el store automáticamente;
persistir es responsabilidad explícita del caller.

## Frontend Handoff Status

Frontend is implemented and frozen during identity/security recovery. No
accelerator changes in `frontend/`, `frontend-next/` or `demo/`. Historical
integration/parity evidence lives in `architecture/PRODUCT_BEHAVIORAL_PARITY.md`;
BFF integration and browser site topology still require their activation gates.

## Data Acquisition Policy Status

**DOCUMENTATION FREEZE (2026-08-17):**
[`DATA_ACQUISITION_MATRIX.md`](DATA_ACQUISITION_MATRIX.md) is the field-level
source of truth, and [`architecture/DATA_SOURCES.md`](architecture/DATA_SOURCES.md)
owns shared acquisition rules. No external enrichment adapter is implemented.
Amazon SP-API Catalog is **DOC VERIFIED / DEVELOPER REGISTRATION
REJECTED_REMEDIATION_REQUIRED / LIVE VALIDATION BLOCKED**: Amazon's
2026-08-17 decision is **NOT ELIGIBLE FOR SP-API ACCESS**. JUVAl remains a
**PRIVATE DEVELOPER** for internal use by its own organization and seller
account, but must remediate the documented findings, update the Developer
Profile truthfully and submit a **new** case (not reopen the prior one). No
production application client, self-authorization or credentials exist. Keepa
remains a **candidate, not approved**. Product Intelligence cannot proceed
until remediation, Amazon approval, the documented authorization gates,
matching-ambiguity and business decisions are reconciled.

## Completed Phases

| Phase | Status |
|---|---|
| Phase 0 — Foundation / Repository / Documentation | **COMPLETE** |
| Phase 1 — Domain + Processing Core | **COMPLETE** |
| Phase 2 — SourcingRecord + Excel Vertical Slice | **COMPLETE** |
| Phase 3 — Data Quality + ExecutionRun + Auditability | **COMPLETE** |

Ninguna fase posterior a la 3 está `COMPLETE` hoy. Fase 2 se declaró
completa el 2026-08-16 tras evaluar formalmente su Completion Gate
(`docs/PHASE_GATES.md` §Fase 2) y cerrar el único criterio en `FAIL`
(`record_ref` sin aprobación formal) mediante ADR-012. Fase 3 se declaró
completa la misma fecha tras implementar persistencia local de
`ExecutionRun` (SQLite, ADR-013 `Aceptada`), resolver
explícitamente que `run_pipeline()` no la integra automáticamente
(Opción B), y re-evaluar el Completion Gate completo — sin cambios de
código en esta última sesión, solo la aprobación formal y la
reconciliación documental correspondiente.

## Implementation Status

| Component | Current classification |
|---|---|
| Domain, processing, Excel/CSV, CLI, API | IMPLEMENTED_TESTED; business scoring/severity policy limitations remain |
| SQLite and Supabase run/record persistence | IMPLEMENTED; historical live verification in SUPABASE/PROJECT_STATUS session records |
| Frontend React/Vite | IMPLEMENTED, frozen; BFF integration pending |
| FusionAuth instance and exact tenant/application | RUNTIME_READ_ONLY_VERIFIED existence; names/roles not reverified |
| BFF and durable sessions | IMPLEMENTED_TESTED_NOT_ACTIVATED; live session migration pending |
| Public nginx | Template/lab only; N-1 fixed, asset compatibility and D-1 pending |
| AI/enrichment | NOT_IMPLEMENTED; authorized source/business decisions required |

## Completion Gate Status

Phases 0–3 remain historically COMPLETE. No new global phase closure is
claimed. Identity/security activation and Amazon reapplication remain BLOCKED;
see `PHASE_GATES.md` and the current readiness ledger. Technical implementation,
lab verification and production readiness are separate claims.

## Tests

Current measured results are recorded in the dated accelerator blocks below.
Backend, disposable PostgreSQL and real nginx suites have separate counts and
skip conditions. Historical counts are not the current baseline.

## Documentation

Documentación de arquitectura (`docs/architecture/*.md`) — 12 documentos,
todos verificados contra código en esta reconciliación:
`ARCHITECTURE.md`, `DATA_MODEL.md`, `DATA_DICTIONARY.md`,
`DATA_PROVENANCE.md`, `DATA_SOURCES.md`, `DECISION_ENGINE.md`,
`AI_ANALYST.md`, `EXCEL_PROCESSING.md`, `PROCESSING_PIPELINE.md`,
`EXECUTION_MODEL.md`, `TESTING_STRATEGY.md`, `SECURITY.md`,
`TECHNOLOGY_DECISIONS.md`.

Documentación de proceso (`docs/*.md`): `PROJECT_PLAN.md`,
`DEVELOPMENT_LOOP.md`, `PHASE_GATES.md`, `DEVELOPMENT_ENVIRONMENT.md`
(nota de entorno de desarrollo, no del producto),
`RECONCILIATION_REPORT.md`, este documento.

17 ADRs en `docs/adr/` (ADR-001 a ADR-017; solo ADR-009 en estado
Propuesta, el resto Aceptada — incluido ADR-014 (PWA), ADR-015
(fallback fail-closed de severidad), ADR-016 (FastAPI backend, Fase
4A) y ADR-017 (Supabase/PostgreSQL como persistencia de producción —
código preparado, no verificado contra una base real), las cuatro
últimas aprobadas 2026-08-17).

## Known Technical Debt

1. **`DecisionScoreResult` implementado pero no integrado en el
   pipeline.** El código y los tests existen (`processing/decision_score.py`,
   6 tests); `process_record`/`process_batch` no lo invocan. Razón: las
   fórmulas de cada subscore no están aprobadas por negocio
   (`docs/architecture/DECISION_ENGINE.md` §7). **Fase que debería
   resolverlo**: Fase 5 (Decision Intelligence) — no antes, porque
   requiere una decisión de negocio externa que no le corresponde
   inventar al agente.
2. **`ExecutionRun` no captura `thresholds` ni `sources_used`** —
   gap frente al diseño original (`ARCHITECTURE.md` §8). Ver
   `docs/architecture/EXECUTION_MODEL.md` §3.
3. ~~`record_ref` (`row_{n}[:supplier_sku]`) sin decisión arquitectónica
   `APPROVED`~~ — **RESUELTO 2026-08-16** por ADR-012 (`Estado:
   Aceptada`): la estrategia ya implementada queda formalmente
   documentada y aprobada, sin cambio de código. `ARCHITECTURE.md`
   §14.3 queda cerrada por esta decisión.
4. **Solo 2 de 14 `RiskType` tienen fuente de datos** (HAZMAT, BULKY,
   ambos desde Excel). Los 12 restantes quedan simplemente ausentes de
   `RiskProfile.flags` — no se fabrican como `UNKNOWN`, lo cual es
   correcto (no inventar datos), pero limita la cobertura real de riesgo
   hasta que existan fuentes para ellos.
5. **`DEFAULT_RISK_SEVERITY`** (HAZMAT→HIGH, BULKY→MEDIUM) está
   correctamente documentado (ADR-010) pero los valores en sí siguen sin
   aprobación de negocio. ~~Fallback silencioso `.get(risk_type,
   Severity.MEDIUM)` para cualquier `RiskType` no mapeado~~ —
   **RESUELTO 2026-08-17** vía ADR-015 (`Estado: Aceptada`): ahora
   produce `KeyError` (fail-closed) en vez de asumir `MEDIUM`. Esto no
   aprueba HAZMAT/BULKY en sí — sigue pendiente la aprobación de
   negocio de esos dos valores concretos.
6. ~~Persistencia de `ExecutionRun` entre corridas: no implementada~~ —
   **RESUELTO 2026-08-16** vía SQLite local
   (`infrastructure/logging/sqlite_execution_run_store.py`, ADR-013
   `Estado: Aceptada`, aprobada explícitamente por el usuario).
   `run_pipeline()` no invoca el store automáticamente por decisión
   arquitectónica deliberada (Opción B, también aprobada explícitamente)
   — persistir una corrida es una acción explícita del llamador, no una
   deuda pendiente. La política de invocación automática queda diferida
   a la primera interfaz operativa real (CLI/API, Fase 4).
7. ~~**CLI ausente**~~ — **RESUELTO 2026-08-17**: `interfaces/cli/main.py`
   implementado (`argparse`, stdlib, sin dependencia nueva), cerrando la
   recomendación de `ARCHITECTURE.md` §15/ADR-005. Ver
   §Sesión 2026-08-17 abajo para el detalle.
8. **`max_cog_target_profit`/`max_cog_target_roi` no se exportaban a
   Excel** — **RESUELTO 2026-08-17**: `exporter.py::HEADERS` ahora incluye
   ambas columnas (`<campo>`/`<campo>_status`), ya se calculaban en
   `profitability.py` desde antes, solo faltaba exponerlas.
9. **`validate_freshness()`/`validate_source()` no conectadas al
   pipeline** — **evaluado y diferido conscientemente, no resuelto**: hoy
   todo dato viene del Excel en el mismo instante de import (`now` es el
   único `retrieved_at` que existe), así que "freshness"/"placeholder
   source" no tienen ninguna variación real que detectar todavía — conectar
   estas validaciones ahora sería código sin capacidad de fallar un test
   con datos reales. Ambas funciones ya existen, están probadas
   individualmente (`test_data_quality.py`) y no se tocan (`CLAUDE.md`
   "no eliminar código sin consumidores actuales" — tampoco se fuerza su
   uso sin uno). Se activan de forma natural cuando exista una fuente con
   `retrieved_at` distinto del import (Fase 6, `BLOCKED`).
10. **`SourcingRecord.with_*()` sin uso en `src/`** — evaluado, sin
    acción: `pipeline.py::process_record` hace un único
    `dataclasses.replace(record, profitability=..., decision=...,
    issues=...)` en vez de encadenar tres `with_*()`; ambas formas son
    equivalentes en comportamiento y el código actual ya pasa 185 tests.
    Migrar sería puro churn estético sin corregir un defecto — no se
    hace (Ponytail: no refactorizar sin valor real). Los métodos
    `with_*()` se conservan (están probados en `test_sourcing_record.py`
    y documentados como la forma pública de mutar-vía-copia un
    `SourcingRecord`) para cuando un consumidor futuro (ej. un caso de
    uso que solo necesite cambiar un campo) los necesite.

## Sesión 2026-08-17 — CLI + cierre de deuda técnica menor

Continuación de trabajo tras el cierre de Fase 3 (2026-08-16). Fase 2 y
Fase 3 seguían `COMPLETE`; Fases 4-10 seguían `BLOCKED` por decisiones
`PENDING` que el agente no puede tomar (§Pending Decisions). En vez de
detenerse ahí, se identificó trabajo de categoría A (ejecutable sin
ninguna decisión de negocio/arquitectura pendiente) y se ejecutó:

1. **`interfaces/cli/main.py`** — CLI real, recomendado explícitamente
   por ADR-005 (`Estado: Aceptada`) y `ARCHITECTURE.md` §15 como la
   primera interfaz para validar el Core end-to-end, deliberadamente
   *antes* de decidir PWA vs. `.exe` (ADR-005 dice textualmente que
   permite "implementar primero la interfaz más simple... sin
   comprometerse a PWA o `.exe`"). No requirió ninguna decisión bloqueada:
   usa `argparse` (stdlib, cero dependencia nueva, evita la pregunta
   abierta `typer` vs. `argparse` de `ARCHITECTURE.md` §15), exige que el
   operador declare thresholds/fees por flag (nunca un default comercial
   inventado, ADR-007), y solo persiste el `ExecutionRun` si el operador
   pasa `--persist-db` explícitamente (continuación directa de Opción B/
   ADR-013, no una decisión nueva). 7 tests de integración
   (`tests/integration/test_cli.py`), probado también manualmente contra
   la fixture real. Esto resuelve la deuda técnica #7 (histórica) y dota
   al proyecto de su primer entrypoint real — antes, todo el valor de
   Juval solo era accesible escribiendo Python directamente (ver
   `README.md`).
2. **Excel export gap** — `max_cog_target_profit`/`max_cog_target_roi`
   ya se calculaban en `processing/profitability.py` (con
   `target_profit`/`target_roi` de `Thresholds`) pero nunca se exportaban;
   `exporter.py::HEADERS` ahora incluye ambas columnas con su
   `<campo>_status` correspondiente, siguiendo el mismo patrón que el
   resto de campos sensibles. 1 test nuevo
   (`test_excel_exporter.py::test_export_includes_max_cog_targets`).
3. **Docstring desactualizado en `domain/execution_run.py`** — seguía
   diciendo "in-memory/local only... no persistence layer", una
   afirmación que ADR-013 dejó obsoleta el 2026-08-16 pero que nadie
   había corregido en el propio código fuente (aunque sí en `docs/`).
   Corregido para apuntar al puerto/adapter reales
   (`ExecutionRunStore`/`SqliteExecutionRunStore`).
4. **`validate_freshness()`/`validate_source()` y `SourcingRecord.with_*()`**
   — evaluados y **diferidos conscientemente** con justificación explícita
   (ver Known Technical Debt #9/#10 arriba) en vez de forzarlos sin valor
   real o borrarlos sin necesidad.

Nada de esto tocó una decisión de `§Pending Decisions` — ninguna fue
aprobada, inventada ni asumida. Fase 2 y Fase 3 siguen `COMPLETE` sin
cambios en sus Completion Gates (`docs/PHASE_GATES.md`); este trabajo no
abre ni cierra ninguna fase nueva del `PROJECT_PLAN.md` (el CLI no tiene
un número de fase propio — ver nota en `PROJECT_PLAN.md` sobre esto).

## Sesión 2026-08-17 (bloque 2) — ADR-014: elección de PWA

Sesión puramente documental/arquitectónica, sin código. El usuario tomó
explícitamente la decisión que la sesión de planificación anterior
(§Sesión 2026-08-17 arriba) había dejado como la más urgente para
desbloquear Fase 4: **PWA como interfaz principal** ("PWA definitivamente").

Se creó `docs/adr/ADR-014-eleccion-pwa-interfaz-principal.md`
(`Estado: Aceptada`), y se actualizaron en el mismo cambio:
`docs/PROJECT_PLAN.md` (mapa de dependencias §3, tabla de decisiones
bloqueantes §4, sección Fase 4), este documento (§Implementation Status,
§Pending Decisions, §Next Recommended Action), `CLAUDE.md` §14,
`docs/architecture/ARCHITECTURE.md` (§10, §14, §16),
`docs/architecture/TECHNOLOGY_DECISIONS.md` (filas PWA/`.exe`/Vercel/
FastAPI), y `src/juval/interfaces/api/README.md` /
`src/juval/interfaces/desktop/README.md`.

**Lo que este ADR aprueba**: únicamente "PWA como interfaz principal".
**Lo que NO aprueba** (permanece explícitamente `PENDING`, ver ADR-014
§"Límites explícitos de esta decisión"): framework de backend concreto,
framework de frontend concreto, Vercel/hosting, Supabase, Clerk, Docker,
proveedor cloud. Fase 4 sigue `BLOCKED` — esta decisión resuelve
únicamente el bloqueo de *elección de interfaz*, no los demás bloqueos
de la fase (ver `PROJECT_PLAN.md` §Fase 4 actualizado).

`.exe` no se descarta como imposible para siempre (ADR-005 sigue
garantizando la independencia de diseño), pero no es el camino que se
construirá — no hay trabajo planeado en esa dirección.

Ningún código de `interfaces/api/` ni de ningún frontend se implementó
en esta sesión, por instrucción explícita. `interfaces/cli/main.py`
sigue siendo la única interfaz operativa real hoy.

## Sesión 2026-08-17 (bloque 3) — Fase 4A: backend FastAPI + preparación Supabase

El usuario aprobó FastAPI (backend), React+Vite (frontend, no
implementado esta sesión), Vercel, Git/GitHub, y Supabase en un mismo
prompt de alcance muy amplio. Antes de ejecutar, se verificó
disponibilidad de herramientas: `git` disponible (2.55.0); `node`,
`npm`, `supabase` CLI, y `vercel` CLI — **ninguno disponible**
(`[HECHO VERIFICADO]`, `--version` de cada uno falla). Se preguntó
explícitamente al usuario cómo priorizar dado ese bloqueo; eligió
completar primero el backend FastAPI + preparar (sin desplegar) el
adapter de Supabase.

**Implementado y probado** (209 tests, +21 sobre el baseline de 188):

1. `interfaces/api/{main,models,service}.py` — backend FastAPI
   (ADR-016), `POST /api/v1/runs` + `GET /api/v1/runs/{execution_id}/download`,
   cliente delgado sobre `application.run_pipeline`. 19 tests de
   integración (`test_api.py`) contra el Core real (fixture real, sin
   mocks en el camino principal), incluyendo persistencia opt-in de
   `ExecutionRun`, descarga real, provenance preservada en JSON
   (`value`+`status` juntos, ADR-003/ADR-004), y verificación explícita
   de que ningún traceback/ruta de servidor se expone nunca.
2. **Fix de un bug real de Windows, descubierto probando el flujo
   completo**: `infrastructure/excel/importer.py::import_excel` nunca
   cerraba el `Workbook` (`read_only=True` de `openpyxl` mantiene el
   archivo bloqueado). El CLI nunca lo notó porque nunca intenta borrar
   su archivo de entrada; la API sí (limpieza de temporales, §12 del
   brief), y el intento de borrar el archivo recién procesado fallaba
   con `PermissionError`. Corregido con un `try/finally: workbook.close()`
   — cambio mínimo, fuera de `domain/`/`processing/`/`run_pipeline()`
   (no restringido explícitamente), los 188 tests previos siguen en
   verde sin cambios.
3. `docs/architecture/API_CONTRACT.md` — contrato completo, derivado
   del código real, distingue explícitamente límite técnico (`JUVAL_MAX_UPLOAD_BYTES`,
   configurable, sin límite si no se define) de límite comercial
   (sigue `PENDING`, no inventado).
4. `SupabaseExecutionRunStore` (`infrastructure/persistence/`, ADR-017)
   + migración SQL versionada (`supabase/migrations/`) + `docs/architecture/SUPABASE.md`
   — **preparado, NO verificado contra un proyecto real** (sin CLI, sin
   credenciales, sin proyecto Supabase creado). 2 tests puramente
   estructurales, explícitamente distinguidos de los 12 tests de
   integración reales que sí tiene `SqliteExecutionRunStore` (ADR-013).
5. `.env.example` + `.gitignore` ampliado (`.env`, `node_modules/`) —
   ninguna credencial real en ningún archivo.

**No ejecutado esta sesión** (bloqueado por herramientas/credenciales
ausentes, reportado explícitamente, no inventado):
frontend React+Vite (sin Node/npm), `supabase init`/`db push` reales
(sin Supabase CLI ni proyecto), deployment a Vercel (sin Vercel CLI ni
cuenta), `git init`/push a GitHub (sin remoto ni credenciales — y no
solicitado en el alcance finalmente elegido por el usuario).

## Sesión 2026-08-17 (bloque 4) — Fase 4B: frontend React+Vite+PWA, git init, tooling

El usuario reafirmó explícitamente el alcance completo (PWA, FastAPI,
React+Vite, Vercel, Supabase, Git/GitHub) y autorizó instalar
herramientas si el entorno lo permite de forma segura.

**Herramientas instaladas esta sesión** (todas por canal oficial,
verificadas después de instalar):
- Node.js LTS v24.19.0 — via `winget install OpenJS.NodeJS.LTS` (fuente
  `winget`, hash verificado por winget).
- npm v11.17.0 — incluido con Node.
- Vercel CLI 59.1.3 — via `npm install -g vercel`.
- Supabase CLI 2.114.0 — **no instalable como binario persistente**
  (sin paquete winget/scoop disponible en este entorno); usable vía
  `npx supabase@latest <comando>`, que es el mecanismo que la propia
  documentación de Supabase soporta para Windows sin Scoop.
- `git` ya estaba disponible (2.55.0), sin cambios.

Nota práctica: `node`/`npm`/`vercel` solo resuelven directamente en
shells nuevos — los procesos de shell ya abiertos en la sesión anterior
no heredan el PATH actualizado por el instalador hasta reiniciarse (
comportamiento normal de Windows, no un defecto de la instalación).

**Implementado y verificado**:
1. `frontend/` — React 19 + TypeScript + Vite 8, scaffolded con
   `npm create vite@latest -- --template react-ts`. Sin router (una sola
   pantalla), sin librería de estado global, sin librería de UI — nada
   de eso tiene necesidad demostrada todavía.
2. PWA — `vite-plugin-pwa`, manifest (`name: "JUVAl"`, ícono placeholder
   propio en `public/icon.svg`), service worker autogenerado
   (`generateSW`). Sin offline processing, sin background sync, sin
   push notifications (explícitamente fuera de alcance de esta sesión).
3. `src/types.ts`/`src/api.ts`/`src/components/{RunForm,ResultsTable}.tsx`/`src/App.tsx`
   — cliente delgado puro sobre `docs/architecture/API_CONTRACT.md`, sin
   ningún cálculo de negocio (revisado línea por línea: no hay profit,
   ROI, severidad, decisión, ni thresholds calculados en TypeScript).
   Cada campo sensible se renderiza como `value` + `status` juntos,
   nunca colapsado (ADR-003/ADR-004) — verificado por test.
4. Ningún campo obligatorio del Core (`target_profit`, `target_roi`,
   `minimum_estimated_monthly_sales`, `maximum_risk_severity`,
   `referral_fee`, `referral_fee_rate`) tiene valor prellenado — el
   formulario fuerza input explícito, sin inventar defaults comerciales
   (ADR-007). Los dos campos de `FeeInputs` que sí tienen default en el
   propio dominio (`fulfillment_fee`/`other_selling_fees` = 0) reflejan
   ese mismo default, no uno nuevo.
5. **9 tests de frontend** (Vitest + Testing Library): formulario
   (renderiza, bloquea submit sin archivo, bloquea submit con
   parámetros vacíos sin inventar default, arma el payload exacto que
   el backend espera), tabla de resultados (nunca colapsa
   `FieldValue`, muestra `NOT_FOUND` explícitamente, muestra razones de
   decisión e issues), App (éxito muestra resultados + link de
   descarga real, error de API se muestra como estado, no como crash).
6. `npm run build` — **exitoso**, genera `dist/` + service worker.
7. **1 test E2E real** (Playwright, Chromium): arrancó el backend
   FastAPI real y el frontend real (`npm run dev`), subió el fixture
   real (`tests/fixtures/sample_sourcing_TEST_DATA.xlsx`), confirmó
   `PARTIAL_SUCCESS`, el ASIN real (`B0TESTAAA1`), provenance
   `[VERIFIED]` visible, y una descarga real de `.xlsx` — **no un
   mock**. Durante esta verificación se encontró y corrigió un bug real
   de configuración (CORS solo permitía `localhost:5173`, el dev server
   respondía en `127.0.0.1:5173` — orígenes distintos para el
   navegador); corregido documentando ambos orígenes en el ejemplo de
   `frontend/e2e/README.md`, sin tocar el mecanismo de CORS en sí
   (ya era correctamente configurable, `API_CONTRACT.md` §7).
8. `git init` — repositorio local inicializado, `146` archivos
   staged (`git add -A`), verificados sin secretos/credenciales/
   `node_modules`/`.venv`/archivos temporales (`git status --ignored`
   confirma que todo lo sensible está excluido). **Commit NO
   ejecutado**: `git commit` requiere `user.name`/`user.email`, que
   este agente tiene prohibido configurar (`Git Safety Protocol: NEVER
   update the git config`) — bloqueo real reportado, no una decisión
   silenciosa. Ver §"Qué falta" del reporte de esta sesión para el
   comando exacto.
9. `frontend/vercel.json` preparado (`buildCommand`, `outputDirectory:
   dist`, `framework: vite`) — sin desplegar (`vercel whoami` confirma
   sesión no iniciada, requiere `vercel login` interactivo).
10. Supabase: `npx supabase@latest projects list` confirma sesión no
    iniciada (`LegacyPlatformAuthRequiredError`) — requiere `supabase
    login` interactivo (OAuth de navegador). La migración
    (`supabase/migrations/20260817000000_execution_runs.sql`) sigue sin
    aplicarse a ningún proyecto real.

**Backend**: sin cambios de lógica — 209 tests siguen en verde.
Confirmado end-to-end real contra el frontend (no solo `TestClient`).

## Sesión 2026-08-17 (bloque 5) — cierre de infraestructura: Git/Supabase/Vercel

Re-verificación completa de INSPECT (no se asumió el estado del bloque
4). Sin cambios de código de negocio. Resultado idéntico al bloque 4 en
los tres bloqueos externos, más un hallazgo nuevo de investigación:

1. **Git**: `git status`/`git remote -v`/`git branch`/`git log` — sin
   commits, sin remoto, sin rama con historial. `git config user.name`/
   `user.email` — **ambos vacíos** (confirmado, no asumido). **STOP** en
   este punto exacto, tal como se instruyó — no se inventó identidad,
   no se ejecutó commit. 146 archivos siguen staged, re-verificados sin
   secretos (`git diff --cached --check` sin errores; scan de patrones
   de secretos sin resultados).
2. **Supabase**: `npx supabase@latest projects list` →
   `LegacyPlatformAuthRequiredError`. **STOP** — "Supabase requiere
   login interactivo del usuario", tal como se instruyó reportar
   literalmente. Nada más de Fase 3/4/5 del brief se ejecutó (dependían
   de esto).
3. **Vercel**: `vercel whoami` → `Logged out`. **STOP** — "Vercel
   requiere login interactivo del usuario". No se usó
   `vercel deploy --temporary` (publicaría el frontend en un dominio
   público de Vercel sin tu cuenta; no estaba instruido y decidí no
   improvisarlo sin tu confirmación explícita).
4. **`[HECHO VERIFICADO]` hallazgo nuevo — Vercel Functions no es
   compatible con el backend tal como está diseñado hoy**: investigado
   (no implementado, ver `docs/architecture/API_CONTRACT.md` §8.4).
   `/tmp` en Vercel Functions es efímero entre invocaciones (hasta
   500 MB) — el diseño actual de dos fases (`POST` escribe
   `output.xlsx`, `GET` posterior lo lee) no puede garantizar que ambas
   lleguen a la misma instancia. Además: límite de payload 4.5 MB,
   duración 10s(free)/60s(Pro). **Opciones presentadas, ninguna
   aplicada** (requieren tu aprobación, cambian la arquitectura o el
   contrato):
   - **Opción A** (recomendada, consistente con la sesión de diseño de
     Fase 4 previa): desplegar el backend en un host de proceso largo
     (Render/Railway/Fly.io/VPS), **no** en Vercel Functions. Frontend
     sigue en Vercel sin cambios. Cero cambio de código.
   - **Opción B**: rediseñar el contrato para que `POST /api/v1/runs`
     devuelva el Excel directamente en la misma respuesta (sin `GET`
     separado) — viable en Vercel Functions solo si el archivo entra en
     el límite de payload/duración; cambia `API_CONTRACT.md`.
   - **Opción C**: introducir un almacenamiento de objetos persistente
     (ej. Vercel Blob) para que ambas fases puedan leer el mismo
     archivo sin importar la instancia — introduce una dependencia/
     servicio nuevo, no aprobado todavía.
5. **Validación local re-confirmada** (no asumida): backend 209
   passed; frontend 9 passed; `npm run build` exitoso; **E2E
   re-ejecutado desde cero** (backend + frontend reiniciados) — 1
   passed, contra el stack real, sin mocks.
6. **Deployment real**: **NO ejecutado** — ninguno de los tres
   bloqueos (Git, Supabase, Vercel) se resolvió, y el hallazgo del
   punto 4 significa que, aunque Vercel tuviera sesión, el backend no
   debería desplegarse allí sin que tú elijas una de las opciones A/B/C
   primero.

## Sesión 2026-08-17 (bloque 6) — Deployment Architecture Gate: Opción A aprobada

El usuario aprobó explícitamente **Opción A** (§Sesión bloque 5): Vercel
solo para el frontend; backend en un servicio Python de proceso largo
(proveedor concreto todavía sin elegir); Supabase como persistencia de
producción. **Ningún cambio de código de negocio.**

Re-verificación completa de INSPECT (no asumida): `git config
user.name`/`user.email` siguen vacíos; `npx supabase@latest projects list`
sigue devolviendo `LegacyPlatformAuthRequiredError`; `vercel whoami`
sigue devolviendo `Logged out`. **Los tres bloqueos externos son
idénticos a los de la sesión anterior** — cero cambio de estado, porque
ninguno depende de nada que el agente pueda resolver por sí mismo.
`frontend/vercel.json` re-inspeccionado, correcto y sin cambios
(`buildCommand: npm run build`, `outputDirectory: dist`, `framework: vite`).
Validación local re-confirmada: 209 backend + 9 frontend + build
exitoso.

**PRIORIDAD 3 (selección SQLite/Supabase por entorno) deliberadamente
NO implementada esta sesión** — el propio brief la condiciona
explícitamente a "después de verificar Supabase real", precondición
que sigue sin cumplirse (Supabase sigue sin sesión). Implementarla
ahora habría sido ejecutar fuera de orden.

**PRIORIDAD 5 (proveedor de backend)**: sigue sin decidir un proveedor
concreto (Render/Railway/Fly.io/VPS u otro) — no se inventó ninguno,
se reporta como decisión pendiente del usuario.

## Sesión 2026-08-17 (bloque 7) — comparación de proveedores de backend

Los tres bloqueos externos (Git, Supabase, Vercel) se re-verificaron
de nuevo — **idénticos**, cero cambio de estado. Como el propio brief
de esta sesión indica "no repetir indefinidamente las mismas
validaciones... avanzar únicamente con trabajo que no dependa del
bloqueo", el trabajo real de esta sesión fue la comparación de
proveedores de backend pedida explícitamente, investigada con
información real (no memoria sin verificar) — ver fuentes citadas en
esta misma sesión de chat.

### Comparación Render vs. Railway vs. Fly.io vs. VPS

| Criterio | Render | Railway | Fly.io | VPS genérico |
|---|---|---|---|---|
| Soporte FastAPI | Nativo (Python detectado) | Nativo (Nixpacks detecta Python) | Vía Docker (requiere Dockerfile) | Total (tú controlas todo) |
| Proceso persistente | Sí | Sí | Sí (microVMs Firecracker) | Sí |
| Filesystem temporal | Ephemeral **entre deploys/restarts**; **estable entre requests dentro de la misma instancia corriendo** (no es el caso de Vercel Functions) — compatible con el diseño POST/GET actual sin Persistent Disk | Igual — proceso único de larga duración, filesystem estable mientras la instancia corre | Igual — VM de larga duración | Total control |
| Duración de requests | Sin límite agresivo documentado para Starter+ (no es serverless) | Sin límite agresivo (no es serverless) | Sin límite agresivo (no es serverless) | Sin límite (tú decides) |
| Memoria/CPU | Starter: recursos limitados; escala en tiers pagos hasta 32GB/8 CPU (Pro Ultra) | Escala por uso (vCPU/RAM medidos) | `shared-cpu-1x`/1GB por defecto, escalable | Tú eliges el tamaño |
| HTTPS | Automático | Automático | Automático | Manual (Let's Encrypt/certbot) |
| Variables de entorno | Dashboard, simple | Dashboard/CLI, simple | `fly secrets`, simple | Manual (`.env`, systemd) |
| Integración con Supabase | Trivial — solo connection string | Trivial | Trivial | Trivial |
| **Despliegue sin GitHub** (relevante ahora mismo — GitHub bloqueado) | **No** — el flujo estándar de Render requiere GitHub/GitLab/Bitbucket conectado; no hay `git push render` directo | **Sí** — `railway up` sube y despliega el directorio local directamente, sin Git en absoluto | **Sí** — `flyctl deploy` construye y despliega desde el Dockerfile/código local, sin Git | **Sí** — control total, sin dependencia de ningún proveedor de Git |
| Facilidad de operación | Alta (más simple, más opinionado) | Alta | Media (requiere Dockerfile, más control = más configuración) | Baja (todo manual: SO, systemd, proxy, TLS, updates de seguridad) |
| Coste (uso bajo, un operador) | Free tier real pero con cold-start de ~1 min tras 15 min inactivo; Starter pago $7/mes sin cold-start | Sin free tier real (crédito de prueba de $5, luego ~$1/mes de crédito); Hobby $5/mes | Sin free tier real (solo 2h de prueba); pago por segundo | Variable, desde ~$4-6/mes (proveedor genérico) |
| Escalabilidad | Vertical simple, tiers fijos | Vertical + medido por uso | Multi-región nativo (edge), la más flexible | Manual, tú decides |
| Logs | Nativos, dashboard | Nativos, dashboard/CLI | Nativos, `fly logs` | Manual (journald, etc.) |
| Health checks | Nativo (`healthCheckPath`) | Nativo (`healthcheckPath`) | Nativo, requiere endpoint propio | Manual |
| Compatibilidad con el contrato POST/GET actual | Sí, sin cambios | Sí, sin cambios | Sí, sin cambios | Sí, sin cambios |

`[HECHO VERIFICADO]`: ninguno de los cuatro requiere cambiar el
contrato de API ni convertir el backend a serverless — los cuatro son
procesos de larga duración, exactamente lo que la Opción A ya aprobada
requiere.

`[HECHO VERIFICADO]`, hallazgo más relevante dado el bloqueo actual de
GitHub: **Render está efectivamente bloqueado hoy** (su flujo estándar
de deploy depende de un repositorio Git conectado, que no existe
todavía); **Railway y Fly.io sí son desplegables ahora mismo** sin
GitHub, vía sus respectivos CLIs (`railway up` / `flyctl deploy`)
subiendo el código local directamente.

`[RECOMENDACIÓN]`, no aplicada, esperando tu aprobación: **Railway**
— es desplegable ya mismo pese al bloqueo de GitHub, no requiere
Dockerfile (detecta Python automáticamente vía Nixpacks, aunque
`interfaces/api/` ya podría llevar uno si se prefiere control
explícito), y tiene la curva de configuración más baja de los tres
proveedores gestionados. Fly.io es la alternativa más fuerte si más
adelante importa control multi-región; Render sigue siendo válido
cuando GitHub vuelva a estar disponible; un VPS se descarta para un
MVP de un solo operador por la carga operativa que añade sin necesidad
demostrada (Ponytail).

**No se implementó nada de esto** — es una comparación, a la espera de
tu aprobación explícita antes de tocar cualquier configuración de
despliegue.

Sources:
- [Render vs Railway vs Fly.io: 2026 Pricing Showdown](https://expresstech.io/render-vs-railway-vs-fly-io-2026-pricing-showdown/)
- [Persistent Disks – Render Docs](https://render.com/docs/disks)
- [Web Services – Render Docs](https://render.com/docs/web-services)
- [Deploy without GitHub/GitLab | Feature Requests | Render](https://feedback.render.com/features/p/deploy-without-githubgitlab)
- [Deploying with the CLI | Railway Docs](https://docs.railway.com/cli/deploying)
- [railway up | Railway Docs](https://docs.railway.com/cli/up)
- [Deploy a FastAPI App | Railway Guides](https://docs.railway.com/guides/fastapi)
- [Run a FastAPI app · Fly Docs](https://fly.io/docs/python/frameworks/fastapi/)

## Sesión 2026-08-17 (bloque 8) — Railway aprobado: preparación (sin deploy)

El usuario aprobó explícitamente **Railway** como proveedor del backend
(ADR-018, `Estado: Aceptada`). Re-verificación de INSPECT: Git
(identidad vacía), Supabase (sin sesión) — **idénticos** a sesiones
anteriores. Railway CLI instalada (`npm install -g @railway/cli`,
5.41.2) — `railway whoami` → `Unauthorized` (sin sesión, esperado, no
se intentó login).

**Preparado, sin desplegar**:
1. `railway.toml` (raíz del repo) — `buildCommand: pip install .[postgres]`,
   `startCommand: uvicorn juval.interfaces.api.main:app --host 0.0.0.0 --port $PORT`.
   Sin `healthcheckPath` (Railway usa TCP check por defecto; un
   `GET /health` dedicado queda como `[RECOMENDACIÓN]` explícita, no
   implementada — habría sido tocar `interfaces/api/main.py` sin que el
   usuario lo pidiera).
2. **Hallazgo verificado, no asumido**: `pip install -e .` (probado
   localmente) hace que `import juval` funcione **sin** la variable
   `PYTHONPATH=src` que usan los tests — confirmado arrancando
   `uvicorn juval.interfaces.api.main:app` sin esa variable y
   confirmando `GET /openapi.json` → 200. Esto es más correcto para
   producción que replicar la convención de `pytest`.
3. `.env.example` (raíz) ampliado con nota sobre `JUVAL_CORS_ORIGINS`
   (deberá apuntar a la URL real de Vercel, todavía inexistente — no
   inventada) y `PORT` (gestionado por Railway, no configurar
   manualmente).
4. `ADR-018-railway-backend-hosting.md` creado — documenta la elección,
   la configuración, y explícitamente qué NO resuelve (deploy real,
   `/health`, CORS con URL real, integración con Supabase en `main.py`).

**No ejecutado, ni parcialmente**: `railway login`, `railway link`,
`railway up`, ni ningún deploy real. Comando exacto que el usuario
deberá ejecutar cuando quiera desplegar:
```bash
railway login          # abre el navegador
railway link            # o `railway init` si el proyecto Railway no existe todavía
railway up
```
Después del primer deploy, configurar en el dashboard/CLI de Railway
la variable `JUVAL_CORS_ORIGINS` con la URL real del frontend en
Vercel (todavía no existe).

**Validaciones re-confirmadas** (no asumidas): backend 209 passed;
frontend 9 passed; `npm run build` exitoso. Ningún test nuevo — no se
tocó código de aplicación, solo configuración de deployment +
`pyproject.toml` sin cambios (la instalación editable no modificó
ningún archivo versionado, `src/juval.egg-info/` generado ya estaba
cubierto por `.gitignore::*.egg-info/`).

## Sesión 2026-08-17 (bloque 9) — verificación sin cambios

Los cuatro bloqueos externos (Git, Supabase, Vercel, Railway) se
re-verificaron con los comandos reales al inicio de la sesión —
**idénticos a la sesión anterior, sexta vez consecutiva sin cambio**:
`git config user.name`/`user.email` vacíos; `npx supabase@latest projects list`
→ `LegacyPlatformAuthRequiredError`; `vercel whoami` → `Logged out`;
`railway whoami` → `Unauthorized`. Validación local re-confirmada: 209
backend + 9 frontend + build, sin cambios.

Como los cuatro bloqueos son idénticos y **cada** prioridad 2-7 del
brief de esta sesión depende explícitamente de al menos uno de ellos,
no existe trabajo de infraestructura independiente que ejecutar esta
vez (a diferencia del bloque 7, donde la comparación de proveedores sí
era independiente de los bloqueos). No se fabricó ninguna tarea
sustituta — en particular, `GET /health` seguía explícitamente
prohibida esta sesión salvo aprobación, y no se tocó. Sesión de
verificación, no de ejecución.

## Sesión 2026-08-17 (bloque 10) — Supabase e2e + Git/GitHub baseline resueltos; Railway sigue bloqueado

De los cuatro bloqueos externos re-verificados sin cambio en los
bloques 5-9, **dos quedaron resueltos** en sesiones posteriores (no
detalladas bloque a bloque aquí, ver commits/ADRs para el detalle
exacto):

- **Supabase**: el usuario ejecutó `supabase login` fuera de la sesión
  del agente. Proyecto real identificado sin ambigüedad
  (`juvalservicesllc-cloud's Project`, ref `twrgzsbpazcjhhfolaju`),
  repositorio vinculado, migración `20260817000000_execution_runs.sql`
  aplicada y verificada contra el esquema remoto real (columnas, PK,
  índices, RLS habilitado, 0 policies desplegadas — fail-closed
  esperado). `SupabaseExecutionRunStore` probado con una prueba de
  integración real (INSERT + SELECT + cleanup,
  `tests/integration/test_supabase_execution_run_store.py`) — requirió
  el **Connection Pooler** de Supabase, no el host directo (que resuelve
  solo IPv6, sin ruta IPv6 en este entorno). Selector
  `JUVAL_EXECUTION_STORE` (`sqlite`|`supabase`) implementado en
  `main.py::_execution_run_store`, fail-fast, sin fallback implícito
  entre modos — ver `docs/architecture/SUPABASE.md` y
  `docs/architecture/API_CONTRACT.md` §5. ADR-017 actualizado, sin ADR
  nuevo.
- **Git/GitHub**: identidad Git configurada por el usuario. Primer
  commit del repositorio creado (`ee412f4 — chore: establish Juval
  project baseline`, 157 archivos, incluye backend/docs/frontend hasta
  ese punto). `origin` configurado a
  `https://github.com/juvalservicesllc-cloud/JUVAl.git` y publicado
  (`master` → `origin/master`), verificado con `git ls-remote`.

**Railway sigue bloqueado, re-verificado en esta sesión**: `railway
--version` → `5.41.2` (CLI instalada globalmente, sin cambios),
`railway whoami` → `Unauthorized` (idéntico a bloques 5-9). `railway.toml`
ya estaba correctamente preparado (`buildCommand: pip install
.[postgres]`, `startCommand` con `$PORT`/`0.0.0.0`, entrypoint real
`juval.interfaces.api.main:app`) — no requirió ningún cambio esta
sesión. `main.py` ya soporta seleccionar `SupabaseExecutionRunStore`
vía `JUVAL_EXECUTION_STORE=supabase` (bloque anterior), así que el
único paso pendiente para desplegar es que el usuario ejecute `railway
login` (interactivo, no completable por el agente) y, tras eso, vincule
o cree el proyecto/servicio Railway.

## Sesión 2026-08-17 (bloque 11) — ADR-019: persistencia run-scoped de records + GET /api/v1/runs[/records]

Cerrada la brecha `MISSING ARCHITECTURAL CAPABILITY` documentada en el
bloque anterior. Aprobado por el usuario explícitamente: persistencia
detallada run-scoped (nunca `/products` global), `GET /api/v1/runs`
(reabre parcialmente ADR-013 porque ya existe un caller real).

**Implementado, verificado esta sesión**:
- ADR-019 (`docs/adr/ADR-019-persistencia-records-run-scoped.md`,
  siguiente número libre real tras inspeccionar `docs/adr/`).
- `application/record_snapshot.py::record_to_snapshot` — única función
  de mapeo `SourcingRecord -> JSON`, compartida por
  `interfaces/api/service.py::record_to_json` (refactorizado, sin
  duplicar lógica) y los adapters de persistencia.
- `application/execution_run_store.py::ExecutionRunStore` extendido:
  `save_execution_run(run, records=())` (atómico, misma transacción) y
  `list_execution_runs(limit=20)`.
- `application/record_snapshot_store.py::RecordSnapshotStore` — port
  nuevo, pequeño, un solo método (`load_records`), responsabilidad de
  lectura separada de la escritura atómica.
- `SqliteExecutionRunStore` y `SupabaseExecutionRunStore` implementan
  ambos ports ampliados. Nueva tabla `execution_run_records` en ambos
  backends — SQLite vía `CREATE TABLE IF NOT EXISTS` (mismo patrón que
  ADR-013), Supabase vía
  `supabase/migrations/20260817000001_execution_run_records.sql`,
  **aplicada y verificada contra el proyecto real** (`db push` +
  `information_schema.columns` + `pg_tables.rowsecurity` +
  `pg_policies`, mismo mecanismo ya usado en el bloque 5-10).
- `GET /api/v1/runs` y `GET /api/v1/runs/{execution_id}/records`
  implementados en `interfaces/api/main.py` — ver
  `docs/architecture/API_CONTRACT.md` §2b/§2c para el contrato
  completo.
- Tests nuevos: 14 de integración SQLite
  (`tests/integration/test_execution_run_records_store.py` — round-trip,
  orden estable, `record_ref` repetido entre runs sin colisión,
  provenance VERIFIED/INFERRED/NOT_FOUND, atomicidad ante fallo), 10 de
  API (`tests/integration/test_api.py`), 2 estructurales Supabase
  ampliados, y las 3 pruebas de integración real de Supabase
  (`tests/integration/test_supabase_execution_run_store.py`, gated,
  ejecutadas esta sesión con `JUVAL_SUPABASE_DB_URL`: `3 passed`).
  Suite completa: `242 passed, 3 skipped` sin credencial cargada (los 3
  tests reales de Supabase), `0 failed`.

**No implementado, fuera de alcance explícito de esta sesión**: cablear
Railway (sigue `EXTERNAL_BLOCKER`); ningún cambio en `frontend/`
(Codex adapta `ProductsPage`/`RunsPage`/API client después); ninguna
policy RLS nueva (misma postura fail-closed que `execution_runs`); sin
paginación por cursor (limit acotado documentado como suficiente para
el MVP, riesgo de escalabilidad explícito en ADR-019).

## Pending Decisions

Todas `PENDING`, ninguna se resuelve en este documento (ver
`docs/architecture/TECHNOLOGY_DECISIONS.md` para el detalle completo):

- ADR-009 (Development Loop + Completion Gates) — `Estado: Propuesta`,
  no confirmada por el usuario.
- ~~PWA vs. `.exe`~~ — **RESUELTO 2026-08-17**: el usuario eligió
  explícitamente PWA (ADR-014, `Estado: Aceptada`). ADR-005 sigue vigente
  para la independencia de diseño (no modificado). Se conserva aquí como
  registro histórico — ya no es un ítem `PENDING`.
- ~~Framework de backend para `interfaces/api/`~~ — **RESUELTO
  2026-08-17**: FastAPI (ADR-016, `Estado: Aceptada`), implementado y
  probado (19 tests).
- ~~Framework frontend (React + Vite)~~ — **RESUELTO/IMPLEMENTED
  2026-08-17 (bloque 4)**: `frontend/` (React 19 + TypeScript + Vite 8 +
  PWA), 9 tests + 1 E2E real contra el backend, `npm run build`
  exitoso. Sin ADR propio todavía (no se creó uno nuevo esta sesión —
  el usuario ya había elegido el framework explícitamente, no había una
  decisión de "cuál" que documentar).
- Vercel (deployment, **solo frontend**) — aprobado como plataforma
  objetivo; CLI instalada (59.1.3) y `frontend/vercel.json` preparado,
  **sin desplegar**: `vercel whoami` confirma sesión no iniciada
  (`vercel login` requiere interacción del usuario, OAuth de
  navegador).
- ~~Proveedor de hosting del backend~~ — **RESUELTO 2026-08-17 (bloque
  8)**: Railway (ADR-018, `Estado: Aceptada`), tras comparación
  explícita con Render/Fly.io/VPS (bloque 7). `railway.toml` preparado,
  **sin desplegar**: `railway whoami` confirma sesión no iniciada
  (`railway login` requiere interacción del usuario). Vercel Functions
  descartado explícitamente para el backend por incompatibilidad real
  verificada (`API_CONTRACT.md` §8.4).
- Supabase — aprobado como persistencia de producción (ADR-017,
  `Estado: Aceptada`), CLI utilizable vía `npx supabase@latest`, **sin
  verificar contra un proyecto real**: `supabase projects list` confirma
  sesión no iniciada (`supabase login` requiere interacción del
  usuario, OAuth de navegador). No confundir "decisión aprobada" con
  "implementación verificada" (ver `docs/architecture/SUPABASE.md` §1).
- Clerk — autenticación, sin aprobación.
- Fuente(s) externa(s) de enriquecimiento (Amazon SP-API, datos de
  mercado tipo Keepa) — ninguna aprobada.
- Proveedor/modelo de IA para el AI Analyst — no evaluado.
- Fórmulas de subscore del Decision Score y thresholds comerciales
  reales — no aprobados.
- Aprobación de negocio de `DEFAULT_RISK_SEVERITY` (los valores, no la
  documentación — ver Technical Debt #5).
- ~~ADR-013 (Persistencia de `ExecutionRun` vía SQLite) — `Estado:
  Propuesta`~~ — **RESUELTO 2026-08-16**: aprobada explícitamente por el
  usuario, `Estado: Aceptada`. Se conserva aquí como registro histórico.
- ~~Si `run_pipeline()` debe invocar `SqliteExecutionRunStore`
  automáticamente~~ — **RESUELTO 2026-08-16 (Opción B)**: NO.
  `run_pipeline()` permanece puro/determinista por diseño; persistir
  sigue siendo una acción explícita del llamador. En su momento (sesión
  2026-08-16) esta nota decía "no requirió un ADR nuevo" sin asignarle
  número — **corrección 2026-08-17**: esa referencia numérica ya no se
  usa aquí porque ADR-014 fue asignado después a una decisión distinta
  (elección de PWA, ver arriba); esta decisión de Opción B nunca tuvo
  ni necesitó ADR propio, confirmado explícitamente por el usuario en su
  momento. Ya no es un ítem `PENDING` — se conserva como registro
  histórico.

## Architecture Risks

- **Confiar en `CLAUDE.md`/documentación de proceso sin verificar contra
  código** es el riesgo que esta misma tarea existió para mitigar — ya
  ocurrió una vez en este repositorio (ver
  `docs/RECONCILIATION_REPORT.md` §8, hallazgo #1/#2). Mitigación:
  `docs/DEVELOPMENT_LOOP.md` Step 1 (Inspect) exige verificar código
  directamente, no solo documentación — pero ese mismo proceso (ADR-009)
  sigue sin aceptación formal.
- **Declarar una fase `COMPLETE` sin ejecutar su Completion Gate** —
  el riesgo que motivó ADR-009. Fase 2 y Fase 3 se declararon `COMPLETE`
  en este documento solo después de evaluar formalmente su Completion
  Gate criterio por criterio (`docs/PHASE_GATES.md` §Fase 2/§Fase 3,
  ambas 2026-08-16) — el riesgo permanece vigente para cualquier fase
  futura que se declare completa sin ese mismo proceso explícito.
- **Persistencia ahora existe (SQLite, ADR-013) pero no es automática,
  por decisión arquitectónica deliberada (Opción B, 2026-08-16)** — un
  `ExecutionRun` puede sobrevivir al fin del proceso que lo generó solo
  si el llamador invoca `store.save_execution_run(run)` explícitamente;
  `run_pipeline()` no lo hace por sí mismo, y no lo hará hasta que una
  interfaz operativa real (Fase 4) defina su propia política. La
  promesa de "auditabilidad" del nombre de Fase 3 sigue siendo parcial
  mientras no exista esa interfaz — esto ya no es una decisión abierta,
  es una consecuencia aceptada de la decisión ya tomada.
- ~~Ninguna interfaz de usuario existe~~ — **parcialmente mitigado
  2026-08-17**: `interfaces/cli/main.py` es un entrypoint real (línea de
  comandos), pero sigue sin ser una interfaz gráfica utilizable por un
  usuario no técnico — requiere conocer flags y ejecutar Python desde una
  terminal. Cualquier demostración a un usuario no técnico real sigue
  requiriendo Fase 4 (bloqueada).

## Next Recommended Action

Follow the prioritized queue in `IDENTITY_SECURITY_READINESS.md`. Autonomous
safe work proceeds under the operator's accelerator authorization; Admin
credentials, DNS/topology, live migration, business policy and Amazon submission
remain human boundaries. Do not restart obsolete provider-selection work.

## Relacionado

`docs/RECONCILIATION_REPORT.md` (evidencia completa de esta fotografía),
`docs/PROJECT_PLAN.md` (plan de fases completo), `docs/PHASE_GATES.md`
(checklist de cierre normativa), `docs/DEVELOPMENT_LOOP.md` (proceso,
ADR-009 `Propuesta`), `docs/architecture/TECHNOLOGY_DECISIONS.md`
(matriz de tecnologías).


---

## Sesión 2026-09-09 — cierre de la arquitectura de identidad (ADR-034/035/036)

Fase de investigación, laboratorio aislado e implementación. **Producción no
fue mutada**: `fusionauth-app` mantuvo `MainPID=369334`, `NRestarts=0` y su
`ActiveEnterTimestamp` original de principio a fin; `JUVAL_AUTH_MODE` sigue sin
definir; `frontend/`, `frontend-next/` y `demo/` sin tocar.

### Correcciones a afirmaciones previas de este documento y de CLAUDE.md

Se corrigen, **sin reescribir el histórico** — las afirmaciones antiguas eran
ciertas cuando se escribieron o eran errores honestos, y se anotan como
superadas en lugar de borrarse:

| Afirmación previa | Estado real medido |
|---|---|
| El runtime `navegador → OIDC → PKCE → JWT → JWKS → FastAPI → RBAC` existía | **Falso.** Sólo existían los tres últimos eslabones. `frontend/` no contenía cliente OIDC alguno y la superficie pública devolvía 404 en `/oauth2/authorize`. Corregido por ADR-034 en el backend; el frontend sigue congelado |
| Los dos listeners (`:9011`/`:9012`) eran una anomalía sin explicar de `juval-server` | **Explicado.** Es comportamiento de fábrica de FusionAuth 1.69.0, reproducido en una instancia limpia de laboratorio |
| El portal self-service de FusionAuth es una función de pago (Starter) | **Retirado.** `GET /account/?client_id=…` responde **200 en Community sin licencia**. Fue una lectura de la página de precios contradicha por medición |
| Onboarding posible como «crear usuario → primer login → enrolar MFA» | **Rechazado.** Con `loginPolicy=Required` el usuario sin método recibe `242` con `methods: []` y no puede ni completar el reto ni enrolar (`421`). Ver `docs/compliance/IDENTITY_ONBOARDING.md` |
| Control 6 dependía de base documental | **Base conductual.** Medido en laboratorio: nombres aceptados, control positivo (`containsEmail`/`containsUsername`) disparando |
| ADR-022 como referencia viva en `auth.py`/`pyproject.toml` | Stale — ADR-022 está `RECHAZADA`. Sustituido por ADR-028/ADR-031 |
| «RBAC en los 5 endpoints» | Son **10+** |

### Qué se implementó

| Área | Archivo | Estado |
|---|---|---|
| BFF OIDC | `src/juval/interfaces/api/bff.py` | IMPLEMENTED + 28 tests, **no activado** |
| Puertos de sesión | `src/juval/application/session_store.py` | IMPLEMENTED |
| Adaptador en memoria | `src/juval/infrastructure/sessions/in_memory_session_store.py` | IMPLEMENTED (un solo proceso; ADR-036 decide el duradero) |
| Control 6 | `src/juval/domain/password_policy.py` | IMPLEMENTED + 20 tests |
| Puerta de mutación de contraseña | `src/juval/application/password_provisioning.py` | IMPLEMENTED (puerto sin adaptador, a propósito) |
| Endurecimiento | `src/juval/interfaces/api/auth.py` | leeway de reloj, caché JWKS explícita, `WWW-Authenticate`, resolver de sesión + 11 tests |
| Superficie pública | `deploy/fusionauth/nginx-fusionauth-public.conf` | Plantilla ampliada; **no recargada en producción** (el recuento exacto se corrige abajo, en la sesión 2026-09-10) |

Tests: **544 pasando, 7 skipped** — *cifra no reproducible; corregida en la
sesión siguiente*.

### Qué sigue bloqueado

`JUVAL_AUTH_MODE` no se activa hasta que: ADR-036 esté decidido, la superficie
pública esté medida y desplegada, y el frontend integre el contrato del BFF.
`RF-03`/`RF-04` siguen `NOT_VERIFIED`; la reaplicación a Amazon sigue
`BLOCKED`.

*(Nota añadida 2026-09-10: ADR-036 se aceptó a las 16:18 de ese mismo día, 26
minutos después de escribirse esta sección, que por eso lo daba por pendiente.)*


---

## Sesión 2026-09-10 — recuperación y consolidación del trabajo de identidad

La sesión del 2026-09-09 terminó por agotamiento de tokens con ~5.500 líneas sin
commitear. Esta sesión hizo primero una **auditoría forense** de ese árbol de
trabajo y después una **consolidación**. No se activó nada: `JUVAL_AUTH_MODE`
sigue sin definir, la migración sin aplicar, nginx sin recargar, FusionAuth sin
mutar (`MainPID=369334`, `NRestarts=0`, `ActiveEnterTimestamp` de 2026-09-07
idénticos al principio y al final), y `frontend/`, `frontend-next/` y `demo/`
sin tocar.

### Defecto corregido: el almacén de sesiones no llegaba a sus consumidores

`principal_from_session()` y `csrf_guard()` leían un global de módulo que
`build_stores()` podía no haber poblado nunca. Un worker que no hubiera servido
`/login` respondía a una cookie desde el adaptador en memoria de
pre-inicialización aunque la selección configurada fuera PostgreSQL: **fail
closed (401), pero la sesión duradera multi-instancia — la razón de ser de
ADR-036 — no estaba en uso.**

Corregido con un **único punto de inicialización** (`bff.ensure_configured()`)
al que llegan login, callback, resolución de sesión, refresh, CSRF y logout a
través de `session_store()` / `transaction_store()`. Sin globals inconsistentes,
sin segunda implementación, sin degradación silenciosa.

### Fail-closed de verdad al arrancar

ADR-036 prometía que una configuración inválida fallaba «al arrancar»; la
implementación lo hacía de forma perezosa, en la primera petición que tocara el
BFF. Ahora se valida en el `lifespan` de FastAPI: DSN ausente, clave de cifrado
ausente, backend desconocido, `memory` bajo `oidc` sin el opt-in explícito, o un
flujo de navegador **a medio configurar**, y el proceso no arranca. Un
despliegue sólo-bearer (ninguna variable del BFF definida) sigue siendo válido:
las rutas del BFF responden 404 y no se exige base de datos, porque ninguna
sesión puede crearse.

### Qué se verificó de verdad

| Verificación | Resultado | Clase |
|---|---|---|
| Contrato del `PostgresSessionStore` | **36 tests en verde** contra PostgreSQL **16.15** desechable (espacio de usuario, sin `sudo`, sin puerto TCP, socket unix, destruido al terminar) | `VERIFIED_TEST` |
| Migración `20260909000004` | Aplicada dos veces (idempotente) y revertida dos veces, sin residuo, en ese mismo cluster | `VERIFIED_TEST` |
| RLS | Activado, cero políticas, `FORCE` deliberadamente apagado → **el DSN debe conectar con el rol propietario** | `VERIFIED_CONFIG` |
| Suite backend completa | **619 pasando, 28 skipped** (647 recolectados) | `VERIFIED_TEST` |

### Afirmaciones retiradas por no ser reproducibles

- **«544 tests pasando, 7 skipped»**: medido, 619/28. La cifra anterior se
  escribió antes de añadir ~106 tests de la misma sesión.
- **«nginx: de 2 a 5 rutas exactas»**: el archivo real tiene **diez** reglas
  (siete `location =` y tres prefijos).
- **«MEASURED 2026-09-09» sobre `/oauth2/two-factor`, `/oauth2/two-factor-methods`
  y los prefijos `/css/`, `/js/`, `/images/`**: no se pudo correlacionar con
  ninguna evidencia registrada — el documento de laboratorio da el lab por
  destruido antes de esa hora y no lista esas rutas. Las cinco reglas quedan
  marcadas **`NOT_VERIFIED`** en la propia plantilla y **bloquean la Fase 2**
  hasta que se midan en un laboratorio nuevo. La afirmación se retira, no se
  reescribe.
- **ADR-036 «Propuesta»** en tres documentos: está **`Aceptada`** desde
  2026-09-09.

### Hueco cerrado en Control 6

`application/password_provisioning.py` — el chokepoint del que depende toda la
exigibilidad del control — **no tenía un solo test**. Añadidos 10: que una
contraseña violatoria nunca llega al puerto de identidad, que un sujeto sin
nombre se rechaza en vez de pasar en vacío, que «sin adaptador» no se confunde
con «política satisfecha», y que ni el log de rechazo ni el de éxito contienen
la contraseña.

`CONTROL_6_AMAZON` sigue **`PARTIALLY_SATISFIED`**. Nada de esto es evidencia
conductual de producción, y no puede citarse a Amazon.

### Qué sigue bloqueado (sin cambios)

`RF-03`/`RF-04` `NOT_VERIFIED`; RF-03 behavioral `NOT_EXECUTED`; reaplicación a
Amazon `BLOCKED`. La activación necesita, en este orden: medir la superficie de
nginx, aplicar la migración a Supabase, integrar el frontend, crear el tenant
con usuarios reales, y sólo entonces `JUVAL_AUTH_MODE=oidc`.

---

## Sesión 2026-09-10 (bloque 2) — laboratorio de la superficie pública nginx

**Estado: PARTIALLY IMPLEMENTED.** La plantilla `deploy/fusionauth/nginx-fusionauth-public.conf`
se ejecutó por primera vez bajo un nginx real. Hasta ahora toda afirmación
sobre ese archivo provenía de leerlo.

**Nada productivo se tocó**: nginx **no** se activó, `/etc/nginx` no se leyó ni
se escribió, FusionAuth no se contactó, no se abrió ningún puerto LAN,
`JUVAL_AUTH_MODE` sigue sin definir y no se aplicó ninguna migración.
`frontend/` intacto.

### Cómo

Binario nginx 1.24.0 obtenido con `apt-get download` + `dpkg-deb -x` a un
directorio scratch — **sin `sudo`, sin `apt install`, sin estado de paquetes del
sistema**. Prefijo, pid, logs y temporales bajo un único `mktemp -d`, borrado en
`finally`. Listener en un puerto efímero de `127.0.0.1` (nunca `8080`); upstream
= servidor eco desechable (nunca `9011`/`9012`), de modo que **el laboratorio es
estructuralmente incapaz de alcanzar FusionAuth**. Se sustituyen exactamente
tres cosas de la plantilla y se **afirma** que ninguna línea `location`,
`limit_except`, `return` ni `proxy_set_header` cambió.

Herramienta: `tools/nginx_surface_lab.py` (59 sondas + 4 mediciones).
Tests: `tests/compliance/test_nginx_public_surface.py` (11 estáticos siempre,
68 conductuales que hacen `skip` sin binario nginx).
Evidencia completa: `docs/research/NGINX_PUBLIC_SURFACE_LAB.md`.

### Qué quedó medido (`LAB_BEHAVIOURALLY_VERIFIED`)

- **Ninguna petición denegada llegó al upstream**: 0 de 45 sondas no-proxied.
  Es la única propiedad que justifica una allow-list, y no estaba probada.
- La lista de nunca-publicar de ADR-035 Condición 2 (`/admin`, `/api`,
  `/account`, `/password`) responde 404 para todos los verbos sondeados, igual
  que los siete flujos OAuth no usados.
- Las siete rutas exactas son exactas: `/oauth2/authorize/`, `/oauth2/authorizex`,
  `/oauth2/token/x` y `/OAuth2/authorize` son 404.
- Cada `limit_except` rechaza con 403 los verbos que excluye.
- Las cinco cabeceras reenviadas llegan con los valores escritos **aunque el
  cliente envíe valores hostiles**; `X-Forwarded-For` **añade**, no reemplaza.
  Importa más allá de la higiene: FusionAuth construye su emisor con ellas.
- El query string de autorización se reenvía byte a byte (PKCE y `state` intactos).
- Sin el include del host, `nginx -t` **rechaza** el archivo — fail-closed.

### Hallazgos

- **N-1 (abierto, con exposición)**: el inventario del archivo dice «Everything
  else: 404» y para tres URIs es **falso**. `/css`, `/js` e `/images` responden
  **301**, con `Location` construido a partir del `Host` **del cliente**, en
  `http://`, y filtrando el puerto del listener. `proxy_set_header Host` no
  puede influirlo: el redirect se genera antes de proxyear. `absolute_redirect off;`
  lo resuelve, pero **no se aplicó** — es un cambio de comportamiento en una
  plantilla de despliegue, o sea una decisión, no una limpieza.
- **N-2 (bueno)**: el traversal por encima de la raíz se rechaza con **400**
  antes de elegir location. Se esperaba 404; 400 es más fuerte.
- **N-3 (registrado)**: la plantilla no fija ninguna cabecera de seguridad,
  ni `server_tokens`, ni `limit_req` sobre `/oauth2/authorize` — el endpoint al
  que el formulario hospedado envía credenciales. Depende de un
  `/etc/nginx/nginx.conf` que no está en el repositorio.

### Qué NO cambió

Las cinco reglas `NOT_VERIFIED` **siguen `NOT_VERIFIED`** y **siguen bloqueando
la Fase 2**. No lo estaban por falta de medición del proxy: lo están porque
nadie ha establecido qué sirve FusionAuth 1.69.0 (`/oauth2/two-factor`,
`/oauth2/two-factor-methods`, y qué prefijos de assets piden sus páginas). Eso
es una pregunta sobre el proveedor y necesita una instancia de FusionAuth, no un
proxy. Este laboratorio no puede responderla y no la promueve.

`CONTROL_6_AMAZON` = `PARTIALLY_SATISFIED`; RF-03 behavioral = `NOT_EXECUTED`;
reaplicación a Amazon = `BLOCKED`; `IDENTITY_SECURITY_GATE` = `BLOCKED`. Sin
cambios. **Nada de esto es evidencia de producción ni puede citarse a Amazon.**

### Fuera de alcance, registrado

`SEC-DEPS-01 = PENDING_REVIEW` — Dependabot reporta 5 vulnerabilidades (4 high,
1 moderate) en `frontend/`. No se inspeccionó la rama, no se mergeó, no se tocó
`frontend/`. Sin inferencia de impacto.

## Sesión 2026-09-10 — accelerator: reconstrucción y seguridad de tests

Workspace autoritativo `/home/juval/JUVAl/APP`, HEAD inicial `16189b7`, limpio;
referencia local `origin/master` = `32c3aef`, divergencia local 0/3. `git fetch
origin` falló con `Permission denied (publickey)`: estado remoto actual
NOT_VERIFIED, push bloqueado por autenticación SSH; sin reescritura.

Baseline medida: 734 passed, 96 skipped; compliance 9 PASS / 1 WARN / 0 FAIL,
secret scan sin hallazgos en 422 archivos. El warning exige completar el owner
del plan de incidentes. No es evidencia de cumplimiento Amazon.

Corrección de seguridad: los tests de sesiones ya no toman DSNs de runtime ni
borran tablas de sesiones compartidas. Usan una variable exclusiva de tests y
un esquema aleatorio por caso; `tools/session_store_lab.py` reproduce el
contrato y la migración/rollback en PostgreSQL desechable. Ver `tests/README.md`.

La sesión no expone control de navegador: baseline Admin UI de redirects no
leído, mutación temporal no ejecutada; real login sigue NOT_VERIFIED. Frontend
congelado, FusionAuth y PostgreSQL de runtime sin cambios.

Validación del cambio: laboratorio PostgreSQL **37 passed / 2 skipped**
(skips estructurales de memoria); selección amplia BFF/sesiones **70 passed /
22 skipped** sin DSN de tests; `git diff --check` limpio. El primer intento del
nuevo lab detectó encoding SQL_ASCII por `--no-locale`; corregido fijando UTF-8,
sin debilitar tests. Self-review: esquema/cleanup aislados, sin dependencia
nueva, sin cambios de dominio ni frontend. Ponytail no está disponible como
herramienta/skill en esta sesión; revisión manual de simplicidad realizada,
no se declara ejecución del plugin.

### Accelerator — session startup readiness

Second correction: PostgreSQL selection now verifies connectivity, table and
column existence, role ownership and zero-policy RLS in a bounded read-only
startup check. Before this change a nonempty bad DSN passed startup because
adapters connected lazily. No migration or runtime activation. ADR-036 remains
the approved policy; this makes its stated startup behavior effective.

Validación startup: backend **735 passed / 104 skipped** (los nuevos tests de
PostgreSQL requieren el DSN de tests; verificación real separada: **44 passed /
2 skipped**). BFF focal **54 passed**. No datos de sesiones leídos por el
preflight; sin migración implícita; sin fallback. Self-review y diff check sin
hallazgos pendientes del cambio. Límites: no prueba completa de tipos/índices,
no garantiza disponibilidad después del arranque.

### Accelerator — nginx N-1 and N-3

ADR-037: inactive template pins relative nginx redirects and suppresses version
emission. **90 nginx tests passed**, no skips with disposable nginx. N-1 =
REMEDIATED_TEMPLATE / LAB_BEHAVIOURALLY_VERIFIED; N-3 partial (version only).
No asset allow-list expansion; D-1/real login remain blocked, no production
activation. Runtime FusionAuth untouched; frontend diff remains empty.

Gate nginx ampliado: **224 tests compliance passed** con nginx real; script de
lab 0 fallos, `Location: /css/`, sin Host/scheme/port reflejado y `Server: nginx`.
Self-review: ninguna ruta añadida, ninguna cabecera de upstream reinterpretada;
el gate de compatibilidad real y producción permanece abierto.

### Accelerator — truthful session projection and dependency review

`/auth/session` no longer reports an authenticated snapshot after refresh has
revoked its store record. It reloads and clears cookies on missing state;
provider outages retain the valid session. Regression covers both HTTP outcomes.

SEC-DEPS-01 reviewed against current npm advisories and local dependency paths:
five unique frontend advisories (four fast-uri high, one Vitest moderate),
dev/build-only paths; no reachable exploit sink found in reviewed product/config.
Minimal patched targets and gates in `docs/compliance/SEC_DEPS_01_REVIEW.md`.
Remediation blocked by explicit frontend freeze; no files there changed.
Backend pip-audit and other two frontend lock audits show no known advisories.


### Accelerator — new remote evidence changes consolidation boundary

Read-only HTTPS fallback succeeded after SSH denial: fetched `origin/master`
**6a6d07c04c17cbf7e3714c32d3d2e1576d5ddf6a**, with two remote-only commits
`bafaa19` and `6a6d07c` adding `project-portal/` and its connected Git deployment
configuration. This supersedes the earlier statement that the remote could not
be read or that no portal existed. At discovery divergence was **2 remote-only /
8 local-only**. No local work overwritten, no merge/rebase or push performed.
The user's no-merge-to-synchronize/no-rebase rules require an explicit
preservation/integration decision. Portal deployed status is a remote doc claim,
not newly verified Vercel runtime evidence.

Final core milestone gate: backend with real nginx **821 passed / 36 skipped**;
disposable sessions **44 passed / 2 skipped** separately. Discovery **103 passed**;
auth/BFF selection **93 passed**. Compliance **9 PASS / 1 WARN / 0 FAIL**;
secret scan clean (427 files at that pass). Frontend content diff from starting
HEAD is empty. ADR-038 topology is PENDING, no cookie policy or DNS changed.

### Accelerator — portal draft and scanner coverage

Preserved remote portal history on branch `accelerator/portal-readiness`.
Draft maps current lab/blocker evidence from immutable Linux commit `63568c4`
and removes invented Windows/origin provenance from the JUnit exporter.
Validation: 10 model + 4 component/i18n + 3 Python exporter tests, lint/build,
portal npm audit clean. No hosted deployment or product-frontend changes.
The source scanner now covers JS/TS module suffixes used by the portal;
23 compliance-check tests pass; portal pattern scan clean (38 files).

### Accelerator stop checkpoint — 2026-09-10

Nine coherent work loops completed; phase remains **PARTIALLY IMPLEMENTED**.
Portal branch `accelerator/portal-readiness` = `29e90a6`; core tested at
`3a17e12`. Noncommitting integration rehearsal clean, tree
`92c0529328c6c1de6d5245f8726164d33a7b7f18`: **825 passed / 36 skipped**, compliance
9 PASS / 1 WARN / 0 FAIL, secret scan clean (457 files). Skips: unavailable live
DB tests and structural cases; disposable session tests verified separately.
No runtime activation, no merge on master and no push. Both temporary worktrees
and nginx/PostgreSQL scratch removed. Main worktree and protected frontend
integrity checked. Resume and batched human queue: `IDENTITY_SECURITY_READINESS.md`.

Self-review: correctness regressions covered; evidence scope distinguishes code,
lab, runtime and production; provenance/domain unchanged; no silent fallback or
secret-bearing output added; migrations isolated; no speculative business rule;
no product frontend changes. Ponytail unavailable, manual simplicity review only.
ADRs 034/036 updated, 037 accepted under scoped accelerator authorization,
038 proposed. Estimates for implementation, verification, production, security
and Amazon readiness: NOT_MEASURED. Public/production/control gates stay blocked.


## Sesión 2026-09-10 — accelerator second wave

Estado: PARTIALLY IMPLEMENTED, siguiente límite humano/externo. Historiales
remotos/locales integrados sin conflictos en 5c52451 + 880334c; branch
accelerator/portal-readiness preservado y contenido. Push todavía bloqueado por
SSH; fetch HTTPS confirma remoto 6a6d07c, ningún commit remoto desconocido.
Mapa completo: research/ACCELERATOR_SECOND_WAVE_GIT.md.

SEC-DEPS-01: cinco avisos remediados (73faa8a); únicamente lockfile frontend,
fast-uri 3.1.6, Vitest 4.1.11. 155 tests frontend, lint/build y smoke PWA offline
PASS; audit cero en frontend/frontend-next/demo/portal. Sin fuente o UX modificada.
ADR-038 Aceptada: app/api/id same-site, dominio HUMAN_DOMAIN_SELECTION_PENDING.
Chromium sintético verifica cookies; no evidencia de TLS/BFF/IdP reales.

ADR-039 (7e908e7): exclusión de refresh entre instancias antes de llamar IdP,
relectura de generación, negativa de escritura expirada y HTTP 429/5xx temporal.
Full backend 834 PASS / 38 SKIP con nginx desechable; PostgreSQL 48 PASS / 2 SKIP
más reinicio real del cluster privado PASS, limpieza confirmada. Residual: IdP y
DB no comparten transacción; un fallo después de rotación puede requerir login.

Portal: ADR-040/modelo 1.2 con cinco medidas independientes, scope y denominadores;
11 tests modelo + 4 componente/i18n + 3 exportador Python PASS, lint/build PASS.
E2E inicial 12 PASS/1 FAIL detectó fallback 200 en rutas privadas inexistentes;
corregido antes de cierre, ampliado a archivo sintético y codificación: 14/14 PASS.
No datos privados expuestos observados. No afirmar despliegue publicado.

Runbook humano compacto: compliance/IDENTITY_OPERATOR_CHECKPOINT.md (migración,
RF03, backup/restauración). Ejecución RF03 y migración live no autorizadas.
Control 6 PARTIALLY_SATISFIED. Real login NOT_VERIFIED, baseline redirect no
establecido, ninguna mutación ni cleanup inferido. N-1 lab verificado; D-1 y
nginx/FusionAuth real esperan evidencia del login. N-3 parcial, sin nuevas
cabeceras incompatibles ni ampliación de allow-list. SSH/Admin/dominio/live/RF03/
destino off-host/owner/ventana mantenimiento en cola humana. Sin reboot, upgrades,
UFW/SSH, apertura de puertos, secretos, compras o envío Amazon.


## Sesión 2026-09-10 — third-wave durable resume

Checkpoint b338a67 verificado por fetch SSH autenticado: HEAD=origin/master,
0/0. Se reutilizó el agente SSH autenticado, sin cambios de transporte/SSH ni
lectura de claves. Ambas ramas del portal contenidas; no cherry-pick duplicado.

Seis alertas GitHub reportadas (4 high, 2 moderate) siguen sin IDs/manifest:
API Dependabot 401; no inferir equivalencia con los cinco avisos frontend previos.
Auditorías npm de los cuatro lockfiles y entorno Python instalado limpias.
Hallazgo independiente: mínimos Python permitían versiones vulnerables. Cuatro
floors corregidos y probados en venv privado; cryptography49 rechazado por nuevo
aviso, mínimo50 verificado. Detalles y 23 filas deduplicadas de rangos permitidos
en compliance/DEPENDENCY_THIRD_WAVE_RECONCILIATION.md; no son la lista GitHub.

Gates: 839 backend PASS / 38 SKIP en ambos entornos con nginx desechable;
48 PostgreSQL PASS / 2 SKIP más restart PASS; frontend155, lint/build/smoke PASS,
sin cambios en ningún árbol frontend. Nuevo preflight read-only y test de recuperación
re-login tras pérdida de persistencia durante rotación. Portal descuenta el crédito
de dependencias mientras la discrepancia esté abierta, según ADR-040.

Admin controlable/autenticado y baseline real no disponibles: no redirect añadido,
no login, no callback, no user ni RF03. N-1 lab retenido; D-1/compatibilidad real
bloqueados. Migración live/auth/TLS/DNS/UFW/SSH/reboot/apt/submission sin cambios.


Third-wave preflight follow-up: digest primary keys must be valid and
nondeferrable in both identity tables. Four real PostgreSQL negatives now reject
missing/deferrable keys; no migration change. PostgreSQL final52 PASS/2 SKIP plus
restart PASS. Full suite final839 PASS/42 SKIP; new skips are the four explicit
PostgreSQL-only cases when no disposable DB is supplied to the full suite.

## Sesión 2026-09-10 — cuarta ola

Rotación aditiva de claves verificada sobre PostgreSQL desechable; RF03 preparado
con cambio obligatorio y correo .invalid. Backend 839 PASS / 43 SKIP; PostgreSQL
53 PASS / 2 SKIP y reinicio real PASS. Login real sigue NOT_VERIFIED; ventana
Admin preparada para autenticación privada. Dependabot no bloquea trabajo
independiente: PARTIAL / GITHUB_METADATA_REQUIRED. Evidencia y límites en
`docs/research/ACCELERATOR_FOURTH_WAVE_RESULTS.md`. Sin activación de producción.

## Continuación 2026-09-10 — login real observado

El bloqueo de baseline queda superado: lista vacía / ExactMatch leída mediante
Admin autenticado; callback temporal añadido, probado y eliminado con readback
exacto en cada ciclo. Login inicial real renderizado en Chromium; nginx real
loopback devuelve formulario y assets iniciales. D-1 PARTIAL: MFA/WebAuthn/fuentes
y recuperación aún pendientes. No producción ni Control 6 satisfecho. Evidencia:
`docs/research/REAL_JUVAL_LOGIN_20260910.md` y JSON sanitizados asociados.

## Quinta ola — 2026-09-10

D-1 permanece PARTIAL. Recuperación hosted excluida explícitamente por ADR-035;
no se publica por aparecer el enlace. Rutas MFA genéricas alcanzables, sin prueba
de flujo MFA. Fuentes/icono de huella condicionales; configuración actual pendiente
de lectura Admin. Cuatro headers candidatos pasan renders genéricos por separado,
no se activan en nginx. Matriz y evidencia en
`docs/research/FUSIONAUTH_D1_FIFTH_WAVE.md`. Sin cambios productivos ni redirects.

### Quinta ola — lectura Admin completada

Recuperación email deshabilitada en tenant, heredada por aplicación. MFA Required
con autenticador habilitado; aplicación hereda política. WebAuthn deshabilitado
en ambos. Redirects [] / ExactMatch verificados de nuevo, sin mutaciones. D-1
sigue PARTIAL por flujo MFA/assets condicionales/callback/logout. Evidencia:
`docs/research/fusionauth-wave5-admin-readback.json`. No ejecución RF03.

## Descubrimiento MFA desechable — 2026-09-10

Un único usuario completó enrolamiento TOTP hosted con Required y llegó al
callback interceptado, sin intercambio de tokens. Esto invalida la conclusión
general de que el hosted enrollment no existe. Tres rutas exactas candidatas
se añaden a la plantilla inactiva (ADR-041 Propuesta). El login posterior por
nginx no superó credenciales; no se verificó el desafío de factor existente.
Cambio de contraseña autorizado por humano rechazado por política, sin relajarla.
Usuario eliminado; JUVAl volvió a 0, redirects [] / ExactMatch restaurados.
D-1 PARTIAL; RF03 no autorizado; Control 6 parcialmente satisfecho. Evidencia:
`docs/research/MFA_DISPOSABLE_DISCOVERY_20260910.md`.


## Accelerator 2026-09-15 — compliance evidence classification

Starting local HEAD and cached origin/master: f03574b, clean, divergence 0/0.
Fresh SSH fetch failed with publickey rejection; current remote state is not
verified. No push may be claimed until an authenticated fetch succeeds.

The compliance checker now rejects invalid audit reports without calling them
confirmed vulnerabilities, reports skipped audit coverage, and fails on unreadable
scan files. Its static auth/deadline checks no longer claim behavioral or human
verification. The one ROLE PLACEHOLDER marker is historical; the incident plan's
§2/§12 already records named roles and approval. No organizational approval changed.

Focused first run: 32 PASS / 1 FAIL exposed the local skipped package's absent
version. The parser and fixture were corrected; focused rerun 33 PASS. Added
all-skipped negative; final focused gate 34 PASS; compliance regression: 168 PASS / 86 SKIP. The 86 nginx
behavioral cases skip because no nginx binary is available; they are not verified
by this run. No nginx template, backend runtime, database or frozen frontend change.
Compliance: 9 PASS / 2 WARN / 0 FAIL; working-tree secret scan: 494 files, no
pattern findings. Warnings are the historical role marker and partial dependency
audit coverage; local audits do not close GitHub alerts. Full backend/PostgreSQL/
frontend suites not run for this tooling-only change.

Decision: APPROVED by accelerator authorization to correct evidence/tooling;
no new architecture or production decision. Ponytail callable capability is
unavailable; manual correctness/security/simplicity review performed. The real
MFA branch is not started: Chromium Admin remains open, no usable browser tool
is connected, no redirect or user mutation was performed. Browser reconnection
and local SSH authentication have been requested while independent work proceeds.


## Accelerator 2026-09-15 — reviewed local historical scan and queue reconciliation

The user reviewed and approved `NO_PATTERN_FINDINGS_IN_SCANNED_LOCAL_HISTORY`:
164 locally reachable commits, 1008 eligible unique blobs, 22 excluded unique
blobs, zero findings. The scan was not repeated after approval. Structural
review confirms the JSON contains only aggregate evidence and nine explicit
scope limitations; no individual finding, secret content or derived identifier.
Evidence: `research/history-secret-scan-20260915.json`. SECRETS S-3 is PARTIAL,
not proof of absolute absence, remote synchronization or GitHub alert closure.

The current identity ledger now distinguishes the USER_REPORTED Marcus identity
from an independently read baseline, preserves the existing browser session,
and identifies the real remaining RF-01/RF-05 exercises instead of requesting
role assignments already approved in the incident plan. A local configuration
observation no longer asserts absence of secrets in every environment.
Decision APPROVED: explicit review/accelerator authorization, no architecture
change. No IdP/user/redirect/configuration mutation or cleanup was performed.
Ponytail unavailable; manual disclosure, chronology and evidence-level review.
Documentation-only gates use compliance, current-tree secret scan and diff-check;
backend, nginx, PostgreSQL and frontend suites are not repeated for this change.


## Accelerator 2026-09-15 — per-route compliance guard

A disposable two-route source demonstrated a false PASS: two permission markers
on one protected handler hid another handler without any permission dependency.
The checker now parses main.py without execution and verifies the existing direct
`Depends(require(permission))` parameter convention separately for each HTTP
route declaration. Comments, unrelated functions and function-body calls cannot
satisfy another route; empty/invalid source fails instead of passing vacuously.
Multiline and stacked decorators and keyword-only parameters are covered.

Focused tests: 42 PASS. Compliance regression: 176 PASS / 86 SKIP (nginx binary
unavailable; no new nginx behavioral claim). Only checker/tests/docs changed;
no API behavior, RBAC policy, IdP, database, frontend or production changes.
Decision APPROVED by accelerator verification authorization; no new ADR required.
Manual self-review: existing Python AST/stdlib only; no new dependency, no runtime
source execution. Scope is main.py's direct app HTTP declarations, not included
routers, alias/shadowing resolution, effective permission semantics or deployed
authorization. Existing behavioral RBAC evidence is neither rerun nor promoted.

The preceding documentation commit 355e4c4 passed compliance 9 PASS / 2 WARN /
0 FAIL, current-tree secret scan 495 files, and diff-check. ADR-040/model 1.2
measured that exact committed snapshot: implementation 44/68 (65%), verification
17/68 (25%), production 0/12 (0%), security 5/16 (31%), Amazon 0/18 (0%). The
model/scopes were not changed to award credit for these tooling improvements.

Remaining high-value branches require external/browser/secret/production or
organizational action, as enumerated in IDENTITY_SECURITY_READINESS. No new
source integration, business scoring, production deployment, live migration,
provider mutation, host hardening or human exercise is authorized by these
checker fixes. Full backend, scratch PostgreSQL and frontend suites were not
run for this tooling-only diff.


## Controlled MFA resumption — 2026-09-16

ABORTED_AT_PREFLIGHT / BLOCKED, initial HEAD 958447c, clean, cached origin f03574b
(0/7). Existing seven commits preserved. No runtime/login created. Static local
Playwright review found HTTP redirects bypass the route handler; synthetic tests
remain valid but do not establish live redirect containment. No workaround or
transport activation. [Detailed evidence](research/REAL_MFA_ABORT_20260916.md).
Human Admin deletion/readback confirms Marcus absent, JUVAl 0, Default/Daniel
intact, pre-existing callback and Exact match unchanged. HUMAN_ADMIN_READBACK,
not machine verification. Full pytest 787 PASS / 129 SKIP, Node controllers 13 PASS.
Skips: missing nginx/unconfigured databases and storage-inapplicable cases.
No frontend/dependency/runtime change; ADR-041/042 Proposed; ADR-040 unchanged.
Ponytail unavailable; manual review. Next: separately reviewed containment design
and synthetic HTTP redirect-chain coverage before a future authorized experiment.

Closeout checks: offline compliance + worktree secret scan 8 PASS / 1 historical
marker WARN / 0 FAIL, 513 files without pattern findings. Private ports free,
:100/dedicated Chromium absent, existing Admin viewer loopback listeners present.
Diff-check and frozen frontend comparison passed. SSH fetch failed (publickey);
origin/master f03574b remains cached, remote state NOT_VERIFIED. No push; publication
awaits authenticated fetch and remote-only=0. No network dependency audit repeated.

## Reboot recovery of RF loop — 2026-09-18

Recovered `59bc3a1`, clean worktree, no later commits or interrupted untracked
work. MFA remains explicitly frozen; prior preparation is superseded, callback
containment not repeated. RF-01/04/05 HUMAN_BLOCKED, RF-02 EXTERNAL_BLOCKED;
all remain PARTIAL. Existing implementation/evidence reused, stale IRP/network/
access documentation corrected without policy changes. Fresh read-only listeners
include all-interface 631/9011/9012; effective firewall/external denial not verified.
[Recovery record, scoped test results, human gates and ADR-040 metrics](compliance/RF_RECOVERY_20260918.md).
127 scoped tests passed, one deprecation warning, no skips. No frontend, provider,
production, domain or processing change; only auth.py module-description correction.
Local commit authorized, no push. Ponytail unavailable; manual self-review performed.
