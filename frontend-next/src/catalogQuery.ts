import type { CatalogQuery, RecordSort, SortDirection } from "./api/types"

/**
 * Remembered Catalog query preferences.
 *
 * Scope is `sessionStorage` on purpose. A remembered filter changes *which
 * records an operator sees*, so it should survive moving between screens in
 * this tab but must not silently narrow an unrelated sourcing session tomorrow.
 *
 * Only what the operator chose is stored. Three things are deliberately not:
 *
 * - **the selected run** — that is which dataset is on screen, not a
 *   preference. Restoring a stale execution id would silently point Catalog at
 *   a different run than the one the operator navigated to from Run Detail.
 * - **the page offset** — a stored page number against a run whose contents may
 *   have changed opens on a page that no longer means the same thing.
 * - **anything from the server** — no records, no totals, no error or loading
 *   state. Server truth is never cached here.
 *
 * Everything is validated field by field on read. A stale `sort` from an older
 * build would otherwise reach FastAPI as an out-of-contract value and come back
 * a 422 the operator cannot explain, so an unknown value degrades to its
 * default instead.
 */

/** The persisted subset: `CatalogQuery` minus `offset`. */
export type StoredCatalogQuery = Omit<CatalogQuery, "offset">

const SORTS: RecordSort[] = ["record_ref", "sku", "asin", "title", "price", "cog", "decision", "profit", "roi", "margin", "hazmat", "bulky"]
const DIRECTIONS: SortDirection[] = ["asc", "desc"]
const DECISIONS = ["ALL", "BUY", "REVIEW", "PASS"]
const CONFIDENCES = ["VERIFIED_ONLY", "INCLUDE_INFERRED"]
const RISK = ["", "PRESENT", "ABSENT", "UNKNOWN"]
const PROVENANCE_FIELDS = ["", "asin", "selling_price", "profit", "roi", "margin"]
const PROVENANCE_STATUSES = ["", "VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"]
const LIMITS = [20, 25, 50, 100]

// v1 is the first remembered shape in frontend-next. Bump on any change that
// would make an older stored value mean something different.
const STORAGE_KEY = "juval.next.catalog.query.v1"

function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value) ? (value as T) : fallback
}

/** Only a short numeric string is a usable threshold; anything else is dropped
 *  rather than sent to the API as a filter the operator never typed. */
function numericInput(value: unknown): string {
  return typeof value === "string" && value.length <= 24 && (value === "" || Number.isFinite(Number(value))) ? value : ""
}

export function loadCatalogQuery(defaults: CatalogQuery): CatalogQuery {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") return defaults
    const stored = parsed as Record<string, unknown>
    return {
      // Never restored: the page an operator was on is not a preference.
      offset: 0,
      limit: LIMITS.includes(Number(stored.limit)) ? Number(stored.limit) : defaults.limit,
      search: typeof stored.search === "string" ? stored.search.slice(0, 200) : defaults.search,
      decision: oneOf(stored.decision, DECISIONS, defaults.decision),
      sort: oneOf(stored.sort, SORTS, defaults.sort),
      direction: oneOf(stored.direction, DIRECTIONS, defaults.direction),
      minRoi: numericInput(stored.minRoi),
      minProfit: numericInput(stored.minProfit),
      minMargin: numericInput(stored.minMargin),
      confidence: oneOf(stored.confidence, CONFIDENCES, defaults.confidence) as CatalogQuery["confidence"],
      hazmat: oneOf(stored.hazmat, RISK, defaults.hazmat),
      bulky: oneOf(stored.bulky, RISK, defaults.bulky),
      provenanceField: oneOf(stored.provenanceField, PROVENANCE_FIELDS, defaults.provenanceField),
      provenanceStatus: oneOf(stored.provenanceStatus, PROVENANCE_STATUSES, defaults.provenanceStatus),
    }
  } catch {
    return defaults
  }
}

export function saveCatalogQuery(query: CatalogQuery): void {
  try {
    const { offset: _offset, ...preferences } = query
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(preferences satisfies StoredCatalogQuery))
  } catch { /* preference only */ }
}

/** Reset must clear the stored copy too, otherwise the next mount silently
 *  restores the filters the operator just cleared. */
export function clearCatalogQuery(): void {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* preference only */ }
}
