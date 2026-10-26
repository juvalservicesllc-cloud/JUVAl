import { render, screen, waitFor, within } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { BatchPage } from "./BatchPage"

const file = (ordinal: number, filename: string, status: string, execution_id: string | null) => ({
  ordinal, filename, content_type: null, size_bytes: 10, status, execution_id, warnings: [], errors: [],
  records_total: 0, records_processed: 0, records_with_errors: 0, warning_count: 0,
})
const batch = (persisted = true) => ({
  batch_id: "batch-1", created_at: "2026-10-26T10:00:00Z", status: "PARTIAL_SUCCESS", persisted,
  total_files: 5, succeeded_files: 3, failed_files: 2, records_total: 9, records_processed: 9, records_with_errors: 1, warning_count: 0,
  files: [
    file(0, "alpha.csv", "SUCCESS", "run-a"),
    file(1, "beta.xlsx", "SUCCESS", "run-b"),
    file(2, "gamma.csv", "SUCCESS", "run-c"),
    file(3, "delta.csv", "FAILED", "run-d"),
    file(4, "notes.pdf", "REJECTED", null),
  ],
})
const summary = (count: number, average: string | null) => ({ count, sum: null, average, minimum: null, maximum: null })
const analytics = (id: string, total: number, decisions: Record<string, number>, avgProfit: string | null, profitCount: number, profitStatus: Record<string, number>) => ({
  execution_id: id, records: { total_records: total }, decisions,
  risks: { hazmat: { status: {}, severity: {} }, bulky: { status: {}, severity: {} } },
  provenance: { profit: profitStatus },
  data_quality: { records_with_issues: 1, total_issue_count: 2 },
  profitability: { profit: summary(profitCount, avgProfit), roi: summary(profitCount, avgProfit === null ? null : "0.5"), margin: summary(0, null) },
  brands: { items: [], distinct: 0, not_recorded: total }, issue_types: [], price_spread: { count: 0, average_amount: null, at_or_below_cog: 0, largest: [] },
})
const BODIES: Record<string, () => Response> = {
  "run-a": () => new Response(JSON.stringify(analytics("run-a", 4, { BUY: 1, REVIEW: 2, PASS: 1 }, "7.12", 3, { VERIFIED: 3, INFERRED: 1 }))),
  "run-b": () => new Response(JSON.stringify(analytics("run-b", 5, { PASS: 5 }, null, 0, { NOT_FOUND: 3, INVALID: 2 }))),
  "run-c": () => new Response(JSON.stringify({ detail: "internal server error" }), { status: 500 }),
  "run-d": () => new Response(JSON.stringify({ detail: "unknown execution_id" }), { status: 404 }),
}

function stub(body = batch()) {
  const mock = vi.fn((url: string) => {
    const path = new URL(String(url)).pathname
    if (path.endsWith("/analytics")) return Promise.resolve(BODIES[decodeURIComponent(path.split("/")[4])]())
    return Promise.resolve(new Response(JSON.stringify(body)))
  })
  vi.stubGlobal("fetch", mock)
  return mock
}
const row = (name: string) => within(screen.getByRole("table", { name: "Per-file analytics" })).getByText(name).closest("tr") as HTMLElement
const cells = (name: string) => Array.from(row(name).querySelectorAll("td")).map((td) => td.textContent)

describe("Per-file analytics on Batch Detail (Golden multi-source table)", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("asks each file's own run for its analytics, and nothing for a file that never ran", async () => {
    const mock = stub()
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await waitFor(() => expect(mock.mock.calls.filter((c) => String(c[0]).endsWith("/analytics"))).toHaveLength(4))
    const asked = mock.mock.calls.filter((c) => String(c[0]).endsWith("/analytics")).map((c) => new URL(String(c[0])).pathname)
    expect(asked.sort()).toEqual(["/api/v1/runs/run-a/analytics", "/api/v1/runs/run-b/analytics", "/api/v1/runs/run-c/analytics", "/api/v1/runs/run-d/analytics"])
  })

  it("puts each file's backend figures side by side, with the coverage of every average", async () => {
    stub()
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await waitFor(() => expect(cells("alpha.csv")[1]).toBe("4"))
    expect(cells("alpha.csv")).toEqual(["alpha.csv", "4", "1", "2", "1", "$7.12 (3)", "50.0% (3)", "1", "1", "0"])
  })

  it("shows an unusable average as unavailable and keeps not-found and invalid profit visible", async () => {
    stub()
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await waitFor(() => expect(cells("beta.xlsx")[1]).toBe("5"))
    expect(cells("beta.xlsx")).toEqual(["beta.xlsx", "5", "0", "0", "5", "— (0)", "— (0)", "1", "0", "5"])
  })

  it("isolates a failing or missing file to its own row", async () => {
    stub()
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await waitFor(() => expect(row("gamma.csv")).toHaveTextContent("Analytics could not be loaded for this file"))
    expect(row("delta.csv")).toHaveTextContent("Not stored")
    expect(row("notes.pdf")).toHaveTextContent("Never ran — no analytics")
    expect(cells("alpha.csv")[1]).toBe("4")   // siblings unaffected
  })

  it("links each file that ran to its Dashboard", async () => {
    stub()
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await screen.findByRole("table", { name: "Per-file analytics" })
    expect(within(row("alpha.csv")).getByRole("link", { name: "alpha.csv" })).toHaveAttribute("href", "/?run=run-a")
    expect(within(row("notes.pdf")).queryByRole("link")).toBeNull()
  })

  it("adds nothing for a batch that was not persisted, since its runs have no analytics", async () => {
    const mock = stub(batch(false))
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await screen.findByRole("table", { name: "Included files" })
    expect(screen.queryByRole("table", { name: "Per-file analytics" })).not.toBeInTheDocument()
    expect(mock.mock.calls.some((c) => String(c[0]).endsWith("/analytics"))).toBe(false)
  })

  it("refuses an incomplete analytics body instead of rendering guessed values", async () => {
    const mock = stub()
    mock.mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(String(url).endsWith("/analytics") ? { records: {} } : batch()))))
    render(<BatchPage batchId="batch-1" go={vi.fn()} />)
    await waitFor(() => expect(row("alpha.csv")).toHaveTextContent("Analytics could not be loaded for this file"))
  })
})
