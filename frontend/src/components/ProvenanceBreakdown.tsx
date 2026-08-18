import type { RunAnalyticsOut } from "../types"

// Data-confidence view: per-field VERIFIED/INFERRED/NOT_FOUND/INVALID counts
// (ADR-003/ADR-004). Deliberately not a single "quality score" -- collapsing
// four distinct verification states into one number would hide exactly the
// distinction provenance exists to preserve. Rendered as one horizontal
// stacked bar per field, with a numeric legend so no state is communicated
// by color alone.

const STATUS_ORDER = ["VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"] as const
const STATUS_LABEL: Record<string, string> = {
  VERIFIED: "Verified",
  INFERRED: "Inferred",
  NOT_FOUND: "Not found",
  INVALID: "Invalid",
}
const STATUS_COLOR: Record<string, string> = {
  VERIFIED: "var(--success)",
  INFERRED: "var(--warning)",
  NOT_FOUND: "var(--chart-grid)",
  INVALID: "var(--danger)",
}
const FIELD_LABEL: Record<string, string> = {
  asin: "ASIN",
  weight: "Weight",
  selling_price: "Selling price",
  profit: "Profit",
  roi: "ROI",
  margin: "Margin",
}

function orderedStatuses(counts: Record<string, number>): string[] {
  const known = STATUS_ORDER.filter((status) => (counts[status] ?? 0) > 0)
  const unknown = Object.keys(counts).filter((status) => !STATUS_ORDER.includes(status as (typeof STATUS_ORDER)[number]) && counts[status] > 0)
  return [...known, ...unknown]
}

export function ProvenanceBreakdown({ provenance }: { provenance: RunAnalyticsOut["provenance"] }) {
  const fields = Object.keys(provenance) as (keyof RunAnalyticsOut["provenance"])[]

  return (
    <div className="provenance-breakdown">
      {fields.map((field) => {
        const counts = provenance[field] ?? {}
        const total = Object.values(counts).reduce((sum, n) => sum + n, 0)
        const statuses = orderedStatuses(counts)
        return (
          <div className="provenance-row" key={field}>
            <span className="provenance-row-label">{FIELD_LABEL[field] ?? field}</span>
            {total === 0 ? (
              <span className="provenance-row-empty">No data</span>
            ) : (
              <>
                <div
                  className="provenance-bar"
                  role="img"
                  aria-label={`${FIELD_LABEL[field] ?? field}: ${statuses.map((s) => `${STATUS_LABEL[s] ?? s} ${counts[s]}`).join(", ")}, out of ${total} records`}
                >
                  {statuses.map((status) => (
                    <span
                      key={status}
                      className="provenance-segment"
                      style={{ width: `${(counts[status] / total) * 100}%`, background: STATUS_COLOR[status] ?? "var(--chart-grid)" }}
                    />
                  ))}
                </div>
                <ul className="provenance-legend">
                  {statuses.map((status) => (
                    <li key={status}>
                      <i style={{ background: STATUS_COLOR[status] ?? "var(--chart-grid)" }} />
                      {STATUS_LABEL[status] ?? status} <strong>{counts[status]}</strong>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}
