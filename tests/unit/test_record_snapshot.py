"""Unit tests for application/record_snapshot.py -- specifically that
RiskFlag.severity's own provenance (ADR-020, FieldValue[Severity]) is
unwrapped correctly into the snapshot's hazmat_severity/bulky_severity
plain-string fields, without changing that field's shape (still a bare
string, not {value, status} -- API_CONTRACT.md unchanged) and without
crashing on a severity that could not be assessed (NOT_FOUND/INVALID).

Also covers the title/brand/category/height/width/length snapshot fields
added for P0 Record Intelligence (PRODUCT_CAPABILITY_MATRIX.md §3):
`record_to_snapshot` must faithfully relay whatever provenance the domain
already has for these fields -- never upgrade/invent a status.
"""

from datetime import datetime, timezone
from decimal import Decimal

from juval.application.record_snapshot import record_to_snapshot
from juval.domain.product import Dimensions, Identification, Product, ProductInfo
from juval.domain.provenance import FieldValue
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity
from juval.domain.sourcing_record import SourcingRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record_with_risk(*flags: RiskFlag) -> SourcingRecord:
    asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    product = Product(identification=Identification(asin=asin, marketplace="US"))
    return SourcingRecord(record_ref="row_1", product=product, risk=RiskProfile(flags=flags))


def test_policy_derived_severity_survives_as_plain_string():
    flag = RiskFlag(
        risk_type=RiskType.HAZMAT, status=RiskStatus.PRESENT,
        verification_status=FieldValue.verified(True, source="s", method="m", retrieved_at=NOW).status,
        severity=FieldValue.inferred(
            Severity.HIGH, source="DEFAULT_RISK_SEVERITY", method="ADR-010", retrieved_at=NOW,
        ),
        source="s", timestamp=NOW,
    )
    snapshot = record_to_snapshot(_record_with_risk(flag))

    assert snapshot["hazmat_severity"] == "HIGH"
    assert isinstance(snapshot["hazmat_severity"], str)


def test_unassessable_severity_maps_to_none_not_a_crash():
    flag = RiskFlag(
        risk_type=RiskType.HAZMAT, status=RiskStatus.UNKNOWN,
        verification_status=FieldValue.not_found(source="s", method="m", retrieved_at=NOW).status,
        severity=FieldValue.not_found(source="s", method="risk_presence_unknown", retrieved_at=NOW),
        source="s", timestamp=NOW,
    )
    snapshot = record_to_snapshot(_record_with_risk(flag))

    assert snapshot["hazmat_severity"] is None


def test_no_risk_flag_maps_to_none():
    snapshot = record_to_snapshot(_record_with_risk())
    assert snapshot["hazmat_severity"] is None
    assert snapshot["bulky_severity"] is None


def test_title_brand_category_dimensions_carry_their_real_provenance():
    from juval.domain.provenance import SourceType

    asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    info = ProductInfo(
        title=FieldValue.verified("Widget", source="supplier_file", method="direct_read", retrieved_at=NOW),
        brand=FieldValue.verified("Acme", source="supplier_file", method="direct_read", retrieved_at=NOW),
        category=FieldValue.invalid(
            "???", source="supplier_file", method="direct_read", retrieved_at=NOW,
            source_type=SourceType.SUPPLIER_FILE,
        ),
    )
    dims = Dimensions(
        height=FieldValue.verified(Decimal("4"), source="supplier_file", method="direct_read", retrieved_at=NOW, unit="in"),
        width=FieldValue.not_found(source="supplier_file", method="direct_read", retrieved_at=NOW),
    )
    product = Product(identification=Identification(asin=asin, marketplace="US"), info=info, dimensions=dims)
    record = SourcingRecord(record_ref="row_1", product=product)

    snapshot = record_to_snapshot(record)

    assert snapshot["title"] == {"value": "Widget", "status": "VERIFIED"}
    assert snapshot["brand"] == {"value": "Acme", "status": "VERIFIED"}
    # category failed validation upstream -- INVALID never carries a usable
    # `value` (only `raw_value`, which the snapshot doesn't expose), so the
    # snapshot must relay {value: None, status: INVALID}, never the raw text.
    assert snapshot["category"] == {"value": None, "status": "INVALID"}
    assert snapshot["height"] == {"value": "4", "status": "VERIFIED"}
    assert snapshot["width"] == {"value": None, "status": "NOT_FOUND"}
    # length was never given a FieldValue at all (info/dims default) -- must
    # be the same shape as an explicitly-not-found field, never a KeyError.
    assert snapshot["length"] == {"value": None, "status": None}


def test_absent_product_info_and_dimensions_never_invent_a_status():
    """A record whose importer found no title/brand/category/dimensions at
    all (ProductInfo()/Dimensions() all-default) must snapshot to
    {value: None, status: None} -- distinct from NOT_FOUND, which implies a
    field that was *looked for* and confirmed absent (ADR-004)."""

    asin = FieldValue.verified("B0EXAMPLE1", source="s", method="m", retrieved_at=NOW)
    product = Product(identification=Identification(asin=asin, marketplace="US"))
    record = SourcingRecord(record_ref="row_1", product=product)

    snapshot = record_to_snapshot(record)

    for field_name in ("title", "brand", "category", "height", "width", "length"):
        assert snapshot[field_name] == {"value": None, "status": None}
