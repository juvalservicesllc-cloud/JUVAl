"""Validate-only preview of a tabular input file (GOLDEN parity items 15-16).

Runs the real importer -- the same `import_file` a run uses, so the same
header rule, parsing and validation -- and reports what it decided: how each
header was resolved, which required columns are missing, how many rows would
become records and which issues the importer raised. Nothing else happens:
no processing, profitability, risk or decision, no `ExecutionRun`, no
persistence. Processing without persisting is already `POST /api/v1/runs`
with `persist=false`; this answers the earlier question "will JUVAl read this
file the way I expect?".
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from juval.domain.execution_run import hash_file
from juval.domain.issues import ProcessingIssue
from juval.infrastructure.excel.column_mapping import COLUMN_SPECS, DEMAND_EVIDENCE_COLUMN_SPECS, FINANCIAL_EVIDENCE_COLUMN_SPECS, ColumnSpec
from juval.infrastructure.excel.importer import HeaderResolution, import_file

#: Issues listed in full; the counts by level and code always cover all of them.
PREVIEW_ISSUE_LIMIT = 100

_SPECS: dict[str, tuple[ColumnSpec, str]] = {
    **{spec.canonical: (spec, "core") for spec in COLUMN_SPECS},
    # Native ADR-047 evidence columns never feed profitability or decisions.
    **{spec.canonical: (spec, "native_financial_evidence") for spec in FINANCIAL_EVIDENCE_COLUMN_SPECS},
    # Declared demand evidence (ADR-052) never feeds decisions either.
    **{spec.canonical: (spec, "declared_demand") for spec in DEMAND_EVIDENCE_COLUMN_SPECS},
}


@dataclass(frozen=True)
class PreviewColumn:
    position: int
    header: str
    normalized: str
    status: str                 # MAPPED | UNKNOWN | DUPLICATE | BLANK (importer's decision)
    canonical: Optional[str]
    alias_of: Optional[str]     # canonical name when the header is one of its aliases
    target: Optional[str]       # MAPPED only
    required: bool              # MAPPED only
    group: Optional[str]        # MAPPED only: core | native_financial_evidence | declared_demand


@dataclass(frozen=True)
class ImportPreview:
    input_filename: str
    input_hash: str
    fatal: bool
    rows_scanned: int
    rows_skipped_blank: int
    records_importable: int
    columns: tuple[PreviewColumn, ...]
    missing_required_columns: tuple[ColumnSpec, ...]
    issue_counts: tuple[tuple[str, str, int], ...]   # (level, code, count), sorted
    issues: tuple[ProcessingIssue, ...]               # first PREVIEW_ISSUE_LIMIT, importer order
    issues_total: int


def _column(resolution: HeaderResolution) -> PreviewColumn:
    # Only a MAPPED column feeds a field; a DUPLICATE keeps `canonical` to say
    # what it repeats, but no target, because the importer ignores it.
    spec, group = _SPECS[resolution.canonical] if resolution.status == "MAPPED" else (None, None)
    return PreviewColumn(
        position=resolution.position,
        header=resolution.header,
        normalized=resolution.normalized,
        status=resolution.status,
        canonical=resolution.canonical,
        alias_of=resolution.canonical if resolution.canonical and resolution.normalized != resolution.canonical else None,
        target=spec.target if spec else None,
        required=bool(spec and spec.required),
        group=group,
    )


def preview_import(path: Path, *, now: datetime) -> ImportPreview:
    """Import `path` exactly as a run would and describe the outcome.

    Raises what `import_file` raises for an unreadable or unsupported file.
    """
    result = import_file(path, now=now)
    # The importer's own verdict, not a second check: an empty file reports
    # EMPTY_FILE and no missing column, because no header was evaluated.
    missing = {issue.field for issue in result.issues if issue.code == "MISSING_REQUIRED_COLUMN"}
    counts = Counter((issue.level.value, issue.code) for issue in result.issues)
    return ImportPreview(
        input_filename=Path(path).name,
        input_hash=hash_file(path),
        fatal=result.fatal,
        rows_scanned=result.rows_scanned,
        rows_skipped_blank=result.rows_skipped_blank,
        records_importable=len(result.records),
        columns=tuple(_column(r) for r in result.columns),
        missing_required_columns=tuple(s for s in COLUMN_SPECS if s.canonical in missing),
        issue_counts=tuple((level, code, n) for (level, code), n in sorted(counts.items())),
        issues=result.issues[:PREVIEW_ISSUE_LIMIT],
        issues_total=len(result.issues),
    )
