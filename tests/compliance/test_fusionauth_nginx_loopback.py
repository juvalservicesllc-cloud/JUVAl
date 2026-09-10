"""The live opt-in lab must not turn a denied-route regression into verification."""
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
try:
    spec = importlib.util.spec_from_file_location('fusionauth_nginx_loopback', ROOT / 'tools/fusionauth_nginx_loopback.py')
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
finally:
    sys.path.pop(0)


def test_live_lab_requires_explicit_redirect_attestation():
    result = subprocess.run([sys.executable, str(ROOT / 'tools/fusionauth_nginx_loopback.py')], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'baseline/add/readback required' in result.stderr


def test_required_asset_and_private_route_regressions_fail():
    assert lab.verify_paths([{'path': '/css/login.css', 'status': 200}, {'path': '/admin', 'status': 404}])
    assert not lab.verify_paths([{'path': '/admin', 'status': 200}])
    assert not lab.verify_paths([{'path': '/js/login.js', 'status': 404}])
    assert lab.verify_paths([{'path': '/fonts/fontawesome-webfont.woff2', 'status': 404}])
