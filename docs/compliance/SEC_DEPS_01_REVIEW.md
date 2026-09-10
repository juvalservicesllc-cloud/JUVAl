# SEC-DEPS-01 — dependency exposure review

Date: 2026-09-10. **REMEDIATED_LOCKFILE / VERIFIED_TEST**.
Review baseline: `16189b7`; second-wave authorization B permits only security remediation.
Private GitHub alert status is NOT_VERIFIED; this is a fresh npm registry audit of committed lockfiles, not a claim
that GitHub alerts were closed.

## Reproduction and results

In each of `frontend`, `frontend-next`, `demo`, run:
`npm audit --package-lock-only --ignore-scripts --json` (no mutation).
`npm explain fast-uri` and `npm explain @vitest/mocker` in `frontend` confirm
installed dependency paths; source/config search confirms no application imports
of fast-uri, mockerPlugin or interceptorPlugin.

| Scope | Actual result |
|---|---|
| Backend installed Python environment | pip-audit: no known vulnerabilities (via compliance check) |
| frontend | Five unique advisories: four high, one moderate; npm aggregates these into three affected package entries (one high, two moderate) |
| frontend-next | Zero advisories |
| demo | Zero advisories |

Counts are not exposure estimates. Python's unbounded lower version floors
permit older installations; this audit certifies only the installed environment.

## Advisory-by-advisory disposition

All four fast-uri advisories affect locked **3.1.5**. Minimal patched target:
**3.1.6**, within existing transitive semver. Path:
`vite-plugin-pwa@1.3.0 → workbox-build@7.4.1 → ajv@8.20.0 → fast-uri`;
`@apideck/better-ajv-errors` also peers on that AJV. **Dev/build tooling**, no
backend or direct application runtime import. The checked configuration uses
local Workbox build schemas; no attacker-controlled host-policy/fetch path was
found. Reachability: **NOT_REACHABLE_IN_REVIEWED_PRODUCT_PATH**, a source-based
assessment, not dynamic exploitation proof or an assertion about future configs.

| Advisory (maintainer source) | Affected 3.x range | Failure | JUVAl exposure / upgrade risk / required tests |
|---|---|---|---|
| [GHSA-5jgf-p345-68v8](https://github.com/fastify/fast-uri/security/advisories/GHSA-5jgf-p345-68v8) | ≥3.1.3, <3.1.6 | Scheme-relative IDN host confusion | Build-schema URI handling; no product host-policy sink found. Patch may reject formerly accepted malformed URIs; PWA build and service-worker smoke required |
| [GHSA-f65p-4m7j-42xc](https://github.com/fastify/fast-uri/security/advisories/GHSA-f65p-4m7j-42xc) | ≥3.0.0, <3.1.6 | Malformed IPv6 normalization / SSRF | Same dependency path and tooling-only exposure; same build regression gate |
| [GHSA-fph4-wmhf-6fwf](https://github.com/fastify/fast-uri/security/advisories/GHSA-fph4-wmhf-6fwf) | ≥3.1.2, <3.1.6 | Repeated hostname percent decoding / SSRF | Same dependency path and tooling-only exposure; same build regression gate |
| [GHSA-jqff-g426-hqxp](https://github.com/fastify/fast-uri/security/advisories/GHSA-jqff-g426-hqxp) | ≥3.0.0, <3.1.6 | Encoded-scheme host confusion | Same dependency path and tooling-only exposure; same build regression gate |
| [GHSA-82fw-gwwq-j7x9](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9) | ≥2.1.0, <4.1.11 | Redirect mock arbitrary file read | Direct dev dependency `vitest@4.1.10 → @vitest/mocker@4.1.10`. Patched target **4.1.11** for both. Checked Vitest config uses jsdom and `vitest run`, no browser mode or exported mocker plugins; vulnerable unauthenticated WebSocket registration not enabled. NOT_REACHABLE_IN_REVIEWED_CONFIG. Patch risk: mock resolution changes; run complete frontend unit suite |

## Authorized remediation — second wave

Only frontend/package-lock.json changed: fast-uri 3.1.5 → 3.1.6 and Vitest
4.1.10 → 4.1.11 with its eight matching package entries (Vitest plus seven
@vitest packages). Existing manifest ranges unchanged; no product source,
UX, styles or other lockfiles modified. Targeted npm resolution initially chose
fast-uri 3.1.7; the final lock entry uses the minimum patched 3.1.6 with registry
resolved URL/integrity, verified by clean npm ci. No force audit fix.

Fresh npm audit confirms zero advisories in the final frontend lock. Clean
install, 155 frontend tests, lint and production/PWA build pass. Chromium smoke
against the built output verifies nonempty shell, service-worker activation and
control, then offline reload; external API requests blocked for this isolated
shell test. It is not a backend sourcing E2E or production deployment claim.
Full backend after concurrent session correction: 834 passed, 38 skipped;
PostgreSQL scratch: 48 passed, 2 skips. Existing bundle-size warning remains,
and npm reports a glob deprecation while registry audit is clean; neither is
hidden or used to justify unrelated upgrades. GitHub alert closure and deployed
artifact versions remain NOT_VERIFIED until publication/provider evidence.
