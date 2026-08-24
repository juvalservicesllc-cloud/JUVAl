"""Pure aggregation helpers shared by the record-snapshot store adapters.

SQLite and Postgres speak different SQL dialects, so each adapter writes its
own queries -- but the arithmetic applied to the rows those queries return is
one behavior, not two. Keeping it here stops the same money math from drifting
between `infrastructure/logging/` and `infrastructure/persistence/`.

Framework-free and I/O-free on purpose: these functions take already-fetched
rows and return JSON-safe dicts. Decimal is used for every monetary/ratio
computation (never float), and a missing or unparseable value is skipped --
never coerced to zero (ADR-004).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional, Sequence

LARGEST_SPREAD_LIMIT = 5
BRAND_LIMIT = 10


def _decimal(raw: Any) -> Optional[Decimal]:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def numeric_summary(raw_values: Iterable[Any]) -> dict[str, Any]:
    """count/sum/average/min/max over the usable values only.

    `count` is the number of values that actually participated. When nothing
    participated every statistic is `None` -- never `0`, which would read as a
    real measurement of zero.
    """

    values = [value for value in map(_decimal, raw_values) if value is not None]
    if not values:
        return {"count": 0, "sum": None, "average": None, "minimum": None, "maximum": None}
    return {
        "count": len(values),
        "sum": str(sum(values)),
        "average": str(sum(values) / len(values)),
        "minimum": str(min(values)),
        "maximum": str(max(values)),
    }


def price_spread(rows: Sequence[tuple[Any, Any, Any, Any]]) -> dict[str, Any]:
    """Sourcing spread per record: selling price minus cost of goods.

    `rows` are `(record_ref, title, selling_price, cog)` for records whose
    selling price is VERIFIED and whose COG was recorded -- the caller's query
    enforces that, so no record with an unusable price is ever given an
    implied one here.

    This is the canonical production equivalent of the previous experience's
    "supplier price discount": production has no supplier *suggested retail*
    column, so the spread is measured against the selling price actually used
    by the Profitability Engine. `at_or_below_cog` counts records where the
    spread is not positive -- the sourcing red flag the old chart surfaced.
    """

    entries: list[dict[str, Any]] = []
    for record_ref, title, raw_price, raw_cog in rows:
        price, cog = _decimal(raw_price), _decimal(raw_cog)
        if price is None or cog is None:
            continue
        amount = price - cog
        entries.append(
            {
                "record_ref": record_ref,
                "title": title,
                "amount": str(amount),
                "percent": str(amount / price) if price > 0 else None,
            }
        )

    if not entries:
        return {"count": 0, "average_amount": None, "at_or_below_cog": 0, "largest": []}

    amounts = [Decimal(entry["amount"]) for entry in entries]
    largest = sorted(entries, key=lambda entry: (-Decimal(entry["amount"]), str(entry["record_ref"])))
    return {
        "count": len(entries),
        "average_amount": str(sum(amounts) / len(amounts)),
        "at_or_below_cog": sum(1 for amount in amounts if amount <= 0),
        "largest": largest[:LARGEST_SPREAD_LIMIT],
    }


def brand_distribution(rows: Sequence[tuple[Any, int]]) -> dict[str, Any]:
    """`rows` are `(brand_value, count)`; a NULL brand is reported as its own
    `not_recorded` count instead of being folded into a named brand."""

    named = [(str(brand), int(count)) for brand, count in rows if brand is not None]
    not_recorded = sum(int(count) for brand, count in rows if brand is None)
    named.sort(key=lambda item: (-item[1], item[0]))
    return {
        "items": [{"label": brand, "count": count} for brand, count in named[:BRAND_LIMIT]],
        "distinct": len(named),
        "not_recorded": not_recorded,
    }


def issue_types(rows: Sequence[tuple[Any, int]]) -> list[dict[str, Any]]:
    """`rows` are `(issue_code, count)` straight from the persisted codes."""

    counted = [(str(code), int(count)) for code, count in rows if code is not None]
    counted.sort(key=lambda item: (-item[1], item[0]))
    return [{"code": code, "count": count} for code, count in counted]
