"""Native financial evidence capture from new XLSX imports (ADR-047 §22 step 3).

Synthetic workbooks only: no supplier, fee schedule or commercial data.
"""
import ast
import pathlib
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest

from juval.domain.financial_evidence import FinancialEvidenceSet, FinancialTerm, FinancialTermEvidence
from juval.domain.provenance import SourceType, VerificationStatus
from juval.infrastructure.excel import financial_capture
from juval.infrastructure.excel.column_mapping import (
    COLUMN_SPECS, FINANCIAL_EVIDENCE_COLUMN_SPECS, financial_term_column,
)
from juval.infrastructure.excel.importer import import_csv, import_excel, import_file
from juval.processing.pipeline import process_batch

NOW = datetime(2026, 3, 1, 12, tzinfo=timezone.utc)
EFFECTIVE = "2026-02-01T00:00:00+00:00"
BASE = {"marketplace": "US", "asin": "B000SYNTH1", "supplier_sku": "SKU-1", "cost": "4.50",
        "selling_price": "19.99"}
SCENARIO = {"fin_scenario_id": "synthetic-scenario", "fin_scenario_version": "v1", "fin_currency": "USD",
            "fin_sellable_unit": "one sellable unit", "fin_policy_identity": "synthetic-policy@v1",
            "fin_required_terms": "COG;REFERRAL_FEE;REFERRAL_FEE_RATE"}
COG, REFERRAL, RATE = FinancialTerm.COG, FinancialTerm.REFERRAL_FEE, FinancialTerm.REFERRAL_FEE_RATE


def col(term, suffix):
    return financial_term_column(term, suffix)


def declared(term, amount="1.00", *, currency="USD", applies="yes", **extra):
    cells = {col(term, "applies"): applies, col(term, "justification"): "synthetic declaration",
             col(term, "effective_at"): EFFECTIVE, col(term, "basis"): "synthetic per-unit basis"}
    if amount is not None:
        cells[col(term, "amount")] = amount
    if currency is not None:
        cells[col(term, "currency")] = currency
    cells.update({col(term, key): value for key, value in extra.items()})
    return cells


FULL = {**BASE, **SCENARIO, **declared(COG, "4.50"), **declared(REFERRAL, "3.00"),
        **declared(RATE, "0.15", currency=None)}


def xlsx(tmp_path, *rows, name="synthetic.xlsx"):
    headers = list(dict.fromkeys(key for row in rows for key in row))
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header) for header in headers])
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def capture_of(tmp_path, row):
    result = import_excel(xlsx(tmp_path, row), now=NOW)
    [capture] = result.financial_captures
    return capture


def evidence(capture, term):
    return next((item for item in capture.terms if item.term == term), None)


# -- Column contract -------------------------------------------------------

def test_native_columns_are_optional_unique_and_ratio_has_no_currency_column():
    headers = [spec.canonical for spec in FINANCIAL_EVIDENCE_COLUMN_SPECS]
    assert len(headers) == len(set(headers))
    assert not set(headers) & {spec.canonical for spec in COLUMN_SPECS}
    assert not any(spec.required for spec in FINANCIAL_EVIDENCE_COLUMN_SPECS)
    assert col(RATE, "currency") not in headers
    assert all(col(term, "amount") in headers for term in FinancialTerm)


# -- Legacy compatibility --------------------------------------------------

def test_legacy_workbook_has_no_capture_and_identical_records(tmp_path):
    legacy = import_excel(xlsx(tmp_path, BASE, name="legacy/s.xlsx"), now=NOW)
    native = import_excel(xlsx(tmp_path, FULL, name="native/s.xlsx"), now=NOW)
    assert legacy.financial_captures == ()
    assert not any(issue.code == "UNKNOWN_COLUMN" for issue in native.issues)
    assert [i.code for i in native.issues] == [i.code for i in legacy.issues]
    # Native columns never reach CostInputs/FeeInputs, profitability or decisions.
    legacy_record, native_record = legacy.records[0], native.records[0]
    assert native_record.costs == legacy_record.costs and native_record.fees is None
    assert native_record == legacy_record


def test_pipeline_decisions_are_unchanged_by_native_columns(tmp_path):
    from juval.domain.decision import Thresholds
    from juval.domain.risk import Severity
    thresholds = Thresholds(target_profit=Decimal("3"), target_roi=Decimal("0.3"),
                            minimum_estimated_monthly_sales=1, maximum_risk_severity=Severity.MEDIUM)
    legacy = import_excel(xlsx(tmp_path, BASE, name="legacy/s.xlsx"), now=NOW).records
    native = import_excel(xlsx(tmp_path, FULL, name="native/s.xlsx"), now=NOW).records
    [a] = process_batch(legacy, thresholds, now=NOW)
    [b] = process_batch(native, thresholds, now=NOW)
    assert (a.profitability, a.decision, a.issues) == (b.profitability, b.decision, b.issues)


def test_csv_and_xlsx_capture_identically(tmp_path):
    headers = list(FULL)
    csv_path = tmp_path / "synthetic.csv"
    csv_path.write_text(",".join(headers) + "\n" + ",".join(FULL[h] for h in headers) + "\n",
                        encoding="utf-8", newline="")
    assert import_csv(csv_path, now=NOW).financial_captures == \
        replace_source(import_excel(xlsx(tmp_path, FULL), now=NOW).financial_captures, "synthetic.csv")


def replace_source(captures, source):
    def swap(fv):
        return None if fv is None else replace(fv, provenance=replace(fv.provenance, source=source))
    return tuple(replace(c, terms=tuple(
        replace(t, amount=swap(t.amount), applicability=replace(t.applicability, applies=swap(t.applicability.applies)))
        for t in c.terms)) for c in captures)


# -- Complete and partial evidence -----------------------------------------

def test_complete_declaration_binds_one_evidence_set_per_record(tmp_path):
    result = import_excel(xlsx(tmp_path, FULL, {**FULL, "supplier_sku": "SKU-2"}), now=NOW)
    assert [c.record_ref for c in result.financial_captures] == [r.record_ref for r in result.records]
    capture = result.financial_captures[0]
    assert capture.problems == ()
    bound = capture.bind("run-0001")
    assert isinstance(bound, FinancialEvidenceSet)
    assert (bound.execution_id, bound.record_reference) == ("run-0001", result.records[0].record_ref)
    assert bound.unresolved_required_terms == ()
    assert bound.evidence_for(COG).amount.value == Decimal("4.50")
    assert bound.evidence_for(COG).amount.unit == "USD"
    assert bound.evidence_for(RATE).amount.unit == "ratio"


def test_partial_declaration_keeps_missing_terms_unresolved_not_excluded(tmp_path):
    row = {**BASE, **SCENARIO, **declared(COG, "4.50")}
    capture = capture_of(tmp_path, row)
    bound = capture.bind("run-1")
    assert [t.term for t in capture.terms] == [COG]
    assert bound.unresolved_required_terms == (REFERRAL, RATE)
    assert bound.evidence_for(REFERRAL) is None


# -- Absence, blank, zero, invalid -----------------------------------------

def test_absent_amount_column_is_structural_absence(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, None)})
    assert evidence(capture, COG).amount is None


def test_blank_amount_cell_is_not_found_never_zero(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "")})
    amount = evidence(capture, COG).amount
    assert amount.status is VerificationStatus.NOT_FOUND and amount.value is None


def test_explicit_zero_is_declared_but_its_applicability_is_separate(tmp_path):
    zero = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(REFERRAL, "0")}), REFERRAL)
    assert zero.amount.value == Decimal("0") and zero.amount.status is VerificationStatus.VERIFIED
    unresolved = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(REFERRAL, "0", applies="")}),
                          REFERRAL)
    assert unresolved.amount.value == Decimal("0") and not unresolved.applicability.is_resolved


@pytest.mark.parametrize("raw", ["abc", "NaN", "Infinity", "-Infinity", "sNaN", "-1"])
def test_invalid_or_non_finite_amount_is_invalid_with_raw_value(tmp_path, raw):
    amount = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, raw)}), COG).amount
    assert amount.status is VerificationStatus.INVALID
    assert amount.value is None and amount.raw_value == raw


# -- Scenario and currency --------------------------------------------------

def test_missing_currency_builds_no_scenario_and_says_why(tmp_path):
    row = {**FULL, "fin_currency": ""}
    capture = capture_of(tmp_path, row)
    assert capture.scenario is None
    assert "scenario: not declared: fin_currency" in capture.problems
    with pytest.raises(ValueError, match="no complete financial scenario"):
        capture.bind("run-1")


def test_amount_without_its_own_currency_is_not_captured(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "4.50", currency="")})
    assert evidence(capture, COG) is None
    assert any(p.startswith("COG:") and "currency" in p for p in capture.problems)


def test_incompatible_currency_is_rejected_not_converted(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "4.50", currency="EUR")})
    assert evidence(capture, COG) is None
    assert "COG: currency EUR is incompatible with scenario currency USD; not converted" in capture.problems


def test_malformed_scenario_declarations_are_reported(tmp_path):
    for overrides in ({"fin_currency": "usd"}, {"fin_required_terms": "COG;SHIPPING_COST"}):
        capture = capture_of(tmp_path, {**FULL, **overrides})
        assert capture.scenario is None and any(p.startswith("scenario:") for p in capture.problems)


# -- Applicability and exclusions ------------------------------------------

def test_blank_applicability_is_unresolved(tmp_path):
    item = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "4.50", applies="")}), COG)
    assert not item.applicability.is_resolved and not item.applicability.excludes
    assert item.applicability.applies.status is VerificationStatus.NOT_FOUND


def test_missing_applicability_column_is_never_inferred_from_the_amount(tmp_path):
    row = {**BASE, **SCENARIO, **declared(COG, "4.50")}
    del row[col(COG, "applies")]
    capture = capture_of(tmp_path, row)
    assert evidence(capture, COG) is None
    assert any("applicability is never inferred" in p for p in capture.problems)


def test_declared_exclusion_carries_no_amount(tmp_path):
    item = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(REFERRAL, "", applies="no")}),
                    REFERRAL)
    assert item.applicability.excludes and item.amount is None
    assert item.applicability.applies.status is VerificationStatus.VERIFIED


def test_exclusion_with_an_amount_even_zero_is_rejected(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(REFERRAL, "0", applies="no")})
    assert evidence(capture, REFERRAL) is None
    assert any("exclusion carries no amount" in p for p in capture.problems)


def test_supplier_inferred_exclusion_stays_inferred(tmp_path):
    row = {**BASE, **SCENARIO, **declared(REFERRAL, "", applies="no",
                                          applies_method="supplier rule: private-label items")}
    applies = evidence(capture_of(tmp_path, row), REFERRAL).applicability.applies
    assert applies.status is VerificationStatus.INFERRED
    assert applies.provenance.method == "supplier rule: private-label items"


def test_applicability_assertion_requires_a_declared_justification(tmp_path):
    row = {**BASE, **SCENARIO, **declared(COG, "4.50", justification="")}
    capture = capture_of(tmp_path, row)
    assert evidence(capture, COG) is None


# -- Referral rate ----------------------------------------------------------

def test_referral_rate_is_a_ratio_and_out_of_range_is_invalid(tmp_path):
    ok = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(RATE, "0.15", currency=None)}), RATE)
    assert ok.amount.unit == "ratio" and ok.amount.value == Decimal("0.15")
    for raw in ("1", "15", "-0.1"):
        bad = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(RATE, raw, currency=None)}), RATE)
        assert bad.amount.status is VerificationStatus.INVALID and bad.amount.raw_value == raw


def test_a_ratio_currency_header_is_not_a_native_column(tmp_path):
    row = {**BASE, **SCENARIO, **declared(RATE, "0.15", currency=None), "fin_referral_fee_rate_currency": "USD"}
    result = import_excel(xlsx(tmp_path, row), now=NOW)
    assert any(i.code == "UNKNOWN_COLUMN" and i.field == "fin_referral_fee_rate_currency" for i in result.issues)


# -- Allocation and COG -------------------------------------------------------

def test_cog_per_sellable_unit_needs_no_allocation(tmp_path):
    item = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "4.50")}), COG)
    assert item.allocation_method is None and item.has_usable_amount


def test_pack_sourced_cog_requires_and_keeps_its_declared_allocation(tmp_path):
    allocated = {**BASE, **SCENARIO, **declared(COG, "4.50", source_basis="pack",
                                                allocation="pack of 6 at 27.00 split evenly")}
    item = evidence(capture_of(tmp_path, allocated), COG)
    assert item.allocation_method == "pack of 6 at 27.00 split evenly"
    assert item.amount.value == Decimal("4.50")  # declared per unit, never divided here
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "27.00", source_basis="pack")})
    assert evidence(capture, COG) is None
    assert any("allocation" in p for p in capture.problems)


def test_allocated_term_without_allocation_is_rejected(tmp_path):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(FinancialTerm.STORAGE, "0.20")})
    assert evidence(capture, FinancialTerm.STORAGE) is None
    assert any(p.startswith("STORAGE:") and "allocation_method" in p for p in capture.problems)


# -- Effective context ------------------------------------------------------

@pytest.mark.parametrize("effective_at", ["", "2026-02-01T00:00:00", "tomorrow",
                                          datetime(2026, 2, 1)])
def test_missing_naive_or_malformed_effective_at_is_not_substituted(tmp_path, effective_at):
    capture = capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "4.50", effective_at=effective_at)})
    assert evidence(capture, COG) is None
    assert any(p.startswith("COG:") for p in capture.problems)


def test_effective_at_stays_separate_from_retrieval(tmp_path):
    item = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "4.50")}), COG)
    assert item.context.effective_at == datetime(2026, 2, 1, tzinfo=timezone.utc)
    assert item.amount.provenance.retrieved_at == NOW


# -- Provenance and scope guards --------------------------------------------

def test_provenance_is_supplier_file_and_never_amazon(tmp_path):
    item = evidence(capture_of(tmp_path, FULL), COG)
    provenance = item.amount.provenance
    assert provenance.source_type is SourceType.SUPPLIER_FILE
    assert provenance.source == "synthetic.xlsx"
    assert provenance.source_reference == "row=2;column=fin_cog_amount"
    assert provenance.source_type is not SourceType.OFFICIAL_API


def test_capture_is_deterministic(tmp_path):
    path = xlsx(tmp_path, FULL, {**FULL, "supplier_sku": "SKU-2", "fin_currency": ""})
    assert import_file(path, now=NOW) == import_file(path, now=NOW)


def test_capture_creates_no_price_observation_and_touches_no_downstream_layer():
    tree = ast.parse(pathlib.Path(financial_capture.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported == {"__future__", "dataclasses", "datetime", "decimal", "typing",
                        "juval.domain.financial_evidence", "juval.domain.provenance", "juval.domain.units",
                        "column_mapping"}
    assert not {"PriceObservation", "CostInputs", "FeeInputs"} & set(vars(financial_capture))


def test_captured_terms_are_domain_evidence_not_a_parallel_model(tmp_path):
    capture = capture_of(tmp_path, FULL)
    assert all(type(item) is FinancialTermEvidence for item in capture.terms)


def test_numeric_excel_cell_is_read_by_its_shortest_repr_without_arithmetic(tmp_path):
    # XLSX stores numbers as binary doubles; the importer reads the displayed
    # shortest repr (same rule as every legacy decimal column), never float math.
    item = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, 0.1)}), COG)
    assert item.amount.value == Decimal("0.1")
    text = evidence(capture_of(tmp_path, {**BASE, **SCENARIO, **declared(COG, "0.10")}), COG)
    assert str(text.amount.value) == "0.10"
