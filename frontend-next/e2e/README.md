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

## What `severity-provenance.spec.ts` covers

Severity provenance (ADR-020) through the real pipeline, using `severity-provenance.xlsx`
with hazmat `true`/`false`/blank/`maybe`:
- the compact tags in the Catalog risk cells, with the Hazmat filter and sorting still working;
- the full labels in Product Detail, with no Amazon claim;
- a historical snapshot with no source shown.

It writes screenshots in dark and light, at desktop and phone width.

## Recovery blocks B/C (2026-11-03)

`recovery-b1` covers 2/10 synthetic XLSX files, each preview, submitted status,
Batch Detail and per-file analytics. Selecting 11 queues the first 10, names
the overflow using the existing contract message, and sends no API request.
Selection itself never submits files. CSV support is unchanged.

`recovery-b2` checks 30% → `min_roi=0.3`, the visible percentage, filtered
XLSX rows and `query_metadata` filters/units. `recovery-b3` uses `seed-buy`
against the disposable SQLite store: an explicitly synthetic rendering
snapshot, not an uploaded BUY outcome (ADR-052). Its economics are coherent;
FieldValues remain INFERRED with synthetic methods. Plain monetary fields
have no status on the API contract; the test does not invent one.

`recovery-b4` captures REVIEW/PASS URLs from the browser's export button,
checks consecutive responses, then starts two requests together and parses
those actual responses. Each workbook's metadata and rows are compared to
the equivalent `/records` query. To also check server protocol errors, capture
the runner's server output in a private directory outside APP:

```bash
# Set LOG to an existing private directory outside the repository.
env -i HOME=/home/juval \
  PATH=/home/juval/.nvm/versions/node/v24.19.0/bin:/usr/bin:/bin \
  LANG=C.UTF-8 TMPDIR="$LOG/tmp" \
  JUVAL_PYTHON=/home/juval/juval-recon/venv-auditfix-20261028/bin/python \
  PYTHONPATH=/home/juval/JUVAl/APP/src PYTHONDONTWRITEBYTECODE=1 \
  JUVAL_E2E_OUTPUT="$LOG/e2e-out" JUVAL_E2E_SERVER_LOG="$LOG/e2e.log" \
  DEBUG=pw:webserver npm run e2e >"$LOG/e2e.log" 2>&1
```

Without `JUVAL_E2E_SERVER_LOG`, B4 explicitly annotates the protocol-error
count as unverified. Capture must contain the real server output; a successful
download alone is not evidence of zero server errors. The full suite must
also finish successfully before accepting that log.

`recovery-c2` and `recovery-c3` cover Catalog columns and Methodology, with
light/dark screenshots under the E2E output directory. Column settings use
`juval.catalog.columns.v1`, with Title always visible; neither records
requests nor export URLs change.

Run the suite outside the Codex sandbox: inside it, Node's `spawnSync`
returns EPERM, so the config cannot start the fixture generator. Keep
`TMPDIR` short: Chromium aborts with "Socket path too long" when its
singleton socket path does not fit a Unix socket address (108 bytes).
Results of the 2026-11-03 run are in `docs/PROJECT_STATUS.md`.
