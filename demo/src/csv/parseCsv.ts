import Papa from "papaparse"

// The shared tabular contract for every browser-local file parser.
export type CsvParseResult = { headers: string[]; rows: Record<string, string>[]; errors: string[]; rowNumbers?: number[] }

export function parseCsv(text: string): CsvParseResult {
  if (!text.trim()) return { headers: [], rows: [], errors: ["The CSV file is empty."] }
  const parsed = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: "greedy", transformHeader: header => header.trim() })
  return {
    headers: parsed.meta.fields ?? [],
    rows: parsed.data.filter(row => Object.values(row).some(value => value?.trim())),
    errors: parsed.errors.map(error => `Row ${error.row ?? "?"}: ${error.message}`),
  }
}
