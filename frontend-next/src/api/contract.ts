export const SUPPORTED_EXTENSIONS = [".xlsx", ".csv"] as const
export const MAX_FILES = 10

/** The domain stores ROI and margin as ratios (0.30); operators type percent
 *  (30). This is the one conversion point. Empty or non-numeric input returns
 *  `undefined` so a cleared filter is dropped rather than sent as 0, which
 *  would silently mean "at least 0%" and change the result set. */
export function percentInputToRatio(input: string): string | undefined {
  if (input.trim() === "") return undefined
  const percent = Number(input)
  if (!Number.isFinite(percent)) return undefined
  return String(Number((percent / 100).toFixed(6)))
}
