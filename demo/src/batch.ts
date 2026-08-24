import { normalize, type DemoRecord } from "./demo-engine"
import { parseCsv, type CsvParseResult } from "./csv/parseCsv"
import { detectWestMarine } from "./adapters/WestMarineCsvAdapter"
import { parseXlsx, XlsxParseError, type XlsxParseResult } from "./xlsx/parseXlsx"

export const MAX_FILES = 10

export type SourceFile = {
  sourceFileId: string
  filename: string
  fileType: "CSV" | "XLSX" | "UNSUPPORTED"
  size: number
  sheetName?: string
  sheetCount?: number
  rowsDetected: number
  rowsProcessed: number
  status: "VALID" | "INVALID"
  warnings: string[]
  errors: string[]
  errorCode?: "PARSE_ERROR" | "UNSUPPORTED_SOURCE" | "EMPTY_WORKBOOK" | "UNSUPPORTED_FILE"
}

export type BatchResult = {
  files: SourceFile[]
  rejectedFiles: string[]
  records: DemoRecord[]
  status: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED"
}

const sourceFileIdOf = (index: number, file: File) => `${index}-${file.name}-${file.size}-${file.lastModified}`

function toRecords(parsed: CsvParseResult, sourceFileId: string, filename: string, fileType: "CSV" | "XLSX"): DemoRecord[] {
  if (detectWestMarine(parsed.headers).format !== "WEST_MARINE_SCRAPER_CSV") throw Object.assign(new Error("Unsupported source columns for this demo (expects West Marine supplier export columns)."), { code: "UNSUPPORTED_SOURCE" })
  return normalize(parsed).map((record, row): DemoRecord => ({ ...record, sourceFileId, sourceFilename: filename, sourceFileType: fileType, sourceRowNumber: parsed.rowNumbers?.[row] ?? row + 2 }))
}

export async function parseBatch(files: File[]): Promise<BatchResult> {
  const accepted = files.slice(0, MAX_FILES)
  const rejectedFiles = files.slice(MAX_FILES).map(file => file.name)
  const metadata: SourceFile[] = []
  const records: DemoRecord[] = []

  for (const [index, file] of accepted.entries()) {
    const sourceFileId = sourceFileIdOf(index, file)
    const extension = file.name.toLowerCase().split(".").pop()
    const fileType = extension === "xlsx" ? "XLSX" : extension === "csv" ? "CSV" : "UNSUPPORTED"
    try {
      if (fileType === "UNSUPPORTED") throw Object.assign(new Error("Only CSV and XLSX files are supported."), { code: "UNSUPPORTED_FILE" })
      const parsed = fileType === "XLSX" ? await parseXlsx(file) : parseCsv(await file.text())
      const normalized = toRecords(parsed, sourceFileId, file.name, fileType)
      records.push(...normalized)
      metadata.push({
        sourceFileId, filename: file.name, fileType, size: file.size,
        sheetName: fileType === "XLSX" ? (parsed as XlsxParseResult).sheetName : undefined,
        sheetCount: fileType === "XLSX" ? (parsed as XlsxParseResult).sheetNames.length : undefined,
        rowsDetected: parsed.rows.length, rowsProcessed: normalized.length,
        status: "VALID", warnings: parsed.errors, errors: [],
      })
    } catch (error) {
      const errorCode = error instanceof XlsxParseError ? error.code : error && typeof error === "object" && "code" in error && typeof error.code === "string" ? error.code : "PARSE_ERROR"
      metadata.push({
        sourceFileId, filename: file.name, fileType, size: file.size,
        rowsDetected: 0, rowsProcessed: 0, status: "INVALID", warnings: [],
        errors: [error instanceof Error ? error.message : "Could not parse file"], errorCode: errorCode as SourceFile["errorCode"],
      })
    }
  }

  const valid = metadata.filter(file => file.status === "VALID").length
  const status = valid === 0 ? "FAILED" : valid === metadata.length ? "SUCCESS" : "PARTIAL_SUCCESS"
  return { files: metadata, rejectedFiles, records, status }
}
