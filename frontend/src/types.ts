// Mirrors docs/architecture/API_CONTRACT.md exactly. No business logic --
// pure data shapes. Never collapse a FieldValueOut to a bare `value`:
// `status` (VerificationStatus) must always travel with it (ADR-003/ADR-004).

export type Severity = "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"

export interface ThresholdsIn {
  target_profit: string
  target_roi: string
  minimum_estimated_monthly_sales: number
  maximum_risk_severity: Severity
  allow_restricted: boolean
  allow_approval_required: boolean
  allow_unknown_risk: boolean
}

export interface FeesIn {
  referral_fee: string
  referral_fee_rate: string
  fulfillment_fee: string
  other_selling_fees: string
}

export interface FieldValueOut {
  value: string | number | boolean | null
  status: "VERIFIED" | "INFERRED" | "NOT_FOUND" | "INVALID" | null
  unit?: string | null
  raw_value?: string | number | boolean | null
  provenance?: ProvenanceOut | null
}

export interface ProvenanceOut {
  source: string
  source_type: string
  verification_status: "VERIFIED" | "INFERRED" | "NOT_FOUND" | "INVALID"
  retrieved_at: string
  method: string
  confidence: number | null
  evidence: string | null
  source_reference: string | null
}

export interface RecordOut {
  record_ref: string
  marketplace: string | null
  supplier_sku: string | null
  asin: FieldValueOut
  upc: FieldValueOut
  title?: FieldValueOut
  brand?: FieldValueOut
  category?: FieldValueOut
  weight: FieldValueOut
  height?: FieldValueOut
  width?: FieldValueOut
  length?: FieldValueOut
  selling_price: FieldValueOut
  cog: string | null
  shipping_per_unit: string | null
  // Intermediate Profitability Engine terms. `null` means the snapshot did
  // not store them (unusable selling price, or a pre-F1 snapshot) -- never 0.
  total_fees?: string | null
  seller_proceeds?: string | null
  total_cost?: string | null
  profit: FieldValueOut
  roi: FieldValueOut
  margin: FieldValueOut
  break_even_price: FieldValueOut
  max_cog_target_profit: FieldValueOut
  max_cog_target_roi: FieldValueOut
  hazmat_status: string | null
  hazmat_severity: string | null
  bulky_status: string | null
  bulky_severity: string | null
  decision: string | null
  decision_reasons: string[]
  issue_count: number
  issues: string[]
  // Canonical ProcessingIssue codes; absent on snapshots written before the
  // field existed, and never reconstructed from the rendered strings.
  issue_codes?: string[]
}

export interface RunResponse {
  execution_id: string
  status: string
  input_filename: string
  input_hash: string
  records_total: number
  records_processed: number
  records_successful: number
  records_with_errors: number
  warnings: number
  persisted: boolean
  records: RecordOut[]
}

export interface BatchFileResponse {
  ordinal: number
  filename: string
  content_type: string | null
  size_bytes: number
  status: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED" | "REJECTED"
  execution_id: string | null
  warnings: string[]
  errors: string[]
  // Counts from this file's own child ExecutionRun. A REJECTED file never ran,
  // so 0 here means "never processed", not a measured zero.
  records_total: number
  records_processed: number
  records_with_errors: number
  warning_count: number
}

export interface BatchResponse {
  batch_id: string
  created_at: string
  status: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED"
  total_files: number
  succeeded_files: number
  failed_files: number
  persisted: boolean
  records_total: number
  records_processed: number
  records_with_errors: number
  warning_count: number
  files: BatchFileResponse[]
}

export interface RunFailedResponse {
  execution_id: string
  status: "FAILED"
  input_filename: string
  input_hash: string
  message: string
}

export type RunState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "processing" }
  | { status: "success"; result: RunResponse }
  | { status: "error"; message: string }

export type ProvenanceStatus = "VERIFIED" | "INFERRED" | "NOT_FOUND" | "INVALID"
export type Decision = "BUY" | "REVIEW" | "PASS"

// GET /api/v1/runs -- real ExecutionRun fields (API_CONTRACT.md §2b).
// Deliberately not "created_at"/"valid"/"excluded": those have no
// domain equivalent (see docs/FRONTEND_BACKEND_HANDOFF.md §6).
export interface RunSummaryOut {
  execution_id: string
  started_at: string
  finished_at: string | null
  status: "RUNNING" | "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED"
  input_filename: string
  input_hash: string
  records_total: number
  records_processed: number
  records_successful: number
  records_with_errors: number
  warnings: number
}

export interface RunsListResponse {
  items: RunSummaryOut[]
}

// GET /api/v1/runs/{execution_id}/records (ADR-019) -- run-scoped only,
// never a global product identity (record_ref is unique per execution,
// ADR-012). RecordOut is the same shape as RunResponse.records. Query and
// pagination are server-side (API_CONTRACT.md); the frontend must never
// fetch every page and re-filter/sort/paginate in the browser.
export interface RecordPaginationOut {
  limit: number
  offset: number
  total: number
  has_more: boolean
}

export interface RunRecordsResponse {
  execution_id: string
  records: RecordOut[]
  pagination: RecordPaginationOut
}

export type RecordSort = "record_ref" | "sku" | "asin" | "title" | "price" | "cog" | "decision" | "profit" | "roi" | "margin" | "hazmat" | "bulky"
export type SortDirection = "asc" | "desc"

export interface RunRecordsQuery {
  limit?: number
  offset?: number
  search?: string
  decision?: Decision
  sort?: RecordSort
  direction?: SortDirection
  min_roi?: string
  min_profit?: string
  min_margin?: string
  confidence?: "VERIFIED_ONLY" | "INCLUDE_INFERRED"
  hazmat?: string
  bulky?: string
  provenance_field?: "asin" | "selling_price" | "profit" | "roi" | "margin"
  provenance_status?: "VERIFIED" | "INFERRED" | "NOT_FOUND" | "INVALID"
}

// GET /api/v1/runs/{execution_id}/analytics -- backend-computed aggregates
// only (API_CONTRACT.md). The frontend never recomputes these: it renders
// exactly what the Core/persistence layer already aggregated. `count`
// fields count usable (VERIFIED) values only; a summary with count 0 has
// every numeric field as `null`, never 0 -- see docs on provenance-aware
// averaging (ADR-004): missing/invalid values are never coerced to zero.
export interface NumericSummary {
  count: number
  sum: string | null
  average: string | null
  minimum: string | null
  maximum: string | null
}

// Internal analytics projections aggregated from canonical snapshot fields
// (no provider data, no ranking model). `not_recorded` stays separate from any
// named brand, and a spread `percent` is null when the price is not > 0.
export interface BrandDistributionOut {
  items: { label: string; count: number }[]
  distinct: number
  not_recorded: number
}

export interface PriceSpreadOut {
  count: number
  average_amount: string | null
  at_or_below_cog: number
  largest: { record_ref: string; title: string | null; amount: string; percent: string | null }[]
}

export interface RunAnalyticsOut {
  execution_id: string
  records: { total_records: number }
  decisions: Record<string, number>
  risks: Record<string, { status: Record<string, number>; severity: Record<string, number> }>
  provenance: Record<"asin" | "weight" | "selling_price" | "profit" | "roi" | "margin", Record<string, number>>
  data_quality: { records_with_issues: number; total_issue_count: number }
  profitability: { profit: NumericSummary; roi: NumericSummary; margin: NumericSummary }
  brands: BrandDistributionOut
  issue_types: { code: string; count: number }[]
  price_spread: PriceSpreadOut
}
