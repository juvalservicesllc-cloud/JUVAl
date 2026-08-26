/** Deterministic formatting. `toLocaleString(undefined, …)` asks the *runtime*
 *  for a locale, so the same figure reads differently on different machines —
 *  not acceptable for output that has to be auditable and reproducible. */
const LOCALE = "en-US"

export const money = (amount: number, digits = 2) =>
  amount.toLocaleString(LOCALE, { style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits })

/** The backend stores ROI and margin as ratios; the UX contract shows
 *  percentages, so the ×100 belongs here rather than at every call site. */
export const percent = (ratio: number, digits = 1) =>
  `${(ratio * 100).toLocaleString(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`

export const count = (value: number) => value.toLocaleString(LOCALE)

/** Money/percent field that may carry no value. The status is rendered by the
 *  caller — never dropped. */
export function fieldMoney(value: string | number | null): string {
  if (value === null || value === undefined) return "—"
  const n = Number(value)
  return Number.isFinite(n) ? money(n) : "—"
}

export function fieldPercent(value: string | number | null): string {
  if (value === null || value === undefined) return "—"
  const n = Number(value)
  return Number.isFinite(n) ? percent(n) : "—"
}
