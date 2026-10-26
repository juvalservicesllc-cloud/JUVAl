"""Informative sub-classification of REVIEW records (D7-D, 2026-10-26).

A REVIEW record whose *only* reason code is DEMAND_UNKNOWN cleared every other
rule -- economics, risk, restrictions -- and is held back solely because no
demand evidence exists. That is worth finding, and it stays REVIEW: this module
never changes, overrides or predicts a decision, and it is not a BUY signal.

It reads the structured `decision_reason_codes` of a snapshot. Snapshots
written before that field existed have no codes; their display text is never
parsed back into codes, so they are NOT_CLASSIFIABLE rather than guessed.

The SQL filters and counts in both stores mirror `review_classification()`
exactly; tests hold them to the same answers.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

PENDING_DEMAND_VERIFICATION = "PENDING_DEMAND_VERIFICATION"
NOT_CLASSIFIABLE = "NOT_CLASSIFIABLE"
DEMAND_ONLY_CODES = ["DEMAND_UNKNOWN"]


def review_classification(snapshot: Mapping[str, Any]) -> Optional[str]:
    """PENDING_DEMAND_VERIFICATION, NOT_CLASSIFIABLE, or None.

    None means "no sub-classification": the record is not REVIEW, or it is a
    REVIEW with other blockers besides (or instead of) unknown demand.
    """
    if snapshot.get("decision") != "REVIEW":
        return None
    codes = snapshot.get("decision_reason_codes")
    if codes is None:
        return NOT_CLASSIFIABLE
    return PENDING_DEMAND_VERIFICATION if list(codes) == DEMAND_ONLY_CODES else None
