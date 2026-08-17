"""Data quality validation (Phase 1, requirement 16).

Each function here is an independent, composable check that returns a list
of `ProcessingIssue`s — never raises for a data problem (raising is reserved
for programming errors / malformed calls). This lets a batch keep processing
every record and report every issue found, instead of stopping at the first
one (see docs/architecture/ARCHITECTURE.md §7).

These checks are a defense-in-depth audit layer: they re-verify data that
may have been constructed elsewhere (importer, enrichment adapter) rather
than assuming upstream code already got it right.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from juval.domain.identifiers import is_valid_asin, is_valid_ean, is_valid_gtin, is_valid_upc
from juval.domain.issues import IssueLevel, ProcessingIssue
from juval.domain.product import Competition, Dimensions, Identification, Price
from juval.domain.provenance import FieldValue
from juval.processing.profitability import ProfitabilityResult

_EPSILON = Decimal("0.01")


@dataclass(frozen=True)
class DataQualityConfig:
    """Sanity/staleness bounds — NOT commercial thresholds. These exist to
    catch obviously broken data (a 50000 lb "book", a price quoted in 2019),
    not to make a sourcing decision. Defaults are deliberately generous;
    override per-catalog if needed.
    """

    max_reasonable_weight_lb: Decimal = Decimal("500")
    max_reasonable_dimension_in: Decimal = Decimal("200")
    max_data_age: timedelta = timedelta(days=30)


_PLACEHOLDER_SOURCES = {"unknown", "n/a", "na", "todo", "tbd", "?"}


def validate_identification(identification: Identification, *, record_ref: Optional[str] = None) -> list[ProcessingIssue]:
    issues: list[ProcessingIssue] = []

    def _check(fv: Optional[FieldValue[str]], field_name: str, validator) -> None:
        if fv is None or not fv.is_usable:
            return
        if not validator(fv.value):
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR,
                    code=f"INVALID_{field_name.upper()}_FORMAT",
                    message=f"{field_name} value {fv.value!r} has status {fv.status.value} but fails format validation.",
                    field=field_name,
                    record_ref=record_ref,
                )
            )

    _check(identification.asin, "asin", is_valid_asin)
    _check(identification.upc, "upc", is_valid_upc)
    _check(identification.ean, "ean", is_valid_ean)
    _check(identification.gtin, "gtin", is_valid_gtin)
    return issues


def validate_dimensions(
    dimensions: Dimensions, *, config: DataQualityConfig = DataQualityConfig(), record_ref: Optional[str] = None
) -> list[ProcessingIssue]:
    issues: list[ProcessingIssue] = []

    def _check_positive(fv: Optional[FieldValue[Decimal]], field_name: str, max_bound: Decimal) -> None:
        if fv is None or not fv.is_usable:
            return
        if fv.value <= 0:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR,
                    code=f"IMPOSSIBLE_{field_name.upper()}",
                    message=f"{field_name} must be positive, got {fv.value} {fv.unit}.",
                    field=field_name,
                    record_ref=record_ref,
                )
            )
        elif fv.value > max_bound:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.WARNING,
                    code=f"{field_name.upper()}_EXCEEDS_SANITY_BOUND",
                    message=f"{field_name} {fv.value} {fv.unit} exceeds the configured sanity bound {max_bound}; verify.",
                    field=field_name,
                    record_ref=record_ref,
                )
            )

    _check_positive(dimensions.weight, "weight", config.max_reasonable_weight_lb)
    _check_positive(dimensions.height, "height", config.max_reasonable_dimension_in)
    _check_positive(dimensions.width, "width", config.max_reasonable_dimension_in)
    _check_positive(dimensions.length, "length", config.max_reasonable_dimension_in)
    return issues


def validate_price(price: Price, *, record_ref: Optional[str] = None) -> list[ProcessingIssue]:
    issues: list[ProcessingIssue] = []
    candidates = {
        "current_buy_box": price.current_buy_box,
        "average_buy_box_30d": price.average_buy_box_30d,
        "average_buy_box_90d": price.average_buy_box_90d,
        "average_buy_box_180d": price.average_buy_box_180d,
        "min_fba_price": price.min_fba_price,
        "min_fbm_price": price.min_fbm_price,
        "selling_price_used": price.selling_price_used,
    }
    for field_name, fv in candidates.items():
        if fv is not None and fv.is_usable and fv.value < 0:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR,
                    code="NEGATIVE_PRICE",
                    message=f"{field_name} must not be negative, got {fv.value}.",
                    field=field_name,
                    record_ref=record_ref,
                )
            )
    return issues


def validate_financial_consistency(
    result: ProfitabilityResult, *, record_ref: Optional[str] = None
) -> list[ProcessingIssue]:
    """Recomputes profit/ROI/margin from the intermediate values carried in
    `result` and flags any drift — catches a caller having hand-built a
    ProfitabilityResult (e.g. from a cache or an import) with inconsistent
    numbers, which the dataclass itself does not police."""

    issues: list[ProcessingIssue] = []
    if result.seller_proceeds is None or result.total_cost is None:
        return issues

    expected_profit = result.seller_proceeds - result.total_cost
    if result.profit.is_usable and abs(result.profit.value - expected_profit) > _EPSILON:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR,
                code="PROFIT_INCONSISTENT",
                message=f"profit={result.profit.value} does not match seller_proceeds-total_cost={expected_profit}.",
                field="profit",
                record_ref=record_ref,
            )
        )

    if result.profit.is_usable and result.total_cost > 0 and result.roi.is_usable:
        expected_roi = result.profit.value / result.total_cost
        if abs(result.roi.value - expected_roi) > _EPSILON:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR,
                    code="ROI_INCONSISTENT",
                    message=f"roi={result.roi.value} does not match profit/total_cost={expected_roi}.",
                    field="roi",
                    record_ref=record_ref,
                )
            )

    if result.profit.is_usable and result.roi.is_usable:
        if (result.profit.value > 0) != (result.roi.value > 0) and result.profit.value != 0 and result.roi.value != 0:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR,
                    code="PROFIT_ROI_SIGN_MISMATCH",
                    message=f"profit={result.profit.value} and roi={result.roi.value} have inconsistent signs.",
                    record_ref=record_ref,
                )
            )
    return issues


def validate_competition_consistency(
    competition: Competition, *, record_ref: Optional[str] = None
) -> list[ProcessingIssue]:
    issues: list[ProcessingIssue] = []
    total = competition.total_offers
    if total is not None and total.is_usable:
        if competition.amazon_in_buy_box is not None and competition.amazon_in_buy_box.is_usable:
            if competition.amazon_in_buy_box.value and total.value == 0:
                issues.append(
                    ProcessingIssue(
                        level=IssueLevel.RECORD_ERROR,
                        code="CONTRADICTORY_BUY_BOX_DATA",
                        message="amazon_in_buy_box is True but total_offers is 0.",
                        record_ref=record_ref,
                    )
                )
        eligible_fba = competition.buy_box_eligible_fba
        eligible_fbm = competition.buy_box_eligible_fbm
        if eligible_fba is not None and eligible_fba.is_usable and eligible_fbm is not None and eligible_fbm.is_usable:
            if eligible_fba.value + eligible_fbm.value > total.value:
                issues.append(
                    ProcessingIssue(
                        level=IssueLevel.RECORD_ERROR,
                        code="CONTRADICTORY_OFFER_COUNTS",
                        message=(
                            f"buy_box_eligible_fba+buy_box_eligible_fbm "
                            f"({eligible_fba.value}+{eligible_fbm.value}) exceeds total_offers ({total.value})."
                        ),
                        record_ref=record_ref,
                    )
                )
    return issues


def validate_freshness(
    fv: FieldValue,
    *,
    field_name: str,
    now: datetime,
    config: DataQualityConfig = DataQualityConfig(),
    record_ref: Optional[str] = None,
) -> list[ProcessingIssue]:
    if not fv.is_usable:
        return []
    age = now - fv.provenance.retrieved_at
    if age > config.max_data_age:
        return [
            ProcessingIssue(
                level=IssueLevel.WARNING,
                code="STALE_DATA",
                message=f"{field_name} was retrieved {age} ago, older than the configured max age {config.max_data_age}.",
                field=field_name,
                record_ref=record_ref,
            )
        ]
    return []


def validate_source(fv: FieldValue, *, field_name: str, record_ref: Optional[str] = None) -> list[ProcessingIssue]:
    if not fv.is_usable:
        return []
    if fv.provenance.source.strip().lower() in _PLACEHOLDER_SOURCES:
        return [
            ProcessingIssue(
                level=IssueLevel.WARNING,
                code="UNKNOWN_SOURCE",
                message=f"{field_name} has status {fv.status.value} but a placeholder source ({fv.provenance.source!r}).",
                field=field_name,
                record_ref=record_ref,
            )
        ]
    return []
