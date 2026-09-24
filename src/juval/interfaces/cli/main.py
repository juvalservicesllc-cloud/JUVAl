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

Native financial evidence (ADR-047) is a second opt-in, `--native-financial-evidence`,
and needs `--persist-db`: the run, its record snapshots and one v1 financial
document per record with declared native evidence are saved in one SQLite
transaction. It never changes records, profitability or decisions. Its only
extra inputs are explicit flags with their own unit (`--financial-target-profit`
+ `--financial-target-profit-currency`, `--financial-target-roi` as a ratio);
the commercial `--target-*` thresholds are never reused, and no per-record
weight input exists, so per-pound shipping results stay blocked.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Sequence

import juval
from juval.application.financial_persistence import save_run_with_financial_records
from juval.application.native_financial_documents import build_financial_documents
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline, run_pipeline_with_financial_evidence
from juval.domain.costs import FeeInputs
from juval.domain.decision import Decision, Thresholds
from juval.domain.execution_run import ExecutionStatus
from juval.domain.provenance import FieldValue, SourceType
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

    financial = parser.add_argument_group(
        "native financial evidence (ADR-047, opt-in; never changes profitability or decisions)"
    )
    financial.add_argument(
        "--native-financial-evidence", action="store_true",
        help="Resolve, calculate and persist the file's fin_* evidence (requires --persist-db).",
    )
    financial.add_argument("--financial-target-profit", type=_decimal, default=None,
                           help="Target profit amount for MAX_COG_TARGET_PROFIT (needs its currency).")
    financial.add_argument("--financial-target-profit-currency", default=None,
                           help="Currency of --financial-target-profit, e.g. USD; never inferred.")
    financial.add_argument("--financial-target-roi", type=_decimal, default=None,
                           help="Target ROI as a ratio (0.30 = 30%%) for MAX_COG_TARGET_ROI.")
    return parser


def _financial_input(value: Decimal, unit: str, flag: str, now: datetime) -> FieldValue:
    # Declared by the operator for this run: USER_INPUT, never a supplier or Amazon value.
    return FieldValue.verified(value, unit=unit, source="juval-cli", method=f"operator flag {flag}",
                               retrieved_at=now, source_type=SourceType.USER_INPUT)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.native_financial_evidence and args.persist_db is None:
        parser.error("--native-financial-evidence requires --persist-db")
    financial_flags = (args.financial_target_profit, args.financial_target_profit_currency, args.financial_target_roi)
    if not args.native_financial_evidence and any(flag is not None for flag in financial_flags):
        parser.error("--financial-target-* flags require --native-financial-evidence")
    if (args.financial_target_profit is None) != (args.financial_target_profit_currency is None):
        parser.error("--financial-target-profit and --financial-target-profit-currency go together")

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

    pipeline = run_pipeline_with_financial_evidence if args.native_financial_evidence else run_pipeline
    try:
        outcome = pipeline(
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
    run, records = (outcome.run, outcome.records) if args.native_financial_evidence else outcome

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

    if args.native_financial_evidence:
        return _persist_native_financial(args, outcome, now)

    if args.persist_db is not None:
        store = SqliteExecutionRunStore(args.persist_db)
        store.save_execution_run(run)
        print(f"execution_run persisted to {args.persist_db} (execution_id={run.execution_id})")

    return 0


def _persist_native_financial(args: argparse.Namespace, outcome, now: datetime) -> int:
    target_profit = None
    if args.financial_target_profit is not None:
        target_profit = _financial_input(args.financial_target_profit, args.financial_target_profit_currency,
                                         "--financial-target-profit", now)
    target_roi = None
    if args.financial_target_roi is not None:
        target_roi = _financial_input(args.financial_target_roi, "ratio", "--financial-target-roi", now)
    documents = build_financial_documents(outcome, calculated_at=now, target_profit=target_profit,
                                          target_roi=target_roi)
    problems = sum(len(item.problems) for item in outcome.financial_evidence)
    print(f"financial: captures={len(outcome.financial_evidence)} documents={len(documents)} "
          f"without_scenario={sum(1 for item in outcome.financial_evidence if item.evidence is None)} "
          f"capture_problems={problems}")
    for item in outcome.financial_evidence:
        for problem in item.problems:
            print(f"  {item.record_ref}: {problem}")
    try:
        save_run_with_financial_records(SqliteExecutionRunStore(args.persist_db), outcome.run,
                                        [record_to_snapshot(record) for record in outcome.records], documents)
    except (ValueError, sqlite3.Error) as error:
        # One transaction: nothing of this run was persisted.
        print(f"error: persistence failed, nothing was persisted for {outcome.run.execution_id}: {error}",
              file=sys.stderr)
        return 3
    print(f"execution_run, {len(outcome.records)} record snapshots and {len(documents)} financial documents "
          f"persisted to {args.persist_db} (execution_id={outcome.run.execution_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
