"""Synthetic fixtures only: no market/provider evidence or commercial calibration."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal

import pytest

from juval.domain.market_evidence import (
    AmazonPresenceObservation, AmazonPresenceScope, CompetitionCount,
    CountPopulation, DemandMetric, DemandObservation, EvidenceWindow,
    FulfillmentScope, PriceKind, PriceObservation, PriceSeries,
)
from juval.domain.product import Identification, Product
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus

NOW = datetime(2026, 1, 2, tzinfo=timezone.utc)
START = NOW - timedelta(days=1)
WINDOW = EvidenceWindow(START, NOW)
SCOPE = "synthetic listing, new condition, declared marketplace, all offers"
BASIS = "synthetic new item offer, shipping included, taxes excluded"


def fv(value, unit=None, status=VerificationStatus.INFERRED, retrieved_at=NOW):
    common = dict(source="synthetic-fixture", method="explicit synthetic observation",
                  retrieved_at=retrieved_at, source_type=SourceType.USER_INPUT,
                  evidence="test fixture, not live data", source_reference="fixture:1")
    if status == VerificationStatus.NOT_FOUND:
        return FieldValue.not_found(**common)
    if status == VerificationStatus.INVALID:
        return FieldValue.invalid(value, **common)
    build = FieldValue.verified if status == VerificationStatus.VERIFIED else FieldValue.inferred
    return build(value, unit=unit, **common)


SUBJECT = Identification(fv("B000000001", status=VerificationStatus.VERIFIED), "US")


def demand(metric=DemandMetric.ESTIMATED_SALES, value=None, **overrides):
    data = dict(subject=SUBJECT, metric=metric, value=fv(0, "units") if value is None else value,
                observed_at=NOW, population_definition=SCOPE,
                window=None if metric == DemandMetric.CURRENT_BSR else WINDOW,
                rank_category="synthetic category")
    data.update(overrides)
    return DemandObservation(**data)


def count(value=None, **overrides):
    data = dict(subject=SUBJECT, value=fv(0, "offers") if value is None else value,
                observed_at=NOW, population=CountPopulation.OFFERS,
                fulfillment=FulfillmentScope.ALL, eligible_only=False, population_definition=SCOPE)
    data.update(overrides)
    return CompetitionCount(**data)


def presence(value=None, **overrides):
    data = dict(subject=SUBJECT, value=fv(False) if value is None else value,
                observed_at=NOW, scope=AmazonPresenceScope.BUY_BOX, population_definition=SCOPE)
    data.update(overrides)
    return AmazonPresenceObservation(**data)


def price(value=None, **overrides):
    data = dict(subject=SUBJECT, amount=fv(Decimal("0"), "USD") if value is None else value,
                observed_at=START, kind=PriceKind.SUPPLIER_QUOTE, currency="USD", price_basis=BASIS)
    data.update(overrides)
    return PriceObservation(**data)


def series(points=(), **overrides):
    data = dict(subject=SUBJECT, kind=PriceKind.SUPPLIER_QUOTE, currency="USD",
                price_basis=BASIS, window=WINDOW, observations=points)
    data.update(overrides)
    return PriceSeries(**data)


@pytest.mark.parametrize("start,end", [(NOW, NOW), (NOW, START), (START.replace(tzinfo=None), NOW)])
def test_window_rejects_nonpositive_or_naive_intervals(start, end):
    with pytest.raises(ValueError):
        EvidenceWindow(start, end)


def test_time_comparison_uses_instants_and_preserves_original_timestamps():
    offset = timezone(timedelta(hours=2))
    same_now = NOW.astimezone(offset)
    observation = demand(observed_at=same_now)
    assert observation.observed_at is same_now
    assert observation.value.provenance.retrieved_at == NOW
    with pytest.raises(ValueError):
        EvidenceWindow(NOW, same_now)
    with pytest.raises(ValueError):
        series((price(), price(observed_at=START.astimezone(offset))))


class NoOffset(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize("builder", [demand, count, presence, price])
@pytest.mark.parametrize("observed", [NOW.replace(tzinfo=None), NOW.replace(tzinfo=NoOffset()),
                                     NOW + timedelta(seconds=1), None])
def test_observation_requires_known_aware_time_not_after_retrieval(builder, observed):
    with pytest.raises(ValueError):
        builder(observed_at=observed)


def test_retrieval_requires_effective_offset_even_if_legacy_provenance_accepts_tzinfo():
    value = fv(Decimal("1"), "USD", retrieved_at=NOW.replace(tzinfo=NoOffset()))
    with pytest.raises(ValueError):
        price(value)


@pytest.mark.parametrize("metric,value,unit", [
    (DemandMetric.ESTIMATED_SALES, 0, "units"),
    (DemandMetric.SALES_VELOCITY, Decimal("0.25"), "units/day"),
    (DemandMetric.CURRENT_BSR, 1, "rank"),
    (DemandMetric.AVERAGE_BSR, Decimal("1.5"), "rank"),
    (DemandMetric.RANK_DROPS, 0, "drops"),
])
def test_demand_canonical_values_and_invalid_type_unit_range(metric, value, unit):
    evidence = fv(value, unit)
    assert demand(metric, evidence).value is evidence
    for invalid in (fv(value, "wrong"), fv(-1, unit), fv(True, unit), fv(float(value), unit)):
        with pytest.raises(ValueError):
            demand(metric, invalid)


@pytest.mark.parametrize("metric,value", [(DemandMetric.CURRENT_BSR, 0),
                                         (DemandMetric.AVERAGE_BSR, Decimal("0"))])
def test_rank_starts_at_one(metric, value):
    with pytest.raises(ValueError):
        demand(metric, fv(value, "rank"))


def test_estimated_sales_cannot_be_presented_as_verified_observed_sales():
    with pytest.raises(ValueError):
        demand(value=fv(10, "units", VerificationStatus.VERIFIED))
    assert demand().value.status == VerificationStatus.INFERRED


@pytest.mark.parametrize("metric", [DemandMetric.ESTIMATED_SALES, DemandMetric.SALES_VELOCITY,
                                    DemandMetric.AVERAGE_BSR, DemandMetric.RANK_DROPS])
def test_aggregate_requires_completed_window_even_when_value_unavailable(metric):
    missing = fv(None, status=VerificationStatus.NOT_FOUND)
    for window in (None, "window", EvidenceWindow(START, NOW + timedelta(seconds=1))):
        with pytest.raises(ValueError):
            demand(metric, missing, window=window)
    assert demand(metric, missing).window is WINDOW


@pytest.mark.parametrize("metric", [DemandMetric.CURRENT_BSR, DemandMetric.AVERAGE_BSR, DemandMetric.RANK_DROPS])
@pytest.mark.parametrize("category", [None, "", " "])
def test_rank_category_required(metric, category):
    with pytest.raises(ValueError):
        demand(metric, fv(None, status=VerificationStatus.NOT_FOUND), rank_category=category)


def test_current_bsr_cannot_carry_aggregate_window():
    with pytest.raises(ValueError):
        demand(DemandMetric.CURRENT_BSR, fv(1, "rank"), window=WINDOW)


@pytest.mark.parametrize("population,unit", [(CountPopulation.OFFERS, "offers"),
                                           (CountPopulation.DISTINCT_SELLERS, "sellers")])
@pytest.mark.parametrize("fulfillment", list(FulfillmentScope))
@pytest.mark.parametrize("eligible", [False, True])
def test_count_populations_filters_and_observed_zero(population, unit, fulfillment, eligible):
    evidence = fv(0, unit, VerificationStatus.VERIFIED)
    observation = count(evidence, population=population, fulfillment=fulfillment, eligible_only=eligible)
    assert observation.value is evidence
    assert observation.eligible_only is eligible
    assert observation.value.value == 0
    with pytest.raises(ValueError):
        count(fv(0, "sellers" if unit == "offers" else "offers"), population=population)


@pytest.mark.parametrize("value", [-1, True, Decimal("1"), 1.5])
def test_count_rejects_wrong_type_or_range(value):
    with pytest.raises(ValueError):
        count(fv(value, "offers"))


@pytest.mark.parametrize("scope", list(AmazonPresenceScope))
@pytest.mark.parametrize("observed", [True, False])
def test_presence_requires_actual_boolean_and_preserves_scope(scope, observed):
    evidence = fv(observed, status=VerificationStatus.VERIFIED)
    result = presence(evidence, scope=scope)
    assert result.value is evidence
    assert result.scope is scope


@pytest.mark.parametrize("value", [0, 1, "false", Decimal("0")])
def test_presence_rejects_non_boolean(value):
    with pytest.raises(ValueError):
        presence(fv(value))


@pytest.mark.parametrize("builder,kwargs", [
    (demand, {"metric": "ESTIMATED_SALES"}), (count, {"population": "OFFERS"}),
    (count, {"fulfillment": "ALL"}), (count, {"eligible_only": 0}),
    (presence, {"scope": "BUY_BOX"}), (price, {"kind": "BUY_BOX"}),
    (series, {"kind": "BUY_BOX"}),
])
def test_enums_and_boolean_filters_are_explicit(builder, kwargs):
    with pytest.raises(ValueError):
        builder(**kwargs)


@pytest.mark.parametrize("builder,field", [(demand, "population_definition"), (count, "population_definition"),
                                          (presence, "population_definition"), (price, "price_basis"),
                                          (series, "price_basis")])
@pytest.mark.parametrize("text", [None, "", " \t"])
def test_required_scope_text(builder, field, text):
    with pytest.raises(ValueError):
        builder(**{field: text})


@pytest.mark.parametrize("currency", [None, "usd", "US", "USDD", "U1D", "ÜSD", " USD"])
@pytest.mark.parametrize("builder", [price, series])
def test_currency_format_is_explicit(builder, currency):
    with pytest.raises(ValueError):
        builder(currency=currency)


@pytest.mark.parametrize("kind", list(PriceKind))
def test_price_kinds_do_not_reclassify_supplier_quotes(kind):
    point = price(kind=kind)
    assert point.kind is kind
    assert point.amount.value == Decimal("0")


@pytest.mark.parametrize("value", [Decimal("-1"), 1, True, 1.5,
                                   Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_price_rejects_invalid_amounts(value):
    with pytest.raises(ValueError):
        price(fv(value, "USD"))


@pytest.mark.parametrize("metric,unit", [(DemandMetric.SALES_VELOCITY, "units/day"),
                                        (DemandMetric.AVERAGE_BSR, "rank")])
@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_demand_decimal_must_be_finite(metric, unit, value):
    with pytest.raises(ValueError):
        demand(metric, fv(Decimal(value), unit))


def test_price_unit_must_match_currency_without_conversion():
    with pytest.raises(ValueError):
        price(fv(Decimal("10"), "EUR"))


@pytest.mark.parametrize("status", list(VerificationStatus))
@pytest.mark.parametrize("builder,raw,unit", [(count, 0, "offers"), (presence, False, None),
                                           (price, Decimal("0"), "USD")])
def test_field_identity_provenance_and_diagnostics_are_preserved(status, builder, raw, unit):
    evidence = fv(raw, unit, status)
    observation = builder(evidence)
    stored = observation.amount if isinstance(observation, PriceObservation) else observation.value
    assert stored is evidence
    assert stored.provenance is evidence.provenance
    assert stored.status == status
    if status in (VerificationStatus.NOT_FOUND, VerificationStatus.INVALID):
        assert stored.value is None
    if status == VerificationStatus.INVALID:
        assert stored.raw_value == raw


@pytest.mark.parametrize("metric", list(DemandMetric))
@pytest.mark.parametrize("status", [VerificationStatus.NOT_FOUND, VerificationStatus.INVALID])
def test_unavailable_demand_retains_raw_diagnostics(metric, status):
    evidence = fv({"raw": "unparseable"}, status=status)
    assert demand(metric, evidence).value is evidence
    assert evidence.value is None


def test_invalid_field_with_nonempty_value_is_not_accepted_as_evidence():
    invalid = replace(fv("bad", status=VerificationStatus.INVALID), value=Decimal("1"))
    with pytest.raises(ValueError):
        price(invalid)


def test_series_empty_single_and_gapped_samples_do_not_fill_coverage():
    empty = series()
    assert empty.observations == ()
    first, last = price(), price(observed_at=NOW - timedelta(seconds=1))
    single = series((first,))
    assert single.observations == (first,)
    points = (first, last)
    sparse = series(points, expected_interval=timedelta(minutes=1))
    assert sparse.observations is points
    assert len(sparse.observations) == 2
    with pytest.raises(FrozenInstanceError):
        sparse.window = EvidenceWindow(START, NOW + timedelta(days=1))


@pytest.mark.parametrize("time", [START - timedelta(microseconds=1), NOW])
def test_series_half_open_boundaries(time):
    with pytest.raises(ValueError):
        series((price(observed_at=time),))
    assert series((price(observed_at=START),)).observations[0].observed_at == START


def test_series_rejects_duplicate_and_descending_timestamps():
    first, second = price(), price(observed_at=START + timedelta(hours=1))
    for points in ((first, first), (second, first)):
        with pytest.raises(ValueError):
            series(points)


@pytest.mark.parametrize("change", [
    {"subject": replace(SUBJECT, marketplace="CA")},
    {"kind": PriceKind.BUY_BOX}, {"price_basis": "different tax basis"},
    {"currency": "EUR", "amount": fv(Decimal("0"), "EUR")},
])
def test_series_rejects_mixed_context(change):
    with pytest.raises(ValueError):
        series((replace(price(), **change),))


@pytest.mark.parametrize("interval", [timedelta(0), timedelta(seconds=-1), 60, "daily"])
def test_expected_interval_must_be_positive_timedelta(interval):
    with pytest.raises(ValueError):
        series(expected_interval=interval)


@pytest.mark.parametrize("points", [[], [price()], (None,)])
def test_series_requires_tuple_of_observations(points):
    with pytest.raises(ValueError):
        series(points)


@pytest.mark.parametrize("builder", [demand, count, presence, price, series])
def test_subject_reuses_identification_without_new_identity_type(builder):
    assert builder().subject is SUBJECT
    with pytest.raises(ValueError):
        builder(subject="B000000001")


def test_observations_do_not_project_into_legacy_or_create_scoring_results():
    product = Product(SUBJECT)
    observation = demand()
    assert observation.subject is product.identification
    assert product.demand.estimated_monthly_sales is None
    assert product.competition.total_offers is None
    assert product.price.current_buy_box is None
    with pytest.raises(FrozenInstanceError):
        observation.value = fv(100, "units")
