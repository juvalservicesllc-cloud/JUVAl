import { describe, expect, it, beforeEach, vi } from "vitest"
import { loadRuns, saveRuns, type Run } from "./storage"
import { normalize, parseCsv } from "./engine"

function memoryLocalStorage() {
  const data = new Map<string, string>()
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v), removeItem: (k: string) => void data.delete(k) }
}

const record = normalize(parseCsv("position-relative href,img-fluid src,product-brand-name,link,item-price,item-price (2)\n/a,,Brand,Title,$10,$20"))[0]

describe("batch run persistence", () => {
  beforeEach(() => vi.stubGlobal("localStorage", memoryLocalStorage()))

  it("round-trips files and records through save/load", () => {
    const run: Run = { schema: 1, runId: "run-1", createdAt: "2026-01-01T00:00:00Z", inputFilename: "a.csv, b.xlsx", records: [{ ...record, sourceFileId: "file-a" }], warnings: [], files: [{ sourceFileId: "file-a", filename: "a.csv", fileType: "CSV", size: 10, rowsDetected: 1, rowsProcessed: 1, status: "VALID", warnings: [], errors: [] }], status: "SUCCESS" }
    saveRuns([run])
    const reloaded = loadRuns().runs
    expect(reloaded).toEqual([run])
  })

  it("migrates a legacy saved run that predates multi-file batches by defaulting files/status", () => {
    localStorage.setItem("juval.demo.runs.v1", JSON.stringify([{ schema: 1, runId: "legacy-1", createdAt: "2026-01-01T00:00:00Z", inputFilename: "old.csv", records: [record], warnings: [] }]))
    const reloaded = loadRuns().runs
    expect(reloaded[0].files).toEqual([])
    expect(reloaded[0].status).toBe("SUCCESS")
  })

  it("never persists raw binary workbook bytes, only normalized string fields", () => {
    const run: Run = { schema: 1, runId: "run-1", createdAt: "2026-01-01T00:00:00Z", inputFilename: "a.xlsx", records: [{ ...record, sourceFileType: "XLSX" }], warnings: [], files: [], status: "SUCCESS" }
    saveRuns([run])
    const raw = localStorage.getItem("juval.demo.runs.v1")!
    expect(raw).not.toMatch(/ArrayBuffer|Uint8Array|base64/i)
    expect(JSON.parse(raw)[0].records[0].raw["item-price"]).toBe("$10")
  })
})
