"""The one door a password may pass through on its way to the IdP.

ADR-035. Amazon Control 6 is only a control if it cannot be walked around.
`domain/password_policy.py` decides whether a password is acceptable; this
module is the *chokepoint* that guarantees the decision is actually taken.

Why a service and not a helper function
---------------------------------------
A helper is something a caller may forget to call. This is deliberately the
only object in the codebase that knows how to hand a password to an identity
provider, and it validates before it delegates -- `set_password` has no branch
that reaches `IdentityPasswordPort` without passing through `check_password`
first. Adding a second path to the IdP would be a reviewable, obvious change
rather than an accidental one.

Why there is no concrete adapter here
-------------------------------------
There is no production password path yet, and building one now would mean
holding a FusionAuth API key with `POST /api/user` / `PATCH /api/user` /
`POST /api/user/forgot-password`, which ADR-035 Condition 1 forbids for a
standing credential and ADR-032 scopes to a narrow, approved, temporary task.
So the port is defined and left unimplemented on purpose (CLAUDE.md Sec. 4:
the interface exists because a real rule needs a home, not because an adapter
is anticipated). When a provisioning task is approved, its adapter implements
`IdentityPasswordPort` and inherits the control for free.

What this does NOT cover
------------------------
The FusionAuth admin console. An operator with console access sets a password
inside FusionAuth, where JUVAl code does not run. That is a named residual in
ADR-035 with an operator procedure attached, not a gap this module can close,
and it is documented rather than papered over.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from juval.domain.password_policy import (
    EvidenceClass,
    PasswordPolicyError,
    PasswordPolicyResult,
    check_password,
)

logger = logging.getLogger("juval.application.password_provisioning")


@dataclass(frozen=True)
class PasswordSubject:
    """Who the password belongs to.

    `first_name`/`last_name` are what Control 6 needs. They are required at
    provisioning for exactly that reason: a subject with no name silently
    disables the rule, so `PasswordProvisioningService` refuses one rather than
    passing a vacuous check (see `set_password`).
    """

    user_id: str
    first_name: Optional[str]
    last_name: Optional[str]


class IdentityPasswordPort(Protocol):
    """Hands an already-validated password to the identity provider.

    Implementations live in `infrastructure/`. None ships today -- see the
    module docstring. An implementation must never re-validate or relax: the
    check has happened by the time it is called.
    """

    def set_password(self, subject: PasswordSubject, password: str) -> None: ...


class PasswordProvisioningError(RuntimeError):
    """Raised when no identity adapter is configured.

    Distinct from `PasswordPolicyError`: one means "the password is not
    allowed", the other means "JUVAl is not wired to set passwords at all".
    Collapsing them would let a configuration mistake read as a policy pass.
    """


class PasswordProvisioningService:
    """Validate, then delegate. There is no other order."""

    def __init__(self, identity: Optional[IdentityPasswordPort] = None) -> None:
        self._identity = identity

    def validate(self, subject: PasswordSubject, password: str) -> PasswordPolicyResult:
        """Run Control 6 without setting anything.

        Exposed so a UI can pre-flight a password and show the reason before
        submitting. That is a convenience, never the control: `set_password`
        validates again regardless of whether this was called.
        """
        if not (subject.first_name or subject.last_name):
            raise PasswordProvisioningError(
                "Control 6 requires a first or last name; refusing to provision a "
                "password for a subject with neither (ADR-035)"
            )
        return check_password(password, subject.first_name, subject.last_name)

    def set_password(self, subject: PasswordSubject, password: str) -> PasswordPolicyResult:
        """Validate against Control 6, then hand the password to the IdP.

        Raises `PasswordPolicyError` when the rule fails -- carrying the
        structured result, never the password -- and never reaches the port in
        that case.
        """
        result = self.validate(subject, password)
        if not result.ok:
            # Log the *rule* and the subject, never the password and never the
            # matched substring of it.
            logger.warning(
                "password rejected by policy: user_id=%s rules=%s",
                subject.user_id,
                ",".join(sorted({v.rule.value for v in result.violations})),
            )
            raise PasswordPolicyError(result)

        if self._identity is None:
            raise PasswordProvisioningError(
                "no identity password adapter is configured; JUVAl holds no standing "
                "FusionAuth credential able to set a password (ADR-032, ADR-035 Condition 1)"
            )

        self._identity.set_password(subject, password)
        logger.info(
            "password set for user_id=%s (evidence_class=%s)",
            subject.user_id,
            EvidenceClass.VERIFIED_POLICY.value,
        )
        return result
