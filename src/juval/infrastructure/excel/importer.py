"""Excel Importer — Fase 2 vertical slice.

Excel Input -> Parse -> Normalize -> Validate -> Build SourcingRecord

Headers are matched by name (via `column_mapping.py`), never by position.
Every value is either accepted (VERIFIED, since it came straight from the
supplier's file), left absent (NOT_FOUND for a blank cell in a present
column), or flagged (INVALID, with the raw cell value preserved) — nothing
is ever silently defaulted to zero or guessed. See
docs/architecture/EXCEL_PROCESSING.md for the full column-by-column
contract this module implements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import openpyxl

from juval.domain.costs import CostInputs
from juval.domain.identifiers import is_valid_asin, is_valid_upc
from juval.domain.issues import IssueLevel, ProcessingIssue
from juval.domain.product import (
    Dimensions,
    Identification,
    Price,
    Product,
    ProductInfo,
    SellingPriceSource,
)
from juval.domain.provenance import FieldValue, SourceType, VerificationStatus
from juval.domain.risk import RiskFlag, RiskProfile, RiskStatus, RiskType, Severity
from juval.domain.sourcing_record import SourcingRecord
from juval.domain.units import CANONICAL_LENGTH_UNIT, CANONICAL_WEIGHT_UNIT, UnsupportedUnitError, to_inches, to_pounds

from .column_mapping import ALIAS_TO_CANONICAL, COLUMN_SPECS

# Provisional: a supplier declaring a risk PRESENT does not tell us its
# severity, so the importer must assign one to build a valid RiskFlag.
# This mapping is a placeholder classification, not a commercial threshold —
# it has NOT been reviewed/approved by the business. See ADR-010.
#
# Only RiskTypes listed here may be looked up by _build_risk_flag() — a
# RiskType with no entry raises KeyError (fail-closed) instead of falling
# back to a guessed severity. See ADR-015.
DEFAULT_RISK_SEVERITY: dict[RiskType, Severity] = {
    RiskType.HAZMAT: Severity.HIGH,
    RiskType.BULKY: Severity.MEDIUM,
}


@dataclass(frozen=True)
class ImportResult:
    records: tuple[SourcingRecord, ...]
    issues: tuple[ProcessingIssue, ...]
    fatal: bool
    rows_scanned: int
    rows_skipped_blank: int


def normalize_header(raw: Any) -> str:
    text = "" if raw is None else str(raw).strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _resolve_headers(normalized_headers: list[str]) -> tuple[dict[str, int], list[ProcessingIssue]]:
    issues: list[ProcessingIssue] = []
    column_index: dict[str, int] = {}
    seen: set[str] = set()
    for idx, header in enumerate(normalized_headers):
        if not header:
            continue
        canonical = ALIAS_TO_CANONICAL.get(header)
        if canonical is None:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.WARNING,
                    code="UNKNOWN_COLUMN",
                    message=f"Column {header!r} is not recognized and will be ignored.",
                    field=header,
                )
            )
            continue
        if canonical in seen:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.WARNING,
                    code="DUPLICATE_COLUMN",
                    message=f"Column {canonical!r} appears more than once; using the first occurrence.",
                    field=canonical,
                )
            )
            continue
        column_index[canonical] = idx
        seen.add(canonical)

    for spec in COLUMN_SPECS:
        if spec.required and spec.canonical not in column_index:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.FATAL,
                    code="MISSING_REQUIRED_COLUMN",
                    message=f"Required column {spec.canonical!r} ({spec.target}) is missing from the input file.",
                    field=spec.canonical,
                )
            )
    return column_index, issues


def _parse_cell(raw: Any, value_type: str) -> tuple[Optional[Any], bool]:
    """Returns (parsed_value, is_valid). (None, True) means the cell was
    blank — absent, not an error. (raw_text, False) means present but
    unparseable for `value_type`; the caller preserves it as raw_value."""

    if raw is None:
        return None, True
    text = str(raw).strip()
    if text == "":
        return None, True

    if value_type == "str":
        return text, True
    if value_type in ("asin", "upc"):
        candidate = text.upper() if value_type == "asin" else re.sub(r"[\s-]", "", text)
        validator = is_valid_asin if value_type == "asin" else is_valid_upc
        return candidate, validator(candidate)
    if value_type == "decimal":
        try:
            return Decimal(text), True
        except InvalidOperation:
            return text, False
    if value_type == "int":
        try:
            return int(Decimal(text)), True
        except (InvalidOperation, ValueError):
            return text, False
    if value_type == "bool":
        lowered = text.lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True, True
        if lowered in {"false", "0", "no", "n"}:
            return False, True
        return text, False
    raise AssertionError(f"unknown value_type: {value_type!r}")


def _field_value(
    raw: Any,
    value_type: str,
    *,
    source: str,
    method: str,
    retrieved_at: datetime,
    source_reference: str,
    unit: Optional[str] = None,
) -> FieldValue:
    value, is_valid = _parse_cell(raw, value_type)
    if value is None:
        return FieldValue.not_found(
            source=source, method=method, retrieved_at=retrieved_at,
            source_type=SourceType.NOT_FOUND, source_reference=source_reference,
        )
    if not is_valid:
        return FieldValue.invalid(
            value, source=source, method=method, retrieved_at=retrieved_at,
            source_type=SourceType.SUPPLIER_FILE, source_reference=source_reference,
        )
    return FieldValue.verified(
        value, source=source, method=method, retrieved_at=retrieved_at,
        source_type=SourceType.SUPPLIER_FILE, unit=unit, source_reference=source_reference,
    )


def _optional_field_value(
    cells: dict[str, Any], canonical: str, value_type: str, *, source: str, now: datetime, source_reference: str
) -> Optional[FieldValue]:
    if canonical not in cells:
        return None
    return _field_value(
        cells[canonical], value_type, source=source, method="direct_read", retrieved_at=now,
        source_reference=source_reference,
    )


def _build_dimension_field(
    cells: dict[str, Any],
    field_canonical: str,
    unit_canonical: str,
    *,
    is_weight: bool,
    source: str,
    now: datetime,
    source_reference: str,
    row_ref: str,
    issues: list[ProcessingIssue],
) -> Optional[FieldValue]:
    if field_canonical not in cells:
        return None

    value, is_valid = _parse_cell(cells[field_canonical], "decimal")
    if value is None:
        return FieldValue.not_found(
            source=source, method="direct_read", retrieved_at=now,
            source_type=SourceType.NOT_FOUND, source_reference=source_reference,
        )
    if not is_valid:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="INVALID_NUMBER",
                message=f"{field_canonical} value {value!r} is not a valid number.",
                field=field_canonical, record_ref=row_ref,
            )
        )
        return FieldValue.invalid(
            value, source=source, method="direct_read", retrieved_at=now,
            source_type=SourceType.SUPPLIER_FILE, source_reference=source_reference,
        )

    unit_raw = cells.get(unit_canonical)
    unit_text, _ = _parse_cell(unit_raw, "str")
    if unit_text is None:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="MISSING_UNIT",
                message=f"{field_canonical} has a value ({value}) but no unit was given in {unit_canonical!r}.",
                field=field_canonical, record_ref=row_ref,
            )
        )
        return FieldValue.invalid(
            str(value), source=source, method="direct_read", retrieved_at=now,
            source_type=SourceType.SUPPLIER_FILE, source_reference=source_reference,
        )

    try:
        normalized = to_pounds(value, unit_text) if is_weight else to_inches(value, unit_text)
    except UnsupportedUnitError as exc:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="UNSUPPORTED_UNIT", message=str(exc),
                field=field_canonical, record_ref=row_ref,
            )
        )
        return FieldValue.invalid(
            str(value), source=source, method="direct_read", retrieved_at=now,
            source_type=SourceType.SUPPLIER_FILE, source_reference=source_reference,
        )

    canonical_unit = CANONICAL_WEIGHT_UNIT if is_weight else CANONICAL_LENGTH_UNIT
    return FieldValue.verified(
        normalized, source=source, method="unit_normalized_read", retrieved_at=now,
        source_type=SourceType.SUPPLIER_FILE, unit=canonical_unit, source_reference=source_reference,
    )


def _build_risk_flag(
    cells: dict[str, Any],
    canonical: str,
    risk_type: RiskType,
    *,
    source: str,
    now: datetime,
    row_ref: str,
    issues: list[ProcessingIssue],
) -> Optional[RiskFlag]:
    if canonical not in cells:
        return None
    value, is_valid = _parse_cell(cells[canonical], "bool")
    if value is None:
        return RiskFlag(
            risk_type=risk_type, status=RiskStatus.UNKNOWN, verification_status=VerificationStatus.NOT_FOUND,
            # Presence is unknown, so severity cannot be assessed either
            # (ADR-020) -- it mirrors presence's own NOT_FOUND rather than
            # defaulting to a bare Severity.NONE that would look verified.
            severity=FieldValue.not_found(source=source, method="risk_presence_unknown", retrieved_at=now),
            source=source, timestamp=now, evidence="column present but cell is blank",
        )
    if not is_valid:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="INVALID_BOOLEAN",
                message=f"{canonical} value {value!r} is not a recognized true/false value.",
                field=canonical, record_ref=row_ref,
            )
        )
        return RiskFlag(
            risk_type=risk_type, status=RiskStatus.UNKNOWN, verification_status=VerificationStatus.INVALID,
            severity=FieldValue.invalid(
                value, source=source, method="risk_presence_unknown", retrieved_at=now,
                source_type=SourceType.SUPPLIER_FILE,
            ),
            source=source, timestamp=now, evidence=f"unrecognized boolean value: {value!r}",
        )
    if value is True:
        return RiskFlag(
            risk_type=risk_type, status=RiskStatus.PRESENT, verification_status=VerificationStatus.VERIFIED,
            # Fail-closed on purpose (see ADR-015): a RiskType with no explicit
            # entry here must never silently receive an assumed severity — that
            # would be exactly the kind of invented business value this project
            # forbids. Adding a new risk source requires adding its severity to
            # DEFAULT_RISK_SEVERITY first, not falling back to a guess.
            #
            # This severity is INFERRED, never VERIFIED (ADR-020): the
            # supplier verified that the risk is PRESENT, not that Juval's
            # internal HIGH/MEDIUM classification for it is correct --
            # DEFAULT_RISK_SEVERITY is a provisional, business-unapproved
            # policy table (ADR-010), not data read from the file.
            severity=FieldValue.inferred(
                DEFAULT_RISK_SEVERITY[risk_type], source="DEFAULT_RISK_SEVERITY",
                method="ADR-010 provisional internal severity classification (not business-approved)",
                retrieved_at=now, source_type=SourceType.CALCULATED,
            ),
            source=source, timestamp=now, evidence="declared by supplier",
        )
    return RiskFlag(
        risk_type=risk_type, status=RiskStatus.ABSENT, verification_status=VerificationStatus.VERIFIED,
        # No risk present -> NONE severity is a certain logical consequence
        # of a verified absence, not a policy guess -- VERIFIED is correct
        # here (unlike the PRESENT branch above).
        severity=FieldValue.verified(
            Severity.NONE, source=source, method="no_risk_present", retrieved_at=now,
            source_type=SourceType.SUPPLIER_FILE,
        ),
        source=source, timestamp=now,
    )


def _build_price(
    cells: dict[str, Any], *, source: str, now: datetime, source_reference: str, row_ref: str, issues: list[ProcessingIssue]
) -> Price:
    if "selling_price" not in cells:
        return Price()
    observed = _field_value(
        cells["selling_price"], "decimal", source=source, method="manual_price_observation",
        retrieved_at=now, source_reference=source_reference,
    )
    if observed.status == VerificationStatus.INVALID:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="INVALID_PRICE",
                message=f"selling_price {observed.raw_value!r} is not a valid number.",
                field="selling_price", record_ref=row_ref,
            )
        )
        return Price()
    if observed.status == VerificationStatus.NOT_FOUND:
        return Price()
    return Price(current_buy_box=observed, selling_price_used=observed, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX)


def _build_costs(
    cells: dict[str, Any], *, row_ref: str, issues: list[ProcessingIssue]
) -> Optional[CostInputs]:
    cog_value, cog_valid = _parse_cell(cells.get("cost"), "decimal")
    if cog_value is None:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="MISSING_REQUIRED_FIELD",
                message="cost (COG) is required to compute profitability but the cell is blank.",
                field="cost", record_ref=row_ref,
            )
        )
        return None
    if not cog_valid:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="INVALID_NUMBER",
                message=f"cost {cog_value!r} is not a valid number.", field="cost", record_ref=row_ref,
            )
        )
        return None
    if cog_value < 0:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="NEGATIVE_COST",
                message=f"cost must not be negative, got {cog_value}.", field="cost", record_ref=row_ref,
            )
        )
        return None

    shipping_value = Decimal("0")
    if "shipping_per_unit" in cells:
        parsed, valid = _parse_cell(cells["shipping_per_unit"], "decimal")
        if parsed is None:
            pass  # blank optional cost column -> 0 is the documented CostInputs default, not a hidden error
        elif not valid:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR, code="INVALID_NUMBER",
                    message=f"shipping_per_unit {parsed!r} is not a valid number.",
                    field="shipping_per_unit", record_ref=row_ref,
                )
            )
        elif parsed < 0:
            issues.append(
                ProcessingIssue(
                    level=IssueLevel.RECORD_ERROR, code="NEGATIVE_COST",
                    message=f"shipping_per_unit must not be negative, got {parsed}.",
                    field="shipping_per_unit", record_ref=row_ref,
                )
            )
        else:
            shipping_value = parsed

    return CostInputs(cog=cog_value, shipping_per_unit=shipping_value)


def _build_record(
    row_number: int, cells: dict[str, Any], now: datetime, *, source: str
) -> tuple[Optional[SourcingRecord], list[ProcessingIssue]]:
    issues: list[ProcessingIssue] = []
    source_reference = f"row={row_number}"

    supplier_sku, _ = _parse_cell(cells.get("supplier_sku"), "str")
    row_ref = f"row_{row_number}" + (f":{supplier_sku}" if supplier_sku else "")

    marketplace, marketplace_valid = _parse_cell(cells.get("marketplace"), "str")
    if marketplace is None or not marketplace_valid:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="MISSING_REQUIRED_FIELD",
                message="marketplace is required but the cell is blank; this row cannot be built.",
                field="marketplace", record_ref=row_ref,
            )
        )
        return None, issues

    asin_fv = _field_value(
        cells.get("asin"), "asin", source=source, method="direct_read", retrieved_at=now, source_reference=source_reference
    )
    if asin_fv.status == VerificationStatus.INVALID:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="INVALID_ASIN_FORMAT",
                message=f"asin {asin_fv.raw_value!r} is not a valid 10-character ASIN.",
                field="asin", record_ref=row_ref,
            )
        )

    upc_fv = _optional_field_value(cells, "upc", "upc", source=source, now=now, source_reference=source_reference)
    if upc_fv is not None and upc_fv.status == VerificationStatus.INVALID:
        issues.append(
            ProcessingIssue(
                level=IssueLevel.RECORD_ERROR, code="INVALID_UPC_FORMAT",
                message=f"upc {upc_fv.raw_value!r} fails the GS1 checksum.", field="upc", record_ref=row_ref,
            )
        )

    identification = Identification(
        asin=asin_fv, marketplace=marketplace, upc=upc_fv, supplier_sku=supplier_sku
    )

    info = ProductInfo(
        title=_optional_field_value(cells, "title", "str", source=source, now=now, source_reference=source_reference),
        brand=_optional_field_value(cells, "brand", "str", source=source, now=now, source_reference=source_reference),
        category=_optional_field_value(cells, "category", "str", source=source, now=now, source_reference=source_reference),
    )

    dimensions = Dimensions(
        weight=_build_dimension_field(
            cells, "weight", "weight_unit", is_weight=True, source=source, now=now,
            source_reference=source_reference, row_ref=row_ref, issues=issues,
        ),
        height=_build_dimension_field(
            cells, "height", "dimension_unit", is_weight=False, source=source, now=now,
            source_reference=source_reference, row_ref=row_ref, issues=issues,
        ),
        width=_build_dimension_field(
            cells, "width", "dimension_unit", is_weight=False, source=source, now=now,
            source_reference=source_reference, row_ref=row_ref, issues=issues,
        ),
        length=_build_dimension_field(
            cells, "length", "dimension_unit", is_weight=False, source=source, now=now,
            source_reference=source_reference, row_ref=row_ref, issues=issues,
        ),
    )

    price = _build_price(cells, source=source, now=now, source_reference=source_reference, row_ref=row_ref, issues=issues)

    product = Product(identification=identification, info=info, dimensions=dimensions, price=price)

    costs = _build_costs(cells, row_ref=row_ref, issues=issues)

    risk_flags = tuple(
        flag
        for flag in (
            _build_risk_flag(cells, "hazmat", RiskType.HAZMAT, source=source, now=now, row_ref=row_ref, issues=issues),
            _build_risk_flag(cells, "bulky", RiskType.BULKY, source=source, now=now, row_ref=row_ref, issues=issues),
        )
        if flag is not None
    )
    risk = RiskProfile(flags=risk_flags)

    record = SourcingRecord(
        record_ref=row_ref, product=product, costs=costs, risk=risk, issues=tuple(issues)
    )
    return record, issues


def import_excel(path: Path, *, now: datetime, sheet_name: Optional[str] = None) -> ImportResult:
    path = Path(path)
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        return _import_from_workbook(workbook, path, now=now, sheet_name=sheet_name)
    finally:
        # `read_only=True` keeps the underlying zip file handle open (lazy
        # row access) until explicitly closed. Without this, a caller that
        # tries to delete/replace `path` right after import_excel() returns
        # gets a PermissionError on Windows (file still locked by this
        # process) -- e.g. interfaces/api, which removes the uploaded temp
        # file immediately after processing it.
        workbook.close()


def _import_from_workbook(
    workbook: openpyxl.workbook.Workbook, path: Path, *, now: datetime, sheet_name: Optional[str] = None
) -> ImportResult:
    sheet = workbook[sheet_name] if sheet_name else workbook.worksheets[0]
    rows_iter = sheet.iter_rows(values_only=True)

    try:
        raw_headers = next(rows_iter)
    except StopIteration:
        return ImportResult(
            records=(),
            issues=(ProcessingIssue(level=IssueLevel.FATAL, code="EMPTY_FILE", message=f"{path.name} has no rows."),),
            fatal=True,
            rows_scanned=0,
            rows_skipped_blank=0,
        )

    normalized_headers = [normalize_header(h) for h in raw_headers]
    column_index, header_issues = _resolve_headers(normalized_headers)
    if any(issue.level == IssueLevel.FATAL for issue in header_issues):
        return ImportResult(
            records=(), issues=tuple(header_issues), fatal=True, rows_scanned=0, rows_skipped_blank=0,
        )

    issues: list[ProcessingIssue] = list(header_issues)
    records: list[SourcingRecord] = []
    rows_scanned = 0
    rows_skipped_blank = 0

    for row_number, raw_row in enumerate(rows_iter, start=2):
        if raw_row is None or all(v is None for v in raw_row):
            rows_skipped_blank += 1
            continue
        rows_scanned += 1
        cells = {canonical: raw_row[idx] for canonical, idx in column_index.items() if idx < len(raw_row)}
        record, row_issues = _build_record(row_number, cells, now, source=path.name)
        issues.extend(row_issues)
        if record is not None:
            records.append(record)

    return ImportResult(
        records=tuple(records), issues=tuple(issues), fatal=False,
        rows_scanned=rows_scanned, rows_skipped_blank=rows_skipped_blank,
    )
