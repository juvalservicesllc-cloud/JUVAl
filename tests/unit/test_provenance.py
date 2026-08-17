from datetime import datetime, timezone

import pytest

from juval.domain.provenance import (
    FieldValue,
    Provenance,
    SourceType,
    VerificationStatus,
    combine_verification_status,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_verified_field_value_carries_a_value():
    fv = FieldValue.verified("B0EXAMPLE1", source="excel_input", method="direct_read", retrieved_at=NOW)
    assert fv.value == "B0EXAMPLE1"
    assert fv.status == VerificationStatus.VERIFIED
    assert fv.is_usable


def test_inferred_field_value_carries_a_value():
    fv = FieldValue.inferred(True, source="rule:hazmat_by_keyword", method="keyword_match", retrieved_at=NOW)
    assert fv.status == VerificationStatus.INFERRED
    assert fv.is_usable


def test_not_found_field_value_has_no_value():
    fv = FieldValue.not_found(source="official_api", method="lookup", retrieved_at=NOW)
    assert fv.value is None
    assert fv.status == VerificationStatus.NOT_FOUND
    assert not fv.is_usable


def test_not_found_cannot_carry_a_value():
    with pytest.raises(ValueError):
        FieldValue(
            value=42,
            provenance=Provenance(
                source="x",
                source_type=SourceType.USER_INPUT,
                verification_status=VerificationStatus.NOT_FOUND,
                retrieved_at=NOW,
                method="m",
            ),
        )


def test_verified_requires_a_value():
    with pytest.raises(ValueError):
        FieldValue(
            value=None,
            provenance=Provenance(
                source="x",
                source_type=SourceType.USER_INPUT,
                verification_status=VerificationStatus.VERIFIED,
                retrieved_at=NOW,
                method="m",
            ),
        )


def test_invalid_field_value_requires_raw_value_preserved():
    fv = FieldValue.invalid(
        "not-a-number", source="supplier_file", method="parse", retrieved_at=NOW, source_type=SourceType.SUPPLIER_FILE
    )
    assert fv.value is None
    assert fv.raw_value == "not-a-number"
    assert fv.status == VerificationStatus.INVALID
    assert not fv.is_usable


def test_invalid_without_raw_value_is_rejected():
    with pytest.raises(ValueError):
        FieldValue(
            value=None,
            provenance=Provenance(
                source="x",
                source_type=SourceType.SUPPLIER_FILE,
                verification_status=VerificationStatus.INVALID,
                retrieved_at=NOW,
                method="m",
            ),
        )


def test_verified_and_inferred_are_structurally_distinct():
    verified = FieldValue.verified(1, source="a", method="m", retrieved_at=NOW)
    inferred = FieldValue.inferred(1, source="a", method="m", retrieved_at=NOW)
    assert verified.status != inferred.status
    assert verified != inferred


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        Provenance(
            source="x",
            source_type=SourceType.USER_INPUT,
            verification_status=VerificationStatus.VERIFIED,
            retrieved_at=datetime(2026, 1, 1),  # no tzinfo
            method="m",
        )


def test_confidence_out_of_range_is_rejected():
    with pytest.raises(ValueError):
        Provenance(
            source="x",
            source_type=SourceType.USER_INPUT,
            verification_status=VerificationStatus.VERIFIED,
            retrieved_at=NOW,
            method="m",
            confidence=1.5,
        )


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ([VerificationStatus.VERIFIED, VerificationStatus.VERIFIED], VerificationStatus.VERIFIED),
        ([VerificationStatus.VERIFIED, VerificationStatus.INFERRED], VerificationStatus.INFERRED),
        ([VerificationStatus.VERIFIED, VerificationStatus.NOT_FOUND], VerificationStatus.NOT_FOUND),
        ([VerificationStatus.INFERRED, VerificationStatus.INVALID], VerificationStatus.NOT_FOUND),
        ([VerificationStatus.VERIFIED], VerificationStatus.VERIFIED),
    ],
)
def test_combine_verification_status_weakest_link(statuses, expected):
    assert combine_verification_status(statuses) == expected


def test_combine_verification_status_requires_at_least_one():
    with pytest.raises(ValueError):
        combine_verification_status([])
