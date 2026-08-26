/** Run-scoped catalog favourites, stored in this browser only.
 *
 * Recovered from the Golden Product Experience (ADR-029, `demo/src/favorites.ts`),
 * with the demo's identity model kept deliberately: a favourite is keyed by
 * `(execution_id, record_ref)`, never by a product. JUVAl has no global product
 * identity and ADR-011/ADR-012 keep it that way, so starring a record marks
 * *that snapshot in that run* -- two runs of the same supplier file produce two
 * independent favourites, which is the honest reading of a run-scoped snapshot.
 *
 * This is a browser preference, exactly like the column layout and the theme,
 * and it is labelled as such in the UI. It is **not** persisted server-side:
 * there is no ownership, authentication-scoped storage or sharing contract yet
 * (see CATALOG_GOLDEN_UX_PARITY_V2.md, Favorites). Nothing here touches a
 * value, a status, or a decision.
 */

const STORAGE_KEY = "juval.catalog.favorites.v1"

export function favoriteKey(executionId: string, recordRef: string): string {
  return `${executionId}:${recordRef}`
}

export function loadFavorites(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]")
    return Array.isArray(parsed) && parsed.every((entry) => typeof entry === "string") ? parsed : []
  } catch {
    // Corrupt or unavailable storage must not take the catalog down with it.
    return []
  }
}

export function saveFavorites(favorites: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites))
  } catch { /* local preference only, safe to skip if storage is unavailable */ }
}

export function toggleFavorite(favorites: string[], key: string): string[] {
  return favorites.includes(key) ? favorites.filter((entry) => entry !== key) : [...favorites, key]
}
