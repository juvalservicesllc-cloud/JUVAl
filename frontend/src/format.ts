/** Deterministic number formatting for the whole app.
 *
 * `toLocaleString(undefined, ...)` asks the *runtime* for a locale, so the
 * same figure rendered from the same data reads differently on different
 * machines: "$5.00" on a US laptop and "5,00 $" on an operator's es_ES
 * server. For a tool whose output is a sourcing decision that has to be
 * auditable and reproducible (CLAUDE.md sec. 2), a value that changes shape
 * with the host's locale is not reproducible -- two operators comparing the
 * same run would be reading differently formatted evidence.
 *
 * So money and ratios are pinned to one locale. This is a presentation
 * decision only: the canonical values stay Decimal on the backend
 * (ADR-006), and nothing here parses, rounds or recomputes them for a
 * calculation -- these functions are display-only.
 *
 * Timestamps deliberately keep `toLocaleString()` at their call sites: an
 * operator reads a time against their own clock, and the underlying instant
 * is identical either way.
 */

// Amazon US marketplace: the currency is fixed by the domain, so the
// formatting locale is too.
const LOCALE = "en-US"

export function money(amount: number, fractionDigits = 2): string {
  return amount.toLocaleString(LOCALE, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

/** Renders a ratio as a percentage -- 0.1 becomes "10.00%".
 *
 * The backend stores ROI and margin as ratios; the UX contract shows
 * percentages, so the x100 belongs here rather than at every call site.
 */
export function percent(ratio: number, fractionDigits = 2): string {
  return `${(ratio * 100).toLocaleString(LOCALE, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })}%`
}

/** Whole-number counts (records, warnings, rows) with grouping separators. */
export function count(value: number): string {
  return value.toLocaleString(LOCALE)
}
