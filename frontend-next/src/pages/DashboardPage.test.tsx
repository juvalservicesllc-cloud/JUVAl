import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DashboardPage } from "./DashboardPage"

const run = (id: string, file: string) => ({
  execution_id: id, started_at: "2026-10-26T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: file, input_hash: "h",
  records_total: 4, records_processed: 4, records_successful: 4, records_with_errors: 0, warnings: 0,
})
const summary = (count: number, sum: string | null, average: string | null, minimum: string | null, maximum: string | null) => ({ count, sum, average, minimum, maximum })
const analytics = (id: string) => ({
  execution_id: id,
  records: { total_records: 4 },
  decisions: { PASS: 1, REVIEW: 3 },
  risks: { hazmat: { status: { ABSENT: 1, PRESENT: 1, UNKNOWN: 2 }, severity: { HIGH: 1, NONE: 1, UNKNOWN: 2 } }, bulky: { status: { ABSENT: 3, UNKNOWN: 1 }, severity: { NONE: 3, UNKNOWN: 1 } } },
  provenance: { asin: { VERIFIED: 2, INVALID: 1, NOT_FOUND: 1 }, margin: { VERIFIED: 2, UNKNOWN: 2 } },
  data_quality: { records_with_issues: 2, total_issue_count: 7 },
  profitability: { profit: summary(2, "14.24", "7.12", "5.25", "8.99"), roi: summary(2, "2.6", "1.3", "1.1", "1.5"), margin: summary(2, "0.8", "0.4", "0.35", "0.45") },
  brands: { items: [{ label: "Acme", count: 4 }], distinct: 1, not_recorded: 0 },
  issue_types: [{ code: "INVALID_ASIN_FORMAT", count: 1 }],
  price_spread: { count: 2, average_amount: "12.995", at_or_below_cog: 0, largest: [{ record_ref: "row_2:SUP-001", title: "Widget Alpha", amount: "14.99", percent: "0.75" }] },
})
const batch = { batch_id: "b-1", created_at: "2026-10-26T10:00:00Z", status: "PARTIAL_SUCCESS", persisted: true, total_files: 3, succeeded_files: 2, failed_files: 1, records_total: 8, records_with_errors: 0, warning_count: 0, files: [] }

const json = (status: number, body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status }))
function stub({ runs = [run("run-1", "first.csv"), run("run-2", "second.csv")], analyticsStatus = 200, batchStatus = 404 } = {}) {
  const mock = vi.fn((url: string) => {
    const path = new URL(String(url)).pathname
    const id = decodeURIComponent(path.split("/")[4] ?? "")
    if (path.endsWith("/analytics")) return analyticsStatus === 200 ? json(200, analytics(id)) : json(analyticsStatus, { detail: "internal server error" })
    if (path.endsWith("/batch")) return batchStatus === 200 ? json(200, batch) : json(batchStatus, { detail: batchStatus === 404 ? "run was not submitted as part of a batch" : "internal server error" })
    return json(200, { items: runs })
  })
  vi.stubGlobal("fetch", mock)
  return mock
}
const kpi = (label: string) => within(screen.getByLabelText("Key figures")).getByText(label).closest("article") as HTMLElement

describe("Dashboard on GET /analytics", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("opens on the most recent run and shows backend aggregates only", async () => {
    stub()
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    expect(kpi("Records")).toHaveTextContent("4")
    expect(kpi("Records with issues")).toHaveTextContent("2")
    expect(kpi("Issues")).toHaveTextContent("7")
    expect(kpi("Average ROI")).toHaveTextContent("130.0%")
    expect(kpi("Average margin")).toHaveTextContent("40.0%")
    expect(screen.getByLabelText("Run")).toHaveValue("run-1")
  })

  it("switches Donut/Bars without another request and keeps exact counts and recent links", async () => {
    const mock = stub()
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    const requests = mock.mock.calls.length
    const user = userEvent.setup()
    await user.click(screen.getByRole("button", { name: "Donut" }))
    const chart = screen.getByLabelText("Decision distribution")
    expect(chart).toHaveTextContent("BUY: 0")
    expect(chart).toHaveTextContent("REVIEW: 3")
    expect(chart).toHaveTextContent("PASS: 1")
    expect(screen.getByRole("button", { name: "Donut" })).toHaveAttribute("aria-pressed", "true")
    await user.click(screen.getByRole("button", { name: "Bars" }))
    expect(screen.getByLabelText("Decision distribution").tagName).toBe("UL")
    expect(mock).toHaveBeenCalledTimes(requests)
    const link = within(screen.getByRole("region", { name: "Recent runs" })).getByRole("link", { name: "first.csv" })
    expect(link).toHaveAttribute("href", "/runs/run-1")
    expect(link).not.toHaveAttribute("target")
  })

  it("shows a decision that never occurred as a real zero, since the run has records", async () => {
    stub()
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    const cards = within(screen.getByLabelText("Key figures")).getAllByRole("article")
    const buy = cards.find((c) => c.textContent?.includes("BUY"))!
    expect(buy).toHaveTextContent("0")
  })

  it("says how many records each financial figure covers and that it is verified only", async () => {
    stub()
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    expect(kpi("Sum of verified unit profit")).toHaveTextContent("$14.24")
    expect(kpi("Sum of verified unit profit")).toHaveTextContent("2 of 4 records, verified only")
    expect(kpi("Sum of verified unit profit")).toHaveTextContent("not a sales forecast")
    expect(kpi("Average profit")).toHaveTextContent("$7.12")
  })

  it("shows batch file counts only for a run that belongs to a batch", async () => {
    stub({ batchStatus: 200 })
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    expect(kpi("Files in batch")).toHaveTextContent("3")
    expect(kpi("Processed files")).toHaveTextContent("2")
    expect(kpi("Failed or rejected files")).toHaveTextContent("1")
  })

  it("explains the absence of file counts for a single-file run instead of inventing one", async () => {
    stub({ batchStatus: 404 })
    render(<DashboardPage go={vi.fn()} />)
    expect(await screen.findByText(/submitted on its own/)).toBeInTheDocument()
    expect(screen.queryByText("Files in batch")).not.toBeInTheDocument()
  })

  it("keeps the analytics when the batch lookup fails, and says so", async () => {
    stub({ batchStatus: 500 })
    render(<DashboardPage go={vi.fn()} />)
    expect(await screen.findByText(/batch could not be loaded/)).toBeInTheDocument()
    expect(kpi("Records")).toHaveTextContent("4")
  })

  it("separates every verification status per field, with unrecorded values in their own column", async () => {
    stub()
    render(<DashboardPage go={vi.fn()} />)
    const table = await screen.findByRole("table", { name: "Provenance by field" })
    const margin = within(table).getByText("Margin").closest("tr")!
    expect(Array.from(margin.querySelectorAll("td")).map((td) => td.textContent)).toEqual(["Margin", "2", "0", "0", "0", "2"])
  })

  it("shows risk status and severity, issue types, brands and the largest spreads linking to Product Detail", async () => {
    stub()
    render(<DashboardPage go={vi.fn()} />)
    expect(await screen.findByLabelText("HazMat severity")).toHaveTextContent("HIGH1")
    expect(screen.getByRole("table", { name: "Issue types" })).toHaveTextContent("INVALID_ASIN_FORMAT1")
    expect(screen.getByLabelText("Issue type distribution")).toHaveTextContent("INVALID_ASIN_FORMAT1")
    expect(screen.getByLabelText("Price spread distribution")).toHaveTextContent("$14.99")
    expect(screen.getByLabelText("ASIN verification distribution")).toHaveTextContent("VERIFIED2")
    expect(screen.getByLabelText("Brand distribution")).toHaveTextContent("Acme4")
    expect(screen.getByRole("link", { name: "Widget Alpha" })).toHaveAttribute("href", "/run/run-1/product/row_2%3ASUP-001")
  })

  it("switches runs and reloads that run's analytics", async () => {
    const mock = stub()
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    await userEvent.setup().selectOptions(screen.getByLabelText("Run"), "run-2")
    await waitFor(() => expect(mock.mock.calls.some((c) => String(c[0]).includes("/runs/run-2/analytics"))).toBe(true))
  })

  it("keeps a long run option intact and selects it by its execution id", async () => {
    const filename = "Supplier inventory with a long descriptive filename for visual review.xlsx"
    const mock = stub({ runs: [run("run-1", "first.csv"), run("run-2", filename)] })
    const go = vi.fn()
    render(<DashboardPage go={go} />)
    await screen.findByLabelText("Key figures")
    const selector = screen.getByRole("combobox", { name: "Run" })
    const option = within(selector).getByRole("option", { name: `${filename} — ${new Date("2026-10-26T10:00:00Z").toLocaleString()}` })
    expect(option).toHaveValue("run-2")
    await userEvent.setup().selectOptions(selector, option)
    expect(selector).toHaveValue("run-2")
    await waitFor(() => expect(mock.mock.calls.some((c) => String(c[0]).includes("/runs/run-2/analytics"))).toBe(true))
    await userEvent.setup().click(screen.getByRole("button", { name: "Run detail" }))
    expect(go).toHaveBeenCalledWith("/runs/run-2")
  })

  it("honours a run passed in the address", async () => {
    const mock = stub()
    render(<DashboardPage initialRunId="run-2" go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    expect(mock.mock.calls.some((c) => String(c[0]).includes("/runs/run-1/analytics"))).toBe(false)
  })

  it("offers Import when there are no persisted runs", async () => {
    stub({ runs: [] })
    const go = vi.fn()
    render(<DashboardPage go={go} />)
    await userEvent.setup().click(await screen.findByRole("button", { name: "Import a file" }))
    expect(go).toHaveBeenCalledWith("/import")
  })

  it("reports an analytics failure with a retry and shows no figures", async () => {
    stub({ analyticsStatus: 500 })
    render(<DashboardPage go={vi.fn()} />)
    expect(await screen.findByRole("alert")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument()
    expect(screen.queryByLabelText("Key figures")).not.toBeInTheDocument()
  })

  it("shows unusable financial summaries as unavailable, never as zero", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      const path = new URL(String(url)).pathname
      if (path.endsWith("/analytics")) return json(200, { ...analytics("run-1"), profitability: { profit: summary(0, null, null, null, null), roi: summary(0, null, null, null, null), margin: summary(0, null, null, null, null) } })
      if (path.endsWith("/batch")) return json(404, {})
      return json(200, { items: [run("run-1", "first.csv")] })
    }))
    render(<DashboardPage go={vi.fn()} />)
    await screen.findByLabelText("Key figures")
    expect(kpi("Sum of verified unit profit")).toHaveTextContent("—")
    expect(kpi("Sum of verified unit profit")).not.toHaveTextContent("$0")
    expect(kpi("Average ROI")).toHaveTextContent("0 of 4 records")
  })
})
