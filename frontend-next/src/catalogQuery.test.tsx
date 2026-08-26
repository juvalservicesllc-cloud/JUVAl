import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CatalogPage } from "./pages/CatalogPage"

const KEY = "juval.next.catalog.query.v1"

const runs = [
  { execution_id: "run-1", started_at: "2026-08-20T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "a.csv", input_hash: "h1", records_total: 2, records_processed: 2, records_successful: 2, records_with_errors: 0, warnings: 0 },
  { execution_id: "run-2", started_at: "2026-08-19T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "b.csv", input_hash: "h2", records_total: 2, records_processed: 2, records_successful: 2, records_with_errors: 0, warnings: 0 },
]
const empty = { value: null, status: null }
const record = {
  record_ref: "row-0", marketplace: "US", supplier_sku: "SKU-0",
  asin: { value: "ASIN-0", status: "VERIFIED" }, upc: empty,
  title: { value: "Alpha anchor", status: "VERIFIED" }, brand: { value: "Acme", status: "VERIFIED" }, category: empty,
  weight: empty, selling_price: { value: "20", status: "VERIFIED" }, cog: "8", shipping_per_unit: "1",
  profit: { value: "2", status: "VERIFIED" }, roi: { value: "0.1", status: "VERIFIED" }, margin: { value: "0.3", status: "VERIFIED" },
  break_even_price: empty, hazmat_status: "ABSENT", bulky_status: "UNKNOWN",
  decision: "REVIEW", decision_reasons: [], issue_count: 0, issues: [],
}

function stubFetch(total = 120) {
  const mock = vi.fn((url: string) => {
    if (String(url).includes("/records")) {
      const params = new URL(String(url)).searchParams
      const limit = Number(params.get("limit") ?? 20)
      const offset = Number(params.get("offset") ?? 0)
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ execution_id: "run-1", records: [record], pagination: { limit, offset, total, has_more: offset + 1 < total } }) })
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: runs }) })
  })
  vi.stubGlobal("fetch", mock)
  return mock
}

const lastRecordsUrl = (mock: ReturnType<typeof vi.fn>): URL => {
  const calls = mock.mock.calls.filter((c: unknown[]) => String(c[0]).includes("/records"))
  return new URL(String(calls[calls.length - 1][0]))
}
const stored = () => JSON.parse(sessionStorage.getItem(KEY) ?? "{}")

describe("Catalog filter persistence (milestone 2B)", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("persists a filter and restores it on a fresh mount, as the same server query", async () => {
    const first = stubFetch()
    const user = userEvent.setup()
    const view = render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await user.selectOptions(screen.getByLabelText("Decision"), "BUY")
    await user.selectOptions(screen.getByLabelText("Hazmat"), "PRESENT")
    await waitFor(() => expect(lastRecordsUrl(first).searchParams.get("decision")).toBe("BUY"))

    // Leaving Catalog and coming back is a fresh mount of the component.
    view.unmount()
    const second = stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    const params = lastRecordsUrl(second).searchParams
    expect(params.get("decision")).toBe("BUY")
    expect(params.get("hazmat")).toBe("PRESENT")
    expect((screen.getByLabelText("Decision") as HTMLSelectElement).value).toBe("BUY")
  })

  it("restores every supported preference into the canonical query", async () => {
    sessionStorage.setItem(KEY, JSON.stringify({
      search: "anchor", decision: "PASS", sort: "roi", direction: "asc", limit: 50,
      minRoi: "30", minProfit: "5", minMargin: "20", confidence: "INCLUDE_INFERRED",
      hazmat: "ABSENT", bulky: "PRESENT", provenanceField: "asin", provenanceStatus: "NOT_FOUND",
    }))
    const mock = stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    const p = lastRecordsUrl(mock).searchParams
    expect(p.get("search")).toBe("anchor")
    expect(p.get("decision")).toBe("PASS")
    expect(p.get("sort")).toBe("roi")
    expect(p.get("direction")).toBe("asc")
    expect(p.get("limit")).toBe("50")
    expect(p.get("confidence")).toBe("INCLUDE_INFERRED")
    expect(p.get("hazmat")).toBe("ABSENT")
    expect(p.get("bulky")).toBe("PRESENT")
    expect(p.get("provenance_field")).toBe("asin")
    expect(p.get("provenance_status")).toBe("NOT_FOUND")
    // Percentages still convert to canonical ratios on restore.
    expect(p.get("min_roi")).toBe("0.3")
    expect(p.get("min_margin")).toBe("0.2")
    expect(p.get("min_profit")).toBe("5")
  })

  it("never restores the selected run from stored preferences", async () => {
    // A stale run id would silently point Catalog at a different dataset than
    // the one the operator navigated to.
    sessionStorage.setItem(KEY, JSON.stringify({ decision: "BUY", runId: "run-2", execution_id: "run-2" }))
    const mock = stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    expect(lastRecordsUrl(mock).pathname).toContain("run-1")
    expect(stored().runId).toBeUndefined()
    expect(stored().execution_id).toBeUndefined()
  })

  it("never restores the page offset", async () => {
    sessionStorage.setItem(KEY, JSON.stringify({ decision: "BUY", offset: 80 }))
    const mock = stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    expect(lastRecordsUrl(mock).searchParams.get("offset")).toBe("0")
    expect(stored().offset).toBeUndefined()
  })

  it("does not persist paging as the operator moves through pages", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await user.click(screen.getByRole("button", { name: "Next" }))
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("offset")).toBe("20"))

    expect(stored().offset).toBeUndefined()
  })

  it("caches no server result in session storage", async () => {
    stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    const raw = sessionStorage.getItem(KEY) ?? ""
    expect(raw).not.toContain("Alpha anchor")
    expect(raw).not.toContain("row-0")
    expect(stored().records).toBeUndefined()
  })

  it("resets active filters, the sort default and the stored copy together", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await user.selectOptions(screen.getByLabelText("Decision"), "BUY")
    await user.click(screen.getByRole("button", { name: /^Cost/ }))
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("sort")).toBe("cog"))

    await user.click(screen.getByRole("button", { name: /reset filters/i }))

    await waitFor(() => {
      const p = lastRecordsUrl(mock).searchParams
      expect(p.has("decision")).toBe(false)
      expect(p.get("sort")).toBe("profit")
      expect(p.get("direction")).toBe("desc")
      expect(p.get("offset")).toBe("0")
    })
    // The stored copy must go too, or the next mount restores what was cleared.
    expect(stored().decision === undefined || stored().decision === "ALL").toBe(true)
    expect(stored().sort === undefined || stored().sort === "profit").toBe(true)
  })

  it("ignores corrupt session storage instead of failing the catalog", async () => {
    sessionStorage.setItem(KEY, "{ not json")
    const mock = stubFetch()
    render(<CatalogPage />)

    expect(await screen.findByText("Alpha anchor")).toBeInTheDocument()
    expect(lastRecordsUrl(mock).searchParams.get("sort")).toBe("profit")
  })

  it("drops out-of-contract stored values rather than sending them to FastAPI", async () => {
    sessionStorage.setItem(KEY, JSON.stringify({
      sort: "supplier_url_from_an_older_build", direction: "sideways", limit: 9999,
      decision: "MAYBE", confidence: "GUESS", hazmat: "SOMETIMES",
      provenanceField: "nope", provenanceStatus: "PROBABLY", minRoi: "abc",
    }))
    const mock = stubFetch()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    const p = lastRecordsUrl(mock).searchParams
    // An obsolete sort must never reach the API and come back a 422.
    expect(p.get("sort")).toBe("profit")
    expect(p.get("direction")).toBe("desc")
    expect(p.get("limit")).toBe("20")
    expect(p.get("confidence")).toBe("VERIFIED_ONLY")
    expect(p.has("decision")).toBe(false)
    expect(p.has("hazmat")).toBe(false)
    expect(p.has("provenance_field")).toBe(false)
    expect(p.has("min_roi")).toBe(false)
  })

  it("keeps the filtered export equivalent to the restored query, minus pagination", async () => {
    sessionStorage.setItem(KEY, JSON.stringify({ decision: "BUY", minRoi: "30", hazmat: "ABSENT", sort: "roi", direction: "asc", limit: 50 }))
    stubFetch()
    const open = vi.fn()
    vi.stubGlobal("open", open)
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")

    await userEvent.setup().click(screen.getByRole("button", { name: /^Export \d/ }))

    const url = new URL(String(open.mock.calls.at(-1)?.[0]))
    expect(url.pathname).toContain("/records/export")
    expect(url.searchParams.get("decision")).toBe("BUY")
    expect(url.searchParams.get("min_roi")).toBe("0.3")
    expect(url.searchParams.get("hazmat")).toBe("ABSENT")
    expect(url.searchParams.get("sort")).toBe("roi")
    expect(url.searchParams.has("limit")).toBe(false)
    expect(url.searchParams.has("offset")).toBe(false)
  })

  it("leaves favourites in local storage, untouched by query persistence", async () => {
    const mock = stubFetch()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByText("Alpha anchor")
    const before = mock.mock.calls.length

    await user.click(screen.getByRole("button", { name: /add alpha anchor to favorites/i }))

    expect(JSON.parse(localStorage.getItem("juval.catalog.favorites.v1") ?? "[]")).toEqual(["run-1:row-0"])
    expect(sessionStorage.getItem(KEY) ?? "").not.toContain("row-0")
    expect(mock.mock.calls.length).toBe(before)
  })
})
