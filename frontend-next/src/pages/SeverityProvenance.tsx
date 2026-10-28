import type { ProvenanceStatus, SeveritySourceType } from "../api/types"

/**
 * Where a HazMat/Bulky severity comes from (ADR-020), as the backend stored it.
 * The pair (status, source type) is only translated into words; nothing is
 * derived here. `null`/absent (a snapshot written before 2026-10-28, or a file
 * without the column) renders nothing -- it is never assumed VERIFIED, INFERRED
 * or NOT_FOUND. None of these is an Amazon verification.
 */
const KNOWN: Record<string, { label: string; short: string }> = {
  "INFERRED|CALCULATED": { label: "JUVAl classification (inferred)", short: "JUVAl" },
  "VERIFIED|SUPPLIER_FILE": { label: "Absence declared in supplier file", short: "file" },
  "NOT_FOUND|NOT_FOUND": { label: "Not found", short: "N/F" },
  "INVALID|SUPPLIER_FILE": { label: "Invalid in supplier file", short: "INV" },
}

export function severityProvenance(status: ProvenanceStatus | null | undefined, sourceType: SeveritySourceType | null | undefined) {
  if (!status) return null
  const known = KNOWN[`${status}|${sourceType ?? ""}`]
  // An unexpected pair is shown exactly as stored, not interpreted.
  const { label, short } = known ?? { label: `${status} · ${sourceType ?? "source not recorded"}`, short: status }
  return { status, label, short, title: `Severity: ${label} — not an Amazon verification` }
}

export function SeverityProvenance({ risk, status, sourceType, compact = false }: {
  risk: "HazMat" | "Bulky"
  status: ProvenanceStatus | null | undefined
  sourceType: SeveritySourceType | null | undefined
  compact?: boolean
}) {
  const shown = severityProvenance(status, sourceType)
  if (!shown) return null
  return <em className={`prov severity-prov prov-${shown.status.toLowerCase().replaceAll("_", "-")}`}
    title={shown.title} aria-label={`${risk} severity provenance: ${shown.label}`}>
    {compact ? shown.short : shown.label}
  </em>
}
