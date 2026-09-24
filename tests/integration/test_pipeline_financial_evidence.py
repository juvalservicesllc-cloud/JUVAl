"""Native financial evidence transported through run_pipeline (ADR-047). Synthetic files only."""
import ast
import pathlib
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.application import run_pipeline as run_pipeline_module
from juval.application.run_pipeline import (
    bind_financial_captures, run_pipeline, run_pipeline_with_financial_evidence,
)
from juval.domain.decision import Thresholds
from juval.domain.financial_evidence import FinancialEvidenceSet, FinancialTerm
from juval.domain.provenance import SourceType, VerificationStatus
from juval.domain.risk import Severity
from juval.infrastructure.excel.financial_capture import BLANK_CELL_EVIDENCE
from juval.infrastructure.excel.importer import import_file

from .test_native_financial_capture import BASE, COG, FULL, REFERRAL, SCENARIO, declared, xlsx

NOW = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
THRESHOLDS = Thresholds(target_profit=Decimal("3"), target_roi=Decimal("0.3"),
                        minimum_estimated_monthly_sales=1, maximum_risk_severity=Severity.MEDIUM)


def run(path, execution_id="run-A"):
    return run_pipeline_with_financial_evidence(path, THRESHOLDS, application_version="0.0.0-test",
                                                execution_id=execution_id, now=NOW)


def legacy(path, execution_id="run-A"):
    return run_pipeline(path, THRESHOLDS, application_version="0.0.0-test", execution_id=execution_id, now=NOW)


def test_legacy_file_has_no_evidence_and_identical_run(tmp_path):
    path = xlsx(tmp_path, BASE)
    result = run(path)
    assert result.financial_evidence == ()
    assert (result.run, result.records) == legacy(path)


def test_complete_evidence_is_bound_to_the_run_and_record(tmp_path):
    path = xlsx(tmp_path, FULL, {**FULL, "supplier_sku": "SKU-2", "fin_cog_amount": "5.25"})
    result = run(path, "run-XYZ")
    assert [e.record_ref for e in result.financial_evidence] == [r.record_ref for r in result.records]
    second = result.evidence_for(result.records[1].record_ref)
    assert isinstance(second.evidence, FinancialEvidenceSet)
    assert second.execution_id == second.evidence.execution_id == result.run.execution_id == "run-XYZ"
    assert second.evidence.record_reference == result.records[1].record_ref
    assert second.evidence.evidence_for(COG).amount.value == Decimal("5.25")
    assert second.problems == ()


def test_partial_evidence_keeps_unresolved_terms_and_diagnostics(tmp_path):
    rows = [{**BASE, **SCENARIO, **declared(COG, "4.50"), **declared(REFERRAL, "3.00", currency="EUR")},
            {**BASE, "supplier_sku": "SKU-NOSCN", **declared(COG, "4.50")}]
    first, second = run(xlsx(tmp_path, *rows)).financial_evidence
    assert first.evidence.unresolved_required_terms == (REFERRAL, FinancialTerm.REFERRAL_FEE_RATE)
    assert "REFERRAL_FEE: currency EUR is incompatible with scenario currency USD; not converted" in first.problems
    # No complete scenario: no set is fabricated, captured terms and reasons remain.
    assert second.evidence is None
    assert [t.term for t in second.capture.terms] == [COG]
    assert any(p.startswith("scenario: not declared") for p in second.problems)


def test_row_without_native_declaration_gets_a_capture_but_no_fabricated_set(tmp_path):
    result = run(xlsx(tmp_path, FULL, {**BASE, "supplier_sku": "SKU-LEGACY"}))
    plain = result.financial_evidence[1]
    assert plain.evidence is None and plain.capture.terms == ()


def test_dropped_row_does_not_shift_captures_and_duplicate_asin_is_irrelevant(tmp_path):
    rows = [{**FULL, "supplier_sku": "A", "fin_cog_amount": "1.00"},
            {**FULL, "supplier_sku": "DROP", "marketplace": ""},          # importer drops this row
            {**FULL, "supplier_sku": "C", "fin_cog_amount": "3.00"}]      # same ASIN as row A
    result = run(xlsx(tmp_path, *rows))
    assert [r.record_ref for r in result.records] == ["row_2:A", "row_4:C"]
    amounts = {e.record_ref: e.evidence.evidence_for(COG).amount for e in result.financial_evidence}
    assert amounts["row_4:C"].value == Decimal("3.00")
    assert amounts["row_4:C"].provenance.source_reference == "row=4;column=fin_cog_amount"


def test_record_with_legacy_errors_keeps_its_own_capture(tmp_path):
    result = run(xlsx(tmp_path, {**FULL, "cost": "", "fin_cog_amount": "4.50"}))
    [record], [item] = result.records, result.financial_evidence
    assert record.costs is None and record.has_record_errors
    assert item.record_ref == record.record_ref
    assert item.evidence.evidence_for(COG).has_usable_amount
    assert item.problems == ()  # capture diagnostics stay apart from legacy issues


def test_two_files_keep_separate_execution_identities(tmp_path):
    a = run(xlsx(tmp_path, FULL, name="a/in.xlsx"), "run-A")
    b = run(xlsx(tmp_path, {**FULL, "fin_cog_amount": "9.00"}, name="b/in.xlsx"), "run-B")
    assert {e.evidence.execution_id for e in a.financial_evidence} == {"run-A"}
    assert {e.evidence.execution_id for e in b.financial_evidence} == {"run-B"}
    assert b.financial_evidence[0].evidence.evidence_for(COG).amount.value == Decimal("9.00")


def test_cardinality_or_identity_mismatch_is_rejected(tmp_path):
    path = xlsx(tmp_path, FULL, {**FULL, "supplier_sku": "SKU-2"})
    imported = import_file(path, now=NOW)
    records = imported.records
    for bad_import, bad_records in (
        (replace(imported, financial_captures=imported.financial_captures[:1]), records),
        (replace(imported, financial_captures=imported.financial_captures[::-1]), records),
        (replace(imported, financial_captures=(imported.financial_captures[0],) * 2), records),
        (imported, records[::-1]),
        (imported, records[:1]),
    ):
        with pytest.raises(ValueError):
            bind_financial_captures(bad_import, bad_records, execution_id="run-A")


def test_blank_cell_not_found_is_a_supplier_non_declaration(tmp_path):
    item = run(xlsx(tmp_path, {**BASE, **SCENARIO, **declared(COG, "")})).financial_evidence[0]
    amount = item.evidence.evidence_for(COG).amount
    assert amount.status is VerificationStatus.NOT_FOUND
    assert amount.provenance.source_type is SourceType.SUPPLIER_FILE
    assert amount.provenance.evidence == BLANK_CELL_EVIDENCE
    assert amount.provenance.source_reference == "row=2;column=fin_cog_amount"
    assert amount.provenance.source_type is not SourceType.OFFICIAL_API


def test_provenance_context_currency_applicability_and_allocation_survive(tmp_path):
    row = {**BASE, **SCENARIO, **declared(COG, "4.50", source_basis="pack", allocation="pack of 6 split evenly"),
           **declared(REFERRAL, "", applies="no", applies_method="supplier rule")}
    bound = run(xlsx(tmp_path, row)).financial_evidence[0].evidence
    cog = bound.evidence_for(COG)
    assert (cog.amount.status, cog.amount.unit, cog.allocation_method) == (
        VerificationStatus.VERIFIED, "USD", "pack of 6 split evenly")
    assert cog.amount.provenance.source_type is SourceType.SUPPLIER_FILE
    assert cog.context.effective_at == datetime(2026, 2, 1, tzinfo=timezone.utc)
    exclusion = bound.evidence_for(REFERRAL)
    assert exclusion.applicability.excludes and exclusion.amount is None
    assert exclusion.applicability.applies.status is VerificationStatus.INFERRED


def test_evidence_never_changes_profitability_decisions_or_risk(tmp_path):
    base = legacy(xlsx(tmp_path, {**BASE, "hazmat": "yes"}, name="legacy/in.xlsx"))
    native = run(xlsx(tmp_path, {**FULL, "hazmat": "yes", "fin_cog_amount": "0"}, name="native/in.xlsx"))
    [a], [b] = base[1], native.records
    assert (a.profitability, a.decision, a.risk, a.score, a.costs, a.fees) == \
        (b.profitability, b.decision, b.risk, b.score, b.costs, b.fees)
    assert b.costs.cog == Decimal("4.50")  # legacy cost column, not the native declaration
    assert base[0] == replace(native.run, input_hash=base[0].input_hash)


def test_no_evidence_from_legacy_defaults(tmp_path):
    result = run(xlsx(tmp_path, {**FULL, "shipping_per_unit": ""}))
    bound = result.financial_evidence[0].evidence
    assert result.records[0].costs.shipping_per_unit == Decimal("0")  # legacy default
    assert bound.evidence_for(FinancialTerm.SHIPPING_PER_UNIT) is None


def test_transport_is_deterministic_immutable_and_stateless(tmp_path):
    path = xlsx(tmp_path, FULL, {**BASE, "supplier_sku": "X"})
    first, second = run(path), run(path)
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.financial_evidence = ()
    assert isinstance(first.financial_evidence, tuple)
    # No module-level mutable containers were introduced for transport.
    tree = ast.parse(pathlib.Path(run_pipeline_module.__file__).read_text(encoding="utf-8"))
    module_assignments = [node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))]
    assert module_assignments == []


def test_no_persistence_or_api_dependency():
    tree = ast.parse(pathlib.Path(run_pipeline_module.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not {m for m in modules if m and ("persistence" in m or "interfaces" in m or "logging" in m
                                              or "record_snapshot" in m or "profitability" in m)}
