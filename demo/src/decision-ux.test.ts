import { readFileSync } from "node:fs"
import { describe, expect, it } from "vitest"
import { defaultCatalogState, selectCatalog } from "./catalog/select"
import { applyDecisionPolicy, decideDemo, exportCsv, type DemoRecord } from "./demo-engine"

const record = (recordRef: string, roi: number, decision: DemoRecord["decision"]): DemoRecord => ({ recordRef, roi, decision, reasons: [decision], title: recordRef, brand: "Brand", url: "", image: "", cost: 10, suggested: 20, raw: {}, asin: "A", match: "DEMO_FIXTURE", selling: 20, fees: 3, shipping: 1, weight: 1, hazmat: "ABSENT", bulky: "ABSENT", profit: 6, margin: .3, issues: [], trace: [] })

describe("ROI filter and decision thresholds", () => {
  it("uses the minimum ROI only to select visible/exported records, without changing their decisions", () => {
    const records = [record("low", .2, "PASS"), record("high", .5, "BUY")]
    const result = selectCatalog(records, { ...defaultCatalogState, minRoi: "50" })
    expect(result.all.map(item => item.recordRef)).toEqual(["high"])
    expect(records.map(item => item.decision)).toEqual(["PASS", "BUY"])
    expect(exportCsv(result.all)).toContain('"high"')
    expect(exportCsv(result.all)).not.toContain('"low"')
  })

  it("changes BUY and REVIEW qualification only through decision thresholds", () => {
    const input = { profit: 20, roi: .3, match: "DEMO_FIXTURE" as const, hazmat: "ABSENT", bulky: "ABSENT" }
    expect(decideDemo(input, { modelVersion: "1", reviewRoiThreshold: .15, buyRoiThreshold: .35 }).decision).toBe("REVIEW")
    expect(decideDemo(input, { modelVersion: "1", reviewRoiThreshold: .15, buyRoiThreshold: .25 }).decision).toBe("BUY")
    expect(decideDemo(input, { modelVersion: "1", reviewRoiThreshold: .35, buyRoiThreshold: .4 }).decision).toBe("PASS")
  })

  it("keeps blockers ahead of thresholds and exports recalculated decisions", () => {
    const policy = { modelVersion: "1", reviewRoiThreshold: 0, buyRoiThreshold: 0 }
    expect(decideDemo({ profit: 20, roi: .9, match: "DEMO_FIXTURE", hazmat: "PRESENT", bulky: "ABSENT" }, policy).decision).toBe("PASS")
    const updated = applyDecisionPolicy([record("threshold", .3, "REVIEW")], { modelVersion: "1", reviewRoiThreshold: .15, buyRoiThreshold: .25 })
    expect(updated[0].decision).toBe("BUY")
    expect(exportCsv(updated)).toContain('"BUY"')
  })

  it("keeps BUY, REVIEW, and PASS mapped to green, amber, and red semantic classes", () => {
    const css = readFileSync(new URL("./style.css", import.meta.url), "utf8")
    expect(css).toMatch(/\.BUY\{color:var\(--success\)\}/)
    expect(css).toMatch(/\.REVIEW\{color:var\(--warning\)\}/)
    expect(css).toMatch(/\.PASS\{color:var\(--danger\)\}/)
  })
})
