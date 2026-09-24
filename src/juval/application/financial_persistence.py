"""Persist and load native financial records (ADR-047 §22 step 6, SQLite).

Stores the v1 payload of application/financial_serialization.py next to the
run and its record snapshots, in the same transaction, and reads it back.
The format is not changed: what is stored is exactly serialize_financial_record.

Read outcomes stay distinct:
  * None                          -> that run/record has no financial document;
  * FinancialSerializationError   -> stored text is not a valid v1 payload
                                     (corrupt JSON/structure, unknown format or version);
  * FinancialRecordIntegrityError -> a valid payload whose identity or stored
                                     format columns contradict where it was found;
  * sqlite3.Error                 -> storage failure, propagated untouched.

A stored document is a faithful copy of what was serialized. It does not by
itself make a calculation historically reproducible (ADR-047 §19): see the
limits recorded in ADR-047.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Protocol, Sequence

from juval.application.financial_serialization import (
    FORMAT,
    VERSION,
    FinancialRecordDocument,
    FinancialSerializationError,
    deserialize_financial_record,
    serialize_financial_record,
)
from juval.domain.execution_run import ExecutionRun


class FinancialRecordIntegrityError(ValueError):
    """A financial document does not belong where it is being saved or was found."""


class FinancialRecordStore(Protocol):
    def save_execution_run(self, run: ExecutionRun, records: Sequence[Mapping[str, Any]] = (), *,
                           financial_records: Sequence[Mapping[str, Any]] = ()) -> None: ...

    def load_financial_record(self, execution_id: str, record_ref: str) -> Optional[tuple[str, int, str]]: ...


def save_run_with_financial_records(
    store: FinancialRecordStore,
    run: ExecutionRun,
    snapshots: Sequence[Mapping[str, Any]],
    documents: Sequence[FinancialRecordDocument],
) -> None:
    """Save run + snapshots + financial documents atomically.

    Every document must belong to `run` and to one of `snapshots`, at most once
    per record. Records without a document are fine: absence is not an error.
    """
    refs = {snapshot["record_ref"] for snapshot in snapshots}
    seen: set[str] = set()
    payloads = []
    for document in documents:
        evidence = document.evidence
        if evidence.execution_id != run.execution_id:
            raise FinancialRecordIntegrityError(
                f"document of execution {evidence.execution_id!r} cannot be saved with {run.execution_id!r}")
        if evidence.record_reference not in refs:
            raise FinancialRecordIntegrityError(f"{evidence.record_reference!r} is not a record of this run")
        if evidence.record_reference in seen:
            raise FinancialRecordIntegrityError(f"{evidence.record_reference!r} has more than one document")
        seen.add(evidence.record_reference)
        payloads.append(serialize_financial_record(document))
    store.save_execution_run(run, snapshots, financial_records=payloads)


def load_financial_record(
    store: FinancialRecordStore, execution_id: str, record_ref: str
) -> Optional[FinancialRecordDocument]:
    row = store.load_financial_record(execution_id, record_ref)
    if row is None:
        return None
    stored_format, stored_version, text = row
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise FinancialSerializationError(f"stored financial record is not JSON: {error}") from error
    document = deserialize_financial_record(payload)  # rejects unknown format/version and corruption
    if (stored_format, stored_version) != (FORMAT, VERSION):
        raise FinancialRecordIntegrityError(
            f"stored columns declare {stored_format!r} v{stored_version}, payload is {FORMAT!r} v{VERSION}")
    found = (document.evidence.execution_id, document.evidence.record_reference)
    if found != (execution_id, record_ref):
        raise FinancialRecordIntegrityError(f"payload identity {found} stored under {(execution_id, record_ref)}")
    return document
