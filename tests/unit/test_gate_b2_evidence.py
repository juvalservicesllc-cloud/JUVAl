from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import socket
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gate_b2_evidence", ROOT / "tools/gate_b2_evidence.py")
assert SPEC and SPEC.loader
evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = evidence
SPEC.loader.exec_module(evidence)
SPEC = importlib.util.spec_from_file_location("b2_collector_test", ROOT / "tools/gate_b2_readonly_preflight.py")
assert SPEC and SPEC.loader
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)

STAMP = "2026-10-06T12:00:00.000000Z"
LIFECYCLE_FLAGS = (
    "connection_established", "read_only_setup_complete", "read_only_verified",
    "observations_complete", "rollback_attempted", "rollback_succeeded",
    "connection_close_attempted", "connection_close_succeeded", "connection_closed",
)
FAKE_PASSWORD = "JUVAL-SANITIZED-FIXTURE"
FAKE_DSN = "postgresql://offline:" + FAKE_PASSWORD + "@example.invalid/fixture"


@pytest.fixture(autouse=True)
def offline_boundary(monkeypatch):
    # No test may reach a driver/socket or either real candidate, even by accident.
    monkeypatch.delenv("JUVAL_SUPABASE_DB_URL", raising=False)

    def denied(*args, **kwargs):
        pytest.fail("unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    import builtins
    original_open, original_os_open = builtins.open, os.open

    def guard(path):
        if isinstance(path, (str, bytes, os.PathLike)):
            if Path(os.fsdecode(path)).name in (".env.supabase-gate", ".env.supabase-gate.save"):
                pytest.fail("unexpected real credential access")

    def guarded_open(path, *args, **kwargs):
        guard(path)
        return original_open(path, *args, **kwargs)

    def guarded_os_open(path, *args, **kwargs):
        guard(path)
        return original_os_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)


@pytest.fixture
def lifecycle():
    return {"attempt_count": 1, "transaction_read_only": "on",
            **{key: True for key in LIFECYCLE_FLAGS}}


@pytest.fixture
def catalog():
    return {
        "database_identity": {"database": "postgres", "server_version_num": 170006,
                              "transaction_read_only": "on", "current_user": "postgres"},
        "relations": [{
            "name": name, "state": "PRESENT", "owner": "postgres",
            "rls_enabled": True, "rls_forced": False, "policies": [],
            "columns": [{"name": "id", "type": "uuid", "not_null": True}],
            "constraints": [{"name": "pk", "definition": "PRIMARY KEY (id)"}],
            "declared_acl_entries": [{"grantor": "postgres", "grantee": "anon", "privilege_type": "MAINTAIN"}],
            "effective_table_privileges": {"anon": {p: True for p in evidence.ALL_TABLE_PRIVILEGES}},
        } for name in evidence.TARGET_RELATIONS],
        "migration_ledger": {"state": "PRESENT", "versions": [
            {"version": "20260909000004", "state": "ABSENT"},
            {"version": "20261005000007", "state": "ABSENT"},
            {"version": "20260817000000", "state": "PRESENT"},
        ]},
        "roles": [{"rolname": "postgres", "rolsuper": False, "rolbypassrls": True}],
        "relevant_memberships": [{"member": "postgres", "granted_role": "admin"}],
        "public_schema": [{"name": "public", "owner": "postgres",
                           "effective_privileges": {"anon": {"USAGE": True, "CREATE": False}}}],
        "public_schema_declared_acl_entries": [{"grantee": "anon", "privilege_type": "USAGE"}],
        "default_privileges_by_owner": [
            {"owner": "postgres", "schema": None, "object_type": "f", "grantee": "PUBLIC", "privilege_type": "EXECUTE"},
            {"owner": "supabase_admin", "schema": "public", "object_type": "r", "grantee": "anon", "privilege_type": "SELECT"},
        ],
        "maintain": {"postgres_major": 17, "effective_checks_applicable": True},
    }


def document(catalog, lifecycle):
    return evidence.build_evidence_document(catalog, lifecycle, timestamp_utc=STAMP)


def directory(root):
    return root / evidence.DEFAULT_EVIDENCE_RELATIVE_PATH


def test_deterministic_serialization_and_schema(catalog, lifecycle):
    first = evidence.serialize_evidence(document(catalog, lifecycle))
    second = evidence.serialize_evidence(document(copy.deepcopy(catalog), lifecycle))
    assert first == second
    assert json.loads(first)["evidence_schema_version"] == evidence.EVIDENCE_SCHEMA_VERSION
    assert first.endswith(b"\n")


def test_order_independent_catalog_rows(catalog, lifecycle):
    def reverse(value):
        if isinstance(value, dict):
            return {key: reverse(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reverse(item) for item in reversed(value)]
        return value
    assert evidence.serialize_evidence(document(catalog, lifecycle)) == evidence.serialize_evidence(
        document(reverse(catalog), lifecycle))


def test_raw_and_classification_are_independent(catalog, lifecycle):
    original = copy.deepcopy(catalog)
    doc = document(catalog, lifecycle)
    assert catalog == original
    raw = doc["RAW_OBSERVATION"]["catalog"]
    assert "security_state" not in raw["relations"][0]
    assert "grant_origin" not in raw["default_privileges_by_owner"][0]
    assert "CLASSIFICATION" in doc
    for key in original:
        assert key in raw


def test_utf8_preserved(catalog, lifecycle):
    catalog["note"] = "observación π"
    assert "observación π".encode() in evidence.serialize_evidence(document(catalog, lifecycle))


def test_dsn_and_sensitive_fields_removed(catalog, lifecycle, monkeypatch):
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", FAKE_DSN)
    catalog.update(dsn=FAKE_DSN, password=FAKE_PASSWORD, credential_contents=FAKE_DSN, note=FAKE_DSN)
    payload = evidence.serialize_evidence(document(catalog, lifecycle))
    assert FAKE_DSN.encode() not in payload
    assert FAKE_PASSWORD.encode() not in payload


@pytest.mark.parametrize("dsn", [FAKE_DSN, "host=example.invalid password=" + FAKE_PASSWORD], ids=["uri", "keyword"])
def test_password_in_arbitrary_catalog_field_fails_closed(catalog, lifecycle, monkeypatch, dsn):
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", dsn)
    catalog["relations"][0]["policies"] = [{"qual": FAKE_PASSWORD}]
    with pytest.raises(evidence.EvidenceSecretError) as error:
        document(catalog, lifecycle)
    assert FAKE_PASSWORD not in str(error.value)
    assert dsn not in str(error.value)


@pytest.mark.parametrize("key", [*LIFECYCLE_FLAGS, "attempt_count", "transaction_read_only"])
def test_each_lifecycle_failure_prevents_valid_artifact(catalog, lifecycle, tmp_path, key):
    lifecycle[key] = 0 if key == "attempt_count" else "off" if key == "transaction_read_only" else False
    with pytest.raises(evidence.EvidenceNotFinalizable):
        doc = document(catalog, lifecycle)
        evidence.write_evidence_artifact(doc, repository_root=tmp_path)
    assert not directory(tmp_path).exists()


def test_mutated_valid_document_is_revalidated(catalog, lifecycle, tmp_path):
    doc = document(catalog, lifecycle)
    doc["RAW_OBSERVATION"]["connection_lifecycle"]["connection_closed"] = False
    with pytest.raises(evidence.EvidenceNotFinalizable):
        evidence.write_evidence_artifact(doc, repository_root=tmp_path)
    assert not directory(tmp_path).exists()


def test_artifact_mode_hash_and_no_self_reference(catalog, lifecycle, tmp_path):
    doc = document(catalog, lifecycle)
    artifact = evidence.write_evidence_artifact(doc, repository_root=tmp_path)
    path = Path(artifact["path"])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == 0o700
    data = path.read_bytes()
    assert data == evidence.serialize_evidence(doc)
    assert hashlib.sha256(data).hexdigest() == artifact["sha256"]
    assert artifact["sha256"].encode() not in data
    assert json.loads(data)["artifact_status"] == "VALID"
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("component", [".local-evidence", ".local-evidence/gate_b2"])
def test_symlink_directory_rejected(catalog, lifecycle, tmp_path, component):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / component
    link.parent.mkdir(exist_ok=True, mode=0o700)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert not list(outside.iterdir())


def test_symlink_root_ancestor_rejected(catalog, lifecycle, tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    repo = actual / "repo"
    repo.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=alias / "repo")


@pytest.mark.parametrize("stamp", ["../../escape", "2026-10-06T00:00:00Z/escape"])
def test_unsafe_filename_rejected(catalog, lifecycle, tmp_path, stamp):
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path, timestamp_for_name=stamp)
    assert not directory(tmp_path).exists()


def test_unsafe_existing_directory_permissions_rejected(catalog, lifecycle, tmp_path):
    (tmp_path / ".local-evidence").mkdir(mode=0o755)
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)


@pytest.mark.parametrize("symlink", [False, True])
def test_existing_destination_not_overwritten(catalog, lifecycle, tmp_path, monkeypatch, symlink):
    monkeypatch.setattr(evidence.secrets, "token_hex", lambda count: "a" * 24)
    doc = document(catalog, lifecycle)
    first = evidence.write_evidence_artifact(doc, repository_root=tmp_path)
    path = Path(first["path"])
    original = path.read_bytes()
    if symlink:
        outside = tmp_path / "untouched"
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(doc, repository_root=tmp_path)
    assert path.read_bytes() == original
    assert not list(path.parent.glob("*.tmp"))


def test_atomic_publication_after_file_fsync(catalog, lifecycle, tmp_path, monkeypatch):
    events = []
    rename, fsync = evidence._rename_noreplace, os.fsync

    def sync(fd):
        events.append("directory_sync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_sync")
        fsync(fd)

    def publish(fd, temp, final):
        assert events == ["file_sync"]
        assert not (directory(tmp_path) / final).exists()
        assert (directory(tmp_path) / temp).read_bytes() == evidence.serialize_evidence(document(catalog, lifecycle))
        rename(fd, temp, final)
        assert (directory(tmp_path) / final).exists()
        events.append("published")

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(evidence, "_rename_noreplace", publish)
    evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert events == ["file_sync", "published", "directory_sync"]


def test_publish_failure_cleans_temp_without_secret_diagnostics(catalog, lifecycle, tmp_path, monkeypatch):
    def fail(*args):
        raise OSError(FAKE_DSN + FAKE_PASSWORD)
    monkeypatch.setattr(evidence, "_rename_noreplace", fail)
    with pytest.raises(evidence.EvidencePathError) as error:
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert FAKE_PASSWORD not in str(error.value)
    assert not list(directory(tmp_path).iterdir())


def test_pg17_maintain_and_all_evidence_categories_preserved(catalog, lifecycle):
    raw = json.loads(evidence.serialize_evidence(document(catalog, lifecycle)))["RAW_OBSERVATION"]
    assert raw["catalog"]["maintain"]["postgres_major"] == 17
    assert raw["catalog"]["relations"][0]["effective_table_privileges"]["anon"]["MAINTAIN"] is True
    assert raw["catalog"]["database_identity"]["server_version_num"] == 170006
    assert raw["connection_lifecycle"]["observations_complete"] is True
    assert raw["observation_counts"]["target_relations"] == 8
    assert raw["catalog"]["relevant_memberships"]


def test_classification_dimensions_remain_separate(catalog, lifecycle):
    classified = document(catalog, lifecycle)["CLASSIFICATION"]
    relation = classified["relations"][0]
    assert relation["security_state"] == "DRIFT"
    assert relation["grant_origin"] == "SUPABASE_PLATFORM_DEFAULT_PLAUSIBLE"
    assert relation["object_control"] == "JUVAL_CONTROLLED"
    assert classified["postgresql_capability"] == "VERIFIED"
    assert classified["public_api_exploitability"] == "UNDETERMINED_NOT_TESTED"
    item = next(row for row in classified["ledger"] if row["version"] == "20261005000007")
    assert item["ledger_state"] == "ABSENT"
    assert item["security_state"] == "EXPECTED"
    assert item["material_schema_state"] == "UNDETERMINED"


def test_platform_and_postgres_defaults_not_juval_owned(catalog, lifecycle):
    rows = document(catalog, lifecycle)["CLASSIFICATION"]["default_privileges"]
    assert next(row for row in rows if row["owner"] == "supabase_admin")["object_control"] == "SUPABASE_MANAGED"
    assert next(row for row in rows if row["owner"] == "postgres")["object_control"] == "UNDETERMINED"


@pytest.mark.parametrize("state", [None, "NOT_OBSERVED", "ABSENT"])
def test_missing_relation_not_manufactured_into_absence(catalog, lifecycle, state):
    catalog["relations"] = [] if state is None else [{"name": "execution_runs", "state": state}]
    doc = document(catalog, lifecycle)
    assert all(row["security_state"] == "UNDETERMINED" for row in doc["CLASSIFICATION"]["relations"])
    assert doc["RAW_OBSERVATION"]["catalog"]["relations"] == catalog["relations"]
    summary = evidence.compact_summary(doc, {"path": "safe.json", "sha256": "a" * 64})
    assert summary["target_relations_absent"] == (1 if state == "ABSENT" else 0)


def test_unknown_roles_remain_undetermined(catalog, lifecycle):
    del catalog["roles"]
    summary = evidence.compact_summary(document(catalog, lifecycle), {"path": "safe.json", "sha256": "a" * 64})
    assert summary["juval_backend"] == "UNDETERMINED"


def test_compact_summary_without_raw_evidence_or_secrets(catalog, lifecycle, monkeypatch):
    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", FAKE_DSN)
    catalog["bulk"] = "x" * 30000
    catalog["password"] = FAKE_PASSWORD
    doc = document(catalog, lifecycle)
    text = json.dumps(evidence.compact_summary(doc, {"path": "safe.json", "sha256": "a" * 64}))
    assert len(text) < 2500
    assert "RAW_OBSERVATION" not in text and "bulk" not in text
    assert FAKE_PASSWORD not in text and FAKE_DSN not in text


@pytest.mark.parametrize("failure", ["none", "read_only", "collect", "rollback", "close", "unconfirmed_close", "connect", "artifact"])
def test_collector_lifecycle_and_secret_safe_output(catalog, tmp_path, monkeypatch, capsys, failure):
    events = []

    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, sql):
            events.append(sql)
        def fetchone(self):
            return ("off" if failure == "read_only" else "on",)

    class Connection:
        autocommit = False
        closed = False
        def cursor(self):
            return Cursor()
        def rollback(self):
            events.append("rollback")
            if failure == "rollback":
                raise RuntimeError(FAKE_DSN)
        def close(self):
            events.append("close")
            if failure == "close":
                raise RuntimeError(FAKE_PASSWORD)
            self.closed = failure != "unconfirmed_close"

    def connect(*args, **kwargs):
        events.append("connect")
        assert args == (FAKE_DSN,)
        assert kwargs["autocommit"] is False
        if failure == "connect":
            raise RuntimeError(FAKE_DSN)
        return Connection()

    def collect(conn):
        events.append("collect")
        if failure == "collect":
            raise RuntimeError(FAKE_DSN)
        return copy.deepcopy(catalog)

    writer = evidence.write_evidence_artifact

    def publish(doc, **kwargs):
        assert events[-2:] == ["rollback", "close"]
        events.append("finalize")
        if failure == "artifact":
            raise OSError(FAKE_DSN)
        return writer(doc, **kwargs)

    monkeypatch.setenv("JUVAL_SUPABASE_DB_URL", FAKE_DSN)
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    monkeypatch.setattr(collector, "ROOT", tmp_path)
    monkeypatch.setattr(collector, "build_report", collect)
    monkeypatch.setattr(collector, "write_evidence_artifact", publish)
    result = collector.main()
    output = capsys.readouterr()
    assert FAKE_DSN not in output.out + output.err
    assert FAKE_PASSWORD not in output.out + output.err
    assert len(output.out) < 2500
    assert events.count("connect") == 1
    if failure == "none":
        assert result == 0
        assert events.index("collect") < events.index("rollback") < events.index("close") < events.index("finalize")
        assert len(list(directory(tmp_path).glob("*.json"))) == 1
    else:
        assert result == 1
        assert not list(directory(tmp_path).glob("*.json"))
        if failure != "artifact":
            assert "finalize" not in events


def test_static_collector_readonly_scope():
    source = (ROOT / "tools/gate_b2_readonly_preflight.py").read_text()
    tree = ast.parse(source)
    connects = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "connect"
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "psycopg"]
    assert len(connects) == 1
    assert any(key.arg == "autocommit" and isinstance(key.value, ast.Constant)
               and key.value.value is False for key in connects[0].keywords)
    sql = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        index = None
        if isinstance(node.func, ast.Name) and node.func.id in ("_fetchone", "_fetchall"):
            index = 1
        if isinstance(node.func, ast.Attribute) and node.func.attr == "execute":
            index = 0
        if index is not None and len(node.args) > index and isinstance(node.args[index], ast.Constant):
            sql.append(node.args[index].value.strip())
    assert "SET TRANSACTION READ ONLY" in sql
    assert "SHOW transaction_read_only" in sql
    assert all(query.startswith("SELECT") or query in ("SET TRANSACTION READ ONLY", "SHOW transaction_read_only") for query in sql)
    assert 'report["transaction_read_only"] == "on"' in source
    assert "conn.rollback()" in source and "finally:" in source and "conn.close()" in source
    assert "conn.closed" in source and 'report["observations_complete"] = True' in source
    assert collector.TARGET_RELATIONS == evidence.TARGET_RELATIONS
    assert "20260909000004" in collector.LEDGER_VERSIONS
    assert 'if pg_major >= 17' in source
    assert 'print(json.dumps(document' not in source


def test_generated_evidence_ignore_pattern():
    assert "/.local-evidence/gate_b2/" in (ROOT / ".gitignore").read_text()


def test_preexisting_temporary_symlink_never_followed(catalog, lifecycle, tmp_path, monkeypatch):
    directory_fd = evidence._open_private_evidence_directory(tmp_path)
    os.close(directory_fd)
    outside = tmp_path / "untouched"
    outside.write_bytes(b"untouched")
    nonce = "b" * 24
    link = directory(tmp_path) / f".gate-b2-{nonce}.tmp"
    link.symlink_to(outside)
    monkeypatch.setattr(evidence.secrets, "token_hex", lambda count: nonce)
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert outside.read_bytes() == b"untouched"
    assert link.is_symlink()
    assert not list(directory(tmp_path).glob("*.json"))


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_fsync_failure_never_reports_canonical_success(catalog, lifecycle, tmp_path, monkeypatch, kind):
    sync = os.fsync
    fired = False

    def fail_once(fd):
        nonlocal fired
        is_dir = stat.S_ISDIR(os.fstat(fd).st_mode)
        if not fired and (kind == "directory") == is_dir:
            fired = True
            raise OSError(FAKE_DSN)
        sync(fd)

    monkeypatch.setattr(os, "fsync", fail_once)
    with pytest.raises(evidence.EvidencePathError) as error:
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert FAKE_DSN not in str(error.value)
    assert not list(directory(tmp_path).iterdir())


def test_final_byte_validation_detects_corruption(catalog, lifecycle, tmp_path, monkeypatch):
    rename = evidence._rename_noreplace

    def corrupt(fd, temporary, final):
        rename(fd, temporary, final)
        (directory(tmp_path) / final).write_bytes(b"corrupted")

    monkeypatch.setattr(evidence, "_rename_noreplace", corrupt)
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert not list(directory(tmp_path).iterdir())


def test_no_atomic_rename_support_fails_closed(catalog, lifecycle, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence.ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace())
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=tmp_path)
    assert not list(directory(tmp_path).iterdir())


def test_relative_repository_root_rejected(catalog, lifecycle):
    with pytest.raises(evidence.EvidencePathError):
        evidence.write_evidence_artifact(document(catalog, lifecycle), repository_root=Path("."))


def test_unknown_privileges_and_rls_do_not_become_expected(catalog, lifecycle):
    catalog["roles"].append({"rolname": "juval_backend"})
    catalog["relations"] = [{"name": "execution_runs", "state": "PRESENT"}]
    assert document(catalog, lifecycle)["CLASSIFICATION"]["relations"][0]["security_state"] == "UNDETERMINED"


def load_runner():
    spec = importlib.util.spec_from_file_location("b2_runner_extra", ROOT / "tools/run_gate_b2_readonly_preflight.py")
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def test_runner_wrong_owner_rejected_without_chown(tmp_path, monkeypatch):
    runner = load_runner()
    candidate = tmp_path / "synthetic.env"
    candidate.write_text("JUVAL_SUPABASE_DB_URL=offline-marker\n")
    candidate.chmod(0o600)
    owner = candidate.stat().st_uid
    monkeypatch.setattr(runner.os, "geteuid", lambda: owner + 1)
    with pytest.raises(ValueError, match="owner does not match"):
        runner.read_authorized_candidate(str(candidate))


def test_runner_all_sensitive_env_removed_and_credential_env_only(monkeypatch, tmp_path, capsys):
    runner = load_runner()
    monkeypatch.setattr(sys, "argv", ["runner", "--credential-candidate", str(tmp_path / "synthetic.env")])
    monkeypatch.setattr(runner, "read_authorized_candidate", lambda path: FAKE_DSN)
    for key in runner.CHILD_CREDENTIAL_ENV_KEYS:
        monkeypatch.setenv(key, "synthetic-excluded-value")
    monkeypatch.setenv("B2_OFFLINE_KEEP", "preserved")
    child_environment = None

    def child(argv, **kwargs):
        nonlocal child_environment
        child_environment = kwargs["env"]
        assert FAKE_DSN not in " ".join(argv)
        assert kwargs.get("shell", False) is False
        assert kwargs["stdin"] is runner.subprocess.DEVNULL
        assert kwargs["env"][runner.KEY] == FAKE_DSN
        assert kwargs["env"]["B2_OFFLINE_KEEP"] == "preserved"
        assert all(key not in kwargs["env"] for key in runner.CHILD_CREDENTIAL_ENV_KEYS)
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(runner.subprocess, "run", child)
    assert runner.main() == 7
    assert runner.KEY not in child_environment
    captured = capsys.readouterr()
    assert FAKE_DSN not in captured.out + captured.err
    assert FAKE_PASSWORD not in captured.out + captured.err
