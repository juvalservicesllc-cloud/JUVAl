# Gate B1 — local batch-table security evidence, 2026-09-30

Gate B1: **PASS — READY FOR REMOTE DEPLOYMENT REVIEW**. SQL validation remains
**13 PASS / 0 SKIP**, reused without repetition under the user-authorized
anti-loop protocol. The initial dependency-audit blocker below was resolved by
the separately authorized minimal local dependency correction; no risk waiver.
[Dependency findings, compatibility, final audit and offline gate](DEPENDENCY_AUDIT_REMEDIATION_20260930.md).
The local commit containing these records closes local preparation only.
This record provides no remote deployment authority.

## Recovery

Initial branch: `master`. Initial HEAD:
`642f094a9afff3d04890e874cd9b1b2fd9d01781`. No later commits existed.
The only workspace changes were two untracked files:
`supabase/migrations/20260928000006_batch_table_security.sql` and
`tests/integration/test_postgres_batch_security.py`. ADR-025 was unchanged;
the interrupted documentation patch had not been applied. Those files were
reviewed and retained; the recovered tests initially passed 9/9.

Gate A PASS and Gate B0 closed BLOCKED are confirmed session context, not
new remote observations. Neither gate nor the architecture investigation was
restarted. No remote connection or credential was used for this phase.

## Original migration integrity

The following SHA-256 values matched initial workspace, initial HEAD and
final workspace byte-for-byte:

| Migration | SHA-256 before and after |
| --- | --- |
| 20260819000002_batches.sql | `f61d267590bd54ac9d1adf6bb8e1c150ef4aa7e83240bbb056647846a21cf040` |
| 20260819000003_batch_file_counts.sql | `cde3dc047125f497a7684d05100971bd47332615ce46d9efaf66b428bdf51704` |

## Migration 000006

The recovered migration was preserved. Its complete executable SQL is:

```sql
ALTER TABLE public.batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batch_files ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.batches, public.batch_files
    FROM PUBLIC, anon, authenticated;
```

Only those two tables are targeted. No policies, FORCE RLS, ownership changes,
default-privilege changes, data mutations or migration-history DML are included.
Revoking all table privileges covers SELECT, INSERT, UPDATE, DELETE, TRUNCATE,
REFERENCES and TRIGGER. There is no automatic down migration that would
restore the unsafe grants.

## Measured PostgreSQL behavior

PostgreSQL **16.15**, using `/usr/lib/postgresql/16/bin`, was initialized in
private temporary directories by the existing cluster fixture. Listening was
Unix-socket-only (`listen_addresses=''`), verified by the tests. Each test used
a disposable database, synthetic rows and LOGIN NOSUPERUSER NOBYPASSRLS
NOINHERIT roles without inherited membership. No SQL security guarantee used
a mock. Schema-scoped permissive default grants reproduced the unsafe starting
state only inside those databases; the tests proved those grants were effective
before applying 000006.

Results apply to both `public.batches` and `public.batch_files`:

| Role | SELECT | INSERT | UPDATE | DELETE | TRUNCATE |
| --- | --- | --- | --- | --- | --- |
| anon | privilege denial | privilege denial | privilege denial | privilege denial | privilege denial |
| authenticated | privilege denial | privilege denial | privilege denial | privilege denial | privilege denial |
| PUBLIC via public_probe | privilege denial | privilege denial | privilege denial | privilege denial | privilege denial |
| batch_backend, owner | succeeds | succeeds | succeeds | succeeds | succeeds for both tables together |

Effective REFERENCES/TRIGGER privileges were also absent for the public roles.
PUBLIC had no ACL entry. Final RLS was enabled, not forced, and policy count was
zero on each table. Owner remained `batch_backend`; default ACLs and untargeted
execution-table columns, constraints, ownership, ACLs and RLS flags were unchanged.
The real SupabaseExecutionRunStore adapter round-tripped runs and batches against
the local owner connection; its class name does not imply a Supabase connection.

With test-only DML grants, anon/authenticated SELECT returned no rows;
UPDATE/DELETE affected zero rows; INSERT failed with a row-level-security error.
TRUNCATE still failed by privileges. Separate test-only TRUNCATE grants to anon,
authenticated and PUBLIC allowed TRUNCATE despite enabled RLS and zero policies.
Those probes were rolled back, rows survived, and reapplying 000006 removed
the temporary grants. This distinguishes privilege denial from RLS default-deny
and demonstrates why explicit TRUNCATE revocation is necessary.

The local sequence was 000002 -> 000003 -> 000006 -> verification -> COMMIT in
one transaction. A second connection could see neither new table nor new ledger
entries before COMMIT. An injected SQL failure after verification rolled back
both tables and the three synthetic ledger entries; base state survived.
Successful COMMIT retained all three entries with their actual file contents.
The ledger existed only in disposable databases; no real history was repaired,
rewritten or claimed to match it.

## Initial tests and review, before dependency remediation

Run final tests without runtime credentials or DSNs:

```sh
env -i PATH=/usr/local/bin:/usr/bin:/bin PGPASSFILE=/dev/null PGSERVICEFILE=/dev/null JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin .venv/bin/python -m pytest -q -rs tests/integration/test_postgres_batch_security.py
env -i PATH=/usr/local/bin:/usr/bin:/bin PGPASSFILE=/dev/null PGSERVICEFILE=/dev/null JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin .venv/bin/python -m pytest -q -rs
```

- Recovered tests: **9 passed**, 3.07 s.
- Expanded tests initially exposed a test-only direct grant to `public_probe`
  outside the revocation scope. The probe was corrected to grant PUBLIC.
- Final B1: **13 passed**, 4.43 s, zero skips.
- Full suite: **1640 passed, 129 skipped, 1 failed**, 43.75 s; one existing
  Starlette/httpx deprecation warning. Failure:
  `tests/compliance/test_compliance_check.py::test_run_all_exits_clean_on_the_current_repository`.
  Its automatic dependency audit reported vulnerable installed `pyjwt 2.13.0`
  and `urllib3 2.7.0`. Dependency files, compliance checker and that test are
  byte-identical to initial HEAD. No installation, test deletion or bypass.
- Full-suite skips: nginx (binary unconfigured), Supabase (remote DSN absent),
  session PostgreSQL (test-only DSN absent), and storage cases where encryption
  is not applicable. No skip earns security evidence.
- Separate offline compliance/secret checks: **8 PASS, 1 WARN, 0 FAIL**;
  no secret-pattern findings in **575 files**. Warning: historical incident-plan
  ROLE PLACEHOLDER marker. This run excluded dependency network auditing; the
  full suite above did execute its own dependency audit and failed.
- Final secret scan including this evidence record: **PASS**, no secret-pattern
  findings in **576 files**.
- `git diff --check`: PASS. Ponytail skill/tool unavailable; manual simplicity,
  correctness, architecture, security, traceability and reproducibility review.

## Decisions, limits and exclusions

APPROVED: independent 000006 and local security tests, by explicit user
instruction; documented in ADR-025. PENDING: resolution of its aggregate-status
discrepancy. The ADR says a PARTIAL_SUCCESS child alone yields aggregate SUCCESS;
the existing code yields PARTIAL_SUCCESS. Neither text was silently reconciled
by changing runtime semantics. Native financial parity for batches, per-file
failure isolation, extra ten-file SQL constraints, retry and Decision Score
work remain outside scope.

Remote role memberships, ownership, grants and current drift were not measured
in B1. Future deployment review must confirm the backend/owner path and atomic
verification strategy before authorizing any remote write. The local owner test
does not attest the live backend identity. Existing dependency vulnerabilities
remain a separate unresolved concern.

The initial self-review confirmed unchanged 000002/000003/000004, runtime code, MFA,
financial batch behavior, frontend/frontend-next/demo/project-portal and
ADR-040. No Supabase write, db push, history repair, Git push, credentials,
secret exposure, installation or host infrastructure change occurred in the
initial B1 phase. The later authorized dependency correction is recorded in
the linked remediation report. ADR-040
earns **no new criterion credit**: no literal criterion or qualifying status
changed, and local SQL evidence is not production verification.
