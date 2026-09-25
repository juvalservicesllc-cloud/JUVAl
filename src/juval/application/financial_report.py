"""Read-only report of the financial state stored for one execution (ADR-047).

Assembles what is persisted — record snapshots, financial documents (v1 or
v2, each kept as its own type) and capture diagnostics sets — without
computing, repairing or completing anything. Loading reuses
financial_persistence's readers, so a corrupt payload, an unknown version or
an identity mismatch raises instead of being reported as absence.

Where a v2 document and a stored diagnostics set both exist, the fields they
share must agree; a disagreement is reported as an inconsistency, and neither
side is preferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

from juval.application.capture_diagnostics import RecordCaptureDiagnostics
from juval.application.financial_persistence import (
    AnyFinancialRecord,
    read_capture_diagnostics_row,
    read_financial_row,
)
from juval.application.financial_serialization_v2 import FinancialRecordDocumentV2
from juval.domain.execution_run import ExecutionRun


class ExecutionNotFound(LookupError):
    pass


class ReportStore(Protocol):
    """Read methods only; satisfied by the read-only SQLite reader."""

    def load_execution_run(self, execution_id: str) -> Optional[ExecutionRun]: ...

    def load_records(self, execution_id: str) -> list[dict[str, Any]]: ...

    def load_financial_rows(
        self, execution_id: str, record_refs: Optional[Sequence[str]] = None,
    ) -> tuple[dict[str, tuple[str, int, str]], dict[str, tuple[str, int, str]]]: ...


@dataclass(frozen=True)
class RecordFinancialReport:
    record_ref: str
    snapshot: dict[str, Any]
    document: Optional[AnyFinancialRecord]
    diagnostics: Optional[RecordCaptureDiagnostics]
    inconsistencies: tuple[str, ...] = ()
    # The stored JSON behind `document` / `diagnostics`, as persisted (None when
    # nothing is stored), so a reader can expose it without re-serializing.
    document_payload: Optional[dict[str, Any]] = None
    diagnostics_payload: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class FinancialRunReport:
    run: ExecutionRun
    records: tuple[RecordFinancialReport, ...]

    @property
    def inconsistencies(self) -> tuple[str, ...]:
        return tuple(f"{r.record_ref}: {issue}" for r in self.records for issue in r.inconsistencies)


def build_financial_report(store: ReportStore, execution_id: str) -> FinancialRunReport:
    """Everything stored for `execution_id`, in processing order. Raises
    ExecutionNotFound for an unknown run; never writes."""
    run = store.load_execution_run(execution_id)
    if run is None:
        raise ExecutionNotFound(execution_id)
    return FinancialRunReport(run, record_financial_reports(store, execution_id, store.load_records(execution_id),
                                                            whole_run=True))


def record_financial_reports(store: ReportStore, execution_id: str, snapshots: Sequence[dict[str, Any]], *,
                             whole_run: bool = False) -> tuple[RecordFinancialReport, ...]:
    """What is stored for these record snapshots of `execution_id`, in their
    order, from one batch read (not one read per record); never writes.
    `whole_run` reads every row of the run instead of listing the refs."""
    refs = None if whole_run else [snapshot["record_ref"] for snapshot in snapshots]
    documents, diagnostics_rows = store.load_financial_rows(execution_id, refs)
    reports = []
    for snapshot in snapshots:
        ref = snapshot["record_ref"]
        document, document_payload = read_financial_row(documents.get(ref), execution_id, ref) or (None, None)
        diagnostics, diagnostics_payload = (read_capture_diagnostics_row(diagnostics_rows.get(ref), execution_id, ref)
                                            or (None, None))
        reports.append(RecordFinancialReport(ref, snapshot, document, diagnostics,
                                             _inconsistencies(document, diagnostics),
                                             document_payload, diagnostics_payload))
    return tuple(reports)


def _inconsistencies(document: Optional[AnyFinancialRecord],
                     diagnostics: Optional[RecordCaptureDiagnostics]) -> tuple[str, ...]:
    if not isinstance(document, FinancialRecordDocumentV2) or diagnostics is None:
        return ()  # nothing shared to compare (v1 holds no problems; a set may predate or be absent)
    in_document = [(p.text, p.subject, p.row, p.column, p.raw_value) for p in document.capture_problems]
    in_store = [(d.text, d.subject, d.row, d.column, d.raw_value) for d in diagnostics.diagnostics]
    if in_document != in_store:
        return (f"v2 document holds {len(in_document)} capture problems and the diagnostics set holds "
                f"{len(in_store)}; their shared fields differ",)
    return ()
