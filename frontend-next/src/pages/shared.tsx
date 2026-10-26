import type { ProvenanceStatus } from "../api/types"

export const fmt = (n: number | null, suffix = "") => (n === null ? "—" : `${suffix}${n.toFixed(2)}`)

export const Badge = ({ children }: { children: string }) => {
  const icon = children === "BUY" ? "●" : children === "REVIEW" ? "▲" : children === "PASS" ? "■" : ""
  return <em className={`badge ${children}`}>{icon && `${icon} `}{children}</em>
}

/** Verification status beside the value it qualifies. Abbreviated so a row
 *  stays one line, but never reduced to colour alone and never hover-only:
 *  the full word is in `title` and in the accessible name. */
const SHORT: Record<string, string> = { VERIFIED: "VER", INFERRED: "INF", NOT_FOUND: "N/F", INVALID: "INV", DEMO_FIXTURE: "DEMO" }

export const ProvenanceBadge = ({ status }: { status: ProvenanceStatus | string }) => (
  <em className={`prov prov-${status.toLowerCase().replaceAll("_", "-")}`} title={status.replaceAll("_", " ")} aria-label={`Status: ${status.replaceAll("_", " ")}`}>
    {SHORT[status] ?? status}
  </em>
)

/** Neutral, text-first label beside an official REVIEW badge: never green,
 *  never a decision icon, never the word BUY (D7-D). */
export const PendingDemandTag = () => (
  <em className="pending-demand" title="REVIEW — only demand evidence is missing; demand has not been verified">demand not verified</em>
)

/** BUY/REVIEW/PASS counts of a run's stored records, as `GET /api/v1/runs`
 *  reports them. With counts present, a missing decision key is a real 0
 *  (records exist, none got it). Without counts nothing is known, so no number
 *  is shown -- a run with no stored records is not a run of zero BUYs. */
export function DecisionCounts({ decisions }: { decisions: Record<string, number> | null | undefined }) {
  if (!decisions) return <span className="decision-counts unavailable">Decision counts not available — no stored records for this run</span>
  const undecided = decisions.UNKNOWN ?? 0
  return <span className="decision-counts" aria-label="Decision counts">
    {(["BUY", "REVIEW", "PASS"] as const).map((d) => <span key={d}><Badge>{d}</Badge> {decisions[d] ?? 0}</span>)}
    {undecided > 0 && <span>{undecided} without decision</span>}
  </span>
}
