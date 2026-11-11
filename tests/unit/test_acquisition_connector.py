"""ADR-057/058 connector contract with synthetic fixtures and transport doubles only."""

from __future__ import annotations

import os
import socket

import pytest

from juval.domain.acquisition import ConfiguredSource, FailureCategory, ItemOutcome
from juval.domain.provenance import SourceType, VerificationStatus
from juval.infrastructure.enrichment.connector import (
    AuthorizedContract,
    ContractVerificationError,
    HttpResponse,
    RetryPolicy,
    TransportError,
    TransportTimeout,
    UnknownContractError,
    classify_status,
    verify_contract_document,
)
from juval.processing.acquisition_port import AcquisitionItem, ItemResult

from .acquisition_synthetic import (
    CONTRACT,
    EVIDENCE,
    SOURCE,
    SYNTHETIC_SPEC,
    T0,
    ScriptedTransport,
    connector,
    found,
    no_match,
    ok,
    status,
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def items(*ids: str) -> list[AcquisitionItem]:
    return [AcquisitionItem(f"row_{n}", identifier) for n, identifier in enumerate(ids, start=2)]


def outcome(result, n=0) -> ItemResult:
    return result.items[n]


# --- valid answers -------------------------------------------------------------


def test_valid_response_produces_values_with_the_source_provenance():
    transport = ScriptedTransport(ok(found("B0TEST0001", weight_lb=1.5)))
    result = connector(transport).acquire(items("B0TEST0001"))
    item = outcome(result)
    assert item.outcome is ItemOutcome.WITH_EVIDENCE and item.failure is None
    assert [v.field for v in item.values] == ["catalog_title", "catalog_weight"]
    for acquired in item.values:
        p = acquired.value.provenance
        assert p.source == SOURCE.source_id                       # PD-6
        assert p.source_type is SourceType.AUTHORIZED_EXTERNAL_SOURCE
        assert p.verification_status is VerificationStatus.INFERRED  # synthetic is never VERIFIED
        assert p.method.startswith("synthetic catalog lookup")     # method keeps its meaning
        assert SOURCE.source_id not in p.method and CONTRACT.sha256 not in p.method
        assert p.evidence == EVIDENCE and p.retrieved_at == T0
    assert (result.requests_sent, result.retries) == (1, 0)
    assert result.first_request_at == result.last_request_at == T0


def test_no_match_is_a_legitimate_not_found_not_a_failure():
    result = connector(ScriptedTransport(ok(no_match("B0TEST0001")))).acquire(items("B0TEST0001"))
    item = outcome(result)
    assert item.outcome is ItemOutcome.NO_EVIDENCE and item.failure is None
    assert item.values[0].value.provenance.verification_status is VerificationStatus.NOT_FOUND
    assert item.values[0].value.value is None


def test_invalid_provider_value_is_a_rejected_result():
    result = connector(ScriptedTransport(ok({"id": "B0TEST0001", "status": "FOUND", "title": "x",
                                             "weight_lb": -3}))).acquire(items("B0TEST0001"))
    statuses = [v.value.status for v in outcome(result).values]
    assert statuses == [VerificationStatus.INFERRED, VerificationStatus.INVALID]
    assert outcome(result).outcome is ItemOutcome.WITH_EVIDENCE  # §6 precedence: evidence wins


# --- operational failures: never NOT_FOUND ---------------------------------------


@pytest.mark.parametrize("code", [401, 403])
def test_auth_errors_are_configuration_failures_and_are_not_retried(code):
    transport = ScriptedTransport(status(code))
    sleeps: list = []
    result = connector(transport, sleeps=sleeps).acquire(items("B0TEST0001", "B0TEST0002"))
    assert [i.failure for i in result.items] == [FailureCategory.AUTH_OR_CONFIGURATION] * 2
    assert all(i.outcome is ItemOutcome.FAILED and i.values == () for i in result.items)
    assert len(transport.sent) == 1 and sleeps == [] and result.retries == 0


def test_429_is_retried_with_retry_after_then_succeeds():
    transport = ScriptedTransport(status(429, {"Retry-After": "7"}), ok(found("B0TEST0001")))
    sleeps: list = []
    result = connector(transport, sleeps=sleeps).acquire(items("B0TEST0001"))
    assert outcome(result).outcome is ItemOutcome.WITH_EVIDENCE
    assert sleeps == [7.0] and result.retries == 1 and result.requests_sent == 1
    assert len(transport.sent) == 2
    assert result.last_request_at > result.first_request_at


def test_429_exhausting_retries_is_throttled():
    transport = ScriptedTransport(status(429), status(429), status(429))
    sleeps: list = []
    result = connector(transport, max_retries=2, sleeps=sleeps).acquire(items("B0TEST0001"))
    assert outcome(result).failure is FailureCategory.THROTTLED
    assert sleeps == [1.0, 2.0] and result.retries == 2   # bounded exponential backoff, injected sleep


@pytest.mark.parametrize("code", [500, 503])
def test_5xx_is_a_source_failure_after_bounded_retries(code):
    transport = ScriptedTransport(status(code), status(code), status(code))
    result = connector(transport).acquire(items("B0TEST0001"))
    assert outcome(result).failure is FailureCategory.SOURCE_FAILURE
    assert len(transport.sent) == 3


def test_5xx_then_success_counts_the_retry():
    transport = ScriptedTransport(status(503), ok(no_match("B0TEST0001")))
    result = connector(transport).acquire(items("B0TEST0001"))
    assert outcome(result).outcome is ItemOutcome.NO_EVIDENCE and result.retries == 1


@pytest.mark.parametrize("error", [TransportTimeout("timed out"), TransportError("connection refused")])
def test_timeout_and_connection_errors_are_source_failures(error):
    result = connector(ScriptedTransport(error), max_retries=0).acquire(items("B0TEST0001"))
    assert outcome(result).failure is FailureCategory.SOURCE_FAILURE
    assert outcome(result).values == ()


@pytest.mark.parametrize("response", [
    HttpResponse(200, {}, b"not json"),
    HttpResponse(200, {}, b'{"items": [], "extra": 1}'),
    ok({"id": "B0TEST0001", "status": "FOUND"}),                 # FOUND without title
    ok({"id": "B0TEST0001", "status": "MAYBE"}),                 # status outside the contract
    ok({"id": "B0TEST0001", "status": "NO_MATCH", "rank": 3}),   # unknown key
    ok(found("B0TEST9999")),                                     # id that was not requested
    status(404),                                                 # status the contract does not handle
])
def test_malformed_or_out_of_contract_responses_are_schema_failures(response):
    transport = ScriptedTransport(response)
    sleeps: list = []
    result = connector(transport, sleeps=sleeps).acquire(items("B0TEST0001"))
    assert outcome(result).failure is FailureCategory.SCHEMA_FAILURE
    assert outcome(result).values == ()        # never a default or a NOT_FOUND
    assert sleeps == [] and len(transport.sent) == 1


def test_an_identifier_missing_from_a_valid_response_fails_only_that_item():
    result = connector(ScriptedTransport(ok(found("B0TEST0001")))).acquire(items("B0TEST0001", "B0TEST0002"))
    assert [i.outcome for i in result.items] == [ItemOutcome.WITH_EVIDENCE, ItemOutcome.FAILED]
    assert result.items[1].failure is FailureCategory.SCHEMA_FAILURE


# --- batching and identity -------------------------------------------------------


def test_batches_respect_the_contract_size_and_keep_item_order():
    transport = ScriptedTransport(ok(found("A1"), found("A2")), ok(no_match("A3")))
    result = connector(transport, batch=2).acquire(items("A1", "A2", "A3"))
    assert result.requests_sent == 2 and len(transport.sent) == 2
    assert [i.record_ref for i in result.items] == ["row_2", "row_3", "row_4"]
    assert [i.outcome for i in result.items] == [ItemOutcome.WITH_EVIDENCE] * 2 + [ItemOutcome.NO_EVIDENCE]


def test_records_sharing_an_identifier_are_requested_once_and_answered_each():
    transport = ScriptedTransport(ok(found("A1")))
    result = connector(transport).acquire([AcquisitionItem("row_2", "A1"), AcquisitionItem("row_3", "A1")])
    assert b'"ids": ["A1"]' in transport.sent[0][0].body
    assert [i.outcome for i in result.items] == [ItemOutcome.WITH_EVIDENCE] * 2


def test_a_record_is_consulted_once_per_source():
    with pytest.raises(ValueError, match="at most once"):
        connector(ScriptedTransport()).acquire([AcquisitionItem("row_2", "A1"), AcquisitionItem("row_2", "A2")])


# --- contract identity (ADR-057 D3) -------------------------------------------------


def test_unknown_contract_is_refused_before_any_request():
    transport = ScriptedTransport()
    other = ConfiguredSource(SOURCE.source_id, SOURCE.source_type, "synthetic-test/other/v9", SOURCE.contract_sha256)
    with pytest.raises(UnknownContractError):
        connector(transport, source=other)
    different_hash = ConfiguredSource(SOURCE.source_id, SOURCE.source_type, SOURCE.contract_id, "0" * 64)
    with pytest.raises(UnknownContractError):
        connector(transport, source=different_hash)
    assert transport.sent == []


def test_kept_contract_document_must_match_its_hash():
    verify_contract_document(SYNTHETIC_SPEC, CONTRACT)
    with pytest.raises(ContractVerificationError):
        verify_contract_document(SYNTHETIC_SPEC + b" ", CONTRACT)


@pytest.mark.parametrize("location", ["https://user:pw@synthetic.invalid/spec", "https://synthetic.invalid/spec?token=x"])
def test_contract_location_never_carries_credentials(location):
    with pytest.raises(ValueError, match="credentials"):
        AuthorizedContract(**{**CONTRACT.__dict__, "location": location})


def test_status_classification_table():
    assert classify_status(200) is None and classify_status(204) is None
    assert classify_status(401) is classify_status(403) is FailureCategory.AUTH_OR_CONFIGURATION
    assert classify_status(429) is FailureCategory.THROTTLED
    assert classify_status(500) is classify_status(503) is FailureCategory.SOURCE_FAILURE
    assert classify_status(400) is classify_status(404) is FailureCategory.SCHEMA_FAILURE


def test_retry_policy_bounds():
    policy = RetryPolicy(max_retries=5, base_delay_seconds=1, max_delay_seconds=4)
    assert [policy.delay(n, None) for n in range(4)] == [1, 2, 4, 4]
    assert policy.delay(0, HttpResponse(429, {"retry-after": "120"})) == 4   # capped
    assert policy.delay(0, HttpResponse(429, {"Retry-After": "Wed, 21 Oct 2026"})) == 1  # date form ignored
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1, base_delay_seconds=1, max_delay_seconds=1)


def test_no_credentials_or_real_endpoints_in_the_synthetic_contract():
    assert "JUVAL TEST SYNTHETIC" in CONTRACT.publisher
    assert CONTRACT.location.startswith("https://synthetic.invalid/")
    assert not any(name.startswith("JUVAL_") and "ACQUISITION" in name for name in os.environ)
