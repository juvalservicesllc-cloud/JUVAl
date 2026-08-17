import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "./client"
import { getRuns } from "./runs"

describe("getRuns", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("returns typed runs, including an empty list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    await expect(getRuns()).resolves.toEqual({ items: [] })
  })

  it("accepts the real RunSummaryOut shape (API_CONTRACT.md §2b)", async () => {
    const run = {
      execution_id: "run-1", started_at: "2026-08-17T12:00:00Z", finished_at: "2026-08-17T12:05:00Z",
      status: "SUCCESS", input_filename: "catalog.xlsx", input_hash: "abc123",
      records_total: 4, records_processed: 4, records_successful: 3, records_with_errors: 1, warnings: 0,
    }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [run] }) }))
    await expect(getRuns()).resolves.toEqual({ items: [run] })
  })

  it("passes limit through as a query parameter", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) })
    vi.stubGlobal("fetch", fetchMock)
    await getRuns({ limit: 5 })
    expect(fetchMock.mock.calls[0][0].toString()).toContain("limit=5")
  })

  it("rejects HTTP errors without exposing backend internals", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "unavailable" }) }))
    await expect(getRuns()).rejects.toBeInstanceOf(ApiError)
  })

  it("rejects an invalid response shape", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [{ execution_id: "incomplete" }] }) }))
    await expect(getRuns()).rejects.toThrow("invalid response")
  })
})
