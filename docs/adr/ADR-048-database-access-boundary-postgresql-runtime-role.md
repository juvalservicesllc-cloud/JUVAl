# ADR-048 — Database Access Boundary and PostgreSQL Runtime Role

- Status: Accepted.
- Date: 2026-10-05.
- Authority: explicit human approval in Gate B2.
- Implementation status: local candidate; not deployed.

## Context

JUVAl persists runs, snapshots, financial evidence, batches, and backend
identity state in PostgreSQL. The execution store and session store use direct
PostgreSQL connections. The observed remote connection used `postgres` as
`current_user` and `session_user`.

The remote preflight verified that the existing execution and financial tables
had RLS enabled, RLS not forced, and no policies. It also verified broad ACLs
for `anon`, `authenticated`, and `service_role`. The repository migrations
examined do not grant those table privileges or alter default privileges. The
historical origin of the remote ACLs and defaults remains undetermined.

The repository contains earlier descriptions of backend access through
`service_role` and later direct PostgreSQL owner access. The implemented
adapters use PostgreSQL directly. This ADR resolves the database runtime
boundary; it does not assert that the proposed role exists remotely or that the
Supabase project has provisioned it.

## Problem

RLS and ACL are separate controls. RLS with no policies denies row access to a
non-owner role, but does not replace revoking table privileges; in particular,
RLS does not control `TRUNCATE`. Running the application as the table owner
also bypasses RLS by default. Broad ACL and default ACL entries can therefore
undermine the intended backend-only boundary and can affect future objects.

## Decision

Use a dedicated PostgreSQL runtime role named `juval_backend`. It is a login
role, non-owner, non-superuser, `NOINHERIT`, and has `BYPASSRLS=false`. It has
no administrative role memberships. It receives only table operations
required by the current adapters, through both explicit ACL and role-specific
RLS policies.

Initially, `postgres`/the existing owner remains the migration and
administration identity. Its credential is kept outside the application
runtime. `service_role` remains conceptually separate from the direct SQL
runtime and receives no direct table privileges without a separately approved
functional need.

The architecture target in this decision is distinct from verified remote
state: `juval_backend` has not been verified as present or usable on Supabase;
the currently observed remote runtime identity remains `postgres`.

## Object and Platform Governance Boundary

Every role, object, and default-privilege scope must be classified as
`JUVAL_CONTROLLED`, `SUPABASE_MANAGED`, `MIXED`, or `UNDETERMINED` before
JUVAl changes its privileges, ownership, or lifecycle. JUVAl administers
privileges, ownership, and lifecycle only for `JUVAL_CONTROLLED` objects.
Roles, objects, and default privileges managed by Supabase remain
`SUPABASE_MANAGED`; JUVAl does not change them unless a supported integration
explicitly requires it and that scope is separately established. Effective
privileges on JUVAl-controlled objects must still be verified, including
privileges inherited through role membership and grants to `PUBLIC`.

`supabase_admin` remains platform-managed. JUVAl must not modify its object
lifecycle or default privileges merely to make a migration pass.

## Role Matrix

The matrix covers internal tables in `public`. “No” applies to direct table
privileges. `CONDITIONAL` must not be interpreted as an implicit grant.

| Principal | Internal table access | Ownership | `BYPASSRLS` | Notes |
|---|---|---:|---:|---|
| `postgres` / owner | Administrative access | Yes, for migrations/administration | Yes if the platform role has it | Never the normal application credential. |
| `juval_backend` | Per-table CRUD matrix below | No | No | Direct PostgreSQL runtime; subject to RLS. |
| `service_role` | Deny direct SQL access | No | No JUVAl dependency | Any future API use needs a separate decision. |
| `anon` | Deny | No | Deny | No ACL and no policies. |
| `authenticated` | Deny | No | Deny | No ACL and no policies. |
| `authenticator` | Deny direct access | No | Deny | No direct table ACL or policies. |
| `PUBLIC` | Deny | No | Not applicable | No table grants or policies. |

The exact platform attributes of Supabase-managed roles are not asserted by
this ADR. The provisioning and deployment checks must inspect them where
relevant and fail closed on unexpected privilege inheritance.

## Per-table CRUD Matrix

The matrix is derived from SQL operations in the current PostgreSQL adapters.
`SELECT` on `identity_oauth_transactions` is required for the columns returned
by `DELETE ... RETURNING`. No privilege is inferred from future cleanup,
administration, or convenience needs.

| Table | SELECT | INSERT | UPDATE | DELETE | Code evidence |
|---|---|---|---|---|---|
| `execution_runs` | REQUIRED | REQUIRED | NOT_REQUIRED | NOT_REQUIRED | `src/juval/infrastructure/persistence/supabase_execution_run_store.py`: `save_execution_run` (INSERT), `load_execution_run`/`list_execution_runs` (SELECT). |
| `execution_run_records` | REQUIRED | REQUIRED | NOT_REQUIRED | NOT_REQUIRED | Same file: `save_execution_run` (INSERT); `load_records`, `load_record`, `list_records` (SELECT). |
| `execution_run_financial_records` | REQUIRED | REQUIRED | NOT_REQUIRED | NOT_REQUIRED | Same file: `save_execution_run` (INSERT); `_payload_row`/`load_financial_rows`/`load_financial_record` (SELECT). |
| `execution_run_capture_diagnostics` | REQUIRED | REQUIRED | NOT_REQUIRED | NOT_REQUIRED | Same file: `save_execution_run` (INSERT); `_payload_row`/`load_financial_rows`/`load_capture_diagnostics` (SELECT). |
| `batches` | REQUIRED | REQUIRED | NOT_REQUIRED | NOT_REQUIRED | `src/juval/infrastructure/persistence/supabase_execution_run_store.py`: `save_batch` (INSERT), `load_batch`/`load_batch_for_run` (SELECT). |
| `batch_files` | REQUIRED | REQUIRED | NOT_REQUIRED | NOT_REQUIRED | Same file: `save_batch` (INSERT), `load_batch`/`load_batch_for_run` (SELECT). |
| `identity_sessions` | REQUIRED | REQUIRED | REQUIRED | REQUIRED | `src/juval/infrastructure/persistence/postgres_session_store.py`: `save` (INSERT/ON CONFLICT UPDATE), `load` (SELECT/UPDATE), `revoke`/`replace_tokens` (UPDATE), `purge_expired` (DELETE). |
| `identity_oauth_transactions` | REQUIRED | REQUIRED | NOT_REQUIRED | REQUIRED | `src/juval/infrastructure/persistence/postgres_session_store.py`: `PostgresOAuthTransactionStore.start` (INSERT), `consume` (DELETE ... RETURNING, requiring SELECT on returned columns), `purge_expired` (DELETE). |

These permissions apply only to the listed tables. The current schema has no
runtime sequence requirement. An operation not demonstrated above remains
ungranted until code evidence and approval are added.

## Runtime Role

`juval_backend` is provisioned operationally, not created by a schema
migration. It must be `LOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`,
`NOREPLICATION`, `NOBYPASSRLS`, and `NOINHERIT`, with no role memberships and
no ownership of internal objects or schemas. Its password is provisioned and
rotated through the approved secret manager; it never appears in a migration,
repository file, test fixture, or log.

Only the per-table permissions in the CRUD matrix are granted. It receives no
`TRUNCATE`, `REFERENCES`, `TRIGGER`, `MAINTAIN`, schema creation, or ownership
privileges. The adapter fails closed when its runtime credential is missing.

## Migration/Admin Role

Initially, migrations run as `postgres`/the established owner. That credential
is separate from runtime and is not available to application processes.
Migrations preserve existing ownership. Provisioning or credential rotation is
operational work, not schema DDL. A dedicated non-superuser migrator can be
considered later after Supabase capabilities and ownership requirements are
verified.

## `service_role`

`service_role` is not the PostgreSQL runtime role. JUVAl grants it no direct
SQL access to internal tables. A future service using the Supabase API must
document its required objects and operations and receive separate approval;
that does not automatically change this direct-connection model.

## `anon`, `authenticated`, `authenticator`, and `PUBLIC`

`anon`, `authenticated`, `authenticator`, and `PUBLIC` receive no table ACLs
and no RLS policies on internal tables. Schema `USAGE` is not table access and
is outside this table-level matrix. No public API exploitability claim is
made by this ADR.

## RLS Strategy

Internal tables retain `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL
SECURITY` remains false. Policies are explicit, one per required command, and
target only `juval_backend`. `SELECT` uses a row predicate; `INSERT` uses a
check predicate; `UPDATE` uses both; `DELETE` uses a row predicate. No `ALL`
policy is used. There are no policies for API roles, `authenticator`,
`service_role`, or `PUBLIC`.

The adapter cannot operate against zero policies as a non-owner; the runtime
policies are therefore installed with its exact grants. RLS does not replace
the ACL matrix. Because `juval_backend` is not an owner and cannot bypass RLS,
the policies apply to its operations.

## Default Privilege Strategy

For JUVAl-controlled objects created by `postgres` in `public`, the intended
default ACLs deny `PUBLIC`,
`anon`, `authenticated`, `authenticator`, `service_role`, and
`juval_backend` automatic access to tables, sequences, and functions. Runtime
grants are explicit per table; there are no automatic runtime table grants.
The current tables do not use sequences, so no sequence grants are approved.
Function execution is not granted to the runtime by default.

PostgreSQL global defaults and schema-specific defaults are inspected
separately. A schema-scoped revoke is not treated as canceling a global grant.
The candidate migration fails closed if unapproved global table or sequence
defaults for the migration owner are present. The built-in global default
`EXECUTE` for functions is a pending scope risk: `ALTER DEFAULT PRIVILEGES FOR
ROLE postgres REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` can affect future
functions created by `postgres` beyond JUVAl-controlled objects. Whether
`postgres` also creates Supabase-managed objects is `UNDETERMINED` until
reconciled with evidence. Do not declare this scope safe or change
`supabase_admin` lifecycle/default privileges to make the migration pass.
Defaults for other object creators, including platform roles, are not changed
by JUVAl.

`MAINTAIN_LOCAL_PG16 = NOT_APPLICABLE`

`MAINTAIN_REMOTE_PG17 = REQUIRED_PREFLIGHT_CHECK`

The disposable PostgreSQL 16 environment does not establish PostgreSQL 17
coverage. The remote preflight must check the effective `MAINTAIN` privilege
before any runtime switch.

RLS and policies are not default privileges: each new table migration must
enable RLS and define its approved runtime policies explicitly.

## Migration Rules

- Historical migrations are immutable.
- Never write manually to `supabase_migrations.schema_migrations`.
- Provision the runtime role before applying migrations that reference it;
  migrations verify its required attributes and fail if memberships or
  conflicting objects violate the boundary.
- Existing table ACL, table RLS/policies, and future default ACL are managed
  explicitly and transactionally.
- Preserve table ownership and verify it before commit.
- Deploy new batch tables and their security correction in one transaction.
- Do not infer an unapplied migration solely from ledger absence; reconcile
  ledger and catalog before a remote deployment.

## Testing Requirements

Use a private Unix-socket PostgreSQL cluster created with `initdb`; do not
read runtime or production DSNs. Tests inspect role attributes, memberships,
ownership, direct ACL, effective privileges, RLS, policies, and defaults.
They verify positive runtime operations and negative operations for
`anon`, `authenticated`, `authenticator`, `service_role`, `PUBLIC`, and
non-required runtime commands. They create future tables, sequences, and
functions as the migration owner and verify inheritance. Tests cover
transaction rollback on migration failure and fingerprint objects outside the
scope.

## Operational Security

The runtime secret is named `JUVAL_RUNTIME_DB_URL`; migration tooling may use
`JUVAL_MIGRATION_DB_URL`. The API process reads only the runtime credential.
It must never fall back to `JUVAL_SUPABASE_DB_URL`, a session/admin DSN, or any
migration credential. Missing runtime configuration fails closed. Secrets are
provided only through the service secret manager and never appear in output.

## Rollout

Provision and verify `juval_backend` out of band, without a password in SQL.
Run the complete disposable-cluster gate, then reconcile the remote ledger and
catalog. Apply versioned ACL/policy/default changes in a reviewed transaction,
verify all conditions before commit, and only then change the application
runtime secret to the dedicated role. The existing remote identity remains
`postgres` until a separately approved deployment completes.

## Rollback

Prefer an application configuration rollback and forward correction of
privileges. Do not perform a destructive post-commit schema rollback. Returning
runtime to `postgres` would restore an over-privileged boundary and is an
emergency exception requiring explicit approval and a time limit.

## Consequences

Runtime compromise has a smaller database blast radius and is subject to
RLS. The project must provision and rotate two credentials, maintain explicit
policies, and validate role attributes and memberships. Any new table or
adapter operation requires an explicit privilege review. The remote state is
still blocked pending reconciliation and deployment review.

## Rejected Alternatives

- `postgres`/owner as normal runtime: rejected because it combines application
  and administrative authority and bypasses RLS.
- `service_role` as the direct SQL runtime: rejected because it conflates the
  Supabase API role with the PostgreSQL runtime and the current adapter is
  direct PostgreSQL.
- Non-owner runtime with `BYPASSRLS`: rejected because it defeats the
  approved RLS boundary.
- Broad default grants or one `ALL` policy: rejected because they grant more
  than the demonstrated CRUD operations.

## Hosted Supabase Runtime Preconditions

`CUSTOM_ROLE_CONNECTION_TEST = REQUIRED_BEFORE_RUNTIME_SWITCH`

Creating `juval_backend` with the approved PostgreSQL attributes does not by
itself prove that the role can authenticate through the production connection
path. JUVAl currently depends on Supavisor Session/IPv4 because the direct
PostgreSQL endpoint has a historical IPv6 connectivity limitation. A real
connection test for `juval_backend` through the intended Supavisor path is
required before switching the application runtime credential.

`DATA_API_NOT_REQUIRED`

The local application audit found no active use of REST/PostgREST, the
GraphQL Data API, `supabase-js` table access, or direct frontend access to the
Supabase database API. The active persistence adapter uses direct PostgreSQL.

`SECURITY_HARDENING_CANDIDATE = disable Supabase Data API`

Disabling the Supabase Data API is a hardening candidate, not an action
authorized by this ADR or Gate B2. Do not disable it until remote
reconciliation confirms that no supported integration depends on it and a
separate change is explicitly approved.

## Remaining Operational Questions

- Can the target Supabase project provision `juval_backend` with the required
  attributes and no inherited memberships?
- Does the production migration path run as `postgres`, as required by the
  candidate default-privilege scope?
- What is the verified remote state of migration 000004 and its identity
  tables?
- Are there production-specific global/default ACLs for other object owners?
- Which credential rotation and rollout window will be approved?
