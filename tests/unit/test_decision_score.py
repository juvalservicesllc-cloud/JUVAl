from datetime import datetime, timezone
from decimal import Decimal

import pytest

from juval.domain.provenance import FieldValue, SourceType, VerificationStatus
from juval.processing.decision_score import ScoreComponents, ScoreWeights, compute_decision_score

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _weights(**overrides):
    defaults = dict(
        profitability=Decimal("0.3"),
        demand=Decimal("0.2"),
        competition=Decimal("0.15"),
        price_stability=Decimal("0.1"),
        risk=Decimal("0.15"),
        operational_complexity=Decimal("0.1"),
    )
    defaults.update(overrides)
    return ScoreWeights(**defaults)


def _verified(value):
    return FieldValue.verified(Decimal(value), source="s", method="m", retrieved_at=NOW)


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        _weights(profitability=Decimal("0.9"))


def test_weights_reject_out_of_range():
    with pytest.raises(ValueError):
        _weights(profitability=Decimal("1.5"), demand=Decimal("-0.5"))


def test_full_components_produce_verified_score():
    components = ScoreComponents(
        profitability=_verified(80),
        demand=_verified(70),
        competition=_verified(60),
        price_stability=_verified(90),
        risk=_verified(100),
        operational_complexity=_verified(50),
    )
    result = compute_decision_score(components, _weights(), now=NOW)
    expected = (
        Decimal("80") * Decimal("0.3")
        + Decimal("70") * Decimal("0.2")
        + Decimal("60") * Decimal("0.15")
        + Decimal("90") * Decimal("0.1")
        + Decimal("100") * Decimal("0.15")
        + Decimal("50") * Decimal("0.1")
    )
    assert result.score.value == expected
    assert result.score.status == VerificationStatus.VERIFIED


@pytest.mark.parametrize("name", list(ScoreComponents.__dataclass_fields__))
@pytest.mark.parametrize("state", ["absent", "not_found", "invalid"])
@pytest.mark.parametrize("zero_weight", [False, True])
def test_missing_component_yields_not_found_score(name, state, zero_weight):
    from dataclasses import replace

    components = ScoreComponents(
        profitability=_verified(80),
        demand=_verified(70),
        competition=_verified(60),
        price_stability=_verified(90),
        risk=_verified(100),
        operational_complexity=_verified(50),
    )
    missing = None
    if state == "not_found":
        missing = FieldValue.not_found(
            source="s", method="missing", retrieved_at=NOW,
        )
    elif state == "invalid":
        missing = FieldValue.invalid(
            "bad", source="s", method="invalid", retrieved_at=NOW,
            source_type=SourceType.SUPPLIER_FILE,
        )
    components = replace(components, **{name: missing})
    weights = _weights()
    if zero_weight:
        other = "demand" if name == "profitability" else "profitability"
        weights = replace(weights, **{
            name: Decimal("0"),
            other: getattr(weights, other) + getattr(weights, name),
        })
    result = compute_decision_score(components, weights, now=NOW)
    assert result.score.status == VerificationStatus.NOT_FOUND
    assert result.score.value is None
    assert result.components is components


def test_component_out_of_range_rejected():
    with pytest.raises(ValueError):
        ScoreComponents(profitability=_verified(150))


def test_any_inferred_component_makes_score_inferred():
    components = ScoreComponents(
        profitability=FieldValue.inferred(Decimal("80"), source="s", method="m", retrieved_at=NOW),
        demand=_verified(70),
        competition=_verified(60),
        price_stability=_verified(90),
        risk=_verified(100),
        operational_complexity=_verified(50),
    )
    result = compute_decision_score(components, _weights(), now=NOW)
    assert result.score.status == VerificationStatus.INFERRED
    assert result.score.value == Decimal('76')
    assert result.components.profitability is components.profitability
    assert result.components.profitability.status == VerificationStatus.INFERRED
