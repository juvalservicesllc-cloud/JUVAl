"""Static verification of deploy/fusionauth/install.sh.

The script needs `sudo` and a real Ubuntu host to actually execute (the agent
running this test suite has neither), so it cannot be exercised end-to-end
here. This pins the parts of it that are checkable without running it: valid
shell syntax, and the two properties that fix the 2026-08-28 schema-creation
defect (see the script's own comments in step 2 and step 5) -- silent mode
explicitly enabled, and no root database credential added to reach it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

INSTALL_SH = Path(__file__).resolve().parent.parent.parent / "deploy" / "fusionauth" / "install.sh"


def _text() -> str:
    return INSTALL_SH.read_text(encoding="utf-8")


def test_script_is_valid_bash():
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_SH)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr


def test_silent_mode_is_explicitly_enabled():
    # Production runtime-mode never runs maintenance mode (FusionAuth docs),
    # so without this line a fresh empty database never gets a schema.
    assert "fusionauth-app.silent-mode=true" in _text()


def test_no_root_database_credential_is_written():
    # database.root.username/password exist to let FusionAuth create a DB
    # user it doesn't yet have permission to create. This role already owns
    # its own database (step 2), so a superuser fallback is unused attack
    # surface -- FusionAuth's own docs recommend silent-mode=true instead of
    # root credentials for exactly this managed-database shape. Checked
    # against the generated properties heredoc only -- the surrounding
    # comment explains the same absence in prose.
    heredoc = _text().split("cat > \"$FA_CONFIG\" <<PROPS")[1].split("PROPS")[0]
    assert "database.root.username" not in heredoc
    assert "database.root.password" not in heredoc


def test_schema_ownership_fix_uses_on_error_stop():
    text = _text()
    assert "alter schema public owner to" in text
    # Every psql invocation that mutates state in this script is expected to
    # fail loudly rather than partially apply -- ON_ERROR_STOP=1 is the
    # existing house style (see the role-creation step).
    assert "-v ON_ERROR_STOP=1 -d \"${DB_NAME}\"" in text


def test_refuses_to_silently_reassign_a_nonempty_schema():
    # A non-empty 'public' schema owned by the wrong role is exactly the
    # known-bad state from a manual postgres-owned import (§33.2). The script
    # must fail and explain, not guess.
    assert 'fail "database ${DB_NAME} already has' in _text()
