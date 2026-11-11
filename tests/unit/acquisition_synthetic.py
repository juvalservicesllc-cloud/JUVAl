"""SYNTHETIC TEST DATA ONLY -- ADR-057 §3.1 transport doubles and a test-only
operation contract, confined to tests/.

Nothing here describes a real provider, endpoint or specification. The
"contract" is a few bytes written for these tests; the host uses the reserved
`.invalid` TLD and is never contacted (the transport is a scripted double).
Acquired values are INFERRED with explicit synthetic evidence: no synthetic
value is ever presented as VERIFIED or as data from a real source.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Mapping, Optional, Sequence, Union

from juval.domain.acquisition import ConfiguredSource, EnabledBy
from juval.domain.provenance import SourceType
from juval.domain.sourcing_record import SourcingRecord
from juval.infrastructure.enrichment.connector import (
    AuthorizedContract,
    AuthorizedHttpConnector,
    HttpRequest,
    HttpResponse,
    ParsedItem,
    RetryPolicy,
    SchemaViolation,
    ValueFactory,
)
from juval.processing.acquisition_port import AcquiredValue

SYNTHETIC_SPEC = (
    b'{"title":"JUVAL TEST SYNTHETIC catalog lookup -- not a real provider",'
    b'"request":{"ids":"array of strings"},'
    b'"response":{"items":[{"id":"string","status":"FOUND|NO_MATCH","title":"string","weight_lb":"number"}]}}'
)
SYNTHETIC_SHA = hashlib.sha256(SYNTHETIC_SPEC).hexdigest()
EVIDENCE = "JUVAL TEST SYNTHETIC fixture; not real provider data"
T0 = datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc)

CONTRACT = AuthorizedContract(
    contract_id="synthetic-test/catalog-lookup/v1", origin="PUBLISHED",
    publisher="JUVAL TEST SYNTHETIC (no real provider)", version="1",
    location="https://synthetic.invalid/spec.json", sha256=SYNTHETIC_SHA, media_type="application/json",
    obtained_at=T0, obtained_by="test-suite", approved_by="test-suite", approved_at=T0,
)
SOURCE = ConfiguredSource("synthetic-test/catalog-lookup", SourceType.AUTHORIZED_EXTERNAL_SOURCE,
                          CONTRACT.contract_id, SYNTHETIC_SHA, EnabledBy.ENV_FLAG)
_ITEM_KEYS = {"id", "status", "title", "weight_lb"}


class SyntheticCatalogOperation:
    """Test-only OperationContract written from SYNTHETIC_SPEC."""

    contract = CONTRACT
    handled_statuses: frozenset[int] = frozenset()

    def __init__(self, max_batch_size: int = 20) -> None:
        self.max_batch_size = max_batch_size

    def identifier_for(self, record: SourcingRecord) -> Optional[str]:
        asin = record.product.identification.asin
        return asin.value if asin is not None and asin.is_usable else None

    def build_request(self, identifiers: Sequence[str]) -> HttpRequest:
        return HttpRequest("POST", "https://synthetic.invalid/catalog", (("content-type", "application/json"),),
                           json.dumps({"ids": list(identifiers)}).encode())

    def parse_response(self, response: HttpResponse, identifiers: Sequence[str],
                       values: ValueFactory) -> Mapping[str, ParsedItem]:
        try:
            body = json.loads(response.body)
        except (ValueError, UnicodeDecodeError) as error:
            raise SchemaViolation("body is not JSON") from error
        if not isinstance(body, dict) or set(body) != {"items"} or not isinstance(body["items"], list):
            raise SchemaViolation("body must be {'items': [...]}")
        parsed: dict[str, ParsedItem] = {}
        for item in body["items"]:
            if not isinstance(item, dict) or not {"id", "status"} <= set(item) <= _ITEM_KEYS:
                raise SchemaViolation(f"item keys {sorted(item) if isinstance(item, dict) else item!r}")
            identifier, status = item["id"], item["status"]
            if identifier not in identifiers or identifier in parsed:
                raise SchemaViolation(f"unexpected or repeated id {identifier!r}")
            reference = f"synthetic-id={identifier}"
            if status == "NO_MATCH":
                parsed[identifier] = ParsedItem((AcquiredValue("catalog_title", values.not_found(
                    method="synthetic catalog lookup: no match", evidence=EVIDENCE, source_reference=reference)),))
            elif status == "FOUND":
                if not isinstance(item.get("title"), str) or not item["title"]:
                    raise SchemaViolation("FOUND requires a title")
                acquired = [AcquiredValue("catalog_title", values.inferred(
                    item["title"], method="synthetic catalog lookup: declared title", evidence=EVIDENCE,
                    source_reference=reference))]
                if "weight_lb" in item:
                    weight = item["weight_lb"]
                    if isinstance(weight, (int, float)) and not isinstance(weight, bool) and weight > 0:
                        acquired.append(AcquiredValue("catalog_weight", values.inferred(
                            Decimal(str(weight)), method="synthetic catalog lookup: declared package weight",
                            unit="lb", evidence=EVIDENCE, source_reference=reference)))
                    else:
                        acquired.append(AcquiredValue("catalog_weight", values.invalid(
                            weight, method="synthetic catalog lookup: declared package weight",
                            evidence=EVIDENCE, source_reference=reference)))
                parsed[identifier] = ParsedItem(tuple(acquired))
            else:
                raise SchemaViolation(f"unknown status {status!r}")
        return parsed


Scripted = Union[HttpResponse, Exception]


class ScriptedTransport:
    """Transport double: answers from a script and records what it was sent."""

    def __init__(self, *script: Scripted) -> None:
        self.script = list(script)
        self.sent: list[tuple[HttpRequest, float]] = []

    def send(self, request: HttpRequest, *, timeout: float) -> HttpResponse:
        self.sent.append((request, timeout))
        if not self.script:
            raise AssertionError("the transport double was called more times than scripted")
        answer = self.script.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class StepClock:
    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def __call__(self) -> datetime:
        current = self.now
        self.now += timedelta(seconds=1)
        return current


def ok(*items: dict, status: int = 200, headers: Optional[dict] = None) -> HttpResponse:
    return HttpResponse(status, headers or {}, json.dumps({"items": list(items)}).encode())


def status(code: int, headers: Optional[dict] = None) -> HttpResponse:
    return HttpResponse(code, headers or {}, b"")


def found(identifier: str, title: str = "JUVAL TEST SYNTHETIC title", **extra) -> dict:
    return {"id": identifier, "status": "FOUND", "title": title, **extra}


def no_match(identifier: str) -> dict:
    return {"id": identifier, "status": "NO_MATCH"}


def connector(transport: ScriptedTransport, *, max_retries: int = 2, batch: int = 20,
              sleeps: Optional[list] = None, source: ConfiguredSource = SOURCE) -> AuthorizedHttpConnector:
    waits = sleeps if sleeps is not None else []
    return AuthorizedHttpConnector(
        source, SyntheticCatalogOperation(batch), transport,
        retry=RetryPolicy(max_retries=max_retries, base_delay_seconds=1.0, max_delay_seconds=30.0),
        timeout_seconds=5.0, clock=StepClock(), sleep=waits.append)
