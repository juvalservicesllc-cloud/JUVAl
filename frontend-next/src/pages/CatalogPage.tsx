import { useEffect, useState, type ReactNode } from "react"
import { apiErrorMessage } from "../api/client"
import { filteredExportUrl, getRunBrands, getRunRecords, getRuns } from "../api/catalog"
import type { BrandDistributionOut, CatalogQuery, FieldValueOut, RecordOut, RecordSort, RunSummaryOut } from "../api/types"
import { clearCatalogQuery, loadCatalogQuery, saveCatalogQuery } from "../catalogQuery"
import { CATALOG_COLUMNS, loadColumns, saveColumns, type ColumnId } from "../catalogColumns"
import { CatalogColumnControls } from "./CatalogColumnControls"
import { favoriteKey, loadFavorites, saveFavorites, toggleFavorite } from "../favorites"
import { count, fieldMoney, fieldPercent } from "../format"
import { DeclaredDemandCell } from "./DeclaredDemand"
import { SuggestedPriceCell } from "./SuggestedPrice"
import { SeverityProvenance } from "./SeverityProvenance"
import { Badge, PendingDemandTag, ProvenanceBadge } from "./shared"
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
  limit: 25, offset: 0, search: "", brand: "", decision: "ALL",
  // Golden opened on the most profitable rows; the backend sorts NULLs last
  // under DESC, so unknown-profit records sink instead of heading the page.
  sort: "profit", direction: "desc",
  minRoi: "", minProfit: "", minMargin: "", confidence: "VERIFIED_ONLY",
  hazmat: "", bulky: "", provenanceField: "", provenanceStatus: "", pendingDemand: false,
}

type RunsState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }
type BrandsState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; brands: BrandDistributionOut }
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

export function CatalogPage({ initialRunId = "", initialPendingDemand = false }: { initialRunId?: string; initialPendingDemand?: boolean } = {}) {
  const [runs, setRuns] = useState<RunsState>({ kind: "loading" })
  const [runId, setRunId] = useState(initialRunId)
  const [records, setRecords] = useState<RecordsState>({ kind: "loading" })
  const [brands, setBrands] = useState<BrandsState>({ kind: "loading" })
  // Restored once, on mount. Only preferences come back -- never the run,
  // never the page, never anything the server returned.
  const [query, setQuery] = useState<CatalogQuery>(() => {
    const restored = loadCatalogQuery(DEFAULT_QUERY)
    return initialPendingDemand ? { ...restored, pendingDemand: true } : restored
  })
  const [favorites, setFavorites] = useState<string[]>(loadFavorites)
  const [reload, setReload] = useState(0)
  const [columns, setColumns] = useState(loadColumns)
  useEffect(() => { saveColumns(columns) }, [columns])
  const visibleColumns = columns.filter((c) => c.visible).map((c) => CATALOG_COLUMNS.find((spec) => spec.id === c.id)!)

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

  // Brand options belong to one run: reload them, and drop a selected brand,
  // whenever the run changes, so a brand never carries over to a run it does
  // not exist in.
  useEffect(() => {
    if (!runId) return
    const controller = new AbortController()
    setBrands({ kind: "loading" })
    getRunBrands(runId, controller.signal)
      .then((distribution) => setBrands({ kind: "ready", brands: distribution }))
      .catch(() => { if (!controller.signal.aborted) setBrands({ kind: "error" }) })
    return () => controller.abort()
  }, [runId, reload])

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
          <label>Run<select aria-label="Run" value={runId} onChange={(e) => { setRunId(e.target.value); setQuery((c) => ({ ...c, brand: "", offset: 0 })) }}>
            {runs.runs.map((run) => <option key={run.execution_id} value={run.execution_id}>{run.input_filename} — {new Date(run.started_at).toLocaleString()}</option>)}
          </select></label>
          {/* Exact brand values the run stored (analytics `brands`), never free
              text: the API matches exactly and case-sensitively, and records
              without a brand have no filter of their own. */}
          <label>Brand<select aria-label="Brand" value={query.brand} disabled={brands.kind !== "ready" || brands.brands.items.length === 0} onChange={(e) => patch({ brand: e.target.value })}>
            <option value="">All Brand</option>
            {brands.kind === "ready" && brands.brands.items.map((b) => <option key={b.label} value={b.label}>{b.label} ({count(b.count)})</option>)}
          </select></label>
          <label>Decision<select aria-label="Decision" value={query.decision} onChange={(e) => patch({ decision: e.target.value })}>
            <option value="ALL">All Decision</option><option>BUY</option><option>REVIEW</option><option>PASS</option>
          </select></label>
          {/* Informative sub-set of REVIEW computed by the backend; it never
              changes a decision and is not a BUY signal (D7-D). */}
          <label>Review status<select aria-label="Review status" value={query.pendingDemand ? "pending" : ""} onChange={(e) => patch({ pendingDemand: e.target.value === "pending" })}>
            <option value="">All records</option><option value="pending">Pending demand verification</option>
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
        {query.minRoi.trim() !== "" && Number.isFinite(Number(query.minRoi)) && <p className="local-note" role="status">Minimum ROI: {query.minRoi}%</p>}
        {query.pendingDemand && <p className="local-note pending-demand-note" role="status">
          Showing REVIEW records whose only recorded blocker is unknown demand: economics and risk passed every rule, but no demand evidence exists, so the decision stays REVIEW. This is not a BUY recommendation. Records processed before reason codes were stored cannot be classified and are not listed.
        </p>}
        {brands.kind === "error" && <p className="local-note">Brand list unavailable for this run; the brand filter is disabled rather than guessed.</p>}
        {brands.kind === "ready" && brands.brands.distinct > brands.brands.items.length && <p className="local-note">
          Brand lists the {count(brands.brands.items.length)} most frequent of {count(brands.brands.distinct)} brands in this run; use search to find the others.
        </p>}
        {brands.kind === "ready" && brands.brands.not_recorded > 0 && <p className="local-note">{count(brands.brands.not_recorded)} record{brands.brands.not_recorded === 1 ? " has" : "s have"} no brand recorded and appear only under All Brand.</p>}
      </section>

      <CatalogColumnControls columns={columns} onChange={setColumns} />

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
            {visibleColumns.map(({ id, label, sort: field }) => {
              if (!field) return <th key={id}>{label}</th>
              const active = query.sort === field
              return <th key={id} aria-sort={active ? (query.direction === "asc" ? "ascending" : "descending") : "none"}>
                <button onClick={() => sortBy(field)} aria-pressed={active}>{label} {active ? (query.direction === "asc" ? "↑" : "↓") : "↕"}</button>
              </th>
            })}
          </tr></thead>
          <tbody>
            {records.records.map((record) => {
              const key = favoriteKey(runId, record.record_ref)
              const starred = favorites.includes(key)
              const cells: Record<ColumnId, ReactNode> = {
                // Preserve the honest unavailable-image slot; no URL is invented.
                image: <ProductThumbnail src="" alt={text(record.title) || record.record_ref} />,
                source: <small title={activeRun?.input_filename}>{activeRun?.input_filename ?? "—"}</small>,
                brand: text(record.brand) || "—",
                title: <a href={`/run/${encodeURIComponent(runId)}/product/${encodeURIComponent(record.record_ref)}`}>{text(record.title) || record.record_ref}</a>,
                cog: fieldMoney(record.cog),
                suggested: <SuggestedPriceCell record={record} />,
                selling: <Cell value={record.selling_price} format={fieldMoney} />,
                profit: <Cell value={record.profit} format={fieldMoney} />,
                roi: <Cell value={record.roi} format={fieldPercent} />,
                margin: <Cell value={record.margin} format={fieldPercent} />,
                hazmat: <>{record.hazmat_status ?? "UNKNOWN"} <SeverityProvenance compact risk="HazMat" status={record.hazmat_severity_status} sourceType={record.hazmat_severity_source_type} /></>,
                bulky: <>{record.bulky_status ?? "UNKNOWN"} <SeverityProvenance compact risk="Bulky" status={record.bulky_severity_status} sourceType={record.bulky_severity_source_type} /></>,
                decision: <>{record.decision ? <Badge>{record.decision}</Badge> : "—"}{record.review_classification === "PENDING_DEMAND_VERIFICATION" && <> <PendingDemandTag /></>}</>,
                demand: <DeclaredDemandCell record={record} />,
                favorite: <button className="favorite-button" aria-label={`${starred ? "Remove" : "Add"} ${text(record.title) || record.record_ref} ${starred ? "from" : "to"} favorites`} aria-pressed={starred} title={starred ? "Starred in this browser" : "Star in this browser"} onClick={() => star(record.record_ref)}>{starred ? "★" : "☆"}</button>,
              }
              return <tr key={record.record_ref}>
                {visibleColumns.map(({ id }) => <td key={id}>{cells[id]}</td>)}
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
