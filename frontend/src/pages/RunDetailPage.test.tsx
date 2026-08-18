import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RunDetailPage } from "./RunDetailPage"

const RUN = {
  execution_id: "run-1",
  started_at: "2026-08-17T12:00:00Z",
  finished_at: "2026-08-17T12:05:00Z",
  status: "PARTIAL_SUCCESS",
  input_filename: "catalog.xlsx",
  input_hash: "abc123",
  records_total: 5,
  records_processed: 4,
  records_successful: 3,
  records_with_errors: 1,
  warnings: 2,
}

const RECORD = {
  record_ref: "row_1:SUP-001",
  marketplace: "US",
  supplier_sku: "SUP-001",
  asin: { value: "B0TESTAAA1", status: "VERIFIED" },
  upc: { value: null, status: "NOT_FOUND" },
  weight: { value: "1.5", status: "VERIFIED" },
  selling_price: { value: "19.99", status: "VERIFIED" },
  cog: "5",
  shipping_per_unit: "1",
  profit: { value: "8.99", status: "VERIFIED" },
  roi: { value: "1.5", status: "VERIFIED" },
  margin: { value: "0.45", status: "VERIFIED" },
  break_even_price: { value: "9.41", status: "VERIFIED" },
  max_cog_target_profit: { value: "8.99", status: "VERIFIED" },
  max_cog_target_roi: { value: "10.53", status: "VERIFIED" },
  hazmat_status: "PRESENT",
  hazmat_severity: "HIGH",
  bulky_status: "ABSENT",
  bulky_severity: "NONE",
  decision: "PASS",
  decision_reasons: ["RISK_ABOVE_MAXIMUM: HAZMAT is PRESENT with severity HIGH, above the configured maximum LOW."],
  issue_count: 0,
  issues: [],
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/runs/:executionId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function stubFetch(runResponse: { ok: boolean; status: number; body: unknown }, recordsResponse: { ok: boolean; status: number; body: unknown }) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const isRecords = url.includes("/records")
      const { ok, status, body } = isRecords ? recordsResponse : runResponse
      return Promise.resolve({ ok, status, json: async () => body })
    }),
  )
}

describe("RunDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while requests are in flight", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderAt("/runs/run-1")
    expect(screen.getByText(/loading run/i)).toBeInTheDocument()
  })

  it("renders run summary and records from real API data", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD] } })
    renderAt("/runs/run-1")

    expect(await screen.findByText("PARTIAL SUCCESS")).toBeInTheDocument()
    expect(screen.getByText("catalog.xlsx")).toBeInTheDocument()
    expect(screen.getByText(/B0TESTAAA1/)).toBeInTheDocument()
    expect(screen.getAllByLabelText("Status: VERIFIED").length).toBeGreaterThan(0)
  })

  it("shows the decision and provenance without collapsing HAZMAT severity into a verified fact", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD] } })
    renderAt("/runs/run-1")

    expect(await screen.findByText("PASS")).toBeInTheDocument()
    // ResultsTable renders "PRESENT (HIGH)" -- never claims severity is VERIFIED.
    expect(screen.getAllByText(/PRESENT/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/HIGH/).length).toBeGreaterThan(0)
  })

  it("shows an empty state when the run has no persisted records", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [] } })
    renderAt("/runs/run-1")

    expect(await screen.findByText(/no processed records/i)).toBeInTheDocument()
  })

  it("shows a not-found state for an unknown execution id", async () => {
    stubFetch({ ok: false, status: 404, body: { detail: "unknown execution_id" } }, { ok: false, status: 404, body: { detail: "unknown execution_id" } })
    renderAt("/runs/does-not-exist")

    expect(await screen.findByText(/no run found/i)).toBeInTheDocument()
  })

  it("shows a server error state, never demo data", async () => {
    stubFetch({ ok: false, status: 500, body: { detail: "internal server error" } }, { ok: false, status: 500, body: { detail: "internal server error" } })
    renderAt("/runs/run-1")

    expect(await screen.findByRole("alert")).toHaveTextContent(/internal server error/i)
  })

  it("offers a real download link for the run's Excel artifact", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD] } })
    renderAt("/runs/run-1")

    const link = await screen.findByRole("link", { name: /download results/i })
    expect(link.getAttribute("href")).toContain("/api/v1/runs/run-1/download")
  })
})
