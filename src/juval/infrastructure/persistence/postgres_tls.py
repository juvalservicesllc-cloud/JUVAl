"""TLS for remote PostgreSQL connections (SEC-01E).

libpq's default `sslmode` is `prefer`: it tries TLS but silently accepts a
plaintext connection, so anyone on the network path can downgrade it and read
the role's password and every row. Owner decision (SEC-01E): a connection
string that reaches another host must name `sslmode=verify-full` -- encrypted
*and* the server's certificate checked against a trusted CA and hostname.
`require`/`verify-ca` encrypt but would accept an impostor server. The CA is
`sslrootcert=<path>` (Supabase's CA file) or libpq's default root store; if
it is missing, libpq refuses to connect, which is the fail-closed outcome.
Unix sockets and loopback need none.

The DSN must say it itself: `PGSSLMODE` in the environment is not accepted,
so the setting travels with the secret and can be reviewed where it lives.
"""

from __future__ import annotations

import os

_TLS_MODE = "verify-full"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def require_tls_for_remote(dsn: str, name: str) -> None:
    """Raise unless `dsn` uses TLS or stays on this machine. Never echoes the DSN."""
    try:
        from psycopg.conninfo import conninfo_to_dict
    except ImportError:
        raise RuntimeError(f"{name}: PostgreSQL support is not installed (pip install -e '.[postgres]')") from None
    try:
        params = conninfo_to_dict(dsn)
    except Exception:
        # The parser's message quotes the connection string.
        raise RuntimeError(f"{name} is not a valid PostgreSQL connection string") from None
    targets = ",".join(
        str(value) for value in (params.get("host") or os.environ.get("PGHOST"), params.get("hostaddr")) if value
    )
    remote = [t for t in targets.split(",") if t and not t.startswith("/") and t not in _LOCAL_HOSTS]
    if remote and params.get("sslmode") != _TLS_MODE:
        raise RuntimeError(
            f"{name} reaches a remote host without TLS verify-full: add "
            "sslmode=verify-full and sslrootcert=<trusted CA file>"
        )
