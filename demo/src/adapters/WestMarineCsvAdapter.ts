import type { CsvParseResult } from "../csv/parseCsv"

export type ColumnClass = "USED" | "OPTIONAL" | "IGNORED"
export type ColumnInfo = { source: string; classification: ColumnClass; canonical?: string; rationale: string }
const required: Record<string, string> = {
  "position-relative href": "supplier_url", "img-fluid src": "image_url", "product-brand-name": "brand", link: "supplier_title", "item-price": "supplier_cost", "item-price (2)": "suggested_price",
}
const optional = new Set(["label", "label (2)", "color-mine-shaft", "swatch-circle src", "swatch-circle src (2)", "swatch-circle src (3)"])

export function detectWestMarine(headers: string[]) {
  const recognized = headers.filter(header => header in required)
  const missing = Object.keys(required).filter(header => !headers.includes(header))
  return { format: recognized.length >= 4 ? "WEST_MARINE_SCRAPER_CSV" : "UNRECOGNIZED_CSV", recognized, missing, confidence: Math.round(recognized.length / Object.keys(required).length * 100) }
}
export function classifyColumns(headers: string[]): ColumnInfo[] {
  return headers.map(source => source in required
    ? { source, classification: "USED", canonical: required[source], rationale: "Required West Marine supplier field" }
    : optional.has(source) ? { source, classification: "OPTIONAL", rationale: "Preserved scraper metadata; not used by this demo calculation" }
      : { source, classification: "IGNORED", rationale: "UI/scraper artifact preserved in raw source but not semantically mapped" })
}
export function validateWestMarine(parsed: CsvParseResult) {
  const detection = detectWestMarine(parsed.headers)
  return { ...detection, warnings: [...parsed.errors, ...(detection.format === "UNRECOGNIZED_CSV" ? ["This file does not expose enough expected West Marine columns."] : []), ...(parsed.rows.length ? [] : ["No data rows were found."])] }
}
