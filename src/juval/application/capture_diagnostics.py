"""Stored capture diagnostics of one record (ADR-047), independent of any financial document.

The capturer's CaptureDiagnostic tuple for one (execution_id, record_ref),
kept as emitted — code, subject, message, row, and column/raw value only when
the capturer set them — whether or not the record declared a scenario. It is
neither financial evidence nor a legacy commercial issue, and it never
creates a FinancialEvidenceSet.

Format FORMAT = "juval.adr047.capture-diagnostics", VERSION = 1: its own
identity, separate from the financial record formats. Pure, no I/O. An empty
tuple means the record was captured with no diagnostics; a record with no
stored set was not captured by the financial flow at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from juval.application.financial_serialization import FinancialSerializationError, _enum, _obj, _str
from juval.infrastructure.excel.financial_capture import CaptureCode, CaptureDiagnostic

FORMAT = "juval.adr047.capture-diagnostics"
VERSION = 1

_ITEM_KEYS = {"subject", "code", "message", "row", "column", "raw_value"}


@dataclass(frozen=True)
class RecordCaptureDiagnostics:
    execution_id: str
    record_ref: str
    diagnostics: tuple[CaptureDiagnostic, ...]

    def __post_init__(self) -> None:
        for name in ("execution_id", "record_ref"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be explicit nonempty text")
        if not isinstance(self.diagnostics, tuple) or not all(
                isinstance(d, CaptureDiagnostic) for d in self.diagnostics):
            raise ValueError("diagnostics must be a tuple of CaptureDiagnostic")


def serialize_capture_diagnostics(item: RecordCaptureDiagnostics) -> dict[str, Any]:
    if not isinstance(item, RecordCaptureDiagnostics):
        raise FinancialSerializationError("Explicit RecordCaptureDiagnostics required")
    return {
        "format": FORMAT,
        "version": VERSION,
        "execution_id": item.execution_id,
        "record_ref": item.record_ref,
        "diagnostics": [{"subject": d.subject, "code": d.code.value, "message": d.message, "row": d.row,
                         "column": d.column, "raw_value": d.raw_value} for d in item.diagnostics],
    }


def deserialize_capture_diagnostics(payload: Any) -> RecordCaptureDiagnostics:
    try:
        return _parse(payload)
    except FinancialSerializationError:
        raise
    except (ValueError, TypeError) as error:
        raise FinancialSerializationError(f"invalid capture diagnostics payload: {error}") from error


def _parse(payload: Any) -> RecordCaptureDiagnostics:
    if isinstance(payload, dict) and "format" in payload and "version" in payload:
        if payload["format"] != FORMAT:
            raise FinancialSerializationError(f"unknown format {payload['format']!r}")
        if type(payload["version"]) is not int or payload["version"] != VERSION:
            raise FinancialSerializationError(f"unsupported {FORMAT} version {payload['version']!r}")
    data = _obj(payload, "payload", {"format", "version", "execution_id", "record_ref", "diagnostics"})
    if data["format"] != FORMAT or type(data["version"]) is not int or data["version"] != VERSION:
        raise FinancialSerializationError("unknown capture diagnostics format or version")
    if not isinstance(data["diagnostics"], list):
        raise FinancialSerializationError("diagnostics must be a list")
    diagnostics = []
    for i, raw in enumerate(data["diagnostics"]):
        where = f"diagnostics[{i}]"
        raw = _obj(raw, where, _ITEM_KEYS)
        row = raw["row"]
        if type(row) is not int or row < 1:
            raise FinancialSerializationError(f"{where}.row must be a positive integer")
        for key in ("subject", "message", "column", "raw_value"):
            if raw[key] == "":
                raise FinancialSerializationError(f"{where}.{key} must not be empty text")
        diagnostics.append(CaptureDiagnostic(
            subject=_str(raw["subject"], f"{where}.subject"),
            code=_enum(CaptureCode, raw["code"], f"{where}.code"),
            message=_str(raw["message"], f"{where}.message"),
            row=row,
            column=_str(raw["column"], f"{where}.column", optional=True),
            raw_value=_str(raw["raw_value"], f"{where}.raw_value", optional=True),
        ))
    return RecordCaptureDiagnostics(_str(data["execution_id"], "execution_id"),
                                    _str(data["record_ref"], "record_ref"), tuple(diagnostics))
