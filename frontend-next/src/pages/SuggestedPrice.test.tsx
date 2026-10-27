import { render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { RecordOut } from "../api/types"
import { CatalogPage } from "./CatalogPage"
import { ImportPreview } from "./ImportPreview"
import { ProductDetailPage } from "./ProductDetailPage"
import { SuggestedPriceCell, SuggestedPricePanel } from "./SuggestedPrice"

const provenance = { source: "price.csv", source_type: "USER_INPUT", verification_status: "INFERRED", retrieved_at: "2026-10-27T15:00:00+00:00",
  method: "declared_in_uploaded_file", evidence: "declared in uploaded file as the supplier's suggested price; author not accredited; not verified; not a selling price or cost",
  source_reference: "row=2;column=supplier_suggested_price" }
const doc = (amount: unknown, currency_raw: string | null, diagnostics: unknown[] = []) => ({ format: "juval.supplier-suggested-price", version: 1, amount, currency_raw, diagnostics })
const none = { value: null, status: null }
const base = {
  record_ref: "row_2", marketplace: "US", supplier_sku: null, asin: none, upc: none, title: { value: "Widget", status: "VERIFIED" }, brand: none, category: none, weight: none,
  selling_price: { value: "30", status: "VERIFIED" }, cog: "3", shipping_per_unit: null, profit: none, roi: none, margin: none, break_even_price: none,
  hazmat_status: "ABSENT", bulky_status: "ABSENT", decision: "REVIEW", decision_reasons: ["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."],
  decision_reason_codes: ["DEMAND_UNKNOWN"], review_classification: "PENDING_DEMAND_VERIFICATION", issue_count: 0, issues: [],
}
const record = (extra: Record<string, unknown>) => ({ ...base, ...extra }) as unknown as RecordOut
const declared = (amount: unknown, currency: string | null, diagnostics: unknown[] = []) =>
  record({ supplier_suggested_price_state: "DECLARED", supplier_suggested_price: doc(amount, currency, diagnostics) })
const inferred = declared({ value: "24.99", status: "INFERRED", unit: "EUR", raw_value: null, provenance }, "EUR")
const invalid = declared({ value: null, status: "INVALID", unit: null, raw_value: "24.99", provenance: { ...provenance, verification_status: "INVALID" } }, "usd",
  [{ code: "SUGGESTED_PRICE_CURRENCY_INVALID", column: "supplier_suggested_price_currency", row: 2, raw_value: "usd", message: "supplier_suggested_price_currency must be three uppercase letters (e.g. USD); not converted" }])
const notFound = declared({ value: null, status: "NOT_FOUND", unit: null, raw_value: null, provenance: { ...provenance, verification_status: "NOT_FOUND" } }, null)

describe("The supplier suggested price is shown as evidence, never as a price or cost input", () => {
  afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear() })

  it("shows the exact amount with its declared currency, INFERRED status and provenance", () => {
    render(<SuggestedPricePanel record={inferred} />)
    const panel = screen.getByLabelText("Supplier suggested price")
    expect(within(panel).getByText("Not used for this decision")).toBeInTheDocument()
    expect(panel).toHaveTextContent("24.99 EUR")
    expect(panel).not.toHaveTextContent("$")                                   // no currency is assumed
    expect(within(panel).getByLabelText("Status: INFERRED")).toBeInTheDocument()
    expect(panel).toHaveTextContent("USER_INPUT · price.csv · row=2;column=supplier_suggested_price")
    expect(panel).toHaveTextContent("Its author is not accredited")
    expect(panel).toHaveTextContent("declared_in_uploaded_file")
    expect(panel).not.toHaveTextContent("VERIFIED")
  })

  it("keeps an unusable amount raw, with its raw currency and diagnostic", () => {
    render(<SuggestedPricePanel record={invalid} />)
    const panel = screen.getByLabelText("Supplier suggested price")
    expect(panel).toHaveTextContent("Invalid value")
    expect(panel).toHaveTextContent("raw 24.99")
    expect(panel).toHaveTextContent("usd")
    expect(within(screen.getByRole("table", { name: "Supplier suggested price diagnostics" })).getByText("SUGGESTED_PRICE_CURRENCY_INVALID")).toBeInTheDocument()
  })

  it("shows an empty amount as no value, never zero", () => {
    render(<SuggestedPricePanel record={notFound} />)
    const panel = screen.getByLabelText("Supplier suggested price")
    expect(panel).toHaveTextContent("No value declared")
    expect(within(panel).getByLabelText("Status: NOT FOUND")).toBeInTheDocument()
    expect(panel).not.toHaveTextContent(/\b0(\.00)?\b/)
  })

  it("distinguishes a file without the columns from a record captured before the feature", () => {
    const { unmount } = render(<SuggestedPricePanel record={record({ supplier_suggested_price: null, supplier_suggested_price_state: "NOT_DECLARED" })} />)
    expect(screen.getByText("The file had no supplier suggested price columns.")).toBeInTheDocument()
    unmount()
    render(<SuggestedPricePanel record={record({})} />)
    expect(screen.getByText(/processed before the supplier suggested price was captured/)).toBeInTheDocument()
  })

  it("renders compact Catalog cells without inventing values", () => {
    const cell = (r: RecordOut) => { const { container, unmount } = render(<SuggestedPriceCell record={r} />); const text = container.textContent; unmount(); return text }
    expect(cell(inferred)).toBe("24.99 EUR INF")
    expect(cell(invalid)).toBe("invalid INV")
    expect(cell(notFound)).toBe("no value N/F")
    expect(cell(record({}))).toBe("—")
  })

  it("adds a non-sortable column between Cost and Selling in the Catalog; the decision and selling price stay the engine's", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      const path = new URL(String(url)).pathname
      const body = path.endsWith("/records") ? { execution_id: "r1", records: [inferred], pagination: { limit: 25, offset: 0, total: 1, has_more: false } }
        : path.endsWith("/analytics") ? { brands: { items: [], distinct: 0, not_recorded: 1 } }
        : { items: [{ execution_id: "r1", started_at: "2026-10-27T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "price.csv", input_hash: "h", records_total: 1, records_processed: 1, records_successful: 1, records_with_errors: 0, warnings: 0 }] }
      return Promise.resolve(new Response(JSON.stringify(body)))
    }))
    render(<CatalogPage />)
    const header = await screen.findByRole("columnheader", { name: "Suggested (supplier)" })
    expect(within(header).queryByRole("button")).toBeNull()
    const labels = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "")
    const at = labels.indexOf("Suggested (supplier)")
    expect(labels[at - 1]).toMatch(/^Cost/)
    expect(labels[at + 1]).toMatch(/^Selling/)
    const row = (await screen.findByText("Widget")).closest("tr") as HTMLElement
    expect(row).toHaveTextContent("24.99 EUR")
    expect(row).toHaveTextContent("$30.00")
    expect(within(row).getByText("▲ REVIEW")).toBeInTheDocument()
  })

  it("shows the panel on Product Detail beside the engine's REVIEW", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(String(url).endsWith("/financial")
      ? { execution_id: "r1", record_ref: "row_2", financial_document: null, capture_diagnostics: null, inconsistencies: [] } : inferred)))))
    render(<ProductDetailPage executionId="r1" recordRef="row_2" go={vi.fn()} />)
    const decision = await screen.findByLabelText("Decision")
    expect(within(decision).getByText("▲ REVIEW")).toBeInTheDocument()
    const panel = screen.getByLabelText("Supplier suggested price")
    expect(panel).toHaveTextContent("24.99 EUR")
    expect(within(panel).getByText("Not used for this decision")).toBeInTheDocument()
  })

  it("labels the columns in the import preview as not affecting decisions", () => {
    render(<ImportPreview onClose={vi.fn()} preview={{
      input_filename: "price.csv", input_hash: "h", fatal: false, rows_scanned: 1, rows_skipped_blank: 0, records_importable: 1, issues_total: 0, issues_truncated: false,
      issue_counts: [], issues: [], missing_required_columns: [],
      columns: [{ position: 7, header: "supplier_suggested_price", normalized: "supplier_suggested_price", status: "MAPPED", canonical: "supplier_suggested_price",
        alias_of: null, target: "supplier_suggested_price.amount", required: false, group: "supplier_suggested_price" }],
    } as never} />)
    expect(screen.getByText(/supplier suggested price, does not affect decisions/)).toBeInTheDocument()
  })
})
