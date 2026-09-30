-- ADR-025 security amendment, Gate B1. Backend-owned grouping, not a public API.
-- Requires 000002 then 000003. Deploy all three in ONE transaction before COMMIT.
-- Explicit revocation also covers TRUNCATE, which RLS does not protect.
-- No policies, ownership changes, default-privilege changes or data changes.
-- No automatic down: restoring inherited grants would reopen the B0 exposure.
ALTER TABLE public.batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batch_files ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.batches, public.batch_files
    FROM PUBLIC, anon, authenticated;
