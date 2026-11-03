import type { RecordSort } from "./api/types"

/** Presentation preferences only; never part of CatalogQuery. */
export const CATALOG_COLUMNS = [
  { id: "image", label: "Image", sort: null },
  { id: "source", label: "Source", sort: null },
  { id: "brand", label: "Brand", sort: null },
  { id: "title", label: "Title", sort: "title" },
  { id: "cog", label: "Cost", sort: "cog" },
  // Supplier evidence can mix currencies; it has no canonical sort key.
  { id: "suggested", label: "Suggested (supplier)", sort: null },
  { id: "selling", label: "Selling", sort: "price" },
  { id: "profit", label: "Profit", sort: "profit" },
  { id: "roi", label: "ROI", sort: "roi" },
  { id: "margin", label: "Margin", sort: "margin" },
  { id: "hazmat", label: "Hazmat", sort: "hazmat" },
  { id: "bulky", label: "Bulky", sort: "bulky" },
  { id: "decision", label: "Decision", sort: "decision" },
  // Declared demand is evidence only, never a sortable decision input.
  { id: "demand", label: "Declared demand", sort: null },
  { id: "favorite", label: "Favorite", sort: null },
  // Extend the historical layout without shifting its existing columns.
  // Saved preferences still take precedence over this default order.
  { id: "sku", label: "SKU", sort: "sku" },
  { id: "identity", label: "ASIN / UPC", sort: "asin" },
  { id: "record_ref", label: "Record", sort: "record_ref" },
  { id: "issues", label: "Issues", sort: null },
] as const satisfies readonly { id: string; label: string; sort: RecordSort | null }[]

export type ColumnId = typeof CATALOG_COLUMNS[number]["id"]
export type ColumnPreference = { id: ColumnId; visible: boolean }
export const COLUMN_KEY = "juval.catalog.columns.v1"
export const defaultColumns = (): ColumnPreference[] => CATALOG_COLUMNS.map(({ id }) => ({ id, visible: true }))

export function loadColumns(): ColumnPreference[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(COLUMN_KEY) ?? "null")
    if (!Array.isArray(parsed)) return defaultColumns()
    const columns: ColumnPreference[] = []
    for (const item of parsed) {
      const column = CATALOG_COLUMNS.find((c) => c.id === item?.id)
      if (!column || columns.some((c) => c.id === column.id)) continue
      columns.push({ id: column.id, visible: column.id === "title" || item.visible !== false })
    }
    // New columns stay available after an upgrade, in their default order.
    return [...columns, ...defaultColumns().filter((c) => !columns.some((p) => p.id === c.id))]
  } catch { return defaultColumns() }
}

export function saveColumns(columns: ColumnPreference[]): void {
  try { localStorage.setItem(COLUMN_KEY, JSON.stringify(columns)) } catch { /* browser preference only */ }
}
