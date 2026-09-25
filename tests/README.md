# tests

- `unit/` — Processing Core en aislamiento, sin I/O.
- `integration/` — importación/exportación Excel y pipeline completo.
- `fixtures/` — archivos Excel de prueba (casos válidos, columnas
  faltantes, tipos inválidos, mezcla de estados de verificación).

Ver `docs/architecture/ARCHITECTURE.md` §9. Ningún test debe ocultar un
error para "pasar" — debe afirmar que el error se reportó correctamente.

## Disposable session database (2026-09-10)

Run `.venv/bin/python tools/session_store_lab.py` to create an isolated UTF-8
PostgreSQL cluster on a private Unix socket, run session contracts plus
migration/rollback checks, and stop/remove it. Requires PostgreSQL server
binaries and the existing `postgres` extra; no sudo or TCP listener.

Direct contract runs accept **only `JUVAL_TEST_SESSION_DB_URL`**, pointing to a
disposable database. Runtime `JUVAL_SESSION_DB_URL`/`JUVAL_SUPABASE_DB_URL` are
not used by these session tests. Each test creates a unique schema, sets its
search path without `public`, and removes only that schema in `finally`.
Previously the fixture dropped runtime-named tables using a runtime DSN;
that unsafe behavior has been removed. Other Supabase integration tests have
separate environment contracts; use the lab to avoid inheriting their DSNs.

## Disposable financial persistence cluster (2026-09-25)

`tests/integration/test_postgres_financial_persistence.py` (ADR-047 step 6)
runs only with `JUVAL_POSTGRES_BIN` (e.g. `/usr/lib/postgresql/16/bin`). It
creates its own cluster with `initdb` in a temporary directory, listening only
on a Unix socket there, applies the real `supabase/migrations/` files to a
per-test schema, and removes everything afterwards. It reads no DSN from the
environment, so it cannot reach a runtime or production database.
