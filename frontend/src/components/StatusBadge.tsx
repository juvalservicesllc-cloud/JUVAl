import type { Decision, ProvenanceStatus } from "../types"

export function StatusBadge({ value }: { value: ProvenanceStatus | Decision | string }) {
  return <span className={`badge badge-${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>
}
