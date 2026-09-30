# Dependency-audit remediation — 2026-09-30

**IMPLEMENTED.** Gate B1 is **PASS — READY FOR REMOTE DEPLOYMENT REVIEW** after
minimal local dependency remediation. Authorization: explicit user instruction
to investigate the dependency blocker, implement an unequivocal local fix and
commit once after affected tests, one audit and one offline suite. No security
risk waiver, new architecture, remote deployment or Git push is authorized.

## Exact failing control and baseline

`tests/compliance/test_compliance_check.py::test_run_all_exits_clean_on_the_current_repository`
calls `tools/compliance_check.py::run_all`, which calls
`check_dependency_vulnerabilities`. That function invokes the installed
interpreter's `pip_audit` with JSON output. Vulnerabilities produce a FAIL finding
for `deps.audit`; the test asserts that run_all returned no FAIL findings.

Before remediation the full suite produced **1640 PASS / 129 SKIP / 1 FAIL**.
The failure already occurred while dependency manifests, checker and failing
test were byte-identical to baseline
`642f094a9afff3d04890e874cd9b1b2fd9d01781`. B1 SQL did not introduce it.
Baseline permits vulnerable PyJWT 2.13.0 and does not constrain urllib3 for audit
tooling. This establishes baseline applicability using the observed local
environment and current advisories; it does not reconstruct historical CI,
deployment versions or the advisory service's state when baseline was committed.

The pytest assertion truncated advisory detail. One explicit diagnostic audit
was permitted by the anti-loop exceptions for incomplete evidence and specific
failure reproduction. It reported **12 PyJWT + 3 urllib3 advisories**. No B1,
compliance, hash, protected-file or SQL validation was repeated to investigate.

## Dependency paths and version resolution

- PyJWT is direct runtime: `pyproject.toml` declares `pyjwt[crypto]` for JWT
  verification and JWKS key resolution. Floor before: `>=2.13.0`; after:
  `>=2.15.1`. cryptography remains at its existing floor and installed version.
- urllib3 is transitive audit tooling: `pip-audit 2.10.1 -> requests 2.34.2 ->
  urllib3`. pip-audit also uses CacheControl, which uses requests. Requests
  requires `urllib3>=1.26,<3`. No JUVAl runtime import of requests/urllib3 was
  found; urllib3 is not promoted to a direct runtime dependency.
- CI installs the editable project with its dev extra, then pip-audit separately.
  There is no Python lockfile. Before this change neither that install nor any
  project manifest constrained urllib3's security floor; installed `.venv`
  versions were 2.13.0 and 2.7.0. `constraints-audit.txt` now sets
  `urllib3>=2.8.0`, consumed by the existing CI pip-audit install.
- Installed editable project metadata contained stale older requirements as
  well as current source metadata. Manifest and actual imported package versions
  were assessed separately; no claim that editable metadata locked resolution.

## Exact advisories and corrected versions

IDs/aliases/minima below came from the diagnostic PyPI vulnerability report;
the linked advisories and release notes are primary maintainer sources.

| Package | CVE | Maintainer advisory | First corrected release |
| --- | --- | --- | --- |
| PyJWT | CVE-2026-102274 | [GHSA-w6j9-cwv2-h6wq](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-w6j9-cwv2-h6wq) | 2.14.0 |
| PyJWT | CVE-2026-101917 | [GHSA-2gx3-rcp4-g85q](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-2gx3-rcp4-g85q) | 2.14.0 |
| PyJWT | CVE-2026-102273 | [GHSA-w2cx-738m-mc7w](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-w2cx-738m-mc7w) | 2.14.0 |
| PyJWT | CVE-2026-102269 | [GHSA-hxm8-2xgr-2p9m](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-hxm8-2xgr-2p9m) | 2.14.0 |
| PyJWT | CVE-2026-102267 | [GHSA-9v7f-9g4p-ffgj](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-9v7f-9g4p-ffgj) | 2.14.0 |
| PyJWT | CVE-2026-102268 | [GHSA-ffc3-869f-jxw9](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-ffc3-869f-jxw9) | 2.14.0 |
| PyJWT | CVE-2026-102272 | [GHSA-r6x4-923q-g947](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-r6x4-923q-g947) | 2.14.0 |
| PyJWT | CVE-2026-102271 | [GHSA-p4g4-x82p-q773](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-p4g4-x82p-q773) | 2.14.0 |
| PyJWT | CVE-2026-102265 | [GHSA-8wjv-2p76-3863](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-8wjv-2p76-3863) | 2.14.0 |
| PyJWT | CVE-2026-102266 | [GHSA-9j54-fg26-wv3r](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-9j54-fg26-wv3r) | 2.14.0 |
| PyJWT | CVE-2026-102270 | [GHSA-jwrc-g2q2-pq5p](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-jwrc-g2q2-pq5p) | 2.14.0 |
| PyJWT | CVE-2026-101918 | [GHSA-42vr-xj54-vc7v](https://github.com/jpadilla/pyjwt/security/advisories/GHSA-42vr-xj54-vc7v) | 2.15.0 |
| urllib3 | CVE-2026-97687 | [GHSA-8988-9cw3-xx77](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77) | 2.8.0 |
| urllib3 | CVE-2026-97688 | [GHSA-gh4c-6fx4-qh6g](https://github.com/urllib3/urllib3/security/advisories/GHSA-gh4c-6fx4-qh6g) | 2.8.0 |
| urllib3 | CVE-2026-97689 | [GHSA-vxq7-64xx-v4gw](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw) | 2.8.0 |

The security minimum covering all listed PyJWT findings is **2.15.0**, not
2.14.0. The selected version is **2.15.1**, the narrow compatibility patch
restoring valid trailing Base64URL padding described in the
[PyJWT changelog](https://pyjwt.readthedocs.io/en/stable/changelog.html).
For urllib3 all three findings share minimum **2.8.0**; the
[maintainer release](https://github.com/urllib3/urllib3/releases/tag/2.8.0)
documents separate proxy TLS configuration and streaming safety fixes.

## Minimal change and compatibility

Only two packages were updated in the existing local `.venv`, with explicit
versions and `--no-deps`; requests, pip-audit, cryptography and psycopg did not
change. Installation used the public PyPI index with pip config/netrc disabled
and no inherited environment credentials. No system package or live deployment
was changed. The committed changes are the PyJWT floor, one transitive audit
constraint and consumption of that constraint in CI; no checker/test bypass.

PyJWT remains on supported 2.x for Python 3.11 (CI) and 3.12 (local). JUVAl's
RS256-only verification, required claims, issuer/audience checks and PyJWKClient
constructor parameters remain unchanged. Library fixes reject JWKS redirects,
limit unknown-kid refreshes, harden malformed parsing and retain valid padded
token compatibility. Mixed HS/asymmetric confusion preconditions do not match
the reviewed RS256-only code, but that is not used to dismiss package advisories.
No authentication/MFA design decision was changed.

urllib3 2.8.0 satisfies requests' existing `<3` range. Its changed HTTPS-proxy
TLS separation and streaming handling affect the audit tool's HTTP stack.
No custom proxy policy or runtime urllib3 consumer was found in JUVAl source.
The actual post-update network audit validates this tooling path. Live JWT
issuer behavior and deployment proxy configurations remain outside local proof.

## Single validation sequence after the dependency change

1. Directly affected auth/JWT/BFF tests: **112 PASS**, one existing
   Starlette/httpx deprecation warning, 5.94 s. Modules:
   `tests/unit/test_auth_hardening.py`, `tests/integration/test_api_auth.py`,
   `tests/integration/test_api_bff.py`,
   `tests/unit/test_bff_refresh_and_store_selection.py`.
2. Actual dependency/security check: **PASS + coverage WARN**, once.
   Imported/installed versions: PyJWT **2.15.1**, urllib3 **2.8.0**, requests
   **2.34.2**, pip-audit **2.10.1**. No known vulnerabilities reported in
   successfully audited packages. Local `juval` is not on PyPI and is skipped;
   this is partial whole-environment advisory coverage, not an absolute absence
   claim or GitHub alert closure. Its source is covered by repository checks.
3. Offline suite: **1627 PASS / 129 SKIP / 1 DESELECTED / 0 FAIL**, once,
   35.31 s, same deprecation warning. Command:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin PGPASSFILE=/dev/null PGSERVICEFILE=/dev/null JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin .venv/bin/python -m pytest -q -rs --ignore=tests/integration/test_postgres_batch_security.py --deselect=tests/compliance/test_compliance_check.py::test_run_all_exits_clean_on_the_current_repository
```

B1's **13 PASS / 0 SKIP** are reused: these two dependency changes cannot
reasonably change PostgreSQL ACL/RLS/rollback guarantees, and psycopg/server/
migration/test inputs stayed unchanged. The one explicitly deselected test is
the aggregate online audit caller above; its live dependency check was executed
once separately. No test was deleted, permanently skipped, or made to return a
fabricated PASS. This is **not** a claim that an unfiltered second full-suite
invocation ran. The original full-suite failure and new bounded results remain
visible. Skips retain their original reasons: nginx unconfigured, remote/test
DSNs absent, and encryption-inapplicable storage cases; none earns evidence.

## Final review and boundaries

APPROVED: local dependency fix and one local coherent commit under the explicit
anti-loop instruction. No architectural expansion or risk acceptance required.
Existing SQL/B1, original migration hashes, privilege/owner/TRUNCATE/rollback,
protected-file and ADR-040 evidence was reused. New diff/metadata and newly
written evidence are reviewed once for scope, correctness, secrets and simplicity.
Ponytail tool/skill remains unavailable; manual final review applies.

No changes to 000002/000003/000004, SQL 000006 after its recovered implementation,
MFA, runtime authentication code, batch status/financial parity, frozen
directories, production, secrets or migration history. No Supabase write,
Git push, remote credential use, host infrastructure change or system install.
ADR-025's SUCCESS/PARTIAL_SUCCESS discrepancy remains PENDING DECISION; ADR-040
has no literally changed criterion and earns no new credit. Remote deployment,
actual backend identity/grants and GitHub alert state require separate review.

Next action is remote deployment review, with no remote execution in this task.
