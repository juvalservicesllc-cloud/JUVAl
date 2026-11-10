"""compliance_check `auth.endpoints`: the public-route exception is exact (SEC-01E)."""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import compliance_check  # noqa: E402

PROTECTED = '''
@app.get("/api/v1/runs")
def list_runs(principal=Depends(require("runs:read"))):
    pass
'''


def gaps(source):
    return compliance_check._route_permission_gaps(ast.parse(textwrap.dedent(PROTECTED + source)))[1]


def test_the_exact_liveness_route_is_allowed():
    assert gaps('''
@app.get("/healthz", include_in_schema=False)
def healthz():
    pass
''') == []


@pytest.mark.parametrize("source", [
    '@app.get("/healthz")\ndef healthz(request):\n    pass\n',            # could read the request
    '@app.get("/health")\ndef healthz():\n    pass\n',                    # another path
    '@app.post("/healthz")\ndef healthz():\n    pass\n',                  # another method
    '@app.get("/healthz")\ndef status():\n    pass\n',                    # another handler
    '@app.get("/status")\ndef status():\n    pass\n',                     # an unrelated public route
    '@app.get("/healthz")\ndef healthz(*, db=None):\n    pass\n',         # keyword parameter
])
def test_anything_else_without_a_permission_fails(source):
    assert gaps(source)


def test_the_real_main_passes():
    findings = {f.check: f for f in compliance_check.check_auth_posture() if f.check == "auth.endpoints"}
    assert findings["auth.endpoints"].status == compliance_check.PASS, findings["auth.endpoints"].message
