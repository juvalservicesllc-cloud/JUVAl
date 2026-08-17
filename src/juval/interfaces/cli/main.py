"""CLI entrypoint: Excel in -> pipeline -> Excel out (+ optional ExecutionRun persistence).

Thin client over `application.run_pipeline` — no business logic lives
here (ADR-001, ADR-005 recommends a CLI as the first interface to
validate the Core end-to-end, independent of the PWA vs. `.exe`
decision). Every commercial threshold/fee value must be supplied
explicitly by the operator via CLI flags; this module never invents a
default (ADR-007 — `Thresholds` has no exported default instance).

Persisting the `ExecutionRun` is opt-in via `--persist-db`, consistent
with the Fase 3 "Option B" decision (ADR-013): `run_pipeline()` never
persists automatically, and this interface is simply the first concrete
caller that can choose to.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Sequence

import juval
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Decision, Thresholds
from juval.domain.execution_run import ExecutionStatus
from juval.domain.risk import Severity
from juval.infrastructure.excel.exporter import export_excel
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore


def _decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"invalid decimal value: {raw!r}") from exc


def _severity(raw: str) -> Severity:
    try:
        return Severity(raw.upper())
    except ValueError as exc:
        valid = ", ".join(s.value for s in Severity)
        raise argparse.ArgumentTypeError(f"invalid severity {raw!r}; choose from: {valid}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="juval",
        description="Import a supplier Excel, run the sourcing pipeline, and export the results.",
    )
    parser.add_argument("input", type=Path, help="Path to the input .xlsx (supplier catalog)")
    parser.add_argument("output", type=Path, help="Path to write the output .xlsx")

    thresholds = parser.add_argument_group(
        "thresholds (required -- no commercial default exists, ADR-007)"
    )
    thresholds.add_argument("--target-profit", type=_decimal, required=True)
    thresholds.add_argument("--target-roi", type=_decimal, required=True)
    thresholds.add_argument("--min-monthly-sales", type=int, default=0)
    thresholds.add_argument("--max-risk-severity", type=_severity, required=True)
    thresholds.add_argument("--allow-restricted", action="store_true")
    thresholds.add_argument("--allow-approval-required", action="store_true")
    thresholds.add_argument("--allow-unknown-risk", action="store_true")

    fees = parser.add_argument_group("fees (required to compute profitability)")
    fees.add_argument("--referral-fee", type=_decimal, required=True)
    fees.add_argument("--referral-fee-rate", type=_decimal, required=True)
    fees.add_argument("--fulfillment-fee", type=_decimal, default=Decimal("0"))
    fees.add_argument("--other-selling-fees", type=_decimal, default=Decimal("0"))

    parser.add_argument("--execution-id", default=None, help="Defaults to a generated UUID4")
    parser.add_argument(
        "--persist-db",
        type=Path,
        default=None,
        help=(
            "Optional path to a SQLite file. If given, the ExecutionRun is saved there "
            "explicitly after the run (persistence is opt-in, see ADR-013 'Option B')."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    thresholds = Thresholds(
        target_profit=args.target_profit,
        target_roi=args.target_roi,
        minimum_estimated_monthly_sales=args.min_monthly_sales,
        maximum_risk_severity=args.max_risk_severity,
        allow_restricted=args.allow_restricted,
        allow_approval_required=args.allow_approval_required,
        allow_unknown_risk=args.allow_unknown_risk,
    )
    fees = FeeInputs(
        referral_fee=args.referral_fee,
        referral_fee_rate=args.referral_fee_rate,
        fulfillment_fee=args.fulfillment_fee,
        other_selling_fees=args.other_selling_fees,
    )

    execution_id = args.execution_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    try:
        run, records = run_pipeline(
            args.input,
            thresholds,
            fees=fees,
            application_version=juval.__version__,
            execution_id=execution_id,
            now=now,
        )
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    if run.status == ExecutionStatus.FAILED:
        print(f"FAILED: import produced no usable records (execution_id={run.execution_id}).", file=sys.stderr)
        print(f"  input_filename={run.input_filename} input_hash={run.input_hash}", file=sys.stderr)
        return 1

    export_excel(records, args.output)

    decisions = {d: 0 for d in Decision}
    for record in records:
        if record.decision is not None:
            decisions[record.decision.decision] += 1

    print(f"execution_id={run.execution_id} status={run.status.value}")
    print(
        f"records_total={run.records_total} processed={run.records_processed} "
        f"successful={run.records_successful} with_errors={run.records_with_errors} warnings={run.warnings}"
    )
    print(
        f"decisions: BUY={decisions[Decision.BUY]} REVIEW={decisions[Decision.REVIEW]} "
        f"PASS={decisions[Decision.PASS]}"
    )
    print(f"output written to {args.output}")

    if args.persist_db is not None:
        store = SqliteExecutionRunStore(args.persist_db)
        store.save_execution_run(run)
        print(f"execution_run persisted to {args.persist_db} (execution_id={run.execution_id})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
