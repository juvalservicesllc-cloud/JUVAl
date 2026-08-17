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
}

export interface RecordOut {
  record_ref: string
  marketplace: string | null
  supplier_sku: string | null
  asin: FieldValueOut
  upc: FieldValueOut
  weight: FieldValueOut
  selling_price: FieldValueOut
  cog: string | null
  shipping_per_unit: string | null
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

export type ProvenanceStatus = "VERIFIED" | "INFERRED" | "NOT_FOUND"
export type Decision = "BUY" | "REVIEW" | "PASS"

export interface DashboardSummary {
  totalProducts: number
  processable: number
  excluded: number
  hazmat: number
  bulky: number
  missingAsin: number
}

export interface ProductRow {
  sku: string
  product: string
  brand: string
  cost: string
  asin: string | null
  asinStatus: ProvenanceStatus
  hazmat: boolean
  bulky: boolean
  decision: Decision
}

export interface ExecutionRunSummary {
  executionId: string
  createdAt: string
  status: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED"
  totalRecords: number
  valid: number
  excluded: number
  errors: number
}

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
// ADR-012). RecordOut is the same shape as RunResponse.records.
export interface RunRecordsResponse {
  execution_id: string
  records: RecordOut[]
}

export interface ProductListItem {
  record_ref: string
  supplier_sku: string | null
  title: FieldValueOut
  brand: FieldValueOut
  cog: string | null
  asin: FieldValueOut
  hazmat_status: string | null
  bulky_status: string | null
  decision: string | null
}

export interface ProductsResponse {
  items: ProductListItem[]
}
