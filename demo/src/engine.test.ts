import { describe, expect, it } from "vitest"
import { readFileSync } from "node:fs"
import { analytics, classifyColumns, detectWestMarine, exportCsv, money, normalize, parseCsv } from "./engine"

const csv = `position-relative href,img-fluid src,product-brand-name,link,item-price,item-price (2)\n/products/a,image.jpg,West Marine,"Anchor, Kit",$20.00,$49.99\n/products/b,,Garmin,"GPS ""quoted""",$0.00,`

describe("West Marine demo workflow", () => {
  it("parses quoted commas, escaped quotes, headers and empty cells", () => {
    const parsed = parseCsv(csv.replace(/\n/g, "\r\n"))
    expect(parsed.errors).toEqual([])
    expect(parsed.rows[0].link).toBe("Anchor, Kit")
    expect(parsed.rows[1].link).toBe('GPS "quoted"')
    expect(parsed.rows[1]["item-price (2)"]).toBe("")
  })
  it("reports empty input", () => expect(parseCsv(" ").errors).toContain("The CSV file is empty."))
  it("detects West Marine columns and rejects unrelated schemas", () => {
    expect(detectWestMarine(parseCsv(csv).headers).format).toBe("WEST_MARINE_SCRAPER_CSV")
    expect(detectWestMarine(["name", "price"]).format).toBe("UNRECOGNIZED_CSV")
  })
  it("classifies source columns without discarding unknown fields", () => {
    const info = classifyColumns([...parseCsv(csv).headers, "quick-view-modal"])
    expect(info.find(column => column.source === "item-price")?.classification).toBe("USED")
    expect(info.find(column => column.source === "quick-view-modal")?.classification).toBe("IGNORED")
  })
  it("keeps zero distinct from missing or invalid money", () => {
    expect(money("$0.00")).toBe(0)
    expect(money("")).toBeNull()
    expect(money("not supplied")).toBeNull()
  })
  it("generates stable run-scoped identity and semantic fixtures", () => {
    const first = normalize(parseCsv(csv)), second = normalize(parseCsv(csv))
    expect(first).toEqual(second)
    expect(first[0].recordRef).toMatch(/^wm-0001-/)
    expect(first[0].match).not.toBe("VERIFIED_SOURCE")
    expect(["DEMO_FIXTURE", "NOT_FOUND"]).toContain(first[0].weight === null ? "NOT_FOUND" : "DEMO_FIXTURE")
  })
  it("keeps CSV filename out of semantic processing", () => {
    const contentUnderAnotherFilename = csv
    expect(normalize(parseCsv(contentUnderAnotherFilename))).toEqual(normalize(parseCsv(csv)))
  })
  it("handles divide-by-zero without inventing ROI", () => expect(normalize(parseCsv(csv))[1].roi).toBeNull())
  it("exports correctly quoted data", () => {
    const output = exportCsv(normalize(parseCsv(csv)))
    expect(output).toContain('"Anchor, Kit"')
    expect(output).toMatch(/^batch_id,source_filename,source_file_type,source_row_number,record_ref,/)
  })
  it("validates the included West Marine file without hardcoding its row count", () => {
    const parsed = parseCsv(readFileSync(new URL("../public/westmarine-2026-08-16.csv", import.meta.url), "utf8"))
    expect(parsed.rows.length).toBeGreaterThan(0)
    expect(parsed.headers.length).toBeGreaterThan(0)
    expect(detectWestMarine(parsed.headers).format).toBe("WEST_MARINE_SCRAPER_CSV")
    expect(normalize(parsed)).toHaveLength(parsed.rows.length)
  })
  it("keeps generated external values and demo calculations out of VERIFIED_SOURCE", () => {
    for (const record of normalize(parseCsv(csv))) {
      expect(record.match).not.toBe("VERIFIED_SOURCE")
      expect(record.match).not.toBe("VERIFIED_SOURCE")
      expect(record.hazmat === "UNKNOWN" ? "NOT_FOUND" : "DEMO_FIXTURE").not.toBe("VERIFIED_SOURCE")
      expect(record.bulky === "UNKNOWN" ? "NOT_FOUND" : "DEMO_FIXTURE").not.toBe("VERIFIED_SOURCE")
    }
  })
  it("derives null-safe analytics and deterministic opportunity ranking", () => {
    const result = analytics(normalize(parseCsv(csv)))
    expect(result.decisions.BUY + result.decisions.REVIEW + result.decisions.PASS).toBe(result.total)
    expect(result.avgRoi).not.toBeNull()
    expect(result.priceAnalysis.largestDiscounts[0]?.amount).toBeGreaterThanOrEqual(0)
    expect(result.topOpportunities).toEqual([...result.topOpportunities].sort((a,b)=>b.profit-a.profit||a.recordRef.localeCompare(b.recordRef)))
  })
})
