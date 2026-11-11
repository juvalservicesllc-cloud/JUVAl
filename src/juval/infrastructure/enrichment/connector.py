"""Reusable machinery for authorized connectors (ADR-057, ADR-058).

What a concrete adapter supplies is an `OperationContract`: how to build the
request for some identifiers and how to validate and normalize the response,
both taken from the provider's authorized specification (ADR-057 D3). This
module does everything else, the same way for every provider:

* checks that the configured source names exactly that contract (an unknown
  contract or a different hash stops construction, i.e. startup);
* sends through an injected `Transport` -- there is no network code here and
  no default transport, so nothing can reach a provider unless a caller hands
  one in;
* classifies outcomes (DATA_SOURCES.md §1b): 401/403 -> AUTH_OR_CONFIGURATION,
  429 -> THROTTLED, 5xx/timeout/connection -> SOURCE_FAILURE, any other status
  or a response that breaks the contract -> SCHEMA_FAILURE. None is NOT_FOUND;
* retries only THROTTLED and SOURCE_FAILURE, a bounded number of times, waiting
  through an injected `sleep` (never a scattered fixed sleep);
* gives the adapter a `ValueFactory` that stamps every value with
  `Provenance.source = source_id`, the configured source type and the request
  instant, and leaves `Provenance.method` to the adapter (ADR-058 §3).

No adapter, provider, credential or transport implementation lives here.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence
from urllib.parse import urlsplit

from juval.domain.acquisition import ConfiguredSource, FailureCategory
from juval.domain.provenance import FieldValue
from juval.domain.sourcing_record import SourcingRecord
from juval.processing.acquisition_port import (
    AcquiredValue,
    AcquisitionItem,
    ItemResult,
    SourceAcquisitionResult,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ORIGINS = frozenset({"PUBLISHED", "AGREEMENT"})


class UnknownContractError(ValueError):
    """The configured source does not name the operation's authorized contract."""


class ContractVerificationError(ValueError):
    """The kept contract document does not hash to the recorded sha256 (D3.3)."""


class SchemaViolation(ValueError):
    """A provider response does not satisfy the authorized contract."""


class TransportTimeout(Exception):
    """The transport gave up waiting for the provider."""


class TransportError(Exception):
    """The transport could not reach the provider (connection, TLS, DNS)."""


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


@dataclass(frozen=True)
class AuthorizedContract:
    """ADR-057 D3.2: identification of one authorized contract document."""

    contract_id: str
    origin: str
    publisher: str
    version: str
    location: str
    sha256: str
    media_type: str
    obtained_at: datetime
    obtained_by: str
    approved_by: str
    approved_at: datetime

    def __post_init__(self) -> None:
        for name in ("contract_id", "publisher", "version", "location", "media_type", "obtained_by", "approved_by"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"AuthorizedContract.{name} must not be empty")
        if self.origin not in _ORIGINS:
            raise ValueError(f"AuthorizedContract.origin must be one of {sorted(_ORIGINS)}")
        if not _SHA256.match(self.sha256):
            raise ValueError("AuthorizedContract.sha256 must be 64 lowercase hex characters")
        _aware(self.obtained_at, "AuthorizedContract.obtained_at")
        _aware(self.approved_at, "AuthorizedContract.approved_at")
        url = urlsplit(self.location)
        if url.scheme in ("http", "https") and (url.username or url.password or url.query or url.fragment):
            raise ValueError("AuthorizedContract.location must not carry credentials, tokens or parameters")


def verify_contract_document(document: bytes, contract: AuthorizedContract) -> None:
    """D3.3: the exact kept bytes must hash to the recorded sha256."""
    if hashlib.sha256(document).hexdigest() != contract.sha256:
        raise ContractVerificationError(f"{contract.contract_id}: kept document does not match its recorded sha256")


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...] = ()
    body: Optional[bytes] = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def header(self, name: str) -> Optional[str]:
        return next((v for k, v in self.headers.items() if k.lower() == name.lower()), None)


class Transport(Protocol):
    def send(self, request: HttpRequest, *, timeout: float) -> HttpResponse:
        """Raises TransportTimeout or TransportError; never retries on its own."""
        ...


class ValueFactory:
    """Builds the FieldValues of one response with the source's provenance.

    `method` is the adapter's description of how the provider obtained or
    derived the value (ADR-046 §9); it never carries the source id or a hash.
    """

    def __init__(self, source: ConfiguredSource, retrieved_at: datetime) -> None:
        self._source = source
        self._retrieved_at = retrieved_at

    def _common(self, method: str, evidence: Optional[str], source_reference: Optional[str]) -> dict[str, Any]:
        return dict(source=self._source.source_id, method=method, retrieved_at=self._retrieved_at,
                    evidence=evidence, source_reference=source_reference)

    def verified(self, value: Any, *, method: str, unit: Optional[str] = None, evidence: Optional[str] = None,
                 source_reference: Optional[str] = None) -> FieldValue[Any]:
        return FieldValue.verified(value, source_type=self._source.source_type, unit=unit,
                                   **self._common(method, evidence, source_reference))

    def inferred(self, value: Any, *, method: str, unit: Optional[str] = None, evidence: Optional[str] = None,
                 source_reference: Optional[str] = None) -> FieldValue[Any]:
        return FieldValue.inferred(value, source_type=self._source.source_type, unit=unit,
                                   **self._common(method, evidence, source_reference))

    def not_found(self, *, method: str, evidence: Optional[str] = None,
                  source_reference: Optional[str] = None) -> FieldValue[Any]:
        """The query succeeded and the provider stated there is no value."""
        return FieldValue.not_found(source_type=self._source.source_type,
                                    **self._common(method, evidence, source_reference))

    def invalid(self, raw_value: Any, *, method: str, evidence: Optional[str] = None,
                source_reference: Optional[str] = None) -> FieldValue[Any]:
        return FieldValue.invalid(raw_value, source_type=self._source.source_type,
                                  **self._common(method, evidence, source_reference))


@dataclass(frozen=True)
class ParsedItem:
    """What the contract made of one identifier in a valid response."""

    values: tuple[AcquiredValue, ...]
    observation_contract_rejected: int = 0


class OperationContract(Protocol):
    """The adapter-specific part, written from the authorized specification."""

    contract: AuthorizedContract
    max_batch_size: int
    #: Non-2xx statuses the contract defines as a valid answer (e.g. 404 = no
    #: match); they go to `parse_response` instead of being classified.
    handled_statuses: frozenset[int]

    def identifier_for(self, record: SourcingRecord) -> Optional[str]: ...

    def build_request(self, identifiers: Sequence[str]) -> HttpRequest: ...

    def parse_response(self, response: HttpResponse, identifiers: Sequence[str],
                       values: ValueFactory) -> Mapping[str, ParsedItem]:
        """Strictly validate and normalize. Raise SchemaViolation for anything
        outside the contract; never fill a missing value with a default."""
        ...


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retries for THROTTLED and SOURCE_FAILURE only."""

    max_retries: int
    base_delay_seconds: float
    max_delay_seconds: float

    def __post_init__(self) -> None:
        if self.max_retries < 0 or self.base_delay_seconds < 0 or self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("RetryPolicy needs max_retries >= 0 and 0 <= base_delay <= max_delay")

    def delay(self, retry: int, response: Optional[HttpResponse]) -> float:
        after = response.header("Retry-After") if response is not None else None
        if after is not None and after.strip().isdigit():
            return min(float(after.strip()), self.max_delay_seconds)
        return min(self.base_delay_seconds * (2 ** retry), self.max_delay_seconds)


_RETRYABLE = frozenset({FailureCategory.THROTTLED, FailureCategory.SOURCE_FAILURE})


def classify_status(status: int) -> Optional[FailureCategory]:
    """None for a 2xx answer; otherwise the failure category (§1b)."""
    if 200 <= status < 300:
        return None
    if status in (401, 403):
        return FailureCategory.AUTH_OR_CONFIGURATION
    if status == 429:
        return FailureCategory.THROTTLED
    if 500 <= status < 600:
        return FailureCategory.SOURCE_FAILURE
    return FailureCategory.SCHEMA_FAILURE


class AuthorizedHttpConnector:
    """Implements processing/acquisition_port.py::AuthorizedConnector."""

    def __init__(self, source: ConfiguredSource, operation: OperationContract, transport: Transport, *,
                 retry: RetryPolicy, timeout_seconds: float, clock: Callable[[], datetime],
                 sleep: Callable[[float], None]) -> None:
        contract = operation.contract
        if source.contract_id != contract.contract_id or source.contract_sha256 != contract.sha256:
            raise UnknownContractError(
                f"{source.source_id}: configured contract {source.contract_id}@{source.contract_sha256[:12]} is not "
                f"the operation's authorized contract {contract.contract_id}@{contract.sha256[:12]}")
        if operation.max_batch_size < 1:
            raise ValueError(f"{source.source_id}: max_batch_size must be >= 1")
        if timeout_seconds <= 0:
            raise ValueError(f"{source.source_id}: timeout_seconds must be > 0")
        self._source = source
        self._operation = operation
        self._transport = transport
        self._retry = retry
        self._timeout = timeout_seconds
        self._clock = clock
        self._sleep = sleep

    @property
    def source(self) -> ConfiguredSource:
        return self._source

    def identifier_for(self, record: SourcingRecord) -> Optional[str]:
        return self._operation.identifier_for(record)

    def acquire(self, items: Sequence[AcquisitionItem]) -> SourceAcquisitionResult:
        refs = [item.record_ref for item in items]
        if len(set(refs)) != len(refs):
            raise ValueError("each record is consulted at most once per source")
        by_identifier: dict[str, list[str]] = {}
        for item in items:
            by_identifier.setdefault(item.identifier, []).append(item.record_ref)
        identifiers = list(by_identifier)
        size = self._operation.max_batch_size
        results: dict[str, ItemResult] = {}
        requests = retries = 0
        instants: list[datetime] = []
        for start in range(0, len(identifiers), size):
            batch = identifiers[start:start + size]
            response, failure, batch_retries, sent_at = self._send(self._operation.build_request(batch))
            requests += 1
            retries += batch_retries
            instants.extend(sent_at)
            parsed: Mapping[str, ParsedItem] = {}
            if failure is None:
                try:
                    parsed = self._operation.parse_response(response, batch, ValueFactory(self._source, sent_at[-1]))
                except SchemaViolation:
                    failure = FailureCategory.SCHEMA_FAILURE
            for identifier in batch:
                item = None if failure is not None else self._checked(parsed.get(identifier))
                for record_ref in by_identifier[identifier]:
                    results[record_ref] = (ItemResult.failed(record_ref, failure or FailureCategory.SCHEMA_FAILURE)
                                           if item is None else
                                           ItemResult.from_values(record_ref, item.values,
                                                                  item.observation_contract_rejected))
        return SourceAcquisitionResult(
            source_id=self._source.source_id, requests_sent=requests, retries=retries,
            first_request_at=min(instants) if instants else None, last_request_at=max(instants) if instants else None,
            items=tuple(results[ref] for ref in refs))

    def _checked(self, item: Optional[ParsedItem]) -> Optional[ParsedItem]:
        """A missing or empty item is outside the contract (SCHEMA_FAILURE).

        A value that does not carry this source's provenance is an adapter
        bug, not a provider failure, and stops the run."""
        if item is None or (not item.values and not item.observation_contract_rejected):
            return None
        for acquired in item.values:
            provenance = acquired.value.provenance
            if provenance.source != self._source.source_id or provenance.source_type is not self._source.source_type:
                raise ValueError(f"{self._source.source_id}: value {acquired.field!r} was not built by its ValueFactory")
        return item

    def _send(self, request: HttpRequest) -> tuple[Optional[HttpResponse], Optional[FailureCategory], int, list[datetime]]:
        retries = 0
        sent_at: list[datetime] = []
        while True:
            now = self._clock()
            _aware(now, "connector clock")
            sent_at.append(now)
            response: Optional[HttpResponse] = None
            try:
                response = self._transport.send(request, timeout=self._timeout)
            except (TransportTimeout, TransportError):
                failure: Optional[FailureCategory] = FailureCategory.SOURCE_FAILURE
            else:
                failure = (None if response.status in self._operation.handled_statuses
                           else classify_status(response.status))
            if failure is None:
                return response, None, retries, sent_at
            if failure not in _RETRYABLE or retries >= self._retry.max_retries:
                return None, failure, retries, sent_at
            self._sleep(self._retry.delay(retries, response))
            retries += 1
