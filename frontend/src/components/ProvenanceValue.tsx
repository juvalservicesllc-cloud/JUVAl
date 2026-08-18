import type { FieldValueOut } from "../types"
import { StatusBadge } from "./StatusBadge"

// A sensitive value is intentionally never rendered without its verification
// status (ADR-003/ADR-004). Missing and invalid values remain explicit.
export function ProvenanceValue({ value }: { value: FieldValueOut }) {
  if (value.status === null) return <span className="fv fv-empty">—</span>
  const display = value.value === null ? "No value" : String(value.value)
  return <span className="provenance-value"><span>{display}</span><StatusBadge value={value.status} /></span>
}
