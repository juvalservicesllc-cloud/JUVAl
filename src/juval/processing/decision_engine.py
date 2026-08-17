"""Decision Engine — rule evaluation for BUY / REVIEW / PASS.

Design intent (Phase 1, requirement 12): this is an extensible model for
rules, not a final, definitive rule set. The default rules below are a
reasonable conceptual starting point (mirroring the example in the Phase 1
brief), explicitly NOT commercial thresholds — every numeric threshold is
read from `Thresholds`, supplied by the caller.

Precedence: PASS rules are evaluated first (hard disqualifiers). If none
match, REVIEW rules are evaluated (borderline / insufficient data). If
neither matches, the decision is BUY.

A rule is any callable `(DecisionInputs, Thresholds) -> Optional[DecisionReason]`.
Returning None means the rule did not fire. Passing custom `pass_rules` /
`review_rules` to `evaluate_decision` replaces the defaults entirely, so
callers can adopt their own rule set without forking this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional, Sequence

from juval.domain.decision import Decision, DecisionInputs, DecisionReason, DecisionResult, Thresholds
from juval.domain.risk import RiskStatus, RiskType

Rule = Callable[[DecisionInputs, Thresholds], Optional[DecisionReason]]

_SEVERITY_RANK = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


# --------------------------------------------------------------------------
# Default PASS rules (hard disqualifiers)
# --------------------------------------------------------------------------


def rule_pass_negative_profit(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if inputs.profit.is_usable and inputs.profit.value < 0:
        return DecisionReason("NEGATIVE_PROFIT", f"Profit is negative ({inputs.profit.value}); sourcing this would lose money.")
    return None


def rule_pass_disqualifying_risk(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    max_rank = _SEVERITY_RANK[thresholds.maximum_risk_severity.value]
    for flag in inputs.risk_profile.flags:
        if flag.status != RiskStatus.PRESENT:
            continue
        if _SEVERITY_RANK[flag.severity.value] > max_rank:
            return DecisionReason(
                "RISK_ABOVE_MAXIMUM",
                f"{flag.risk_type.value} is PRESENT with severity {flag.severity.value}, above the configured maximum {thresholds.maximum_risk_severity.value}.",
            )
    return None


def rule_pass_restricted(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if thresholds.allow_restricted:
        return None
    flag = inputs.risk_profile.flag_for(RiskType.RESTRICTED)
    if flag is not None and flag.status == RiskStatus.PRESENT:
        return DecisionReason("RESTRICTED", "Listing is RESTRICTED and allow_restricted=False.")
    return None


def rule_pass_asin_not_found(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    flag = inputs.risk_profile.flag_for(RiskType.ASIN_NOT_FOUND)
    if flag is not None and flag.status == RiskStatus.PRESENT:
        return DecisionReason("ASIN_NOT_FOUND", "No matching ASIN was found on the target marketplace.")
    return None


DEFAULT_PASS_RULES: tuple[Rule, ...] = (
    rule_pass_negative_profit,
    rule_pass_disqualifying_risk,
    rule_pass_restricted,
    rule_pass_asin_not_found,
)


# --------------------------------------------------------------------------
# Default REVIEW rules (borderline / insufficient data — needs a human)
# --------------------------------------------------------------------------


def rule_review_profit_unknown(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if not inputs.profit.is_usable:
        return DecisionReason("PROFIT_UNKNOWN", f"Profit could not be determined ({inputs.profit.status.value}).")
    return None


def rule_review_profit_below_target(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if inputs.profit.is_usable and inputs.profit.value < thresholds.target_profit:
        return DecisionReason(
            "PROFIT_BELOW_TARGET", f"Profit {inputs.profit.value} is below target {thresholds.target_profit}."
        )
    return None


def rule_review_roi_unknown_or_below_target(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if not inputs.roi.is_usable:
        return DecisionReason("ROI_UNKNOWN", f"ROI could not be determined ({inputs.roi.status.value}).")
    if inputs.roi.value < thresholds.target_roi:
        return DecisionReason("ROI_BELOW_TARGET", f"ROI {inputs.roi.value} is below target {thresholds.target_roi}.")
    return None


def rule_review_demand_unknown_or_below_minimum(
    inputs: DecisionInputs, thresholds: Thresholds
) -> Optional[DecisionReason]:
    sales = inputs.estimated_monthly_sales
    if sales is None or not sales.is_usable:
        return DecisionReason("DEMAND_UNKNOWN", "Estimated monthly sales could not be determined.")
    if sales.value < thresholds.minimum_estimated_monthly_sales:
        return DecisionReason(
            "DEMAND_BELOW_MINIMUM",
            f"Estimated monthly sales {sales.value} is below minimum {thresholds.minimum_estimated_monthly_sales}.",
        )
    return None


def rule_review_unknown_risk(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if thresholds.allow_unknown_risk:
        return None
    if inputs.risk_profile.has_unknown_risk:
        unknown_types = [f.risk_type.value for f in inputs.risk_profile.flags if f.status == RiskStatus.UNKNOWN]
        return DecisionReason("RISK_UNKNOWN", f"Risk could not be determined for: {', '.join(unknown_types)}.")
    return None


def rule_review_approval_required(inputs: DecisionInputs, thresholds: Thresholds) -> Optional[DecisionReason]:
    if thresholds.allow_approval_required:
        return None
    flag = inputs.risk_profile.flag_for(RiskType.APPROVAL_REQUIRED)
    if flag is not None and flag.status == RiskStatus.PRESENT:
        return DecisionReason("APPROVAL_REQUIRED", "Selling this product requires Amazon category approval.")
    return None


DEFAULT_REVIEW_RULES: tuple[Rule, ...] = (
    rule_review_profit_unknown,
    rule_review_profit_below_target,
    rule_review_roi_unknown_or_below_target,
    rule_review_demand_unknown_or_below_minimum,
    rule_review_unknown_risk,
    rule_review_approval_required,
)


def evaluate_decision(
    inputs: DecisionInputs,
    thresholds: Thresholds,
    *,
    now: datetime,
    pass_rules: Sequence[Rule] = DEFAULT_PASS_RULES,
    review_rules: Sequence[Rule] = DEFAULT_REVIEW_RULES,
) -> DecisionResult:
    pass_reasons = tuple(r for r in (rule(inputs, thresholds) for rule in pass_rules) if r is not None)
    if pass_reasons:
        return DecisionResult(decision=Decision.PASS, reasons=pass_reasons, evaluated_at=now)

    review_reasons = tuple(r for r in (rule(inputs, thresholds) for rule in review_rules) if r is not None)
    if review_reasons:
        return DecisionResult(decision=Decision.REVIEW, reasons=review_reasons, evaluated_at=now)

    return DecisionResult(decision=Decision.BUY, reasons=(), evaluated_at=now)
