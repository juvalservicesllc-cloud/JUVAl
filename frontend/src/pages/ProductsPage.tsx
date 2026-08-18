import { useEffect, useState } from "react"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRunRecords } from "../api/records"
import { getRuns } from "../api/runs"
import { ProvenanceValue } from "../components/ProvenanceValue"
import { StatusBadge } from "../components/StatusBadge"
import type { Decision, RecordOut, RecordPaginationOut, RecordSort, RunSummaryOut, SortDirection } from "../types"

type RunsState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }
type RecordsState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; records: RecordOut[]; pagination: RecordPaginationOut }

const LIMIT_OPTIONS = [25, 50, 100]
const SORT_LABEL: Record<RecordSort, string> = { record_ref: "Record", sku: "SKU", decision: "Decision", profit: "Profit", roi: "ROI", margin: "Margin" }
// record_ref/sku/decision are naturally read ascending; profit/roi/margin are
// interesting largest-first -- matches the prior client-side sort behavior.
const DEFAULT_DIRECTION: Record<RecordSort, SortDirection> = { record_ref: "asc", sku: "asc", decision: "asc", profit: "desc", roi: "desc", margin: "desc" }

function text(value: unknown): string {
  return value === null || value === undefined ? "" : String(value)
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
  const [sort, setSort] = useState<RecordSort>("record_ref")
  const [direction, setDirection] = useState<SortDirection>("asc")
  const [limit, setLimit] = useState(50)
  const [offset, setOffset] = useState(0)

  // Server-side search only, lightly debounced so normal typing doesn't
  // issue one request per keystroke. `search` (not `searchInput`) is what
  // reaches the API and what resets the page.
  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(searchInput)
      setOffset(0)
    }, 300)
    return () => clearTimeout(id)
  }, [searchInput])

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
      { limit, offset, search: search || undefined, decision: decision === "ALL" ? undefined : decision, sort, direction },
      controller.signal,
    )
      .then((response) => setRecordsState({ kind: "ready", records: response.records, pagination: response.pagination }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setRecordsState({ kind: "error", message: error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error) })
      })
    return () => controller.abort()
  }, [selectedRunId, search, decision, sort, direction, limit, offset, recordsRetry])

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
    return (
      <button type="button" onClick={() => changeSort(key)} aria-pressed={active}>
        {SORT_LABEL[key]}
        {active && <span aria-hidden="true">{direction === "asc" ? " ▲" : " ▼"}</span>}
      </button>
    )
  }

  const pagination = recordsState.kind === "ready" ? recordsState.pagination : null
  const rangeStart = pagination && pagination.total > 0 ? pagination.offset + 1 : 0
  const rangeEnd = pagination ? Math.min(pagination.offset + limit, pagination.total) : 0

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">RUN-SCOPED CATALOG</p>
          <h2>Products</h2>
          <p>Snapshots belong to an execution run; JUVAl does not claim a global product identity.</p>
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
          <section className="panel catalog-controls">
            <label>
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
              <input
                aria-label="Search catalog"
                value={searchInput}
                maxLength={200}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="SKU, title, brand, ASIN"
              />
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
            <label>
              Per page
              <select aria-label="Records per page" value={limit} onChange={(event) => { setLimit(Number(event.target.value)); setOffset(0) }}>
                {LIMIT_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
          </section>

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
                <table>
                  <thead>
                    <tr>
                      <th>{sortButton("record_ref")}</th>
                      <th>{sortButton("sku")}</th>
                      <th>Product</th>
                      <th>ASIN / provenance</th>
                      <th>Price</th>
                      <th>{sortButton("profit")}</th>
                      <th>{sortButton("roi")}</th>
                      <th>{sortButton("margin")}</th>
                      <th>Risk</th>
                      <th>{sortButton("decision")}</th>
                      <th>Issues</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recordsState.records.map((record) => (
                      <tr key={record.record_ref}>
                        <td className="mono">{record.record_ref}</td>
                        <td>{record.supplier_sku ?? "—"}</td>
                        <td>
                          <strong>{text(record.title?.value) || "—"}</strong>
                          {record.brand?.value ? <div className="text-muted">{text(record.brand.value)}</div> : null}
                        </td>
                        <td><ProvenanceValue value={record.asin} /></td>
                        <td><ProvenanceValue value={record.selling_price} /></td>
                        <td><ProvenanceValue value={record.profit} /></td>
                        <td><ProvenanceValue value={record.roi} /></td>
                        <td><ProvenanceValue value={record.margin} /></td>
                        <td>{record.hazmat_status ?? "UNKNOWN"} / {record.bulky_status ?? "UNKNOWN"}</td>
                        <td>{record.decision ? <StatusBadge value={record.decision} /> : "—"}</td>
                        <td>{record.issue_count > 0 ? record.issue_count : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
                    Showing {rangeStart.toLocaleString()}–{rangeEnd.toLocaleString()} of {pagination.total.toLocaleString()}
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
