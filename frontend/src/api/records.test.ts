import { afterEach, describe, expect, it, vi } from "vitest"
import { getRunRecord } from "./records"

afterEach(() => vi.unstubAllGlobals())

describe("getRunRecord", () => {
  it("requests the run-scoped canonical record endpoint and preserves provenance", async () => {
    const record = { record_ref: "row/2", asin: { value: "B0TEST", status: "VERIFIED", provenance: { source: "supplier.xlsx", source_type: "SUPPLIER_FILE", verification_status: "VERIFIED", retrieved_at: "2026-08-19T00:00:00Z", method: "direct_read", confidence: null, evidence: null, source_reference: "row=2" } } }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => record })
    vi.stubGlobal("fetch", fetchMock)

    const result = await getRunRecord("run-1", "row/2")

    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/runs/run-1/records/row%2F2")
    expect(result.record_ref).toBe("row/2")
    expect(result.asin.provenance?.source_reference).toBe("row=2")
  })

  it("accepts a legacy snapshot with absent provenance metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ record_ref: "legacy", asin: { value: "B0OLD", status: "VERIFIED", provenance: null } }) })
    vi.stubGlobal("fetch", fetchMock)

    const result = await getRunRecord("run-1", "legacy")

    expect(result.asin.provenance).toBeNull()
  })
})
