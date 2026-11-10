"""Local integration environment for the BFF and frontend-next (SEC-01F).

Everything is disposable, loopback-only and synthetic -- no real identity,
credential, Supabase project or FusionAuth instance:

* a private PostgreSQL cluster (Unix socket, no TCP listener), with the
  ADR-048 roles and migrations 00-09 applied as `postgres`, exactly the
  order the activation runbook prescribes;
* synthetic organizations and memberships (OD-1/OD-5) for three users;
* the synthetic OIDC provider (`tools/oidc_lab.py`);
* the real backend (uvicorn) in `oidc` mode with the PostgreSQL session
  store, built from a clean environment so no operator variable leaks in.

    .venv/bin/python tools/integration_lab.py           # serve; prints frontend-next settings
    .venv/bin/python tools/integration_lab.py --check   # end-to-end security smoke, then exit

Users: alice (organization A, operator), bob (organization B, operator),
carol (no organization, viewer). Ports: API 18781, IdP 18782, frontend 5173.
Requires PostgreSQL server binaries (JUVAL_POSTGRES_BIN, pg_config or PATH).
Docs: docs/architecture/LOCAL_INTEGRATION_ENVIRONMENT.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oidc_lab import LabUser, SyntheticIdP  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
ORDER = (
    "20260817000000_execution_runs", "20260817000001_execution_run_records", "20260819000002_batches",
    "20260819000003_batch_file_counts", "20260909000004_identity_sessions",
    "20260925000005_execution_run_financial_records", "20260928000006_batch_table_security",
    "20261005000007_database_access_boundary", "20261110000008_tenant_ownership", "20261110000009_tenant_rls",
)
ORG_A = "aaaaaaaa-0000-4000-8000-00000000000a"
ORG_B = "bbbbbbbb-0000-4000-8000-00000000000b"
CLIENT_ID = "juval-integration-lab"
FIXTURE = ROOT / "tests" / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"
THRESHOLDS = json.dumps({"target_profit": "5", "target_roi": "0.3", "minimum_estimated_monthly_sales": 0,
                         "maximum_risk_severity": "LOW"})
FEES = json.dumps({"referral_fee": "3", "referral_fee_rate": "0.15", "fulfillment_fee": "2"})


def _postgres_binaries() -> tuple[str, str]:
    binary_dir = os.environ.get("JUVAL_POSTGRES_BIN")
    if not binary_dir and shutil.which("pg_config"):
        binary_dir = subprocess.check_output(["pg_config", "--bindir"], text=True).strip()
    initdb = str(Path(binary_dir) / "initdb") if binary_dir else shutil.which("initdb")
    pg_ctl = str(Path(binary_dir) / "pg_ctl") if binary_dir else shutil.which("pg_ctl")
    if not initdb or not pg_ctl or not Path(initdb).is_file() or not Path(pg_ctl).is_file():
        raise SystemExit("BLOCKED: PostgreSQL server binaries required; set JUVAL_POSTGRES_BIN")
    return initdb, pg_ctl


#: A hosting platform injects these; their presence means "not a workstation"
#: (the same signal ADR-055 uses for the loopback lab).
_HOSTING_ENV_PREFIXES = ("RAILWAY_", "VERCEL")


def _refuse_unsafe_environment() -> None:
    if any(name.startswith(_HOSTING_ENV_PREFIXES) for name in os.environ):
        raise SystemExit("BLOCKED: the integration lab runs on a workstation only (hosting environment detected)")


def _require_free_port(port: int) -> None:
    """A busy port would let /healthz answer from someone else's server."""
    import socket

    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"BLOCKED: 127.0.0.1:{port} is already in use") from None


def _without_libpq_environment() -> dict:
    """Remove PG* for the lab's own connections and return them for restoring.

    libpq honours them even with an explicit DSN: PGHOSTADDR, for one, would
    send a connection meant for the private socket to a TCP address -- i.e.
    the migrations to someone else's database.
    """
    return {name: os.environ.pop(name) for name in list(os.environ) if name.startswith("PG")}


def _clean_env() -> dict:
    """No inherited JUVAL_*, PG* or credentials: only what a process needs to run."""
    return {name: os.environ[name] for name in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if name in os.environ}


class Lab:
    def __init__(self, api_port: int, idp_port: int, web_port: int, token_ttl: int, keep: bool):
        self.api_port, self.web_port, self.keep = api_port, web_port, keep
        self.api = f"http://localhost:{api_port}"
        self.web = f"http://localhost:{web_port}"
        self.idp = SyntheticIdP(
            client_id=CLIENT_ID, client_secret=base64.urlsafe_b64encode(os.urandom(24)).decode(),
            redirect_uri=f"{self.api}/api/v1/auth/callback", post_logout_redirect_uri=f"{self.web}/",
            users={"alice": LabUser("alice", "Alice (A, operator)", ["operator"]),
                   "bob": LabUser("bob", "Bob (B, operator)", ["operator"]),
                   "carol": LabUser("carol", "Carol (no organization)", ["viewer"])},
            token_ttl=token_ttl, port=idp_port)
        # Created only once the IdP port is held, so a busy port leaves nothing behind.
        self.scratch = Path(tempfile.mkdtemp(prefix="juval-integration-"))
        self.socket = str(self.scratch)
        self.admin_dsn = f"host={self.socket} dbname=juval user=postgres"
        self.runtime_dsn = f"host={self.socket} dbname=juval user=juval_backend"
        self.backend = None
        self.pg_ctl = None

    # -- setup --------------------------------------------------------------------

    def start(self) -> None:
        initdb, self.pg_ctl = _postgres_binaries()
        env = _clean_env()
        data = self.scratch / "data"
        subprocess.run([initdb, "-D", str(data), "-A", "trust", "-U", "postgres", "--no-locale",
                        "--encoding=UTF8"], env=env, check=True, capture_output=True)
        with (data / "postgresql.conf").open("a") as config:
            config.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{self.socket}'\n")
        subprocess.run([self.pg_ctl, "-D", str(data), "-l", str(self.scratch / "postgres.log"), "-w", "start"],
                       env=env, check=True, capture_output=True)
        self._prepare_database()
        self.idp.start()
        self._start_backend()

    def _prepare_database(self) -> None:
        import psycopg
        from psycopg.conninfo import conninfo_to_dict

        # Every schema change goes to this lab's own socket and nowhere else.
        for dsn in (self.admin_dsn, self.runtime_dsn):
            if conninfo_to_dict(dsn).get("host") != self.socket or any(k.startswith("PG") for k in os.environ):
                raise SystemExit("BLOCKED: refusing to migrate anything but the lab's private cluster")
        from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

        with psycopg.connect(f"host={self.socket} dbname=postgres user=postgres", autocommit=True) as conn:
            for role in ("juval_backend", "anon", "authenticated", "authenticator", "service_role"):
                conn.execute(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                             "NOINHERIT NOREPLICATION NOBYPASSRLS")
            conn.execute("CREATE DATABASE juval OWNER postgres")
        with psycopg.connect(self.admin_dsn) as conn:                  # one migration per transaction
            for migration in ORDER:
                conn.execute((MIGRATIONS / f"{migration}.sql").read_text(encoding="utf-8"))
                conn.commit()
        admin, now = SupabaseExecutionRunStore(self.admin_dsn), datetime.now(timezone.utc)
        admin.create_organization(ORG_A, "Synthetic Organization A", "integration-lab", now)
        admin.create_organization(ORG_B, "Synthetic Organization B", "integration-lab", now)
        admin.add_membership(ORG_A, self.idp.issuer, "alice", "integration-lab", now)
        admin.add_membership(ORG_B, self.idp.issuer, "bob", "integration-lab", now)

    def backend_env(self) -> dict:
        return {
            **_clean_env(),
            "JUVAL_AUTH_MODE": "oidc",
            "JUVAL_OIDC_ISSUER": self.idp.issuer,
            "JUVAL_OIDC_AUDIENCE": CLIENT_ID,
            "JUVAL_OIDC_CLIENT_ID": CLIENT_ID,
            "JUVAL_OIDC_CLIENT_SECRET": self.idp.client_secret,
            "JUVAL_BFF_REDIRECT_URI": self.idp.redirect_uri,
            "JUVAL_BFF_POST_LOGIN_REDIRECT": f"{self.web}/",
            "JUVAL_BFF_POST_LOGOUT_REDIRECT": f"{self.web}/",
            "JUVAL_BFF_INSECURE_COOKIES": "yes-local-http-only",   # plain-HTTP lab only
            "JUVAL_CORS_ORIGINS": self.web,
            "JUVAL_SESSION_STORE": "postgres",
            "JUVAL_RUNTIME_DB_URL": self.runtime_dsn,
            "JUVAL_SESSION_ENCRYPTION_KEYS": "lab:" + base64.b64encode(os.urandom(32)).decode(),
            "JUVAL_EXECUTION_STORE": "supabase",
            "JUVAL_RUN_STORAGE_DIR": str(self.scratch / "runs"),
        }

    def _start_backend(self) -> None:
        _require_free_port(self.api_port)
        self.backend_log = (self.scratch / "backend.log").open("w")
        self.backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "juval.interfaces.api.main:app", "--host", "127.0.0.1",
             "--port", str(self.api_port)],
            env=self.backend_env(), cwd=ROOT, stdout=self.backend_log, stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                if _request("GET", f"{self.api}/healthz")[0] == 200:
                    return
            except OSError:
                pass
            if self.backend.poll() is not None:
                break
            time.sleep(0.1)
        raise SystemExit("backend did not start; see " + str(self.scratch / "backend.log"))

    def stop(self) -> None:
        if self.backend is not None:
            self.backend.terminate()
            try:
                self.backend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.backend.kill()
                self.backend.wait(timeout=10)
            self.backend_log.close()
        self.idp.stop()
        if self.pg_ctl:
            subprocess.run([self.pg_ctl, "-D", str(self.scratch / "data"), "-m", "fast", "stop"],
                           env=_clean_env(), capture_output=True)
        if not self.keep:
            shutil.rmtree(self.scratch, ignore_errors=True)


# --- a minimal browser: no redirect following, host-only cookies for the API ----


def _request(method, url, body=None, headers=None):
    parts = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection("127.0.0.1", parts.port, timeout=30)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    connection.request(method, path, body=body, headers={"Host": parts.netloc, **(headers or {})})
    response = connection.getresponse()
    return response.status, response.getheaders(), response.read()


class Browser:
    def __init__(self, lab: Lab):
        self.lab = lab
        self.cookies: dict[str, str] = {}
        self.raw_set_cookie: list[str] = []

    def call(self, method, url, body=None, headers=None):
        headers = dict(headers or {})
        if url.startswith(self.lab.api) and self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        status, response_headers, data = _request(method, url, body, headers)
        for name, value in response_headers:
            if name.lower() == "set-cookie" and url.startswith(self.lab.api):
                self.raw_set_cookie.append(value)
                key, _, rest = value.partition("=")
                val = rest.split(";", 1)[0]
                if "max-age=0" in value.lower() or not val.strip('"'):
                    self.cookies.pop(key, None)
                else:
                    self.cookies[key] = val
        location = next((v for n, v in response_headers if n.lower() == "location"), None)
        return status, location, data

    def json(self, method, path, **kwargs):
        status, _, data = self.call(method, self.lab.api + path, **kwargs)
        try:
            return status, json.loads(data or b"null")
        except ValueError:
            return status, None

    def login(self, user: str, return_to: str = "/runs") -> str:
        status, location, _ = self.call("GET", f"{self.lab.api}/api/v1/auth/login?"
                                        + urllib.parse.urlencode({"return_to": return_to}))
        assert status == 302 and location.startswith(self.lab.idp.issuer), (status, location)
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(location).query))
        status, location, _ = self.call("POST", f"{self.lab.idp.issuer}/oauth2/authorize",
                                        body=urllib.parse.urlencode({**query, "user": user}),
                                        headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert status == 302 and location.startswith(self.lab.idp.redirect_uri), (status, location)
        status, location, _ = self.call("GET", location)
        assert status == 302, status
        return location

    def session(self):
        return self.json("GET", "/api/v1/auth/session")[1]

    def upload(self, csrf=None):
        boundary = "juvallab" + os.urandom(8).hex()
        parts = [("file", FIXTURE.name, FIXTURE.read_bytes()), ("thresholds", None, THRESHOLDS.encode()),
                 ("fees", None, FEES.encode()), ("persist", None, b"true")]
        body = b""
        for name, filename, value in parts:
            disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
            body += f"--{boundary}\r\nContent-Disposition: {disposition}\r\n\r\n".encode() + value + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if csrf:
            headers["X-JUVAL-CSRF"] = csrf
        return self.json("POST", "/api/v1/runs", body=body, headers=headers)


# --- the end-to-end security smoke ------------------------------------------------


def check(lab: Lab) -> int:
    import psycopg

    results = []

    def expect(condition, label):
        results.append(bool(condition))
        print(f"{'PASS' if condition else 'FAIL'}  {label}")

    status, _, body = _request("GET", f"{lab.api}/healthz")
    expect((status, json.loads(body)) == (200, {"status": "ok"}), "/healthz is public and constant")
    expect(Browser(lab).json("GET", "/api/v1/runs")[0] == 401, "no session -> 401 on a data route")

    alice, bob, carol = Browser(lab), Browser(lab), Browser(lab)
    landing = alice.login("alice", "/runs/abc?tab=records")
    expect(landing == f"{lab.web}/runs/abc?tab=records", "login lands on the app origin with return_to (ADR-038)")
    session_cookie = next(c for c in alice.raw_set_cookie if c.startswith("juval_session="))
    expect("httponly" in session_cookie.lower() and "samesite=lax" in session_cookie.lower()
           and "domain=" not in session_cookie.lower(), "session cookie: HttpOnly, SameSite=Lax, host-only")
    view = alice.session()
    expect(view["authenticated"] and view["roles"] == ["operator"] and view.get("csrf_token"),
           "/session projects roles and the CSRF token, no tokens")
    expect(not {"access_token", "refresh_token", "id_token"} & set(view), "/session never returns tokens")

    status, body = alice.upload()
    expect((status, body) == (403, {"detail": "csrf token missing or invalid"}), "mutation without CSRF -> 403")
    status, body = alice.upload(view["csrf_token"])
    expect(status == 200, "operator creates a run with the CSRF header")
    run = body["execution_id"]
    expect(alice.json("GET", f"/api/v1/runs/{run}")[0] == 200, "owner organization reads the run")

    bob.login("bob")
    foreign = bob.json("GET", f"/api/v1/runs/{run}")
    absent = bob.json("GET", "/api/v1/runs/00000000-0000-4000-8000-000000000000")
    expect(foreign == absent and foreign[0] == 404, "other organization: 404 identical to a missing run (BOLA)")
    expect(run not in json.dumps(bob.json("GET", "/api/v1/runs")[1]), "other organization: not in the listing")

    carol.login("carol")
    expect(carol.json("GET", "/api/v1/runs") == (403, {"detail": "no organization access for this identity"}),
           "valid identity without membership -> 403, no auto-provisioning")

    with psycopg.connect(lab.admin_dsn) as conn:
        digest = hashlib.sha256(alice.cookies["juval_session"].encode()).hexdigest()
        row = conn.execute("SELECT access_token_ciphertext FROM identity_sessions WHERE session_digest = %s",
                           (digest,)).fetchone()
        raw = conn.execute("SELECT count(*) FROM identity_sessions WHERE session_digest = %s",
                           (alice.cookies["juval_session"],)).fetchone()[0]
        expect(row and str(row[0]).startswith("v1.") and raw == 0,
               "PostgreSQL stores the session digest and encrypted tokens only")
        stored = conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0]
    with psycopg.connect(lab.runtime_dsn) as conn:
        unbound = conn.execute("SELECT count(*) FROM execution_runs").fetchone()[0]
    expect(stored >= 1 and unbound == 0, "RLS: juval_backend without an organization binding sees no rows")

    lab.idp.set_roles("alice", ["viewer"])                     # role change at the IdP
    view = alice.session()
    expect(view["roles"] == ["viewer"], "role change reaches the session at the next refresh")
    expect(alice.upload(view["csrf_token"]) == (403, {"detail": "insufficient permissions"}),
           "old permission no longer works")

    lab.idp.disable("bob")                                     # account disabled at the IdP
    expect(bob.json("GET", "/api/v1/runs")[0] == 401, "disabled IdP account: refresh refused, session ends")

    from juval.infrastructure.persistence.postgres_session_store import revoke_sessions
    revoke_sessions(lab.admin_dsn, datetime.now(timezone.utc), "carol")
    expect(carol.session() == {"authenticated": False}, "operator revoke-sessions ends the session at once")

    captured = alice.cookies["juval_session"]
    status, body = alice.json("POST", "/api/v1/auth/logout", headers={"X-JUVAL-CSRF": view["csrf_token"]})
    expect(status == 200 and body["end_session_url"].startswith(f"{lab.idp.issuer}/oauth2/logout"),
           "logout revokes and returns the IdP end-session URL")
    status, headers, _ = _request("GET", body["end_session_url"])
    location = next((v for n, v in headers if n.lower() == "location"), None)
    expect(status == 302 and location == f"{lab.web}/", "IdP logout returns only to the registered app URL")
    alice.cookies["juval_session"] = captured
    expect(alice.json("GET", "/api/v1/runs")[0] == 401, "a captured cookie is useless after logout")

    log = (lab.scratch / "backend.log").read_text()
    expect('"event":"access.denied"' in log and '"kind":"tenant"' in log, "security events are emitted")
    expect(captured not in log and view["csrf_token"] not in log and "alice" not in log,
           "backend log has no cookies, CSRF tokens or raw subjects")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="run the end-to-end security smoke and exit")
    parser.add_argument("--api-port", type=int, default=18781)
    parser.add_argument("--idp-port", type=int, default=18782)
    parser.add_argument("--web-port", type=int, default=5173)
    parser.add_argument("--token-ttl", type=int, default=60,
                        help="access-token lifetime in seconds (below 120 s every request refreshes)")
    parser.add_argument("--keep", action="store_true", help="keep the scratch directory for inspection")
    args = parser.parse_args(argv)
    _refuse_unsafe_environment()
    saved_libpq = _without_libpq_environment()
    lab = None
    try:
        lab = Lab(args.api_port, args.idp_port, args.web_port, args.token_ttl, args.keep)
        lab.start()
        if args.check:
            return check(lab)
        print(f"API      {lab.api}   (healthz: {lab.api}/healthz)")
        print(f"IdP      {lab.idp.issuer}   users: alice (A, operator), bob (B, operator), carol (none)")
        print(f"frontend run in frontend-next/:  VITE_API_BASE_URL={lab.api} npm run dev -- --port {args.web_port}")
        print(f"open     {lab.web}/   then 'Sign in'.   Ctrl-C stops and deletes everything.")
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0
    finally:
        if lab is not None:
            lab.stop()
        os.environ.update(saved_libpq)


if __name__ == "__main__":
    sys.exit(main())
