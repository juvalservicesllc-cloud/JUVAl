"""tools/integration_lab.py stays disposable, local and fail-safe (SEC-01F).

No PostgreSQL is started here: each test stops the lab at the guard it checks.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import integration_lab  # noqa: E402
from oidc_lab import LabUser, SyntheticIdP  # noqa: E402


@pytest.fixture
def private_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def _scratch_dirs(root):
    return [p for p in root.iterdir() if p.name.startswith("juval-integration-")]


def _busy_port():
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen()
    return holder


def test_refuses_to_run_on_a_hosting_platform(private_tmp, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    with pytest.raises(SystemExit, match="workstation only"):
        integration_lab.main(["--check"])
    assert _scratch_dirs(private_tmp) == []


def test_a_busy_idp_port_fails_closed_and_leaves_nothing(private_tmp):
    with _busy_port() as holder:
        with pytest.raises(SystemExit, match="cannot bind"):
            integration_lab.main(["--check", "--idp-port", str(holder.getsockname()[1])])
    assert _scratch_dirs(private_tmp) == []


def test_a_busy_api_port_is_refused_so_no_foreign_server_answers():
    with _busy_port() as holder:
        with pytest.raises(SystemExit, match="already in use"):
            integration_lab._require_free_port(holder.getsockname()[1])


def test_a_failed_start_cleans_up_without_hanging_and_restores_pg_env(private_tmp, monkeypatch):
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.9")
    monkeypatch.setattr(integration_lab, "_postgres_binaries", lambda: ("/bin/false", "/bin/false"))
    done = threading.Event()
    outcome = {}

    def run():
        try:
            integration_lab.main(["--check", "--idp-port", "0", "--api-port", "0"])
        except BaseException as exc:  # noqa: BLE001 - recorded for the assertion
            outcome["error"] = exc
        done.set()

    threading.Thread(target=run, daemon=True).start()
    assert done.wait(30), "cleanup hung"
    assert outcome.get("error") is not None                 # initdb failed: the run failed
    assert _scratch_dirs(private_tmp) == []                  # and left nothing behind
    assert os.environ["PGHOSTADDR"] == "203.0.113.9"        # operator environment restored


def test_libpq_variables_are_absent_while_the_lab_runs(monkeypatch):
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.9")
    monkeypatch.setenv("PGSERVICE", "production")
    seen = {}

    def spy(self):
        seen.update({k: v for k, v in os.environ.items() if k.startswith("PG")})
        raise SystemExit("stop here")

    monkeypatch.setattr(integration_lab.Lab, "start", spy)
    with pytest.raises(SystemExit, match="stop here"):
        integration_lab.main(["--check", "--idp-port", "0"])
    assert seen == {}
    assert os.environ["PGSERVICE"] == "production"


def test_migrations_refuse_any_target_but_the_private_socket(private_tmp, monkeypatch):
    lab = integration_lab.Lab(0, 0, 0, 60, keep=False)
    try:
        monkeypatch.setenv("PGHOSTADDR", "203.0.113.9")       # would redirect libpq to TCP
        with pytest.raises(SystemExit, match="private cluster"):
            lab._prepare_database()
    finally:
        lab.stop()


def test_the_backend_environment_inherits_no_operator_configuration(private_tmp, monkeypatch):
    monkeypatch.setenv("JUVAL_RUNTIME_DB_URL", "host=db.production.example dbname=postgres")
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", "host=db.production.example")
    monkeypatch.setenv("JUVAL_SESSION_ENCRYPTION_KEYS", "real:key")
    lab = integration_lab.Lab(0, 0, 0, 60, keep=False)
    try:
        env = lab.backend_env()
        assert env["JUVAL_RUNTIME_DB_URL"] == f"host={lab.socket} dbname=juval user=juval_backend"
        assert "JUVAL_SUPABASE_DB_URL" not in env
        assert not env["JUVAL_SESSION_ENCRYPTION_KEYS"].startswith("real:")
        assert all(not k.startswith("PG") for k in env)
        assert env["JUVAL_CORS_ORIGINS"].startswith("http://localhost:")
    finally:
        lab.stop()


def test_an_idp_that_never_started_stops_immediately():
    idp = SyntheticIdP(client_id="c", client_secret="s", redirect_uri="http://localhost:1/cb",
                       post_logout_redirect_uri="http://localhost:2/", users={"a": LabUser("a", "A", [])})
    done = threading.Event()
    threading.Thread(target=lambda: (idp.stop(), done.set()), daemon=True).start()
    assert done.wait(5)
