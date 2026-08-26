import { describe, expect, it } from "vitest"
import { catalogSearchParams, filteredExportUrl } from "./catalog"
import type { CatalogQuery } from "./types"

const base: CatalogQuery = {
  limit: 20, offset: 0, search: "", decision: "ALL", sort: "profit", direction: "desc",
  minRoi: "", minProfit: "", minMargin: "", confidence: "VERIFIED_ONLY",
  hazmat: "", bulky: "", provenanceField: "", provenanceStatus: "",
}

describe("catalog query contract", () => {
  it("opens on profit descending, verified-only, paginated server-side", () => {
    const p = catalogSearchParams(base)
    expect(p.get("sort")).toBe("profit")
    expect(p.get("direction")).toBe("desc")
    expect(p.get("confidence")).toBe("VERIFIED_ONLY")
    expect(p.get("limit")).toBe("20")
    expect(p.get("offset")).toBe("0")
  })

  it("converts ROI and margin percentages into canonical ratios", () => {
    const p = catalogSearchParams({ ...base, minRoi: "30", minMargin: "20" })
    expect(p.get("min_roi")).toBe("0.3")
    expect(p.get("min_margin")).toBe("0.2")
  })

  it("omits a cleared threshold rather than sending 0", () => {
    // Sending 0 would silently mean "at least 0%" and change the result set.
    const p = catalogSearchParams({ ...base, minRoi: "", minProfit: "", minMargin: "" })
    expect(p.has("min_roi")).toBe(false)
    expect(p.has("min_profit")).toBe(false)
    expect(p.has("min_margin")).toBe(false)
  })

  it("never sends ALL as a decision filter", () => {
    expect(catalogSearchParams(base).has("decision")).toBe(false)
    expect(catalogSearchParams({ ...base, decision: "BUY" }).get("decision")).toBe("BUY")
  })

  it("maps the Amazon control onto the ASIN field's verification status", () => {
    const p = catalogSearchParams({ ...base, provenanceField: "asin", provenanceStatus: "NOT_FOUND" })
    expect(p.get("provenance_field")).toBe("asin")
    expect(p.get("provenance_status")).toBe("NOT_FOUND")
  })

  it("passes risk filters straight through", () => {
    const p = catalogSearchParams({ ...base, hazmat: "PRESENT", bulky: "ABSENT" })
    expect(p.get("hazmat")).toBe("PRESENT")
    expect(p.get("bulky")).toBe("ABSENT")
  })

  it("exports the identical query the table is showing, minus pagination", () => {
    const query = { ...base, search: "anchor", decision: "BUY", minRoi: "30", hazmat: "ABSENT", offset: 40 }
    const url = new URL(filteredExportUrl("run-1", query))
    expect(url.pathname).toContain("/records/export")
    expect(url.searchParams.get("search")).toBe("anchor")
    expect(url.searchParams.get("decision")).toBe("BUY")
    expect(url.searchParams.get("min_roi")).toBe("0.3")
    expect(url.searchParams.get("hazmat")).toBe("ABSENT")
    expect(url.searchParams.get("sort")).toBe("profit")
    // An export covers the whole filtered set, not the visible page.
    expect(url.searchParams.has("limit")).toBe(false)
    expect(url.searchParams.has("offset")).toBe(false)
  })
})
