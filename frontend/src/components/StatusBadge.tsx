import type { Decision, ProvenanceStatus } from "../types"

export function StatusBadge({ value }: { value: ProvenanceStatus | Decision | string }) {
  const label = value.replaceAll("_", " ")
  return <span className={`badge badge-${value.toLowerCase().replaceAll("_", "-")}`} aria-label={`Status: ${label}`}>{label}</span>
}
