from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "tools" / "run_gate_b2_readonly_preflight.py"

SPEC = importlib.util.spec_from_file_location(
    "gate_b2_readonly_preflight_runner",
    RUNNER_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def write_candidate(
    tmp_path: Path,
    content: str,
    *,
    mode: int = 0o600,
) -> Path:
    path = tmp_path / "candidate.env"
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    return path


def test_valid_0600_candidate_is_accepted(tmp_path: Path) -> None:
    path = write_candidate(
        tmp_path,
        "JUVAL_SUPABASE_DB_URL=postgresql://user:secret@example.com/db\n",
    )

    value = runner.read_authorized_candidate(str(path))

    assert value == "postgresql://user:secret@example.com/db"


def test_candidate_with_wrong_permissions_is_rejected(tmp_path: Path) -> None:
    path = write_candidate(
        tmp_path,
        "JUVAL_SUPABASE_DB_URL=postgresql://fake.invalid/db\n",
        mode=0o640,
    )

    with pytest.raises(ValueError, match="permissions must be exactly 0600"):
        runner.read_authorized_candidate(str(path))


@pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="O_NOFOLLOW unavailable on this platform",
)
def test_symlink_candidate_is_rejected(tmp_path: Path) -> None:
    target = write_candidate(
        tmp_path,
        "JUVAL_SUPABASE_DB_URL=postgresql://fake.invalid/db\n",
    )
    link = tmp_path / "candidate-link.env"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="must not be a symlink"):
        runner.read_authorized_candidate(str(link))


def test_duplicate_target_variable_is_rejected(tmp_path: Path) -> None:
    path = write_candidate(
        tmp_path,
        "JUVAL_SUPABASE_DB_URL=postgresql://first.invalid/db\n"
        "JUVAL_SUPABASE_DB_URL=postgresql://second.invalid/db\n",
    )

    with pytest.raises(ValueError, match="duplicate target variable"):
        runner.read_authorized_candidate(str(path))


def test_missing_target_variable_is_rejected(tmp_path: Path) -> None:
    path = write_candidate(
        tmp_path,
        "SOME_UNRELATED_VARIABLE=fake\n",
    )

    with pytest.raises(ValueError, match="lacks the required target variable"):
        runner.read_authorized_candidate(str(path))


@pytest.mark.parametrize(
    "content",
    (
        "JUVAL_SUPABASE_DB_URL=\n",
        "JUVAL_SUPABASE_DB_URL='unterminated\n",
        'JUVAL_SUPABASE_DB_URL="unterminated\n',
        "JUVAL_SUPABASE_DB_URL\n",
    ),
)
def test_empty_or_malformed_target_is_rejected(
    tmp_path: Path,
    content: str,
) -> None:
    path = write_candidate(tmp_path, content)

    with pytest.raises(ValueError):
        runner.read_authorized_candidate(str(path))


def test_wrong_owner_check_is_present() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "info.st_uid != os.geteuid()" in source


def test_runner_uses_descriptor_based_validation_without_reopen() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "os.open(path, flags)" in source
    assert "os.fstat(fd)" in source
    assert 'os.fdopen(fd, "r"' in source
    assert 'getattr(os, "O_NOFOLLOW", 0)' in source

    assert source.index("os.fstat(fd)") < source.index("os.fdopen(fd")


def test_main_passes_secret_only_via_child_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "postgresql://user:secret@example.com/synthetic_preflight_child_env_fixture"
    path = write_candidate(
        tmp_path,
        f"JUVAL_SUPABASE_DB_URL={secret}\n",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [str(RUNNER_PATH), "--credential-candidate", str(path)],
    )

    for name in runner.CHILD_CREDENTIAL_ENV_KEYS:
        monkeypatch.setenv(name, f"SENSITIVE_{name}")

    captured: dict[str, object] = {}

    def fake_run(argv, *, env, stdin, check):
        captured["argv"] = list(argv)
        captured["env"] = dict(env)
        captured["stdin"] = stdin
        captured["check"] = check
        return subprocess.CompletedProcess(argv, 7)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.main()

    assert result == 7

    argv = captured["argv"]
    child_env = captured["env"]

    assert secret not in " ".join(str(part) for part in argv)
    assert child_env[runner.KEY] == secret

    for name in runner.CHILD_CREDENTIAL_ENV_KEYS:
        assert name not in child_env

    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["check"] is False

    output = capsys.readouterr()
    assert secret not in output.out
    assert secret not in output.err


def test_controlled_child_start_failure_does_not_print_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "postgresql://user:secret@example.com/synthetic_preflight_start_failure_fixture"
    path = write_candidate(
        tmp_path,
        f"JUVAL_SUPABASE_DB_URL={secret}\n",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [str(RUNNER_PATH), "--credential-candidate", str(path)],
    )

    def fail_run(*args, **kwargs):
        raise OSError("controlled test failure")

    monkeypatch.setattr(runner.subprocess, "run", fail_run)

    result = runner.main()

    assert result == 3

    output = capsys.readouterr()
    assert "preflight_child=NOT_STARTED" in output.err
    assert secret not in output.out
    assert secret not in output.err


def test_runner_does_not_use_shell_execution() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "shell=True" not in source


def test_runner_does_not_source_candidate_file() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert "source " not in source
    assert "os.system(" not in source
