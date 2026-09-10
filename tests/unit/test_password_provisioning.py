"""The Control 6 chokepoint (ADR-035): validate, then delegate, in that order.

`domain/password_policy.py` decides whether a password is acceptable and has
its own tests. This file covers the thing that makes that decision *binding*:
`PasswordProvisioningService` is meant to be the only object in the codebase
that can hand a password to an identity provider, and it must be impossible to
reach the provider without passing the rule first.

The recovery audit found this module untested, which mattered more than the
count suggests: Control 6's entire enforceability argument rests on it.

No real password, name or credential appears here -- every value is fictional.
"""

from __future__ import annotations

import logging

import pytest

from juval.application.password_provisioning import (
    PasswordProvisioningError,
    PasswordProvisioningService,
    PasswordSubject,
)
from juval.domain.password_policy import (
    EvidenceClass,
    PasswordPolicyError,
    PasswordPolicyRule,
)

SUBJECT = PasswordSubject(user_id="u-1", first_name="Quenella", last_name="Vorstrand")

COMPLIANT = "7xKf!ptRw3Qm"          # contains no part of the name
CONTAINS_FIRST_NAME = "Quenella-99!x"
CONTAINS_LAST_NAME = "aB3!vorstrandQ"


class RecordingIdentity:
    """Stands in for a future `infrastructure/` adapter. None ships today."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def set_password(self, subject: PasswordSubject, password: str) -> None:
        self.calls.append((subject.user_id, password))


def test_a_compliant_password_reaches_the_identity_port():
    identity = RecordingIdentity()
    result = PasswordProvisioningService(identity).set_password(SUBJECT, COMPLIANT)

    assert result.ok is True
    assert result.evidence_class is EvidenceClass.VERIFIED_POLICY
    assert identity.calls == [("u-1", COMPLIANT)]


@pytest.mark.parametrize("password", [CONTAINS_FIRST_NAME, CONTAINS_LAST_NAME])
def test_a_violating_password_never_reaches_the_identity_port(password):
    """The property the whole design exists for: no path around the rule."""
    identity = RecordingIdentity()
    service = PasswordProvisioningService(identity)

    with pytest.raises(PasswordPolicyError) as raised:
        service.set_password(SUBJECT, password)

    assert identity.calls == []  # the provider was never called
    violations = raised.value.result.violations
    assert violations
    assert all(v.rule is PasswordPolicyRule.CONTAINS_NAME_COMPONENT for v in violations)


def test_a_subject_with_no_name_is_refused_rather_than_passed_vacuously():
    """Without a name the rule has nothing to exclude, so it would pass silently.

    ADR-035 closes that by refusing to provision such a subject at all. This is
    the one place the vacuous pass could have become a hole.
    """
    nameless = PasswordSubject(user_id="u-2", first_name=None, last_name=None)
    identity = RecordingIdentity()

    with pytest.raises(PasswordProvisioningError, match="first or last name"):
        PasswordProvisioningService(identity).set_password(nameless, COMPLIANT)
    assert identity.calls == []


def test_an_empty_string_name_counts_as_no_name():
    """`""` must not slip past the check that `None` fails."""
    blank = PasswordSubject(user_id="u-3", first_name="", last_name="")
    with pytest.raises(PasswordProvisioningError):
        PasswordProvisioningService(RecordingIdentity()).validate(blank, COMPLIANT)


def test_one_name_is_enough_to_provision():
    single = PasswordSubject(user_id="u-4", first_name=None, last_name="Vorstrand")
    identity = RecordingIdentity()
    PasswordProvisioningService(identity).set_password(single, COMPLIANT)
    assert identity.calls == [("u-4", COMPLIANT)]

    with pytest.raises(PasswordPolicyError):
        PasswordProvisioningService(identity).set_password(single, CONTAINS_LAST_NAME)


def test_validate_checks_without_setting_anything():
    """The pre-flight a UI may call. It must not be a way to set a password."""
    identity = RecordingIdentity()
    service = PasswordProvisioningService(identity)

    assert service.validate(SUBJECT, COMPLIANT).ok is True
    assert service.validate(SUBJECT, CONTAINS_FIRST_NAME).ok is False
    assert identity.calls == []


def test_no_adapter_is_a_configuration_error_not_a_policy_pass():
    """Collapsing these two would let a misconfiguration read as success."""
    service = PasswordProvisioningService()  # no adapter -- the shipping state

    with pytest.raises(PasswordProvisioningError, match="no identity password adapter"):
        service.set_password(SUBJECT, COMPLIANT)

    # And a bad password still fails as a *policy* error, before that point.
    with pytest.raises(PasswordPolicyError):
        service.set_password(SUBJECT, CONTAINS_FIRST_NAME)


def test_rejection_logging_names_the_rule_and_never_the_password(caplog):
    service = PasswordProvisioningService(RecordingIdentity())
    with caplog.at_level(logging.WARNING, logger="juval.application.password_provisioning"):
        with pytest.raises(PasswordPolicyError):
            service.set_password(SUBJECT, CONTAINS_FIRST_NAME)

    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert "containsNameComponent" in emitted
    assert "u-1" in emitted
    assert CONTAINS_FIRST_NAME not in emitted
    for fragment in ("99!x", "-99", "!x"):
        assert fragment not in emitted


def test_success_logging_records_the_evidence_class_and_no_password(caplog):
    service = PasswordProvisioningService(RecordingIdentity())
    with caplog.at_level(logging.INFO, logger="juval.application.password_provisioning"):
        service.set_password(SUBJECT, COMPLIANT)

    emitted = "\n".join(record.getMessage() for record in caplog.records)
    assert "VERIFIED_POLICY" in emitted
    assert "AMAZON_VERIFIED_COMPLIANCE" not in emitted  # never claimed here
    assert COMPLIANT not in emitted
