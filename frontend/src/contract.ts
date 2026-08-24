// Frontend-side mirrors of backend contract values, plus the one conversion
// that sits on the boundary between how the domain stores a value and how an
// operator reads it. Kept out of the component files so React Fast Refresh
// still treats those as component-only modules.

// Mirrors the backend's SUPPORTED_INPUT_SUFFIXES and the limit enforced by
// POST /api/v1/batches. Client-side checks are a courtesy, never the
// authority -- the server rejects the same files independently.
export const SUPPORTED_EXTENSIONS = [".xlsx", ".csv"] as const
export const MAX_FILES = 10

/**
 * The domain stores ROI and margin as ratios (0.30). Operators think and type
 * in percent (30). This is the single conversion point between the two: the
 * user types 30, the canonical query receives 0.30, and the chips read "30%".
 * The domain's ratio semantics are never changed to match the input.
 *
 * Returns `undefined` for empty or non-numeric input, so a cleared filter is
 * dropped from the query rather than sent as 0 -- which would silently mean
 * "at least 0%" and change the result set.
 */
export function percentInputToRatio(input: string): string | undefined {
  if (input.trim() === "") return undefined
  const percent = Number(input)
  if (!Number.isFinite(percent)) return undefined
  // toFixed(6) keeps 33.333333% precise enough for a threshold without
  // emitting float noise like 0.30000000000000004 into the query string.
  return String(Number((percent / 100).toFixed(6)))
}
