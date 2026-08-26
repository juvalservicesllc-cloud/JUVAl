import type { Decision, ProvenanceStatus } from "../types"

/** Short forms used by the catalog table. A colour alone is not a status:
 *  provenance is load-bearing in JUVAl (ADR-003/ADR-004), so the compact badge
 *  still carries readable text and the reader never has to hover to tell a
 *  verified figure from an inferred or missing one. */
const SHORT_STATUS: Record<string, string> = {
  VERIFIED: "VER", INFERRED: "INF", NOT_FOUND: "N/F", INVALID: "INV", DEMO_FIXTURE: "DEMO",
}

/**
 * `compact` abbreviates the status instead of spelling it out.
 *
 * The catalog shows a status beside *every* economic value; spelled out,
 * "VERIFIED" is wider than the figure it qualifies, so the column either clips
 * the badge or the row grows a second line per field. Abbreviating keeps the
 * row on one line while leaving the distinction legible on screen -- the full
 * word stays in `aria-label` and `title`, but it is never the *only* place the
 * status exists. A status with no short form falls back to the full word rather
 * than rendering blank. Detail views stay spelled out.
 */
export function StatusBadge({ value, compact = false }: { value: ProvenanceStatus | Decision | string; compact?: boolean }) {
  const label = value.replaceAll("_", " ")
  const short = compact ? SHORT_STATUS[value] ?? label : label
  const className = `badge badge-${value.toLowerCase().replaceAll("_", "-")}${compact ? " badge-compact" : ""}`
  return <span className={className} aria-label={`Status: ${label}`} title={compact ? label : undefined}>{short}</span>
}
