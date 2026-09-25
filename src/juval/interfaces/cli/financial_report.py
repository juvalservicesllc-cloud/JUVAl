"""Read-only CLI report of the financial documents and capture diagnostics
stored for one execution (ADR-047).

    python -m juval.interfaces.cli.financial_report --persist-db runs.db --execution-id <id>

It opens the database read-only (SQLite `mode=ro`): no file is created, no
DDL runs, nothing is recalculated. It never imports a file or runs the
pipeline, and there is no default database or "latest run".

Exit codes: 0 report printed; 2 database file not found (or bad arguments);
4 execution_id not stored; 5 integrity error (corrupt payload, unknown format
version, identity mismatch, or v2 document and diagnostics set disagreeing);
6 not a readable SQLite database / SQLite error.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional, Sequence

from juval.application.financial_persistence import FinancialRecordIntegrityError
from juval.application.financial_report import (
    ExecutionNotFound,
    FinancialRunReport,
    RecordFinancialReport,
    build_financial_report,
)
from juval.application.financial_serialization import FinancialRecordDocument, FinancialSerializationError
from juval.application.financial_serialization_v2 import FinancialRecordDocumentV2
from juval.domain.financial_dependencies import FinancialResult
from juval.infrastructure.logging.sqlite_read_only import ReadOnlySqliteRunReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="juval-financial-report",
        description="Show the financial documents and capture diagnostics stored for one execution (read-only).",
    )
    parser.add_argument("--persist-db", type=Path, required=True, help="Existing SQLite file to read")
    parser.add_argument("--execution-id", required=True, help="Execution to report; never inferred")
    return parser


def _document_lines(document) -> list[str]:
    if document is None:
        return ["  financial document: none"]
    if isinstance(document, FinancialRecordDocumentV2):
        core, lines = document.document, ["  financial document: v2"]
    else:
        assert isinstance(document, FinancialRecordDocument)
        core, lines = document, ["  financial document: v1"]
    if core.calculations is None:
        lines.append("    calculations: not stored")
        return lines
    present = {item.result for item in core.calculations.calculations}
    for item in core.calculations.calculations:
        value = item.value
        if item.blocker is None:
            exact = "" if item.exact else " (inexact)"
            lines.append(f"    {item.result.value}: {value.value} {value.unit} {value.status.value}{exact}")
        else:
            lines.append(f"    {item.result.value}: BLOCKED {value.status.value} - {value.provenance.evidence}")
    missing = [result.value for result in FinancialResult if result not in present]
    if missing:
        lines.append(f"    not requested: {', '.join(missing)}")
    return lines


def _diagnostics_lines(diagnostics) -> list[str]:
    if diagnostics is None:
        return ["  capture diagnostics: not stored"]
    lines = [f"  capture diagnostics: {len(diagnostics.diagnostics)}"]
    for d in diagnostics.diagnostics:
        where = f"row={d.row}" + (f" column={d.column}" if d.column else "") + \
                (f" raw={d.raw_value!r}" if d.raw_value is not None else "")
        lines.append(f"    [{d.code.value}] {d.subject} {where}: {d.message}")
    return lines


def _record_lines(record: RecordFinancialReport) -> list[str]:
    snapshot = record.snapshot
    asin = (snapshot.get("asin") or {}).get("value")
    lines = [f"record {record.record_ref} sku={snapshot.get('supplier_sku')} asin={asin}"]
    lines += _document_lines(record.document) + _diagnostics_lines(record.diagnostics)
    lines += [f"  integrity: INCONSISTENT - {issue}" for issue in record.inconsistencies]
    return lines


def format_report(report: FinancialRunReport) -> str:
    lines = [f"execution_id={report.run.execution_id} status={report.run.status.value} "
             f"records={len(report.records)}"]
    for record in report.records:
        lines += _record_lines(record)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_financial_report(ReadOnlySqliteRunReader(args.persist_db), args.execution_id)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except ExecutionNotFound:
        print(f"error: execution_id {args.execution_id!r} is not stored in this database", file=sys.stderr)
        return 4
    except (FinancialSerializationError, FinancialRecordIntegrityError, json.JSONDecodeError) as error:
        print(f"error: integrity: {error}", file=sys.stderr)
        return 5
    except sqlite3.Error as error:
        print(f"error: not a readable SQLite database: {error}", file=sys.stderr)
        return 6
    print(format_report(report))
    if report.inconsistencies:
        for issue in report.inconsistencies:
            print(f"error: integrity: {issue}", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
