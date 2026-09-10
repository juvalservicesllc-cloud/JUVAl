# Third-wave dependency reconciliation — 2026-09-10

**GITHUB_ALERT_RECONCILIATION = BLOCKED_METADATA_REQUIRED.** The operator reports
six default-branch alerts (4 high / 2 moderate). No authenticated Dependabot API
is available: public request returns HTTP 401. SSH Git authentication verifies
repository access, not alert access. Do not map those six to the advisories below
or label them stale without their IDs/manifests. No global clean claim.

## Current checked artifacts

Fresh SSH fetch: b338a67 equals origin/master, 0/0. All four npm lockfile audits
report zero advisories; installed Python environment pip-audit reports none.
The five earlier frontend advisories remain absent in those registry checks.
No frontend patch is justified by this evidence; product source stays frozen.

## Separate supported-minimum finding

The declared lower bounds in pyproject.toml allow vulnerable Python releases.
Audit the original direct minima from b338a67 using pip-audit --no-deps
--disable-pip against exact versions; this is not a transitive resolution, actual
installed exposure assessment or identification of the six GitHub alerts.
PyPI returns duplicate aliases in some entries; rows below deduplicate package
and GHSA. Ranges are public GitHub advisory metadata; some bugs introduced after
the old floor still occur within its allowed >= range. Never infer that every
row affects the exact minimum itself from a coarse PyPI release association.

| Package | Advisory | Severity | Public affected range | Listed fix |
|---|---|---|---|---|
| python-multipart | [GHSA-59g5-xgcq-4qw3](https://github.com/advisories/GHSA-59g5-xgcq-4qw3) | high | < 0.0.18 | 0.0.18 |
| python-multipart | [GHSA-wp53-j4wj-2cfg](https://github.com/advisories/GHSA-wp53-j4wj-2cfg) | high | < 0.0.22 | 0.0.22 |
| python-multipart | [GHSA-mj87-hwqh-73pj](https://github.com/advisories/GHSA-mj87-hwqh-73pj) | medium | < 0.0.26 | 0.0.26 |
| python-multipart | [GHSA-pp6c-gr5w-3c5g](https://github.com/advisories/GHSA-pp6c-gr5w-3c5g) | high | < 0.0.27 | 0.0.27 |
| python-multipart | [GHSA-v9pg-7xvm-68hf](https://github.com/advisories/GHSA-v9pg-7xvm-68hf) | low | < 0.0.31 | 0.0.31 |
| python-multipart | [GHSA-5rvq-cxj2-64vf](https://github.com/advisories/GHSA-5rvq-cxj2-64vf) | high | < 0.0.30 | 0.0.30 |
| python-multipart | [GHSA-6jv3-5f52-599m](https://github.com/advisories/GHSA-6jv3-5f52-599m) | low | < 0.0.30 | 0.0.30 |
| pyjwt | [GHSA-752w-5fwx-jx9f](https://github.com/advisories/GHSA-752w-5fwx-jx9f) | high | <= 2.11.0 | 2.12.0 |
| pyjwt | PYSEC-2025-183 / CVE-2025-45768 | NOT_VERIFIED | consult advisory | NOT_LISTED |
| pyjwt | [GHSA-xgmm-8j9v-c9wx](https://github.com/advisories/GHSA-xgmm-8j9v-c9wx) | high | < 2.13.0 | 2.13.0 |
| pyjwt | [GHSA-993g-76c3-p5m4](https://github.com/advisories/GHSA-993g-76c3-p5m4) | medium | >= 2.0.0, <= 2.12.1 | 2.13.0 |
| pyjwt | [GHSA-fhv5-28vv-h8m8](https://github.com/advisories/GHSA-fhv5-28vv-h8m8) | low | >= 2.0.0, <= 2.12.1 | 2.13.0 |
| pyjwt | [GHSA-w7vc-732c-9m39](https://github.com/advisories/GHSA-w7vc-732c-9m39) | medium | >= 2.8.0, <= 2.12.1 | 2.13.0 |
| cryptography | [GHSA-6vqw-3v5j-54x4](https://github.com/advisories/GHSA-6vqw-3v5j-54x4) | high | >= 38.0.0, < 42.0.4 | 42.0.4 |
| cryptography | [GHSA-m959-cc7f-wv43](https://github.com/advisories/GHSA-m959-cc7f-wv43) | low | < 46.0.6 | 46.0.6 |
| cryptography | [GHSA-79v4-65xg-pq4g](https://github.com/advisories/GHSA-79v4-65xg-pq4g) | low | >= 42.0.0, < 44.0.1 | 44.0.1 |
| cryptography | [GHSA-9v9h-cgj8-h64p](https://github.com/advisories/GHSA-9v9h-cgj8-h64p) | medium | < 42.0.2 | 42.0.2 |
| cryptography | [GHSA-r6ph-v2qm-q3c2](https://github.com/advisories/GHSA-r6ph-v2qm-q3c2) | high | <= 46.0.4 | 46.0.5 |
| cryptography | [GHSA-jwv3-5hgf-82ww](https://github.com/advisories/GHSA-jwv3-5hgf-82ww) | high | >= 42.0.0, <= 48.0.0 | 49.0.0 |
| cryptography | [GHSA-m2h6-j472-rp4c](https://github.com/advisories/GHSA-m2h6-j472-rp4c) | medium | >= 45.0.0, <= 48.0.0 | 49.0.0 |
| cryptography | [GHSA-h4gh-qq45-vh27](https://github.com/advisories/GHSA-h4gh-qq45-vh27) | medium | >= 37.0.0, < 43.0.1 | 43.0.1 |
| cryptography | [GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf) | high | >= 0.5.0, < 48.0.1 | 48.0.1 |
| pytest | [GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g) | medium | < 9.0.3 | 9.0.3 |

## Dependency paths, reachability and minimal remediation

- python-multipart: direct runtime dependency, FastAPI/Starlette multipart uploads.
  Parsing DoS paths require attention; standalone parse_form helpers are not called
  by JUVAl. Do not classify the whole package as unreachable. Floor 0.0.9 → 0.0.31.
- PyJWT: direct runtime JWT validation; pinned RS256 prevents the reviewed mixed
  HMAC/asymmetric algorithm-confusion setup. Other claim validation behavior must
  retain the existing authentication tests. Floor 2.8 → 2.13.0.
- cryptography: direct runtime AES-GCM sessions and PyJWT RSA verification. No
  JUVAl PKCS7 decryption or X.509 path-building consumer found in src; those
  specific sinks are not reachable in reviewed source. Floor 42.0 → 50.0.0.
  Intermediate candidate 49.0.0 still reported GHSA-g6cj-pr64-35w5 (PKCS7 oracle,
  fixed 50.0.0), so it was rejected before commit. Installed environment already
  used 50.0.0; this is a support-floor correction, not a production upgrade.
- pytest: direct dev extra; tmpdir issue concerns multi-user Unix test hosts,
  not the production API. Floor 7 → 9.0.3.

Upgrade risks: multipart parser strictness, JWT claim validation, cryptography
major-version compatibility and pytest fixture/plugin behavior. Validate the
selected minima in a private venv with full backend and PostgreSQL lab; retain
main-environment gates. Auditing the four final exact minimum versions reports
zero advisories. This does not lock or prove every transitive resolution allowed
by all remaining ranges. Real deployment versions and the six GitHub alerts
remain NOT_VERIFIED. No arbitrary dependency upgrade or security dismissal.

Sources: pip-audit/PyPI vulnerability service and per-row public GitHub advisory
metadata. [Dependabot alert access requirements](https://docs.github.com/en/rest/dependabot/alerts)
explain why SSH Git success does not supply alert metadata. Required non-secret
operator export: all six alert IDs, GHSA/CVE, package, manifest, severity, affected
version/range, fixed version and current state. Never request an API token.


## Validation and reproducibility

Selected exact minima: python-multipart 0.0.31, PyJWT 2.13.0, cryptography 50.0.0,
pytest 9.0.3. Create a private venv, write those four exact constraints and install
`-e '.[dev,postgres]' -c <constraints>`; no runtime environment changed. Full
backend with disposable nginx: **839 PASS / 38 SKIP** both in that environment
and the existing environment. Private PostgreSQL: **48 PASS / 2 SKIP**, restart
probe PASS, cleanup confirmed. Main warning is existing Starlette/httpx deprecation;
minimum environment also emits the anyio BlockingPortal deprecation.

The newly created venv initially bundled pip 24.0. Its audit reported six unique
pip advisories (duplicated service entries), separate from project dependencies
and from GitHub's unknown six alerts. Upgrade this disposable installer to
pip 26.2.0 before reproducing the whole-environment audit; do not hide toolchain
findings or claim them to be GitHub alerts. No system pip/apt changes made.
