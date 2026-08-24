# JUVAl Product Experience and Catalog Contracts

## Status and scope

**M0 — APPROVED DESIGN, LARGELY IMPLEMENTED** (design 2026-08-19; status
re-verified against the code 2026-08-20). The information architecture,
Catalog contract and percentage semantics below are implemented and covered
by tests; Compare and Saved Opportunities remain deferred for the reasons
stated in their sections. `frontend/` is the production PWA; `demo/` is a UX
reference only. The code and API contract remain the source of truth for what
is implemented today — where this document and the code disagree, the code
wins and this file is corrected.

## Information architecture

| Destination | User question | Data source | Primary action | Drill-down / mobile |
|---|---|---|---|---|
| Dashboard | What happened, what needs attention, what next? | One selected persisted run and its real analytics | Upload / open the active catalog | Compact KPI/action cards; drill into run or catalog |
| Upload | How do I process these supplier catalogs? | `POST /api/v1/runs`, `POST /api/v1/batches` | Submit up to ten CSV/XLSX files with explicit thresholds/fees | Per-file validation, real processing state naming every submitted file, then per-file and aggregate result |
| Catalog | Which records in this run should I inspect? | `GET /runs/{id}/records` | Open record detail | Run selector and filters remain visible; table becomes cards/essential columns on mobile |
| Runs | What has been processed and is auditable? | `GET /runs`, run snapshots | Open a run | Run Detail -> batch context / record detail |
| Batch Detail | Which files did one submission contain, and how did each fare? | `GET /batches/{id}`, `GET /runs/{id}/batch` | Open a child run | Included-file table; each processed file links to its own independent run |
| Settings / Appearance | How should this workspace look? | local visual preferences only | Change appearance | Not primary navigation |

Upload is the only entry into processing. Validation, processing and result
are states of that workflow; Run Detail is its auditable review surface.
Catalog replaces the user-facing term Products but stays run-scoped.

A Batch groups child runs; it never merges them. Batch scope and
`ExecutionRun` scope stay distinct everywhere: Catalog, Product Detail and
exports remain per child execution, and a run reached from a batch still shows
its own totals as the primary numbers.

**Percentage vs ratio.** The domain stores ROI and margin as ratios (`0.30`);
operators read and type percent (`30`). `frontend/src/contract.ts` is the
single conversion point: the input takes a percentage, the canonical query and
the export carry the ratio, and the active-filter chip reads `30%`. The
domain's ratio semantics are never changed to match an input control.

## Product-detail model

The canonical order is Decision, Identity, Source, Economics, Risks, Data
Quality, Provenance, Market, Explanation, Actions. Source reports the file,
row and source type read from stored field provenance -- never reconstructed;
a snapshot without provenance says so. Economics includes the Profitability
Engine's intermediate terms (selling fees, seller proceeds, total landed
cost); when a snapshot did not store them the row renders an em dash, never
`$0.00`. Every sensitive value displays its
`FieldValue` status. The current market chart is a `DEMO_FIXTURE`; it cannot
alter BUY/REVIEW/PASS, ranking or filtering. A stable direct record lookup is
required before Product Detail can rely on URL refresh beyond the first page.

### Provenance payload (F1)

F1 now serializes the complete domain `Provenance` additively in each
`FieldValueOut` (`source`, `source_type`, `retrieved_at`, `method`, optional
`confidence`, `evidence`, and `source_reference`), plus the existing `unit` and
`raw_value` when present. New snapshots therefore retain the information
needed by Product Detail and Catalog without recalculation.

Catalog and detail return the same projection. Existing historical snapshots
that do not contain it return an explicit absent/legacy provenance payload
(`provenance: null`); they are never reconstructed or inferred at read time.
This is a snapshot/API evolution, not a new calculation, global identity, or
business rule.

## Contract A — canonical single-record lookup (IMPLEMENTED F1)

```
GET /api/v1/runs/{execution_id}/records/{record_ref}
```

- `execution_id` and URL-decoded `record_ref` together identify the resource;
  neither is a global product identifier.
- `200`: the exact persisted `RecordOut` snapshot, including the additive
  provenance payload specified above when that snapshot version contains it,
  identical in shape to the catalog response; no recalculation or reconstructed
  domain object.
- `404`: the run is unknown **or** the record does not exist in that run. The
  detail may use a deliberately non-enumerating message such as
  `unknown record for execution`.
- `500`: store unavailable, consistent with existing persisted-read routes.
- Requires a `RecordSnapshotStore.load_record(execution_id, record_ref)`
  capability backed by the existing `(execution_id, record_ref)` primary key.

SQLite and Postgres already have that key. No schema change is needed for the
lookup itself; it is an additive port/API implementation and test slice.

## Contract B — advanced catalog query (PROPOSED)

The canonical query applies only to one immutable run:

```
GET /api/v1/runs/{execution_id}/records?
  search=&decision=&sort=&direction=&limit=&offset=
  min_roi=&min_profit=&min_margin=&economic_status_mode=
  hazmat_status=&hazmat_severity=&bulky_status=&bulky_severity=
  provenance_field=&provenance_status=
```

Existing parameters retain their current meanings and validation. Proposed
parameters are optional and composable with AND semantics:

| Parameter | Canonical snapshot field | Design rule |
|---|---|---|
| `min_roi`, `min_profit`, `min_margin` | `roi/profit/margin.value` | Decimal threshold; requires an explicit economic status mode |
| `economic_status_mode` | field `.status` | `VERIFIED_ONLY` or `INCLUDE_INFERRED`; no silent mixing |
| risk status/severity | `hazmat_*`, `bulky_*` | Exact canonical enum value. `*_status` is risk presence (`PRESENT`/`ABSENT`/`UNKNOWN`), not verification status; severity must later expose its own status before it can be filtered as confidence-bearing data |
| `provenance_field` + `provenance_status` | named `FieldValue.status` | A pair: field is required when status is supplied; allow-list only fields present in `RecordOut` |

`NOT_FOUND` and `INVALID` never satisfy an economic threshold. `INCLUDE_INFERRED`
does not make an inferred field verified; UI must label both the active mode
and each returned value. This is a query/presentation rule, not a new
profitability or decision rule.

**Pending decision:** whether an omitted `economic_status_mode` is rejected
when an economic threshold is supplied, or defaults to `VERIFIED_ONLY`. M4
must not choose this silently. The safer proposed API is to require it when
any economic threshold is present.

## Contract C — reproducible filtered export (PROPOSED)

```
GET /api/v1/runs/{execution_id}/export?<the same catalog query except offset/limit>
```

This endpoint must parse the same canonical query object as Catalog, not a
second export-specific filter model. Export has no pagination: it streams or
writes every record matching the query in the exact requested order. The
output workbook includes a `Query Metadata` sheet containing:

- execution ID and input hash;
- UTC generation timestamp and application version;
- canonical normalized filters, sort and direction;
- total exported count;
- economic status mode, if used;
- canonical snapshot/API schema version and any legacy-provenance limitation;
- a statement that records are immutable snapshots from that execution.

The existing `/download` remains the complete output produced by the pipeline;
it must not change semantics. This is a new filtered-export endpoint.

## Contract D — opportunity query (ANALYSIS ONLY)

“Top opportunity” is not a storage or UI-only sort. It needs an approved
business definition that combines decision, economic evidence, risk and data
quality. `BUY`/`REVIEW`/`PASS` are deterministic outputs, not a ranking. A
highest-ROI sort can favor tiny profits, inferred values, or records with
unknown risks.

The first safe capability is a non-ranking **Opportunities requiring review**
query: records whose canonical decision is `REVIEW`, with visible decision
reasons, risk status/severity and provenance. Any cross-field priority score,
“top” list, weighting, or inclusion of INFERRED values requires an
**ADR_REQUIRED** business definition. Dashboard may link to the equivalent
Catalog query only after that query exists.

## Persistence and scale

Current adapters execute page queries in the database and return only one
page, so 100 and 1,000 records are suitable for the existing offset model.
They store canonical JSON snapshots and have `(execution_id, record_ref)` as
primary key plus `(execution_id, ordinal)` index.

| Scale | Current suitability | Required before expansion |
|---:|---|---|
| 100 | Suitable | None beyond existing tests |
| 1,000 | Suitable for paging; JSON search/sort is acceptable for MVP | Measure with representative data |
| 10,000 | Offset and unindexed JSON expressions become material | Add adapter-equivalent expression/generated-column indexes for supported filters/sorts; define export streaming |
| 100,000 | Not suitable as currently indexed or exported in-memory | Query plan benchmarks, indexed projection strategy, keyset/cursor decision if measured offset cost is unacceptable, streaming/async export and retention policy |

For M4, indexes should be added only for approved query fields. At minimum the
implementation must assess indexes for `(execution_id, decision)`, numeric
ROI/profit/margin values plus their status, and HazMat/Bulky status/severity.
SQLite needs expression indexes over `json_extract`/numeric casts; Postgres
needs matching expression or generated-column B-tree indexes. Free-text
substring search may need a separate measured design (SQLite FTS/Postgres
trigram); it is not approved by this document. The current `%term%` scan is
not a 100k design.

Snapshot JSON already preserves the fields required by Contract B except
severity provenance status: `hazmat_severity` and `bulky_severity` are plain
strings in `RecordOut` despite `RiskFlag.severity` being a `FieldValue` in the
domain. Filters by severity value are possible; confidence-sensitive severity
filtering needs an additive snapshot/API field and contract decision.

## Reserved capabilities

Compare is a contextual Catalog/Detail workflow, deferred until a
comparable-identity model is approved. Exact supplier URL is insufficient.
Saved Opportunities is a contextual capability, deferred until authenticated
ownership, persistence and organization data isolation are approved. Neither
is a primary route or a localStorage feature.

## Delivery sequence

1. **M1:** real Upload -> processing/result -> Run Detail UX; no invented
   stages.
2. **M2:** Catalog terminology and structural UX using current query support.
3. **F1:** Contract A implementation and additive persisted provenance.
4. **F2:** stable run-scoped Product Detail presentation using F1 contracts.
4. **M4:** Contract B/C implementation, indexes justified by supported query
   fields, and query-faithful export.
5. **M5:** actionable Dashboard using real query/analytics capabilities.
6. **M6:** Runs enrichment using real metadata and analytics.
7. **M7:** Compare after a comparable-identity ADR.
8. **M8:** Saved Opportunities after auth/ownership ADR.
9. **M9:** market history after authorized-provider decision.

## Non-negotiable provenance rules

`VERIFIED`, `INFERRED`, `NOT_FOUND` and `INVALID` are distinct states. No
catalog filter, export, dashboard or ranking may collapse them, coerce missing
values to zero, or use demo market data as evidence. Calculated economics keep
the weakest-input status from `combine_verification_status`.

## Capability preservation gate

`PRODUCT_CAPABILITY_BASELINE.md` records the minimum production experience
future frontend work must preserve. A frontend phase requires functional tests,
relevant visual QA, and a documented capability-regression check; a green test
suite alone is insufficient. Removed coverage must be replaced by equivalent
or stronger behavior coverage, unless an intentional supersession is recorded.
