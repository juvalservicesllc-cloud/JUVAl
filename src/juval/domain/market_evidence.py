"""Provider-neutral evidence observations (ADR-046).

These objects validate declarations, not their truth or coverage. No ingestion,
scoring, persistence, freshness policy or projection to legacy Product fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from .product import Identification
from .provenance import FieldValue, VerificationStatus


def _instant(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Evidence timestamps require an effective timezone offset")
    return value.astimezone(timezone.utc)


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be explicit nonempty text")


def _subject(value: Identification) -> None:
    if not isinstance(value, Identification):
        raise ValueError("subject must reuse Identification")


def _currency(value: str) -> None:
    if (not isinstance(value, str) or len(value) != 3 or not value.isascii()
            or not value.isalpha() or not value.isupper()):
        raise ValueError("currency requires three uppercase ASCII letters")


def _observation(subject: Identification, value: FieldValue, observed_at: datetime) -> None:
    _subject(subject)
    if not isinstance(value, FieldValue) or not isinstance(value.status, VerificationStatus):
        raise ValueError("Evidence requires a FieldValue with an explicit verification status")
    if _instant(observed_at) > _instant(value.provenance.retrieved_at):
        raise ValueError("observed_at cannot follow retrieved_at")
    if not value.is_usable and value.value is not None:
        raise ValueError("NOT_FOUND/INVALID evidence must not carry a usable value")


def _number(value: FieldValue, unit: str, *, integer: bool, minimum: int) -> None:
    if not value.is_usable:
        return  # Preserve unavailable evidence/diagnostics, without unit or zero substitution.
    number = value.value
    valid_type = isinstance(number, int) and not isinstance(number, bool) if integer else isinstance(number, Decimal)
    if not valid_type or (isinstance(number, Decimal) and not number.is_finite()):
        raise ValueError("Evidence requires a finite number of the declared type")
    if value.unit != unit or number < minimum:
        raise ValueError("Evidence unit or range is invalid")


@dataclass(frozen=True)
class EvidenceWindow:
    """Declared/requested interval [start, end); never a coverage assertion."""
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if _instant(self.start) >= _instant(self.end):
            raise ValueError("Evidence window must have positive duration")


class DemandMetric(str, Enum):
    ESTIMATED_SALES = "ESTIMATED_SALES"
    SALES_VELOCITY = "SALES_VELOCITY"
    CURRENT_BSR = "CURRENT_BSR"
    AVERAGE_BSR = "AVERAGE_BSR"
    RANK_DROPS = "RANK_DROPS"


@dataclass(frozen=True)
class DemandObservation:
    subject: Identification
    metric: DemandMetric
    value: FieldValue[int | Decimal]
    observed_at: datetime
    population_definition: str
    window: EvidenceWindow | None = None
    rank_category: str | None = None

    def __post_init__(self) -> None:
        _observation(self.subject, self.value, self.observed_at)
        _text(self.population_definition, "population_definition")
        if not isinstance(self.metric, DemandMetric):
            raise ValueError("Explicit DemandMetric required")
        if self.rank_category is not None:
            _text(self.rank_category, "rank_category")
        if self.metric == DemandMetric.CURRENT_BSR:
            if self.window is not None:
                raise ValueError("CURRENT_BSR is a point observation without an aggregate window")
        elif not isinstance(self.window, EvidenceWindow) or _instant(self.window.end) > _instant(self.observed_at):
            raise ValueError("Aggregate demand requires a window ending no later than observed_at")
        if self.metric in (DemandMetric.CURRENT_BSR, DemandMetric.AVERAGE_BSR, DemandMetric.RANK_DROPS):
            _text(self.rank_category, "rank_category")
        unit, integer, minimum = {
            DemandMetric.ESTIMATED_SALES: ("units", True, 0),
            DemandMetric.SALES_VELOCITY: ("units/day", False, 0),
            DemandMetric.CURRENT_BSR: ("rank", True, 1),
            DemandMetric.AVERAGE_BSR: ("rank", False, 1),
            DemandMetric.RANK_DROPS: ("drops", True, 0),
        }[self.metric]
        _number(self.value, unit, integer=integer, minimum=minimum)
        if self.metric == DemandMetric.ESTIMATED_SALES and self.value.is_usable:
            if self.value.status != VerificationStatus.INFERRED:
                raise ValueError("Usable estimated sales must remain INFERRED")


class CountPopulation(str, Enum):
    OFFERS = "OFFERS"
    DISTINCT_SELLERS = "DISTINCT_SELLERS"


class FulfillmentScope(str, Enum):
    ALL = "ALL"
    FBA = "FBA"
    FBM = "FBM"


@dataclass(frozen=True)
class CompetitionCount:
    """Point count; eligible_only filters the declared population, not JUVAl."""
    subject: Identification
    value: FieldValue[int]
    observed_at: datetime
    population: CountPopulation
    fulfillment: FulfillmentScope
    eligible_only: bool
    population_definition: str

    def __post_init__(self) -> None:
        _observation(self.subject, self.value, self.observed_at)
        _text(self.population_definition, "population_definition")
        if not isinstance(self.population, CountPopulation) or not isinstance(self.fulfillment, FulfillmentScope):
            raise ValueError("Explicit count population and fulfillment required")
        if type(self.eligible_only) is not bool:
            raise ValueError("eligible_only must be an explicit bool")
        unit = "offers" if self.population == CountPopulation.OFFERS else "sellers"
        _number(self.value, unit, integer=True, minimum=0)


class AmazonPresenceScope(str, Enum):
    OFFER_POPULATION = "OFFER_POPULATION"
    BUY_BOX = "BUY_BOX"


@dataclass(frozen=True)
class AmazonPresenceObservation:
    subject: Identification
    value: FieldValue[bool]
    observed_at: datetime
    scope: AmazonPresenceScope
    population_definition: str

    def __post_init__(self) -> None:
        _observation(self.subject, self.value, self.observed_at)
        _text(self.population_definition, "population_definition")
        if not isinstance(self.scope, AmazonPresenceScope):
            raise ValueError("Explicit AmazonPresenceScope required")
        if self.value.is_usable and type(self.value.value) is not bool:
            raise ValueError("Presence requires boolean evidence")


class PriceKind(str, Enum):
    SUPPLIER_QUOTE = "SUPPLIER_QUOTE"
    BUY_BOX = "BUY_BOX"
    FBA_OFFER = "FBA_OFFER"
    FBM_OFFER = "FBM_OFFER"


@dataclass(frozen=True)
class PriceObservation:
    subject: Identification
    amount: FieldValue[Decimal]
    observed_at: datetime
    kind: PriceKind
    currency: str
    price_basis: str

    def __post_init__(self) -> None:
        _observation(self.subject, self.amount, self.observed_at)
        if not isinstance(self.kind, PriceKind):
            raise ValueError("Explicit PriceKind required")
        _currency(self.currency)
        _text(self.price_basis, "price_basis")
        _number(self.amount, self.currency, integer=False, minimum=0)


@dataclass(frozen=True)
class PriceSeries:
    """Comparable observations; gaps remain gaps, with no stability assertion.

    expected_interval declares a sampling cadence, not actual coverage.
    A frozen container does not deeply freeze arbitrary raw diagnostics.
    """
    subject: Identification
    kind: PriceKind
    currency: str
    price_basis: str
    window: EvidenceWindow
    observations: tuple[PriceObservation, ...]
    expected_interval: timedelta | None = None

    def __post_init__(self) -> None:
        _subject(self.subject)
        if not isinstance(self.kind, PriceKind):
            raise ValueError("Explicit PriceKind required")
        _currency(self.currency)
        _text(self.price_basis, "price_basis")
        if not isinstance(self.window, EvidenceWindow):
            raise ValueError("Series requires EvidenceWindow")
        if not isinstance(self.observations, tuple):
            raise ValueError("Series observations must be an immutable tuple")
        if self.expected_interval is not None:
            if not isinstance(self.expected_interval, timedelta) or self.expected_interval <= timedelta(0):
                raise ValueError("Expected sampling interval must be a positive timedelta")
        previous = None
        for point in self.observations:
            if not isinstance(point, PriceObservation):
                raise ValueError("Series elements must be PriceObservation")
            if (point.subject, point.kind, point.currency, point.price_basis) != (self.subject, self.kind, self.currency, self.price_basis):
                raise ValueError("Series cannot mix subjects, kinds, currencies or bases")
            instant = _instant(point.observed_at)
            if not _instant(self.window.start) <= instant < _instant(self.window.end):
                raise ValueError("Price observation outside series window")
            if previous is not None and instant <= previous:
                raise ValueError("Series requires unique increasing observation instants")
            previous = instant
