"""Declared demand capture from one file row (ADR-052 §3, amendment to ADR-046).

Reads only the `demand_*` columns and returns evidence for
`SourcingRecord.market_evidence`. It never touches `Product.demand`, never
produces a decision input, and never completes a declaration: a missing or
ambiguous window, instant, zone, population or method leaves no usable value,
only a diagnostic carrying the raw cell. The value is a strict non-negative
integer -- nothing is truncated or rounded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from juval.domain.declared_demand import DeclaredDemandCapture, DeclaredObservation, DemandDiagnostic
from juval.domain.market_evidence import DemandMetric, DemandObservation, EvidenceWindow
from juval.domain.product import Identification
from juval.domain.provenance import FieldValue, SourceType

EVIDENCE_TEXT = "declared in uploaded file; author not accredited; not verified"
EMPTY_TEXT = "declared demand column present; value cell empty"
MAX_TEXT = 500
_OFFSET = re.compile(r"^(?:UTC)?([+-])(\d{2}):(\d{2})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DIGITS = re.compile(r"^\d+$")


class _Failure(Exception):
    def __init__(self, code: str, message: str, column: Optional[str], raw: Any) -> None:
        super().__init__(message)
        self.diagnostic = (code, message, column, raw)


@dataclass(frozen=True)
class _Context:
    window: EvidenceWindow
    observed_at: datetime
    population: str
    method: str
    window_source: str
    declared_month: Optional[str]
    declared_timezone: Optional[str]


def _blank(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def _text_of(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, (datetime, date)):
        return raw.isoformat()
    return str(raw)


def parse_estimated_sales(raw: Any) -> tuple[Optional[int], bool]:
    """(value, valid): (None, True) blank; (int, True) valid; (None, False) invalid."""
    if _blank(raw):
        return None, True
    if isinstance(raw, bool):
        return None, False
    if isinstance(raw, int):
        return (raw, True) if raw >= 0 else (None, False)
    if isinstance(raw, float):
        return (int(raw), True) if raw.is_integer() and raw >= 0 else (None, False)
    if isinstance(raw, Decimal):
        return (int(raw), True) if raw.is_finite() and raw == raw.to_integral_value() and raw >= 0 else (None, False)
    text = str(raw).strip()
    return (int(text), True) if _DIGITS.match(text) else (None, False)


def parse_timezone(raw: str) -> tzinfo:
    text = raw.strip()
    match = _OFFSET.match(text)
    if match:
        sign, hours, minutes = match.groups()
        delta = timedelta(hours=int(hours), minutes=int(minutes))
        if delta >= timedelta(hours=24):
            raise ValueError(text)
        return timezone(delta if sign == "+" else -delta)
    if text.upper() == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(text) from error


def localize(naive: datetime, zone: tzinfo) -> datetime:
    """Attach `zone` to a wall-clock time, refusing DST gaps and folds."""
    first, second = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        back = first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        raise ValueError("nonexistent" if back != naive else "ambiguous")
    return first


class _Row:
    def __init__(self, cells: dict[str, Any], headers: dict[str, str], row_number: int) -> None:
        self.cells, self.headers, self.row = cells, headers, row_number

    def raw(self, canonical: str) -> Any:
        return self.cells.get(canonical)

    def present(self, canonical: str) -> bool:
        return canonical in self.headers and not _blank(self.cells.get(canonical))

    def column(self, canonical: str) -> Optional[str]:
        return self.headers.get(canonical)

    def fail(self, code: str, message: str, canonical: Optional[str]) -> _Failure:
        return _Failure(code, message, self.column(canonical) if canonical else None,
                        _text_of(self.raw(canonical)) if canonical else None)

    def zone(self) -> Optional[tzinfo]:
        if not self.present("demand_timezone"):
            return None
        try:
            return parse_timezone(str(self.raw("demand_timezone")))
        except ValueError:
            raise self.fail("DEMAND_TIMEZONE_INVALID", "demand_timezone is not an IANA zone, UTC or a ±HH:MM offset",
                            "demand_timezone") from None

    def instant(self, canonical: str, zone: Optional[tzinfo]) -> datetime:
        raw = self.raw(canonical)
        if isinstance(raw, datetime):
            value = raw
        elif isinstance(raw, date):
            value = datetime(raw.year, raw.month, raw.day)
        else:
            try:
                value = datetime.fromisoformat(str(raw).strip())
            except ValueError:
                raise self.fail("DEMAND_CONTEXT_INVALID", f"{canonical} is not an ISO 8601 date-time", canonical) from None
        if value.tzinfo is not None and value.utcoffset() is not None:
            # An instant with its own offset is unambiguous; a declared zone must agree with it there.
            if zone is not None and value.astimezone(zone).utcoffset() != value.utcoffset():
                raise self.fail("DEMAND_TIMEZONE_CONFLICT", f"{canonical} offset disagrees with demand_timezone", canonical)
            return value
        if zone is None:
            raise self.fail("DEMAND_TIME_NAIVE", f"{canonical} has no time zone and demand_timezone is not declared", canonical)
        try:
            return localize(value, zone)
        except ValueError as error:
            code = "DEMAND_TIME_NONEXISTENT" if str(error) == "nonexistent" else "DEMAND_TIME_AMBIGUOUS"
            raise self.fail(code, f"{canonical} is {error} local time in demand_timezone; no offset is chosen", canonical) from None

    def text(self, canonical: str, label: str) -> str:
        if not self.present(canonical):
            raise self.fail("DEMAND_CONTEXT_MISSING", f"{label} not declared", canonical)
        value = str(self.raw(canonical)).strip()
        if len(value) > MAX_TEXT:
            raise self.fail("DEMAND_CONTEXT_INVALID", f"{label} exceeds {MAX_TEXT} characters", canonical)
        return value


def _month_window(row: _Row, zone: Optional[tzinfo]) -> tuple[EvidenceWindow, str]:
    text = str(row.raw("demand_month")).strip() if isinstance(row.raw("demand_month"), str) else None
    match = _MONTH.match(text) if text else None
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise row.fail("DEMAND_CONTEXT_INVALID", "demand_month must be text AAAA-MM", "demand_month")
    if zone is None:
        raise row.fail("DEMAND_CONTEXT_MISSING", "demand_month requires demand_timezone", "demand_timezone")
    year, month = int(match.group(1)), int(match.group(2))
    following = (year + 1, 1) if month == 12 else (year, month + 1)
    try:
        start = localize(datetime(year, month, 1), zone)
        end = localize(datetime(*following, 1), zone)
    except ValueError as error:
        code = "DEMAND_TIME_NONEXISTENT" if str(error) == "nonexistent" else "DEMAND_TIME_AMBIGUOUS"
        raise row.fail(code, f"the month boundary is {error} local time in demand_timezone", "demand_month") from None
    return EvidenceWindow(start, end), text


def _context(row: _Row, captured_at: datetime) -> _Context:
    zone = row.zone()
    explicit = row.present("demand_window_start") or row.present("demand_window_end")
    if row.present("demand_month"):
        if explicit:
            raise row.fail("DEMAND_WINDOW_CONFLICT", "demand_month and an explicit window are both declared", "demand_month")
        window, month = _month_window(row, zone)
        source = "DECLARED_MONTH"
    else:
        for canonical in ("demand_window_start", "demand_window_end"):
            if not row.present(canonical):
                raise row.fail("DEMAND_CONTEXT_MISSING", f"{canonical} not declared; never substituted", canonical)
        start, end = row.instant("demand_window_start", zone), row.instant("demand_window_end", zone)
        if start >= end:
            raise row.fail("DEMAND_CONTEXT_INVALID", "demand_window_start must precede demand_window_end", "demand_window_end")
        window, month, source = EvidenceWindow(start, end), None, "EXPLICIT"
    if not row.present("demand_observed_at"):
        raise row.fail("DEMAND_CONTEXT_MISSING", "demand_observed_at not declared; the import time never substitutes for it",
                       "demand_observed_at")
    observed_at = row.instant("demand_observed_at", zone)
    if window.end > observed_at:
        raise row.fail("DEMAND_CONTEXT_INVALID", "the window must end no later than demand_observed_at", "demand_observed_at")
    if observed_at > captured_at:
        raise row.fail("DEMAND_CONTEXT_INVALID", "demand_observed_at is after the import instant", "demand_observed_at")
    population = row.text("demand_population", "demand_population")
    method = row.text("demand_method", "demand_method")
    declared_zone = str(row.raw("demand_timezone")).strip() if row.present("demand_timezone") else None
    return _Context(window, observed_at, population, method, source, month, declared_zone)


def capture_declared_demand(
    cells: dict[str, Any], headers: dict[str, str], *, subject: Identification, record_ref: str,
    row_number: int, source: str, captured_at: datetime,
) -> DeclaredDemandCapture:
    """One record's declared demand. `headers` maps demand canonicals present
    in the file to their original header text (for `source_reference`)."""
    row = _Row(cells, headers, row_number)
    diagnostics: list[DemandDiagnostic] = []

    def note(code: str, message: str, column: Optional[str], raw: Any) -> None:
        diagnostics.append(DemandDiagnostic(code=code, message=message, row=row_number, column=column, raw_value=_text_of(raw)))

    value_column = headers.get("demand_estimated_sales")
    raw_value = cells.get("demand_estimated_sales")
    value, valid = parse_estimated_sales(raw_value)
    empty = value is None and valid
    if not valid:
        note("DEMAND_VALUE_INVALID", "estimated sales must be a whole number >= 0; kept as raw", value_column, raw_value)

    try:
        context: Optional[_Context] = _context(row, captured_at)
    except _Failure as failure:
        context = None
        code, message, column, raw = failure.diagnostic
        if empty and code == "DEMAND_CONTEXT_MISSING":
            note("DEMAND_VALUE_EMPTY", "no estimated sales declared for this row", value_column, None)
        else:
            if empty:
                note("DEMAND_VALUE_EMPTY", "no estimated sales declared for this row", value_column, None)
            elif valid:
                note("DEMAND_VALUE_NOT_USABLE", "declared value kept as raw; its context is incomplete or invalid",
                     value_column, raw_value)
            diagnostics.append(DemandDiagnostic(code=code, message=message, row=row_number, column=column, raw_value=raw))

    observations: tuple[DeclaredObservation, ...] = ()
    if context is not None:
        reference = f"row={row_number};column={value_column}" if value_column else f"row={row_number}"
        common = dict(source=source, method=context.method, retrieved_at=captured_at,
                      source_type=SourceType.USER_INPUT, source_reference=reference)
        if empty:
            field = FieldValue.not_found(evidence=EMPTY_TEXT, **common)
        elif valid:
            field = FieldValue.inferred(value, unit="units", evidence=EVIDENCE_TEXT, **common)
        else:
            field = FieldValue.invalid(raw_value=_text_of(raw_value), evidence=EVIDENCE_TEXT, **common)
        try:
            observation = DemandObservation(
                subject=subject, metric=DemandMetric.ESTIMATED_SALES, value=field, observed_at=context.observed_at,
                population_definition=context.population, window=context.window,
            )
            observations = (DeclaredObservation(
                observation_id=f"{record_ref}#ESTIMATED_SALES#1", observation=observation,
                window_source=context.window_source, declared_month=context.declared_month,
                declared_timezone=context.declared_timezone,
            ),)
        except ValueError as error:   # the ADR-046 contract refuses it: keep the reason, never repair
            note("DEMAND_CONTEXT_INVALID", f"declaration refused by the ADR-046 contract: {error}", value_column, raw_value)

    return DeclaredDemandCapture(captured_at=captured_at, observations=observations, diagnostics=tuple(diagnostics))
