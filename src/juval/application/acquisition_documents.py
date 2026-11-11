"""ADR-058: canonical documents, NOT_RECORDED and integrity against provenance.

* Serialization of `acquisition_configuration` / `acquisition_execution`
  (ADR-058 §5): canonical JSON, explicit `format` + `version`, strict reading
  (unknown format, version or key is an error, never a reinterpretation, P4).
* `columns_for_write` -- the single place both stores call before their INSERT:
  it checks the run's persisted provenance against the record (P6, P7) and
  returns the two column values. Nothing is written when it raises.
* `record_from_columns` -- both NULL is NOT_RECORDED (None); one NULL is a
  storage integrity error (P3).
* The per-record `acquired_evidence` snapshot document, where values obtained
  from an external source are persisted with their provenance so utilization
  can be derived from what is stored (ADR-058 §7). It is informational: never
  projected to Product or DecisionInputs (ADR-052 §20.3, ADR-058 I6).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence

from juval.domain.acquisition import (
    EXTERNAL_SOURCE_TYPES,
    AcquisitionConfiguration,
    AcquisitionExecution,
    AcquisitionRecord,
    ConfiguredSource,
    EnabledBy,
    FailureCategory,
    ItemCounts,
    NotConsultedReason,
    SourceExecution,
    ValueCounts,
)
from juval.application.record_snapshot import _fv
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus

CONFIGURATION_FORMAT = "juval.adr058.acquisition-configuration"
EXECUTION_FORMAT = "juval.adr058.acquisition-execution"
ACQUIRED_EVIDENCE_FORMAT = "juval.adr058.acquired-evidence"
ACQUIRED_EVIDENCE_KEY = "acquired_evidence"
VERSION = 1

_EXTERNAL_TYPE_VALUES = frozenset(t.value for t in EXTERNAL_SOURCE_TYPES)


class AcquisitionDocumentError(ValueError):
    """A stored or supplied acquisition document is not a valid v1 document."""


class AcquisitionIntegrityError(ValueError):
    """The record does not match the run's persisted provenance (P6/P7)."""


def canonical_json(document: Mapping[str, Any]) -> str:
    """ADR-058 §5: stricter than ADR-047's text, which keeps default separators."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)


# --- serialization -------------------------------------------------------------


def _instant(value: Optional[datetime]) -> Optional[str]:
    return None if value is None else value.isoformat()


def configuration_document(config: AcquisitionConfiguration) -> dict[str, Any]:
    return {
        "format": CONFIGURATION_FORMAT,
        "version": VERSION,
        "captured_at": config.captured_at.isoformat(),
        "sources": [
            {"source_id": s.source_id, "source_type": s.source_type.value, "contract_id": s.contract_id,
             "contract_sha256": s.contract_sha256, "enabled_by": s.enabled_by.value}
            for s in sorted(config.sources, key=lambda s: s.source_id)
        ],
    }


def execution_document(execution: AcquisitionExecution) -> dict[str, Any]:
    return {
        "format": EXECUTION_FORMAT,
        "version": VERSION,
        "sources": [
            {
                "source_id": s.source_id,
                "first_request_at": _instant(s.first_request_at),
                "last_request_at": _instant(s.last_request_at),
                "requests_sent": s.requests_sent,
                "retries": s.retries,
                "items": {
                    "requested": s.items.requested, "with_evidence": s.items.with_evidence,
                    "no_evidence": s.items.no_evidence, "rejected": s.items.rejected,
                    "failed": {c.value: n for c, n in s.items.failed.items()},
                },
                "values": {"used": s.values.used, "not_found": s.values.not_found, "invalid": s.values.invalid},
                "observation_contract_rejected": s.observation_contract_rejected,
                "not_consulted_reason": None if s.not_consulted_reason is None else s.not_consulted_reason.value,
            }
            for s in sorted(execution.sources, key=lambda s: s.source_id)
        ],
    }


def _obj(data: Any, where: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(data, dict):
        raise AcquisitionDocumentError(f"{where} must be an object")
    if set(data) != keys:
        raise AcquisitionDocumentError(f"{where} keys {sorted(data)} != {sorted(keys)}")
    return data


def _header(data: Mapping[str, Any], expected_format: str) -> None:
    if data["format"] != expected_format:
        raise AcquisitionDocumentError(f"unknown format {data['format']!r}, expected {expected_format!r}")
    if isinstance(data["version"], bool) or data["version"] != VERSION:
        raise AcquisitionDocumentError(f"unsupported {expected_format} version {data['version']!r}")


def _parse_instant(text: Any, where: str) -> Optional[datetime]:
    if text is None:
        return None
    if not isinstance(text, str):
        raise AcquisitionDocumentError(f"{where} must be an ISO 8601 string")
    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        raise AcquisitionDocumentError(f"{where} is not ISO 8601") from error


def _load(text: Any, where: str) -> Any:
    if not isinstance(text, str):
        raise AcquisitionDocumentError(f"{where} must be JSON text")
    try:
        data = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(
            AcquisitionDocumentError(f"{where}: {token} is not allowed")))
    except json.JSONDecodeError as error:
        raise AcquisitionDocumentError(f"{where} is not valid JSON") from error
    return data


def parse_configuration(text: str) -> AcquisitionConfiguration:
    data = _obj(_load(text, "acquisition_configuration"), "acquisition_configuration",
                {"format", "version", "captured_at", "sources"})
    _header(data, CONFIGURATION_FORMAT)
    if not isinstance(data["sources"], list):
        raise AcquisitionDocumentError("acquisition_configuration.sources must be a list")
    try:
        sources = tuple(
            ConfiguredSource(
                source_id=item["source_id"], source_type=SourceType(item["source_type"]),
                contract_id=item["contract_id"], contract_sha256=item["contract_sha256"],
                enabled_by=EnabledBy(item["enabled_by"]))
            for item in (_obj(s, "configured source",
                              {"source_id", "source_type", "contract_id", "contract_sha256", "enabled_by"})
                         for s in data["sources"]))
        config = AcquisitionConfiguration(_parse_instant(data["captured_at"], "captured_at"), sources)
    except AcquisitionDocumentError:
        raise
    except (ValueError, TypeError) as error:
        raise AcquisitionDocumentError(f"invalid acquisition_configuration: {error}") from error
    _require_canonical(text, configuration_document(config), "acquisition_configuration")
    return config


def parse_execution(text: str) -> AcquisitionExecution:
    data = _obj(_load(text, "acquisition_execution"), "acquisition_execution", {"format", "version", "sources"})
    _header(data, EXECUTION_FORMAT)
    if not isinstance(data["sources"], list):
        raise AcquisitionDocumentError("acquisition_execution.sources must be a list")
    entries = []
    try:
        for raw in data["sources"]:
            item = _obj(raw, "source execution", {
                "source_id", "first_request_at", "last_request_at", "requests_sent", "retries", "items",
                "values", "observation_contract_rejected", "not_consulted_reason"})
            items = _obj(item["items"], "items", {"requested", "with_evidence", "no_evidence", "rejected", "failed"})
            failed = _obj(items["failed"], "items.failed", {c.value for c in FailureCategory})
            values = _obj(item["values"], "values", {"used", "not_found", "invalid"})
            reason = item["not_consulted_reason"]
            entries.append(SourceExecution(
                source_id=item["source_id"],
                first_request_at=_parse_instant(item["first_request_at"], "first_request_at"),
                last_request_at=_parse_instant(item["last_request_at"], "last_request_at"),
                requests_sent=item["requests_sent"], retries=item["retries"],
                items=ItemCounts(items["requested"], items["with_evidence"], items["no_evidence"], items["rejected"],
                                 {FailureCategory(k): v for k, v in failed.items()}),
                values=ValueCounts(values["used"], values["not_found"], values["invalid"]),
                observation_contract_rejected=item["observation_contract_rejected"],
                not_consulted_reason=None if reason is None else NotConsultedReason(reason),
            ))
        execution = AcquisitionExecution(tuple(entries))
    except AcquisitionDocumentError:
        raise
    except (ValueError, TypeError) as error:
        raise AcquisitionDocumentError(f"invalid acquisition_execution: {error}") from error
    _require_canonical(text, execution_document(execution), "acquisition_execution")
    return execution


def _require_canonical(text: str, document: Mapping[str, Any], where: str) -> None:
    if canonical_json(document) != text:
        raise AcquisitionDocumentError(f"{where} is not in canonical form")


def record_from_columns(configuration: Optional[str], execution: Optional[str]) -> Optional[AcquisitionRecord]:
    """None is NOT_RECORDED. It is never rebuilt from snapshots or settings."""
    if configuration is None and execution is None:
        return None
    if configuration is None or execution is None:
        raise AcquisitionDocumentError("only one acquisition column is set (ADR-058 P3)")
    try:
        return AcquisitionRecord(parse_configuration(configuration), parse_execution(execution))
    except AcquisitionDocumentError:
        raise
    except ValueError as error:
        raise AcquisitionDocumentError(str(error)) from error


# --- acquired evidence in record snapshots -------------------------------------


def acquired_evidence_document(values: Iterable[tuple[str, str, FieldValue[Any]]]) -> dict[str, Any]:
    """`values`: (source_id, field, FieldValue) of one record."""
    entries = sorted(values, key=lambda item: (item[0], item[1]))
    keys = [(source_id, field) for source_id, field, _ in entries]
    if len(set(keys)) != len(keys):
        raise ValueError("a source produced the same field twice for one record")
    return {
        "format": ACQUIRED_EVIDENCE_FORMAT,
        "version": VERSION,
        "values": [{"source_id": source_id, "field": field, "value": _fv(fv)}
                   for source_id, field, fv in entries],
    }


# --- derivation from persisted provenance (ADR-058 §7) ---------------------------


def _field_values(node: Any) -> Iterator[Mapping[str, Any]]:
    """Every serialized FieldValue (a mapping with a provenance object) under `node`."""
    if isinstance(node, Mapping):
        provenance = node.get("provenance")
        if isinstance(provenance, Mapping) and "source_type" in provenance and "verification_status" in provenance:
            yield node
        for child in node.values():
            yield from _field_values(child)
    elif isinstance(node, list):
        for child in node:
            yield from _field_values(child)


def derive_value_counts(
    snapshots: Sequence[Mapping[str, Any]], financial_payloads: Sequence[Mapping[str, Any]] = (),
) -> dict[str, ValueCounts]:
    """Values with an external source type, per `Provenance.source`.

    Scope: every field of every record snapshot (including `demand_evidence`
    and `acquired_evidence`) and every ADR-047 financial document of the run.
    """
    counts: dict[str, list[int]] = {}
    for document in (*snapshots, *financial_payloads):
        for value in _field_values(document):
            provenance = value["provenance"]
            if provenance.get("source_type") not in _EXTERNAL_TYPE_VALUES:
                continue
            slot = counts.setdefault(provenance.get("source"), [0, 0, 0])
            status = provenance.get("verification_status")
            if status in (VerificationStatus.VERIFIED.value, VerificationStatus.INFERRED.value):
                slot[0] += 1
            elif status == VerificationStatus.NOT_FOUND.value:
                slot[1] += 1
            elif status == VerificationStatus.INVALID.value:
                slot[2] += 1
    return {source: ValueCounts(*slot) for source, slot in counts.items()}


def check_integrity(record: Optional[AcquisitionRecord], snapshots: Sequence[Mapping[str, Any]],
                    financial_payloads: Sequence[Mapping[str, Any]] = ()) -> None:
    derived = derive_value_counts(snapshots, financial_payloads)
    if record is None:
        if derived:  # an external value can only exist in a run that recorded its sources
            raise AcquisitionIntegrityError(f"external values without an acquisition record: {sorted(map(str, derived))}")
        return
    configured = {s.source_id for s in record.configuration.sources}
    unattributed = sorted(map(str, set(derived) - configured))
    if unattributed:  # P6
        raise AcquisitionIntegrityError(f"persisted external values from unconfigured sources: {unattributed}")
    for entry in record.execution.sources:  # P7
        expected = derived.get(entry.source_id, ValueCounts(0, 0, 0))
        if entry.values != expected:
            raise AcquisitionIntegrityError(
                f"{entry.source_id}: recorded values {entry.values} differ from persisted provenance {expected}")


def columns_for_write(record: Optional[AcquisitionRecord], snapshots: Sequence[Mapping[str, Any]],
                      financial_payloads: Sequence[Mapping[str, Any]] = ()) -> tuple[Optional[str], Optional[str]]:
    """(acquisition_configuration, acquisition_execution) for the run's INSERT."""
    check_integrity(record, snapshots, financial_payloads)
    if record is None:
        return None, None
    return canonical_json(configuration_document(record.configuration)), canonical_json(
        execution_document(record.execution))
