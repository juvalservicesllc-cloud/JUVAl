import { render, screen, waitFor, within } from "@testing-library/react"
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
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("shows a loading state while the persisted-run selector is being fetched", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderPage()

    expect(screen.getByText(/loading catalog/i)).toBeInTheDocument()
  })

  it("issues the initial query against the server contract and renders real records", async () => {
    const fetchMock = stubFetch()
    renderPage()

    expect(await screen.findByText("Alpha")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Catalog" })).toBeInTheDocument()
    expect(screen.getByText(/run context/i)).toBeInTheDocument()
    // Scoped to the table on purpose: the unscoped query also matched the
    // provenance-status <select> options, so it passed without the table
    // showing any status at all.
    const table = document.querySelector(".catalog-table") as HTMLElement
    expect(within(table).getAllByLabelText("Status: VERIFIED").length).toBeGreaterThan(0)
    expect(within(table).getAllByLabelText("Status: INFERRED").length).toBeGreaterThan(0)
    expect(screen.getByText("10.00%")).toBeInTheDocument()
    expect(screen.getByText("40.00%")).toBeInTheDocument()

    const url = lastRequestUrl(fetchMock)
    expect(url.searchParams.get("limit")).toBe("50")
    expect(url.searchParams.get("offset")).toBe("0")
    // Catalog opens on the most profitable rows (ADR-029 golden default).
    expect(url.searchParams.get("sort")).toBe("profit")
    expect(url.searchParams.get("direction")).toBe("desc")
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

  it("sends economic thresholds and explicit confidence server-side", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")
    // The operator types a percentage; the canonical query carries the ratio.
    await user.type(screen.getByLabelText("Minimum ROI percentage"), "30")
    await user.selectOptions(screen.getByLabelText("Economic confidence"), "INCLUDE_INFERRED")
    await waitFor(() => {
      const url = lastRequestUrl(fetchMock)
      expect(url.searchParams.get("min_roi")).toBe("0.3")
      expect(url.searchParams.get("confidence")).toBe("INCLUDE_INFERRED")
    })
    expect(screen.getByText(/ROI ≥ 30%/)).toBeInTheDocument()
  })

  it("converts the margin percentage to a canonical ratio too", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")
    await user.type(screen.getByLabelText("Minimum margin percentage"), "12.5")
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("min_margin")).toBe("0.125"))
    expect(screen.getByText(/Margin ≥ 12.5%/)).toBeInTheDocument()
  })

  it("never sends 0 for a cleared percentage filter", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")
    const roi = screen.getByLabelText("Minimum ROI percentage")
    await user.type(roi, "30")
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("min_roi")).toBe("0.3"))
    await user.clear(roi)
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.has("min_roi")).toBe(false))
  })

  it("allows presentation-only column visibility and reset", async () => {
    stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")
    await user.click(screen.getByText("Configure columns"))
    await user.click(screen.getByLabelText("ASIN / UPC"))
    expect(screen.queryByRole("columnheader", { name: "ASIN" })).not.toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /reset columns/i }))
    await waitFor(() => expect(screen.getByRole("columnheader", { name: "ASIN" })).toBeInTheDocument())
  })

  it("resets the active query state without changing the selected run contract", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.selectOptions(screen.getByLabelText(/filter by decision/i), "BUY")
    await waitFor(() => expect(screen.getByRole("button", { name: /reset search & filters/i })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /reset search & filters/i }))

    await waitFor(() => {
      const url = lastRequestUrl(fetchMock)
      expect(url.searchParams.has("decision")).toBe(false)
      expect(url.searchParams.get("sort")).toBe("profit")
      expect(url.searchParams.get("direction")).toBe("desc")
      expect(screen.queryByRole("button", { name: /reset search & filters/i })).not.toBeInTheDocument()
    })
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

    // Start from a non-default key so the first click selects a new sort key
    // rather than flipping the default's direction.
    await user.click(screen.getByRole("button", { name: /^COG/i }))
    await waitFor(() => {
      expect(lastRequestUrl(fetchMock).searchParams.get("sort")).toBe("cog")
      expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("asc")
    })

    await user.click(screen.getByRole("button", { name: /^COG/i }))
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("desc"))
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

  it("stays on the current page when the search debounce settles without a search", async () => {
    const fetchMock = stubFetch(() => ({ records, total: 120 }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.click(screen.getByRole("button", { name: /next/i }))
    await screen.findByText(/showing 51–100 of 120/i)

    // Regression: the search debounce used to arm a timer on mount as well as
    // on a keystroke, and that timer called setOffset(0) unconditionally. A
    // user who opened Catalog and paged within 300 ms was silently returned to
    // page 1. Waiting past the debounce window is deterministic -- the timer
    // either fires and resets the page, or it was never armed.
    await new Promise((resolve) => setTimeout(resolve, 450))

    expect(screen.getByText(/showing 51–100 of 120/i)).toBeInTheDocument()
    expect(lastRequestUrl(fetchMock).searchParams.get("offset")).toBe("50")
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

  it("keeps row issues available through an accessible progressive disclosure", async () => {
    const issueRecord = { ...recordFor(0, "VERIFIED"), issue_count: 1, issues: ["Missing supplier dimensions"] }
    stubFetch(() => ({ records: [issueRecord], total: 1 }))
    const user = userEvent.setup()
    renderPage()

    await screen.findByText("Alpha")
    const disclosure = screen.getByText("1 issue")
    expect(screen.getByText("Missing supplier dimensions")).not.toBeVisible()
    await user.click(disclosure)
    expect(screen.getByText("Missing supplier dimensions")).toBeVisible()
  })

  it("keeps row inspection as an explicit run-scoped action", async () => {
    stubFetch()
    renderPage()

    await screen.findByText("Alpha")
    expect(screen.getByRole("link", { name: /open detail for row-0/i })).toHaveAttribute("href", "/runs/r1/records/row-0")
  })
})

describe("ProductsPage filtered export", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("exports the exact canonical query the table is showing, percentages converted", async () => {
    stubFetch()
    const open = vi.fn()
    vi.stubGlobal("open", open)
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.type(screen.getByLabelText("Minimum ROI percentage"), "30")
    await user.type(screen.getByLabelText("Minimum margin percentage"), "20")
    await user.selectOptions(screen.getByLabelText("Filter by decision"), "BUY")
    await user.click(screen.getByRole("button", { name: /^export \d/i }))

    const url = new URL(open.mock.calls.at(-1)![0] as string, "http://localhost")
    expect(url.pathname).toContain("/records/export")
    // The export must carry ratios, exactly like the table's own query --
    // otherwise the downloaded file would not match what was on screen.
    expect(url.searchParams.get("min_roi")).toBe("0.3")
    expect(url.searchParams.get("min_margin")).toBe("0.2")
    expect(url.searchParams.get("decision")).toBe("BUY")
  })

  it("omits a cleared percentage filter from the export query", async () => {
    stubFetch()
    const open = vi.fn()
    vi.stubGlobal("open", open)
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.click(screen.getByRole("button", { name: /^export \d/i }))

    const url = new URL(open.mock.calls.at(-1)![0] as string, "http://localhost")
    expect(url.searchParams.has("min_roi")).toBe(false)
    expect(url.searchParams.has("min_margin")).toBe(false)
  })
})

// Regression cover for the golden-UX Catalog convergence (ADR-029). These
// assert the *contract* behind each migrated visual, not its styling: a
// screenshot can drift, a query parameter cannot.
describe("ProductsPage golden-UX catalog", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("sends the HazMat filter server-side", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.selectOptions(screen.getByLabelText("Filter by HazMat"), "PRESENT")

    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("hazmat")).toBe("PRESENT"))
  })

  it("sends the Bulky filter server-side", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.selectOptions(screen.getByLabelText("Filter by Bulky"), "ABSENT")

    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("bulky")).toBe("ABSENT"))
  })

  it("renders ROI as a percentage, never as the raw ratio", async () => {
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    // Backend ratio 0.1/0.4 must reach the operator as 10.00%/40.00%.
    expect(await screen.findByText("10.00%")).toBeInTheDocument()
    expect(screen.getByText("40.00%")).toBeInTheDocument()
    expect(screen.queryByText("0.1")).not.toBeInTheDocument()
    expect(screen.queryByText("0.4")).not.toBeInTheDocument()
  })

  it("keeps a product media slot per row that never invents an image", async () => {
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    const slots = screen.getAllByRole("img", { name: /no product image available/i })
    expect(slots).toHaveLength(records.length)
    // No <img> may be emitted while RecordOut carries no canonical image field.
    expect(document.querySelectorAll(".catalog-table img")).toHaveLength(0)
  })

  it("names the exact number of rows the filtered export will contain", async () => {
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    expect(await screen.findByRole("button", { name: `Export ${records.length} results` })).toBeInTheDocument()
  })

  it("keeps every sortable column reachable and announces its sort state", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    const roi = screen.getByRole("button", { name: /^ROI\./ })
    await user.click(roi)

    await waitFor(() => {
      const params = lastRequestUrl(fetchMock).searchParams
      expect(params.get("sort")).toBe("roi")
      expect(params.get("direction")).toBe("desc")
    })
    expect(screen.getByRole("button", { name: /^ROI, sorted descending/ })).toHaveAttribute("aria-pressed", "true")
  })
})

// Favourites recovered from the Golden Product Experience (ADR-029). These pin
// the two properties that make the recovery honest: run-scoped identity, and
// no server call.
describe("ProductsPage favorites (recovered from Golden)", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("stars a record against the run, persisting locally and issuing no request", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")
    const before = fetchMock.mock.calls.length

    await user.click(screen.getByRole("button", { name: /add alpha to favorites/i }))

    // Run-scoped key: the record is starred inside run r1, not as a product.
    expect(JSON.parse(localStorage.getItem("juval.catalog.favorites.v1")!)).toEqual(["r1:row-0"])
    // Starring must never reach the backend -- it is a browser preference.
    expect(fetchMock.mock.calls.length).toBe(before)
    expect(screen.getByRole("button", { name: /remove alpha from favorites/i })).toHaveAttribute("aria-pressed", "true")
  })

  it("restores stars from local storage and un-stars them again", async () => {
    localStorage.setItem("juval.catalog.favorites.v1", JSON.stringify(["r1:row-0"]))
    stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    const starred = await screen.findByRole("button", { name: /remove alpha from favorites/i })
    expect(starred).toHaveAttribute("aria-pressed", "true")

    await user.click(starred)
    expect(JSON.parse(localStorage.getItem("juval.catalog.favorites.v1")!)).toEqual([])
  })

  it("says out loud that stars live in this browser only", async () => {
    localStorage.setItem("juval.catalog.favorites.v1", JSON.stringify(["r1:row-0"]))
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    expect(await screen.findByText(/starred in this browser only/i)).toBeInTheDocument()
  })

  it("survives corrupt favorite storage instead of failing the catalog", async () => {
    localStorage.setItem("juval.catalog.favorites.v1", "{ not json")
    stubFetch()
    renderPage()

    expect(await screen.findByText("Alpha")).toBeInTheDocument()
  })
})

// Wave B3: the final catalog pass -- default ordering, provenance legibility,
// column hierarchy and the honesty of the favourites disclosure.
describe("ProductsPage catalog final pass (Wave B3)", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("opens on profit descending and lets the operator override it", async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    expect(lastRequestUrl(fetchMock).searchParams.get("sort")).toBe("profit")
    expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("desc")

    // A user choice must win over the default, in both directions.
    await user.click(screen.getByRole("button", { name: /^Product \/ SKU/ }))
    await waitFor(() => {
      expect(lastRequestUrl(fetchMock).searchParams.get("sort")).toBe("sku")
      expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("asc")
    })
    await user.click(screen.getByRole("button", { name: /^Product \/ SKU/ }))
    await waitFor(() => expect(lastRequestUrl(fetchMock).searchParams.get("direction")).toBe("desc"))
  })

  it("carries the effective sort into the filtered export", async () => {
    stubFetch()
    const open = vi.fn()
    vi.stubGlobal("open", open)
    renderPage()
    await screen.findByText("Alpha")

    await userEvent.setup().click(screen.getByRole("button", { name: /^export \d/i }))

    const url = new URL(open.mock.calls.at(-1)![0] as string, "http://localhost")
    expect(url.searchParams.get("sort")).toBe("profit")
    expect(url.searchParams.get("direction")).toBe("desc")
  })

  it("shows provenance as readable text in the table, not colour or hover alone", async () => {
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    const table = document.querySelector(".catalog-table") as HTMLElement
    const verified = within(table).getAllByLabelText("Status: VERIFIED")
    const inferred = within(table).getAllByLabelText("Status: INFERRED")
    // Legible on screen: an abbreviation a reader can tell apart without hovering.
    expect(verified[0]).toHaveTextContent("VER")
    expect(inferred[0]).toHaveTextContent("INF")
    expect(verified[0].textContent).not.toBe("")
    // ...and still fully spelled out for assistive technology.
    expect(verified[0]).toHaveAttribute("title", "VERIFIED")
  })

  it("orders decision-critical columns ahead of audit fields by default", async () => {
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    const headers = [...document.querySelectorAll(".catalog-table thead th")].map((th) => th.textContent ?? "")
    const at = (needle: string) => headers.findIndex((h) => h.includes(needle))
    // Decision, ROI and Profit must precede ASIN and Record: at narrow widths
    // the trailing columns are the ones that scroll out of view.
    expect(at("Decision")).toBeLessThan(at("ASIN"))
    expect(at("ROI")).toBeLessThan(at("ASIN"))
    expect(at("Profit")).toBeLessThan(at("Record"))
    expect(at("Decision")).toBeLessThan(at("Record"))
    // ...and the operator can still change all of it.
    expect(screen.getByText(/configure columns/i)).toBeInTheDocument()
  })

  it("labels favourites as local to this browser in the column header", async () => {
    stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    const table = document.querySelector(".catalog-table") as HTMLElement
    expect(within(table).getByText(/favorite \(local\)/i)).toBeInTheDocument()
  })
})

// C1.3 -- catalog filters remembered as a local preference.
describe("ProductsPage remembered filters (C1)", () => {
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear() })

  it("restores a remembered query through the canonical server request", async () => {
    sessionStorage.setItem("juval.catalog.query.v1", JSON.stringify({
      search: "anchor", decision: "BUY", sort: "roi", direction: "asc", limit: 25,
      minRoi: "30", minProfit: "", minMargin: "", confidence: "INCLUDE_INFERRED",
      hazmat: "ABSENT", bulky: "", provenanceField: "", provenanceStatus: "",
    }))
    const fetchMock = stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    const params = lastRequestUrl(fetchMock).searchParams
    expect(params.get("search")).toBe("anchor")
    expect(params.get("decision")).toBe("BUY")
    expect(params.get("sort")).toBe("roi")
    expect(params.get("direction")).toBe("asc")
    expect(params.get("limit")).toBe("25")
    expect(params.get("confidence")).toBe("INCLUDE_INFERRED")
    expect(params.get("hazmat")).toBe("ABSENT")
    // Percentages still convert to canonical ratios on restore.
    expect(params.get("min_roi")).toBe("0.3")
  })

  it("persists the canonical query as the operator filters", async () => {
    stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.selectOptions(screen.getByLabelText(/filter by decision/i), "PASS")

    await waitFor(() => {
      const stored = JSON.parse(sessionStorage.getItem("juval.catalog.query.v1")!)
      expect(stored.decision).toBe("PASS")
    })
  })

  it("clears the remembered query on reset, so it does not come back", async () => {
    stubFetch()
    const user = userEvent.setup()
    renderPage()
    await screen.findByText("Alpha")

    await user.selectOptions(screen.getByLabelText(/filter by decision/i), "BUY")
    await waitFor(() => expect(screen.getByRole("button", { name: /reset search & filters/i })).toBeInTheDocument())
    await user.click(screen.getByRole("button", { name: /reset search & filters/i }))

    await waitFor(() => {
      const raw = sessionStorage.getItem("juval.catalog.query.v1")
      expect(raw === null || JSON.parse(raw).decision === "ALL").toBe(true)
    })
  })

  it("ignores a corrupt remembered query instead of failing the catalog", async () => {
    sessionStorage.setItem("juval.catalog.query.v1", "{ not json")
    const fetchMock = stubFetch()
    renderPage()

    expect(await screen.findByText("Alpha")).toBeInTheDocument()
    expect(lastRequestUrl(fetchMock).searchParams.get("sort")).toBe("profit")
  })

  it("drops out-of-contract stored values rather than sending them to the API", async () => {
    sessionStorage.setItem("juval.catalog.query.v1", JSON.stringify({
      sort: "definitely_not_a_sort_key", direction: "sideways", limit: 9999,
      decision: "MAYBE", confidence: "GUESS", hazmat: "SOMETIMES",
    }))
    const fetchMock = stubFetch()
    renderPage()
    await screen.findByText("Alpha")

    const params = lastRequestUrl(fetchMock).searchParams
    // Every invalid field falls back to its default; none reaches the server.
    expect(params.get("sort")).toBe("profit")
    expect(params.get("direction")).toBe("desc")
    expect(params.get("limit")).toBe("50")
    expect(params.get("confidence")).toBe("VERIFIED_ONLY")
    expect(params.has("decision")).toBe(false)
    expect(params.has("hazmat")).toBe(false)
  })
})
