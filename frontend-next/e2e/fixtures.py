"""Inputs for the frontend-next E2E suite (run with the repository's .venv).

    build <dir>          write the XLSX supplier files the specs upload
    seed-history <db>    store one run whose snapshot predates reason codes and
                         declared demand (D7-D NOT_CLASSIFIABLE, D7-B NOT_CAPTURED)
    dump <xlsx>          print a workbook's first sheet as JSON rows

Every value here is synthetic. Demand says so in its method and population: it is
a declaration in an uploaded file (USER_INPUT, INFERRED), never market data. The
suggested prices are invented amounts, not any supplier's price.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook

BASE = {"marketplace": "US", "cost": 3, "hazmat": "false", "bulky": "false"}
CONTEXT = {
    "demand_window_start": "2026-09-01T00:00:00-04:00", "demand_window_end": "2026-10-01T00:00:00-04:00",
    "demand_observed_at": "2026-10-01T00:00:00-04:00",
    "demand_population": "synthetic E2E population (not real market data)",
    "demand_method": "synthetic E2E declaration",
}

FILES = {
    # target_profit 5 in the specs: 30 -> only DEMAND_UNKNOWN; 6 -> also PROFIT_BELOW_TARGET; 2 -> negative profit, PASS.
    "no-demand.xlsx": [
        {"asin": "B0E2E00001", "title": "E2E pending widget", "selling_price": 30},
        {"asin": "B0E2E00002", "title": "E2E low-profit widget", "selling_price": 6},
        {"asin": "B0E2E00003", "title": "E2E loss widget", "selling_price": 2},
    ],
    "demand-valid.xlsx": [{"asin": "B0E2E00011", "title": "E2E declared million", "selling_price": 30,
                           "estimated_monthly_sales": 1000000, **CONTEXT}],
    "demand-invalid.xlsx": [{"asin": "B0E2E00021", "title": "E2E declared invalid", "selling_price": 30,
                             "estimated_monthly_sales": "approx 400", **CONTEXT}],
    # Supplier suggested price (ADR-053): a numeric cell with its currency, a currency that is not a code, and zero.
    "suggested-price.xlsx": [
        {"asin": "B0E2E00041", "title": "E2E suggested euro", "selling_price": 30,
         "supplier_suggested_price": 24.99, "supplier_suggested_price_currency": "EUR"},
        {"asin": "B0E2E00042", "title": "E2E suggested bad currency", "selling_price": 30,
         "supplier_suggested_price": "19.50", "supplier_suggested_price_currency": "usd"},
        {"asin": "B0E2E00043", "title": "E2E suggested zero", "selling_price": 30,
         "supplier_suggested_price": 0, "supplier_suggested_price_currency": "USD"},
    ],
    # Severity provenance (ADR-020): hazmat declared true, false, blank and unreadable; bulky false on every row.
    "severity-provenance.xlsx": [
        {"asin": "B0E2E00051", "title": "E2E hazmat yes", "selling_price": 30, "hazmat": "true"},
        {"asin": "B0E2E00052", "title": "E2E hazmat no", "selling_price": 30, "hazmat": "false"},
        {"asin": "B0E2E00053", "title": "E2E hazmat blank", "selling_price": 30, "hazmat": None},
        {"asin": "B0E2E00054", "title": "E2E hazmat unreadable", "selling_price": 30, "hazmat": "maybe"},
    ],
    # The observed_at cell is present but empty: incomplete context.
    "demand-incomplete.xlsx": [{"asin": "B0E2E00031", "title": "E2E declared incomplete", "selling_price": 30,
                                "estimated_monthly_sales": 420, **CONTEXT, "demand_observed_at": None}],
}


def build(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in FILES.items():
        headers = list(dict.fromkeys(k for row in rows for k in {**BASE, **row}))
        book = Workbook()
        sheet = book.active
        sheet.append(headers)
        for row in rows:
            cells = {**BASE, **row}
            sheet.append([cells.get(h) for h in headers])
        book.save(directory / name)


def seed_history(db: Path) -> None:
    from juval.domain.execution_run import ExecutionRun, ExecutionStatus
    from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

    at = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
    none = {"value": None, "status": None}
    snapshot = {  # the shape stored before D7-D/D7-B: no decision_reason_codes, no demand_evidence key
        "record_ref": "row_2", "supplier_sku": "HIST-1", "title": {"value": "E2E historical widget", "status": "VERIFIED"},
        "brand": none, "asin": {"value": "B0E2E00099", "status": "VERIFIED"}, "upc": none, "weight": none,
        "selling_price": {"value": "30", "status": "VERIFIED"}, "profit": {"value": "26", "status": "VERIFIED"},
        "roi": {"value": "8.6667", "status": "VERIFIED"}, "margin": none, "break_even_price": none,
        "max_cog_target_profit": none, "max_cog_target_roi": none, "cog": "3", "shipping_per_unit": None,
        "hazmat_status": "ABSENT", "bulky_status": "ABSENT", "decision": "REVIEW",
        "decision_reasons": ["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."], "issue_count": 0, "issues": [],
    }
    run = ExecutionRun("e2e-historical", at, at, ExecutionStatus.SUCCESS, "historical.xlsx", "e2e-hash", "pre-d7", 1, 1, 1, 0, 0)
    SqliteExecutionRunStore(db).save_execution_run(run, [snapshot])


def dump(path: Path) -> None:
    book = load_workbook(path, read_only=True)
    sheet = book[sys.argv[3]] if len(sys.argv) > 3 else book.worksheets[0]
    rows = [[c.isoformat() if isinstance(c, datetime) else c for c in row] for row in sheet.iter_rows(values_only=True)]
    print(json.dumps(rows))


if __name__ == "__main__":
    command, target = sys.argv[1], Path(sys.argv[2])
    {"build": build, "seed-history": seed_history, "dump": dump}[command](target)
