import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { BatchPage } from "./BatchPage"
import { RunDetailPage } from "./RunDetailPage"
import { RunsPage } from "./RunsPage"

const run = {
  execution_id: "run-1", started_at: "2026-08-26T10:00:00Z", finished_at: "2026-08-26T10:00:05Z",
  status: "PARTIAL_SUCCESS", input_filename: "supplier.csv", input_hash: "abc123",
  records_total: 5, records_processed: 5, records_successful: 4, records_with_errors: 1, warnings: 2,
}

const batch = {
  batch_id: "batch-1", created_at: "2026-08-26T10:00:00Z", status: "PARTIAL_SUCCESS",
  total_files: 3, succeeded_files: 1, failed_files: 2, persisted: true,
  records_total: 5, records_processed: 5, records_with_errors: 1, warning_count: 2,
  files: [
    { ordinal: 0, filename: "good.csv", content_type: "text/csv", size_bytes: 10, status: "SUCCESS", execution_id: "run-1", warnings: [], errors: [], records_total: 5, records_processed: 5, records_with_errors: 1, warning_count: 2 },
    { ordinal: 1, filename: "broken.xlsx", content_type: null, size_bytes: 20, status: "FAILED", execution_id: null, warnings: [], errors: ["could not be read as a workbook"], records_total: 0, records_processed: 0, records_with_errors: 0, warning_count: 0 },
    { ordinal: 2, filename: "notes.pdf", content_type: null, size_bytes: 30, status: "REJECTED", execution_id: null, warnings: [], errors: ["unsupported input suffix"], records_total: 0, records_processed: 0, records_with_errors: 0, warning_count: 0 },
  ],
}

// The per-file analytics table repeats file names; these assertions are about
// the included-files table.
const included = () => within(screen.getByRole("table", { name: "Included files" }))

const okJson = (body: unknown) => vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => body }))

describe("RunsPage on real persisted runs", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state, then the real run list", async () => {
    vi.stubGlobal("fetch", okJson({ items: [run] }))
    render(<RunsPage go={vi.fn()} />)

    expect(screen.getByText(/loading runs/i)).toBeInTheDocument()
    expect(await screen.findByText("supplier.csv")).toBeInTheDocument()
    expect(screen.getByText("PARTIAL_SUCCESS")).toBeInTheDocument()
    expect(screen.getByText(/5 records · 4 successful · 1 with errors · 2 warning/)).toBeInTheDocument()
  })

  it("shows an explicit empty state rather than falling back to fixtures", async () => {
    vi.stubGlobal("fetch", okJson({ items: [] }))
    render(<RunsPage go={vi.fn()} />)

    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
    expect(screen.queryByText(/west marine/i)).not.toBeInTheDocument()
  })

  it("shows a retryable error when the API fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 500, json: async () => ({ detail: "store unavailable" }) })))
    render(<RunsPage go={vi.fn()} />)

    expect(await screen.findByRole("alert")).toHaveTextContent(/store unavailable/i)
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("drills into a run and into that run's catalog", async () => {
    vi.stubGlobal("fetch", okJson({ items: [run] }))
    const go = vi.fn()
    render(<RunsPage go={go} />)
    await screen.findByText("supplier.csv")
    const user = userEvent.setup()

    await user.click(screen.getByRole("button", { name: "Open" }))
    expect(go).toHaveBeenCalledWith("/runs/run-1")

    await user.click(screen.getByRole("button", { name: /open in catalog/i }))
    expect(go).toHaveBeenCalledWith("/catalog?run=run-1")
  })

  it("shows each run's decision counts, and no numbers when they are null", async () => {
    const counted = { ...run, decisions: { BUY: 2, REVIEW: 1, PASS: 2 } }
    const uncounted = { ...run, execution_id: "run-2", input_filename: "legacy.csv", decisions: null }
    vi.stubGlobal("fetch", okJson({ items: [counted, uncounted] }))
    render(<RunsPage go={vi.fn()} />)
    await screen.findByText("legacy.csv")

    const counts = screen.getAllByLabelText("Decision counts")
    expect(counts).toHaveLength(1)
    expect(counts[0]).toHaveTextContent("BUY 2")
    expect(counts[0]).toHaveTextContent("REVIEW 1")
    expect(counts[0]).toHaveTextContent("PASS 2")
    const unavailable = screen.getByText(/decision counts not available/i)
    expect(unavailable).not.toHaveTextContent(/\d/)
  })

  it("does not offer duplicate or delete, which have no approved semantics", async () => {
    vi.stubGlobal("fetch", okJson({ items: [run] }))
    render(<RunsPage go={vi.fn()} />)
    await screen.findByText("supplier.csv")

    expect(screen.queryByRole("button", { name: /duplicate|reprocess|delete|reset/i })).not.toBeInTheDocument()
  })
})

describe("BatchPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows aggregate status and every file's own outcome", async () => {
    vi.stubGlobal("fetch", okJson(batch))
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)

    expect(await screen.findByText("PARTIAL_SUCCESS")).toBeInTheDocument()
    expect(included().getByText("good.csv")).toBeInTheDocument()
    // A failed or rejected file stays visible and named -- it is never hidden
    // behind the batch's aggregate status.
    expect(included().getByText("broken.xlsx")).toBeInTheDocument()
    expect(included().getByText("notes.pdf")).toBeInTheDocument()
    expect(screen.getByText(/could not be read as a workbook/i)).toBeInTheDocument()
  })

  it("reports a rejected file's counts as never processed, not as zero", async () => {
    vi.stubGlobal("fetch", okJson(batch))
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await screen.findByRole("table", { name: "Included files" })

    const row = included().getByText("notes.pdf").closest("tr") as HTMLElement
    expect(row.textContent).toContain("—")
    expect(row.textContent).toContain("never ran")
  })

  it("links only the files that actually produced a run", async () => {
    vi.stubGlobal("fetch", okJson(batch))
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await screen.findByRole("table", { name: "Included files" })

    const links = screen.getAllByRole("link", { name: /open run/i })
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute("href", "/runs/run-1")
    // Internal navigation stays in this tab.
    expect(links[0]).not.toHaveAttribute("target")
  })

  it("describes retry as a new batch, never as an in-place mutation", async () => {
    vi.stubGlobal("fetch", okJson(batch))
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await screen.findByRole("table", { name: "Included files" })

    expect(screen.getByText(/retrying creates a new batch rather than changing this one/i)).toBeInTheDocument()
  })
})

describe("RunDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("offers the canonical complete-run XLSX download without catalog filters", async () => {
    const fetch = okJson(run)
    vi.stubGlobal("fetch", fetch)
    render(<RunDetailPage executionId="run-1" go={vi.fn()} />)
    const link = await screen.findByRole("link", { name: "Download complete run (.xlsx)" })
    const url = new URL(link.getAttribute("href")!)
    expect(url.pathname).toBe("/api/v1/runs/run-1/download")
    expect(url.search).toBe("")
    expect(link).toHaveAttribute("download")
    expect(fetch).toHaveBeenCalledTimes(1) // no download until the operator asks
  })

  it("shows the run's own persisted fields", async () => {
    vi.stubGlobal("fetch", okJson(run))
    render(<RunDetailPage executionId="run-1" go={vi.fn()} />)

    expect(await screen.findByRole("heading", { name: "supplier.csv" })).toBeInTheDocument()
    expect(screen.getByText("abc123")).toBeInTheDocument()
    expect(screen.getByText("PARTIAL_SUCCESS")).toBeInTheDocument()
  })

  it("treats an unknown execution id as not found, not as a transport error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 404, json: async () => ({ detail: "unknown execution_id" }) })))
    render(<RunDetailPage executionId="nope" go={vi.fn()} />)

    expect(await screen.findByRole("heading", { name: /run not found/i })).toBeInTheDocument()
    // "Retry" would be misleading: the id is wrong, the request was not.
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument()
  })

  it("hands off into the catalog scoped to this run", async () => {
    vi.stubGlobal("fetch", okJson(run))
    const go = vi.fn()
    render(<RunDetailPage executionId="run-1" go={go} />)
    await screen.findByRole("heading", { name: "supplier.csv" })

    await userEvent.setup().click(screen.getByRole("button", { name: /open in catalog/i }))
    expect(go).toHaveBeenCalledWith("/catalog?run=run-1")
  })

  it("derives no decision metrics the run summary does not carry", async () => {
    vi.stubGlobal("fetch", okJson(run))
    render(<RunDetailPage executionId="run-1" go={vi.fn()} />)
    await screen.findByRole("heading", { name: "supplier.csv" })

    // This summary carries no `decisions` (an older API); showing any would be invented.
    expect(screen.queryByText(/\bBUY\b/)).not.toBeInTheDocument()
    expect(screen.getByText(/decision counts not available/i)).toBeInTheDocument()
    expect(screen.queryByText(/average roi/i)).not.toBeInTheDocument()
  })

  it("shows the stored decision counts the run summary carries", async () => {
    vi.stubGlobal("fetch", okJson({ ...run, decisions: { BUY: 3, PASS: 1, UNKNOWN: 1 } }))
    render(<RunDetailPage executionId="run-1" go={vi.fn()} />)
    const counts = await screen.findByLabelText("Decision counts")

    expect(counts).toHaveTextContent("BUY 3")
    expect(counts).toHaveTextContent("REVIEW 0")   // counts present: an absent key is a real zero
    expect(counts).toHaveTextContent("PASS 1")
    expect(counts).toHaveTextContent("1 without decision")
  })

  it("waits for the response instead of rendering a partial run", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})))
    render(<RunDetailPage executionId="run-1" go={vi.fn()} />)

    await waitFor(() => expect(screen.getByText(/loading run/i)).toBeInTheDocument())
  })
})
