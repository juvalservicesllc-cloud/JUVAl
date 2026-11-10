-- ADR-056 (1/2): organizations, memberships and resource ownership. Schema only.
--
-- Run as postgres, before 20261110000009_tenant_rls.sql. NOT applied to any
-- live database by this repository: applying it to Supabase is an explicit
-- owner action (docs/adr/ADR-056-multi-tenant-resource-authorization.md).
--
--   * organizations and organization_memberships (one membership per identity,
--     OD-6: the identity is the primary key).
--   * execution_runs and batches gain organization_id (a foreign key to
--     organizations) and the creator
--     (created_by_issuer/subject). Existing rows keep NULL: they are
--     quarantined (OD-3) and nothing here assigns them. New rows must carry an
--     owner: CHECK ... NOT VALID checks new rows without rewriting history.
--
-- Privileges and row-level security for these tables and the tenant policies
-- are in 20261110000009_tenant_rls.sql.

-- Organizations and memberships ------------------------------------------------

CREATE TABLE organizations (
    organization_id uuid PRIMARY KEY,
    name            text NOT NULL CHECK (btrim(name) <> ''),
    created_at      timestamptz NOT NULL,
    created_by      text NOT NULL CHECK (created_by <> '')
);
-- One name per organization, ignoring case: an operator cannot create
-- "Customer A" twice and then add a member to the wrong one.
CREATE UNIQUE INDEX organizations_name_unique ON organizations (lower(btrim(name)));

CREATE TABLE organization_memberships (
    issuer          text NOT NULL CHECK (issuer <> ''),
    subject         text NOT NULL CHECK (subject <> ''),
    organization_id uuid NOT NULL REFERENCES organizations (organization_id),
    created_at      timestamptz NOT NULL,
    created_by      text NOT NULL CHECK (created_by <> ''),
    PRIMARY KEY (issuer, subject)
);

-- Ownership columns ------------------------------------------------------------

-- organization_id references a real organization (NULL = unowned history).
ALTER TABLE execution_runs
    ADD COLUMN organization_id uuid REFERENCES organizations (organization_id),
    ADD COLUMN created_by_issuer text,
    ADD COLUMN created_by_subject text;
ALTER TABLE execution_runs
    ADD CONSTRAINT execution_runs_owner_required
    CHECK (organization_id IS NOT NULL AND created_by_issuer IS NOT NULL AND created_by_subject IS NOT NULL)
    NOT VALID;
CREATE INDEX execution_runs_organization_started
    ON execution_runs (organization_id, started_at DESC);

ALTER TABLE batches
    ADD COLUMN organization_id uuid REFERENCES organizations (organization_id),
    ADD COLUMN created_by_issuer text,
    ADD COLUMN created_by_subject text;
ALTER TABLE batches
    ADD CONSTRAINT batches_owner_required
    CHECK (organization_id IS NOT NULL AND created_by_issuer IS NOT NULL AND created_by_subject IS NOT NULL)
    NOT VALID;
