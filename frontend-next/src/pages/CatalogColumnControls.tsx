import { CATALOG_COLUMNS, defaultColumns, type ColumnPreference } from "../catalogColumns"

export function CatalogColumnControls({ columns, onChange }: { columns: ColumnPreference[]; onChange: (columns: ColumnPreference[]) => void }) {
  function move(index: number, direction: number) {
    const next = [...columns]
    const target = index + direction
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }
  return <details className="column-controls">
    <summary>Catalog columns</summary>
    <p>Show, hide and reorder columns in this browser. Title stays visible to open records. Filters and exports are unchanged.</p>
    <fieldset>
      <legend>Visible columns and display order</legend>
      <ol>
        {columns.map((column, index) => {
          const label = CATALOG_COLUMNS.find((c) => c.id === column.id)!.label
          return <li key={column.id}>
            <label><input type="checkbox" checked={column.visible} disabled={column.id === "title"}
              onChange={(e) => onChange(columns.map((c) => c.id === column.id ? { ...c, visible: e.target.checked } : c))} />Show {label} column</label>
            <button type="button" aria-label={`Move ${label} up`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button>
            <button type="button" aria-label={`Move ${label} down`} disabled={index === columns.length - 1} onClick={() => move(index, 1)}>↓</button>
          </li>
        })}
      </ol>
    </fieldset>
    <button type="button" onClick={() => onChange(defaultColumns())}>Reset columns</button>
  </details>
}
