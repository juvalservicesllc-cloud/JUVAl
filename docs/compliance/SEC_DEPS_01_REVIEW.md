# SEC-DEPS-01 — dependency exposure review

Date: 2026-09-10. **REVIEWED / REMEDIATION_BLOCKED_FRONTEND_FREEZE**.
Source baseline: `16189b7`; all three frontend trees unchanged in accelerator.
Private GitHub alert status is NOT_VERIFIED because SSH fetch authentication
failed; this is a fresh npm registry audit of committed lockfiles, not a claim
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

## Concrete remediation after the freeze exception

Authorize dependency-only changes in `frontend/package-lock.json` (and package
manifest only if needed). Resolve fast-uri to 3.1.6 and Vitest/mocker to 4.1.11
with matching Vitest internal packages, preserving all unrelated dependency
versions. No broad `npm audit fix --force`, no unrelated major upgrades.
Verify lock diff, clean install, npm audit, lint, all frontend tests, build,
relevant service-worker E2E, full backend and compliance gates. Commit separately.

This session did not change any frontend files or claim a patched deployment.
The reviewed narrow change remains in the human action queue because the
operator explicitly froze all three frontend directories during security work.
