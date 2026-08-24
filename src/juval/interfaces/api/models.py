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
from typing import Any, Literal, Optional

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


class ProvenanceOut(BaseModel):
    source: str
    source_type: str
    verification_status: str
    retrieved_at: str
    method: str
    confidence: Optional[float] = None
    evidence: Optional[str] = None
    source_reference: Optional[str] = None


class FieldValueOut(BaseModel):
    """Never collapses a FieldValue to a bare value (ADR-003/ADR-004) --
    value and verification_status always travel together, same rule the
    Excel exporter already applies to `<field>`/`<field>_status` columns.
    """

    value: Optional[Any] = None
    status: Optional[str] = None
    unit: Optional[str] = None
    raw_value: Optional[Any] = None
    # ``None`` is meaningful for legacy snapshots written before F1. It is
    # never reconstructed at read time.
    provenance: Optional[ProvenanceOut] = None


class RecordOut(BaseModel):
    record_ref: str
    marketplace: Optional[str] = None
    supplier_sku: Optional[str] = None
    asin: FieldValueOut
    upc: FieldValueOut
    # title/brand/category: whatever the supplier declared in the import
    # file (domain.product.ProductInfo) -- never Amazon-confirmed data;
    # no separate AmazonProductInfo concept exists yet (PRODUCT_CAPABILITY_MATRIX.md §5).
    title: FieldValueOut = FieldValueOut()
    brand: FieldValueOut = FieldValueOut()
    category: FieldValueOut = FieldValueOut()
    weight: FieldValueOut
    # height/width/length: canonical units (domain.units), inches -- same
    # convention as weight (pounds), not re-stated per field.
    height: FieldValueOut = FieldValueOut()
    width: FieldValueOut = FieldValueOut()
    length: FieldValueOut = FieldValueOut()
    selling_price: FieldValueOut
    cog: Optional[Decimal] = None
    shipping_per_unit: Optional[Decimal] = None
    # Intermediate Profitability Engine terms (ProfitabilityResult). Absent on
    # snapshots written before they were persisted; `None` there means "not
    # stored", never zero.
    total_fees: Optional[Decimal] = None
    seller_proceeds: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
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
    issue_codes: list[str] = []


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


class BatchFileOut(BaseModel):
    ordinal: int
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    status: Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED", "REJECTED"]
    execution_id: Optional[str] = None
    warnings: list[str] = []
    errors: list[str] = []
    # Counts from this file's own child ExecutionRun. A REJECTED file never ran,
    # so these stay 0 -- "never processed", not a measured zero.
    records_total: int = 0
    records_processed: int = 0
    records_with_errors: int = 0
    warning_count: int = 0


class BatchResponse(BaseModel):
    batch_id: str
    created_at: str
    status: Literal["SUCCESS", "PARTIAL_SUCCESS", "FAILED"]
    total_files: int
    succeeded_files: int
    failed_files: int
    persisted: bool
    # Aggregates across every child run in the batch.
    records_total: int = 0
    records_processed: int = 0
    records_with_errors: int = 0
    warning_count: int = 0
    files: list[BatchFileOut]


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
    pagination: "RecordPaginationOut"


class RecordPaginationOut(BaseModel):
    limit: int
    offset: int
    total: int
    has_more: bool


class BrandCountOut(BaseModel):
    label: str
    count: int


class BrandDistributionOut(BaseModel):
    """Brands actually recorded in the run. `not_recorded` stays its own count
    -- an absent brand is never folded into a named one."""

    items: list[BrandCountOut] = []
    distinct: int = 0
    not_recorded: int = 0


class IssueTypeOut(BaseModel):
    code: str
    count: int


class PriceSpreadEntryOut(BaseModel):
    record_ref: str
    title: Optional[str] = None
    amount: Decimal
    # None when the selling price is not > 0, so a percentage would be undefined.
    percent: Optional[Decimal] = None


class PriceSpreadOut(BaseModel):
    """Selling price minus COG across the run, VERIFIED selling prices only."""

    count: int = 0
    average_amount: Optional[Decimal] = None
    at_or_below_cog: int = 0
    largest: list[PriceSpreadEntryOut] = []


class RunAnalyticsOut(BaseModel):
    execution_id: str
    records: dict[str, int]
    decisions: dict[str, int]
    risks: dict[str, dict[str, dict[str, int]]]
    provenance: dict[str, dict[str, int]]
    data_quality: dict[str, int]
    profitability: dict[str, dict[str, int | str | None]]
    brands: BrandDistributionOut = BrandDistributionOut()
    issue_types: list[IssueTypeOut] = []
    price_spread: PriceSpreadOut = PriceSpreadOut()
