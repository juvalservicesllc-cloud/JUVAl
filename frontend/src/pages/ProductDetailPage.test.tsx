import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { ProductDetailPage } from "./ProductDetailPage"
import type { RecordOut } from "../types"

const missing = { value: null, status: "NOT_FOUND" as const }
const record: RecordOut = {
  record_ref: "row-1", marketplace: "US", supplier_sku: "SKU-1",
  asin: { value: "B000000001", status: "VERIFIED" }, upc: missing,
  title: { value: "Fixture product", status: "VERIFIED" }, brand: { value: "Fixture brand", status: "VERIFIED" }, category: missing,
  weight: missing, height: missing, width: missing, length: missing,
  selling_price: { value: "20", status: "INFERRED" }, cog: "8", shipping_per_unit: "1",
  profit: { value: "4", status: "INFERRED" }, roi: { value: "0.5", status: "INFERRED" }, margin: { value: "0.2", status: "INFERRED" },
  break_even_price: missing, max_cog_target_profit: missing, max_cog_target_roi: missing,
  hazmat_status: "ABSENT", hazmat_severity: "NONE", bulky_status: "UNKNOWN", bulky_severity: null,
  decision: "REVIEW", decision_reasons: ["Fixture reason"], issue_count: 0, issues: [],
}

describe("ProductDetailPage", () => {
  it("renders the existing run-scoped detail route and labels fixture market data as non-verified", () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: "/runs/run-1/records/row-1", state: { record } }]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText("Fixture product")).toBeInTheDocument()
    expect(screen.getByText("DEMO_FIXTURE")).toBeInTheDocument()
    expect(screen.getByText(/not verified, not inferred/i)).toBeInTheDocument()
    expect(screen.getAllByRole("link", { name: /back to run detail/i })).toHaveLength(2)
    expect(screen.getAllByRole("link", { name: /back to run detail/i })[0]).toHaveAttribute("href", "/runs/run-1")
  })
})
