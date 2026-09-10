"""Amazon Control 6 -- the rule JUVAl owns because FusionAuth does not (ADR-035).

Every name here is fictional. No real person's name and no real password
appears in this file, and no test asserts on a password value: the assertions
are on the *decision* and on which name component matched.
"""

from __future__ import annotations

import pytest

from juval.domain.password_policy import (
    MIN_TOKEN_LENGTH,
    EvidenceClass,
    PasswordPolicyError,
    PasswordPolicyRule,
    check_password,
    name_tokens,
    normalize,
)

FIRST = "Zzqxctrlsix"
LAST = "QqvxNamecheck"


def _rejected(result) -> bool:
    return not result.ok and all(
        v.rule is PasswordPolicyRule.CONTAINS_NAME_COMPONENT for v in result.violations
    )


# --- the two cases Amazon names explicitly -----------------------------


def test_rejects_password_containing_first_name():
    result = check_password(f"{FIRST}7!aQ", FIRST, LAST)
    assert _rejected(result)
    assert any(v.component == "first_name" for v in result.violations)


def test_rejects_password_containing_last_name():
    result = check_password(f"pre{LAST}7!aQ", FIRST, LAST)
    assert _rejected(result)
    assert any(v.component == "last_name" for v in result.violations)


def test_accepts_control_password_containing_neither():
    result = check_password("Wholly1Unrelated!Zq", FIRST, LAST)
    assert result.ok
    assert result.violations == ()


# --- normalization: the ways a match could otherwise be evaded ---------


@pytest.mark.parametrize(
    "password",
    [
        "ZZQXCTRLSIX7!aQ",      # upper
        "zzqxctrlsix7!aQ",      # lower
        "ZzQxCtRlSiX7!aQ",      # mixed
    ],
)
def test_matching_is_case_insensitive(password):
    assert _rejected(check_password(password, FIRST, LAST))


def test_matching_ignores_diacritics():
    # NFKD strips the combining marks, so the accented name is still found.
    assert _rejected(check_password("xMuller9!abcQ", "Müller", None))
    assert _rejected(check_password("xMüller9!abcQ", "Muller", None))


def test_normalize_folds_sharp_s():
    # casefold(), not lower(): "ß" -> "ss". lower() would leave them different.
    assert normalize("Straße") == normalize("STRASSE")


def test_matching_survives_surrounding_whitespace_in_the_name():
    assert _rejected(check_password("xZzqxctrlsix9!aQ", f"  {FIRST}  ", LAST))


# --- multi-part names --------------------------------------------------


def test_hyphenated_name_matches_each_part_and_the_whole():
    tokens = name_tokens("Ana-Maria")
    assert "ana" in tokens and "maria" in tokens and "anamaria" in tokens
    assert _rejected(check_password("xxAnaMaria9!Qz", "Ana-Maria", None))
    assert _rejected(check_password("xxmaria9!Qz", "Ana-Maria", None))


def test_apostrophe_name_matches_the_meaningful_part():
    # "O" is below MIN_TOKEN_LENGTH and is not searched for; "neill" is.
    assert _rejected(check_password("xxNeill9!Qzab", "Fictional", "O'Neill"))


def test_particled_name_matches_run_together_form():
    assert _rejected(check_password("Xanadu9!vanderberg", "van der", "Berg"))


def test_first_and_last_run_together_are_caught():
    # Neither single-field check would see this; the "combined" pass does.
    result = check_password(f"aa{FIRST}{LAST}9!Q", FIRST, LAST)
    assert _rejected(result)


# --- false positives: the reason MIN_TOKEN_LENGTH exists ---------------


def test_short_name_components_are_not_enforced():
    # A two-letter surname would otherwise reject "king", "strong", "morning".
    assert check_password("TheKingIsStrong9!", "Fictionalfirst", "Ng").ok


def test_short_token_threshold_is_explicit():
    assert MIN_TOKEN_LENGTH == 3
    assert name_tokens("Al") == ()


def test_ordinary_password_with_common_words_is_accepted():
    assert check_password("Correct9!HorseBattery", "Zzqxctrlsix", "Qqvxnamecheck").ok


def test_subject_without_any_name_passes_vacuously():
    # Documented limit, not an accident: provisioning refuses a nameless
    # subject (see PasswordProvisioningService.validate).
    assert check_password("Anything9!AtAll", None, None).ok


# --- result contract ---------------------------------------------------


def test_result_is_verified_policy_not_amazon_compliance():
    result = check_password("Wholly1Unrelated!Zq", FIRST, LAST)
    assert result.evidence_class is EvidenceClass.VERIFIED_POLICY
    assert result.evidence_class is not EvidenceClass.AMAZON_VERIFIED_COMPLIANCE


def test_violation_never_carries_the_password():
    password = f"{FIRST}7!aQsecretpart"
    result = check_password(password, FIRST, LAST)
    for violation in result.violations:
        assert violation.token in normalize(FIRST) + normalize(LAST)
        assert "secretpart" not in violation.token
        assert password not in violation.message()


def test_raise_if_violated_message_does_not_leak_the_password():
    password = f"{LAST}9!aQ"
    with pytest.raises(PasswordPolicyError) as exc:
        check_password(password, FIRST, LAST).raise_if_violated()
    assert password not in str(exc.value)
    assert exc.value.result.violations
