"""Pure lifecycle configuration tests; never connect to a viewer or Admin."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('private_viewer_lab', ROOT / 'tools/private_viewer_lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def test_viewer_commands_have_only_dedicated_loopback_endpoints():
    vnc, web = lab.viewer_commands('/private/new/Xauthority')
    assert vnc[vnc.index('-display') + 1] == ':100'
    assert vnc[vnc.index('-listen') + 1] == '127.0.0.1'
    assert '-no6' in vnc
    assert '-nosel' in vnc and '-nosetclipboard' in vnc and '-noremote' in vnc
    assert '-ac' not in vnc
    assert web[-2:] == ['127.0.0.1:6081', '127.0.0.1:5901']
    assert not any('record' in arg or 'traffic' in arg for arg in web)


def test_xauthority_is_private_and_fresh_without_disclosure(tmp_path):
    target = tmp_path / 'Xauthority'
    lab.write_authority(target)
    assert target.stat().st_mode & 0o777 == 0o600
    # Do not read, compare or expose credential material.


def test_listener_allowlist_rejects_external_and_unexpected(monkeypatch):
    import pytest
    monkeypatch.setattr(lab, 'listeners', lambda: {('tcp', '0.0.0.0:6081')})
    with pytest.raises(RuntimeError, match='UNEXPECTED_LISTENER'):
        lab.require_listener_delta(set(), lab.VIEWER_PORTS)
