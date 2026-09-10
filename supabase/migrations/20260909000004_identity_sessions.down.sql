-- Rollback for 20260909000004_identity_sessions.sql
--
-- Dropping these tables logs every user out and cancels every in-flight
-- login. That is the correct behaviour for a rollback of the session layer --
-- there is no partial state worth preserving -- but it is a user-visible
-- effect, so it is stated here rather than discovered.
drop index if exists identity_oauth_transactions_expires_at_idx;
drop index if exists identity_sessions_expires_at_idx;
drop table if exists identity_oauth_transactions;
drop table if exists identity_sessions;
