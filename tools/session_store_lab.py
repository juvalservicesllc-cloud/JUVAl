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
