import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { BatchDetailPage } from "./BatchDetailPage"

const BATCH = {
  batch_id: "batch-1", created_at: "2026-08-19T10:00:00Z", status: "PARTIAL_SUCCESS",
  total_files: 3, succeeded_files: 1, failed_files: 2, persisted: true,
  records_total: 5, records_processed: 4, records_with_errors: 1, warning_count: 3,
  files: [
    { ordinal: 0, filename: "a.xlsx", content_type: null, size_bytes: 2048, status: "PARTIAL_SUCCESS", execution_id: "run-a", warnings: ["3 warning(s) reported by processing"], errors: [], records_total: 5, records_processed: 4, records_with_errors: 1, warning_count: 3 },
    { ordinal: 1, filename: "b.csv", content_type: null, size_bytes: 64, status: "FAILED", execution_id: "run-b", warnings: [], errors: ["import produced no usable records"], records_total: 0, records_processed: 0, records_with_errors: 0, warning_count: 0 },
    { ordinal: 2, filename: "notes.pdf", content_type: null, size_bytes: 12, status: "REJECTED", execution_id: null, warnings: [], errors: ["unsupported file type .pdf"], records_total: 0, records_processed: 0, records_with_errors: 0, warning_count: 0 },
  ],
}

function renderAt(batchId = "batch-1") {
  return render(
    <MemoryRouter initialEntries={[`/batches/${batchId}`]}>
      <Routes><Route path="/batches/:batchId" element={<BatchDetailPage />} /></Routes>
    </MemoryRouter>,
  )
}

function stubFetch(response: { ok: boolean; status: number; body: unknown }) {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: response.ok, status: response.status, json: async () => response.body })))
}

describe("BatchDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while the batch is being fetched", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderAt()
    expect(screen.getByText(/loading batch/i)).toBeInTheDocument()
  })

  it("makes a persisted batch reachable by URL with every included file", async () => {
    stubFetch({ ok: true, status: 200, body: BATCH })
    renderAt()

    expect((await screen.findAllByText("PARTIAL SUCCESS")).length).toBeGreaterThan(0)
    expect(screen.getByText("a.xlsx")).toBeInTheDocument()
    expect(screen.getByText("b.csv")).toBeInTheDocument()
    expect(screen.getByText("notes.pdf")).toBeInTheDocument()
    expect(screen.getByText("unsupported file type .pdf")).toBeInTheDocument()
  })

  it("reports per-file and aggregate counts from the child runs", async () => {
    stubFetch({ ok: true, status: 200, body: BATCH })
    renderAt()

    await screen.findByText("a.xlsx")
    expect(screen.getByText("Rows scanned").nextElementSibling).toHaveTextContent("5")
    expect(screen.getByText("Records processed").nextElementSibling).toHaveTextContent("4")
    // The summary <dt>, not the table column header of the same name.
    expect(screen.getAllByText("Warnings").find((node) => node.tagName === "DT")?.nextElementSibling).toHaveTextContent("3")
  })

  it("shows no counts for a rejected file that never produced a run", async () => {
    stubFetch({ ok: true, status: 200, body: BATCH })
    renderAt()

    const rejected = (await screen.findByText("notes.pdf")).closest("tr")
    expect(rejected).toHaveTextContent("—")
    expect(rejected).toHaveTextContent("No run")
  })

  it("links each processed file to its own independent run", async () => {
    stubFetch({ ok: true, status: 200, body: BATCH })
    renderAt()

    await screen.findByText("a.xlsx")
    expect(screen.getAllByRole("link", { name: /open run/i }).map((link) => link.getAttribute("href"))).toEqual(["/runs/run-a", "/runs/run-b"])
  })

  it("explains a missing batch instead of failing silently", async () => {
    stubFetch({ ok: false, status: 404, body: { detail: "unknown batch_id" } })
    renderAt("nope")

    expect(await screen.findByRole("alert")).toHaveTextContent(/no persisted batch found/i)
  })

  it("shows a server error with retry, never fabricated batch data", async () => {
    stubFetch({ ok: false, status: 500, body: { detail: "internal server error" } })
    renderAt()

    expect(await screen.findByRole("alert")).toHaveTextContent(/internal server error/i)
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })
})
