"""Translation layer: HTTP/Pydantic <-> Core, and temp-file management.

Thin client over `application.run_pipeline` (ADR-001) -- the same
pattern `interfaces/cli/main.py` already uses. This module never
computes profit/ROI/margin/score/decision/severity itself; it only
converts request models to domain objects, calls the existing pipeline,
and converts the result back to response models (mirroring the
value/status pairing `infrastructure/excel/exporter.py` already applies
for Excel -- see `record_to_json`, structurally parallel to
`exporter.py::_row_for_record`, not a second implementation of any
calculation).
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from juval.application.record_snapshot import record_to_snapshot
from juval.application.demand_evidence import demand_evidence_state
from juval.application.suggested_price_evidence import suggested_price_state
from juval.application.review_classification import review_classification
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.sourcing_record import SourcingRecord

from .models import FeesIn, RecordOut, RunSummaryOut, ThresholdsIn


def thresholds_from_in(data: ThresholdsIn) -> Thresholds:
    return Thresholds(
        target_profit=data.target_profit,
        target_roi=data.target_roi,
        minimum_estimated_monthly_sales=data.minimum_estimated_monthly_sales,
        maximum_risk_severity=data.maximum_risk_severity,
        allow_restricted=data.allow_restricted,
        allow_approval_required=data.allow_approval_required,
        allow_unknown_risk=data.allow_unknown_risk,
    )


def fees_from_in(data: FeesIn) -> FeeInputs:
    return FeeInputs(
        referral_fee=data.referral_fee,
        referral_fee_rate=data.referral_fee_rate,
        fulfillment_fee=data.fulfillment_fee,
        other_selling_fees=data.other_selling_fees,
    )


def record_to_json(record: SourcingRecord) -> RecordOut:
    """Thin wrapper: the actual SourcingRecord -> JSON mapping lives in
    `application/record_snapshot.py::record_to_snapshot` (ADR-019),
    shared with the record-snapshot persistence adapters -- never two
    implementations of the same mapping."""

    return record_out(record_to_snapshot(record))


def record_out(snapshot: dict) -> RecordOut:
    """A stored snapshot as the API shows it, plus the informative REVIEW
    sub-classification -- computed in one place, never stored, never a decision."""
    return RecordOut(**{**snapshot, "review_classification": review_classification(snapshot),
                        "demand_evidence_state": demand_evidence_state(snapshot),
                        "supplier_suggested_price_state": suggested_price_state(snapshot)})


def run_to_summary(run: ExecutionRun, decisions: Optional[dict[str, int]] = None) -> RunSummaryOut:
    return RunSummaryOut(
        execution_id=run.execution_id,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at is not None else None,
        status=run.status.value,
        input_filename=run.input_filename,
        input_hash=run.input_hash,
        records_total=run.records_total,
        records_processed=run.records_processed,
        records_successful=run.records_successful,
        records_with_errors=run.records_with_errors,
        warnings=run.warnings,
        decisions=decisions,
    )


# -- Temp storage for uploaded/generated Excel files -------------------
#
# Base directory is read from JUVAL_RUN_STORAGE_DIR *at call time* (not
# at import time) so tests can point it at an isolated tmp_path. No
# permanent storage is created (§12 of the Fase 4A brief) -- this is
# always somewhere under a temp directory.


def storage_dir() -> Path:
    base = os.environ.get("JUVAL_RUN_STORAGE_DIR", tempfile.gettempdir())
    return Path(base) / "juval_runs"


def _path_component(value: str) -> str:
    if value in ("", ".", "..") or "/" in value or "\\" in value or "\0" in value:
        raise ValueError("not a run identifier")
    return value


def run_dir(organization_id: str, execution_id: str) -> Path:
    """The directory of one run: `<storage>/<organization>/<execution_id>`.

    ADR-056: files are partitioned by organization, so a caller can only ever
    name a file inside its own organization's directory -- another
    organization's run is simply not there (404), whatever its id. Files from
    before the partition stay at `<storage>/<execution_id>` and are therefore
    unreachable (quarantine, OD-3).

    Both values also arrive from URL paths, where a percent-encoded `..` is
    decoded before routing: anything that is not a single plain path
    component is refused.
    """
    return storage_dir() / _path_component(organization_id) / _path_component(execution_id)


def output_path(organization_id: str, execution_id: str) -> Path:
    return run_dir(organization_id, execution_id) / "output.xlsx"


def new_execution_id() -> str:
    return str(uuid.uuid4())


def max_upload_bytes() -> Optional[int]:
    """PENDING business decision (see API_CONTRACT.md): no size limit is
    enforced unless JUVAL_MAX_UPLOAD_BYTES is set explicitly -- matches
    the Core's current unlimited behavior (SECURITY.md #3) rather than
    inventing an arbitrary commercial number here."""

    raw = os.environ.get("JUVAL_MAX_UPLOAD_BYTES")
    return int(raw) if raw else None


def cors_origins() -> list[str]:
    raw = os.environ.get("JUVAL_CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
