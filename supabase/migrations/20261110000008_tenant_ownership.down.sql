-- Rollback for 20261110000008_tenant_ownership.sql (run as postgres, after
-- the 20261110000009 rollback).
--
-- It DELETES the organizations, the memberships and every run's and batch's
-- recorded owner and creator; they cannot be rebuilt from other tables.
-- Export them first if they must be kept. Verified only against a disposable
-- PostgreSQL cluster.

ALTER TABLE batches
    DROP CONSTRAINT batches_owner_required,
    DROP COLUMN organization_id,
    DROP COLUMN created_by_issuer,
    DROP COLUMN created_by_subject;
DROP INDEX execution_runs_organization_started;
ALTER TABLE execution_runs
    DROP CONSTRAINT execution_runs_owner_required,
    DROP COLUMN organization_id,
    DROP COLUMN created_by_issuer,
    DROP COLUMN created_by_subject;

DROP TABLE organization_memberships;
DROP TABLE organizations;
