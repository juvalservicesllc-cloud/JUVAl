"""Run pure Node security boundary tests; no browser/display/network is started."""
from pathlib import Path
import subprocess


def test_restricted_auth_evidence_boundary():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ['node', '--test', 'tests/security/restricted_auth_evidence.test.mjs'],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, 'Restricted evidence unit tests failed (details withheld)'
