/** Mirrors of the backend response models (`interfaces/api/models.py`).
 *
 * `FieldValueOut.status` is the whole point: a sensitive value never travels
 * without the verification state that qualifies it (ADR-003/ADR-004), and this
 * app must never render one without the other.
 */
export type ProvenanceStatus = "VERIFIED" | "INFERRED" | "NOT_FOUND" | "INVALID"
export type Decision = "BUY" | "REVIEW" | "PASS"
export type SortDirection = "asc" | "desc"
export type RecordSort =
  | "record_ref" | "sku" | "asin" | "title" | "price" | "cog"
  | "decision" | "profit" | "roi" | "margin" | "hazmat" | "bulky"

export interface FieldValueOut {
  value: string | number | null
  status: ProvenanceStatus | null
  unit?: string | null
  raw_value?: string | null
}

export interface RecordOut {
  record_ref: string
  marketplace: string | null
  supplier_sku: string | null
  asin: FieldValueOut
  upc: FieldValueOut
  title: FieldValueOut
  brand: FieldValueOut
  category: FieldValueOut
  weight: FieldValueOut
  selling_price: FieldValueOut
  cog: string | null
  shipping_per_unit: string | null
  total_fees?: string | null
  profit: FieldValueOut
  roi: FieldValueOut
  margin: FieldValueOut
  break_even_price: FieldValueOut
  hazmat_status: string | null
  bulky_status: string | null
  decision: string | null
  decision_reasons: string[]
  issue_count: number
  issues: string[]
}

export interface RunSummaryOut {
  execution_id: string
  started_at: string
  finished_at: string | null
  status: string
  input_filename: string
  input_hash: string
  records_total: number
  records_processed: number
  records_successful: number
  records_with_errors: number
  warnings: number
  /** Stored-snapshot count per decision (API_CONTRACT §2b). Only keys that
   *  occur are present; "UNKNOWN" counts records without a decision. `null`
   *  (or absent, from an older API) = no snapshot stored: unknown, not zero. */
  decisions?: Record<string, number> | null
}

export interface RecordPaginationOut { limit: number; offset: number; total: number; has_more: boolean }
export interface RunRecordsResponse { execution_id: string; records: RecordOut[]; pagination: RecordPaginationOut }
export interface RunsListResponse { items: RunSummaryOut[] }

export interface CatalogQuery {
  limit: number
  offset: number
  search: string
  /** Exact, case-sensitive stored brand value (API_CONTRACT §2c); "" = all. */
  brand: string
  decision: string
  sort: RecordSort
  direction: SortDirection
  minRoi: string
  minProfit: string
  minMargin: string
  confidence: "VERIFIED_ONLY" | "INCLUDE_INFERRED"
  hazmat: string
  bulky: string
  provenanceField: string
  provenanceStatus: string
}

/** The `brands` projection of `GET /api/v1/runs/{id}/analytics` (§13): the top
 *  brands by record count (at most ten), how many distinct brands exist, and
 *  how many records have none. Only `label` values are valid `brand` filters. */
export interface BrandDistributionOut {
  items: { label: string; count: number }[]
  distinct: number
  not_recorded: number
}

export interface ThresholdsIn {
  target_profit: string
  target_roi: string
  minimum_estimated_monthly_sales: number
  maximum_risk_severity: string
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

/** One file's own outcome inside a batch. A REJECTED file never ran, so its
 *  counts stay 0 — "never processed", not a measured zero. */
export interface BatchFileOut {
  ordinal: number
  filename: string
  content_type: string | null
  size_bytes: number
  status: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED" | "REJECTED"
  execution_id: string | null
  warnings: string[]
  errors: string[]
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
  files: BatchFileOut[]
}

/** `POST /api/v1/runs/preview` (API_CONTRACT §1b): the importer's verdict on
 *  one file. Nothing is processed, decided or stored; there is no run. */
export interface PreviewColumnOut {
  position: number
  header: string
  normalized: string
  status: "MAPPED" | "UNKNOWN" | "DUPLICATE" | "BLANK"
  canonical: string | null
  alias_of: string | null
  /** MAPPED only. */
  target: string | null
  required: boolean
  group: "core" | "native_financial_evidence" | null
}

export interface ImportPreviewResponse {
  input_filename: string
  input_hash: string
  fatal: boolean
  rows_scanned: number
  rows_skipped_blank: number
  records_importable: number
  columns: PreviewColumnOut[]
  missing_required_columns: { canonical: string; target: string }[]
  issue_counts: { level: string; code: string; count: number }[]
  issues: { level: string; code: string; message: string; field: string | null; record_ref: string | null }[]
  issues_total: number
  issues_truncated: boolean
}
