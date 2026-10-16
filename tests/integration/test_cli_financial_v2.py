"""CLI opt-in flow writing format v2 to temporary SQLite; v1 rows stay v1. Synthetic data only."""
import json
from dataclasses import replace
from decimal import Decimal

import pytest

import juval
from juval.application import financial_persistence
from juval.application.financial_persistence import load_financial_record, save_run_with_financial_records
from juval.application.financial_recalculation import check_recalculation
from juval.application.financial_serialization import FinancialRecordDocument
from juval.application.financial_serialization_v2 import (
    FinancialRecordDocumentV2, assess_reproducibility, current_dependency_matrix_digest,
    current_expressions_digest, serialize_financial_record_v2,
)
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.financial_dependencies import FinancialResult as R, ResolutionBlocker
from juval.domain.financial_evidence import FinancialTerm as T
from juval.domain.provenance import SourceType, VerificationStatus as VS
from juval.domain.risk import Severity

from .test_cli_native_financial import FINANCIAL, NOW, cli_run, count, fixed_now, refs, row  # noqa: F401 (fixture)
from .test_native_financial_capture import declared


def load_v2(store, execution_id="run-A", index=0):
    document = load_financial_record(store, execution_id, refs(store, execution_id)[index])
    assert type(document) is FinancialRecordDocumentV2
    return document


def test_cli_writes_canonical_v2_rows_that_round_trip(tmp_path):
    code, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    assert code == 0
    ref = refs(store)[0]
    stored_format, stored_version, text = store.load_financial_record("run-A", ref)
    assert (stored_format, stored_version) == ("juval.adr047.financial-record", 2)
    document = load_financial_record(store, "run-A", ref)
    assert json.dumps(serialize_financial_record_v2(document), sort_keys=True) == text
    core = document.document
    assert str(core.evidence.evidence_for(T.COG).amount.value) == "4.50"
    assert core.evidence.evidence_for(T.COG).amount.provenance.source_type is SourceType.SUPPLIER_FILE
    assert core.calculations.for_result(R.PROFIT).value.value == Decimal("9.30")
    cog = next(d for d in core.resolution.for_result(R.PROFIT).dependencies if d.dependency == "COG")
    assert cog.evidence is core.evidence.evidence_for(T.COG)


def test_supplied_inputs_are_what_the_resolver_received(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    document = load_v2(store)
    inputs = document.supplied_inputs
    assert inputs.selling_price == document.document.selling_price.amount            # the declared native price
    assert str(inputs.selling_price.value) == "20.00"
    assert (inputs.target_profit.value, inputs.target_profit.unit) == (Decimal("3"), "USD")
    assert (inputs.target_roi.value, inputs.target_roi.unit) == (Decimal("0.30"), "ratio")
    assert inputs.target_profit.provenance.source_type is SourceType.USER_INPUT
    assert inputs.weight is None                                                        # no per-record weight input


def test_targets_absent_stay_absent_and_blocked_results_survive(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], "--native-financial-evidence")
    document = load_v2(store)
    assert (document.supplied_inputs.target_profit, document.supplied_inputs.target_roi) == (None, None)
    item = document.document.calculations.for_result(R.MAX_COG_TARGET_ROI)
    assert item.value.status is VS.NOT_FOUND and item.blocker is not None


@pytest.mark.parametrize("raw,status,blocker", [
    ("", VS.NOT_FOUND, ResolutionBlocker.VALUE_NOT_FOUND),
    ("abc", VS.INVALID, ResolutionBlocker.VALUE_INVALID),
])
def test_unusable_native_price_is_kept_as_supplied(tmp_path, raw, status, blocker):
    _, _, store = cli_run(tmp_path, [row("A", fin_selling_price_amount=raw)], *FINANCIAL)
    document = load_v2(store)
    price = document.supplied_inputs.selling_price
    assert price.status is status and price.value is None
    if status is VS.INVALID:
        assert price.raw_value == "abc"                                                  # original value survives
    [dep] = [d for d in document.document.resolution.for_result(R.PROFIT).blockers if d.dependency == "SELLING_PRICE"]
    assert dep.blocker is blocker


def test_incompatible_target_currency_is_kept_verbatim(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], "--native-financial-evidence", "--financial-target-profit", "3",
                          "--financial-target-profit-currency", "EUR")
    document = load_v2(store)
    assert document.supplied_inputs.target_profit.unit == "EUR"
    [blocked] = document.document.resolution.for_result(R.MAX_COG_TARGET_PROFIT).blockers
    assert blocked.blocker is ResolutionBlocker.CURRENCY_INCOMPATIBLE


def test_capture_problems_keep_text_and_the_structure_emitted_at_source(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A", **declared(T.PREP, "0.40", currency=""))], *FINANCIAL)
    document = load_v2(store)
    [problem] = document.capture_problems
    assert problem.text.startswith("PREP: a monetary amount requires its declared currency")
    # Emitted by the capturer (4M): the blank currency cell is the cause, it has no raw value.
    assert (problem.subject, problem.row, problem.column, problem.raw_value) == ("PREP", 2, "fin_prep_currency", None)
    assert document.document.evidence.evidence_for(T.PREP) is None                       # not turned into evidence


def test_problems_belong_to_their_own_record(tmp_path):
    rows = [row("A"), row("B", **declared(T.PREP, "0.40", currency=""))]
    _, _, store = cli_run(tmp_path, rows, *FINANCIAL)
    assert load_v2(store, index=0).capture_problems == ()
    assert len(load_v2(store, index=1).capture_problems) == 1


def test_implementation_identity_is_real_and_unknowns_stay_unknown(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    identity = load_v2(store).implementation
    assert identity.application_version == juval.__version__
    assert (identity.code_revision, identity.configuration, identity.derivation_methods) == (None, None, ())
    assert identity.expressions_digest == current_expressions_digest()
    assert identity.dependency_matrix_digest == current_dependency_matrix_digest()


def test_reproducibility_of_cli_documents_is_assessed_not_claimed(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    assessment = assess_reproducibility(load_v2(store))
    assert assessment.state_recovery == () and assessment.input_reconstruction == ()
    assert "code_revision is unknown" in assessment.historical_reproduction
    assert "the code and runtime a document names cannot be verified from the document" in \
        assessment.historical_reproduction


def test_existing_v1_rows_are_read_as_v1_next_to_new_v2_rows(tmp_path):
    _, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    new_core = load_v2(store).document
    # A pre-4L style v1 document for another run, written through the same writer.
    old_run = replace(store.load_execution_run("run-A"), execution_id="run-OLD")
    old_v1 = FinancialRecordDocument(replace(new_core.evidence, execution_id="run-OLD"), new_core.selling_price)
    snapshot = store.load_records("run-A")[0]
    save_run_with_financial_records(store, old_run, [snapshot], [old_v1])
    ref = snapshot["record_ref"]
    assert store.load_financial_record("run-OLD", ref)[1] == 1
    loaded_old = load_financial_record(store, "run-OLD", ref)
    assert type(loaded_old) is FinancialRecordDocument and loaded_old == old_v1           # not upgraded
    assert type(load_financial_record(store, "run-A", ref)) is FinancialRecordDocumentV2


def test_v2_serialization_failure_persists_nothing(tmp_path, monkeypatch, capsys):
    def fail(_document):
        raise financial_persistence.FinancialSerializationError("synthetic v2 serialization failure")

    monkeypatch.setattr(financial_persistence, "serialize_financial_record_v2", fail)
    code, _, store = cli_run(tmp_path, [row("A")], *FINANCIAL)
    assert code == 3 and "nothing was persisted" in capsys.readouterr().err
    assert store.load_execution_run("run-A") is None and store.load_records("run-A") == []
    assert count(tmp_path / "runs.db") == 0


def test_snapshots_written_with_v2_documents_are_the_commercial_ones(tmp_path):
    _, path, store = cli_run(tmp_path, [row("A"), row("B", hazmat="yes")], *FINANCIAL)
    fees = FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2"))
    thresholds = Thresholds(target_profit=Decimal("5"), target_roi=Decimal("0.3"), minimum_estimated_monthly_sales=0,
                            maximum_risk_severity=Severity.LOW)
    _, records = run_pipeline(path, thresholds, fees=fees, application_version=juval.__version__,
                              execution_id="run-A", now=NOW)
    assert store.load_records("run-A") == [record_to_snapshot(r) for r in records]


@pytest.mark.parametrize("args", [FINANCIAL, ("--native-financial-evidence",)], ids=["targets", "no-targets"])
def test_documents_read_back_from_sqlite_recalculate_exactly_under_the_current_code(tmp_path, args):
    _, _, store = cli_run(tmp_path, [row("A"), row("B")], *args)
    for index in range(2):
        check = check_recalculation(load_v2(store, index=index))
        assert check.matches, check
