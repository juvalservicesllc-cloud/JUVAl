import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
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
  afterEach(() => vi.unstubAllGlobals())

  it("renders the existing run-scoped detail route and labels fixture market data as non-verified", () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: "/runs/run-1/records/row-1", state: { record } }]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )

    expect(screen.getAllByText("Fixture product")[0]).toBeInTheDocument()
    expect(screen.getByText("DEMO_FIXTURE")).toBeInTheDocument()
    expect(screen.getByText("NOT VERIFIED")).toBeInTheDocument()
    expect(screen.getByText("NOT INFERRED FROM PRODUCTION DATA")).toBeInTheDocument()
    expect(screen.getAllByRole("link", { name: /back to run detail/i })).toHaveLength(2)
    expect(screen.getAllByRole("link", { name: /back to run detail/i })[0]).toHaveAttribute("href", "/runs/run-1")
  })

  it("loads a direct link from the canonical endpoint, formats economics, and toggles the fixture chart", async () => {
    const provenance = { source: "supplier.xlsx", source_type: "SUPPLIER_FILE", verification_status: "VERIFIED" as const, retrieved_at: "2026-08-19T00:00:00Z", method: "direct_read", confidence: null, evidence: null, source_reference: "row=2" }
    const richRecord = { ...record, asin: { ...record.asin, provenance }, roi: { ...record.roi, provenance }, selling_price: { ...record.selling_price, provenance } }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => richRecord })
    vi.stubGlobal("fetch", fetchMock)
    render(
      <MemoryRouter initialEntries={["/runs/run-1/records/row-1"]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )

    expect((await screen.findAllByText("Fixture product"))[0]).toBeInTheDocument()
    // Economics and the provenance evidence summary both format the ratio.
    expect(screen.getAllByText("50.00%").length).toBeGreaterThan(0)
    expect(screen.getAllByText("supplier.xlsx")[0]).toBeInTheDocument()
    const bar = screen.getByRole("button", { name: "Bar" })
    await userEvent.click(bar)
    expect(bar).toHaveAttribute("aria-pressed", "true")
    expect(String(fetchMock.mock.calls[0][0])).toContain("/records/row-1")
  })

  it("renders a non-fabricated 404 state for a missing canonical record", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({ detail: "unknown record for execution" }) }))
    render(
      <MemoryRouter initialEntries={["/runs/run-1/records/missing"]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText("This record does not exist in the selected run.")).toBeInTheDocument())
  })
})

describe("ProductDetailPage source and economics recovery", () => {
  afterEach(() => vi.unstubAllGlobals())

  const provenance = {
    source: "supplier-q3.xlsx", source_type: "SUPPLIER_FILE", verification_status: "VERIFIED" as const,
    retrieved_at: "2026-08-19T00:00:00Z", method: "direct_read", confidence: null, evidence: null, source_reference: "row=7",
  }

  function renderRecord(value: RecordOut) {
    return render(
      <MemoryRouter initialEntries={[{ pathname: "/runs/run-1/records/row-1", state: { record: value } }]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )
  }

  it("reports the source file and row from stored provenance", () => {
    renderRecord({ ...record, asin: { ...record.asin, provenance } })

    expect(screen.getByText(/where this record came from/i)).toBeInTheDocument()
    expect(screen.getAllByText("supplier-q3.xlsx").length).toBeGreaterThan(0)
    expect(screen.getByText("7")).toBeInTheDocument()
  })

  it("says the source is unrecorded rather than inventing one for a legacy snapshot", () => {
    renderRecord(record)

    expect(screen.getAllByText(/not recorded on this snapshot/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/supplier-q3/)).not.toBeInTheDocument()
  })

  it("shows fees, seller proceeds and total landed cost when the snapshot stored them", () => {
    renderRecord({ ...record, total_fees: "5", seller_proceeds: "15", total_cost: "9" })

    expect(screen.getByText("Selling fees")).toBeInTheDocument()
    expect(screen.getByText("$5.00")).toBeInTheDocument()
    expect(screen.getByText("$15.00")).toBeInTheDocument()
    expect(screen.getByText("$9.00")).toBeInTheDocument()
  })

  it("shows an em dash, never $0.00, when those terms were not stored", () => {
    renderRecord(record)

    const feesValue = screen.getByText("Selling fees").nextElementSibling
    expect(feesValue).toHaveTextContent("—")
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument()
  })

  it("states that no canonical image or supplier link exists instead of showing an unverified one", () => {
    renderRecord(record)

    expect(screen.getByText(/no canonical product image/i)).toBeInTheDocument()
    expect(screen.getByText(/no supplier or marketplace URL is stored/i)).toBeInTheDocument()
    // No <img> at all: an absent image must never be filled with a stand-in.
    expect(document.querySelector("img")).toBeNull()
  })
})

describe("ProductDetailPage evidence precision", () => {
  afterEach(() => vi.unstubAllGlobals())

  // ROI is a division, so the persisted Decimal runs to dozens of digits.
  const noisyRoi = { value: "1.498333333333333333333333333", status: "VERIFIED" as const }

  function renderRecord(value: RecordOut) {
    return render(
      <MemoryRouter initialEntries={[{ pathname: "/runs/run-1/records/row-1", state: { record: value } }]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )
  }

  function roiEvidence(): HTMLElement {
    // The ROI entry in the provenance evidence list, not the Economics <dt>.
    return screen.getAllByText("ROI").find((node) => node.closest("summary"))!.closest("details")!
  }

  it("formats evidence summaries instead of dumping raw Decimal precision", () => {
    renderRecord({ ...record, roi: noisyRoi })

    const summary = within(roiEvidence()).getByText("ROI").closest("summary")!
    expect(summary).toHaveTextContent("149.83%")
    expect(summary).not.toHaveTextContent("1.4983333")
  })

  it("still discloses the exact stored value for auditing", () => {
    renderRecord({ ...record, roi: noisyRoi })

    const evidence = within(roiEvidence())
    expect(evidence.getByText("Stored value")).toBeInTheDocument()
    expect(evidence.getByText("1.498333333333333333333333333")).toBeInTheDocument()
  })
})

// C1.4 / C1.5 -- metric explanations and provenance-grouped confidence,
// recovered from the Golden Product Experience (ADR-029).
describe("ProductDetailPage explanations and confidence grouping (C1)", () => {
  afterEach(() => vi.unstubAllGlobals())

  function renderDetail() {
    return render(
      <MemoryRouter initialEntries={[{ pathname: "/runs/run-1/records/row-1", state: { record } }]}>
        <Routes><Route path="/runs/:executionId/records/:recordRef" element={<ProductDetailPage />} /></Routes>
      </MemoryRouter>,
    )
  }

  it("explains each economic metric without recommending or recomputing", async () => {
    renderDetail()
    const user = userEvent.setup()

    const triggers = screen.getAllByRole("group").filter((el) => el.className.includes("metric-explainer"))
    expect(triggers.length).toBeGreaterThanOrEqual(6)

    await user.click(screen.getByLabelText("What does ROI mean?"))
    const roiText = screen.getByText(/profit divided by the cost of goods/i)
    expect(roiText).toBeInTheDocument()
    // Definition only: never a buy/avoid recommendation.
    expect(roiText.textContent).not.toMatch(/should|recommend|good deal|avoid/i)
  })

  it("uses a native disclosure so the explanation works without hover", () => {
    renderDetail()

    const summary = screen.getByLabelText("What does Margin mean?")
    expect(summary.tagName).toBe("SUMMARY")
    expect(summary.closest("details")).toBeInTheDocument()
  })

  it("states that the decision comes from the backend engine, not the browser", () => {
    renderDetail()
    expect(screen.getByText(/never recalculated in the browser/i)).toBeInTheDocument()
  })

  it("groups the record's own fields by verification status", () => {
    renderDetail()

    expect(screen.getByText(/fields by confidence/i)).toBeInTheDocument()
    const verified = screen.getByText("Verified").closest("section") as HTMLElement
    expect(within(verified).getByText("ASIN")).toBeInTheDocument()
    const inferred = screen.getByText("Inferred").closest("section") as HTMLElement
    expect(within(inferred).getByText("Profit")).toBeInTheDocument()
    const notFound = screen.getByText("Not found").closest("section") as HTMLElement
    expect(within(notFound).getByText("UPC")).toBeInTheDocument()
  })

  it("never promotes a fixture or an inferred value into VERIFIED", () => {
    renderDetail()

    const verified = screen.getByText("Verified").closest("section") as HTMLElement
    // selling_price/profit/roi/margin are INFERRED on this record.
    expect(within(verified).queryByText("Selling price")).not.toBeInTheDocument()
    expect(within(verified).queryByText("Profit")).not.toBeInTheDocument()
  })
})
