# frontend-next E2E (real browser)

`npm run e2e` starts everything it needs and tears it down:

- a **disposable API**: uvicorn on `127.0.0.1:18771`, `JUVAL_AUTH_MODE=disabled`,
  `JUVAL_EXECUTION_STORE=sqlite` in a fresh `/tmp/juval-e2e-*` directory,
  `JUVAL_SUPABASE_DB_URL` stripped from its environment;
- the **Vite dev server** on `127.0.0.1:18772`, pointed at that API;
- Chromium, headless.

Everything is on loopback. Nothing touches Supabase, a migration or a running
service. The temporary directory is removed at the end; `JUVAL_E2E_KEEP=1`
keeps it for inspection.

```bash
cd frontend-next
# Any local Chromium works; otherwise run `npx playwright install chromium` once.
JUVAL_CHROME_BIN=/snap/chromium/current/usr/lib/chromium-browser/chrome npm run e2e
```

The snap launcher (`/snap/bin/chromium`) cannot create its runtime directory for
service accounts; the binary inside the snap runs directly.

Overrides: `JUVAL_E2E_API_PORT`, `JUVAL_E2E_WEB_PORT`, `JUVAL_PYTHON` (default
`../.venv/bin/python`), `JUVAL_E2E_OUTPUT` (default `test-results/`: failure
screenshots, traces, `report.json`, and the desktop screenshots of the D7 screens).

## What `d7-demand.spec.ts` covers

D7-D (pending demand verification) and D7-B (declared demand, ADR-052) through
the real import pipeline. `fixtures.py` writes the XLSX inputs, whose demand
values are labelled synthetic. It also seeds one pre-D7 snapshot.

The tests run in order and share the database:

- empty and loading states;
- upload without demand, which gives REVIEW `DEMAND_UNKNOWN`;
- the server-side "Pending demand verification" filter;
- the Dashboard count and its link;
- Product Detail from the Catalog, plus Back;
- a declared 1,000,000 units: INFERRED, `USER_INPUT`, "Not used for this
  decision", still REVIEW;
- an invalid value (raw kept, diagnostic);
- incomplete context (raw kept, diagnostics);
- a historical snapshot (`NOT_CAPTURED`, not classified);
- Catalog export vs. run download vs. API on every `demand_*` column;
- Retry after a failed request, and an unknown record;
- desktop screenshots with basic accessibility checks.

## What `g17-suggested-price.spec.ts` covers

GOLDEN 17 (ADR-053): `suggested-price.xlsx` declares one usable amount (EUR), one
with a lowercase currency and one zero. The spec covers:

- the preview group;
- a non-sortable Catalog column between Cost and Selling;
- the Product Detail panel, with provenance and diagnostics;
- the decision and selling price staying the engine's;
- the Catalog export, the run download and the API agreeing on every
  `supplier_suggested_price_*` column;
- NOT_CAPTURED on the historical snapshot;
- screenshots with basic accessibility checks.

It reuses `support.ts`, and seeds the historical run itself when it runs alone.

Every test fails on a console error, an uncaught exception or an HTTP status
≥ 400 that it did not declare as expected.
