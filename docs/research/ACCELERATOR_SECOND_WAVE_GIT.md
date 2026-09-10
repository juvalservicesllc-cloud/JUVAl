# Second-wave Git reconciliation

Date: 2026-09-10. Authoritative Linux workspace. HTTPS fetch verified remote; SSH authentication unavailable.

Starting HEAD: `5e264a66d3cb60f1ef2e0281f84a7d38e74c11ae`. Remote: `6a6d07c04c17cbf7e3714c32d3d2e1576d5ddf6a`. Merge base: `32c3aef63352e1de1eac908dc0409681d3b29886`. Initial divergence: 2 remote-only / 12 local-only. Clean worktree.

## REMOTE_ONLY_COMMITS

```text
6a6d07c04c17cbf7e3714c32d3d2e1576d5ddf6a | Daniel Liendo | 2026-09-10T12:23:12-04:00 | docs(portal): record connected Git deployment configuration

 project-portal/AUTO_SYNC.md | 4 ++++
 1 file changed, 4 insertions(+)
bafaa1951f83e5fe1959f5d73c674edca11eb3e5 | Daniel Liendo | 2026-09-10T12:10:38-04:00 | feat(portal): version bilingual intelligence portal and Git deployment pipeline

 project-portal/.gitignore                 |   15 +
 project-portal/AUTO_SYNC.md               |   11 +
 project-portal/README.md                  |  152 ++
 project-portal/data/project-config.json   |  384 +++++
 project-portal/index.html                 |    1 +
 project-portal/package-lock.json          | 2536 +++++++++++++++++++++++++++++
 project-portal/package.json               |   33 +
 project-portal/playwright.config.ts       |    2 +
 project-portal/scripts/github.mjs         |   13 +
 project-portal/scripts/model.d.mts        |    5 +
 project-portal/scripts/model.mjs          |   57 +
 project-portal/scripts/prepare-build.mjs  |    6 +
 project-portal/scripts/prepare-vercel.mjs |   10 +
 project-portal/scripts/record-tests.py    |   23 +
 project-portal/scripts/refresh.mjs        |   17 +
 project-portal/scripts/server.mjs         |   14 +
 project-portal/scripts/sync-build.mjs     |   20 +
 project-portal/scripts/sync.mjs           |   70 +
 project-portal/src/assurance.tsx          |    9 +
 project-portal/src/es.json                |  488 ++++++
 project-portal/src/evidence-tool.ts       |   12 +
 project-portal/src/i18n.ts                |   23 +
 project-portal/src/main.tsx               |   84 +
 project-portal/src/model.ts               |    9 +
 project-portal/src/registers.tsx          |   15 +
 project-portal/src/style.css              |   16 +
 project-portal/src/vite-env.d.ts          |    1 +
 project-portal/tests/components.test.tsx  |   10 +
 project-portal/tests/e2e/portal.spec.ts   |   66 +
 project-portal/tests/i18n.test.tsx        |   12 +
 project-portal/tests/model.test.mjs       |   15 +
 project-portal/tsconfig.json              |    1 +
 project-portal/vercel.json                |   35 +
 project-portal/vite.config.ts             |    2 +
 project-portal/vitest.config.ts           |    2 +
 35 files changed, 4169 insertions(+)
```

## LOCAL_ONLY_COMMITS

```text
5e264a66d3cb60f1ef2e0281f84a7d38e74c11ae | Daniel Liendo | 2026-09-10T17:22:35+00:00 | docs: record integration rehearsal and accelerator stop boundary

 docs/IDENTITY_SECURITY_READINESS.md | 30 ++++++++++++++++++++++++++++++
 docs/PROJECT_STATUS.md              | 20 ++++++++++++++++++++
 2 files changed, 50 insertions(+)
3a17e125397b975efb582c87f614d1538ec15b10 | Daniel Liendo | 2026-09-10T17:19:50+00:00 | security: include JavaScript module files in secret scanning

 docs/PROJECT_STATUS.md                    | 10 ++++++++++
 docs/compliance/SECRETS.md                |  7 +++++++
 tests/compliance/test_compliance_check.py | 10 ++++++++++
 tools/compliance_check.py                 |  2 +-
 4 files changed, 28 insertions(+), 1 deletion(-)
63568c40dd35e07e8b489d5a8bf27a3112eb6d77 | Daniel Liendo | 2026-09-10T17:13:55+00:00 | docs: reconcile identity readiness and prepare operator checkpoint

 AGENTS.md                                          | 207 +++++---------
 CLAUDE.md                                          | 296 +++++----------------
 deploy/fusionauth/README.md                        |  38 +--
 docs/IDENTITY_SECURITY_READINESS.md                | 196 ++++++++++++++
 docs/PHASE_GATES.md                                |  68 ++---
 docs/PROJECT_PLAN.md                               |  92 +++----
 docs/PROJECT_STATUS.md                             | 164 +++++-------
 docs/SESSION_CHECKPOINT.md                         |   5 +-
 .../adr/ADR-038-browser-site-topology-readiness.md |  41 +++
 docs/compliance/ACCESS_CONTROL.md                  |  21 +-
 docs/compliance/HOST_CONTROLS_JUVAL_SERVER.md      |  12 +
 docs/compliance/SECRETS.md                         |  10 +-
 docs/compliance/SP_API_REGISTRATION_REMEDIATION.md |  51 ++++
 src/juval/interfaces/api/main.py                   |   4 +-
 tools/systemd/README.md                            |   2 +-
 15 files changed, 580 insertions(+), 627 deletions(-)
5430b0f1688277996d0fdd57fe271f81bdaaf093 | Daniel Liendo | 2026-09-10T17:13:55+00:00 | security: assess five frontend dependency advisories

 docs/compliance/SEC_DEPS_01_REVIEW.md | 57 +++++++++++++++++++++++++++++++++++
 1 file changed, 57 insertions(+)
6c6539bb4e8a8c749fb6d7a1fc4e7841bb422289 | Daniel Liendo | 2026-09-10T17:08:16+00:00 | identity: prepare guarded exact-client PKCE surface probe

 .../FUSIONAUTH_PUBLIC_SURFACE_DISCOVERY.md         | 13 ++++
 .../test_fusionauth_surface_discovery.py           | 48 +++++++++++++
 tools/fusionauth_surface_discovery.py              | 79 ++++++++++++++++++++++
 3 files changed, 140 insertions(+)
c0cf4f89c07538a24a60f1175e7e97d91dd3bd2b | Daniel Liendo | 2026-09-10T17:04:55+00:00 | fix: report revoked sessions as unauthenticated after refresh

 .../adr/ADR-034-bff-oidc-browser-authentication.md |  9 +++++++
 src/juval/interfaces/api/bff.py                    |  9 ++++++-
 tests/integration/test_api_bff.py                  | 30 ++++++++++++++++++++++
 3 files changed, 47 insertions(+), 1 deletion(-)
fc75aa5a9d6af971a5f342161c56a1d1e4b1ad41 | Daniel Liendo | 2026-09-10T17:02:19+00:00 | security: harden nginx-generated identity responses

 deploy/fusionauth/nginx-fusionauth-public.conf     | 12 ++---
 docs/PROJECT_STATUS.md                             | 13 ++++++
 .../ADR-037-nginx-generated-response-hardening.md  | 41 +++++++++++++++++
 .../FUSIONAUTH_PUBLIC_SURFACE_DISCOVERY.md         |  9 ++++
 docs/research/NGINX_PUBLIC_SURFACE_LAB.md          | 14 ++++++
 tests/compliance/test_nginx_public_surface.py      | 51 +++++++++-------------
 6 files changed, 103 insertions(+), 37 deletions(-)
beec1cf335baeb6beaa81ef23629ecd38ebafb60 | Daniel Liendo | 2026-09-10T17:00:10+00:00 | fix: verify session database readiness before BFF startup

 docs/PROJECT_STATUS.md                             | 15 +++++++
 docs/adr/ADR-036-durable-session-store.md          | 15 +++++++
 docs/compliance/SECRETS.md                         | 10 +++++
 .../persistence/postgres_session_store.py          | 41 ++++++++++++++++++
 src/juval/interfaces/api/bff.py                    |  2 +
 tests/integration/test_session_store_contract.py   | 49 ++++++++++++++++++++++
 tests/unit/test_bff_refresh_and_store_selection.py | 25 +++++++++++
 7 files changed, 157 insertions(+)
bdd57d212802e88e1224fb8c0d6922f285d96e92 | Daniel Liendo | 2026-09-10T16:57:36+00:00 | tests: isolate session contracts from runtime databases

 docs/PROJECT_STATUS.md                           | 29 +++++++++
 docs/adr/ADR-036-durable-session-store.md        | 12 ++++
 tests/README.md                                  | 15 +++++
 tests/integration/test_session_store_contract.py | 83 +++++++++++++++++-------
 tools/session_store_lab.py                       | 72 ++++++++++++++++++++
 5 files changed, 189 insertions(+), 22 deletions(-)
16189b79e2ab630bc434ff2c96f29cf90b611cfb | Daniel Liendo | 2026-09-10T16:48:04+00:00 | identity: record FusionAuth public-surface discovery

 CLAUDE.md                                          |  19 +-
 .../FUSIONAUTH_PUBLIC_SURFACE_DISCOVERY.md         | 619 ++++++++++++++++++
 .../test_fusionauth_surface_discovery.py           | 524 +++++++++++++++
 tools/fusionauth_surface_discovery.py              | 722 +++++++++++++++++++++
 4 files changed, 1879 insertions(+), 5 deletions(-)
3a599ba57f36731e2e04c3382f29cf8e54840d7d | Daniel Liendo | 2026-09-10T15:37:09+00:00 | tests: make token-cipher tamper test deterministic

 tests/unit/test_token_cipher.py | 72 +++++++++++++++++++++++++++++++++++++++--
 1 file changed, 70 insertions(+), 2 deletions(-)
acf5cf16fab192643bc6161b98df4c4826f051bb | Daniel Liendo | 2026-09-10T15:09:15+00:00 | identity: add reproducible nginx public-surface lab

 CLAUDE.md                                          |   2 +-
 deploy/fusionauth/nginx-fusionauth-public.conf     |  60 +-
 docs/PROJECT_STATUS.md                             |  80 +++
 .../adr/ADR-034-bff-oidc-browser-authentication.md |  30 +-
 docs/compliance/SP_API_REGISTRATION_REMEDIATION.md |  13 +-
 docs/research/NGINX_PUBLIC_SURFACE_LAB.md          | 223 +++++++
 tests/compliance/test_nginx_public_surface.py      | 325 ++++++++++
 tools/nginx_surface_lab.py                         | 703 +++++++++++++++++++++
 8 files changed, 1427 insertions(+), 9 deletions(-)
```

## PORTAL_COMMITS

```text
29e90a6ae71266d15b61a976edfa972a25f96da5 | Daniel Liendo | 2026-09-10T17:19:50+00:00 | docs(portal): record accelerator validation scope

 project-portal/README.md | 7 +++++++
 1 file changed, 7 insertions(+)
e91d7d84a036d35ddb51c751519428421e1bd59f | Daniel Liendo | 2026-09-10T17:18:25+00:00 | portal: map accelerator evidence and require test provenance

 project-portal/README.md                  | 32 +++++++++++++
 project-portal/data/project-config.json   | 80 +++++++++++++++++++++++++------
 project-portal/scripts/record-tests.py    | 63 ++++++++++++++++--------
 project-portal/tests/model.test.mjs       | 17 ++++++-
 project-portal/tests/test_record_tests.py | 48 +++++++++++++++++++
 5 files changed, 206 insertions(+), 34 deletions(-)
```

## Review and integration

Both remote commits are authored by the established project author and add only
project-portal. Reviewed scripts, package lifecycle commands, deployment config,
model and evidence extraction are JUVAl-specific. Tests/docs/portal UI/build are
affected; backend runtime and frontend/frontend-next/demo are not. No destructive
history or unrelated payload found. Repository scanner passed after integration.
Local history comprises identity tooling, deterministic tests, session fixes,
nginx hardening, security review and evidence documentation; protected product
frontend unchanged. This is source/content review, not cryptographic author attestation.

Portal branch: `accelerator/portal-readiness`; base `6a6d07c`; no additional
worktree. Neither of its two commits was initially reachable from local master
or origin/master. Classification INTEGRATE_NOW, now ALREADY_CONTAINED in local
master. Branch retained. No portal work abandoned.

Remote merge: `5c52451`, message `merge: reconcile accelerator and remote JUVAl work`.
Portal merge: `880334c`, message `merge: preserve portal readiness and evidence provenance`.
Both conflict-free, normal two-parent merges; no rebase, reset, or force push.
Post-integration full backend with disposable nginx: 825 passed, 36 skipped;
PostgreSQL lab: 44 passed, 2 memory-only skips, cleanup confirmed. Portal:
10 model + 4 component/i18n + 3 Python exporter tests; lint/build pass.
Compliance: 9 PASS, 1 WARN (security owner), 0 FAIL; secret scan clean 464 files.
Normal SSH push attempted and rejected for missing authentication; no commits
pushed at this checkpoint. Remote-only is now zero; publication remains pending.
