import * as XLSX from "xlsx"
import type { CsvParseResult } from "../csv/parseCsv"

export type XlsxParseResult = CsvParseResult & { sheetName: string; sheetNames: string[] }
export class XlsxParseError extends Error {
  constructor(readonly code: "PARSE_ERROR" | "EMPTY_WORKBOOK", message: string) { super(message) }
}

const cell = (value: unknown): string => (value === null || value === undefined ? "" : String(value))

// ponytail: first non-empty worksheet wins; add an explicit picker only when a supplier needs it.
export async function parseXlsx(file: File): Promise<XlsxParseResult> {
  const bytes = await file.arrayBuffer()
  if (new Uint8Array(bytes).slice(0, 2).join(",") !== "80,75") throw new XlsxParseError("PARSE_ERROR", "The XLSX workbook could not be read. It may be corrupted, encrypted, or unsupported.")
  let workbook: XLSX.WorkBook
  try {
    workbook = XLSX.read(bytes, { type: "array", raw: true })
  } catch {
    throw new XlsxParseError("PARSE_ERROR", "The XLSX workbook could not be read. It may be corrupted, encrypted, or unsupported.")
  }
  const sheetNames = workbook.SheetNames
  if (!sheetNames.length) throw new XlsxParseError("EMPTY_WORKBOOK", "The XLSX workbook has no worksheets.")
  for (const sheetName of sheetNames) {
    const table = XLSX.utils.sheet_to_json<unknown[]>(workbook.Sheets[sheetName], { header: 1, raw: true, defval: null, blankrows: true })
    if (!table.some(row => row.some(value => cell(value).trim()))) continue
    const [headerRow = [], ...dataRows] = table
    const headers = headerRow.map(cell).map(header => header.trim())
    const rows = dataRows
      .map((row, index) => ({ row, rowNumber: index + 2 }))
      .filter(({ row }) => row.some(value => cell(value).trim()))
    if (!headers.some(Boolean) || !rows.length) throw new XlsxParseError("EMPTY_WORKBOOK", `Worksheet "${sheetName}" has no header row and data rows.`)
    return {
      headers,
      rows: rows.map(({ row }) => Object.fromEntries(headers.map((header, index) => [header, cell(row[index])]))),
      rowNumbers: rows.map(({ rowNumber }) => rowNumber),
      errors: sheetNames.length > 1 ? [`Multiple worksheets found; using "${sheetName}". Other sheets were not merged.`] : [],
      sheetName,
      sheetNames,
    }
  }
  throw new XlsxParseError("EMPTY_WORKBOOK", "The XLSX workbook has no non-empty worksheets.")
}
