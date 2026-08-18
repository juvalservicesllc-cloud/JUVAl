import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { ResultsTable } from "./ResultsTable"
import type { RecordOut } from "../types"

const empty = { value: null, status: null }

function record(overrides: Partial<RecordOut>): RecordOut {
  return {
    record_ref: "row_2:SUP-001",
    marketplace: "US",
    supplier_sku: "SUP-001",
    asin: empty,
    upc: empty,
    weight: empty,
    selling_price: empty,
    cog: null,
    shipping_per_unit: null,
    profit: empty,
    roi: empty,
    margin: empty,
    break_even_price: empty,
    max_cog_target_profit: empty,
    max_cog_target_roi: empty,
    hazmat_status: null,
    hazmat_severity: null,
    bulky_status: null,
    bulky_severity: null,
    decision: null,
    decision_reasons: [],
    issue_count: 0,
    issues: [],
    ...overrides,
  }
}

describe("ResultsTable", () => {
  it("never collapses a FieldValue to a bare value -- value and verification_status always render together", () => {
    render(
      <ResultsTable
        records={[record({ asin: { value: "B0TESTAAA1", status: "VERIFIED" } })]}
      />,
    )
    expect(screen.getByText(/B0TESTAAA1/)).toBeInTheDocument()
    expect(screen.getByLabelText("Status: VERIFIED")).toBeInTheDocument()
  })

  it("shows NOT_FOUND explicitly instead of hiding a missing value", () => {
    render(
      <ResultsTable
        records={[record({ asin: { value: null, status: "NOT_FOUND" } })]}
      />,
    )
    expect(screen.getByLabelText("Status: NOT FOUND")).toBeInTheDocument()
  })

  it("shows decision reasons and issues when present", () => {
    render(
      <ResultsTable
        records={[
          record({
            decision: "PASS",
            decision_reasons: ["RISK_ABOVE_MAXIMUM: HAZMAT is PRESENT with severity HIGH"],
            issue_count: 1,
            issues: ["[WARNING] STALE_DATA: weight was retrieved 40 days ago"],
          }),
        ]}
      />,
    )
    expect(screen.getByText("PASS")).toBeInTheDocument()
    expect(screen.getByText(/RISK_ABOVE_MAXIMUM/)).toBeInTheDocument()
    expect(screen.getByText(/STALE_DATA/)).toBeInTheDocument()
  })
})
