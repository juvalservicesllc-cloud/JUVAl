import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { CatalogPage } from "./CatalogPage"

const run = (id: string, file: string) => ({
  execution_id: id, started_at: "2026-10-26T10:00:00Z", finished_at: null, status: "SUCCESS",
  input_filename: file, input_hash: "h", records_total: 2, records_processed: 2, records_successful: 2,
  records_with_errors: 0, warnings: 0,
})
const empty = { value: null, status: null }
const record = {
  record_ref: "row-1", marketplace: "US", supplier_sku: "SKU-1", asin: { value: "B000000001", status: "VERIFIED" }, upc: empty,
  title: { value: "Anchor", status: "VERIFIED" }, brand: { value: "Acme", status: "VERIFIED" }, category: empty, weight: empty,
  selling_price: { value: "20", status: "VERIFIED" }, cog: "8", shipping_per_unit: null,
  profit: { value: "8", status: "VERIFIED" }, roi: { value: "0.4", status: "VERIFIED" }, margin: { value: "0.3", status: "VERIFIED" },
  break_even_price: empty, hazmat_status: "ABSENT", bulky_status: "ABSENT", decision: "BUY", decision_reasons: [], issue_count: 0, issues: [],
}
const BRANDS: Record<string, unknown> = {
  "run-1": { items: [{ label: "Acme", count: 1 }, { label: "acme", count: 1 }], distinct: 12, not_recorded: 3 },
  "run-2": { items: [{ label: "Zeta", count: 2 }], distinct: 1, not_recorded: 0 },
}

function stub({ analyticsFails = false, brands = BRANDS }: { analyticsFails?: boolean; brands?: Record<string, unknown> } = {}) {
  const mock = vi.fn((url: string) => {
    const u = new URL(String(url))
    const runId = decodeURIComponent(u.pathname.split("/")[4] ?? "")
    const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: async () => body })
    if (u.pathname.endsWith("/analytics")) {
      return analyticsFails ? Promise.resolve({ ok: false, status: 500, json: async () => ({ detail: "internal server error" }) })
        : ok({ brands: brands[runId] })
    }
    if (u.pathname.endsWith("/records")) {
      const limit = Number(u.searchParams.get("limit")); const offset = Number(u.searchParams.get("offset"))
      return ok({ execution_id: runId, records: [record], pagination: { limit, offset, total: 60, has_more: offset + 1 < 60 } })
    }
    return ok({ items: [run("run-1", "first.csv"), run("run-2", "second.csv")] })
  })
  vi.stubGlobal("fetch", mock)
  return mock
}

const lastRecordsUrl = (mock: ReturnType<typeof vi.fn>) => {
  const calls = mock.mock.calls.filter((c: unknown[]) => new URL(String(c[0])).pathname.endsWith("/records"))
  return new URL(String(calls[calls.length - 1][0]))
}

describe("Catalog brand filter (exact, from the run's own analytics)", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); sessionStorage.clear(); localStorage.clear() })

  it("offers only the brand labels the run stored, case preserved", async () => {
    stub()
    render(<CatalogPage />)
    await screen.findByRole("option", { name: "Acme (1)" })
    const options = Array.from((screen.getByLabelText("Brand") as HTMLSelectElement).options).map((o) => o.value)
    expect(options).toEqual(["", "Acme", "acme"])   // two different brands, never merged
  })

  it("queries the server with the exact brand and returns to the first page", async () => {
    const mock = stub()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByRole("option", { name: "Acme (1)" })
    await user.click(await screen.findByRole("button", { name: "Next" }))
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("offset")).toBe("20"))

    await user.selectOptions(screen.getByLabelText("Brand"), "acme")
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("brand")).toBe("acme"))
    expect(lastRecordsUrl(mock).searchParams.get("offset")).toBe("0")
  })

  it("exports the same brand-filtered query", async () => {
    stub()
    const open = vi.spyOn(window, "open").mockImplementation(() => null)
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByRole("option", { name: "Acme (1)" })
    await user.selectOptions(screen.getByLabelText("Brand"), "Acme")
    await user.click(await screen.findByRole("button", { name: /^Export/ }))

    const url = new URL(String(open.mock.calls[0][0]))
    expect(url.pathname).toContain("/records/export")
    expect(url.searchParams.get("brand")).toBe("Acme")
  })

  it("drops the brand when the run changes and loads that run's brands", async () => {
    const mock = stub()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByRole("option", { name: "Acme (1)" })
    await user.selectOptions(screen.getByLabelText("Brand"), "Acme")
    await waitFor(() => expect(lastRecordsUrl(mock).searchParams.get("brand")).toBe("Acme"))

    await user.selectOptions(screen.getByLabelText("Run"), "run-2")
    await screen.findByRole("option", { name: "Zeta (2)" })
    expect(lastRecordsUrl(mock).pathname).toContain("run-2")
    expect(lastRecordsUrl(mock).searchParams.has("brand")).toBe(false)
    expect((screen.getByLabelText("Brand") as HTMLSelectElement).value).toBe("")
  })

  it("never remembers a brand across sessions", async () => {
    stub()
    const user = userEvent.setup()
    render(<CatalogPage />)
    await screen.findByRole("option", { name: "Acme (1)" })
    await user.selectOptions(screen.getByLabelText("Brand"), "Acme")
    await waitFor(() => expect(sessionStorage.getItem("juval.next.catalog.query.v1")).not.toBeNull())
    expect(JSON.parse(sessionStorage.getItem("juval.next.catalog.query.v1")!)).not.toHaveProperty("brand")
  })

  it("states that only the most frequent brands are listed and that unbranded records have no filter", async () => {
    stub()
    render(<CatalogPage />)
    expect(await screen.findByText(/lists the 2 most frequent of 12 brands/i)).toBeInTheDocument()
    expect(screen.getByText(/3 records have no brand recorded/i)).toBeInTheDocument()
  })

  it("disables the filter instead of guessing when the brand list is unavailable", async () => {
    stub({ analyticsFails: true })
    render(<CatalogPage />)
    expect(await screen.findByText(/brand list unavailable/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Brand")).toBeDisabled()
    expect(await screen.findByText("Anchor")).toBeInTheDocument()   // records still load
  })

  it("keeps the filter disabled while the brand list loads and when the run has no brands", async () => {
    stub({ brands: { "run-1": { items: [], distinct: 0, not_recorded: 2 }, "run-2": { items: [], distinct: 0, not_recorded: 0 } } })
    render(<CatalogPage />)
    await screen.findByLabelText("Brand")
    expect(screen.getByLabelText("Brand")).toBeDisabled()          // loading: nothing to choose yet
    expect(await screen.findByText(/2 records have no brand recorded/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Brand")).toBeDisabled()          // empty: no option is invented
    expect((screen.getByLabelText("Brand") as HTMLSelectElement).options).toHaveLength(1)
  })
})
