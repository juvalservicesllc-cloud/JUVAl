> Updated 2026-09-10: Windows safely synchronized to origin/master 32c3aef (0/0 divergence). See [source reconciliation](SOURCE_RECONCILIATION.md). Earlier checkout comparisons below describe the initial delivery only.

# JUVAl Project Intelligence

Isolated internal engineering, product and compliance portal. The commercial
`frontend/`, `frontend-next/` and `demo/` are unchanged.

## Run

Node 24 and npm, matching the repository runtime. From `project-portal/`:

```sh
npm ci
npm run sync
npm run dev
```

Open `http://127.0.0.1:4317`. `PORTAL_PORT` optionally changes the port.
The server binds only to loopback. No production credentials are needed.

## Architecture and approved decisions

APPROVED by the portal request: isolated application, read-only repository
integration, explicit weighted model, local generated snapshots, Vercel
preparation without deployment. React, TypeScript and Vite follow the existing
repository convention; Next.js was a preference, not a requirement. No chart,
router, state-management or component-runtime dependency is necessary here.
Native dialogs, controls, CSS charts and React handle the interface.

`scripts/sync.mjs` reads an immutable resolved Git commit → explicit source
allowlist → parsers and curated criteria → schema validation → atomic JSON
snapshot. `scripts/server.mjs` serves `/api/state` and same-origin POST
`/api/sync`. The browser renders the normalized model; it cannot execute shell
commands or choose paths. Code files are indexed by name and source link;
document text is sanitized. Source content is text, never executed HTML.

## Sources and synchronization

The default source is `origin/master`, not the local working tree. This matters:
the initial local checkout was `6f731f9`; the remote was `32c3aef`. Both are
reported separately. No merge, checkout change, commit or push is performed.

- `npm run sync`: regenerate from the currently cached Git ref, offline-capable.
- **Sync repository**: fetch `origin/master`, query bounded GitHub metadata via
  the authenticated GitHub CLI, then regenerate. No polling or webhook is claimed.
- `npm run sync:github`: refresh GitHub metadata only.
- `node scripts/refresh.mjs`: the same complete refresh outside the browser.

GitHub needs read-only repository contents, metadata, issues, pull requests,
Actions, and Dependabot alerts (the latter permission is optional). Use `gh`
authentication or server-side `GITHUB_TOKEN`. Never use `VITE_*` or
`NEXT_PUBLIC_*` for credentials. No token is written into generated JSON.
Unavailable sources carry warnings; an empty array alone is not evidence of
zero alerts. Metadata is bounded to 30 records per category and 20 workflow
runs/releases; local history to 80 commits. The app does not claim full history.

Failures preserve the prior snapshot and record the attempt. No snapshot is
presented as live production telemetry. The UI labels its sync time, commit,
source warnings and offline state. A static build reads `project-state.json`
and labels **OFFLINE SNAPSHOT**; remote sync then requires the local server.

## Progress and provenance

`data/project-config.json` is readable human metadata: phase names, criterion
weights, source rules, dependencies and conservative unresolved decisions.
It is not a business-approved project completion estimate. Scope is phases
0–10 of the repository plan, not just the current release.

Implementation credit: COMPLETE=1, PARTIAL/IN_PROGRESS=0.5,
BLOCKED/NOT_STARTED=0. DEFERRED is excluded. Percentage is the rounded weighted
mean. Every percentage opens its numerator, denominator and criteria.
Weights are deliberately visible and editable; no magic global percentage.
Test/behavioral verification is a second weighted calculation. Code presence
does not earn test evidence or prove correctness. Documentation-based test
evidence is explicitly labeled as a recorded claim, not re-execution.

Each criterion includes source, line anchor, excerpt, parser, commit, detection
time, confidence, status, verification, dependencies and notes. Missing sources
fail to NOT_VERIFIED and produce warnings. Exact section headers and explicit
status blocks are parsed; ambiguous free prose is not silently promoted.
Curated architecture edges are labeled logical, not observed live topology.
Security and Amazon approval never follow from code-file presence.

Generated files must not be edited by hand. Manual updates belong in config,
followed by sync. No UI or process writes back to GitHub. Local theme is persisted;
the repository is always read-only. No production identity flow is activated.

## Tests

```sh
npm test
npm run lint
npm run build
npm run test:e2e
```

E2E uses installed Google Chrome and the running loopback server. It verifies
the core journeys, navigation, evidence, filters, search, theme persistence,
responsive overflow and failure preservation, with screenshots at 1440, 1280,
768 and 390 pixels. Model tests cover weighted progress, normalization, ADRs,
provenance/schema, redaction, risk ordering and the generated snapshot.

The backend test execution used an isolated `origin/master` archive under
`.verification/`, not the older working tree. `scripts/record-tests.py` exports
only JUnit counters, timestamp and commit. Raw JUnit logs are never served.
Backend failures are displayed honestly, separately from portal tests. Coverage
and flakiness remain NOT_MEASURED unless actual supporting evidence exists.

## Deployment and security boundary

`npm run build` creates a static Vercel-compatible `dist/`. Set Vercel's project
root to `project-portal`; `vercel.json` supplies build settings and headers.
**Do not publish the internal snapshot without access protection.** Configure
Vercel Deployment Protection or an explicitly approved identity integration
before deployment. Authentication remains PENDING / INACTIVE, and deployment
was not performed. A static deployment cannot run local Git commands; a trusted
build environment must regenerate snapshots and publish them under protection.
No new insecure password system or public unauthenticated sync endpoint exists.

Secrets, untracked directories, `.env`, `.git`, test execution artifacts and
arbitrary filesystem paths are excluded from serving/ingestion. The scanner
only reads allowlisted tracked files at a fixed Git commit and applies defensive
redaction. The snapshot remains internal project information, even after
redaction. The local server validates POST origin and has a sync concurrency
guard. Runtime production configuration is never probed or changed.

## Operational limitations

- Phase/workstream coverage is curated; newly introduced product capabilities
  need a criterion mapping. ADRs, files, commits and remote metadata auto-discover.
- Status prose can conflict across historical documents; explicit latest status
  blocks win where supported, and conflicting source context stays visible.
- Risks are deterministic triage proxies, not probability estimates. Owners,
  effort and calendar deadlines are unknown when no source supplies them.
- Live infrastructure, Amazon external approval, production auth and session
  activation cannot be verified by a repository portal alone.
- Technical debt IDs assigned here are portal IDs; historical IDs absent from
  the repository are not fabricated as existing records.

See `DELIVERY_REPORT.md` for validation results and remaining external gates.

## Language / Idioma

Use **English / Español** in the top bar. The preference is saved on this browser; switching language preserves the current page and filters. Original repository evidence and external content keep their source language. Portal translations live in `src/es.json`; there is no external translation service.

## Hosted portal

Production: https://juval-project-intelligence.vercel.app (Vercel login required). This is a published snapshot; the hosted refresh button reloads the published data. New repository observations require a new build/deployment. Run `npm run build`, `node scripts/prepare-vercel.mjs`, then `vercel deploy --prebuilt --prod --yes --scope juval1`. Only the compiled static output is uploaded; maintain protection for all deployments.

## Automatic updates from GitHub

The production portal now follows `master` through Vercel's Git integration. Each push regenerates evidence at the exact deployed commit and runs the portal's validation before publishing. Failed builds leave the last successful version online. See [automatic synchronization](AUTO_SYNC.md). Earlier manual-deployment instructions describe the initial setup; normal updates are now Git pushes.
