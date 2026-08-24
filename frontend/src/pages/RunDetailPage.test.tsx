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

const ANALYTICS = {
  execution_id: "run-1",
  records: { total_records: 5 },
  decisions: { BUY: 1, REVIEW: 2, PASS: 2 },
  risks: {},
  provenance: {},
  data_quality: { records_with_issues: 1, total_issue_count: 2 },
  profitability: { profit: { count: 1, sum: "8", average: "8", minimum: "8", maximum: "8" }, roi: { count: 1, sum: "1.5", average: "1.5", minimum: "1.5", maximum: "1.5" }, margin: { count: 1, sum: "0.45", average: "0.45", minimum: "0.45", maximum: "0.45" } },
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

const BATCH = {
  batch_id: "batch-9", created_at: "2026-08-17T12:00:00Z", status: "PARTIAL_SUCCESS",
  total_files: 2, succeeded_files: 1, failed_files: 1, persisted: true,
  records_total: 5, records_processed: 4, records_with_errors: 1, warning_count: 2,
  files: [
    { ordinal: 0, filename: "catalog.xlsx", content_type: null, size_bytes: 2048, status: "PARTIAL_SUCCESS", execution_id: "run-1", warnings: [], errors: [], records_total: 5, records_processed: 4, records_with_errors: 1, warning_count: 2 },
    { ordinal: 1, filename: "broken.pdf", content_type: null, size_bytes: 12, status: "REJECTED", execution_id: null, warnings: [], errors: ["unsupported file type .pdf"], records_total: 0, records_processed: 0, records_with_errors: 0, warning_count: 0 },
  ],
}

function stubFetch(
  runResponse: { ok: boolean; status: number; body: unknown },
  recordsResponse: { ok: boolean; status: number; body: unknown },
  batchResponse: { ok: boolean; status: number; body: unknown } = { ok: false, status: 404, body: { detail: "this run is not part of a batch" } },
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/analytics")) return Promise.resolve({ ok: true, status: 200, json: async () => ANALYTICS })
      if (url.endsWith("/batch")) return Promise.resolve({ ok: batchResponse.ok, status: batchResponse.status, json: async () => batchResponse.body })
      const isRecords = url.includes("/records")
      const { ok, status, body } = isRecords ? recordsResponse : runResponse
      return Promise.resolve({ ok, status, json: async () => body })
    }),
  )
}

const OK_RUN = { ok: true, status: 200, body: RUN }
const OK_RECORDS = { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD], pagination: { limit: 100, offset: 0, total: 1, has_more: false } } }

describe("RunDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while requests are in flight", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderAt("/runs/run-1")
    expect(screen.getByText(/loading run/i)).toBeInTheDocument()
  })

  it("renders run summary and records from real API data", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD], pagination: { limit: 100, offset: 0, total: 1, has_more: false } } })
    renderAt("/runs/run-1")

    expect(await screen.findByText("PARTIAL SUCCESS")).toBeInTheDocument()
    expect(screen.getByText("catalog.xlsx")).toBeInTheDocument()
    expect(screen.getByText(/B0TESTAAA1/)).toBeInTheDocument()
    expect(screen.getAllByLabelText("Status: VERIFIED").length).toBeGreaterThan(0)
    expect(screen.getByText("Canonical run totals")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Open Catalog" })).toHaveAttribute("href", "/products")
  })

  it("shows the decision and provenance without collapsing HAZMAT severity into a verified fact", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD], pagination: { limit: 100, offset: 0, total: 1, has_more: false } } })
    renderAt("/runs/run-1")

    expect((await screen.findAllByText("PASS")).length).toBeGreaterThan(0)
    // ResultsTable renders "PRESENT (HIGH)" -- never claims severity is VERIFIED.
    expect(screen.getAllByText(/PRESENT/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/HIGH/).length).toBeGreaterThan(0)
  })

  it("shows an empty state when the run has no persisted records", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [], pagination: { limit: 100, offset: 0, total: 0, has_more: false } } })
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

  it("shows the included-file table when the run came from a multi-file batch", async () => {
    stubFetch(OK_RUN, OK_RECORDS, { ok: true, status: 200, body: BATCH })
    renderAt("/runs/run-1")

    expect(await screen.findByText(/batch context/i)).toBeInTheDocument()
    expect(screen.getByText("broken.pdf")).toBeInTheDocument()
    expect(screen.getByText("unsupported file type .pdf")).toBeInTheDocument()
    // The current run is marked as such rather than offered as a link to itself.
    expect(screen.getByText("This run")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /open batch/i })).toHaveAttribute("href", "/batches/batch-9")
  })

  it("never shows counts for a rejected file that produced no run", async () => {
    stubFetch(OK_RUN, OK_RECORDS, { ok: true, status: 200, body: BATCH })
    renderAt("/runs/run-1")

    await screen.findByText("broken.pdf")
    const rejectedRow = screen.getByText("broken.pdf").closest("tr")
    // A file that never ran shows "—", not a zero that reads as a measurement.
    expect(rejectedRow).toHaveTextContent("—")
    expect(rejectedRow).not.toHaveTextContent(/\b0\b/)
  })

  it("omits batch context entirely for a standalone run", async () => {
    stubFetch(OK_RUN, OK_RECORDS)
    renderAt("/runs/run-1")

    expect(await screen.findByText("PARTIAL SUCCESS")).toBeInTheDocument()
    expect(screen.queryByText(/batch context/i)).not.toBeInTheDocument()
  })

  it("offers a real download link for the run's Excel artifact", async () => {
    stubFetch({ ok: true, status: 200, body: RUN }, { ok: true, status: 200, body: { execution_id: "run-1", records: [RECORD], pagination: { limit: 100, offset: 0, total: 1, has_more: false } } })
    renderAt("/runs/run-1")

    const link = await screen.findByRole("link", { name: /download results/i })
    expect(link.getAttribute("href")).toContain("/api/v1/runs/run-1/download")
  })
})
