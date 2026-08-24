import { describe, expect, it } from "vitest"
import { parseXlsx } from "./parseXlsx"
import { buildXlsxFile } from "./xlsxFixture"

const headers = ["position-relative href", "img-fluid src", "product-brand-name", "link", "item-price", "item-price (2)"]
const row = ["/products/a", "image.jpg", "West Marine", "Anchor Kit", "$20.00", "$49.99"]

describe("XLSX workbook parsing", () => {
  it("parses a single-sheet workbook into CSV-shaped rows", async () => {
    const file = await buildXlsxFile([{ name: "Sheet1", rows: [headers, row] }])
    const result = await parseXlsx(file)
    expect(result.headers).toEqual(headers)
    expect(result.rows).toEqual([Object.fromEntries(headers.map((h, i) => [h, row[i]]))])
    expect(result.sheetName).toBe("Sheet1")
    expect(result.errors).toEqual([])
  })

  it("picks the first non-empty sheet and warns which one was used", async () => {
    const file = await buildXlsxFile([{ name: "Empty", rows: [] }, { name: "Data", rows: [headers, row] }])
    const result = await parseXlsx(file)
    expect(result.sheetName).toBe("Data")
    expect(result.sheetNames).toEqual(["Empty", "Data"])
    expect(result.errors[0]).toContain('using "Data"')
  })

  it("reports no usable worksheet instead of throwing", async () => {
    const file = await buildXlsxFile([{ name: "Empty", rows: [] }])
    await expect(parseXlsx(file)).rejects.toMatchObject({ code: "EMPTY_WORKBOOK" })
  })

  it("skips fully blank data rows", async () => {
    const file = await buildXlsxFile([{ name: "Sheet1", rows: [headers, row, ["", "", "", "", "", ""]] }])
    const result = await parseXlsx(file)
    expect(result.rows).toHaveLength(1)
  })

  it("preserves numeric zero and keeps a missing cell empty", async () => {
    const file = await buildXlsxFile([{ name: "Sheet1", rows: [headers, ["/products/zero", "", "Brand", "Zero", 0, null]] }])
    const result = await parseXlsx(file)
    expect(result.rows[0]["item-price"]).toBe("0")
    expect(result.rows[0]["item-price (2)"]).toBe("")
    expect(result.rowNumbers).toEqual([2])
  })
})
