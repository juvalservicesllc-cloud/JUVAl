"""The FusionAuth config tool must stay in lock-step with the backend.

`tools/configure_fusionauth.py` creates the application roles that
`interfaces/api/auth.py` maps to permissions. If the two ever disagree -- a
role renamed on one side only -- tokens would carry a role the backend does
not recognise, which `auth.py` treats as *no permissions* (never full
access), so the failure is a silent lockout rather than a privilege
escalation. Still worth catching here rather than in production.

Also pins the template's password rules to Amazon's numeric baseline, so a
well-meaning edit that loosens `minLength` back below 12 fails a test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


configure_fusionauth = _load("configure_fusionauth")


def test_required_roles_match_the_backend_exactly():
    from juval.interfaces.api.auth import ROLE_PERMISSIONS

    assert set(configure_fusionauth.REQUIRED_ROLES) == set(ROLE_PERMISSIONS), (
        "tools/configure_fusionauth.py REQUIRED_ROLES and "
        "interfaces/api/auth.py ROLE_PERMISSIONS have diverged"
    )


def test_template_meets_amazon_password_baseline():
    tenant = configure_fusionauth.load_template()
    rules = tenant["passwordValidationRules"]

    assert rules["minLength"] >= 12                       # control 1
    assert rules["requireMixedCase"] is True              # controls 2, 3
    assert rules["requireNumber"] is True                 # control 4
    assert rules["requireNonAlpha"] is True               # control 5
    assert rules["rememberPreviousPasswords"]["enabled"] is True
    assert rules["rememberPreviousPasswords"]["count"] >= 10   # control 7

    lockout = tenant["failedAuthenticationConfiguration"]
    assert 0 < lockout["tooManyAttempts"] <= 10           # control 11


def test_age_controls_are_within_amazon_bounds():
    assert configure_fusionauth.MINIMUM_PASSWORD_AGE_SECONDS >= 86_400      # control 8
    assert 0 < configure_fusionauth.MAXIMUM_PASSWORD_AGE_DAYS <= 365        # control 9


def test_template_enables_no_licensed_feature():
    """Community-only: breach detection and email/SMS MFA are paid (ADR-031)."""
    raw = json.dumps(configure_fusionauth.load_template())
    assert "breachDetection" not in raw
    tenant = configure_fusionauth.load_template()
    mfa = tenant["multiFactorConfiguration"]
    assert mfa["email"]["enabled"] is False
    assert mfa["sms"]["enabled"] is False
    assert mfa["authenticator"]["enabled"] is True        # TOTP is Community


def test_no_implicit_or_client_credentials_grant_is_configured():
    """Least privilege: the tool must not enable a grant nothing needs."""
    grants = set(configure_fusionauth.LEAST_PRIVILEGE_GRANTS)
    assert grants == {"authorization_code", "refresh_token"}
    assert "implicit" not in grants
    assert "client_credentials" not in grants
    assert "password" not in grants
