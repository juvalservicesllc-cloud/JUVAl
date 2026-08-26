import { useEffect, useState } from "react"
import { ArrowUpRight, CaretDown, CaretUp, CaretUpDown, MagnifyingGlass, Star } from "@phosphor-icons/react"
import { Link } from "react-router-dom"
import { ApiError, apiErrorMessage, apiUrl } from "../api/client"
import { getRunRecords } from "../api/records"
import { getRuns } from "../api/runs"
import { percentInputToRatio } from "../contract"
import { favoriteKey, loadFavorites, saveFavorites, toggleFavorite } from "../favorites"
import { ProductThumbnail } from "../components/ProductThumbnail"
import { StatusBadge } from "../components/StatusBadge"
import type { Decision, RecordOut, RecordPaginationOut, RecordSort, RunSummaryOut, SortDirection } from "../types"
import { count, money, percent } from "../format"

type RunsState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }
type RecordsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; records: RecordOut[]; pagination: RecordPaginationOut }

const LIMIT_OPTIONS = [25, 50, 100]
// Golden opens the catalog on the most profitable rows rather than on record
// order, and that is the sourcing question the page exists to answer. `profit`
// is an allow-listed server-side sort, and SQLite orders NULLs last under DESC,
// so records whose profit is NOT_FOUND/INVALID sink to the bottom instead of
// heading the page (verified against the live API, not assumed). This changes
// presentation order only -- no value, decision or stored record is touched.
const DEFAULT_SORT: RecordSort = "profit"
const DEFAULT_SORT_DIRECTION: SortDirection = "desc"
const SORT_LABEL: Record<RecordSort, string> = { record_ref: "Record", sku: "Product / SKU", asin: "ASIN", title: "Product", price: "Price", cog: "COG", decision: "Decision", profit: "Profit", roi: "ROI", margin: "Margin", hazmat: "HazMat", bulky: "Bulky" }
// record_ref/sku/decision are naturally read ascending; profit/roi/margin are
// interesting largest-first -- matches the prior client-side sort behavior.
const DEFAULT_DIRECTION: Record<RecordSort, SortDirection> = { record_ref: "asc", sku: "asc", asin: "asc", title: "asc", price: "desc", cog: "asc", decision: "asc", profit: "desc", roi: "desc", margin: "desc", hazmat: "asc", bulky: "asc" }
type ColumnKey = "image" | "record_ref" | "product" | "identity" | "price" | "cog" | "profit" | "roi" | "margin" | "hazmat" | "bulky" | "decision" | "issues" | "favorite" | "action"
// Ordered by what a sourcing decision is actually read from, widest-viewport
// last: identity, then the decision itself, then the economics that justify it,
// then risk, then quality/marks, and only then the audit/lookup fields. At
// 1366px everything through Bulky is visible without horizontal scrolling;
// ASIN, record ref and Inspect are the columns that scroll. Every column
// remains toggleable and re-orderable.
const DEFAULT_COLUMNS: ColumnKey[] = ["image", "product", "decision", "roi", "profit", "margin", "price", "cog", "hazmat", "bulky", "issues", "favorite", "identity", "record_ref", "action"]
const COLUMN_LABEL: Record<ColumnKey, string> = { image: "Image", record_ref: "Record", product: "Product / SKU", identity: "ASIN / UPC", price: "Price", cog: "COG", profit: "Profit", roi: "ROI", margin: "Margin", hazmat: "HazMat", bulky: "Bulky", decision: "Decision", issues: "Issues", favorite: "Favorite (local)", action: "Inspect" }
// The one place a column is mapped to its server sort key. Defined once so
// the header button and the `aria-sort` announced on the same cell can
// never disagree. `null` means the column is not sortable server-side.
const COLUMN_SORT_KEY: Record<ColumnKey, RecordSort | null> = { image: null, record_ref: "record_ref", product: "sku", identity: "asin", price: "price", cog: "cog", profit: "profit", roi: "roi", margin: "margin", hazmat: "hazmat", bulky: "bulky", decision: "decision", issues: null, favorite: null, action: null }
// Bumped whenever a column is added: an older stored preference is a valid
// subset of the new keys, so it would silently survive the upgrade and hide the
// new column from exactly the returning users the change is for. v2 added the
// media column, v3 the favourite column, v4 reordered the default hierarchy.
const COLUMN_STORAGE_KEY = "juval.catalog.columns.v4"
// `.catalog-table` is `table-layout: fixed`, so a column is exactly as wide as
// its header cell says. These are the design system's own `.col-*` widths and
// they sum to the table's 1430px, matching the group bar above it.
const COLUMN_WIDTH_CLASS: Record<ColumnKey, string> = {
  image: "col-media", record_ref: "col-record", product: "col-identity", identity: "col-evidence",
  price: "col-money", cog: "col-money", profit: "col-money", roi: "col-number", margin: "col-number",
  hazmat: "col-risk", bulky: "col-risk", decision: "col-decision", issues: "col-quality", favorite: "col-favorite", action: "col-action",
}

function text(value: unknown): string {
  return value === null || value === undefined ? "" : String(value)
}

function formatMoney(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (value === null) return "—"
  const amount = Number(value)
  return Number.isFinite(amount) ? money(amount) : "—"
}

function formatPercent(value: unknown): string {
  const amount = Number(value)
  return Number.isFinite(amount) ? percent(amount) : "—"
}

/** One catalog cell: the value beside its verification status, never without it.
 *
 * When there is no value the badge already reads NOT FOUND / INVALID, so the
 * extra "No value" caption the detail view spells out is dropped here -- at 50
 * rows it doubled the height of every row to repeat what the badge said. The
 * status itself is never dropped (ADR-003/ADR-004).
 */
function formattedField(value: RecordOut["profit"], formatter: (value: unknown) => string) {
  if (value.status === null) return <span className="fv fv-empty">—</span>
  return <span className="provenance-value"><span>{value.value === null ? "—" : formatter(value.value)}</span><StatusBadge value={value.status} compact /></span>
}

export function ProductsPage() {
  const [runsState, setRunsState] = useState<RunsState>({ kind: "loading" })
  const [selectedRunId, setSelectedRunId] = useState("")
  const [recordsState, setRecordsState] = useState<RecordsState>({ kind: "loading" })
  const [runsRetry, setRunsRetry] = useState(0)
  const [recordsRetry, setRecordsRetry] = useState(0)

  const [searchInput, setSearchInput] = useState("")
  const [search, setSearch] = useState("")
  const [decision, setDecision] = useState<"ALL" | Decision>("ALL")
  const [sort, setSort] = useState<RecordSort>(DEFAULT_SORT)
  const [direction, setDirection] = useState<SortDirection>(DEFAULT_SORT_DIRECTION)
  const [limit, setLimit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [minRoi, setMinRoi] = useState("")
  const [minProfit, setMinProfit] = useState("")
  const [minMargin, setMinMargin] = useState("")
  const [confidence, setConfidence] = useState<"VERIFIED_ONLY" | "INCLUDE_INFERRED">("VERIFIED_ONLY")
  const [hazmat, setHazmat] = useState("")
  const [bulky, setBulky] = useState("")
  const [provenanceField, setProvenanceField] = useState("")
  const [provenanceStatus, setProvenanceStatus] = useState("")
  const [favorites, setFavorites] = useState<string[]>(loadFavorites)
  const [columns, setColumns] = useState<ColumnKey[]>(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY) ?? "null")
      return Array.isArray(parsed) && parsed.every((value) => DEFAULT_COLUMNS.includes(value)) ? [...new Set(parsed)] as ColumnKey[] : DEFAULT_COLUMNS
    } catch { return DEFAULT_COLUMNS }
  })

  // Server-side search only, lightly debounced so normal typing doesn't
  // issue one request per keystroke. `search` (not `searchInput`) is what
  // reaches the API and what resets the page.
  //
  // The equality guard is load-bearing, not a micro-optimisation: without it
  // the effect also runs on mount, where the cleanup never fires (its only
  // dependency, `searchInput`, does not change), so a timer scheduled at mount
  // always lands 300 ms later and calls `setOffset(0)`. Anyone who opened
  // Catalog and paged within that window was silently returned to page 1.
  // Settling is only meaningful when the typed value and the applied value
  // actually differ, so that is exactly when the timer is armed.
  useEffect(() => {
    if (searchInput === search) return
    const id = setTimeout(() => {
      setSearch(searchInput)
      setOffset(0)
    }, 300)
    return () => clearTimeout(id)
  }, [searchInput, search])

  useEffect(() => {
    const controller = new AbortController()
    setRunsState({ kind: "loading" })
    getRuns({ limit: 100, signal: controller.signal })
      .then((response) => {
        if (response.items.length === 0) {
          setRunsState({ kind: "empty" })
          return
        }
        setRunsState({ kind: "ready", runs: response.items })
        setSelectedRunId((current) => (current && response.items.some((run) => run.execution_id === current) ? current : response.items[0].execution_id))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setRunsState({ kind: "error", message: error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error) })
      })
    return () => controller.abort()
  }, [runsRetry])

  // The one request this page ever issues per state change: every filter,
  // search, sort and page is a server-side query parameter (API_CONTRACT.md).
  // AbortController cancels a still-in-flight request when any dependency
  // changes again, so a slow earlier response can never overwrite a newer one.
  useEffect(() => {
    if (!selectedRunId) return
    const controller = new AbortController()
    setRecordsState({ kind: "loading" })
    getRunRecords(
      selectedRunId,
      { limit, offset, search: search || undefined, decision: decision === "ALL" ? undefined : decision, sort, direction, min_roi: percentInputToRatio(minRoi), min_profit: minProfit || undefined, min_margin: percentInputToRatio(minMargin), confidence, hazmat: hazmat || undefined, bulky: bulky || undefined, provenance_field: provenanceField ? provenanceField as "asin" | "selling_price" | "profit" | "roi" | "margin" : undefined, provenance_status: provenanceStatus ? provenanceStatus as "VERIFIED" | "INFERRED" | "NOT_FOUND" | "INVALID" : undefined },
      controller.signal,
    )
      .then((response) => setRecordsState({ kind: "ready", records: response.records, pagination: response.pagination }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setRecordsState({ kind: "error", message: error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error) })
      })
    return () => controller.abort()
  }, [selectedRunId, search, decision, sort, direction, limit, offset, minRoi, minProfit, minMargin, confidence, hazmat, bulky, provenanceField, provenanceStatus, recordsRetry])

  function changeSort(key: RecordSort) {
    if (sort === key) {
      setDirection((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSort(key)
      setDirection(DEFAULT_DIRECTION[key])
    }
    setOffset(0)
  }

  function sortButton(key: RecordSort) {
    const active = sort === key
    const nextDirection = active && direction === "asc" ? "descending" : "ascending"
    return (
      <button
        type="button"
        onClick={() => changeSort(key)}
        aria-pressed={active}
        aria-label={`${SORT_LABEL[key]}${active ? `, sorted ${direction === "asc" ? "ascending" : "descending"}. Activate for ${nextDirection}.` : ". Activate to sort."}`}
      >
        {SORT_LABEL[key]}
        {active
          ? (direction === "asc" ? <CaretUp size={11} weight="bold" aria-hidden="true" /> : <CaretDown size={11} weight="bold" aria-hidden="true" />)
          : <CaretUpDown size={11} weight="bold" aria-hidden="true" className="sort-idle" />}
      </button>
    )
  }

  const pagination = recordsState.kind === "ready" ? recordsState.pagination : null
  const rangeStart = pagination && pagination.total > 0 ? pagination.offset + 1 : 0
  const rangeEnd = pagination ? Math.min(pagination.offset + limit, pagination.total) : 0
  const selectedRun = runsState.kind === "ready" ? runsState.runs.find((run) => run.execution_id === selectedRunId) : null
  const hasActiveQuery = Boolean(searchInput || decision !== "ALL" || sort !== DEFAULT_SORT || direction !== DEFAULT_SORT_DIRECTION || offset > 0 || limit !== 50 || minRoi || minProfit || minMargin || confidence !== "VERIFIED_ONLY" || hazmat || bulky || provenanceField || provenanceStatus)

  function resetQuery() {
    setSearchInput("")
    setSearch("")
    setDecision("ALL")
    setSort(DEFAULT_SORT)
    setDirection(DEFAULT_SORT_DIRECTION)
    setLimit(50)
    setOffset(0)
    setMinRoi(""); setMinProfit(""); setMinMargin(""); setConfidence("VERIFIED_ONLY"); setHazmat(""); setBulky(""); setProvenanceField(""); setProvenanceStatus("")
  }

  // Starring marks a run-scoped snapshot in this browser only -- it writes no
  // value, status or decision, and reaches no server (see src/favorites.ts).
  function starRecord(recordRef: string) {
    setFavorites((current) => { const next = toggleFavorite(current, favoriteKey(selectedRunId, recordRef)); saveFavorites(next); return next })
  }

  function updateColumns(next: ColumnKey[]) { setColumns(next); localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(next)) }
  function toggleColumn(key: ColumnKey) { if (key === "record_ref" || key === "product" || key === "decision") return; updateColumns(columns.includes(key) ? columns.filter((column) => column !== key) : [...columns, key]) }
  function moveColumn(key: ColumnKey, delta: number) { const index = columns.indexOf(key); const nextIndex = index + delta; if (index < 0 || nextIndex < 0 || nextIndex >= columns.length) return; const next = [...columns]; [next[index], next[nextIndex]] = [next[nextIndex], next[index]]; updateColumns(next) }
  function resetColumns() { updateColumns(DEFAULT_COLUMNS) }
  function exportFiltered() {
    const params = new URLSearchParams({ sort, direction, confidence })
    if (search) params.set("search", search); if (decision !== "ALL") params.set("decision", decision)
    // Export must issue the identical canonical query the table is showing,
    // percentage conversion included -- otherwise the file would not match the view.
    const roiRatio = percentInputToRatio(minRoi), marginRatio = percentInputToRatio(minMargin)
    if (roiRatio) params.set("min_roi", roiRatio); if (minProfit) params.set("min_profit", minProfit); if (marginRatio) params.set("min_margin", marginRatio)
    if (hazmat) params.set("hazmat", hazmat); if (bulky) params.set("bulky", bulky); if (provenanceField) params.set("provenance_field", provenanceField); if (provenanceStatus) params.set("provenance_status", provenanceStatus)
    window.open(apiUrl(`/api/v1/runs/${encodeURIComponent(selectedRunId)}/records/export?${params}`), "_blank", "noopener,noreferrer")
  }

  function headerFor(column: ColumnKey) {
    const key = COLUMN_SORT_KEY[column]
    if (!key) return <span>{COLUMN_LABEL[column]}</span>
    return <>{sortButton(key)}</>
  }

  function cellFor(column: ColumnKey, record: RecordOut) {
    if (column === "image") return <ProductThumbnail label={text(record.title?.value) || record.record_ref} />
    if (column === "record_ref") return <Link to={`/runs/${encodeURIComponent(selectedRunId)}/records/${encodeURIComponent(record.record_ref)}`} state={{ record }} aria-label={`Inspect record ${record.record_ref}`} title="Inspect run-scoped record">{record.record_ref}</Link>
    if (column === "product") return <div className="product-identity"><div><strong>{text(record.title?.value) || "—"}</strong>{record.brand?.value ? <div className="text-muted">{text(record.brand.value)}</div> : null}<small className="identity-meta">SKU {record.supplier_sku ?? "—"}</small></div></div>
    if (column === "identity") return <div className="identity-evidence"><span><small>ASIN</small>{formattedField(record.asin, text)}</span><span><small>UPC</small>{formattedField(record.upc, text)}</span></div>
    if (column === "price") return formattedField(record.selling_price, formatMoney)
    if (column === "cog") return formatMoney(record.cog)
    if (column === "profit") return formattedField(record.profit, formatMoney)
    if (column === "roi") return formattedField(record.roi, formatPercent)
    if (column === "margin") return formattedField(record.margin, formatPercent)
    if (column === "hazmat") return <StatusBadge value={record.hazmat_status ?? "UNKNOWN"} />
    if (column === "bulky") return <StatusBadge value={record.bulky_status ?? "UNKNOWN"} />
    if (column === "decision") return record.decision ? <StatusBadge value={record.decision} /> : "—"
    if (column === "issues") return record.issue_count > 0 ? <details className="issue-disclosure"><summary>{record.issue_count} issue{record.issue_count === 1 ? "" : "s"}</summary><ul className="issues">{record.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></details> : "—"
    if (column === "favorite") {
      const starred = favorites.includes(favoriteKey(selectedRunId, record.record_ref))
      return <button type="button" className={`favorite-button${starred ? " starred" : ""}`} aria-pressed={starred} aria-label={`${starred ? "Remove" : "Add"} ${text(record.title?.value) || record.record_ref} ${starred ? "from" : "to"} favorites`} title={starred ? "Starred in this browser" : "Star in this browser"} onClick={() => starRecord(record.record_ref)}><Star size={14} weight={starred ? "fill" : "regular"} aria-hidden="true" /></button>
    }
    return <Link className="row-action" to={`/runs/${encodeURIComponent(selectedRunId)}/records/${encodeURIComponent(record.record_ref)}`} state={{ record }} aria-label={`Open detail for ${record.record_ref}`}>Open <ArrowUpRight size={13} weight="bold" aria-hidden="true" /></Link>
  }

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">RUN-SCOPED CATALOG</p>
          <h2>Catalog</h2>
          <p>Inspect, filter, and review immutable records from one processing run at a time.</p>
        </div>
      </div>

      {runsState.kind === "loading" && <div className="status" aria-live="polite">Loading catalog…</div>}
      {runsState.kind === "error" && (
        <div className="status">
          <p role="alert" className="error">{runsState.message}</p>
          <button className="secondary-button" type="button" onClick={() => setRunsRetry((v) => v + 1)}>Retry</button>
        </div>
      )}
      {runsState.kind === "empty" && <div className="status">No persisted runs yet. Process a catalog with persistence enabled to review its records.</div>}

      {runsState.kind === "ready" && (
        <>
          <section className="panel catalog-context" aria-label="Selected run context">
            <div>
              <p className="eyebrow">RUN CONTEXT</p>
              <h2>{selectedRun?.input_filename ?? "Selected run"}</h2>
              <p className="text-muted">Run-scoped snapshots only. No global product identity is created.</p>
            </div>
            <dl className="catalog-context-meta">
              <dt>Status</dt><dd><StatusBadge value={selectedRun?.status ?? "UNKNOWN"} /></dd>
              <dt>Records</dt><dd>{selectedRun ? count(selectedRun.records_total) : "—"}</dd>
              <dt>Execution</dt><dd className="mono">{selectedRunId}</dd>
            </dl>
          </section>
          <section className="panel catalog-controls">
            <div className="catalog-controls-heading">
              <p className="eyebrow">SEARCH &amp; FILTER</p>
              <p className="text-muted">Every change queries the selected run on the server.</p>
            </div>
            <label className="catalog-run-filter">
              Run
              <select aria-label="Catalog run" value={selectedRunId} onChange={(event) => { setSelectedRunId(event.target.value); setOffset(0) }}>
                {runsState.runs.map((run) => (
                  <option key={run.execution_id} value={run.execution_id}>
                    {run.input_filename} — {new Date(run.started_at).toLocaleString()}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Search
              <span className="search-input">
                <MagnifyingGlass size={14} weight="regular" aria-hidden="true" />
                <input
                  aria-label="Search catalog"
                  value={searchInput}
                  maxLength={200}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="SKU, title, brand, ASIN"
                />
              </span>
            </label>
            <label>
              Decision
              <select aria-label="Filter by decision" value={decision} onChange={(event) => { setDecision(event.target.value as "ALL" | Decision); setOffset(0) }}>
                <option value="ALL">All decisions</option>
                <option value="BUY">BUY</option>
                <option value="REVIEW">REVIEW</option>
                <option value="PASS">PASS</option>
              </select>
            </label>
            <label>Min ROI %
              <input aria-label="Minimum ROI percentage" type="number" step="1" value={minRoi} onChange={(event) => { setMinRoi(event.target.value); setOffset(0) }} placeholder="e.g. 30" />
            </label>
            <label>Min profit
              <input aria-label="Minimum profit" type="number" step="0.01" value={minProfit} onChange={(event) => { setMinProfit(event.target.value); setOffset(0) }} placeholder="e.g. 5.00" />
            </label>
            <label>Min margin %
              <input aria-label="Minimum margin percentage" type="number" step="1" value={minMargin} onChange={(event) => { setMinMargin(event.target.value); setOffset(0) }} placeholder="e.g. 20" />
            </label>
            <label>Economic confidence
              <select aria-label="Economic confidence" value={confidence} onChange={(event) => { setConfidence(event.target.value as typeof confidence); setOffset(0) }}>
                <option value="VERIFIED_ONLY">Verified only</option><option value="INCLUDE_INFERRED">Include inferred</option>
              </select>
            </label>
            <label>HazMat
              <select aria-label="Filter by HazMat" value={hazmat} onChange={(event) => { setHazmat(event.target.value); setOffset(0) }}><option value="">All HazMat</option><option>ABSENT</option><option>PRESENT</option><option>UNKNOWN</option></select>
            </label>
            <label>Bulky
              <select aria-label="Filter by Bulky" value={bulky} onChange={(event) => { setBulky(event.target.value); setOffset(0) }}><option value="">All Bulky</option><option>ABSENT</option><option>PRESENT</option><option>UNKNOWN</option></select>
            </label>
            <label>Provenance
              <select aria-label="Provenance field" value={provenanceField} onChange={(event) => { setProvenanceField(event.target.value); setOffset(0) }}><option value="">Any field</option><option value="asin">ASIN</option><option value="selling_price">Price</option><option value="profit">Profit</option><option value="roi">ROI</option><option value="margin">Margin</option></select>
            </label>
            <label>Status
              <select aria-label="Provenance status" value={provenanceStatus} onChange={(event) => { setProvenanceStatus(event.target.value); setOffset(0) }}><option value="">Any status</option><option>VERIFIED</option><option>INFERRED</option><option>NOT_FOUND</option><option>INVALID</option></select>
            </label>
            <label>
              Per page
              <select aria-label="Records per page" value={limit} onChange={(event) => { setLimit(Number(event.target.value)); setOffset(0) }}>
                {LIMIT_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            {/* The count is the same `total` the pagination reports, so the button
                always names exactly how many rows the export will contain. */}
            <button type="button" className="secondary-button catalog-export" onClick={exportFiltered} disabled={!selectedRunId}>
              {pagination ? `Export ${count(pagination.total)} result${pagination.total === 1 ? "" : "s"}` : "Export filtered view"}
            </button>
            {hasActiveQuery && <button type="button" className="secondary-button catalog-reset" onClick={resetQuery}>Reset search &amp; filters</button>}
          </section>

          <section className="panel catalog-columns" aria-label="Catalog column configuration">
            <details>
              <summary>Configure columns</summary>
              <div className="column-config-list">
                {DEFAULT_COLUMNS.map((column) => { const index = columns.indexOf(column); return <div className="column-config-row" key={column}><label><input type="checkbox" checked={index >= 0} disabled={column === "record_ref" || column === "product" || column === "decision"} onChange={() => toggleColumn(column)} /> {COLUMN_LABEL[column]}</label><span><button type="button" aria-label={`Move ${COLUMN_LABEL[column]} left`} disabled={index <= 0} onClick={() => moveColumn(column, -1)}>←</button><button type="button" aria-label={`Move ${COLUMN_LABEL[column]} right`} disabled={index < 0 || index === columns.length - 1} onClick={() => moveColumn(column, 1)}>→</button></span></div> })}
                <button type="button" className="secondary-button" onClick={resetColumns}>Reset columns</button>
              </div>
            </details>
          </section>

          <div className="catalog-query-state" aria-live="polite">
            <span>{pagination ? `${count(pagination.total)} result${pagination.total === 1 ? "" : "s"}` : "Querying results…"}</span>
            {search && <span className="query-chip">Search: “{search}”</span>}
            {decision !== "ALL" && <span className="query-chip">Decision: {decision}</span>}
            {minRoi && <span className="query-chip">ROI ≥ {minRoi}% · {confidence === "VERIFIED_ONLY" ? "verified" : "verified + inferred"}</span>}
            {minProfit && <span className="query-chip">Profit ≥ {minProfit} · {confidence === "VERIFIED_ONLY" ? "verified" : "verified + inferred"}</span>}
            {minMargin && <span className="query-chip">Margin ≥ {minMargin}% · {confidence === "VERIFIED_ONLY" ? "verified" : "verified + inferred"}</span>}
            {hazmat && <span className="query-chip">HazMat: {hazmat}</span>}
            {bulky && <span className="query-chip">Bulky: {bulky}</span>}
            {provenanceField && provenanceStatus && <span className="query-chip">{provenanceField}: {provenanceStatus}</span>}
            {(sort !== DEFAULT_SORT || direction !== DEFAULT_SORT_DIRECTION) && <span className="query-chip">Sorted by: {SORT_LABEL[sort]} {direction === "asc" ? "↑" : "↓"}</span>}
            {/* Favourites are a browser preference, never server state -- say so
                where the operator can see it, so a star is not mistaken for
                saved business data. */}
            {favorites.length > 0 && <span className="query-chip">★ {count(favorites.length)} starred in this browser only</span>}
          </div>

          {recordsState.kind === "loading" && <div className="status" aria-live="polite">Loading records…</div>}
          {recordsState.kind === "error" && (
            <div className="status">
              <p role="alert" className="error">{recordsState.message}</p>
              <button className="secondary-button" type="button" onClick={() => setRecordsRetry((v) => v + 1)}>Retry</button>
            </div>
          )}

          {recordsState.kind === "ready" && (
            <>
              <section className="panel table-panel">
                <p className="mobile-table-hint">Swipe horizontally to inspect all columns.</p>
                {columns.join(",") === DEFAULT_COLUMNS.join(",") && <div className="table-group-bar" aria-hidden="true">
                  <span className="group-identity">PRODUCT / IDENTITY</span>
                  <span className="group-economics">ECONOMICS</span>
                  <span className="group-risk">RISK</span>
                  <span className="group-decision">DECISION</span>
                  <span className="group-quality">QUALITY</span>
                  <span className="group-action">ACTION</span>
                </div>}
                <div className="catalog-table-scroll">
                <table className="catalog-table">
                  <thead>
                    <tr>{columns.map((column) => { const key = COLUMN_SORT_KEY[column]; return <th key={column} className={COLUMN_WIDTH_CLASS[column]} aria-sort={key && sort === key ? (direction === "asc" ? "ascending" : "descending") : "none"}>{headerFor(column)}</th> })}</tr>
                  </thead>
                  <tbody>
                    {recordsState.records.map((record) => (
                      <tr key={record.record_ref}>{columns.map((column) => <td key={column} className={`${column === "record_ref" ? "mono " : ""}${["price", "cog", "profit", "roi", "margin"].includes(column) ? "numeric-cell economic-value" : ""}${column === "product" ? "product-cell" : ""}${column === "identity" ? "identity-cell" : ""}${column === "image" ? "media-cell" : ""}`}>{cellFor(column, record)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
                </div>
                {recordsState.records.length === 0 && <p className="status">No records match these filters.</p>}
              </section>

              {pagination && pagination.total > 0 && (
                <nav className="pagination" aria-label="Catalog pagination">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={pagination.offset === 0}
                    onClick={() => setOffset((value) => Math.max(0, value - limit))}
                  >
                    Previous
                  </button>
                  <span aria-live="polite">
                    Showing {count(rangeStart)}–{count(rangeEnd)} of {count(pagination.total)}
                  </span>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={!pagination.has_more}
                    onClick={() => setOffset((value) => value + limit)}
                  >
                    Next
                  </button>
                </nav>
              )}

              <section className="panel">
                <p className="eyebrow">DETAIL</p>
                <h2>Product detail is available in Run Detail</h2>
                <p>Run Detail preserves the complete record, decision reasons, issues, risk severity, and every available field's provenance without creating a second product identity.</p>
              </section>
            </>
          )}
        </>
      )}
    </>
  )
}
