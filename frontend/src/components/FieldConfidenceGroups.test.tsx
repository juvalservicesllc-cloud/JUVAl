import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { FieldConfidenceGroups } from "./FieldConfidenceGroups"
import type { RecordOut } from "../types"

// C1.5 -- record fields grouped by verification status, recovered from Golden.
const empty = { value: null, status: null }
function recordWith(overrides: Partial<RecordOut>): RecordOut {
  return {
    record_ref: "row-1", marketplace: "US", supplier_sku: "SKU-1",
    asin: { value: "B0TEST", status: "VERIFIED" }, upc: empty,
    title: { value: "Widget", status: "VERIFIED" }, brand: empty, category: empty,
    weight: { value: null, status: "NOT_FOUND" }, height: empty, width: empty, length: empty,
    selling_price: { value: "19.99", status: "VERIFIED" }, cog: null, shipping_per_unit: null,
    profit: { value: "8.99", status: "INFERRED" }, roi: { value: "0.4", status: "INFERRED" },
    margin: empty, break_even_price: empty, max_cog_target_profit: empty, max_cog_target_roi: empty,
    hazmat_status: "ABSENT", hazmat_severity: "NONE", bulky_status: "ABSENT", bulky_severity: null,
    decision: "REVIEW", decision_reasons: [], issue_count: 0, issues: [],
    ...overrides,
  } as unknown as RecordOut
}

describe("FieldConfidenceGroups", () => {
  it("groups each field under its own status, counted in text not colour", () => {
    render(<FieldConfidenceGroups record={recordWith({})} />)

    const verified = screen.getByText("Verified").closest("section") as HTMLElement
    expect(within(verified).getByText("ASIN")).toBeInTheDocument()
    expect(within(verified).getByText("Title")).toBeInTheDocument()
    expect(within(verified).getByText("Selling price")).toBeInTheDocument()
    expect(within(verified).getByText("3")).toBeInTheDocument()

    const inferred = screen.getByText("Inferred").closest("section") as HTMLElement
    expect(within(inferred).getByText("Profit")).toBeInTheDocument()
    expect(within(inferred).getByText("ROI")).toBeInTheDocument()

    const notFound = screen.getByText("Not found").closest("section") as HTMLElement
    expect(within(notFound).getByText("Weight")).toBeInTheDocument()
  })

  it("keeps 'not recorded' separate from 'not found'", () => {
    render(<FieldConfidenceGroups record={recordWith({})} />)

    // status null means the snapshot carries no entry -- a different claim
    // from a field that was looked for and not found.
    const unrecorded = screen.getByText("Not recorded").closest("section") as HTMLElement
    expect(within(unrecorded).getByText("UPC")).toBeInTheDocument()
    expect(within(unrecorded).queryByText("Weight")).not.toBeInTheDocument()
  })

  it("explains what each status means, so trust is not inferred from colour", () => {
    render(<FieldConfidenceGroups record={recordWith({})} />)

    expect(screen.getByText(/evidence was sufficient from a trusted source/i)).toBeInTheDocument()
    expect(screen.getByText(/derived by rule or heuristic/i)).toBeInTheDocument()
    expect(screen.getByText(/never defaulted to zero/i)).toBeInTheDocument()
  })

  it("never invents a status for a field the backend did not classify", () => {
    render(<FieldConfidenceGroups record={recordWith({ asin: empty, title: empty, selling_price: empty } as Partial<RecordOut>)} />)

    expect(screen.queryByText("Verified")).not.toBeInTheDocument()
  })
})
