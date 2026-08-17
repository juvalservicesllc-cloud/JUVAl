import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "./client"
import { getRuns } from "./runs"

describe("getRuns", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("returns typed runs, including an empty list", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    await expect(getRuns()).resolves.toEqual({ items: [] })
  })

  it("accepts the documented minimum run shape", async () => {
    const run = { execution_id: "run-1", created_at: "2026-08-17T12:00:00Z", status: "SUCCESS", total_records: 4, valid: 3, excluded: 1, errors: 0 }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [run] }) }))
    await expect(getRuns()).resolves.toEqual({ items: [run] })
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
