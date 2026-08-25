# Demo artifact review — `demo/vendor/xlsx-0.20.3.tgz` and `demo/public/westmarine-*.csv`

Audit requested for two binary/data files committed under `demo/` (the
browser-only, backend-independent reference demo — see
`demo/README.md` and `docs/architecture/DEMO_PRODUCTION_PARITY_MATRIX.md`,
which uses this demo as the interaction-model baseline the current product
is measured against). Reviewed 2026-08-24. Neither file is touched by
`src/`, `processing/`, `domain/`, or any production code path — both are
scoped entirely to the standalone `demo/` app.

## 1. `demo/vendor/xlsx-0.20.3.tgz` (2.4 MB)

| | |
|---|---|
| Purpose | SheetJS's XLSX parser/writer, a runtime dependency of the demo app (`demo/package.json`: `"xlsx": "file:vendor/xlsx-0.20.3.tgz"`) |
| Source | Official SheetJS release tarball, version 0.20.3 (confirmed via the embedded `package/package.json`: `"name": "xlsx", "author": "sheetjs"`) |
| License/provenance | Apache License 2.0, full text present at `package/LICENSE` inside the tarball — permissive, redistribution-compatible, no obligation beyond preserving the license and copyright notice |
| Reproducibility | `npm install` inside `demo/` cannot resolve `xlsx` from a `file:` dependency without the tarball present locally — this is exactly why it is vendored, not fetched at install time |
| Necessity | SheetJS is **not published to the public npm registry** (its own documented distribution decision, made for security-hygiene reasons unrelated to this project). Without the vendored tarball, `demo/` is not buildable at all — this is load-bearing, not optional |
| Security risk | Low. It is a public, versioned, Apache-2.0 release of a maintained open-source library, used only inside the disconnected demo app. It is a binary blob in git history, which is the one real cost (repository size), traded off against build reproducibility |
| Repository appropriateness | **Appropriate** — already the documented, deliberate choice recorded in commit `549019c` ("SheetJS is not published to the public npm registry, so npm install cannot resolve it otherwise"). This review confirms that reasoning holds and finds no reason to reverse it |

**No change recommended.** Not deleted, not replaced.

## 2. `demo/public/westmarine-2026-08-16.csv` (24 KB, 59 rows)

| | |
|---|---|
| Purpose | The demo's one bundled representative dataset — `demo/README.md`: "The included representative file is `public/westmarine-2026-08-16.csv`," used to drive the demo's CSV-adapter code path (`demo/src/adapters/WestMarineCsvAdapter.ts`) and as the fixture the parity-matrix audit measures against |
| Source | A row-level export of `pro.westmarine.com` product-listing pages — the column names (`position-relative href`, `img-fluid src`, `swatch-circle src`, `quick-view-modal`, `btn href`, …) are literal CSS class/attribute names, which is the signature of a browser-scraper export (each column corresponds to one selector queried against the page DOM), not an official West Marine data feed or API export |
| License/provenance | **Not established in this repository.** No note records who captured this file, under what account/session, whether `pro.westmarine.com` (a professional/trade portal, distinct from the public consumer site) requires authentication to view, or what West Marine's Terms of Use say about redistributing scraped catalog content. This is a genuine gap, not a resolved question |
| Reproducibility | The file is static and committed, so the *demo* is reproducible from it; the *scrape itself* is not reproducible from anything in this repository (no scraper script, no capture procedure) |
| Necessity | The demo needs *some* representative CSV to be useful as a UI/UX reference; whether it specifically needs *this* file, versus a synthetic fixture with the same column shape, is a design choice, not a hard requirement |
| Security risk | Low from a technical standpoint — plain product-listing metadata (brand, name, price, image URLs), no credentials, no PII, no executable content |
| Repository appropriateness | **Needs a user decision, not an agent one.** CLAUDE.md §13 governs authorized external data *sources* for JUVAl's real enrichment pipeline and explicitly prohibits scraping/bypassing authentication for Amazon-research tools; this file is a different case (a competitor/supplier catalog, not Amazon, and not wired into any production code path), but the same underlying principle — don't redistribute scraped third-party content without knowing the terms it was captured under — applies. This is a licensing/legal judgment call this document flags rather than resolves |

**Recommendation, not applied automatically**: either (a) the user confirms
this snapshot was captured under a legitimate account/session with no
redistribution restriction relevant to keeping it in a private-by-default
repository, and this section is updated to record that confirmation, or
(b) the file is replaced with a synthetic fixture carrying the same column
shape (`WestMarineCsvAdapter.ts`'s expected headers) so the demo keeps
working without depending on scraped third-party content. **No file was
deleted or replaced in this pass** — per this mission's instruction, this
is a documented finding for the user, not a unilateral deletion.

## Summary

```
demo/vendor/xlsx-0.20.3.tgz        -> REVIEWED, APPROPRIATE, no action
demo/public/westmarine-*.csv       -> REVIEWED, LICENSING QUESTION OPEN
                                       (PENDING user decision — see above)
```
