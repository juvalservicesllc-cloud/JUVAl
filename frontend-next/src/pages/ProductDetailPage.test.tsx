import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { App } from "../app/App"
import { ProductDetailPage } from "./ProductDetailPage"

const prov = (row = 2) => ({ source: "supplier.xlsx", source_type: "SUPPLIER_FILE", verification_status: "VERIFIED", retrieved_at: "2026-10-26T10:00:00Z", method: "direct_read", source_reference: `row=${row}` })
const verified = (value: string, unit: string | null = null) => ({ value, status: "VERIFIED", unit, raw_value: null, provenance: prov() })
const none = { value: null, status: null }
const record = {
  record_ref: "row_2:SUP-001", marketplace: "US", supplier_sku: "SUP-001",
  asin: verified("B0TESTAAA1"), upc: { value: null, status: "INVALID", raw_value: "12AB", provenance: prov() },
  title: verified("Widget Alpha"), brand: verified("Acme"), category: verified("Home"), weight: verified("1.5", "lb"),
  height: none, width: none, length: none,
  selling_price: verified("19.99"), cog: "5", shipping_per_unit: null,
  total_fees: null, seller_proceeds: null, total_cost: null,
  profit: verified("8.99"), roi: { value: "1.498333333333333333333333333", status: "VERIFIED", provenance: prov() },
  margin: { value: "0.45", status: "INFERRED", provenance: { ...prov(), method: "rule" } },
  break_even_price: { value: null, status: "NOT_FOUND", provenance: null },
  max_cog_target_profit: verified("9.99"), max_cog_target_roi: none,
  hazmat_status: "PRESENT", hazmat_severity: "HIGH", bulky_status: "ABSENT", bulky_severity: "NONE",
  decision: "PASS", decision_reasons: ["HazMat severity HIGH exceeds maximum LOW"], issue_count: 1, issues: ["UPC has an invalid format"], issue_codes: ["INVALID_UPC_FORMAT"],
}
const noFinancial = { execution_id: "run-1", record_ref: record.record_ref, financial_document: null, capture_diagnostics: null, inconsistencies: [] }

const json = (status: number, body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status }))
function stub({ recordStatus = 200, financial = noFinancial as unknown, financialStatus = 200, body = record as unknown } = {}) {
  const mock = vi.fn((url: string) => {
    const path = new URL(String(url)).pathname
    if (path.endsWith("/auth/session")) return json(200, { authenticated: false })
    if (path.endsWith("/financial")) return json(financialStatus, financial)
    return recordStatus === 200 ? json(200, body) : json(recordStatus, { detail: recordStatus === 404 ? "unknown record for execution" : "internal server error" })
  })
  vi.stubGlobal("fetch", mock)
  return mock
}
const page = (go = vi.fn()) => render(<ProductDetailPage executionId="run-1" recordRef="row_2:SUP-001" go={go} />)

describe("Product Detail (one record within one run)", () => {
  afterEach(() => { vi.unstubAllGlobals(); history.pushState({}, "", "/") })

  it("loads the snapshot by its encoded composite identity and its stored evidence", async () => {
    const mock = stub()
    page()
    expect(screen.getByText("Loading record…")).toBeInTheDocument()
    await screen.findByRole("heading", { name: "Widget Alpha" })
    await waitFor(() => expect(mock).toHaveBeenCalledTimes(2))
    expect(mock.mock.calls.map((c) => new URL(String(c[0])).pathname)).toEqual([
      "/api/v1/runs/run-1/records/row_2%3ASUP-001",
      "/api/v1/runs/run-1/records/row_2%3ASUP-001/financial",
    ])
  })

  it("leads with the engine's decision, its reasons and risk severity", async () => {
    stub()
    page()
    const decision = await screen.findByLabelText("Decision")
    expect(within(decision).getByText("■ PASS")).toBeInTheDocument()
    expect(within(decision).getByText("HazMat severity HIGH exceeds maximum LOW")).toBeInTheDocument()
    expect(within(screen.getByLabelText("Risks")).getByText("HIGH")).toBeInTheDocument()
  })

  it("says where each risk severity comes from, as the backend stored it (ADR-020)", async () => {
    stub({ body: { ...record, hazmat_severity_status: "INFERRED", hazmat_severity_source_type: "CALCULATED",
      bulky_severity_status: "VERIFIED", bulky_severity_source_type: "SUPPLIER_FILE" } })
    page()
    const risks = await screen.findByLabelText("Risks")
    expect(within(risks).getByText("HIGH")).toBeInTheDocument()
    expect(within(risks).getByLabelText("HazMat severity provenance: JUVAl classification (inferred)")).toHaveTextContent("JUVAl classification (inferred)")
    expect(within(risks).getByLabelText("Bulky severity provenance: Absence declared in supplier file")).toHaveTextContent("Absence declared in supplier file")
    expect(risks.textContent).not.toMatch(/verified by amazon|VERIFIED_SOURCE/i)
  })

  it("shows a not-found and an invalid severity source without guessing", async () => {
    stub({ body: { ...record, hazmat_status: "UNKNOWN", hazmat_severity: null, hazmat_severity_status: "NOT_FOUND", hazmat_severity_source_type: "NOT_FOUND",
      bulky_status: "UNKNOWN", bulky_severity: null, bulky_severity_status: "INVALID", bulky_severity_source_type: "SUPPLIER_FILE" } })
    page()
    const risks = await screen.findByLabelText("Risks")
    expect(within(risks).getByLabelText("HazMat severity provenance: Not found")).toBeInTheDocument()
    expect(within(risks).getByLabelText("Bulky severity provenance: Invalid in supplier file")).toBeInTheDocument()
  })

  it("keeps a historical snapshot without severity provenance as it was", async () => {
    stub()  // `record` predates the fields
    page()
    const risks = await screen.findByLabelText("Risks")
    expect(within(risks).getByText("HIGH")).toBeInTheDocument()
    expect(within(risks).queryByLabelText(/severity provenance/)).not.toBeInTheDocument()
    expect(within(risks).getByText(/not verified externally/)).toBeInTheDocument()
  })

  it("keeps every value beside its own verification status and never shows a missing amount as zero", async () => {
    stub()
    page()
    const economics = await screen.findByLabelText("Economics")
    const card = (label: string) => within(economics).getByText(label).closest("article") as HTMLElement
    expect(card("Profit")).toHaveTextContent("$8.99")
    expect(within(card("Profit")).getByLabelText("Status: VERIFIED")).toBeInTheDocument()
    expect(card("ROI")).toHaveTextContent("149.8%")
    expect(within(card("Margin")).getByLabelText("Status: INFERRED")).toBeInTheDocument()   // inferred stays inferred
    expect(card("Break-even price")).toHaveTextContent("No value")
    expect(within(card("Break-even price")).getByLabelText("Status: NOT FOUND")).toBeInTheDocument()
    expect(card("Selling fees")).toHaveTextContent("Not stored")
    expect(card("Selling fees")).not.toHaveTextContent("$0")
    expect(card("Max COG (target ROI)")).toHaveTextContent("Not recorded")
  })

  it("explains each metric on demand", async () => {
    stub()
    page()
    const economics = await screen.findByLabelText("Economics")
    const profit = within(economics).getByText("Profit").closest("article") as HTMLElement
    await userEvent.setup().click(within(profit).getByText("What does this mean?"))
    expect(within(profit).getByText(/computed by the backend Profitability Engine/)).toBeVisible()
  })

  it("names the source file and row from stored provenance", async () => {
    stub()
    page()
    const source = await screen.findByLabelText("Source")
    expect(source).toHaveTextContent("supplier.xlsx")
    expect(source).toHaveTextContent("2")
    expect(source).toHaveTextContent("SUPPLIER_FILE")
  })

  it("groups fields by the status they carry, including the ones never recorded", async () => {
    stub()
    page()
    await screen.findByLabelText("Data quality")
    expect(screen.getByLabelText("Verified fields")).toHaveTextContent("Title, Brand, Category, ASIN, Weight, Selling price, Profit, ROI, Max COG (target profit)")
    expect(screen.getByLabelText("Inferred fields")).toHaveTextContent("Margin")
    expect(screen.getByLabelText("Not found fields")).toHaveTextContent("Break-even price")
    expect(screen.getByLabelText("Invalid fields")).toHaveTextContent("UPC")
    expect(screen.getByLabelText("Not recorded fields")).toHaveTextContent("Height, Width, Length, Max COG (target ROI)")
    expect(screen.getByText("UPC has an invalid format")).toBeInTheDocument()
  })

  it("discloses raw and exact stored values in the evidence", async () => {
    stub()
    page()
    await screen.findByText("Evidence by field")
    expect(screen.getByText("12AB")).toBeInTheDocument()                                // INVALID keeps its raw value
    expect(screen.getByText("1.498333333333333333333333333")).toBeInTheDocument()       // exact ROI behind the 149.8%
  })

  it("shows no image, link or market series it has no approved source for", async () => {
    stub()
    page()
    await screen.findByLabelText("Identity")
    expect(document.querySelector("img")).toBeNull()
    expect(screen.queryByText(/demo|fixture|price trend|simulated/i)).not.toBeInTheDocument()
    expect(screen.getByText(/no product image or supplier link is shown/i)).toBeInTheDocument()
  })

  it("says plainly when no financial evidence was stored", async () => {
    stub()
    page()
    expect(await screen.findByText(/no financial document was stored for this record/i)).toBeInTheDocument()
  })

  it("shows a stored document as stored, and its disagreements without choosing a side", async () => {
    stub({ financial: { ...noFinancial, financial_document: { format: "juval.adr047.financial-record", version: 2, payload: { scenario: "declared" } }, inconsistencies: ["document says 2 lines, diagnostics 3"] } })
    page()
    expect(await screen.findByText("Financial document: original stored JSON (juval.adr047.financial-record v2)")).toBeInTheDocument()
    expect(screen.getByText("document says 2 lines, diagnostics 3")).toBeInTheDocument()
  })

  it("keeps the record visible when its evidence cannot be loaded", async () => {
    stub({ financialStatus: 500, financial: { detail: "internal server error" } })
    page()
    expect(await screen.findByText(/could not be loaded; nothing is assumed/i)).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Widget Alpha" })).toBeInTheDocument()
  })

  it("reports an unknown run or record as not found, without a retry", async () => {
    stub({ recordStatus: 404 })
    const go = vi.fn()
    page(go)
    expect(await screen.findByRole("heading", { name: "Record not found" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: "Back to Catalog" }))
    expect(go).toHaveBeenCalledWith("/catalog?run=run-1")
  })

  it("offers a retry on a server failure", async () => {
    const mock = stub({ recordStatus: 500 })
    page()
    await userEvent.setup().click(await screen.findByRole("button", { name: "Retry" }))
    await waitFor(() => expect(mock.mock.calls.filter((c) => !String(c[0]).endsWith("/financial")).length).toBe(2))
  })

  it("is the destination of the Catalog's product link", async () => {
    stub()
    history.pushState({}, "", "/run/run-1/product/row_2%3ASUP-001")
    render(<App />)
    expect(await screen.findByRole("heading", { name: "Widget Alpha" })).toBeInTheDocument()
    expect(screen.queryByText("Page not found")).not.toBeInTheDocument()
  })
})
