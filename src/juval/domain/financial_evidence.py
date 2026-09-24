"""Financial evidence contracts (ADR-047).

Additive domain contracts that make a financial term's *applicability* and its
*value* two separately accredited facts, each carrying its own FieldValue /
Provenance / VerificationStatus (ADR-003, ADR-004, ADR-047 §6).

These objects validate declarations, not their truth, coverage or commercial
sufficiency. Deliberately absent at this stage (ADR-047 §4, §22 steps 3-9):
arithmetic, currency conversion, projection to or from CostInputs/FeeInputs,
importer capture, persistence, API and pipeline integration. Nothing here
accredits legacy data: there is no constructor that turns a bare Decimal or a
legacy record into evidence, and no import of the numeric cost/fee contracts.

Distinctions preserved end to end (ADR-047 §12, §13, §14):

  * amount is None          -> structural absence: no evidence is represented
                               at that location; not zero, not an exclusion,
                               not an attempted lookup.
  * amount NOT_FOUND        -> an authentic attempt produced no usable value.
  * amount INVALID          -> a raw source value failed validation; raw_value
                               is preserved and never exposed as an operand.
  * amount VERIFIED/INFERRED with 0 -> an accredited zero.
  * applies usable and False -> an accredited exclusion, which carries no
                               monetary observation at all.

Legacy compatibility (ADR-047 §20, §22 step 2) is a *gap assessment* only:
assess_legacy_financial_operands reports why legacy operands do not satisfy
this contract and never produces FieldValue, FinancialTermEvidence, a
FinancialEvidenceSet or a price observation from them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .provenance import FieldValue, SourceType, VerificationStatus
from .units import CANONICAL_WEIGHT_UNIT

#: Unit of a dimensionless ratio. A ratio never carries a currency and is never
#: expressed as a percentage (ADR-047 §10, §11).
RATIO_UNIT = "ratio"

#: Exclusive upper bound of a referral rate, consistent with the existing
#: FeeInputs contract and with the break-even denominator (1 - r) of
#: processing/profitability.py. This is a domain-validity bound, not a new
#: commercial policy: an out-of-range source value stays representable as
#: INVALID evidence preserving its raw_value.
MAX_EXCLUSIVE_RATE = Decimal("1")


def _instant(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} requires an effective timezone offset")
    return value.astimezone(timezone.utc)


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be explicit nonempty text")


def _currency(value: str, name: str) -> None:
    if (not isinstance(value, str) or len(value) != 3 or not value.isascii()
            or not value.isalpha() or not value.isupper()):
        raise ValueError(f"{name} requires three uppercase ASCII letters")


class TermNature(str, Enum):
    """Economic nature of a term: what its number means and how it is denominated.

    Separating these natures is what keeps arithmetic between incompatible
    magnitudes out of reach (ADR-047 §10).
    """

    MONETARY_PER_SELLABLE_UNIT = "MONETARY_PER_SELLABLE_UNIT"
    MONETARY_PER_POUND = "MONETARY_PER_POUND"
    DIMENSIONLESS_RATIO = "DIMENSIONLESS_RATIO"


class FinancialTerm(str, Enum):
    """The existing financial terms of ADR-047 §9.

    Membership does not assert that a term applies to any given scenario, and
    the list is not extended with new charges.
    """

    COG = "COG"
    VAT = "VAT"
    INBOUND_SHIPPING = "INBOUND_SHIPPING"
    SHIPPING_PER_UNIT = "SHIPPING_PER_UNIT"
    SHIPPING_PER_POUND = "SHIPPING_PER_POUND"
    PREP = "PREP"
    LABELING = "LABELING"
    FRAGILE_PREP = "FRAGILE_PREP"
    STORAGE = "STORAGE"
    INBOUND_PLACEMENT = "INBOUND_PLACEMENT"
    TAXES = "TAXES"
    OTHER_COSTS = "OTHER_COSTS"
    REFERRAL_FEE = "REFERRAL_FEE"
    FULFILLMENT_FEE = "FULFILLMENT_FEE"
    OTHER_SELLING_FEES = "OTHER_SELLING_FEES"
    REFERRAL_FEE_RATE = "REFERRAL_FEE_RATE"

    @property
    def nature(self) -> TermNature:
        return _TERM_NATURES[self]

    @property
    def requires_allocation_method(self) -> bool:
        """True for the terms ADR-047 §9 describes as *allocated* per unit.

        Their name alone accredits neither the period nor the split that
        produced a per-unit amount, so a usable amount must declare its method.
        """
        return self in _ALLOCATED_TERMS


_TERM_NATURES: dict[FinancialTerm, TermNature] = {
    FinancialTerm.SHIPPING_PER_POUND: TermNature.MONETARY_PER_POUND,
    FinancialTerm.REFERRAL_FEE_RATE: TermNature.DIMENSIONLESS_RATIO,
    **{
        term: TermNature.MONETARY_PER_SELLABLE_UNIT
        for term in FinancialTerm
        if term not in (FinancialTerm.SHIPPING_PER_POUND, FinancialTerm.REFERRAL_FEE_RATE)
    },
}

_ALLOCATED_TERMS = frozenset({
    FinancialTerm.INBOUND_SHIPPING,
    FinancialTerm.SHIPPING_PER_UNIT,
    FinancialTerm.INBOUND_PLACEMENT,
    FinancialTerm.STORAGE,
})


def _declared_currency(unit: str, nature: TermNature) -> str:
    """Currency a monetary unit is denominated in; raises if the unit is malformed."""
    if not isinstance(unit, str) or not unit:
        raise ValueError("A usable monetary amount requires an explicit currency unit")
    if nature is TermNature.MONETARY_PER_POUND:
        suffix = f"/{CANONICAL_WEIGHT_UNIT}"
        if not unit.endswith(suffix):
            raise ValueError(f"A per-weight rate requires a '<CURRENCY>{suffix}' unit, got {unit!r}")
        unit = unit[: -len(suffix)]
    _currency(unit, "Monetary unit")
    return unit


def _reject_ai_source(value: FieldValue, name: str) -> None:
    # Financial amounts and applicability are sensitive fields: AI may explain
    # them, never produce them (ADR-006, ADR-008).
    if value.provenance.source_type is SourceType.AI_ANALYSIS:
        raise ValueError(f"{name} must never come from AI_ANALYSIS")


def _validate_amount(term: FinancialTerm, amount: FieldValue) -> None:
    if not isinstance(amount, FieldValue) or not isinstance(amount.status, VerificationStatus):
        raise ValueError("A financial amount requires a FieldValue with an explicit verification status")
    _reject_ai_source(amount, f"{term.value} amount")
    if not amount.is_usable:
        # NOT_FOUND/INVALID keep their cause and raw diagnostics, and never a
        # usable operand, a substituted zero or a fabricated unit.
        if amount.value is not None:
            raise ValueError("NOT_FOUND/INVALID financial evidence must not carry a usable value")
        return
    value = amount.value
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError("A usable financial amount requires a finite Decimal")
    if term.nature is TermNature.DIMENSIONLESS_RATIO:
        if amount.unit != RATIO_UNIT:
            raise ValueError(
                f"{term.value} is a dimensionless ratio and requires unit {RATIO_UNIT!r}, "
                "never a currency or a percentage"
            )
        if not (Decimal("0") <= value < MAX_EXCLUSIVE_RATE):
            raise ValueError(
                f"A usable {term.value} must be a ratio within [0, {MAX_EXCLUSIVE_RATE}), got {value}"
            )
        return
    _declared_currency(amount.unit, term.nature)
    if value < Decimal("0"):
        raise ValueError(f"A usable {term.value} amount must not be negative, got {value}")


@dataclass(frozen=True)
class EffectiveContext:
    """When and on what basis a term's evidence is effective.

    effective_at is the *effective* instant, kept separate from the acquisition
    instant carried by Provenance.retrieved_at: retrieved_at never substitutes
    for an unknown effective context (ADR-047 §8). Declaring a time does not by
    itself accredit currency or sufficiency.

    Deliberately, no ordering is imposed between effective_at and retrieved_at.
    Unlike a market observation (ADR-046), a financial term can legitimately be
    acquired before it takes effect — an announced schedule — or long after.
    Whether an effective context is current enough is a per-scenario requirement
    to be resolved, not an invariant of this contract.
    """

    effective_at: datetime
    basis_definition: str
    effective_until: datetime | None = None

    def __post_init__(self) -> None:
        start = _instant(self.effective_at, "effective_at")
        # Names what the amount covers, so a concept already included in another
        # amount stays visible instead of being double counted (ADR-047 §8).
        _text(self.basis_definition, "basis_definition")
        if self.effective_until is not None and _instant(self.effective_until, "effective_until") <= start:
            raise ValueError("effective_until must follow effective_at")


@dataclass(frozen=True)
class Applicability:
    """Whether a term applies, as evidence in its own right (ADR-047 §12).

    An unusable assertion leaves applicability *unresolved*; it is not an
    exclusion, and it blocks any result that needs it resolved.
    """

    applies: FieldValue[bool]
    justification: str

    def __post_init__(self) -> None:
        if not isinstance(self.applies, FieldValue) or not isinstance(self.applies.status, VerificationStatus):
            raise ValueError("Applicability requires a FieldValue with an explicit verification status")
        if self.applies.is_usable:
            if type(self.applies.value) is not bool:
                raise ValueError("A usable applicability assertion requires a boolean value")
        elif self.applies.value is not None:
            raise ValueError("An unresolved applicability assertion must not carry a usable value")
        _reject_ai_source(self.applies, "Applicability")
        _text(self.justification, "justification")

    @property
    def is_resolved(self) -> bool:
        return self.applies.is_usable

    @property
    def excludes(self) -> bool:
        """True only for an accredited exclusion, never for an unresolved assertion."""
        return self.applies.is_usable and self.applies.value is False


@dataclass(frozen=True)
class FinancialDependency:
    """Resolvable link to evidence a term actually depended on (ADR-047 §15, §18).

    `term` is set when the dependency is another term of the same scenario, so
    the link can be resolved instead of being asserted in free text.
    """

    reference: str
    role: str
    term: FinancialTerm | None = None

    def __post_init__(self) -> None:
        _text(self.reference, "reference")
        _text(self.role, "role")
        if self.term is not None and not isinstance(self.term, FinancialTerm):
            raise ValueError("A term dependency must reference a FinancialTerm")


@dataclass(frozen=True)
class FinancialTermEvidence:
    """Applicability and (optionally) value of one financial term.

    amount=None is structural absence, not an exclusion and not a failed
    lookup. An accredited exclusion carries no amount at all, because an
    exclusion is not a monetary observation of zero (ADR-047 §12, §13).
    """

    term: FinancialTerm
    applicability: Applicability
    context: EffectiveContext
    amount: FieldValue[Decimal] | None = None
    allocation_method: str | None = None
    depends_on: tuple[FinancialDependency, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.term, FinancialTerm):
            raise ValueError("Explicit FinancialTerm required")
        if not isinstance(self.applicability, Applicability):
            raise ValueError("Explicit Applicability required")
        if not isinstance(self.context, EffectiveContext):
            raise ValueError("Explicit EffectiveContext required")
        if self.amount is not None:
            _validate_amount(self.term, self.amount)
        if self.applicability.excludes and self.amount is not None:
            raise ValueError(
                f"An accredited exclusion of {self.term.value} carries no monetary observation"
            )
        if self.allocation_method is not None:
            _text(self.allocation_method, "allocation_method")
        elif self.term.requires_allocation_method and self.has_usable_amount:
            raise ValueError(
                f"A usable {self.term.value} amount is allocated per sellable unit and must "
                "declare its allocation_method"
            )
        if not isinstance(self.depends_on, tuple):
            raise ValueError("depends_on must be an immutable tuple")
        if (self.has_usable_amount and self.amount.provenance.source_type is SourceType.CALCULATED
                and not self.depends_on):
            # A derived amount keeps resolvable links to what it was derived
            # from (ADR-047 §15, §18); a method string alone is not enough.
            raise ValueError(f"A derived {self.term.value} amount must declare what it depends on")
        seen: set[tuple[str, str, FinancialTerm | None]] = set()
        for dependency in self.depends_on:
            if not isinstance(dependency, FinancialDependency):
                raise ValueError("depends_on elements must be FinancialDependency")
            if dependency.term == self.term:
                raise ValueError(f"{self.term.value} cannot depend on itself")
            key = (dependency.reference, dependency.role, dependency.term)
            if key in seen:
                raise ValueError("depends_on must not repeat the same dependency")
            seen.add(key)

    @property
    def has_usable_amount(self) -> bool:
        return self.amount is not None and self.amount.is_usable


@dataclass(frozen=True)
class DeclaredSellingPrice:
    """A selling price explicitly declared for one record, with its currency.

    Deliberately not an ADR-046 PriceObservation: a supplier-declared price is
    not a market observation and gains no observation context from its name.
    Its currency lives in amount.unit and is never taken from the scenario,
    the marketplace, a price symbol or the legacy selling price (ADR-047 §11).
    """

    amount: FieldValue[Decimal]
    context: EffectiveContext

    def __post_init__(self) -> None:
        if not isinstance(self.amount, FieldValue) or not isinstance(self.amount.status, VerificationStatus):
            raise ValueError("A declared price requires a FieldValue with an explicit verification status")
        _reject_ai_source(self.amount, "A declared price")
        if not isinstance(self.context, EffectiveContext):
            raise ValueError("Explicit EffectiveContext required")
        if not self.amount.is_usable:
            if self.amount.value is not None:
                raise ValueError("NOT_FOUND/INVALID price evidence must not carry a usable value")
            return
        value = self.amount.value
        if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
            raise ValueError("A usable declared price must be a finite, non-negative Decimal")
        _currency(self.amount.unit, "Declared price currency")


@dataclass(frozen=True)
class FinancialScenario:
    """Identity and versioned frame a financial evaluation is computed in (ADR-047 §8).

    The term universe is declared, never deduced from the terms that happen to
    be present: a required concept with no representation stays unresolved
    instead of silently dropping out of the scenario.
    """

    scenario_id: str
    scenario_version: str
    currency: str
    sellable_unit_definition: str
    policy_identity: str
    required_terms: frozenset[FinancialTerm]
    context_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.scenario_id, "scenario_id")
        _text(self.scenario_version, "scenario_version")
        _currency(self.currency, "currency")
        _text(self.sellable_unit_definition, "sellable_unit_definition")
        # Identity of the formula/policy needed to reproduce the evaluation;
        # recording it accredits no commercial approval (ADR-047 §10).
        _text(self.policy_identity, "policy_identity")
        if not isinstance(self.required_terms, frozenset) or not self.required_terms:
            raise ValueError("required_terms must be a nonempty frozenset of FinancialTerm")
        if any(not isinstance(term, FinancialTerm) for term in self.required_terms):
            raise ValueError("required_terms elements must be FinancialTerm")
        if not isinstance(self.context_requirements, tuple):
            raise ValueError("context_requirements must be an immutable tuple")
        for requirement in self.context_requirements:
            _text(requirement, "context requirement")
        if len(set(self.context_requirements)) != len(self.context_requirements):
            raise ValueError("context_requirements must not repeat a requirement")


@dataclass(frozen=True)
class FinancialEvidenceSet:
    """Scenario-bound financial evidence for one evaluated record within one run.

    Binding is what makes the currency link unambiguous: every usable monetary
    amount is denominated in the scenario currency, and mixed-currency evidence
    is rejected rather than normalized implicitly (ADR-047 §11).
    """

    scenario: FinancialScenario
    execution_id: str
    record_reference: str
    terms: tuple[FinancialTermEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, FinancialScenario):
            raise ValueError("Explicit FinancialScenario required")
        _text(self.execution_id, "execution_id")
        _text(self.record_reference, "record_reference")
        if not isinstance(self.terms, tuple):
            raise ValueError("terms must be an immutable tuple")
        present: dict[FinancialTerm, FinancialTermEvidence] = {}
        for evidence in self.terms:
            if not isinstance(evidence, FinancialTermEvidence):
                raise ValueError("terms elements must be FinancialTermEvidence")
            if evidence.term in present:
                raise ValueError(f"{evidence.term.value} must not appear twice in one evidence set")
            present[evidence.term] = evidence
            if evidence.has_usable_amount and evidence.term.nature is not TermNature.DIMENSIONLESS_RATIO:
                declared = _declared_currency(evidence.amount.unit, evidence.term.nature)
                if declared != self.scenario.currency:
                    raise ValueError(
                        f"{evidence.term.value} is denominated in {declared}, "
                        f"incompatible with scenario currency {self.scenario.currency}"
                    )
        for evidence in self.terms:
            for dependency in evidence.depends_on:
                if dependency.term is not None and dependency.term not in present:
                    raise ValueError(
                        f"{evidence.term.value} depends on {dependency.term.value}, "
                        "which is not represented in this evidence set"
                    )

    def evidence_for(self, term: FinancialTerm) -> FinancialTermEvidence | None:
        """Evidence declared for `term`, or None when it is structurally absent."""
        for evidence in self.terms:
            if evidence.term == term:
                return evidence
        return None

    @property
    def unresolved_required_terms(self) -> tuple[FinancialTerm, ...]:
        """Required terms whose applicability this set does not resolve.

        Covers both structural absence and an unusable applicability assertion:
        neither excludes the term (ADR-047 §8, §12), so any result depending on
        one of these stays blocked until it is resolved. Reporting a gap is not
        resolving it — this performs no calculation and no status combination.
        """
        return tuple(
            term
            for term in sorted(self.scenario.required_terms, key=lambda item: item.value)
            if (evidence := self.evidence_for(term)) is None or not evidence.applicability.is_resolved
        )


class LegacyGap(str, Enum):
    """Why a legacy financial location does not satisfy this contract (ADR-047 §5, §20).

    A diagnostic of the legacy representation, never a VerificationStatus:
    it neither replaces nor accompanies a status on any value.
    """

    #: No legacy representation at that location. Not NOT_FOUND (no lookup is
    #: accredited), not zero and not an exclusion (§13, §14).
    STRUCTURALLY_ABSENT = "STRUCTURALLY_ABSENT"
    #: A bare Decimal: no source, status, retrieval time or method (§5).
    NO_PROVENANCE = "NO_PROVENANCE"
    #: A bare legacy zero cannot be told apart from the numeric contract's
    #: Decimal("0") default, so it is not an accredited zero (§13).
    ZERO_INDISTINGUISHABLE_FROM_DEFAULT = "ZERO_INDISTINGUISHABLE_FROM_DEFAULT"
    #: A number does not assert that the term applies to the record (§12).
    APPLICABILITY_UNRESOLVED = "APPLICABILITY_UNRESOLVED"
    #: A legacy amount is bound to no scenario currency; none is inferred (§11).
    #: Never reported for the dimensionless referral rate.
    CURRENCY_UNBOUND = "CURRENCY_UNBOUND"
    #: No effective time or basis; retrieved_at does not substitute for it (§8).
    EFFECTIVE_CONTEXT_UNDECLARED = "EFFECTIVE_CONTEXT_UNDECLARED"
    #: An allocated term carries no allocation method (§10). Reported only for
    #: terms that require one: COG is never assumed to come from a pack.
    ALLOCATION_UNDECLARED = "ALLOCATION_UNDECLARED"


@dataclass(frozen=True)
class LegacyTermGap:
    """Gap report for one term's legacy location; holds no value and no evidence."""

    term: FinancialTerm
    represented: bool
    gaps: tuple[LegacyGap, ...]

    @property
    def satisfies_contract(self) -> bool:
        return not self.gaps


@dataclass(frozen=True)
class LegacyFinancialCompatibility:
    """Deterministic compatibility report over all FinancialTerm locations.

    This is an assessment of what legacy operands *lack*, not financial
    evidence: nothing here can be bound to a FinancialEvidenceSet, projected
    to an operand, persisted as a backfill or read as accreditation.
    """

    terms: tuple[LegacyTermGap, ...]

    @property
    def satisfies_contract(self) -> bool:
        return all(entry.satisfies_contract for entry in self.terms)

    def gap_for(self, term: FinancialTerm) -> LegacyTermGap:
        return next(entry for entry in self.terms if entry.term == term)


def assess_legacy_financial_operands(
    operands: Mapping[FinancialTerm, Decimal | FieldValue | None],
) -> LegacyFinancialCompatibility:
    """Report why legacy financial operands do not satisfy ADR-047 (§20).

    `operands` maps a term to what its legacy location holds: a bare Decimal
    (CostInputs/FeeInputs), an already provenanced FieldValue, or None. Terms
    missing from the mapping are structurally absent. A FieldValue keeps its
    own status untouched and is not promoted: even a source-VERIFIED value
    lacks applicability, scenario currency and effective context, and a
    supplier's VERIFIED is never read as independent Amazon verification.
    The input is only read; nothing is inferred, defaulted or backfilled.
    """
    if not isinstance(operands, Mapping):
        raise ValueError("Legacy operands must be a mapping keyed by FinancialTerm")
    for key, value in operands.items():
        if not isinstance(key, FinancialTerm):
            raise ValueError("Legacy operands must be keyed by FinancialTerm")
        if value is not None and not isinstance(value, (Decimal, FieldValue)):
            raise ValueError(
                f"Legacy {key.value} must be a Decimal, a FieldValue or None, got {type(value).__name__}"
            )
    entries = []
    for term in sorted(FinancialTerm, key=lambda item: item.value):
        value = operands.get(term)
        if value is None:
            entries.append(LegacyTermGap(term, False, (LegacyGap.STRUCTURALLY_ABSENT,)))
            continue
        gaps = []
        if isinstance(value, Decimal):
            gaps.append(LegacyGap.NO_PROVENANCE)
            if value == 0:
                gaps.append(LegacyGap.ZERO_INDISTINGUISHABLE_FROM_DEFAULT)
        gaps.append(LegacyGap.APPLICABILITY_UNRESOLVED)
        if term.nature is not TermNature.DIMENSIONLESS_RATIO:
            gaps.append(LegacyGap.CURRENCY_UNBOUND)
        gaps.append(LegacyGap.EFFECTIVE_CONTEXT_UNDECLARED)
        if term.requires_allocation_method:
            gaps.append(LegacyGap.ALLOCATION_UNDECLARED)
        entries.append(LegacyTermGap(term, True, tuple(gaps)))
    return LegacyFinancialCompatibility(tuple(entries))
