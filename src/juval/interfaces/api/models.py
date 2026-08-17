"""HTTP-boundary models: validate request shape, serialize responses.

These are Pydantic models, not domain models (ADR-001, ADR-013 "thin
client" pattern already used by interfaces/cli/main.py). They mirror the
field names of `domain.decision.Thresholds` / `domain.costs.FeeInputs`
exactly (see `service.py::thresholds_from_in`/`fees_from_in` for the only
place that translates one into the other) so that a request maps
one-to-one onto the domain contract instead of inventing a parallel
shape. No business rule, calculation, or default threshold value lives
here -- Pydantic only validates that the request *looks like* a valid
Thresholds/FeeInputs; `domain.decision.Thresholds.__post_init__` /
`domain.costs.FeeInputs.__post_init__` are still the ones that enforce
the actual invariants (ADR-007: no commercial default is invented at
this layer either).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel

from juval.domain.risk import Severity


class ThresholdsIn(BaseModel):
    target_profit: Decimal
    target_roi: Decimal
    minimum_estimated_monthly_sales: int
    maximum_risk_severity: Severity
    allow_restricted: bool = False
    allow_approval_required: bool = False
    allow_unknown_risk: bool = False


class FeesIn(BaseModel):
    referral_fee: Decimal
    referral_fee_rate: Decimal
    fulfillment_fee: Decimal = Decimal("0")
    other_selling_fees: Decimal = Decimal("0")


class FieldValueOut(BaseModel):
    """Never collapses a FieldValue to a bare value (ADR-003/ADR-004) --
    value and verification_status always travel together, same rule the
    Excel exporter already applies to `<field>`/`<field>_status` columns.
    """

    value: Optional[Any] = None
    status: Optional[str] = None


class RecordOut(BaseModel):
    record_ref: str
    marketplace: Optional[str] = None
    supplier_sku: Optional[str] = None
    asin: FieldValueOut
    upc: FieldValueOut
    weight: FieldValueOut
    selling_price: FieldValueOut
    cog: Optional[Decimal] = None
    shipping_per_unit: Optional[Decimal] = None
    profit: FieldValueOut
    roi: FieldValueOut
    margin: FieldValueOut
    break_even_price: FieldValueOut
    max_cog_target_profit: FieldValueOut
    max_cog_target_roi: FieldValueOut
    hazmat_status: Optional[str] = None
    hazmat_severity: Optional[str] = None
    bulky_status: Optional[str] = None
    bulky_severity: Optional[str] = None
    decision: Optional[str] = None
    decision_reasons: list[str] = []
    issue_count: int = 0
    issues: list[str] = []


class RunResponse(BaseModel):
    execution_id: str
    status: str
    input_filename: str
    input_hash: str
    records_total: int
    records_processed: int
    records_successful: int
    records_with_errors: int
    warnings: int
    persisted: bool
    records: list[RecordOut] = []


class RunFailedResponse(BaseModel):
    execution_id: str
    status: str
    input_filename: str
    input_hash: str
    message: str


class RunSummaryOut(BaseModel):
    """One row of `GET /api/v1/runs` -- ExecutionRun's own real fields,
    not the frontend-demo vocabulary ("created_at"/"valid"/"excluded")
    that has no backend equivalent (ADR-019 "Modelo de recurso" /
    API_CONTRACT.md §9-§10 -- never invent a field to match a mock)."""

    execution_id: str
    started_at: str
    finished_at: Optional[str] = None
    status: str
    input_filename: str
    input_hash: str
    records_total: int
    records_processed: int
    records_successful: int
    records_with_errors: int
    warnings: int


class RunsListResponse(BaseModel):
    items: list[RunSummaryOut]


class RunRecordsResponse(BaseModel):
    execution_id: str
    records: list[RecordOut]
