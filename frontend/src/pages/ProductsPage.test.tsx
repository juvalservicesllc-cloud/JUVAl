import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProductsPage } from "./ProductsPage"

const run = { execution_id: "r1", started_at: "2026-08-18T12:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "catalog.xlsx", input_hash: "x", records_total: 2, records_processed: 2, records_successful: 2, records_with_errors: 0, warnings: 0 }
const empty = { value: null, status: null }
const records = ["VERIFIED", "INFERRED"].map((status, index) => ({ record_ref: `row-${index}`, marketplace: "US", supplier_sku: `SKU-${index}`, asin: { value: `ASIN-${index}`, status }, upc: empty, title: { value: index ? "Beta" : "Alpha", status }, brand: { value: "Brand", status }, category: empty, weight: empty, height: empty, width: empty, length: empty, selling_price: empty, cog: null, shipping_per_unit: null, profit: { value: index ? "8" : "2", status }, roi: { value: index ? "0.4" : "0.1", status }, margin: empty, break_even_price: empty, max_cog_target_profit: empty, max_cog_target_roi: empty, hazmat_status: "ABSENT", hazmat_severity: "NONE", bulky_status: "UNKNOWN", bulky_severity: null, decision: index ? "BUY" : "REVIEW", decision_reasons: [], issue_count: 0, issues: [] }))

describe("ProductsPage", () => {
  afterEach(() => vi.unstubAllGlobals())
  it("uses persisted run records, keeps provenance visible, and filters real records", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve({ ok: true, status: 200, json: async () => url.includes("/records") ? { execution_id: "r1", records } : { items: [run] } })))
    const user = userEvent.setup(); render(<ProductsPage />)
    expect(await screen.findByText("Alpha")).toBeInTheDocument()
    expect(screen.getAllByText("VERIFIED").length).toBeGreaterThan(0); expect(screen.getAllByText("INFERRED").length).toBeGreaterThan(0)
    await user.selectOptions(screen.getByLabelText(/filter by decision/i), "BUY")
    await waitFor(() => expect(screen.queryByText("Alpha")).not.toBeInTheDocument())
    expect(screen.getByText("Beta")).toBeInTheDocument()
  })
})
