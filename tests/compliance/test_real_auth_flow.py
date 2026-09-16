"""Pure real-shaped policy regressions; never starts Chromium or contacts IdP."""
from pathlib import Path
import subprocess


def test_real_auth_flow_policy():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ['node', '--test', 'tests/security/real_auth_flow.test.mjs'],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, 'Real-flow policy tests failed (details withheld)'
