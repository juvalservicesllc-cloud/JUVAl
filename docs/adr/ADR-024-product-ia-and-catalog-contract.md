# ADR-024: Product IA and Catalog Contract Boundary

- Estado: Aceptada — por instrucción explícita del usuario, M0, 2026-08-19.
- Fecha: 2026-08-19

## Decisión

`frontend/` is the only production frontend source of truth. `demo/` is a
UX/product-experience reference only. Its browser-side parsing, localStorage
run/favorite persistence, custom router, simulated enrichment, and simulated
market data must not be promoted as production implementation.

Primary navigation is **Dashboard, Upload, Catalog, Runs**. Appearance lives
under Settings. Methodology is contextual help/documentation. Compare and
Saved Opportunities are reserved contextual capabilities, not primary routes,
and are deferred until their separate domain/persistence decisions exist.

The user-facing name is **Catalog**. Its resource remains the immutable,
run-scoped record snapshot `(execution_id, record_ref)` from ADR-012/019;
this ADR does not create a global Product entity or rename domain objects.

The real workflow is:

```
Upload -> validation -> processing -> result -> review -> catalog
```

Import and Pipeline are not primary destinations. The UI may show only
processing states and per-file/record results that the backend actually
reports; it must never simulate unimplemented stages.

Product Detail is run-scoped and ordered as: Decision, Identity, Economics,
Risks, Data Quality, Provenance, Market, Explanation, Actions. Market history
is `DEMO_FIXTURE` until an authorized source exists, or `INFERRED` only when a
documented rule produces it; it is never `VERIFIED` without evidence.

## Catalog query/export direction

M1–M4 will use one canonical, run-scoped query model for catalog display and
filtered export. Existing filters remain `search`, `decision`, `sort`,
`direction`, `limit`, and `offset`. Proposed additions are documented in
`docs/architecture/PRODUCT_EXPERIENCE.md`; they are not implemented or
commercially approved by this ADR.

Financial query modes must be explicit: `VERIFIED_ONLY` excludes inferred,
missing and invalid economic values; `INCLUDE_INFERRED` includes VERIFIED and
INFERRED but still excludes NOT_FOUND and INVALID. A default for a future
economic threshold filter is deliberately not chosen here.

## Deferred decisions

- Compare requires a future comparable-identity ADR; exact supplier URL is
  not a production identity model.
- Saved Opportunities requires authentication, ownership, persistence and
  data isolation; `localStorage` favorites are rejected.
- Opportunity ranking requires a business definition; highest ROI alone is
  not a valid recommendation.
- Real market history requires an authorized source decision and the data
  source process.

## Consequences

The next implementation slices may improve the production UX without copying
the demo architecture. Contract additions must reuse canonical snapshots,
preserve the complete `FieldValue` provenance needed by Product Detail (the
current snapshot carries only `value`/`status`, so M3 requires an additive
payload evolution), and remain compatible with both SQLite and Supabase
adapters. Historical snapshots must not have provenance reconstructed at read
time. No production code changes in M0.

Future frontend migration phases require the capability-preservation gate in
`PRODUCT_CAPABILITY_BASELINE.md`: functional tests, relevant visual QA, and an
explicit check that protected production capabilities remain available. Green
tests alone do not prove preservation when tests can be removed.

## Related

ADR-003/004 (provenance), ADR-006 (deterministic calculations), ADR-012
(record identity), ADR-014 (PWA), ADR-019 (snapshots), ADR-023 (design-system
governance), and `docs/architecture/PRODUCT_EXPERIENCE.md`.
