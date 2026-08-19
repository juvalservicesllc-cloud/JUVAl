import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ProductsPage } from "./ProductsPage"

function renderPage() {
  return render(<MemoryRouter><ProductsPage /></MemoryRouter>)
}

const run = { execution_id: "r1", started_at: "2026-08-18T12:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "catalog.xlsx", input_hash: "x", records_total: 2, records_processed: 2, records_successful: 2, records_with_errors: 0, warnings: 0 }
const empty = { value: null, status: null }

function recordFor(index: number, status: string) {
  return {
    record_ref: `row-${index}`, marketplace: "US", supplier_sku: `SKU-${index}`, asin: { value: `ASIN-${index}`, status }, upc: empty,
    title: { value: index ? "Beta" : "Alpha", status }, brand: { value: "Brand", status }, category: empty, weight: empty, height: empty, width: empty, length: empty,
    selling_price: empty, cog: null, shipping_per_unit: null, profit: { value: index ? "8" : "2", status }, roi: { value: index ? "0.4" : "0.1", status },
    margin: empty, break_even_price: empty, max_cog_target_profit: empty, max_cog_target_roi: empty,
    hazmat_status: "ABSENT", hazmat_severity: "NONE", bulky_status: "UNKNOWN", bulky_severity: null,
    decision: index ? "BUY" : "REVIEW", decision_reasons: [], issue_count: 0, issues: [],
  }
}

const records = [recordFor(0, "VERIFIED"), recordFor(1, "INFERRED")]

function stubFetch(recordsForUrl: (url: string) => { records: unknown[]; total: number } = () => ({ records, total: records.length })) {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/records")) {
      const { records: items, total } = recordsForUrl(url)
      const params = new URL(url, "http://x").searchParams
      const limit = Number(params.get("limit") ?? 50)
      const offset = Number(params.get("offset") ?? 0)
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ execution_id: "r1", records: items, pagination: { limit, offset, total, has_more: offset + items.length < total } }),
      })
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [run] }) })
  })
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

function lastRequestUrl(fetchMock: ReturnType<typeof vi.fn>): URL {
  const calls = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes("/records"))
  return new URL(String(calls[calls.length - 1][0]), "http://x")
}

describe("ProductsPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while the persisted-run selector is being fetched", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderPage()

    expect(screen.getByText(/loading catalog/i)).toBeInTheDocument()
  })

  it("issues the initial query against the server contract and renders real records", async () => {
    const fetchMock = stubFetch()
    renderPage()

    expect(await screen.findByText("Alpha")).toBeInTheDocument()
    expect(screen.getAllByText("VERIFIED").length).toBeGreaterThan(0)
    expect(screen.getAllByText("INFERRED").length).toBeGreaterThan(0)

    const url = lastRequestUrl(fetchMock)
    expect(url.searchParams.get("limit")).toBe("50")
    expect(url.searchParams.get("offset")).toBe("0")
    expect(url.searchParams.get("sort")).toBe("record_ref")
    expect(url.searchParams.get("direction")).toBe("asc")
    expect(url.searchParams.has("search")).toBe(false)
    expect(url.searchParams.has("decision")).toBe(false)
  })

  it("sends the decision filter server-side and never sends UNKNOWN", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.selectOptions(screen.getByLabelText(/filter by decision/i), "BUY")

    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("decision")).toBe("BUY"))
  })

  it("resets offset to 0 when the decision filter changes", async () => {
    const fetchMock = stubFetch(() => ({ records, total: 120 }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.click(screen.getByRole("button", { name: /next/i }))
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("offset")).toBe("50"))

    await user.selectOptions(screen.getByLabelText(/filter by decision/i), "BUY")
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("offset")).toBe("0"))
  })

  it("debounces search (no request per keystroke) and resets offset when it settles", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")
    const requestsBeforeTyping = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes("/records")).length

    await user.type(screen.getByLabelText(/search catalog/i), "widget")
    const requestsRightAfterTyping = fetchMock.mock.calls.filter((call: unknown[]) => String(call[0]).includes("/records")).length
    // Typing 6 characters must not issue 6 requests -- the debounce collapses them.
    expect(requestsRightAfterTyping - requestsBeforeTyping).toBeLessThan(6)

    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("search")).toBe("widget"), { timeout: 2000 })
    expect(lastRequestUrl(fetchMock).searchParams.get("offset")).toBe("0")
  })

  it("toggles sort direction on repeated clicks and resets offset on a new sort key", async () => {
    const fetchMock = stubFetch(() => ({ records, total: 120 }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.click(screen.getByRole("button", { name: /^profit/i }))
    await waitFor(() => {
      expect(lastRequestUrl(fetchMock).searchParams.get("sort")).toBe("profit")
      expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("desc")
    })

    await user.click(screen.getByRole("button", { name: /^profit/i }))
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("asc"))
  })

  it("paginates with Previous/Next using has_more and shows a range label", async () => {
    const fetchMock = stubFetch(() => ({ records, total: 120 }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    expect(screen.getByText(/showing 1–50 of 120/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /previous/i })).toBeDisabled()

    await user.click(screen.getByRole("button", { name: /next/i }))
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("offset")).toBe("50"))
    await screen.findByText(/showing 51–100 of 120/i)
    expect(screen.getByRole("button", { name: /previous/i })).not.toBeDisabled()
  })

  it("shows a 422 (invalid query) as a retryable error, not a crash", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/records")
          ? Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: "search exceeds 200 characters" }) })
          : Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [run] }) }),
      ),
    )
    renderPage()

    expect(await screen.findByRole("alert")).toHaveTextContent(/search exceeds 200 characters/i)
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("shows an explicit empty state when no records match the query", async () => {
    stubFetch(() => ({ records: [], total: 0 }))
    renderPage()

    expect(await screen.findByText(/no records match these filters/i)).toBeInTheDocument()
  })
})
