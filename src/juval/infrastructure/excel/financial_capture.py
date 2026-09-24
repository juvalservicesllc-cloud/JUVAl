"""Native financial evidence capture from new imports (ADR-047 §22 step 3).

Reads the optional `fin_*` columns of column_mapping.py and turns what a row
explicitly declares into FinancialScenario / FinancialTermEvidence. This is
the NATIVE path: it never reads CostInputs/FeeInputs, legacy snapshots or
application/legacy_financial_projection.py, and it never feeds profitability,
decisions or persistence.

Nothing is inferred (ADR-047 §8, §11-§14):
  * column absent            -> structural absence (term omitted, amount None);
  * blank cell, column there -> NOT_FOUND from SUPPLIER_FILE: the cell was
                                read and declared nothing (never an Amazon lookup);
  * unparseable/non-finite, negative or out-of-range value -> INVALID with raw;
  * an explicit 0            -> a supplier-declared zero, whose applicability
                                is still its own separate declaration;
  * currency, applicability, effective_at, allocation -> only as declared.

A declaration the contract cannot represent (e.g. an amount without its
currency, a naive effective_at, a pack amount without allocation) drops that
term and records why; it is never repaired with a default. Each diagnostic is
emitted where it is detected as a CaptureDiagnostic (subject, code, message,
row, and the column and raw cell value when the failing cell is known);
`problems` keeps the same diagnostics as the legacy "<subject>: <message>" text.

`fin_weight_*` declares the record's weight for the per-pound shipping operand,
as supplied: its unit is never converted or assumed, and the legacy `weight`
column is never read.
VERIFIED here means "declared by this supplier file", never independent
Amazon verification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional

from juval.domain.financial_evidence import (
    MAX_EXCLUSIVE_RATE,
    RATIO_UNIT,
    Applicability,
    DeclaredSellingPrice,
    EffectiveContext,
    FinancialEvidenceSet,
    FinancialScenario,
    FinancialTerm,
    FinancialTermEvidence,
    TermNature,
)
from juval.domain.provenance import FieldValue, SourceType
from juval.domain.units import CANONICAL_WEIGHT_UNIT

from .column_mapping import (
    FINANCIAL_EVIDENCE_COLUMN_SPECS,
    FINANCIAL_PRICE_COLUMNS,
    FINANCIAL_WEIGHT_COLUMNS,
    FINANCIAL_SCENARIO_COLUMNS,
    financial_term_column,
)

ParseCell = Callable[[Any, str], tuple[Optional[Any], bool]]

NATIVE_FINANCIAL_COLUMNS: frozenset[str] = frozenset(spec.canonical for spec in FINANCIAL_EVIDENCE_COLUMN_SPECS)

#: Declared origin of a per-sellable-unit amount. A pack origin is a transformation
#: that must carry its allocation method; the importer never divides anything.
SOURCE_BASES = frozenset({"sellable_unit", "pack"})

_METHOD = "direct_read"

#: Evidence text of a NOT_FOUND produced by a blank cell in a present column.
BLANK_CELL_EVIDENCE = "blank cell in a present supplier-file column; no value declared"


class CaptureCode(str, Enum):
    """Why a declaration was not captured. A diagnostic, not a VerificationStatus."""

    SCENARIO_UNDECLARED = "SCENARIO_UNDECLARED"
    SCENARIO_INVALID = "SCENARIO_INVALID"
    AMOUNT_COLUMN_ABSENT = "AMOUNT_COLUMN_ABSENT"
    CURRENCY_UNDECLARED = "CURRENCY_UNDECLARED"
    CURRENCY_INCOMPATIBLE = "CURRENCY_INCOMPATIBLE"
    APPLICABILITY_COLUMN_ABSENT = "APPLICABILITY_COLUMN_ABSENT"
    JUSTIFICATION_UNDECLARED = "JUSTIFICATION_UNDECLARED"
    EFFECTIVE_AT_UNDECLARED = "EFFECTIVE_AT_UNDECLARED"
    EFFECTIVE_AT_INVALID = "EFFECTIVE_AT_INVALID"
    BASIS_UNDECLARED = "BASIS_UNDECLARED"
    EXCLUSION_WITH_AMOUNT = "EXCLUSION_WITH_AMOUNT"
    SOURCE_BASIS_INVALID = "SOURCE_BASIS_INVALID"
    ALLOCATION_UNDECLARED = "ALLOCATION_UNDECLARED"
    UNIT_UNDECLARED = "UNIT_UNDECLARED"
    #: A domain contract rejected the declaration; the message is the contract's.
    CONTRACT_REJECTED = "CONTRACT_REJECTED"


@dataclass(frozen=True)
class CaptureDiagnostic:
    """One diagnostic as detected. `column`/`raw_value` are set only when a
    specific cell caused it; they are never recovered from the message."""

    subject: str
    code: CaptureCode
    message: str
    row: int
    column: Optional[str] = None
    raw_value: Optional[str] = None

    @property
    def text(self) -> str:
        return f"{self.subject}: {self.message}"


class CaptureFailure(ValueError):
    """A declaration that cannot be captured, with the cell that caused it."""

    def __init__(self, code: CaptureCode, message: str, *, column: Optional[str] = None, raw: Any = None) -> None:
        super().__init__(message)
        self.code, self.column = code, column
        self.raw_value = None if raw is None else str(raw)


@dataclass(frozen=True)
class NativeFinancialCapture:
    """What one imported row declared, before it is bound to an execution.

    `problems` lists, in a deterministic order, every declaration that could
    not be captured and why. `scenario is None` means no complete scenario was
    declared, so the row's evidence cannot be bound. `selling_price` is the
    row's native declared price (None when not declared); it is never the
    legacy `selling_price` and never a market PriceObservation.
    """

    record_ref: str
    scenario: Optional[FinancialScenario]
    terms: tuple[FinancialTermEvidence, ...]
    problems: tuple[str, ...]
    selling_price: Optional[DeclaredSellingPrice] = None
    diagnostics: tuple[CaptureDiagnostic, ...] = ()
    weight: Optional[FieldValue] = None

    def bind(self, execution_id: str) -> FinancialEvidenceSet:
        """This row's FinancialEvidenceSet within `execution_id` (supplied by the caller)."""
        if self.scenario is None:
            raise ValueError(f"{self.record_ref} declares no complete financial scenario to bind")
        return FinancialEvidenceSet(scenario=self.scenario, execution_id=execution_id,
                                    record_reference=self.record_ref, terms=self.terms)


def has_native_financial_columns(column_index: dict[str, int]) -> bool:
    return not NATIVE_FINANCIAL_COLUMNS.isdisjoint(column_index)


def capture_native_financial_evidence(
    cells: dict[str, Any], *, record_ref: str, row_number: int, source: str, now: datetime,
    parse_cell: ParseCell,
) -> NativeFinancialCapture:
    row = _Row(cells, row_number, source, now, parse_cell)
    scenario = row.scenario()
    selling_price = row.selling_price()
    weight = row.weight()
    terms = []
    for term in FinancialTerm:
        evidence = row.term(term)
        if evidence is None:
            continue
        if scenario is not None and evidence.has_usable_amount and term.nature is not TermNature.DIMENSIONLESS_RATIO:
            currency = evidence.amount.unit.split("/")[0]
            if currency != scenario.currency:
                row.problem(term.value, CaptureFailure(
                    CaptureCode.CURRENCY_INCOMPATIBLE,
                    f"currency {currency} is incompatible with scenario currency {scenario.currency}; not converted",
                    column=financial_term_column(term, "currency"), raw=currency))
                continue
        terms.append(evidence)
    diagnostics = tuple(row.diagnostics)
    return NativeFinancialCapture(record_ref, scenario, tuple(terms), tuple(d.text for d in diagnostics),
                                  selling_price, diagnostics, weight)


class _Row:
    def __init__(self, cells: dict[str, Any], row_number: int, source: str, now: datetime,
                 parse_cell: ParseCell) -> None:
        self.cells, self.row_number, self.source, self.now = cells, row_number, source, now
        self.parse_cell = parse_cell
        self.diagnostics: list[CaptureDiagnostic] = []

    def problem(self, subject: str, error: ValueError) -> None:
        if isinstance(error, CaptureFailure):
            code, column, raw = error.code, error.column, error.raw_value
        else:
            code, column, raw = CaptureCode.CONTRACT_REJECTED, None, None
        self.diagnostics.append(CaptureDiagnostic(subject, code, str(error), self.row_number, column, raw))

    def _text(self, column: str) -> Optional[str]:
        value, _ = self.parse_cell(self.cells.get(column), "str")
        return value

    def _provenance(self, column: str) -> dict[str, Any]:
        return dict(source=self.source, method=_METHOD, retrieved_at=self.now,
                    source_reference=f"row={self.row_number};column={column}")

    def _not_found(self, column: str) -> FieldValue:
        # The supplier cell *was* read and declared nothing: SUPPLIER_FILE +
        # NOT_FOUND, not SourceType.NOT_FOUND ("no source attempted"). It is
        # not a marketplace lookup, not proof the term does not exist.
        return FieldValue.not_found(source_type=SourceType.SUPPLIER_FILE, evidence=BLANK_CELL_EVIDENCE,
                                    **self._provenance(column))

    def scenario(self) -> Optional[FinancialScenario]:
        declared = {target: self._text(header) for header, target in FINANCIAL_SCENARIO_COLUMNS.items()}
        optional = {"context_requirements"}
        missing = [header for header, target in FINANCIAL_SCENARIO_COLUMNS.items()
                   if target not in optional and declared[target] is None]
        if missing:
            self.problem("scenario", CaptureFailure(CaptureCode.SCENARIO_UNDECLARED,
                                                    f"not declared: {', '.join(missing)}"))
            return None
        try:
            required = frozenset(FinancialTerm(name.strip().upper())
                                 for name in re.split(r"[;,]", declared["required_terms"]) if name.strip())
            requirements = tuple(item.strip() for item in (declared["context_requirements"] or "").split(";")
                                 if item.strip())
            return FinancialScenario(
                scenario_id=declared["scenario_id"], scenario_version=declared["scenario_version"],
                currency=declared["currency"], sellable_unit_definition=declared["sellable_unit_definition"],
                policy_identity=declared["policy_identity"], required_terms=required,
                context_requirements=requirements,
            )
        except ValueError as error:
            self.problem("scenario", CaptureFailure(CaptureCode.SCENARIO_INVALID, str(error)))
            return None

    def selling_price(self) -> Optional[DeclaredSellingPrice]:
        """The row's declared price; its currency is only ever the declared column."""
        present = {header.removeprefix("fin_selling_price_"): header
                   for header in FINANCIAL_PRICE_COLUMNS if header in self.cells}
        if all(self._text(column) is None for column in present.values()):
            return None  # not declared in this row: structural absence
        try:
            if "amount" not in present:
                raise CaptureFailure(CaptureCode.AMOUNT_COLUMN_ABSENT, "declared without an amount column")
            context = self._context(present)
            column = present["amount"]
            raw = self.cells.get(column)
            value, valid = self.parse_cell(raw, "decimal")
            if value is None:
                amount = self._not_found(column)
            elif not valid or value < 0:
                amount = FieldValue.invalid(str(raw).strip(), source_type=SourceType.SUPPLIER_FILE,
                                            **self._provenance(column))
            else:
                currency = self._text(present["currency"]) if "currency" in present else None
                if currency is None:
                    raise CaptureFailure(CaptureCode.CURRENCY_UNDECLARED,
                                         "a declared price requires its declared currency; none is inferred",
                                         column=present.get("currency"))
                provenance = self._provenance(column)
                method = self._text(present["method"]) if "method" in present else None
                if method is None:
                    amount = FieldValue.verified(value, unit=currency, source_type=SourceType.SUPPLIER_FILE,
                                                 **provenance)
                else:
                    provenance["method"] = method
                    amount = FieldValue.inferred(value, unit=currency, source_type=SourceType.SUPPLIER_FILE,
                                                 **provenance)
            return DeclaredSellingPrice(amount=amount, context=context)
        except ValueError as error:
            self.problem("SELLING_PRICE", error)
            return None

    def weight(self) -> Optional[FieldValue]:
        """The row's declared weight, exactly as supplied; None when not declared.

        The unit is the declared one (None when the unit cell is blank, reported
        as UNIT_UNDECLARED): no unit is assumed and no conversion happens here.
        """
        present = {header.removeprefix("fin_weight_"): header
                   for header in FINANCIAL_WEIGHT_COLUMNS if header in self.cells}
        if all(self._text(column) is None for column in present.values()):
            return None
        if "amount" not in present:
            self.problem("WEIGHT", CaptureFailure(CaptureCode.AMOUNT_COLUMN_ABSENT, "declared without an amount column"))
            return None
        column = present["amount"]
        raw = self.cells.get(column)
        value, valid = self.parse_cell(raw, "decimal")
        if value is None:
            return self._not_found(column)
        if not valid or value < 0:
            return FieldValue.invalid(str(raw).strip(), source_type=SourceType.SUPPLIER_FILE,
                                      **self._provenance(column))
        unit = self._text(present["unit"]) if "unit" in present else None
        if unit is None:
            self.problem("WEIGHT", CaptureFailure(CaptureCode.UNIT_UNDECLARED,
                                                  "weight declared without a unit; none is assumed",
                                                  column=present.get("unit")))
        provenance = self._provenance(column)
        method = self._text(present["method"]) if "method" in present else None
        if method is None:
            return FieldValue.verified(value, unit=unit, source_type=SourceType.SUPPLIER_FILE, **provenance)
        provenance["method"] = method
        return FieldValue.inferred(value, unit=unit, source_type=SourceType.SUPPLIER_FILE, **provenance)

    def term(self, term: FinancialTerm) -> Optional[FinancialTermEvidence]:
        columns = {suffix: financial_term_column(term, suffix)
                   for suffix in ("amount", "currency", "applies", "applies_method", "justification",
                                  "effective_at", "basis", "allocation", "source_basis")}
        present = {suffix: column for suffix, column in columns.items() if column in self.cells}
        if all(self._text(column) is None for column in present.values()):
            return None  # nothing declared for this term in this row: structural absence
        try:
            applicability = self._applicability(term, present)
            context = self._context(present)
            amount = self._amount(term, present, applicability)
            allocation = self._text(present["allocation"]) if "allocation" in present else None
            source_basis = self._text(present["source_basis"]) if "source_basis" in present else None
            if source_basis is not None:
                if source_basis.lower() not in SOURCE_BASES:
                    raise CaptureFailure(CaptureCode.SOURCE_BASIS_INVALID,
                                         f"source_basis must be one of {sorted(SOURCE_BASES)}, got {source_basis!r}",
                                         column=present["source_basis"], raw=source_basis)
                if source_basis.lower() == "pack" and allocation is None:
                    raise CaptureFailure(CaptureCode.ALLOCATION_UNDECLARED,
                                         "a pack-sourced amount must declare its allocation to one sellable unit",
                                         column=present.get("allocation"))
            return FinancialTermEvidence(term=term, applicability=applicability, context=context,
                                         amount=amount, allocation_method=allocation)
        except ValueError as error:
            self.problem(term.value, error)
            return None

    def _applicability(self, term: FinancialTerm, present: dict[str, str]) -> Applicability:
        column = present.get("applies")
        if column is None:
            raise CaptureFailure(CaptureCode.APPLICABILITY_COLUMN_ABSENT,
                                 "declared without an applicability column; applicability is never inferred")
        justification = self._text(present["justification"]) if "justification" in present else None
        raw = self.cells.get(column)
        value, valid = self.parse_cell(raw, "bool")
        if value is None:
            applies = self._not_found(column)
            justification = justification or f"applicability cell blank in {self.source} row {self.row_number}"
        elif not valid:
            applies = FieldValue.invalid(value, source_type=SourceType.SUPPLIER_FILE, **self._provenance(column))
            justification = justification or f"applicability cell invalid in {self.source} row {self.row_number}"
        else:
            if justification is None:
                raise CaptureFailure(CaptureCode.JUSTIFICATION_UNDECLARED,
                                     "an applicability assertion requires a declared justification",
                                     column=present.get("justification"))
            method = self._text(present["applies_method"]) if "applies_method" in present else None
            provenance = self._provenance(column)
            if method is None:
                applies = FieldValue.verified(value, source_type=SourceType.SUPPLIER_FILE, **provenance)
            else:
                # The supplier states it inferred this, and how: it stays INFERRED.
                provenance["method"] = method
                applies = FieldValue.inferred(value, source_type=SourceType.SUPPLIER_FILE, **provenance)
        return Applicability(applies=applies, justification=justification)

    def _context(self, present: dict[str, str]) -> EffectiveContext:
        raw = self.cells.get(present["effective_at"]) if "effective_at" in present else None
        basis = self._text(present["basis"]) if "basis" in present else None
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise CaptureFailure(CaptureCode.EFFECTIVE_AT_UNDECLARED,
                                 "effective_at not declared; the import time never substitutes for it",
                                 column=present.get("effective_at"))
        if basis is None:
            raise CaptureFailure(CaptureCode.BASIS_UNDECLARED,
                                 "basis not declared; the amount's economic basis is never assumed",
                                 column=present.get("basis"))
        if isinstance(raw, datetime):
            effective_at = raw
        else:
            try:
                effective_at = datetime.fromisoformat(str(raw).strip())
            except ValueError:
                raise CaptureFailure(CaptureCode.EFFECTIVE_AT_INVALID, f"effective_at {raw!r} is not an ISO 8601 instant",
                                     column=present["effective_at"], raw=raw) from None
        try:
            return EffectiveContext(effective_at=effective_at, basis_definition=basis)
        except ValueError as error:
            raise CaptureFailure(CaptureCode.EFFECTIVE_AT_INVALID, str(error),
                                 column=present["effective_at"], raw=raw) from None

    def _amount(self, term: FinancialTerm, present: dict[str, str],
                applicability: Applicability) -> Optional[FieldValue]:
        column = present.get("amount")
        if column is None:
            return None  # amount column absent: structural absence, not NOT_FOUND
        raw = self.cells.get(column)
        value, valid = self.parse_cell(raw, "decimal")
        if applicability.excludes:
            if value is not None:
                raise CaptureFailure(CaptureCode.EXCLUSION_WITH_AMOUNT,
                                     "an accredited exclusion carries no amount, not even zero",
                                     column=column, raw=raw)
            return None
        if value is None:
            return self._not_found(column)
        is_ratio = term.nature is TermNature.DIMENSIONLESS_RATIO
        in_domain = valid and (Decimal("0") <= value < MAX_EXCLUSIVE_RATE if is_ratio else value >= 0)
        if not in_domain:
            return FieldValue.invalid(str(raw).strip(), source_type=SourceType.SUPPLIER_FILE,
                                      **self._provenance(column))
        if is_ratio:
            unit = RATIO_UNIT
        else:
            currency = self._text(present["currency"]) if "currency" in present else None
            if currency is None:
                raise CaptureFailure(CaptureCode.CURRENCY_UNDECLARED,
                                     "a monetary amount requires its declared currency; none is inferred",
                                     column=present.get("currency"))
            unit = f"{currency}/{CANONICAL_WEIGHT_UNIT}" if term.nature is TermNature.MONETARY_PER_POUND else currency
        return FieldValue.verified(value, unit=unit, source_type=SourceType.SUPPLIER_FILE,
                                   **self._provenance(column))
