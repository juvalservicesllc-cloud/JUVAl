import { useEffect, useState } from "react"
import { apiErrorMessage } from "../api/client"
import { filteredExportUrl, getRunRecords, getRuns } from "../api/catalog"
import type { CatalogQuery, FieldValueOut, RecordOut, RecordSort, RunSummaryOut } from "../api/types"
import { clearCatalogQuery, loadCatalogQuery, saveCatalogQuery } from "../catalogQuery"
import { favoriteKey, loadFavorites, saveFavorites, toggleFavorite } from "../favorites"
import { count, fieldMoney, fieldPercent } from "../format"
import { Badge, ProvenanceBadge } from "./shared"
import { ProductThumbnail } from "./ProductThumbnail"
import "./catalog-controls.css"

/**
 * Golden's Catalog, running on the real backend (ADR-030).
 *
 * The layout, toolbar, column order, thumbnail slot, sorting affordance,
 * favourite star and pagination are Golden's, deliberately unchanged — this is
 * the user-approved experience and productionization is not a redesign.
 *
 * What changed is everything under it. Golden filtered, sorted and paginated an
 * in-memory array of simulated records. Every one of those is now a server-side
 * query parameter against a persisted ExecutionRun, and every value carries the
 * verification status the backend assigned it.
 */

const DEFAULT_QUERY: CatalogQuery = {
  limit: 20, offset: 0, search: "", decision: "ALL",
  // Golden opened on the most profitable rows; the backend sorts NULLs last
  // under DESC, so unknown-profit records sink instead of heading the page.
  sort: "profit", direction: "desc",
  minRoi: "", minProfit: "", minMargin: "", confidence: "VERIFIED_ONLY",
  hazmat: "", bulky: "", provenanceField: "", provenanceStatus: "",
}

// Golden sorted eleven columns client-side. These are the ones the API can
// actually sort server-side; Brand has no sort key, so its header stays plain
// rather than pretending to be interactive.
const COLUMNS: [label: string, sort: RecordSort | null][] = [
  ["Brand", null], ["Title", "title"], ["Cost", "cog"], ["Selling", "price"],
  ["Profit", "profit"], ["ROI", "roi"], ["Margin", "margin"],
  ["Hazmat", "hazmat"], ["Bulky", "bulky"], ["Decision", "decision"],
]

type RunsState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }
type RecordsState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; records: RecordOut[]; total: number; hasMore: boolean }

function text(value: FieldValueOut): string {
  return value.value === null || value.value === undefined ? "" : String(value.value)
}

/** A sensitive value is never rendered without its verification status
 *  (ADR-003/ADR-004). Golden showed no status at all here because its numbers
 *  were fixtures; real ones must carry theirs. */
function Cell({ value, format }: { value: FieldValueOut; format: (v: string | number | null) => string }) {
  if (value.status === null) return <>—</>
  return <span className="fv">{format(value.value)} <ProvenanceBadge status={value.status} /></span>
}

export function CatalogPage({ initialRunId = "" }: { initialRunId?: string } = {}) {
  const [runs, setRuns] = useState<RunsState>({ kind: "loading" })
  const [runId, setRunId] = useState(initialRunId)
  const [records, setRecords] = useState<RecordsState>({ kind: "loading" })
  // Restored once, on mount. Only preferences come back -- never the run,
  // never the page, never anything the server returned.
  const [query, setQuery] = useState<CatalogQuery>(() => loadCatalogQuery(DEFAULT_QUERY))
  const [favorites, setFavorites] = useState<string[]>(loadFavorites)
  const [reload, setReload] = useState(0)

  const patch = (next: Partial<CatalogQuery>) => setQuery((current) => ({ ...current, ...next, offset: 0 }))

  // Persist the canonical query, so what is remembered is exactly what was sent
  // to the server -- not the raw input on the way to it.
  useEffect(() => { saveCatalogQuery(query) }, [query])

  useEffect(() => {
    const controller = new AbortController()
    setRuns({ kind: "loading" })
    getRuns(controller.signal)
      .then((response) => {
        if (!response.items.length) return setRuns({ kind: "empty" })
        setRuns({ kind: "ready", runs: response.items })
        // A run id from the URL wins when it exists, so Run Detail can hand off
        // straight into that run rather than whichever run happens to be newest.
        setRunId((current) => (current && response.items.some((r) => r.execution_id === current) ? current : response.items[0].execution_id))
      })
      .catch((error: unknown) => { if (!controller.signal.aborted) setRuns({ kind: "error", message: apiErrorMessage(error) }) })
    return () => controller.abort()
  }, [reload])

  // One request per state change. AbortController cancels an in-flight request
  // when any dependency changes again, so a slow earlier response can never
  // overwrite a newer one.
  useEffect(() => {
    if (!runId) return
    const controller = new AbortController()
    setRecords({ kind: "loading" })
    getRunRecords(runId, query, controller.signal)
      .then((response) => setRecords({ kind: "ready", records: response.records, total: response.pagination.total, hasMore: response.pagination.has_more }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setRecords({ kind: "error", message: apiErrorMessage(error) }) })
    return () => controller.abort()
  }, [runId, query, reload])

  function sortBy(field: RecordSort) {
    setQuery((current) => ({
      ...current, offset: 0,
      sort: field,
      direction: current.sort === field ? (current.direction === "asc" ? "desc" : "asc")
        : (field === "profit" || field === "roi" || field === "margin" || field === "price" ? "desc" : "asc"),
    }))
  }

  function star(recordRef: string) {
    setFavorites((current) => { const next = toggleFavorite(current, favoriteKey(runId, recordRef)); saveFavorites(next); return next })
  }

  const activeRun = runs.kind === "ready" ? runs.runs.find((r) => r.execution_id === runId) ?? null : null
  const total = records.kind === "ready" ? records.total : 0
  const pages = Math.max(1, Math.ceil(total / query.limit))
  const page = Math.floor(query.offset / query.limit) + 1

  return <>
    <h1>Run-scoped catalog</h1>

    {runs.kind === "loading" && <p className="panel">Loading persisted runs…</p>}
    {runs.kind === "error" && <section className="panel"><p role="alert">{runs.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>}
    {runs.kind === "empty" && <p className="panel">No persisted runs yet. Process a catalog with persistence enabled to review its records here.</p>}

    {runs.kind === "ready" && <>
      <section className="panel">
        <h2>Filter results</h2>
        <p>Filters change which records are visible and exported; they never recalculate decisions. Every change queries the selected run on the server.</p>
        <div className="filters">
          <input aria-label="Search catalog" placeholder="Search products" value={query.search} onChange={(e) => patch({ search: e.target.value })} />
          <label>Run<select aria-label="Run" value={runId} onChange={(e) => { setRunId(e.target.value); setQuery((c) => ({ ...c, offset: 0 })) }}>
            {runs.runs.map((run) => <option key={run.execution_id} value={run.execution_id}>{run.input_filename} — {new Date(run.started_at).toLocaleString()}</option>)}
          </select></label>
          <label>Decision<select aria-label="Decision" value={query.decision} onChange={(e) => patch({ decision: e.target.value })}>
            <option value="ALL">All Decision</option><option>BUY</option><option>REVIEW</option><option>PASS</option>
          </select></label>
          {/* Golden's "Amazon" filter selected a fixture match state. The real
              equivalent is the ASIN field's verification status. */}
          <label>Amazon<select aria-label="Amazon" value={query.provenanceStatus} onChange={(e) => patch({ provenanceField: e.target.value ? "asin" : "", provenanceStatus: e.target.value })}>
            <option value="">All Amazon</option><option>VERIFIED</option><option>INFERRED</option><option>NOT_FOUND</option><option>INVALID</option>
          </select></label>
          <label>Hazmat<select aria-label="Hazmat" value={query.hazmat} onChange={(e) => patch({ hazmat: e.target.value })}>
            <option value="">All Hazmat</option><option>PRESENT</option><option>ABSENT</option><option>UNKNOWN</option>
          </select></label>
          <label>Bulky<select aria-label="Bulky" value={query.bulky} onChange={(e) => patch({ bulky: e.target.value })}>
            <option value="">All Bulky</option><option>PRESENT</option><option>ABSENT</option><option>UNKNOWN</option>
          </select></label>
          <label>Minimum ROI filter %<input aria-label="Minimum ROI filter" type="number" value={query.minRoi} onChange={(e) => patch({ minRoi: e.target.value })} /></label>
          <label>Minimum Profit<input aria-label="Minimum Profit" type="number" value={query.minProfit} onChange={(e) => patch({ minProfit: e.target.value })} /></label>
          <label>Minimum Margin %<input aria-label="Minimum Margin" type="number" value={query.minMargin} onChange={(e) => patch({ minMargin: e.target.value })} /></label>
          {/* Production-only: Golden could not express it because it had no
              verification states to exclude. */}
          <label>Economic confidence<select aria-label="Economic confidence" value={query.confidence} onChange={(e) => patch({ confidence: e.target.value as CatalogQuery["confidence"] })}>
            <option value="VERIFIED_ONLY">Verified only</option><option value="INCLUDE_INFERRED">Include inferred</option>
          </select></label>
          <label>Per page<select aria-label="Per page" value={query.limit} onChange={(e) => patch({ limit: Number(e.target.value) })}>
            {[25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
          </select></label>
          <button onClick={() => { clearCatalogQuery(); setQuery(DEFAULT_QUERY) }}>Reset filters</button>
          <button onClick={() => window.open(filteredExportUrl(runId, query), "_blank", "noopener,noreferrer")} disabled={!runId}>Export {count(total)} results</button>
        </div>
      </section>

      {/* Golden edited the decision bands here and rewrote stored decisions.
          Production must not: ExecutionRun does not record the thresholds a run
          used, so the bands cannot be shown without inventing them, and a
          frontend must never change a historical decision. */}
      <section className="panel decision-thresholds">
        <div><h2>Decision thresholds</h2><p>Risk and other blockers still take precedence.</p></div>
        <p className="threshold-unavailable">Not recorded for this run. Decisions come from the backend Decision Engine using the thresholds submitted when the run was processed; JUVAl does not yet persist them on the run, so they are not shown rather than guessed.</p>
      </section>

      {records.kind === "loading" && <p className="panel">Loading records…</p>}
      {records.kind === "error" && <section className="panel"><p role="alert">{records.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>}

      {records.kind === "ready" && <>
        <p className="result-count">{count(total)} result{total === 1 ? "" : "s"}</p>
        <div className="table"><table>
          <thead><tr>
            <th>Image</th><th>Source</th>
            {COLUMNS.map(([label, field]) => {
              if (!field) return <th key={label}>{label}</th>
              const active = query.sort === field
              return <th key={label} aria-sort={active ? (query.direction === "asc" ? "ascending" : "descending") : "none"}>
                <button onClick={() => sortBy(field)} aria-pressed={active}>{label} {active ? (query.direction === "asc" ? "↑" : "↓") : "↕"}</button>
              </th>
            })}
            <th>Favorite</th>
          </tr></thead>
          <tbody>
            {records.records.map((record) => {
              const key = favoriteKey(runId, record.record_ref)
              const starred = favorites.includes(key)
              return <tr key={record.record_ref}>
                {/* No canonical product image exists in RecordOut yet, so the
                    slot renders Golden's own "No image" state. No URL is
                    invented, borrowed or scraped. */}
                <td><ProductThumbnail src="" alt={text(record.title) || record.record_ref} /></td>
                <td><small title={activeRun?.input_filename}>{activeRun?.input_filename ?? "—"}</small></td>
                <td>{text(record.brand) || "—"}</td>
                <td><a href={`/run/${encodeURIComponent(runId)}/product/${encodeURIComponent(record.record_ref)}`}>{text(record.title) || record.record_ref}</a></td>
                <td>{fieldMoney(record.cog)}</td>
                <td><Cell value={record.selling_price} format={fieldMoney} /></td>
                <td><Cell value={record.profit} format={fieldMoney} /></td>
                <td><Cell value={record.roi} format={fieldPercent} /></td>
                <td><Cell value={record.margin} format={fieldPercent} /></td>
                <td>{record.hazmat_status ?? "UNKNOWN"}</td>
                <td>{record.bulky_status ?? "UNKNOWN"}</td>
                <td>{record.decision ? <Badge>{record.decision}</Badge> : "—"}</td>
                <td><button className="favorite-button" aria-label={`${starred ? "Remove" : "Add"} ${text(record.title) || record.record_ref} ${starred ? "from" : "to"} favorites`} aria-pressed={starred} title={starred ? "Starred in this browser" : "Star in this browser"} onClick={() => star(record.record_ref)}>{starred ? "★" : "☆"}</button></td>
              </tr>
            })}
          </tbody>
        </table></div>
        {records.records.length === 0 && <p className="panel">No records match these filters.</p>}
        <p>
          <button disabled={query.offset === 0} onClick={() => setQuery((c) => ({ ...c, offset: Math.max(0, c.offset - c.limit) }))}>Previous</button>
          {" "}Page {page} of {pages}{" "}
          <button disabled={!records.hasMore} onClick={() => setQuery((c) => ({ ...c, offset: c.offset + c.limit }))}>Next</button>
        </p>
        {favorites.length > 0 && <p className="local-note">★ {count(favorites.length)} starred in this browser only — favourites are a local preference, not saved to your account or shared.</p>}
      </>}
    </>}
  </>
}
