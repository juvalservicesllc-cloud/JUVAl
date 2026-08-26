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
