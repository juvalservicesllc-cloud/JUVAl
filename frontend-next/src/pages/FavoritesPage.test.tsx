import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { App } from "../app/App"
import { favoriteKey, loadFavorites, parseFavoriteKey } from "../favorites"
import { FavoritesPage } from "./FavoritesPage"

const KEY = "juval.catalog.favorites.v1"
const run = (id: string, file: string) => ({
  execution_id: id, started_at: "2026-10-26T10:00:00Z", finished_at: null, status: "SUCCESS", input_filename: file, input_hash: "h",
  records_total: 3, records_processed: 3, records_successful: 3, records_with_errors: 0, warnings: 0,
})
const none = { value: null, status: null }
const record = (ref: string, title: string, profit: unknown = { value: "8.99", status: "VERIFIED" }) => ({
  record_ref: ref, marketplace: "US", supplier_sku: ref.split(":")[1], asin: none, upc: none,
  title: { value: title, status: "VERIFIED" }, brand: none, category: none, weight: none, selling_price: none,
  cog: "5", shipping_per_unit: null, profit, roi: { value: "0.5", status: "INFERRED" }, margin: none, break_even_price: none,
  hazmat_status: "ABSENT", bulky_status: "ABSENT", decision: "BUY", decision_reasons: [], issue_count: 0, issues: [],
})
const RECORDS: Record<string, () => Response> = {
  "run-a/row_2:A": () => new Response(JSON.stringify(record("row_2:A", "Alpha"))),
  "run-a/row_3:B": () => new Response(JSON.stringify(record("row_3:B", "Beta", { value: null, status: "NOT_FOUND" }))),
  "run-a/row_4:GONE": () => new Response(JSON.stringify({ detail: "unknown record for execution" }), { status: 404 }),
  "run-a/row_5:FAIL": () => new Response(JSON.stringify({ detail: "internal server error" }), { status: 500 }),
  "run-b/row_9:Z": () => new Response(JSON.stringify(record("row_9:Z", "Zeta"))),
}
function stub(runs = [run("run-a", "alpha.csv"), run("run-b", "beta.csv"), run("run-c", "no-stars.csv")]) {
  const mock = vi.fn((url: string) => {
    const path = new URL(String(url)).pathname
    const m = path.match(/^\/api\/v1\/runs\/([^/]+)\/records\/(.+)$/)
    if (m) return Promise.resolve(RECORDS[`${decodeURIComponent(m[1])}/${decodeURIComponent(m[2])}`]())
    return Promise.resolve(new Response(JSON.stringify({ items: runs })))
  })
  vi.stubGlobal("fetch", mock)
  return mock
}
const star = (...keys: string[]) => localStorage.setItem(KEY, JSON.stringify(keys))
const recordCalls = (mock: ReturnType<typeof stub>) => mock.mock.calls.map((c) => new URL(String(c[0])).pathname).filter((p) => p.includes("/records/"))
const card = (title: string) => screen.getByRole("link", { name: title }).closest("li") as HTMLElement

describe("Favorites for one run", () => {
  beforeEach(() => star(
    favoriteKey("run-a", "row_2:A"), favoriteKey("run-a", "row_3:B"), favoriteKey("run-a", "row_4:GONE"), favoriteKey("run-a", "row_5:FAIL"),
    favoriteKey("run-b", "row_9:Z"),
  ))
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); history.pushState({}, "", "/") })

  it("splits a key at the first colon, because record refs contain colons", () => {
    expect(parseFavoriteKey("run-a:row_2:SUP-001")).toEqual({ executionId: "run-a", recordRef: "row_2:SUP-001" })
    expect(parseFavoriteKey("no-colon")).toBeNull()
    expect(parseFavoriteKey(":x")).toBeNull()
  })

  it("resolves only the selected run's starred records, each by its own lookup", async () => {
    const mock = stub()
    render(<FavoritesPage go={vi.fn()} />)
    await screen.findByRole("link", { name: "Alpha" })
    await waitFor(() => expect(recordCalls(mock)).toHaveLength(4))
    expect(recordCalls(mock).every((p) => p.startsWith("/api/v1/runs/run-a/records/"))).toBe(true)
    expect(recordCalls(mock)).toContain("/api/v1/runs/run-a/records/row_2%3AA")
  })

  it("offers only runs that have stars, with their counts", async () => {
    stub()
    render(<FavoritesPage go={vi.fn()} />)
    const select = await screen.findByLabelText("Run")
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.textContent)).toEqual([
      expect.stringMatching(/^alpha\.csv .*\(4\)$/), expect.stringMatching(/^beta\.csv .*\(1\)$/),
    ])
  })

  it("shows each record's decision and figures beside their own status", async () => {
    stub()
    render(<FavoritesPage go={vi.fn()} />)
    await screen.findByRole("link", { name: "Alpha" })
    const alpha = card("Alpha")
    expect(alpha).toHaveTextContent("BUY")
    expect(alpha).toHaveTextContent("$8.99")
    expect(within(alpha).getByLabelText("Status: VERIFIED")).toBeInTheDocument()
    expect(within(alpha).getByLabelText("Status: INFERRED")).toBeInTheDocument()
    expect(alpha).toHaveTextContent("alpha.csv")
    const beta = await screen.findByRole("link", { name: "Beta" })
    expect(within(beta.closest("li") as HTMLElement).getByLabelText("Status: NOT FOUND")).toBeInTheDocument()
    expect(beta.closest("li")).not.toHaveTextContent("$0")
  })

  it("keeps a deleted or failing record visible and removable without blocking the others", async () => {
    stub()
    render(<FavoritesPage go={vi.fn()} />)
    expect(await screen.findByText(/no longer exists in this run/)).toHaveTextContent("row_4:GONE")
    expect(await screen.findByRole("alert")).toHaveTextContent("row_5:FAIL")
    expect(screen.getByRole("link", { name: "Alpha" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Remove row_4:GONE from favorites" })).toBeInTheDocument()
  })

  it("removes a star from storage and from the page, without refetching the rest", async () => {
    const mock = stub()
    render(<FavoritesPage go={vi.fn()} />)
    await screen.findByRole("link", { name: "Alpha" })
    await waitFor(() => expect(recordCalls(mock)).toHaveLength(4))
    await userEvent.setup().click(screen.getByRole("button", { name: "Remove Alpha from favorites" }))
    expect(screen.queryByRole("link", { name: "Alpha" })).not.toBeInTheDocument()
    expect(loadFavorites()).not.toContain(favoriteKey("run-a", "row_2:A"))
    expect(loadFavorites()).toContain(favoriteKey("run-b", "row_9:Z"))
    expect(recordCalls(mock)).toHaveLength(4)
  })

  it("switches to another run's stars", async () => {
    stub()
    render(<FavoritesPage go={vi.fn()} />)
    await screen.findByRole("link", { name: "Alpha" })
    await userEvent.setup().selectOptions(screen.getByLabelText("Run"), "run-b")
    expect(await screen.findByRole("link", { name: "Zeta" })).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: "Alpha" })).not.toBeInTheDocument()
  })

  it("links to Product Detail inside the app, in the same tab", async () => {
    stub()
    history.pushState({}, "", "/favorites?run=run-b")
    render(<App />)
    const link = await screen.findByRole("link", { name: "Zeta" })
    expect(link).not.toHaveAttribute("target")
    await userEvent.setup().click(link)
    expect(location.pathname).toBe("/run/run-b/product/row_9%3AZ")
  })

  it("shows an empty state with a way to Catalog when nothing is starred", async () => {
    localStorage.clear()
    stub()
    const go = vi.fn()
    render(<FavoritesPage go={go} />)
    expect(await screen.findByText(/no favorites yet/i)).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: "Browse Catalog" }))
    expect(go).toHaveBeenCalledWith("/catalog")
  })

  it("says when starred runs are not in the run list and lets them be forgotten", async () => {
    stub([run("run-c", "no-stars.csv")])
    render(<FavoritesPage go={vi.fn()} />)
    expect(await screen.findByText(/2 starred runs are not in the run list/)).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole("button", { name: "Forget those stars" }))
    expect(loadFavorites()).toEqual([])
  })

  it("reports a failure to list runs with a retry", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ detail: "internal server error" }), { status: 500 }))))
    render(<FavoritesPage go={vi.fn()} />)
    expect(await screen.findByRole("alert")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument()
  })

  it("says the stars are stored in this browser only", async () => {
    stub()
    render(<FavoritesPage go={vi.fn()} />)
    await screen.findByRole("link", { name: "Alpha" })
    expect(screen.getByText(/in this browser only — not saved on the server/)).toBeInTheDocument()
  })
})
