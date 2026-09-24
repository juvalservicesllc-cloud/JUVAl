"""A real imported legacy record, diagnosed read-only (ADR-047 §20). Synthetic CSV only."""
from datetime import datetime, timezone
from decimal import Decimal

from juval.application.legacy_financial_projection import (
    legacy_financial_operands, legacy_snapshot_financial_operands,
)
from juval.application.record_snapshot import record_to_snapshot
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.financial_evidence import FinancialTerm, LegacyGap, assess_legacy_financial_operands
from juval.infrastructure.excel.importer import import_file
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CSV = ("marketplace,asin,sku,title,brand,cost,selling_price,shipping_per_unit,hazmat,bulky\n"
       "US,B000SYNTH1,SKU-1,Synthetic item,SynthBrand,4.50,19.99,,no,no\n")


def test_imported_record_blank_shipping_default_is_not_an_accredited_zero(tmp_path):
    path = tmp_path / "synthetic.csv"
    path.write_text(CSV, encoding="utf-8", newline="")
    [record] = import_file(path, now=NOW).records
    costs_before = (record.costs.cog, record.costs.shipping_per_unit)
    price = record.product.price.selling_price_used

    report = assess_legacy_financial_operands(legacy_financial_operands(record.costs, record.fees))

    assert record.costs.shipping_per_unit == Decimal("0")  # importer default for a blank cell
    shipping = report.gap_for(FinancialTerm.SHIPPING_PER_UNIT)
    assert LegacyGap.ZERO_INDISTINGUISHABLE_FROM_DEFAULT in shipping.gaps
    assert LegacyGap.ALLOCATION_UNDECLARED in shipping.gaps
    assert LegacyGap.NO_PROVENANCE in report.gap_for(FinancialTerm.COG).gaps
    # The importer attaches no FeeInputs: fee slots are absent, not zero.
    assert record.fees is None
    assert report.gap_for(FinancialTerm.REFERRAL_FEE).gaps == (LegacyGap.STRUCTURALLY_ABSENT,)
    assert not report.satisfies_contract
    assert (record.costs.cog, record.costs.shipping_per_unit) == costs_before
    # The selling price has no FinancialTerm slot: left untouched, never an observation.
    assert record.product.price.selling_price_used is price
    assert price.value == Decimal("19.99")


def test_sqlite_persisted_snapshot_gives_the_same_diagnosis_as_the_dict(tmp_path):
    path = tmp_path / "synthetic.csv"
    path.write_text(CSV, encoding="utf-8", newline="")
    [record] = import_file(path, now=NOW).records
    written = record_to_snapshot(record)
    run = ExecutionRun(execution_id="run-1", started_at=NOW, finished_at=NOW,
                       status=ExecutionStatus.SUCCESS, input_filename="synthetic.csv",
                       input_hash="synthetic", application_version="0.0.0-test",
                       records_total=1, records_processed=1, records_successful=1,
                       records_with_errors=0, warnings=0)
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    store.save_execution_run(run, [written])

    loaded = store.load_record("run-1", record.record_ref)
    from_store = assess_legacy_financial_operands(legacy_snapshot_financial_operands(loaded))

    assert from_store == assess_legacy_financial_operands(legacy_snapshot_financial_operands(written))
    assert store.load_record("run-1", record.record_ref) == loaded  # reading wrote nothing
    assert LegacyGap.ZERO_INDISTINGUISHABLE_FROM_DEFAULT in from_store.gap_for(
        FinancialTerm.SHIPPING_PER_UNIT).gaps
    # The runtime record still has a CostInputs with 12 slots; the snapshot kept 2.
    runtime = assess_legacy_financial_operands(legacy_financial_operands(record.costs, None))
    assert runtime.gap_for(FinancialTerm.VAT).represented
    assert from_store.gap_for(FinancialTerm.VAT).gaps == (LegacyGap.STRUCTURALLY_ABSENT,)
