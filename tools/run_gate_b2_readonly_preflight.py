"""Safely load one explicitly selected Gate B2 credential candidate.

This wrapper is offline unless the child preflight is explicitly invoked.
It never sources a file, accepts exactly JUVAL_SUPABASE_DB_URL, and passes the
value only in the child process environment (never argv or output).
"""
from __future__ import annotations

import argparse
import errno
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHILD = ROOT / "tools" / "gate_b2_readonly_preflight.py"
KEY = "JUVAL_SUPABASE_DB_URL"
# Credential/key names documented in the repository. Keep the rest of the
# inherited environment for Python, TLS, and platform runtime requirements.
CHILD_CREDENTIAL_ENV_KEYS = (
    "JUVAL_RUNTIME_DB_URL",
    "JUVAL_SESSION_DB_URL",
    "JUVAL_MIGRATION_DB_URL",
    "JUVAL_TEST_SESSION_DB_URL",
    "JUVAL_SESSION_ENCRYPTION_KEYS",
    "JUVAL_OIDC_CLIENT_SECRET",
    "JUVAL_IDP_API_KEY",
)


def read_authorized_candidate(path_text: str) -> str:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("credential candidate must not be a symlink") from None
        raise ValueError("credential candidate could not be opened") from None

    descriptor_open = True
    value: str | None = None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("credential candidate is not a regular file")
        if info.st_uid != os.geteuid():
            raise ValueError("credential candidate owner does not match current user")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise ValueError("credential candidate permissions must be exactly 0600")

        with os.fdopen(fd, "r", encoding="utf-8", closefd=True) as stream:
            descriptor_open = False
            for line in stream:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    if stripped == KEY or stripped.startswith(f"{KEY} "):
                        raise ValueError("credential candidate target definition is malformed")
                    continue
                name, raw = stripped.split("=", 1)
                if name.strip() != KEY:
                    continue
                if value is not None:
                    raise ValueError("credential candidate has duplicate target variable")
                raw = raw.strip()
                if raw[:1] in ("'", '"') or raw[-1:] in ("'", '"'):
                    if len(raw) < 2 or raw[0] != raw[-1]:
                        raise ValueError("credential candidate target definition is malformed")
                    raw = raw[1:-1]
                if not raw or any(char in raw for char in ("\x00", "\n", "\r")):
                    raise ValueError("credential candidate target variable is empty or malformed")
                value = raw
    except (OSError, UnicodeError):
        raise ValueError("credential candidate cannot be read") from None
    finally:
        if descriptor_open:
            os.close(fd)
    if value is None:
        raise ValueError("credential candidate lacks the required target variable")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-candidate", required=True, help="explicitly human-authorized local candidate file")
    args = parser.parse_args()
    try:
        credential = read_authorized_candidate(args.credential_candidate)
    except ValueError as exc:
        print(f"credential_candidate=REJECTED reason={exc}", file=sys.stderr)
        return 2

    child_env = os.environ.copy()
    for name in CHILD_CREDENTIAL_ENV_KEYS:
        child_env.pop(name, None)
    child_env[KEY] = credential
    try:
        result = subprocess.run(
            [sys.executable, str(CHILD)],
            env=child_env,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode
    except OSError:
        print("preflight_child=NOT_STARTED", file=sys.stderr)
        return 3
    finally:
        credential = ""
        child_env.pop(KEY, None)


if __name__ == "__main__":
    raise SystemExit(main())
