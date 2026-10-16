"""Recalculation check of a stored financial record (ADR-047 §19).

Explaining a stored result and reproducing its calculation are not the same
(§19). This check re-runs, under the current code, the dependency resolver
and the accredited calculator on exactly what a format-v2 document recorded
(its evidence set and its supplied inputs, at its own calculation instant and
for the same requested results) and compares the canonical serialization of
the outcome with what was stored, part by part.

A match shows that the stored resolution and calculations are what *this*
code produces from the stored inputs. It is not historical reproduction
(guarantee C of `assess_reproducibility`): the code and runtime that built
the document still cannot be proven from the document itself.

Read-only and pure: nothing is written, the stored document is never
replaced, and the recalculation is never offered as a new result (that would
need its own linked record, §20). No formula, matrix or decimal policy is
duplicated here; the existing resolver and calculator are called as they are.

The check is refused, never approximated, when the document cannot be
recalculated faithfully: format v1 (it does not record the supplied inputs),
no resolution or calculation stored, an expression table, dependency matrix
or decimal policy that differs from the current code's, or calculations that
do not share one calculation instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from juval.application.financial_calculation import (
    DECIMAL_PRECISION,
    DECIMAL_ROUNDING,
    calculate_financial_results,
)
from juval.application.financial_serialization import FinancialRecordDocument, _core_payload
from juval.application.financial_serialization_v2 import (
    FinancialRecordDocumentV2,
    current_dependency_matrix_digest,
    current_expressions_digest,
)
from juval.domain.financial_dependencies import resolve_financial_dependencies


@dataclass(frozen=True)
class RecalculationCheck:
    """Outcome of recalculating one stored record under the current code.

    `refused`: why no recalculation ran; empty when it ran.
    `differing`: the stored parts the recalculation did not reproduce
    ("resolution" and/or result names); empty when every part matched.
    """

    refused: tuple[str, ...]
    differing: tuple[str, ...] = ()

    @property
    def matches(self) -> bool:
        return not self.refused and not self.differing


def check_recalculation(
    document: Union[FinancialRecordDocument, FinancialRecordDocumentV2],
) -> RecalculationCheck:
    if isinstance(document, FinancialRecordDocument):
        return RecalculationCheck(("format v1 does not record the explicit inputs as supplied",))
    if not isinstance(document, FinancialRecordDocumentV2):
        raise ValueError("Explicit financial record document required")
    core = document.document
    stored = core.calculations
    refused = []
    if core.resolution is None or stored is None or not stored.calculations:
        refused.append("no calculation is recorded")
    if document.implementation.expressions_digest != current_expressions_digest():
        refused.append("expression table differs from the current code")
    if document.implementation.dependency_matrix_digest != current_dependency_matrix_digest():
        refused.append("dependency matrix differs from the current code")
    if stored is not None and (stored.decimal_precision, stored.decimal_rounding) != (DECIMAL_PRECISION,
                                                                                    DECIMAL_ROUNDING):
        refused.append("decimal policy differs from the current calculator")
    instants = {calc.value.provenance.retrieved_at for calc in stored.calculations} if stored is not None else set()
    if len(instants) > 1:
        refused.append("calculations do not share one calculation instant")
    if refused:
        return RecalculationCheck(tuple(refused))

    inputs = document.supplied_inputs
    resolution = resolve_financial_dependencies(
        core.evidence, selling_price=inputs.selling_price, weight=inputs.weight,
        target_profit=inputs.target_profit, target_roi=inputs.target_roi)
    calculations = calculate_financial_results(
        resolution, calculated_at=instants.pop(), requested=frozenset(calc.result for calc in stored.calculations))
    before = _core_payload(core)
    after = _core_payload(FinancialRecordDocument(core.evidence, core.selling_price, resolution, calculations))

    differing = ["resolution"] if before["resolution"] != after["resolution"] else []
    recalculated = {item["result"]: item for item in after["calculations"]["calculations"]}
    differing += [item["result"] for item in before["calculations"]["calculations"]
                  if item != recalculated.get(item["result"])]
    return RecalculationCheck((), tuple(differing))
