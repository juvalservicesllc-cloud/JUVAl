import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DashboardPage } from "./DashboardPage"

const RUN_A = {
  execution_id: "run-a", started_at: "2026-08-17T12:00:00Z", finished_at: "2026-08-17T12:05:00Z",
  status: "SUCCESS", input_filename: "catalog-a.xlsx", input_hash: "a",
  records_total: 1, records_processed: 1, records_successful: 1, records_with_errors: 0, warnings: 0,
}
const RUN_B = {
  execution_id: "run-b", started_at: "2026-08-16T09:00:00Z", finished_at: "2026-08-16T09:02:00Z",
  status: "PARTIAL_SUCCESS", input_filename: "catalog-b.xlsx", input_hash: "b",
  records_total: 1, records_processed: 1, records_successful: 0, records_with_errors: 1, warnings: 0,
}

const EMPTY_FV = { value: null, status: null }
function recordFor(runId: string) {
  return {
    record_ref: "row_1", marketplace: "US", supplier_sku: "S1", asin: EMPTY_FV, upc: EMPTY_FV,
    weight: EMPTY_FV, selling_price: EMPTY_FV, cog: null, shipping_per_unit: null,
    profit: EMPTY_FV, roi: EMPTY_FV, margin: EMPTY_FV, break_even_price: EMPTY_FV,
    max_cog_target_profit: EMPTY_FV, max_cog_target_roi: EMPTY_FV,
    hazmat_status: "ABSENT", hazmat_severity: "NONE", bulky_status: "ABSENT", bulky_severity: "NONE",
    decision: "BUY", decision_reasons: [], issue_count: 0, issues: [], _run: runId,
  }
}

function renderPage() {
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>)
}

function stubFetchWithRuns(runs: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/records")) {
        const executionId = url.match(/runs\/([^/]+)\/records/)?.[1]
        return Promise.resolve({ ok: true, status: 200, json: async () => ({ execution_id: executionId, records: [recordFor(executionId ?? "")] }) })
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: runs }) })
    }),
  )
}

describe("DashboardPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while runs are being fetched", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderPage()
    expect(screen.getByText(/loading runs/i)).toBeInTheDocument()
  })

  it("shows an empty state, never demo KPIs, when no runs are persisted", async () => {
    stubFetchWithRuns([])
    renderPage()
    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
    expect(screen.queryByText("DEMO MODE")).not.toBeInTheDocument()
  })

  it("shows an error state with retry, never falling back to demo data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "unavailable" }) })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i)

    fetchMock.mockImplementation((url: string) =>
      Promise.resolve({ ok: true, status: 200, json: async () => (url.includes("/records") ? { execution_id: "run-a", records: [recordFor("run-a")] } : { items: [RUN_A] }) }),
    )
    await user.click(screen.getByRole("button", { name: /retry/i }))
    await waitFor(() => expect(screen.getByText("catalog-a.xlsx")).toBeInTheDocument())
  })

  it("selects the latest run by default and shows its real KPIs", async () => {
    stubFetchWithRuns([RUN_A, RUN_B])
    renderPage()

    expect(await screen.findByText("catalog-a.xlsx")).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: /select run/i })).toHaveValue("run-a")
  })

  it("lets the operator switch to a different persisted run", async () => {
    stubFetchWithRuns([RUN_A, RUN_B])
    const user = userEvent.setup()
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    await user.selectOptions(screen.getByRole("combobox", { name: /select run/i }), "run-b")

    await waitFor(() => expect(screen.getByText("catalog-b.xlsx")).toBeInTheDocument())
  })

  it("links to the selected run's Run Detail page", async () => {
    stubFetchWithRuns([RUN_A])
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect(screen.getByRole("link", { name: /open run detail/i })).toHaveAttribute("href", "/runs/run-a")
  })
})
