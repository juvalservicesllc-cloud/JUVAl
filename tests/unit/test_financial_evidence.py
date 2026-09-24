"""Synthetic fixtures only: no provider evidence, fee schedule or commercial calibration."""
import ast
import pathlib
import sys
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from juval.domain.financial_evidence import (
    MAX_EXCLUSIVE_RATE, RATIO_UNIT, Applicability, EffectiveContext, FinancialDependency,
    FinancialEvidenceSet, FinancialScenario, FinancialTerm, FinancialTermEvidence, TermNature,
)
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus

NOW = datetime(2026, 2, 3, tzinfo=timezone.utc)
EFFECTIVE = NOW - timedelta(days=7)
BASIS = "synthetic per-unit amount, duties excluded, not included in any other term"
CONTEXT = EffectiveContext(effective_at=EFFECTIVE, basis_definition=BASIS)


def fv(value, unit=None, status=VerificationStatus.VERIFIED, retrieved_at=NOW):
    common = dict(source="synthetic-fixture", method="explicit synthetic declaration",
                  retrieved_at=retrieved_at, source_type=SourceType.USER_INPUT,
                  evidence="test fixture, not live data", source_reference="fixture:1")
    if status == VerificationStatus.NOT_FOUND:
        return FieldValue.not_found(**common)
    if status == VerificationStatus.INVALID:
        return FieldValue.invalid(value, **common)
    build = FieldValue.verified if status == VerificationStatus.VERIFIED else FieldValue.inferred
    return build(value, unit=unit, **common)


def applies(value=True, status=VerificationStatus.VERIFIED):
    return Applicability(applies=fv(value, status=status),
                         justification="synthetic scenario declares this term explicitly")


def term(kind=FinancialTerm.COG, amount="unset", **overrides):
    if amount == "unset":
        amount = fv(Decimal("4.50"), "USD")
    data = dict(term=kind, applicability=applies(), context=CONTEXT, amount=amount)
    data.update(overrides)
    return FinancialTermEvidence(**data)


def scenario(**overrides):
    data = dict(scenario_id="synthetic-scenario", scenario_version="v1", currency="USD",
                sellable_unit_definition="one sellable unit, single-unit pack",
                policy_identity="synthetic-policy@v1",
                required_terms=frozenset({FinancialTerm.COG, FinancialTerm.REFERRAL_FEE}),
                context_requirements=("effective fee schedule window",))
    data.update(overrides)
    return FinancialScenario(**data)


def evidence_set(terms=(), **overrides):
    data = dict(scenario=scenario(), execution_id="run-0001",
                record_reference="record-0001", terms=terms)
    data.update(overrides)
    return FinancialEvidenceSet(**data)


# -- Natures, units and currency ------------------------------------------

def test_every_adr_047_term_declares_one_explicit_nature():
    assert len(FinancialTerm) == 16
    assert FinancialTerm.SHIPPING_PER_POUND.nature is TermNature.MONETARY_PER_POUND
    assert FinancialTerm.REFERRAL_FEE_RATE.nature is TermNature.DIMENSIONLESS_RATIO
    monetary = [t for t in FinancialTerm if t.nature is TermNature.MONETARY_PER_SELLABLE_UNIT]
    assert len(monetary) == 14 and FinancialTerm.REFERRAL_FEE in monetary


def test_per_pound_rate_requires_currency_per_pound_unit():
    assert term(FinancialTerm.SHIPPING_PER_POUND, fv(Decimal("0.55"), "USD/lb")).has_usable_amount
    for unit in ("USD", "USD/kg", "/lb", "usd/lb", RATIO_UNIT):
        with pytest.raises(ValueError):
            term(FinancialTerm.SHIPPING_PER_POUND, fv(Decimal("0.55"), unit))


@pytest.mark.parametrize("unit", [None, "", "US", "usd", "U$D", RATIO_UNIT])
def test_usable_monetary_amount_requires_an_explicit_currency_unit(unit):
    with pytest.raises(ValueError):
        term(FinancialTerm.COG, fv(Decimal("4.50"), unit))


def test_evidence_set_rejects_currency_incompatible_with_the_scenario():
    with pytest.raises(ValueError, match="incompatible with scenario currency"):
        evidence_set((term(FinancialTerm.COG, fv(Decimal("4.50"), "EUR")),))
    with pytest.raises(ValueError, match="incompatible with scenario currency"):
        evidence_set((term(FinancialTerm.SHIPPING_PER_POUND, fv(Decimal("0.55"), "EUR/lb"),
                           allocation_method=None),))
    assert evidence_set((term(FinancialTerm.COG),)).evidence_for(FinancialTerm.COG) is not None


def test_unusable_amount_keeps_diagnostics_without_asserting_a_currency():
    not_found = term(FinancialTerm.COG, fv(None, status=VerificationStatus.NOT_FOUND))
    invalid = term(FinancialTerm.COG, fv("four fifty", status=VerificationStatus.INVALID))
    for evidence in (not_found, invalid):
        assert not evidence.has_usable_amount and evidence.amount.value is None
        assert evidence_set((evidence,)).evidence_for(FinancialTerm.COG) is evidence
    assert invalid.amount.raw_value == "four fifty"
    assert not_found.amount.provenance.evidence == "test fixture, not live data"


# -- Referral rate: ratio semantics and bounds ----------------------------

def test_referral_rate_is_a_ratio_never_a_currency_or_a_percentage():
    rate = term(FinancialTerm.REFERRAL_FEE_RATE, fv(Decimal("0.15"), RATIO_UNIT))
    assert rate.amount.unit == RATIO_UNIT
    for unit in ("USD", "USD/lb", "%", "percent", None):
        with pytest.raises(ValueError, match="dimensionless ratio"):
            term(FinancialTerm.REFERRAL_FEE_RATE, fv(Decimal("0.15"), unit))
    with pytest.raises(ValueError, match=r"ratio within \[0, 1\)"):
        term(FinancialTerm.REFERRAL_FEE_RATE, fv(Decimal("15"), RATIO_UNIT))


@pytest.mark.parametrize("value,accepted", [
    (Decimal("0"), True), (Decimal("0.9999"), True),
    (MAX_EXCLUSIVE_RATE, False), (Decimal("1.2"), False), (Decimal("-0.01"), False),
])
def test_usable_referral_rate_bounds_match_the_break_even_denominator(value, accepted):
    build = lambda: term(FinancialTerm.REFERRAL_FEE_RATE, fv(value, RATIO_UNIT))
    if accepted:
        assert build().amount.value == value
    else:
        with pytest.raises(ValueError):
            build()


def test_out_of_range_rate_stays_representable_as_invalid_evidence():
    rejected = term(FinancialTerm.REFERRAL_FEE_RATE, fv(Decimal("1.2"), status=VerificationStatus.INVALID))
    assert not rejected.has_usable_amount and rejected.amount.raw_value == Decimal("1.2")


def test_referral_amount_and_rate_are_independent_evidences():
    amount = term(FinancialTerm.REFERRAL_FEE, fv(Decimal("6.30"), "USD"))
    rate = term(FinancialTerm.REFERRAL_FEE_RATE, fv(Decimal("0.15"), RATIO_UNIT))
    bound = evidence_set((amount, rate))
    assert bound.evidence_for(FinancialTerm.REFERRAL_FEE).depends_on == ()
    derived = replace(amount, depends_on=(
        FinancialDependency("term:REFERRAL_FEE_RATE", "rate applied to the declared price basis",
                            FinancialTerm.REFERRAL_FEE_RATE),
        FinancialDependency("price:observation-1", "price the declared rate was applied to"),
    ))
    assert evidence_set((derived, rate)).evidence_for(FinancialTerm.REFERRAL_FEE).depends_on[0].term \
        is FinancialTerm.REFERRAL_FEE_RATE


# -- Value types ----------------------------------------------------------

@pytest.mark.parametrize("value", [True, False, 4, 4.5, "4.50", Decimal("NaN"), Decimal("Infinity")])
def test_usable_amount_requires_a_finite_decimal_and_rejects_bool(value):
    with pytest.raises(ValueError, match="finite Decimal"):
        term(FinancialTerm.COG, fv(value, "USD"))


def test_usable_monetary_amount_rejects_a_negative_value():
    with pytest.raises(ValueError, match="must not be negative"):
        term(FinancialTerm.COG, fv(Decimal("-0.01"), "USD"))


def test_applicability_requires_a_boolean_assertion():
    with pytest.raises(ValueError, match="boolean value"):
        Applicability(applies=fv("yes"), justification="synthetic")
    with pytest.raises(ValueError):
        Applicability(applies=fv(True), justification="   ")


# -- Zero, exclusion, structural absence, NOT_FOUND, INVALID --------------

def test_the_five_states_of_a_term_stay_distinct():
    accredited_zero = term(FinancialTerm.VAT, fv(Decimal("0"), "USD"))
    excluded = term(FinancialTerm.VAT, None, applicability=applies(False))
    absent = term(FinancialTerm.VAT, None)
    not_found = term(FinancialTerm.VAT, fv(None, status=VerificationStatus.NOT_FOUND))
    invalid = term(FinancialTerm.VAT, fv("n/a", status=VerificationStatus.INVALID))

    assert accredited_zero.has_usable_amount and accredited_zero.amount.value == Decimal("0")
    assert not accredited_zero.applicability.excludes

    assert excluded.applicability.excludes and excluded.amount is None
    assert absent.amount is None and not absent.applicability.excludes and absent.applicability.is_resolved
    assert not not_found.applicability.excludes and not_found.amount.status is VerificationStatus.NOT_FOUND
    assert invalid.amount.status is VerificationStatus.INVALID and not invalid.has_usable_amount
    assert not any(e.has_usable_amount for e in (excluded, absent, not_found, invalid))


def test_an_accredited_exclusion_carries_no_monetary_observation():
    with pytest.raises(ValueError, match="carries no monetary observation"):
        term(FinancialTerm.VAT, fv(Decimal("0"), "USD"), applicability=applies(False))
    with pytest.raises(ValueError, match="carries no monetary observation"):
        term(FinancialTerm.VAT, fv(None, status=VerificationStatus.NOT_FOUND), applicability=applies(False))


def test_an_inferred_exclusion_keeps_its_inferred_status():
    excluded = term(FinancialTerm.STORAGE, None,
                    applicability=applies(False, VerificationStatus.INFERRED))
    assert excluded.applicability.excludes and excluded.applicability.applies.status is VerificationStatus.INFERRED
    assert excluded.applicability.justification


@pytest.mark.parametrize("status", [VerificationStatus.NOT_FOUND, VerificationStatus.INVALID])
def test_unresolved_applicability_is_neither_exclusion_nor_inclusion(status):
    evidence = term(FinancialTerm.COG, applicability=Applicability(
        applies=fv("unknown", status=status), justification="applicability not yet evaluated"))
    assert not evidence.applicability.excludes and not evidence.applicability.is_resolved
    assert FinancialTerm.COG in evidence_set((evidence,)).unresolved_required_terms


def test_structural_absence_of_a_required_term_does_not_exclude_it():
    bound = evidence_set((term(FinancialTerm.COG),))
    assert bound.evidence_for(FinancialTerm.REFERRAL_FEE) is None
    assert bound.unresolved_required_terms == (FinancialTerm.REFERRAL_FEE,)
    resolved = evidence_set((term(FinancialTerm.COG),
                             term(FinancialTerm.REFERRAL_FEE, None, applicability=applies(False))))
    assert resolved.unresolved_required_terms == ()


# -- Allocation and double counting ---------------------------------------

@pytest.mark.parametrize("kind", sorted(
    {FinancialTerm.STORAGE, FinancialTerm.INBOUND_SHIPPING,
     FinancialTerm.SHIPPING_PER_UNIT, FinancialTerm.INBOUND_PLACEMENT}, key=lambda t: t.value))
def test_allocated_terms_require_an_explicit_allocation_method(kind):
    assert kind.requires_allocation_method
    with pytest.raises(ValueError, match="allocation_method"):
        term(kind, fv(Decimal("1.20"), "USD"))
    allocated = term(kind, fv(Decimal("1.20"), "USD"),
                     allocation_method="shipment amount divided by declared units received")
    assert allocated.allocation_method
    # An absent or unusable amount asserts no allocation at all.
    assert term(kind, None).allocation_method is None


def test_a_pack_sourced_amount_can_declare_its_allocation_to_one_sellable_unit():
    """ADR-047 §10: a per-pack amount is not automatically a per-sellable-unit amount."""
    per_pack = term(FinancialTerm.COG, fv(Decimal("1.50"), "USD"),
                    allocation_method="supplier pack price divided by declared units per pack",
                    depends_on=(FinancialDependency("supplier-file:units_per_pack",
                                                    "declared pack size used to allocate"),))
    assert per_pack.allocation_method and per_pack.depends_on[0].term is None
    assert evidence_set((per_pack,)).evidence_for(FinancialTerm.COG).has_usable_amount


def test_effective_context_does_not_impose_an_order_against_acquisition_time():
    """An announced amount may be acquired before or after it takes effect (§8)."""
    announced = replace(CONTEXT, effective_at=NOW + timedelta(days=30))
    for context in (CONTEXT, announced):
        evidence = term(FinancialTerm.REFERRAL_FEE, fv(Decimal("6.30"), "USD"), context=context)
        assert evidence.context.effective_at != evidence.amount.provenance.retrieved_at


def test_non_allocated_terms_do_not_require_an_allocation_method():
    assert not FinancialTerm.COG.requires_allocation_method
    assert term(FinancialTerm.COG).allocation_method is None
    with pytest.raises(ValueError):
        term(FinancialTerm.COG, allocation_method="  ")


def test_context_basis_definition_is_mandatory_and_explicit():
    with pytest.raises(ValueError, match="basis_definition"):
        EffectiveContext(effective_at=EFFECTIVE, basis_definition="")


# -- Effective time vs acquisition time -----------------------------------

def test_effective_time_is_kept_separate_from_acquisition_time():
    evidence = term(FinancialTerm.COG, fv(Decimal("4.50"), "USD", retrieved_at=NOW))
    assert evidence.context.effective_at == EFFECTIVE
    assert evidence.amount.provenance.retrieved_at == NOW
    assert evidence.context.effective_at != evidence.amount.provenance.retrieved_at


@pytest.mark.parametrize("field,value", [
    ("effective_at", EFFECTIVE.replace(tzinfo=None)),
    ("effective_until", EFFECTIVE.replace(tzinfo=None)),
    ("effective_until", EFFECTIVE),
    ("effective_until", EFFECTIVE - timedelta(days=1)),
])
def test_effective_context_rejects_naive_or_nonpositive_intervals(field, value):
    with pytest.raises(ValueError):
        replace(CONTEXT, **{field: value})


def test_effective_window_is_accepted_when_it_has_positive_duration():
    windowed = replace(CONTEXT, effective_until=EFFECTIVE + timedelta(days=30))
    assert windowed.effective_until > windowed.effective_at


# -- Dependencies ---------------------------------------------------------

def test_dependencies_must_be_explicit_resolvable_and_non_circular():
    with pytest.raises(ValueError, match="cannot depend on itself"):
        term(FinancialTerm.COG, depends_on=(FinancialDependency("x", "role", FinancialTerm.COG),))
    with pytest.raises(ValueError, match="must not repeat"):
        term(FinancialTerm.COG, depends_on=(FinancialDependency("x", "role"),
                                            FinancialDependency("x", "role")))
    with pytest.raises(ValueError):
        term(FinancialTerm.COG, depends_on=[FinancialDependency("x", "role")])
    with pytest.raises(ValueError):
        FinancialDependency("", "role")
    with pytest.raises(ValueError):
        FinancialDependency("x", "role", term="REFERRAL_FEE")


def test_a_term_dependency_must_be_represented_in_the_same_evidence_set():
    weight_dependent = term(FinancialTerm.SHIPPING_PER_POUND, fv(Decimal("0.55"), "USD/lb"),
                            depends_on=(FinancialDependency("product:weight_lb",
                                                            "effective weight the rate is applied to"),))
    assert evidence_set((weight_dependent,)).terms
    dangling = term(FinancialTerm.REFERRAL_FEE, depends_on=(
        FinancialDependency("term:REFERRAL_FEE_RATE", "rate used",
                            FinancialTerm.REFERRAL_FEE_RATE),))
    with pytest.raises(ValueError, match="not represented in this evidence set"):
        evidence_set((dangling,))


# -- Scenario identity ----------------------------------------------------

def test_scenario_identifies_version_currency_unit_and_policy():
    declared = scenario()
    assert (declared.scenario_id, declared.scenario_version, declared.currency) == (
        "synthetic-scenario", "v1", "USD")
    assert declared.policy_identity and declared.sellable_unit_definition
    assert FinancialTerm.COG in declared.required_terms


@pytest.mark.parametrize("overrides", [
    {"scenario_id": ""}, {"scenario_version": " "}, {"currency": "usd"}, {"currency": "US"},
    {"sellable_unit_definition": ""}, {"policy_identity": ""},
    {"required_terms": frozenset()}, {"required_terms": {FinancialTerm.COG}},
    {"required_terms": frozenset({"COG"})},
    {"context_requirements": ("a", "a")}, {"context_requirements": ("",)},
    {"context_requirements": ["a"]},
])
def test_scenario_rejects_incomplete_or_mutable_identity(overrides):
    with pytest.raises(ValueError):
        scenario(**overrides)


def test_evidence_set_binds_scenario_run_and_record():
    bound = evidence_set((term(FinancialTerm.COG),))
    assert (bound.execution_id, bound.record_reference) == ("run-0001", "record-0001")
    assert bound.scenario.scenario_version == "v1"
    for overrides in ({"execution_id": ""}, {"record_reference": " "}, {"scenario": "synthetic"},
                      {"terms": [term(FinancialTerm.COG)]}, {"terms": ("COG",)}):
        with pytest.raises(ValueError):
            evidence_set(**overrides)


def test_evidence_set_rejects_a_duplicated_term():
    with pytest.raises(ValueError, match="must not appear twice"):
        evidence_set((term(FinancialTerm.COG), term(FinancialTerm.COG, None)))


def test_unresolved_required_terms_is_deterministic_and_reports_only_required_terms():
    bound = evidence_set(
        (term(FinancialTerm.PREP),),
        scenario=scenario(required_terms=frozenset(
            {FinancialTerm.REFERRAL_FEE, FinancialTerm.COG, FinancialTerm.VAT})))
    assert bound.unresolved_required_terms == (
        FinancialTerm.COG, FinancialTerm.REFERRAL_FEE, FinancialTerm.VAT)
    assert bound.evidence_for(FinancialTerm.PREP) is not None


# -- Immutability and scope guards ----------------------------------------

@pytest.mark.parametrize("instance,field", [
    (CONTEXT, "effective_at"), (applies(), "justification"), (term(), "amount"),
    (FinancialDependency("x", "role"), "reference"), (scenario(), "currency"),
    (evidence_set((term(),)), "execution_id"),
])
def test_contracts_are_frozen(instance, field):
    with pytest.raises(FrozenInstanceError):
        setattr(instance, field, "mutated")


def test_contracts_neither_calculate_nor_accredit_legacy_numeric_inputs():
    module = sys.modules["juval.domain.financial_evidence"]
    assert not {"CostInputs", "FeeInputs", "ProfitabilityResult"} & set(vars(module))
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    # Evidence contracts stay upstream of the legacy numeric operands and of
    # every calculating/IO layer: no projection or accreditation can hide here.
    assert imported == {"dataclasses", "datetime", "decimal", "enum", "provenance", "units",
                        "__future__"}
