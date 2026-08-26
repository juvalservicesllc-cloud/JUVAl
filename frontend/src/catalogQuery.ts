import type { RecordSort, SortDirection } from "./types"

/** Remembered Catalog query, recovered from the Golden Product Experience
 *  (ADR-029, `demo/src/pages/CatalogPage.tsx` stores its `CatalogState` in
 *  `sessionStorage`).
 *
 *  Scope is deliberately identical to Golden's: **this tab, this session**.
 *  A remembered filter changes which records an operator sees, so it should
 *  not silently outlive the sitting and quietly narrow a later review --
 *  `sessionStorage`, not `localStorage`, is what makes that true.
 *
 *  What is stored is the query the user typed, never a record, a value, a
 *  status or a decision. The selected run is *not* stored either: it belongs
 *  to the data, not to the operator's preference, and restoring a stale run id
 *  would silently point the catalog at a different dataset.
 *
 *  The stored shape is validated field by field on read. Anything unknown,
 *  stale or corrupt degrades to the defaults rather than reaching the API --
 *  an out-of-contract `sort` would otherwise become a 422 the operator cannot
 *  explain.
 */
export interface CatalogQuery {
  search: string
  decision: string
  sort: RecordSort
  direction: SortDirection
  limit: number
  minRoi: string
  minProfit: string
  minMargin: string
  confidence: string
  hazmat: string
  bulky: string
  provenanceField: string
  provenanceStatus: string
}

const SORTS: RecordSort[] = ["record_ref", "sku", "asin", "title", "price", "cog", "decision", "profit", "roi", "margin", "hazmat", "bulky"]
const DIRECTIONS: SortDirection[] = ["asc", "desc"]
const DECISIONS = ["ALL", "BUY", "REVIEW", "PASS"]
const CONFIDENCES = ["VERIFIED_ONLY", "INCLUDE_INFERRED"]
const RISK = ["", "PRESENT", "ABSENT", "UNKNOWN"]
const PROVENANCE_FIELDS = ["", "asin", "selling_price", "profit", "roi", "margin"]
const PROVENANCE_STATUSES = ["", "VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"]
const LIMITS = [25, 50, 100]

// v1 is the first remembered-query shape. Bump on any change that would make
// an older stored value mean something different.
const STORAGE_KEY = "juval.catalog.query.v1"

/** Only a short numeric string is a usable threshold; anything else is dropped
 *  rather than sent to the API as a filter the operator never typed. */
function numericInput(value: unknown): string {
  return typeof value === "string" && value.length <= 24 && (value === "" || Number.isFinite(Number(value))) ? value : ""
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value) ? (value as T) : fallback
}

export function loadCatalogQuery(defaults: CatalogQuery): CatalogQuery {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return defaults
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== "object") return defaults
    const stored = parsed as Record<string, unknown>
    return {
      search: typeof stored.search === "string" ? stored.search.slice(0, 200) : defaults.search,
      decision: oneOf(stored.decision, DECISIONS, defaults.decision),
      sort: oneOf(stored.sort, SORTS, defaults.sort),
      direction: oneOf(stored.direction, DIRECTIONS, defaults.direction),
      limit: LIMITS.includes(Number(stored.limit)) ? Number(stored.limit) : defaults.limit,
      minRoi: numericInput(stored.minRoi),
      minProfit: numericInput(stored.minProfit),
      minMargin: numericInput(stored.minMargin),
      confidence: oneOf(stored.confidence, CONFIDENCES, defaults.confidence),
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
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(query)) } catch { /* preference only */ }
}

/** Reset must clear the stored copy too, otherwise the next mount silently
 *  restores the filters the operator just cleared. */
export function clearCatalogQuery(): void {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* preference only */ }
}
