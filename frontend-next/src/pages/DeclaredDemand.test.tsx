import { render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { RecordOut } from "../api/types"
import { CatalogPage } from "./CatalogPage"
import { DeclaredDemandCell, DeclaredDemandPanel } from "./DeclaredDemand"
import { ImportPreview } from "./ImportPreview"
import { ProductDetailPage } from "./ProductDetailPage"

const provenance = { source: "demand.csv", source_type: "USER_INPUT", verification_status: "INFERRED", retrieved_at: "2026-10-26T15:00:00+00:00",
  method: "supplier POS export", evidence: "declared in uploaded file; author not accredited; not verified", source_reference: "row=2;column=estimated_monthly_sales" }
const observation = (value: unknown) => ({
  observation_id: "row_2#ESTIMATED_SALES#1", metric: "ESTIMATED_SALES", value,
  observed_at: "2026-10-01T00:00:00-04:00", window: { start: "2026-09-01T00:00:00-04:00", end: "2026-10-01T00:00:00-04:00" },
  window_source: "EXPLICIT", declared_month: null, declared_timezone: null, population_definition: "all sellers of this listing on amazon.com",
})
const doc = (observations: unknown[], diagnostics: unknown[] = []) => ({ format: "juval.adr046.demand-evidence", version: 1, captured_at: "2026-10-26T15:00:00+00:00", observations, diagnostics })
const none = { value: null, status: null }
const base = {
  record_ref: "row_2", marketplace: "US", supplier_sku: null, asin: none, upc: none, title: { value: "Widget", status: "VERIFIED" }, brand: none, category: none, weight: none,
  selling_price: none, cog: "3", shipping_per_unit: null, profit: none, roi: none, margin: none, break_even_price: none, hazmat_status: "ABSENT", bulky_status: "ABSENT",
  decision: "REVIEW", decision_reasons: ["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."], decision_reason_codes: ["DEMAND_UNKNOWN"],
  review_classification: "PENDING_DEMAND_VERIFICATION", issue_count: 0, issues: [],
}
const record = (extra: Partial<RecordOut> | Record<string, unknown>) => ({ ...base, ...extra }) as unknown as RecordOut
const inferred = record({ demand_evidence_state: "DECLARED", demand_evidence: doc([observation({ value: 1000000, status: "INFERRED", unit: "units", raw_value: null, provenance })]) })
const invalid = record({ demand_evidence_state: "DECLARED", demand_evidence: doc([observation({ value: null, status: "INVALID", unit: null, raw_value: "approx 400", provenance: { ...provenance, verification_status: "INVALID" } })],
  [{ code: "DEMAND_VALUE_INVALID", column: "estimated_monthly_sales", row: 2, raw_value: "approx 400", message: "estimated sales must be a whole number >= 0; kept as raw" }]) })
const notFound = record({ demand_evidence_state: "DECLARED", demand_evidence: doc([observation({ value: null, status: "NOT_FOUND", unit: null, raw_value: null, provenance: { ...provenance, verification_status: "NOT_FOUND" } })]) })
const unusable = record({ demand_evidence_state: "DECLARED", demand_evidence: doc([], [
  { code: "DEMAND_VALUE_NOT_USABLE", column: "estimated_monthly_sales", row: 2, raw_value: "420", message: "declared value kept as raw; its context is incomplete or invalid" },
  { code: "DEMAND_CONTEXT_MISSING", column: "demand_observed_at", row: 2, raw_value: null, message: "demand_observed_at not declared; the import time never substitutes for it" },
]) })

describe("Declared demand is shown as evidence, never as a decision input", () => {
  afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear() })

  it("shows the declared value with its INFERRED status, context, source and method, and says it is not used", () => {
    render(<DeclaredDemandPanel record={inferred} />)
    const panel = screen.getByLabelText("Declared demand")
    expect(within(panel).getByText("Not used for this decision")).toBeInTheDocument()
    expect(panel).toHaveTextContent("1,000,000 units")
    expect(within(panel).getByLabelText("Status: INFERRED")).toBeInTheDocument()
    expect(panel).toHaveTextContent("2026-09-01T00:00:00-04:00 → 2026-10-01T00:00:00-04:00")
    expect(panel).toHaveTextContent("all sellers of this listing on amazon.com")
    expect(panel).toHaveTextContent("supplier POS export")
    expect(panel).toHaveTextContent("USER_INPUT · demand.csv · row=2;column=estimated_monthly_sales")
    expect(panel).not.toHaveTextContent("VERIFIED")
  })

  it("keeps an invalid value raw and lists its diagnostic", () => {
    render(<DeclaredDemandPanel record={invalid} />)
    const panel = screen.getByLabelText("Declared demand")
    expect(panel).toHaveTextContent("Invalid value")
    expect(panel).toHaveTextContent("raw approx 400")
    expect(within(screen.getByRole("table", { name: "Declared demand diagnostics" })).getByText("DEMAND_VALUE_INVALID")).toBeInTheDocument()
  })

  it("shows a NOT_FOUND declaration as no value, never zero", () => {
    render(<DeclaredDemandPanel record={notFound} />)
    const panel = screen.getByLabelText("Declared demand")
    expect(panel).toHaveTextContent("No value declared")
    expect(within(panel).getByLabelText("Status: NOT FOUND")).toBeInTheDocument()
    expect(panel).not.toHaveTextContent(/\b0 units/)
  })

  it("explains an unusable declaration through its diagnostics", () => {
    render(<DeclaredDemandPanel record={unusable} />)
    expect(screen.getByText(/No usable declaration/)).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Declared demand diagnostics" })).toHaveTextContent("DEMAND_CONTEXT_MISSING")
  })

  it("distinguishes a file without demand columns from a record captured before the feature", () => {
    const { unmount } = render(<DeclaredDemandPanel record={record({ demand_evidence: null, demand_evidence_state: "NOT_DECLARED" })} />)
    expect(screen.getByText("The file declared no demand columns.")).toBeInTheDocument()
    unmount()
    render(<DeclaredDemandPanel record={record({})} />)
    expect(screen.getByText(/processed before declared demand was captured/)).toBeInTheDocument()
  })

  it("renders compact Catalog cells without inventing values", () => {
    const cell = (r: RecordOut) => { const { container, unmount } = render(<DeclaredDemandCell record={r} />); const text = container.textContent; unmount(); return text }
    expect(cell(inferred)).toBe("1,000,000 INF")
    expect(cell(invalid)).toBe("invalid INV")
    expect(cell(notFound)).toBe("no value N/F")
    expect(cell(unusable)).toBe("not usable")
    expect(cell(record({}))).toBe("—")
  })

  it("adds a non-sortable Declared demand column to the Catalog", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      const path = new URL(String(url)).pathname
      const body = path.endsWith("/records") ? { execution_id: "r1", records: [inferred], pagination: { limit: 25, offset: 0, total: 1, has_more: false } }
        : path.endsWith("/analytics") ? { brands: { items: [], distinct: 0, not_recorded: 1 } }
        : { items: [{ execution_id: "r1", started_at: "2026-10-26T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "demand.csv", input_hash: "h", records_total: 1, records_processed: 1, records_successful: 1, records_with_errors: 0, warnings: 0 }] }
      return Promise.resolve(new Response(JSON.stringify(body)))
    }))
    render(<CatalogPage />)
    const header = await screen.findByRole("columnheader", { name: "Declared demand" })
    expect(within(header).queryByRole("button")).toBeNull()
    const row = (await screen.findByText("Widget")).closest("tr") as HTMLElement
    expect(row).toHaveTextContent("1,000,000")
    expect(within(row).getByText("▲ REVIEW")).toBeInTheDocument()                 // the decision is the engine's
  })

  it("keeps REVIEW on Product Detail beside the declared value", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(String(url).endsWith("/financial")
      ? { execution_id: "r1", record_ref: "row_2", financial_document: null, capture_diagnostics: null, inconsistencies: [] } : inferred)))))
    render(<ProductDetailPage executionId="r1" recordRef="row_2" go={vi.fn()} />)
    const decision = await screen.findByLabelText("Decision")
    expect(within(decision).getByText("▲ REVIEW")).toBeInTheDocument()
    expect(within(screen.getByLabelText("Declared demand")).getByText("Not used for this decision")).toBeInTheDocument()
  })

  it("labels declared demand columns in the import preview as not affecting decisions", () => {
    render(<ImportPreview onClose={vi.fn()} preview={{
      input_filename: "demand.csv", input_hash: "h", fatal: false, rows_scanned: 1, rows_skipped_blank: 0, records_importable: 1, issues_total: 0, issues_truncated: false,
      issue_counts: [], issues: [], missing_required_columns: [],
      columns: [{ position: 7, header: "estimated_monthly_sales", normalized: "estimated_monthly_sales", status: "MAPPED", canonical: "demand_estimated_sales",
        alias_of: "estimated_monthly_sales", target: "declared_demand.estimated_sales", required: false, group: "declared_demand" }],
    } as never} />)
    expect(screen.getByText(/declared demand, does not affect decisions/)).toBeInTheDocument()
  })
})
