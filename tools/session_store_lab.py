"""Run session/migration tests against a disposable PostgreSQL Unix socket.

No runtime DSN, TCP listener, sudo, or live migration. Requires PostgreSQL
server binaries (JUVAL_POSTGRES_BIN, pg_config, or PATH) and the postgres extra.
The cluster and every test schema are removed on success or failure.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def verify_restart(dsn, pg_ctl, data, log, env):
    """Only called for the private cluster created below; never accepts runtime DSNs."""
    from datetime import datetime, timedelta, timezone
    import secrets
    import psycopg
    from psycopg.conninfo import make_conninfo
    from juval.application.session_store import Session, OAuthTransaction
    from juval.infrastructure.crypto.token_cipher import TokenCipher, _Key
    from juval.infrastructure.persistence.postgres_session_store import (
        PostgresSessionStore, PostgresOAuthTransactionStore,
    )

    with psycopg.connect(dsn) as conn:
        conn.execute("create schema juval_restart_probe")
    scoped = make_conninfo(dsn, options="-c search_path=juval_restart_probe")
    migration = Path(__file__).resolve().parent.parent / "supabase/migrations/20260909000004_identity_sessions.sql"
    with psycopg.connect(scoped) as conn:
        conn.execute(migration.read_text())
    cipher = TokenCipher(_Key("disposable-restart", os.urandom(32)))
    sessions = PostgresSessionStore(scoped, cipher)
    transactions = PostgresOAuthTransactionStore(scoped, cipher)
    now = datetime.now(timezone.utc)
    live_id, revoked_id, transaction_id = (secrets.token_urlsafe(32) for _ in range(3))
    for session_id in (live_id, revoked_id):
        sessions.save(Session(session_id, "disposable", (), secrets.token_urlsafe(32),
                              now, now + timedelta(hours=1), "lab-access", "lab-refresh"))
    sessions.revoke(revoked_id, now)
    transactions.start(OAuthTransaction(transaction_id, "lab-state", "lab-verifier",
                                       "lab-nonce", "https://api.test.invalid/callback",
                                       now, now + timedelta(minutes=5)))
    assert transactions.consume(transaction_id, now) is not None
    subprocess.run([pg_ctl, "-D", str(data), "-l", str(log), "-m", "fast", "-w", "restart"],
                   env=env, check=True, capture_output=True)
    sessions = PostgresSessionStore(scoped, cipher)
    transactions = PostgresOAuthTransactionStore(scoped, cipher)
    after = datetime.now(timezone.utc)
    record = sessions.load(live_id, after)
    assert record is not None and record.refresh_token == "lab-refresh"
    assert sessions.load(revoked_id, after) is None
    assert transactions.consume(transaction_id, after) is None
    print("POSTGRES_RESTART_PASS: live session durable; revocation and consumed transaction remain effective")


def main() -> int:
    binary_dir = os.environ.get("JUVAL_POSTGRES_BIN")
    if not binary_dir and shutil.which("pg_config"):
        binary_dir = subprocess.check_output(["pg_config", "--bindir"], text=True).strip()
    initdb = str(Path(binary_dir) / "initdb") if binary_dir else shutil.which("initdb")
    pg_ctl = str(Path(binary_dir) / "pg_ctl") if binary_dir else shutil.which("pg_ctl")
    if not initdb or not pg_ctl or not Path(initdb).is_file() or not Path(pg_ctl).is_file():
        print("BLOCKED: PostgreSQL server binaries required; set JUVAL_POSTGRES_BIN")
        return 2
    if os.geteuid() == 0:
        print("BLOCKED: run this disposable lab as an unprivileged user")
        return 2

    root = Path(__file__).resolve().parent.parent
    scratch = tempfile.mkdtemp(prefix="juval-sessions-")
    try:
        data = Path(scratch) / "data"
        log = Path(scratch) / "postgres.log"
        # Scratch is mode 0700; trust is limited to its private Unix socket.
        env = os.environ.copy()
        for name in tuple(env):
            if name.startswith("JUVAL_") or name.startswith("PG"):
                env.pop(name)
        started = False
        try:
            subprocess.run([initdb, "-D", str(data), "-A", "trust", "--no-locale", "--encoding=UTF8"],
                           env=env, check=True, capture_output=True)
            with (data / "postgresql.conf").open("a") as config:
                config.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{scratch}'\n")
            subprocess.run([pg_ctl, "-D", str(data), "-l", str(log), "-w", "start"],
                           env=env, check=True, capture_output=True)
            started = True
            env["JUVAL_TEST_SESSION_DB_URL"] = f"host={scratch} dbname=postgres"
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/integration/test_session_store_contract.py", "-q"],
                cwd=root, env=env,
            )
            if result.returncode == 0:
                verify_restart(env["JUVAL_TEST_SESSION_DB_URL"], pg_ctl, data, log, env)
            return result.returncode
        except subprocess.CalledProcessError:
            print("FAIL: disposable PostgreSQL setup failed; no runtime database was used")
            return 1
        finally:
            if started or (data / "postmaster.pid").exists():
                subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "-w", "stop"],
                               env=env, check=True, capture_output=True)
    except Exception:
        print(f"LAB_CLEANUP_REQUIRES_REVIEW: {scratch}")
        raise
    finally:
        if not (data / "postmaster.pid").exists():
            shutil.rmtree(scratch)
            print("TEMPORARY_POSTGRES_STOPPED; SCRATCH_REMOVED")


if __name__ == "__main__":
    raise SystemExit(main())
