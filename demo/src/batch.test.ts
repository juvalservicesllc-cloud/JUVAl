import { describe, expect, it } from "vitest"
import { MAX_FILES, parseBatch } from "./batch"
import { buildXlsxFile } from "./xlsx/xlsxFixture"

const headers = "position-relative href,img-fluid src,product-brand-name,link,item-price,item-price (2)"
const csvFile = (name: string, rows = 1) => new File([`${headers}\n${Array.from({ length: rows }, (_, i) => `/products/${name}-${i},image.jpg,Brand,${name} item ${i},$10.00,$20.00`).join("\n")}`], name, { type: "text/csv" })
const xlsxHeaders = headers.split(",")
const xlsxRow = ["/products/x", "image.jpg", "Brand", "XLSX item", "$15.00", "$30.00"]

describe("multi-file batch parsing", () => {
  it("parses a single CSV file", async () => {
    const result = await parseBatch([csvFile("a.csv")])
    expect(result.status).toBe("SUCCESS")
    expect(result.files).toHaveLength(1)
    expect(result.files[0].status).toBe("VALID")
    expect(result.records).toHaveLength(1)
  })

  it("parses an XLSX file through the same pipeline as CSV", async () => {
    const file = await buildXlsxFile([{ name: "Sheet1", rows: [xlsxHeaders, xlsxRow] }], "a.xlsx")
    const result = await parseBatch([file])
    expect(result.status).toBe("SUCCESS")
    expect(result.files[0].fileType).toBe("XLSX")
    expect(result.files[0].sheetName).toBe("Sheet1")
    expect(result.files[0].sheetCount).toBe(1)
    expect(result.records[0].sourceFileType).toBe("XLSX")
    expect(result.records[0].sourceRowNumber).toBe(2)
  })

  it("accepts a mixed CSV + XLSX batch and tags each record with its own source file", async () => {
    const xlsx = await buildXlsxFile([{ name: "Sheet1", rows: [xlsxHeaders, xlsxRow] }], "b.xlsx")
    const result = await parseBatch([csvFile("a.csv"), xlsx])
    expect(result.status).toBe("SUCCESS")
    expect(new Set(result.records.map(r => r.sourceFileId)).size).toBe(2)
    expect(result.records.map(r => r.sourceFilename).sort()).toEqual(["a.csv", "b.xlsx"])
    expect(result.records.map(r => r.sourceFileType).sort()).toEqual(["CSV", "XLSX"])
  })

  it(`accepts exactly ${MAX_FILES} files and reports the 11th as rejected`, async () => {
    const files = Array.from({ length: MAX_FILES + 1 }, (_, i) => csvFile(`f${i}.csv`))
    const result = await parseBatch(files)
    expect(result.files).toHaveLength(MAX_FILES)
    expect(result.rejectedFiles).toEqual(["f10.csv"])
  })

  it("keeps valid files processed and invalid files visible on PARTIAL_SUCCESS", async () => {
    const badCsv = new File(["name,price\nx,$1"], "bad.csv", { type: "text/csv" })
    const result = await parseBatch([csvFile("good.csv"), badCsv])
    expect(result.status).toBe("PARTIAL_SUCCESS")
    expect(result.files.find(f => f.filename === "good.csv")?.status).toBe("VALID")
    const bad = result.files.find(f => f.filename === "bad.csv")!
    expect(bad.status).toBe("INVALID")
    expect(bad.errors[0]).toMatch(/unsupported source columns/i)
    expect(result.records).toHaveLength(1)
  })

  it("isolates a malformed XLSX file in a mixed batch", async () => {
    const validXlsx = await buildXlsxFile([{ name: "Data", rows: [xlsxHeaders, xlsxRow] }], "valid.xlsx")
    const result = await parseBatch([csvFile("valid.csv"), new File(["not an xlsx"], "broken.xlsx"), validXlsx])
    expect(result.status).toBe("PARTIAL_SUCCESS")
    expect(result.records).toHaveLength(2)
    expect(result.files.find(file => file.filename === "broken.xlsx")).toMatchObject({ status: "INVALID", errorCode: "PARSE_ERROR" })
  })

  it("keeps a valid workbook with an unsupported supplier schema distinct from a parse error", async () => {
    const wrongSchema = await buildXlsxFile([{ name: "Data", rows: [["name", "price"], ["Item", 10]] }], "wrong.xlsx")
    const result = await parseBatch([wrongSchema])
    expect(result.status).toBe("FAILED")
    expect(result.files[0]).toMatchObject({ status: "INVALID", errorCode: "UNSUPPORTED_SOURCE" })
  })

  it("reports an empty XLSX workbook without fake records", async () => {
    const empty = await buildXlsxFile([{ name: "Empty", rows: [] }], "empty.xlsx")
    const result = await parseBatch([empty])
    expect(result.status).toBe("FAILED")
    expect(result.records).toEqual([])
    expect(result.files[0]).toMatchObject({ status: "INVALID", errorCode: "EMPTY_WORKBOOK" })
  })

  it("preserves XLSX zero separately from a missing value", async () => {
    const zero = await buildXlsxFile([{ name: "Data", rows: [xlsxHeaders, ["/products/zero", "", "Brand", "Zero", 0, null]] }], "zero.xlsx")
    const result = await parseBatch([zero])
    expect(result.records[0]).toMatchObject({ cost: 0, suggested: null, raw: { "item-price": "0", "item-price (2)": "" } })
  })

  it("reports FAILED when no file in the batch is usable", async () => {
    const result = await parseBatch([new File(["name,price\nx,$1"], "bad.csv", { type: "text/csv" })])
    expect(result.status).toBe("FAILED")
    expect(result.records).toHaveLength(0)
  })

  it("assigns distinct sourceFileId to two files with the same filename", async () => {
    const result = await parseBatch([csvFile("dup.csv"), csvFile("dup.csv")])
    expect(new Set(result.files.map(f => f.sourceFileId)).size).toBe(2)
  })

  it("records exact source row numbers, offset for the header row", async () => {
    const result = await parseBatch([csvFile("rows.csv", 3)])
    expect(result.records.map(r => r.sourceRowNumber)).toEqual([2, 3, 4])
  })
})
