# Dependency-audit remediation — 2026-10-28

**IMPLEMENTED in the isolated candidate; not applied to the operating `.venv`.**
Follows the 2026-09-30 precedent
([DEPENDENCY_AUDIT_REMEDIATION_20260930.md](DEPENDENCY_AUDIT_REMEDIATION_20260930.md)):
transitive audit tooling is constrained in `constraints-audit.txt`, never promoted
to a runtime dependency. No test, checker or advisory was bypassed.

## Failing control

`tests/compliance/test_compliance_check.py::test_run_all_exits_clean_on_the_current_repository`
→ `tools/compliance_check.py::check_dependency_vulnerabilities` (`deps.audit`)
reported, with the operator `.venv` (2026-10-28):

| Package | Installed | Advisories | Path | Fixed in |
| --- | --- | --- | --- | --- |
| certifi | 2026.7.22 | PYSEC-2026-4320 (GHSA-6q48-6c7w-9gw2) | pip-audit → requests; httpx (`dev` extra) | 2026.10.19 |
| filelock | 3.32.4 | CVE-2026-112907, CVE-2026-112913, CVE-2026-112940 | pip-audit → `CacheControl[filecache]` (`filelock>=3.8.0`) | 4.2.1 |
| msgpack | 1.2.1 | CVE-2026-114613 (GHSA-j586-36cw-2gc2) | pip-audit → CacheControl (`msgpack>=0.5.2,<2.0.0`) | 1.2.3 |

None is a runtime dependency (`pyproject.toml` `dependencies`); JUVAl source does
not import them. These are new advisories against an unchanged environment, not a
regression of the candidate.

## Change

`constraints-audit.txt` gains three security floors (`certifi>=2026.10.19`,
`filelock>=4.2.1`, `msgpack>=1.2.3`), consumed by the existing CI step
`python -m pip install -c constraints-audit.txt pip-audit`. Floors, not pins:
CI resolves the newest compatible release, as it already does for urllib3.

## Reproducibility evidence

- CI step on a venv pre-seeded with the vulnerable versions (as left by
  `pip install -e ".[dev]"`): raises them to certifi 2026.10.23, filelock 4.2.4,
  msgpack 1.2.4; `pip check` clean. Control with the previous constraints file:
  all three stay vulnerable. Run locally on Python 3.12; CI uses 3.11 (all three
  packages support both).
- Exact local remediation, outside APP: the operator `.venv` `pip freeze` with
  only these three lines changed, installed `--no-deps` into a new venv;
  `pip check` clean; `pip-audit`: no known vulnerabilities.

Operator `.venv` (PENDING, not applied):

```sh
.venv/bin/python -m pip install --no-deps certifi==2026.10.19 filelock==4.2.1 msgpack==1.2.3
.venv/bin/python -m pip check && .venv/bin/python -m pip_audit --progress-spinner off
```

## Residual risk

`pip-audit` coverage is partial (local `juval` is not on PyPI; GitHub alerts not
checked). filelock 4.x is a major version; its only consumer here is
CacheControl's file cache inside pip-audit, exercised by the audit run itself.
New advisories can reappear at any time without code changes.
