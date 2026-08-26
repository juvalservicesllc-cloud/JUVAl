import type { Decision, ProvenanceStatus } from "../types"

/**
 * `compact` renders the same status as a colour-coded marker instead of a word.
 *
 * The catalog table shows a status beside *every* economic value; spelled out,
 * "VERIFIED" is wider than the figure it qualifies, so the column either clips
 * the badge or the row grows a second line per field. The marker keeps the
 * status attached to its value and fully announced (`aria-label`) and hoverable
 * (`title`) -- what changes is how much width the word takes, never whether the
 * provenance is there (ADR-003/ADR-004). Detail views stay spelled out.
 */
export function StatusBadge({ value, compact = false }: { value: ProvenanceStatus | Decision | string; compact?: boolean }) {
  const label = value.replaceAll("_", " ")
  const className = `badge badge-${value.toLowerCase().replaceAll("_", "-")}${compact ? " badge-compact" : ""}`
  return <span className={className} aria-label={`Status: ${label}`} title={compact ? label : undefined}>{compact ? "" : label}</span>
}
