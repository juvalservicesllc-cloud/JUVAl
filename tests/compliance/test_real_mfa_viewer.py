"""Finite real-viewer controller output checks; no viewer/provider contact."""
import io
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import real_mfa_viewer as viewer


def test_controller_boundary_rejects_unbounded_or_mismatched_evidence(monkeypatch):
    monkeypatch.setattr(viewer.select, 'select', lambda readers, *_args: (readers, [], []))
    for line in [
        '{"status":"LOGIN","path":"/oauth2/authorize?SYNTHETIC_PRIVATE_SENTINEL"}\n',
        '{"status":"LOGIN","path":"/oauth2/authorize","extra":"SYNTHETIC_PRIVATE_SENTINEL"}\n',
        '{"status":"SYNTHETIC_PRIVATE_SENTINEL","path":null}\n',
        'X' * 1024,
    ]:
        child = SimpleNamespace(stdout=io.StringIO(line))
        with pytest.raises(RuntimeError, match='CONTROLLER_SCHEMA'):
            viewer.protocol(child)
    child = SimpleNamespace(stdout=io.StringIO('{"status":"LOGIN","path":"/oauth2/authorize"}\n'),
                            stdin=io.StringIO())
    assert viewer.protocol(child, 'observe') == {'status': 'LOGIN', 'path': '/oauth2/authorize'}
    assert child.stdin.getvalue() == '{"op": "observe"}\n'
