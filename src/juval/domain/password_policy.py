"""Amazon Control 6 -- a password must not contain any part of the user's name.

Why this lives in `domain/` and not in the API layer or the frontend
-------------------------------------------------------------------
This is a business rule about a value, expressed as a pure function of that
value: no HTTP, no IdP, no I/O (ADR-001). It is also a *security* rule, so it
must sit where every caller has to pass through it, not where a caller may
choose to. A frontend check is a courtesy to the user; it is never a control
(the same reasoning `interfaces/api/auth.py` applies to RBAC).

Why the rule exists
-------------------
Amazon's Key Security Control Guidance, mapped to Data Protection Policy
Sec. 1.4 (general requirements, *not* the PII-specific Sec. 2), requires:
"minimum 12 characters with mixed case letters, numbers, and special
characters, and must not include any part of the user's name."

FusionAuth 1.69.0 implements the composition half natively. It does **not**
implement the name half: `disallowUserLoginId` matches the full login
identifier only. Measured in an isolated 1.69.0 lab (2026-09-09,
docs/research/FUSIONAUTH_169_IDENTITY_LAB.md Sec. 9.6): a password containing
`firstName` or `lastName` is accepted even with that flag on, while the full
email/username is rejected with `containsEmail`/`containsUsername`. That is
FusionAuth implementing the rule it documents -- not a defect -- and it is why
JUVAl owns this one rule (ADR-035).

Evidence classification
-----------------------
A pass from this module is `VERIFIED_POLICY`: the password satisfies the rule
JUVAl implements. It is **not** `AMAZON_VERIFIED_COMPLIANCE`, which would
require production behavioral evidence over every real password-setting path.
`PasswordPolicyResult.evidence_class` carries this so a caller cannot lose it.

Secret handling
---------------
The password is read, never stored, never logged, never echoed. A violation
reports which *name* component matched (the user's own name, not a secret) and
never the password, nor the matched substring of it.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Tuple

#: Name tokens shorter than this are not searched for.
#:
#: A one- or two-character token ("Al", "Ng", "Li", a middle initial) appears
#: inside a large share of ordinary strings -- "Ng" alone would reject "king",
#: "strong", "morning". Enforcing it would push users toward *worse* passwords
#: by rejecting good ones, which is a security loss, not a gain. Three is the
#: shortest length at which the false-positive rate stops dominating.
#:
#: This is a disclosed residual, not a silent one: a name component of one or
#: two characters is NOT excluded from passwords. ADR-035 records it, and
#: `SHORT_TOKEN_RESIDUAL` below names it so a caller can surface it.
MIN_TOKEN_LENGTH = 3

SHORT_TOKEN_RESIDUAL = (
    f"name components shorter than {MIN_TOKEN_LENGTH} characters are not enforced "
    "(false-positive rate would exceed the control's value); disclosed in ADR-035"
)

#: Characters that separate one name component from another. Hyphenated
#: ("Ana-Maria"), apostrophised ("O'Neill"), particled ("van der Berg") and
#: comma-ordered ("Smith, John") names all decompose here, so each *part* is
#: checked independently as well as the whole.
_SEPARATORS = " \t\r\n-_.,'’/\\()[]"

#: The class of evidence a passing result constitutes. Deliberately an enum of
#: exactly two members so no caller can invent a third, stronger one.
class EvidenceClass(str, Enum):
    VERIFIED_POLICY = "VERIFIED_POLICY"
    AMAZON_VERIFIED_COMPLIANCE = "AMAZON_VERIFIED_COMPLIANCE"


class PasswordPolicyRule(str, Enum):
    """Only the rules JUVAl owns. Length/composition/history/breach stay with
    the IdP (ADR-021 control-ownership matrix) and are deliberately absent."""

    CONTAINS_NAME_COMPONENT = "containsNameComponent"


@dataclass(frozen=True)
class PasswordPolicyViolation:
    """One failed rule.

    `component` says which field the match came from (`first_name`,
    `last_name`, `combined`) and `token` is the *name* token that matched --
    the user's own name, never any part of the password.
    """

    rule: PasswordPolicyRule
    component: str
    token: str

    def message(self) -> str:
        return "password must not contain any part of your name"


@dataclass(frozen=True)
class PasswordPolicyResult:
    ok: bool
    violations: Tuple[PasswordPolicyViolation, ...] = ()
    evidence_class: EvidenceClass = EvidenceClass.VERIFIED_POLICY

    def raise_if_violated(self) -> None:
        if not self.ok:
            raise PasswordPolicyError(self)


class PasswordPolicyError(ValueError):
    """Raised when a password fails the rule.

    Carries the structured result, never the password. `str(exc)` is a fixed,
    non-revealing sentence so the exception is safe to log and safe to return.
    """

    def __init__(self, result: PasswordPolicyResult) -> None:
        super().__init__("password rejected by JUVAl password policy")
        self.result = result


def normalize(value: str) -> str:
    """Fold away the differences an attacker would otherwise use to slip past.

    NFKD decomposes accented characters into base + combining mark; dropping
    the marks makes `Muller` match `Müller` and `Jose` match `José`. Casefold
    (not `lower()`) handles the cases `lower()` gets wrong, e.g. German sharp s
    folds to `ss`, so `Straße` and `STRASSE` compare equal.

    Deliberately NOT done here: leetspeak folding (`4` -> `a`, `0` -> `o`).
    Adding it would reject `pa55w0rd`-shaped passwords for a user named "Ass"
    or "Boo" and, more importantly, is not what Amazon asks for. It is recorded
    in ADR-035 as an accepted, disclosed gap rather than an unowned one.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold()


def name_tokens(*names: Optional[str]) -> Tuple[str, ...]:
    """Normalized, deduplicated tokens worth searching for.

    Each name is split on `_SEPARATORS`; every part at least
    `MIN_TOKEN_LENGTH` long is a token. The whole normalized name is a token
    too when it survives the length test, so "van der Berg" contributes
    "vanderberg" as well as "van", "der" and "berg" -- a password containing
    the run-together form is caught even though no single part appears.
    """
    tokens: list[str] = []
    for name in names:
        if not name:
            continue
        normalized = normalize(name)
        parts = [p for p in _split(normalized) if len(p) >= MIN_TOKEN_LENGTH]
        tokens.extend(parts)
        collapsed = "".join(_split(normalized))
        if len(collapsed) >= MIN_TOKEN_LENGTH:
            tokens.append(collapsed)
    # dedupe, preserving order so violations are reported deterministically
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return tuple(ordered)


def _split(normalized: str) -> Iterable[str]:
    out: list[str] = []
    current: list[str] = []
    for ch in normalized:
        if ch in _SEPARATORS:
            if current:
                out.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        out.append("".join(current))
    return out


def check_password(
    password: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> PasswordPolicyResult:
    """Amazon Control 6: reject a password containing any part of the name.

    Returns a structured result rather than a bare bool so the caller can
    report *which* component matched without ever touching the password.

    A user with no name on record yields a pass: there is nothing to exclude.
    That is a real limit of the control and is recorded in ADR-035 -- names are
    required at provisioning precisely so this cannot become a silent hole.
    """
    haystack = normalize(password)
    violations: list[PasswordPolicyViolation] = []

    for component, value in (("first_name", first_name), ("last_name", last_name)):
        for token in name_tokens(value):
            if token in haystack:
                violations.append(
                    PasswordPolicyViolation(
                        rule=PasswordPolicyRule.CONTAINS_NAME_COMPONENT,
                        component=component,
                        token=token,
                    )
                )

    # first+last and last+first run together ("johnsmith", "smithjohn") are
    # name parts too, and neither single-field pass above would see them.
    for component, joined in (
        ("combined", f"{first_name or ''}{last_name or ''}"),
        ("combined", f"{last_name or ''}{first_name or ''}"),
    ):
        for token in name_tokens(joined):
            if token in haystack and not any(v.token == token for v in violations):
                violations.append(
                    PasswordPolicyViolation(
                        rule=PasswordPolicyRule.CONTAINS_NAME_COMPONENT,
                        component=component,
                        token=token,
                    )
                )

    return PasswordPolicyResult(ok=not violations, violations=tuple(violations))
