"""ADR-058 domain invariants, canonical documents and derivation from provenance."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from juval.application.acquisition_documents import (
    ACQUIRED_EVIDENCE_KEY,
    AcquisitionDocumentError,
    AcquisitionIntegrityError,
    acquired_evidence_document,
    canonical_json,
    check_integrity,
    columns_for_write,
    configuration_document,
    derive_value_counts,
    execution_document,
    parse_configuration,
    parse_execution,
    record_from_columns,
)
from juval.domain.acquisition import (
    PLACEHOLDER_SOURCES,
    AcquisitionConfiguration,
    AcquisitionExecution,
    AcquisitionRecord,
    ConfiguredSource,
    FailureCategory,
    ItemCounts,
    ItemOutcome,
    NotConsultedReason,
    SourceExecution,
    ValueCounts,
    validate_source_id,
)
from juval.domain.provenance import FieldValue, SourceType
from juval.processing import data_quality
from juval.processing.acquisition_port import AcquiredValue, ItemResult

T0 = datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc)
SHA = "a" * 64
SRC = "synthetic-test/catalog-lookup"


def failed(**counts) -> dict:
    return {c: counts.get(c.value, 0) for c in FailureCategory}


def source(source_id: str = SRC) -> ConfiguredSource:
    return ConfiguredSource(source_id, SourceType.AUTHORIZED_EXTERNAL_SOURCE, "synthetic-test/contract/v1", SHA)


def consulted(source_id: str = SRC, *, used=1, not_found=1, invalid=0) -> SourceExecution:
    return SourceExecution(source_id, T0, T0 + timedelta(seconds=3), 2, 1,
                           ItemCounts(4, 1, 1, 0, failed(THROTTLED=1, SOURCE_FAILURE=1)),
                           ValueCounts(used, not_found, invalid), 0, None)


def not_consulted(source_id: str = SRC, reason=NotConsultedReason.NO_ELIGIBLE_RECORDS) -> SourceExecution:
    return SourceExecution(source_id, None, None, 0, 0, ItemCounts.empty(), ValueCounts(0, 0, 0), 0, reason)


def record(*entries: SourceExecution) -> AcquisitionRecord:
    return AcquisitionRecord(AcquisitionConfiguration(T0, tuple(source(e.source_id) for e in entries)),
                             AcquisitionExecution(entries))


def acquired_snapshot(*values: FieldValue, ref: str = "row_2") -> dict:
    return {"record_ref": ref, "asin": {"value": "B0TEST", "status": "VERIFIED", "provenance": {
        "source": "file.xlsx", "source_type": "SUPPLIER_FILE", "verification_status": "VERIFIED"}},
        ACQUIRED_EVIDENCE_KEY: acquired_evidence_document(
            [(v.provenance.source, f"field_{n}", v) for n, v in enumerate(values)])}


def ext(status: str, source_id: str = SRC) -> FieldValue:
    common = dict(source=source_id, method="synthetic", retrieved_at=T0, source_type=SourceType.AUTHORIZED_EXTERNAL_SOURCE)
    return {"used": lambda: FieldValue.inferred("x", **common), "not_found": lambda: FieldValue.not_found(**common),
            "invalid": lambda: FieldValue.invalid("bad", **common)}[status]()


# --- domain invariants ---------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "nosplit", "UPPER/case", "a/b/c", "/x", "x/", "n/a", "a /b"])
def test_source_id_shape_and_placeholders(bad):
    with pytest.raises(ValueError):
        validate_source_id(bad)
    assert validate_source_id("sp-api/catalog-items") == "sp-api/catalog-items"


def test_placeholder_sources_mirror_processing():  # ADR-058 P10
    assert PLACEHOLDER_SOURCES == data_quality._PLACEHOLDER_SOURCES


@pytest.mark.parametrize("source_type", [SourceType.SUPPLIER_FILE, SourceType.USER_INPUT, SourceType.CALCULATED,
                                         SourceType.DATABASE, SourceType.AI_ANALYSIS])
def test_only_external_source_types_can_be_configured(source_type):
    with pytest.raises(ValueError, match="external"):
        ConfiguredSource(SRC, source_type, "c", SHA)


def test_configuration_rejects_duplicates_and_naive_instants():
    with pytest.raises(ValueError, match="more than once"):
        AcquisitionConfiguration(T0, (source(), source()))
    with pytest.raises(ValueError, match="timezone-aware"):
        AcquisitionConfiguration(datetime(2026, 11, 11), ())


def test_item_counts_must_add_up():  # I2
    with pytest.raises(ValueError, match="sum"):
        ItemCounts(3, 1, 1, 0, failed())
    with pytest.raises(ValueError, match="FailureCategory"):
        ItemCounts(0, 0, 0, 0, {})


@pytest.mark.parametrize("kwargs, message", [
    (dict(requests_sent=0), "requests_sent"),                                   # I3
    (dict(not_consulted_reason=NotConsultedReason.NO_ELIGIBLE_RECORDS), "not_consulted_reason"),
    (dict(first_request_at=None), "instants"),
    (dict(values=ValueCounts(0, 1, 0)), "evidence exist exactly"),              # I4
    (dict(values=ValueCounts(1, 0, 0)), "NOT_FOUND"),                           # I4
    (dict(last_request_at=T0 - timedelta(seconds=1)), "precedes"),
])
def test_source_execution_invariants(kwargs, message):
    base = consulted().__dict__
    with pytest.raises(ValueError, match=message):
        SourceExecution(**{**base, **kwargs})


def test_unconsulted_source_has_no_values_or_retries():
    with pytest.raises(ValueError):
        SourceExecution(SRC, None, None, 0, 0, ItemCounts.empty(), ValueCounts(1, 0, 0), 0,
                        NotConsultedReason.NO_ELIGIBLE_RECORDS)
    with pytest.raises(ValueError):
        SourceExecution(SRC, None, None, 0, 1, ItemCounts.empty(), ValueCounts(0, 0, 0), 0,
                        NotConsultedReason.NO_ELIGIBLE_RECORDS)


def test_record_needs_one_execution_entry_per_configured_source():  # I1
    with pytest.raises(ValueError, match="one entry per configured source"):
        AcquisitionRecord(AcquisitionConfiguration(T0, (source(),)), AcquisitionExecution(()))


def test_item_outcome_precedence_is_computed_not_chosen():  # ADR-058 §6
    used, nf, inv = ext("used"), ext("not_found"), ext("invalid")
    assert ItemResult.from_values("r", [AcquiredValue("a", nf), AcquiredValue("b", used)]).outcome is ItemOutcome.WITH_EVIDENCE
    assert ItemResult.from_values("r", [AcquiredValue("a", nf), AcquiredValue("b", inv)]).outcome is ItemOutcome.REJECTED
    assert ItemResult.from_values("r", [AcquiredValue("a", nf)], 1).outcome is ItemOutcome.REJECTED
    assert ItemResult.from_values("r", [AcquiredValue("a", nf)]).outcome is ItemOutcome.NO_EVIDENCE
    with pytest.raises(ValueError, match="at least one value"):
        ItemResult.from_values("r", [])
    with pytest.raises(ValueError, match="precedence"):
        ItemResult("r", ItemOutcome.NO_EVIDENCE, None, (AcquiredValue("a", used),))
    with pytest.raises(ValueError, match="never NOT_FOUND"):
        ItemResult("r", ItemOutcome.FAILED, FailureCategory.THROTTLED, (AcquiredValue("a", nf),))


# --- canonical documents (ADR-058 §5) ----------------------------------------------------


def test_documents_round_trip_byte_identically():
    rec = record(consulted(), not_consulted("synthetic-test/other-op"))
    config_text, execution_text = columns_for_write(rec, [acquired_snapshot(ext("used"), ext("not_found"))])
    assert config_text == canonical_json(json.loads(config_text))
    assert " " not in config_text and " " not in execution_text
    loaded = record_from_columns(config_text, execution_text)
    assert loaded == rec
    assert canonical_json(configuration_document(loaded.configuration)) == config_text
    assert canonical_json(execution_document(loaded.execution)) == execution_text
    doc = json.loads(execution_text)
    assert doc["format"] == "juval.adr058.acquisition-execution" and doc["version"] == 1
    assert [s["source_id"] for s in doc["sources"]] == sorted(s["source_id"] for s in doc["sources"])


def test_empty_sources_is_recorded_and_distinct_from_not_recorded():
    empty = AcquisitionRecord(AcquisitionConfiguration(T0, ()), AcquisitionExecution(()))
    assert record_from_columns(*columns_for_write(empty, [])) == empty
    assert record_from_columns(None, None) is None  # NOT_RECORDED


def test_one_null_column_is_an_integrity_error():  # P3
    config_text, execution_text = columns_for_write(record(not_consulted()), [])
    with pytest.raises(AcquisitionDocumentError, match="P3"):
        record_from_columns(config_text, None)
    with pytest.raises(AcquisitionDocumentError, match="P3"):
        record_from_columns(None, execution_text)


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(format="juval.adr058.other"),
    lambda d: d.update(version=2),
    lambda d: d.update(version=True),
    lambda d: d.update(extra=1),
    lambda d: d["sources"][0].update(source_type="SUPPLIER_FILE"),
    lambda d: d["sources"][0].update(contract_sha256="xyz"),
])
def test_configuration_is_read_strictly(mutate):  # P4
    text, _ = columns_for_write(record(not_consulted()), [])
    data = json.loads(text)
    mutate(data)
    with pytest.raises(AcquisitionDocumentError):
        parse_configuration(canonical_json(data))


@pytest.mark.parametrize("mutate", [
    lambda d: d["sources"][0]["items"]["failed"].pop("THROTTLED"),
    lambda d: d["sources"][0]["items"].update(requested=99),
    lambda d: d["sources"][0].update(not_consulted_reason="BUDGET_EXHAUSTED"),
    lambda d: d["sources"][0]["values"].update(used=-1),
])
def test_execution_is_read_strictly(mutate):
    _, text = columns_for_write(record(consulted()), [acquired_snapshot(ext("used"), ext("not_found"))])
    data = json.loads(text)
    mutate(data)
    with pytest.raises(AcquisitionDocumentError):
        parse_execution(canonical_json(data))


def test_non_canonical_or_nan_text_is_refused():
    config_text, execution_text = columns_for_write(record(not_consulted()), [])
    with pytest.raises(AcquisitionDocumentError, match="canonical"):
        parse_configuration(json.dumps(json.loads(config_text), indent=1))
    with pytest.raises(AcquisitionDocumentError):
        parse_execution(execution_text.replace('"retries":0', '"retries":NaN'))


# --- derivation and integrity (ADR-058 §7, P6, P7) -----------------------------------------


def test_derivation_counts_only_external_values_by_source():
    snapshots = [acquired_snapshot(ext("used"), ext("not_found"), ext("invalid")),
                 acquired_snapshot(ext("used", "synthetic-test/other-op"), ref="row_3")]
    financial = [{"term": {"value": "1", "provenance": {
        "source": "juval-api", "source_type": "USER_INPUT", "verification_status": "VERIFIED"}}}]
    assert derive_value_counts(snapshots, financial) == {
        SRC: ValueCounts(1, 1, 1), "synthetic-test/other-op": ValueCounts(1, 0, 0)}


def test_derivation_includes_adr047_financial_documents():
    financial = [{"fees": [{"value": "3.10", "provenance": {
        "source": SRC, "source_type": "OFFICIAL_API", "verification_status": "VERIFIED"}}]}]
    assert derive_value_counts([], financial) == {SRC: ValueCounts(1, 0, 0)}


def test_recorded_counts_must_match_persisted_provenance():  # P7
    snapshots = [acquired_snapshot(ext("used"), ext("not_found"))]
    check_integrity(record(consulted()), snapshots)
    with pytest.raises(AcquisitionIntegrityError, match="differ"):
        check_integrity(record(consulted(used=2)), snapshots)


def test_values_from_an_unconfigured_source_are_refused():  # P6
    snapshots = [acquired_snapshot(ext("used"), ext("not_found"), ext("used", "synthetic-test/rogue"))]
    with pytest.raises(AcquisitionIntegrityError, match="unconfigured"):
        check_integrity(record(consulted()), snapshots)
    with pytest.raises(AcquisitionIntegrityError, match="without an acquisition record"):
        check_integrity(None, snapshots)


def test_historical_snapshots_without_external_values_stay_not_recorded():
    legacy = [{"record_ref": "row_2", "asin": {"value": "B0", "status": "VERIFIED", "provenance": {
        "source": "f.xlsx", "source_type": "SUPPLIER_FILE", "verification_status": "VERIFIED"}}},
              {"record_ref": "row_3", "asin": {"value": None, "status": None, "provenance": None}}]
    assert columns_for_write(None, legacy) == (None, None)


def test_acquired_evidence_document_is_versioned_and_rejects_duplicate_fields():
    doc = acquired_evidence_document([(SRC, "b", ext("used")), (SRC, "a", ext("not_found"))])
    assert doc["format"] == "juval.adr058.acquired-evidence" and doc["version"] == 1
    assert [v["field"] for v in doc["values"]] == ["a", "b"]
    assert doc["values"][1]["value"]["provenance"]["source"] == SRC
    with pytest.raises(ValueError, match="twice"):
        acquired_evidence_document([(SRC, "a", ext("used")), (SRC, "a", ext("used"))])
