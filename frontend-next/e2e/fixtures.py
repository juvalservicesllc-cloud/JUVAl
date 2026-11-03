"""Inputs for the frontend-next E2E suite (run with the repository's .venv).

    build <dir>          write the XLSX supplier files the specs upload
    seed-history <db>    store one run whose snapshot predates reason codes and
                         declared demand (D7-D NOT_CLASSIFIABLE, D7-B NOT_CAPTURED)
    seed-buy <db>        store a synthetic BUY snapshot for rendering only
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
    **{f"batch-{i:02}.xlsx": [{"asin": f"B0E2EB{i:04}", "title": f"E2E batch {i:02} (synthetic)", "selling_price": 30}]
       for i in range(1, 12)},
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


def seed_buy(db: Path) -> None:
    """Rendering fixture, not a pipeline outcome (ADR-052 forbids uploaded BUY).

    Fixed synthetic economics: 30 - 3 fees - (10 COG + 2 shipping) = 15 profit;
    ROI = 15/12 = 1.25, margin = 15/30 = .5. Fees are fixed in this example,
    so break-even = 15. No external source or demand verification is claimed.
    """
    from juval.domain.execution_run import ExecutionRun, ExecutionStatus
    from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

    at = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)

    def inferred(value: str, method: str, source_type: str = "CALCULATED") -> dict:
        return {"value": value, "status": "INFERRED", "provenance": {
            "source": "E2E synthetic BUY fixture (not market evidence)", "source_type": source_type,
            "verification_status": "INFERRED", "retrieved_at": at.isoformat(), "method": method,
            "evidence": "Synthetic rendering test only; not an Amazon or Keepa verification",
        }}

    none = {"value": None, "status": None}
    snapshot = {
        "record_ref": "row_2", "marketplace": "US", "supplier_sku": "E2E-SYNTHETIC-BUY",
        "title": inferred("E2E seeded BUY (synthetic)", "synthetic fixture label", "USER_INPUT"),
        "asin": none, "upc": none, "brand": none, "weight": none,
        "selling_price": inferred("30", "synthetic fixture input", "USER_INPUT"),
        "cog": "10", "shipping_per_unit": "2", "total_fees": "3", "seller_proceeds": "27", "total_cost": "12",
        "profit": inferred("15", "synthetic example: 30 - 3 - (10 + 2)"),
        "roi": inferred("1.25", "synthetic example: 15 / 12"),
        "margin": inferred("0.5", "synthetic example: 15 / 30"),
        "break_even_price": inferred("15", "synthetic example: fixed fees 3 + landed cost 12"),
        "max_cog_target_profit": none, "max_cog_target_roi": none,
        "hazmat_status": "ABSENT", "hazmat_severity": "NONE", "hazmat_severity_status": "INFERRED",
        "hazmat_severity_source_type": "USER_INPUT",
        "bulky_status": "ABSENT", "bulky_severity": "NONE", "bulky_severity_status": "INFERRED",
        "bulky_severity_source_type": "USER_INPUT",
        "decision": "BUY", "decision_reasons": [], "decision_reason_codes": [],
        "issue_count": 0, "issues": [], "issue_codes": [],
    }
    run = ExecutionRun("e2e-seeded-buy", at, at, ExecutionStatus.SUCCESS, "E2E synthetic BUY snapshot", "e2e-synthetic-hash", "e2e-render-only", 1, 1, 1, 0, 0)
    SqliteExecutionRunStore(db).save_execution_run(run, [snapshot])


if __name__ == "__main__":
    command, target = sys.argv[1], Path(sys.argv[2])
    {"build": build, "seed-history": seed_history, "seed-buy": seed_buy, "dump": dump}[command](target)
