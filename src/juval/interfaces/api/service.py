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
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.execution_run import ExecutionRun, ExecutionStatus
from juval.domain.provenance import FieldValue
from juval.domain.risk import RiskType
from juval.domain.sourcing_record import SourcingRecord

from .models import FeesIn, FieldValueOut, RecordOut, ThresholdsIn


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


def _fv(fv: Optional[FieldValue[Any]]) -> FieldValueOut:
    if fv is None:
        return FieldValueOut(value=None, status=None)
    value = str(fv.value) if isinstance(fv.value, Decimal) else fv.value
    return FieldValueOut(value=value, status=fv.status.value)


def record_to_json(record: SourcingRecord) -> RecordOut:
    ident = record.product.identification
    dims = record.product.dimensions
    price = record.product.price

    cog = record.costs.cog if record.costs is not None else None
    shipping_per_unit = record.costs.shipping_per_unit if record.costs is not None else None

    if record.profitability is not None:
        profit = _fv(record.profitability.profit)
        roi = _fv(record.profitability.roi)
        margin = _fv(record.profitability.margin)
        break_even_price = _fv(record.profitability.break_even_price)
        max_cog_target_profit = _fv(record.profitability.max_cog_target_profit)
        max_cog_target_roi = _fv(record.profitability.max_cog_target_roi)
    else:
        profit = roi = margin = break_even_price = FieldValueOut()
        max_cog_target_profit = max_cog_target_roi = FieldValueOut()

    hazmat_flag = record.risk.flag_for(RiskType.HAZMAT)
    bulky_flag = record.risk.flag_for(RiskType.BULKY)

    if record.decision is not None:
        decision = record.decision.decision.value
        decision_reasons = [f"{r.code}: {r.message}" for r in record.decision.reasons]
    else:
        decision = None
        decision_reasons = []

    return RecordOut(
        record_ref=record.record_ref,
        marketplace=ident.marketplace,
        supplier_sku=ident.supplier_sku,
        asin=_fv(ident.asin),
        upc=_fv(ident.upc),
        weight=_fv(dims.weight),
        selling_price=_fv(price.selling_price_used),
        cog=cog,
        shipping_per_unit=shipping_per_unit,
        profit=profit,
        roi=roi,
        margin=margin,
        break_even_price=break_even_price,
        max_cog_target_profit=max_cog_target_profit,
        max_cog_target_roi=max_cog_target_roi,
        hazmat_status=hazmat_flag.status.value if hazmat_flag is not None else None,
        hazmat_severity=hazmat_flag.severity.value if hazmat_flag is not None else None,
        bulky_status=bulky_flag.status.value if bulky_flag is not None else None,
        bulky_severity=bulky_flag.severity.value if bulky_flag is not None else None,
        decision=decision,
        decision_reasons=decision_reasons,
        issue_count=len(record.issues),
        issues=[f"[{i.level.value}] {i.code}: {i.message}" for i in record.issues],
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


def run_dir(execution_id: str) -> Path:
    return storage_dir() / execution_id


def output_path(execution_id: str) -> Path:
    return run_dir(execution_id) / "output.xlsx"


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
