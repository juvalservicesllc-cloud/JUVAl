"""Accredited fee evidence per record (ADR-047 §12, §15, §22 step 4).

Builds, for one FinancialEvidenceSet, the fee view ADR-047 requires: each
fee term's own evidence classified by what it is, never completed from a
batch-wide FeeInputs, a legacy default or another fee. It computes nothing.

Referral fee and referral fee rate stay independent: ADR-047 §15 approves no
method to derive one from the other, so no derivation exists here. A derived
fee (SourceType.CALCULATED) can only enter through FinancialTermEvidence,
which requires it to declare its dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .financial_evidence import FinancialEvidenceSet, FinancialTerm, FinancialTermEvidence
from .provenance import SourceType, VerificationStatus

#: The fee terms of ADR-047 §9: three monetary fees and the referral ratio.
FEE_TERMS: tuple[FinancialTerm, ...] = (
    FinancialTerm.REFERRAL_FEE,
    FinancialTerm.FULFILLMENT_FEE,
    FinancialTerm.OTHER_SELLING_FEES,
    FinancialTerm.REFERRAL_FEE_RATE,
)

_OBSERVED_SOURCES = frozenset({SourceType.OFFICIAL_API, SourceType.AUTHORIZED_EXTERNAL_SOURCE})
_DECLARED_SOURCES = frozenset({SourceType.SUPPLIER_FILE, SourceType.USER_INPUT})


class FeeEvidenceState(str, Enum):
    """What one fee's evidence is. A classification, not a VerificationStatus."""

    STRUCTURALLY_ABSENT = "STRUCTURALLY_ABSENT"      # no evidence represented for the term
    APPLICABILITY_UNRESOLVED = "APPLICABILITY_UNRESOLVED"
    EXCLUDED = "EXCLUDED"                            # accredited exclusion; never a zero amount
    AMOUNT_ABSENT = "AMOUNT_ABSENT"                  # applies, but no amount represented
    NOT_FOUND = "NOT_FOUND"
    INVALID = "INVALID"
    OBSERVED = "OBSERVED"                            # VERIFIED from an authorized API/source
    DECLARED = "DECLARED"                            # VERIFIED as declared by a supplier file/user
    INFERRED = "INFERRED"                            # usable INFERRED, kept INFERRED
    DERIVED = "DERIVED"                              # VERIFIED CALCULATED with declared dependencies


USABLE_FEE_STATES = frozenset({
    FeeEvidenceState.OBSERVED, FeeEvidenceState.DECLARED, FeeEvidenceState.INFERRED,
    FeeEvidenceState.DERIVED,
})


@dataclass(frozen=True)
class FeeEvidence:
    """One fee term of one record; `evidence` is the untouched domain object."""

    term: FinancialTerm
    state: FeeEvidenceState
    evidence: Optional[FinancialTermEvidence]

    @property
    def usable(self) -> bool:
        return self.state in USABLE_FEE_STATES


def accredited_fee_evidence(evidence_set: FinancialEvidenceSet) -> tuple[FeeEvidence, ...]:
    """Classify each fee term of one record's evidence set, in FEE_TERMS order."""
    if not isinstance(evidence_set, FinancialEvidenceSet):
        raise ValueError("Explicit FinancialEvidenceSet required")
    return tuple(_classify(term, evidence_set.evidence_for(term)) for term in FEE_TERMS)


def _classify(term: FinancialTerm, item: Optional[FinancialTermEvidence]) -> FeeEvidence:
    if item is None:
        state = FeeEvidenceState.STRUCTURALLY_ABSENT
    elif not item.applicability.is_resolved:
        state = FeeEvidenceState.APPLICABILITY_UNRESOLVED
    elif item.applicability.excludes:
        state = FeeEvidenceState.EXCLUDED
    elif item.amount is None:
        state = FeeEvidenceState.AMOUNT_ABSENT
    elif item.amount.status is VerificationStatus.NOT_FOUND:
        state = FeeEvidenceState.NOT_FOUND
    elif item.amount.status is VerificationStatus.INVALID:
        state = FeeEvidenceState.INVALID
    elif item.amount.status is VerificationStatus.INFERRED:
        state = FeeEvidenceState.INFERRED
    else:
        source = item.amount.provenance.source_type
        if source is SourceType.CALCULATED:
            state = FeeEvidenceState.DERIVED
        elif source in _OBSERVED_SOURCES:
            state = FeeEvidenceState.OBSERVED
        elif source in _DECLARED_SOURCES:
            state = FeeEvidenceState.DECLARED
        else:
            # DATABASE/INFERRED/NOT_FOUND sources do not say who accredited a
            # VERIFIED fee; refuse to label it rather than guess.
            raise ValueError(f"{term.value} is VERIFIED from {source.value}, which accredits no fee origin")
    return FeeEvidence(term, state, item)
