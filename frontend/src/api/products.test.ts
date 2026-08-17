import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "./client"
import { getProducts } from "./products"

const product = {
  record_ref: "row_2:WM-10482",
  supplier_sku: "WM-10482",
  title: { value: "Marine Sealant 3 oz", status: "VERIFIED" },
  brand: { value: "3M", status: "VERIFIED" },
  cog: "8.40",
  asin: { value: "B0000AY6CA", status: "VERIFIED" },
  hazmat_status: "ABSENT",
  bulky_status: "ABSENT",
  decision: "BUY",
}

describe("getProducts", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("returns a valid collection and accepts an empty collection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    await expect(getProducts()).resolves.toEqual({ items: [] })
  })

  it("preserves structured provenance from a valid response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [product] }) }))
    await expect(getProducts()).resolves.toEqual({ items: [product] })
  })

  it("rejects HTTP errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "unavailable" }) }))
    await expect(getProducts()).rejects.toBeInstanceOf(ApiError)
  })

  it("rejects malformed product data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [{ record_ref: "missing-fields" }] }) }))
    await expect(getProducts()).rejects.toThrow("invalid response")
  })
})
