"""Static verification of deploy/fusionauth/backup.sh.

The script needs `sudo`, a real PostgreSQL cluster and a real `postgres` OS
user to actually execute (the agent running this test suite has none), so it
cannot be exercised end-to-end here. This pins the fix for the 2026-08-31
H-17 runtime defect: `sudo bash backup.sh` on the real host created
`/var/backups/juval-fusionauth` as root:root 0700 (via a plain `install -d`,
run as the script's own root-check requires), then `runuser -u postgres --
pg_dump --file=...` failed with "Permission denied", because the postgres OS
user -- not root -- is the one that opens the dump file. The systemd unit has
no `User=` override, so it hits the identical failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_SH = REPO_ROOT / "deploy" / "fusionauth" / "backup.sh"
BACKUP_SERVICE = REPO_ROOT / "tools" / "systemd" / "juval-fusionauth-backup.service"


def _text() -> str:
    return BACKUP_SH.read_text(encoding="utf-8")


def test_script_is_valid_bash():
    result = subprocess.run(
        ["bash", "-n", str(BACKUP_SH)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr


def test_destination_is_explicitly_owned_by_postgres():
    # pg_dump runs as the postgres OS user (runuser -u postgres) and writes
    # its --file argument directly as that user. A root-owned destination
    # (from a root `install -d` with no chown) is unwritable by postgres --
    # this is the exact regression reproduced against the live host.
    text = _text()
    assert "chown postgres:postgres" in text
    assert "chmod 0700" in text


def test_ownership_fix_runs_before_pg_dump():
    text = _text()
    chown_pos = text.index("chown postgres:postgres")
    # The explanatory comment above also mentions "pg_dump --file=..." as
    # prose -- anchor on the actual invocation (--format=custom), which only
    # appears once, in the real code.
    dump_pos = text.index("pg_dump --format=custom")
    assert chown_pos < dump_pos, "ownership must be fixed before pg_dump writes into it"


def test_ownership_is_set_unconditionally_not_only_on_first_creation():
    # `install -d` alone does not reliably fix ownership/mode on a directory
    # that already exists with the wrong owner (e.g. left root:root by a
    # pre-fix run) -- chown/chmod must run every time, unconditionally, so a
    # broken directory self-heals instead of failing forever.
    text = _text()
    install_pos = text.index("install -d -m 0700")
    chown_pos = text.index("chown postgres:postgres")
    assert install_pos < chown_pos
    # No conditional guard (if/test) between directory creation and the
    # ownership fix -- it must be unconditional.
    between = text[install_pos:chown_pos]
    assert "if " not in between
    assert "[ " not in between


def test_destination_directory_is_not_world_or_group_accessible():
    # Least privilege: only postgres (owner) and root (which bypasses DAC)
    # may access the backup directory. No 777/755/750-style broad grant.
    text = _text()
    assert "chmod 0700" in text
    assert "chmod 777" not in text
    assert "chmod -R" not in text


def test_preflight_checks_the_postgres_user_exists():
    # Fails loudly before attempting any write, rather than failing deep
    # inside pg_dump with a less diagnostic error.
    assert 'id postgres >/dev/null 2>&1 || fail "postgres system user not found"' in _text()


def test_backup_service_has_no_user_override():
    # The service unit intentionally runs as root (no User=) -- backup.sh's
    # own root check and privilege drop (runuser -u postgres) is what makes
    # this correct. Documents that the systemd path hits the identical
    # ownership requirement as the manual `sudo bash backup.sh` path, not a
    # different one.
    service_text = BACKUP_SERVICE.read_text(encoding="utf-8")
    assert "User=" not in service_text
