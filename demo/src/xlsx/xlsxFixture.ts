import * as XLSX from "xlsx"

// Test-only helper: builds a real in-memory .xlsx File so parseXlsx can be exercised
// without checking a binary fixture into the repo.
export async function buildXlsxFile(sheets: { name: string; rows: unknown[][] }[], filename = "test.xlsx"): Promise<File> {
  const workbook = XLSX.utils.book_new()
  for (const sheet of sheets) XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(sheet.rows), sheet.name)
  return new File([XLSX.write(workbook, { type: "array", bookType: "xlsx" })], filename, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })
}
