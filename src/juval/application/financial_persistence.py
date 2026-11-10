"""Persist and load native financial records (ADR-047 §22 step 6, SQLite).

Stores a financial record payload next to the run and its record snapshots,
in the same transaction, and reads it back. What is stored is exactly the
canonical serialization of the document's own version: v1
(serialize_financial_record) or v2 (serialize_financial_record_v2). Stored
v1 rows are never rewritten or upgraded.

Read outcomes stay distinct:
  * None                          -> that run/record has no financial document;
  * FinancialRecordDocument       -> a valid v1 document, returned as v1;
  * FinancialRecordDocumentV2     -> a valid v2 document;
  * FinancialSerializationError   -> stored text is not a valid payload
                                     (corrupt JSON/structure, unknown format or version);
  * FinancialRecordIntegrityError -> a valid payload whose identity or stored
                                     format columns contradict where it was found;
  * FinancialStorageUnavailable   -> the store's financial tables do not exist
                                     (PostgreSQL migration not applied), never
                                     read as "no document";
  * sqlite3.Error / psycopg.Error -> other storage failures, propagated untouched.

read_financial_row / read_capture_diagnostics_row apply those same checks to a
row the caller already fetched (e.g. one batch read for a page), and return the
validated object together with the stored JSON exactly as parsed from the
stored text, for callers (the read-only API) that must expose the persisted
payload, not a re-serialization of it.

Capture diagnostics (application/capture_diagnostics.py) are saved in the same
transaction, one set per captured record, independent of any document: a
record without a scenario has diagnostics and no financial document.
load_capture_diagnostics follows the same outcome rules.

A stored document is a faithful copy of what was serialized. It does not by
itself make a calculation historically reproducible (ADR-047 §19): see the
limits recorded in ADR-047.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Protocol, Sequence, Union

from juval.application.financial_serialization import (
    FORMAT,
    FinancialRecordDocument,
    FinancialSerializationError,
    serialize_financial_record,
)
from juval.application.financial_serialization_v2 import (
    FinancialRecordDocumentV2,
    read_financial_record,
    serialize_financial_record_v2,
)
from juval.application.capture_diagnostics import (
    FORMAT as DIAGNOSTICS_FORMAT,
    VERSION as DIAGNOSTICS_VERSION,
    RecordCaptureDiagnostics,
    deserialize_capture_diagnostics,
    serialize_capture_diagnostics,
)
from juval.application.tenancy import Ownership
from juval.domain.execution_run import ExecutionRun


class FinancialRecordIntegrityError(ValueError):
    """A financial document does not belong where it is being saved or was found."""


class FinancialStorageUnavailable(RuntimeError):
    """The store has no financial tables: its schema migration was not applied."""


AnyFinancialRecord = Union[FinancialRecordDocument, FinancialRecordDocumentV2]


def _core(document: AnyFinancialRecord) -> FinancialRecordDocument:
    return document.document if isinstance(document, FinancialRecordDocumentV2) else document


def _serialize(document: AnyFinancialRecord) -> dict[str, Any]:
    if isinstance(document, FinancialRecordDocumentV2):
        return serialize_financial_record_v2(document)
    return serialize_financial_record(document)


class FinancialRecordStore(Protocol):
    def save_execution_run(self, run: ExecutionRun, records: Sequence[Mapping[str, Any]] = (), *,
                           financial_records: Sequence[Mapping[str, Any]] = (),
                           capture_diagnostics: Sequence[Mapping[str, Any]] = (),
                           owner: Optional[Ownership] = None) -> None: ...

    def load_financial_record(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]: ...

    def load_capture_diagnostics(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]: ...


def save_run_with_financial_records(
    store: FinancialRecordStore,
    run: ExecutionRun,
    snapshots: Sequence[Mapping[str, Any]],
    documents: Sequence[AnyFinancialRecord],
    capture_diagnostics: Sequence[RecordCaptureDiagnostics] = (),
    owner: Optional[Ownership] = None,
) -> None:
    """Save run + snapshots + financial documents + capture diagnostics atomically.

    Every document and diagnostics set must belong to `run` and to one of
    `snapshots`, at most once per record. Records without a document are fine:
    absence is not an error.
    """
    payloads, diagnostics_payloads = financial_payloads(run, snapshots, documents, capture_diagnostics)
    store.save_execution_run(run, snapshots, financial_records=payloads,
                             capture_diagnostics=diagnostics_payloads, owner=owner)


def financial_payloads(
    run: ExecutionRun,
    snapshots: Sequence[Mapping[str, Any]],
    documents: Sequence[AnyFinancialRecord],
    capture_diagnostics: Sequence[RecordCaptureDiagnostics] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate that every document and diagnostics set belongs to `run` and to
    one of `snapshots` (once per record) and serialize them; writes nothing."""
    refs = {snapshot["record_ref"] for snapshot in snapshots}
    seen: set[str] = set()
    payloads = []
    for document in documents:
        evidence = _core(document).evidence
        if evidence.execution_id != run.execution_id:
            raise FinancialRecordIntegrityError(
                f"document of execution {evidence.execution_id!r} cannot be saved with {run.execution_id!r}")
        if evidence.record_reference not in refs:
            raise FinancialRecordIntegrityError(f"{evidence.record_reference!r} is not a record of this run")
        if evidence.record_reference in seen:
            raise FinancialRecordIntegrityError(f"{evidence.record_reference!r} has more than one document")
        seen.add(evidence.record_reference)
        payloads.append(_serialize(document))
    diagnostics_payloads = []
    seen.clear()
    for item in capture_diagnostics:
        if not isinstance(item, RecordCaptureDiagnostics):
            raise FinancialRecordIntegrityError("capture diagnostics must be RecordCaptureDiagnostics")
        if item.execution_id != run.execution_id:
            raise FinancialRecordIntegrityError(
                f"diagnostics of execution {item.execution_id!r} cannot be saved with {run.execution_id!r}")
        if item.record_ref not in refs:
            raise FinancialRecordIntegrityError(f"{item.record_ref!r} is not a record of this run")
        if item.record_ref in seen:
            raise FinancialRecordIntegrityError(f"{item.record_ref!r} has more than one diagnostics set")
        seen.add(item.record_ref)
        diagnostics_payloads.append(serialize_capture_diagnostics(item))
    return payloads, diagnostics_payloads


def load_financial_record(
    store: FinancialRecordStore, execution_id: str, record_ref: str
) -> Optional[AnyFinancialRecord]:
    loaded = read_financial_row(store.load_financial_record(execution_id, record_ref), execution_id, record_ref)
    return loaded[0] if loaded is not None else None


def read_financial_row(row: Optional[tuple[str, int, str]], execution_id: str,
                       record_ref: str) -> Optional[tuple[AnyFinancialRecord, dict[str, Any]]]:
    """Validate one stored `(format, format_version, payload)` row found under
    `(execution_id, record_ref)`; None stays None (nothing stored)."""
    if row is None:
        return None
    stored_format, stored_version, text = row
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise FinancialSerializationError(f"stored financial record is not JSON: {error}") from error
    document = read_financial_record(payload)  # explicit version dispatch; rejects unknown/corrupt
    version = 2 if isinstance(document, FinancialRecordDocumentV2) else 1
    if (stored_format, stored_version) != (FORMAT, version):
        raise FinancialRecordIntegrityError(
            f"stored columns declare {stored_format!r} v{stored_version}, payload is {FORMAT!r} v{version}")
    evidence = _core(document).evidence
    found = (evidence.execution_id, evidence.record_reference)
    if found != (execution_id, record_ref):
        raise FinancialRecordIntegrityError(f"payload identity {found} stored under {(execution_id, record_ref)}")
    return document, json.loads(text)  # fresh parse: the stored JSON, untouched by the reader


def load_capture_diagnostics(
    store: FinancialRecordStore, execution_id: str, record_ref: str
) -> Optional[RecordCaptureDiagnostics]:
    """None when no set was stored for that run/record (e.g. a legacy run)."""
    loaded = read_capture_diagnostics_row(store.load_capture_diagnostics(execution_id, record_ref),
                                          execution_id, record_ref)
    return loaded[0] if loaded is not None else None


def read_capture_diagnostics_row(row: Optional[tuple[str, int, str]], execution_id: str,
                                 record_ref: str) -> Optional[tuple[RecordCaptureDiagnostics, dict[str, Any]]]:
    if row is None:
        return None
    stored_format, stored_version, text = row
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise FinancialSerializationError(f"stored capture diagnostics are not JSON: {error}") from error
    item = deserialize_capture_diagnostics(payload)
    if (stored_format, stored_version) != (DIAGNOSTICS_FORMAT, DIAGNOSTICS_VERSION):
        raise FinancialRecordIntegrityError(
            f"stored columns declare {stored_format!r} v{stored_version}, "
            f"payload is {DIAGNOSTICS_FORMAT!r} v{DIAGNOSTICS_VERSION}")
    if (item.execution_id, item.record_ref) != (execution_id, record_ref):
        raise FinancialRecordIntegrityError(
            f"diagnostics identity {(item.execution_id, item.record_ref)} stored under {(execution_id, record_ref)}")
    return item, json.loads(text)
