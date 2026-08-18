import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DashboardPage } from "./DashboardPage"

const RUN_A = {
  execution_id: "run-a", started_at: "2026-08-17T12:00:00Z", finished_at: "2026-08-17T12:05:00Z",
  status: "SUCCESS", input_filename: "catalog-a.xlsx", input_hash: "a",
  records_total: 3, records_processed: 3, records_successful: 3, records_with_errors: 0, warnings: 0,
}
const RUN_B = {
  execution_id: "run-b", started_at: "2026-08-16T09:00:00Z", finished_at: "2026-08-16T09:02:00Z",
  status: "PARTIAL_SUCCESS", input_filename: "catalog-b.xlsx", input_hash: "b",
  records_total: 1, records_processed: 1, records_successful: 0, records_with_errors: 1, warnings: 0,
}

const nullSummary = { count: 0, sum: null, average: null, minimum: null, maximum: null }

function analyticsFor(executionId: string, overrides: Record<string, unknown> = {}) {
  return {
    execution_id: executionId,
    records: { total_records: 3 },
    decisions: { BUY: 2, REVIEW: 1 },
    risks: {
      hazmat: { status: { ABSENT: 2, PRESENT: 1 }, severity: { HIGH: 1 } },
      bulky: { status: { ABSENT: 3 }, severity: {} },
    },
    provenance: {
      asin: { VERIFIED: 3 }, weight: { VERIFIED: 2, NOT_FOUND: 1 }, selling_price: { VERIFIED: 3 },
      profit: { VERIFIED: 2, INFERRED: 1 }, roi: { VERIFIED: 2, INFERRED: 1 }, margin: { VERIFIED: 3 },
    },
    data_quality: { records_with_issues: 1, total_issue_count: 2 },
    profitability: {
      profit: { count: 2, sum: "30", average: "15", minimum: "10", maximum: "20" },
      roi: { count: 2, sum: "0.6", average: "0.3", minimum: "0.2", maximum: "0.4" },
      margin: { count: 3, sum: "0.9", average: "0.3", minimum: "0.1", maximum: "0.5" },
    },
    ...overrides,
  }
}

function renderPage() {
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>)
}

function stubFetchWithRuns(runs: unknown[], analyticsByRun: Record<string, unknown> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/analytics")) {
        const executionId = url.match(/runs\/([^/]+)\/analytics/)?.[1] ?? ""
        return Promise.resolve({ ok: true, status: 200, json: async () => analyticsByRun[executionId] ?? analyticsFor(executionId) })
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

    fetchMock.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [RUN_A] }) }),
    )
    await user.click(screen.getByRole("button", { name: /retry/i }))
    await waitFor(() => expect(screen.getByText("catalog-a.xlsx")).toBeInTheDocument())
  })

  it("selects the latest run by default, fetches its analytics (not records), and renders real KPIs", async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.includes("/records")) throw new Error("Dashboard must never fetch records for charts")
      if (url.includes("/analytics")) return Promise.resolve({ ok: true, status: 200, json: async () => analyticsFor("run-a") })
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [RUN_A, RUN_B] }) })
    })
    vi.stubGlobal("fetch", fetchMock)
    renderPage()

    expect(await screen.findByText("catalog-a.xlsx")).toBeInTheDocument()
    expect(screen.getByRole("combobox", { name: /select run/i })).toHaveValue("run-a")
    const totalRecordsCard = (await screen.findByText("Total records")).closest("article")
    expect(totalRecordsCard).toHaveTextContent("3") // analytics.records.total_records
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

  it("shows an UNKNOWN decision bucket and every dynamic decision key from the backend", async () => {
    stubFetchWithRuns([RUN_A], { "run-a": analyticsFor("run-a", { decisions: { BUY: 1, UNKNOWN: 2 } }) })
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect((await screen.findAllByText("UNKNOWN")).length).toBeGreaterThan(0)
  })

  it("renders HazMat and Bulky status distributions from analytics.risks", async () => {
    stubFetchWithRuns([RUN_A])
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect(await screen.findByText("HAZMAT")).toBeInTheDocument()
    expect(screen.getByText("BULKY")).toBeInTheDocument()
    expect(screen.getAllByText("PRESENT").length).toBeGreaterThan(0)
  })

  it("renders per-field provenance states without collapsing them into a score", async () => {
    stubFetchWithRuns([RUN_A])
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect(await screen.findByText(/data confidence/i)).toBeInTheDocument()
    expect(screen.queryByText(/quality score/i)).not.toBeInTheDocument()
    expect(screen.getAllByText("Verified").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Inferred").length).toBeGreaterThan(0)
    expect(screen.getByText("Not found")).toBeInTheDocument()
  })

  it("never displays a null profitability average as zero", async () => {
    stubFetchWithRuns([RUN_A], {
      "run-a": analyticsFor("run-a", { profitability: { profit: nullSummary, roi: nullSummary, margin: nullSummary } }),
    })
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect(await screen.findAllByText("—")).not.toHaveLength(0)
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument()
  })

  it("renders a real numeric zero profitability average distinctly from null", async () => {
    stubFetchWithRuns([RUN_A], {
      "run-a": analyticsFor("run-a", {
        profitability: {
          profit: { count: 4, sum: "0", average: "0", minimum: "-5", maximum: "5" },
          roi: nullSummary,
          margin: nullSummary,
        },
      }),
    })
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect((await screen.findAllByText(/\$0\.00/)).length).toBeGreaterThan(0)
  })

  it("shows records-with-issues and total-issue-count from data_quality", async () => {
    stubFetchWithRuns([RUN_A])
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect(await screen.findByText(/2 total issues/i)).toBeInTheDocument()
  })

  it("shows an explicit empty-analytics state for a zero-record run, not a broken chart", async () => {
    stubFetchWithRuns([RUN_A], {
      "run-a": analyticsFor("run-a", {
        records: { total_records: 0 }, decisions: {}, risks: { hazmat: { status: {}, severity: {} }, bulky: { status: {}, severity: {} } },
        provenance: { asin: {}, weight: {}, selling_price: {}, profit: {}, roi: {}, margin: {} },
        data_quality: { records_with_issues: 0, total_issue_count: 0 },
        profitability: { profit: nullSummary, roi: nullSummary, margin: nullSummary },
      }),
    })
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    expect(await screen.findByText(/this run has no records to analyze/i)).toBeInTheDocument()
  })

  it("shows an analytics error state with retry, independent of the run selector", async () => {
    const fetchMock = vi.fn<(url: string) => Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }>>((url) => {
      if (url.includes("/analytics")) return Promise.resolve({ ok: false, status: 500, json: async () => ({ detail: "analytics store unavailable" }) })
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [RUN_A] }) })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText("catalog-a.xlsx")).toBeInTheDocument()
    expect(await screen.findByRole("alert")).toHaveTextContent(/analytics store unavailable/i)

    fetchMock.mockImplementation((url: string) =>
      url.includes("/analytics")
        ? Promise.resolve({ ok: true, status: 200, json: async () => analyticsFor("run-a") })
        : Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [RUN_A] }) }),
    )
    await user.click(screen.getByRole("button", { name: /retry/i }))
    await waitFor(() => expect(screen.getAllByText("2").length).toBeGreaterThan(0))
  })

  it("toggles the decision chart between donut and bars", async () => {
    stubFetchWithRuns([RUN_A])
    const user = userEvent.setup()
    renderPage()

    await screen.findByText("catalog-a.xlsx")
    const barsButton = await screen.findByRole("button", { name: "Bars" })
    expect(screen.getByRole("button", { name: "Donut" })).toHaveAttribute("aria-pressed", "true")

    await user.click(barsButton)
    expect(barsButton).toHaveAttribute("aria-pressed", "true")
  })
})
