import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CatalogPage } from "./CatalogPage"

const run = {
  execution_id: "run-1", started_at: "2026-08-20T10:00:00Z", finished_at: null, status: "SUCCESS",
  input_filename: "supplier.csv", records_total: 2, records_processed: 2, records_successful: 2,
  records_with_errors: 0, warnings: 0,
}
const empty = { value: null, status: null }

function recordFor(i: number, status: string) {
  return {
    record_ref: `row-${i}`, marketplace: "US", supplier_sku: `SKU-${i}`,
    asin: { value: `ASIN-${i}`, status }, upc: empty,
    title: { value: i ? "Beta anchor" : "Alpha anchor", status }, brand: { value: "Acme", status }, category: empty,
    weight: empty, selling_price: { value: "20", status }, cog: "8", shipping_per_unit: "1",
    profit: { value: i ? "8" : "2", status }, roi: { value: i ? "0.4" : "0.1", status }, margin: { value: "0.3", status },
    break_even_price: empty, hazmat_status: "ABSENT", bulky_status: "UNKNOWN",
    decision: i ? "BUY" : "REVIEW", decision_reasons: [], issue_count: 0, issues: [],
  }
}
const records = [recordFor(0, "VERIFIED"), recordFor(1, "INFERRED")]

function stubFetch(total = records.length) {
  const mock = vi.fn((url: string) => {
    if (String(url).includes("/records")) {
      const params = new URL(String(url)).searchParams
      const limit = Number(params.get("limit") ?? 20)
      const offset = Number(params.get("offset") ?? 0)
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ execution_id: "run-1", records, pagination: { limit, offset, total, has_more: offset + records.length < total } }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [run] }) })
  })
  vi.stubGlobal("fetch", mock)
  return mock
}

function lastRecordsUrl(mock: ReturnType<typeof vi.fn>): URL {
  const calls = mock.mock.calls.filter((c: unknown[]) => String(c[0]).includes("/records"))
  return new URL(String(calls[calls.length - 1][0]))
}

describe("CatalogPage on the real backend", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear() })

  it("renders real persisted records, never fixture data", async () => {
    stubFetch()
    render(<CatalogPage />)

    expect(await screen.findByText("Alpha anchor")).toBeInTheDocument()
    expect(screen.getByText("Beta anchor")).toBeInTheDocument()
    // Golden's own demo copy must not survive into a production candidate.
    expect(screen.queryByText(/demo mode/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/simulated enrichment/i)).not.toBeInTheDocument()
  })

  it("shows every economic value with its verification status attached", async () => {
    stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    const table = document.querySelector(".table") as HTMLElement
    expect(within(table).getAllByLabelText("Status: VERIFIED").length).toBeGreaterThan(0)
    expect(within(table).getAllByLabelText("Status: INFERRED").length).toBeGreaterThan(0)
    // Legible on screen: not colour-only, not hover-only.
    expect(within(table).getAllByLabelText("Status: VERIFIED")[0]).toHaveTextContent("VER")
  })

  it("renders ROI and margin as percentages, never as the stored ratio", async () => {
    stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    expect(screen.getByText(/10\.0%/)).toBeInTheDocument()
    expect(screen.getByText(/40\.0%/)).toBeInTheDocument()
    expect(screen.queryByText("0.1")).not.toBeInTheDocument()
  })

  it("sends decision and risk filters server-side", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await user.selectOptions(screen.getByLabelText("Decision"), "BUY")
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("decision")).toBe("BUY"))

    await user.selectOptions(screen.getByLabelText("Hazmat"), "PRESENT")
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("hazmat")).toBe("PRESENT"))
  })

  it("converts the ROI percentage filter into a canonical ratio", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await user.type(screen.getByLabelText("Minimum ROI filter"), "30")
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("min_roi")).toBe("0.3"))
  })

  it("sorts server-side and toggles direction on the same column", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await user.click(screen.getByRole("button", { name: /^Cost/ }))
    await waitFor(() => {
      expect(lastRecordsUrl(mock).searchParams.get("sort")).toBe("cog")
      expect(lastRecordsUrl(mock).searchParams.get("direction")).toBe("asc")
    })
    await user.click(screen.getByRole("button", { name: /^Cost/ }))
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("direction")).toBe("desc"))
  })

  it("paginates server-side using has_more", async () => {
    const mock = stubFetch(120)
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    expect(screen.getByText(/page 1 of 6/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Next" }))
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("offset")).toBe("20"))
  })

  it("names the row count on the export button", async () => {
    stubFetch(58)
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    expect(screen.getByRole("button", { name: "Export 58 results" })).toBeInTheDocument()
  })

  it("stars a record against the run, locally, with no request", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")
    const before = mock.mock.calls.length

    await user.click(screen.getByRole("button", { name: /add alpha anchor to favorites/i }))

    expect(JSON.parse(localStorage.getItem("juval.catalog.favorites.v1") ?? "[]")).toEqual(["run-1:row-0"])
    expect(mock.mock.calls.length).toBe(before)
    expect(screen.getByText(/starred in this browser only/i)).toBeInTheDocument()
  })

  it("keeps a media slot without inventing a product image", async () => {
    stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    expect(screen.getAllByText("No image").length).toBe(records.length)
    expect(document.querySelectorAll(".table img")).toHaveLength(0)
  })

  it("does not show decision bands it cannot source from the run", async () => {
    stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    // ExecutionRun does not persist the thresholds a run used, so inventing
    // bands would misstate how a stored decision was reached.
    expect(screen.getByText(/not recorded for this run/i)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: /edit thresholds/i })).not.toBeInTheDocument()
  })

  it("surfaces an API failure as a retryable error, not a crash", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: "invalid query" }) })))
    render(<CatalogPage />)

    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid query/i)
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("shows an explicit empty state when no run is persisted", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [] }) })))
    render(<CatalogPage />)

    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
  })
})
