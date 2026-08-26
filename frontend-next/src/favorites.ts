/** Run-scoped favourites, stored in this browser only.
 *
 * Golden keyed these `runId:sourceFileId:recordRef`. Production creates one
 * ExecutionRun per file, so the middle segment is redundant here and the key is
 * `executionId:recordRef`. The run-scoped shape is deliberate: JUVAl has no
 * global product identity (ADR-011/ADR-012), so a star marks *that snapshot in
 * that run*, never a product.
 *
 * This is a browser preference and is labelled as such in the UI. It is not
 * persisted server-side: no ownership, authentication-scoped storage or sharing
 * contract exists yet. Nothing here touches a value, a status or a decision,
 * and starring issues no request.
 */
const KEY = "juval.catalog.favorites.v1"

export const favoriteKey = (executionId: string, recordRef: string) => `${executionId}:${recordRef}`

export function loadFavorites(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? "[]")
    return Array.isArray(parsed) && parsed.every((x) => typeof x === "string") ? parsed : []
  } catch { return [] }
}

export function saveFavorites(favorites: string[]): void {
  try { localStorage.setItem(KEY, JSON.stringify(favorites)) } catch { /* preference only */ }
}

export const toggleFavorite = (favorites: string[], key: string): string[] =>
  favorites.includes(key) ? favorites.filter((x) => x !== key) : [...favorites, key]
