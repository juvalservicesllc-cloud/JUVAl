import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { App } from "../app/App"
import { CatalogPage } from "./CatalogPage"
import { DashboardPage } from "./DashboardPage"
import { ProductDetailPage } from "./ProductDetailPage"

const run = { execution_id: "run-1", started_at: "2026-10-26T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "first.csv", input_hash: "h", records_total: 3, records_processed: 3, records_successful: 3, records_with_errors: 0, warnings: 0 }
const none = { value: null, status: null }
const record = (ref: string, decision: string, classification: string | null, codes: string[] | null) => ({
  record_ref: ref, marketplace: "US", supplier_sku: ref, asin: none, upc: none, title: { value: `Item ${ref}`, status: "VERIFIED" }, brand: none, category: none, weight: none,
  selling_price: { value: "30", status: "VERIFIED" }, cog: "3", shipping_per_unit: null, profit: { value: "26", status: "VERIFIED" }, roi: { value: "8.6", status: "VERIFIED" },
  margin: none, break_even_price: none, hazmat_status: "ABSENT", bulky_status: "ABSENT", decision,
  decision_reasons: (codes ?? ["DEMAND_UNKNOWN"]).map((c) => `${c}: message`), decision_reason_codes: codes, review_classification: classification, issue_count: 0, issues: [],
})
const RECORDS = [record("r-pending", "REVIEW", "PENDING_DEMAND_VERIFICATION", ["DEMAND_UNKNOWN"]), record("r-other", "REVIEW", null, ["DEMAND_UNKNOWN", "PROFIT_BELOW_TARGET"]), record("r-old", "REVIEW", "NOT_CLASSIFIABLE", null)]
const summary = { count: 1, sum: "26", average: "26", minimum: "26", maximum: "26" }
const analytics = (classification: unknown = { pending_demand_verification: 1, review_not_classifiable: 1 }) => ({
  execution_id: "run-1", records: { total_records: 3 }, decisions: { REVIEW: 3 }, risks: { hazmat: { status: {}, severity: {} }, bulky: { status: {}, severity: {} } },
  provenance: {}, data_quality: { records_with_issues: 0, total_issue_count: 0 }, profitability: { profit: summary, roi: summary, margin: summary },
  brands: { items: [], distinct: 0, not_recorded: 3 }, issue_types: [], price_spread: { count: 0, average_amount: null, at_or_below_cog: 0, largest: [] },
  ...(classification === null ? {} : { review_classification: classification }),   // null = an API that predates the field
})

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }))
function stub({ analyticsBody = analytics() as unknown } = {}) {
  const mock = vi.fn((url: string) => {
    const u = new URL(String(url))
    if (u.pathname.endsWith("/analytics")) return json(analyticsBody)
    if (u.pathname.endsWith("/batch")) return json({ detail: "not part of a batch" }, 404)
    if (u.pathname.endsWith("/financial")) return json({ execution_id: "run-1", record_ref: "x", financial_document: null, capture_diagnostics: null, inconsistencies: [] })
    if (u.pathname.endsWith("/records")) {
      const pending = u.searchParams.get("review_classification") === "PENDING_DEMAND_VERIFICATION"
      const items = pending ? RECORDS.filter((r) => r.review_classification === "PENDING_DEMAND_VERIFICATION") : RECORDS
      return json({ execution_id: "run-1", records: items, pagination: { limit: 25, offset: 0, total: items.length, has_more: false } })
    }
    const ref = u.pathname.match(/\/records\/(.+)$/)?.[1]
    if (ref) return json(RECORDS.find((r) => r.record_ref === decodeURIComponent(ref)))
    return json({ items: [run] })
  })
  vi.stubGlobal("fetch", mock)
  return mock
}
const lastRecordsUrl = (mock: ReturnType<typeof stub>) => new URL(String(mock.mock.calls.filter((c) => new URL(String(c[0])).pathname.endsWith("/records")).at(-1)![0]))

describe("Pending demand verification (informative, stays REVIEW)", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); sessionStorage.clear(); history.pushState({}, "", "/") })

  it("does not filter by default", async () => {
    const mock = stub()
    render(<CatalogPage />)
    await screen.findByText("Item r-pending")
    expect(lastRecordsUrl(mock).searchParams.has("review_classification")).toBe(false)
  })

  it("asks the server for the classification and exports the same query", async () => {
    const mock = stub()
    const open = vi.spyOn(window, "open").mockImplementation(() => null)
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Item r-other")
    await user.selectOptions(screen.getByLabelText("Review status"), "pending")
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("review_classification")).toBe("PENDING_DEMAND_VERIFICATION"))
    expect(lastRecordsUrl(mock).searchParams.get("offset")).toBe("0")
    await waitFor(() => expect(screen.queryByText("Item r-other")).not.toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /^Export/ }))
    expect(new URL(String(open.mock.calls[0][0])).searchParams.get("review_classification")).toBe("PENDING_DEMAND_VERIFICATION")
    expect(screen.getByRole("status")).toHaveTextContent(/decision stays REVIEW.*not a BUY recommendation/)
  })

  it("keeps REVIEW as the official decision and labels the row neutrally, never as BUY", async () => {
    stub()
    render(<CatalogPage />)
    const row = (await screen.findByText("Item r-pending")).closest("tr") as HTMLElement
    expect(within(row).getByText("▲ REVIEW")).toBeInTheDocument()
    const tag = within(row).getByText("demand not verified")
    expect(tag).toHaveClass("pending-demand")
    expect(tag).not.toHaveClass("BUY")
    expect(row).not.toHaveTextContent("BUY")
    // Only the server-classified row is labelled: other REVIEWs, including the
    // unclassifiable historical one, carry no label.
    expect(within(screen.getByText("Item r-other").closest("tr") as HTMLElement).queryByText("demand not verified")).toBeNull()
    expect(within(screen.getByText("Item r-old").closest("tr") as HTMLElement).queryByText("demand not verified")).toBeNull()
  })

  it("opens filtered from the Dashboard link in the same tab", async () => {
    const mock = stub()
    history.pushState({}, "", "/catalog?run=run-1&review=pending-demand")
    render(<App />)
    await screen.findByText("Item r-pending")
    expect(lastRecordsUrl(mock).searchParams.get("review_classification")).toBe("PENDING_DEMAND_VERIFICATION")
    expect(screen.getByLabelText("Review status")).toHaveValue("pending")
  })

  it("counts the classification on the Dashboard, beside the unclassifiable REVIEWs", async () => {
    stub()
    const go = vi.fn()
    render(<DashboardPage go={go} />)
    const panel = await screen.findByLabelText("Pending demand verification")
    expect(panel).toHaveTextContent("1 of 3 REVIEW records are held back only because demand could not be determined")
    expect(panel).toHaveTextContent("they are not BUY")
    expect(panel).toHaveTextContent("1 REVIEW records were processed before reason codes were stored")
    await userEvent.setup().click(within(panel).getByRole("button", { name: "Show them in Catalog" }))
    expect(go).toHaveBeenCalledWith("/catalog?run=run-1&review=pending-demand")
  })

  it("says the count is unavailable from an older API instead of showing zero", async () => {
    stub({ analyticsBody: analytics(null) })
    render(<DashboardPage go={vi.fn()} />)
    const panel = await screen.findByLabelText("Pending demand verification")
    expect(panel).toHaveTextContent("Not available from this API version")
    expect(panel).not.toHaveTextContent(/\b0\b/)
  })

  it("explains the classification on Product Detail without changing the decision", async () => {
    stub()
    render(<ProductDetailPage executionId="run-1" recordRef="r-pending" go={vi.fn()} />)
    const decision = await screen.findByLabelText("Decision")
    expect(within(decision).getByText("▲ REVIEW")).toBeInTheDocument()
    expect(within(decision).getByRole("status")).toHaveTextContent("The decision stays REVIEW until demand is evidenced — this is not a BUY.")
  })

  it("says a historical record is not classified", async () => {
    stub()
    render(<ProductDetailPage executionId="run-1" recordRef="r-old" go={vi.fn()} />)
    const decision = await screen.findByLabelText("Decision")
    expect(decision).toHaveTextContent("Reason codes were not stored for this earlier record")
    expect(within(decision).queryByText("demand not verified")).toBeNull()
  })
})
