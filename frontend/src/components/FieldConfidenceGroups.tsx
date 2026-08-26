import type { FieldValueOut, RecordOut } from "../types"

/**
 * This record's own fields, grouped by verification status — recovered from the
 * Golden Product Experience (ADR-029, `demo/src/quality.ts` groups every field
 * under VERIFIED_SOURCE / DEMO_FIXTURE / INFERRED / NOT_FOUND / INVALID).
 *
 * The point is the question "what in this record can I trust?", which a flat
 * issue list does not answer: an issue list says what went wrong, not which of
 * the twelve values on screen are actually verified.
 *
 * Every group is built from `FieldValueOut.status` already persisted on the
 * snapshot — nothing is derived, inferred or scored here, and no status is
 * invented for a field the backend did not classify. A field whose `status` is
 * `null` was never recorded on this snapshot and is listed separately rather
 * than being silently counted as missing data.
 *
 * `DEMO_FIXTURE` is included in the ordering deliberately: production records
 * never carry it today, but the group must exist so that if a fixture-backed
 * field is ever surfaced it is grouped as fixture rather than folded into
 * VERIFIED.
 */

const GROUP_ORDER = ["VERIFIED", "INFERRED", "DEMO_FIXTURE", "NOT_FOUND", "INVALID"] as const

const GROUP_LABEL: Record<string, string> = {
  VERIFIED: "Verified",
  INFERRED: "Inferred",
  DEMO_FIXTURE: "Demo fixture",
  NOT_FOUND: "Not found",
  INVALID: "Invalid",
}

const GROUP_MEANING: Record<string, string> = {
  VERIFIED: "Evidence was sufficient from a trusted source.",
  INFERRED: "Derived by rule or heuristic — review before relying on it.",
  DEMO_FIXTURE: "Demonstration data. Never treat as verified evidence.",
  NOT_FOUND: "No evidence was found. The value is absent, never defaulted to zero.",
  INVALID: "A value was present but failed validation. The raw input is kept for diagnosis.",
}

const FIELD_LABEL: [keyof RecordOut, string][] = [
  ["asin", "ASIN"], ["upc", "UPC"], ["title", "Title"], ["brand", "Brand"], ["category", "Category"],
  ["weight", "Weight"], ["height", "Height"], ["width", "Width"], ["length", "Length"],
  ["selling_price", "Selling price"], ["profit", "Profit"], ["roi", "ROI"], ["margin", "Margin"],
  ["break_even_price", "Break-even price"], ["max_cog_target_profit", "Max COG (target profit)"], ["max_cog_target_roi", "Max COG (target ROI)"],
]

function isFieldValue(value: unknown): value is FieldValueOut {
  return typeof value === "object" && value !== null && "status" in value
}

export function FieldConfidenceGroups({ record }: { record: RecordOut }) {
  const groups = new Map<string, string[]>()
  const unrecorded: string[] = []

  for (const [key, label] of FIELD_LABEL) {
    const value = record[key]
    if (!isFieldValue(value)) continue
    if (value.status === null || value.status === undefined) { unrecorded.push(label); continue }
    const bucket = groups.get(value.status) ?? []
    bucket.push(label)
    groups.set(value.status, bucket)
  }

  const ordered = [
    ...GROUP_ORDER.filter((status) => groups.has(status)),
    ...[...groups.keys()].filter((status) => !GROUP_ORDER.includes(status as (typeof GROUP_ORDER)[number])),
  ]

  return (
    <div className="confidence-groups">
      {ordered.map((status) => {
        const fields = groups.get(status) ?? []
        return (
          <section className={`confidence-group confidence-${status.toLowerCase().replaceAll("_", "-")}`} key={status}>
            <header>
              <span className="confidence-group-name">{GROUP_LABEL[status] ?? status}</span>
              <strong>{fields.length}</strong>
            </header>
            <p className="confidence-group-meaning">{GROUP_MEANING[status] ?? "Status reported by the backend."}</p>
            <ul>{fields.map((field) => <li key={field}>{field}</li>)}</ul>
          </section>
        )
      })}
      {unrecorded.length > 0 && (
        <section className="confidence-group confidence-unrecorded">
          <header>
            <span className="confidence-group-name">Not recorded</span>
            <strong>{unrecorded.length}</strong>
          </header>
          <p className="confidence-group-meaning">This snapshot carries no entry for these fields, which is different from a field that was looked for and not found.</p>
          <ul>{unrecorded.map((field) => <li key={field}>{field}</li>)}</ul>
        </section>
      )}
    </div>
  )
}
