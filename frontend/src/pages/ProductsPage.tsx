import { useEffect, useMemo, useState } from "react"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRunRecords } from "../api/records"
import { getRuns } from "../api/runs"
import { ProvenanceValue } from "../components/ProvenanceValue"
import { StatusBadge } from "../components/StatusBadge"
import type { RecordOut, RunSummaryOut } from "../types"

type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[]; records: RecordOut[] }
type SortKey = "sku" | "title" | "roi" | "profit" | "decision"

function text(value: unknown) { return value === null || value === undefined ? "" : String(value) }
function number(value: RecordOut["roi"] | RecordOut["profit"]) { const result = Number(value.value); return Number.isFinite(result) ? result : Number.NEGATIVE_INFINITY }

export function ProductsPage() {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [runId, setRunId] = useState("")
  const [query, setQuery] = useState("")
  const [decision, setDecision] = useState("ALL")
  const [sort, setSort] = useState<SortKey>("sku")
  const [descending, setDescending] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    getRuns({ limit: 100, signal: controller.signal }).then(async ({ items }) => {
      if (!items.length) { setState({ kind: "empty" }); return }
      const selected = runId && items.some((run) => run.execution_id === runId) ? runId : items[0].execution_id
      if (selected !== runId) setRunId(selected)
      const response = await getRunRecords(selected, controller.signal)
      setState({ kind: "ready", runs: items, records: response.records })
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return
      setState({ kind: "error", message: error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error) })
    })
    return () => controller.abort()
  }, [runId, retry])

  const rows = useMemo(() => {
    if (state.kind !== "ready") return []
    const needle = query.trim().toLowerCase()
    const sorted = state.records.filter((record) => {
      const searchable = [record.supplier_sku, record.title?.value, record.brand?.value, record.asin.value, record.record_ref].map(text).join(" ").toLowerCase()
      return (!needle || searchable.includes(needle)) && (decision === "ALL" || record.decision === decision)
    }).slice().sort((left, right) => {
      const values: Record<SortKey, [string | number, string | number]> = {
        sku: [text(left.supplier_sku), text(right.supplier_sku)], title: [text(left.title?.value), text(right.title?.value)],
        roi: [number(left.roi), number(right.roi)], profit: [number(left.profit), number(right.profit)], decision: [text(left.decision), text(right.decision)],
      }
      const [a, b] = values[sort]; const result = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b))
      return descending ? -result : result
    })
    return sorted
  }, [state, query, decision, sort, descending])

  return <>
    <div className="page-intro"><div><p className="eyebrow">RUN-SCOPED CATALOG</p><h2>Products</h2><p>Snapshots belong to an execution run; JUVAl does not claim a global product identity.</p></div></div>
    {state.kind === "loading" && <div className="status" aria-live="polite">Loading catalog…</div>}
    {state.kind === "empty" && <div className="status">No persisted runs yet. Process a catalog with persistence enabled to review its records.</div>}
    {state.kind === "error" && <div className="status"><p role="alert" className="error">{state.message}</p><button className="secondary-button" type="button" onClick={() => setRetry((value) => value + 1)}>Retry</button></div>}
    {state.kind === "ready" && <>
      <section className="panel catalog-controls"><label>Run<select aria-label="Catalog run" value={runId} onChange={(event) => setRunId(event.target.value)}>{state.runs.map((run) => <option key={run.execution_id} value={run.execution_id}>{run.input_filename} — {new Date(run.started_at).toLocaleString()}</option>)}</select></label><label>Search<input aria-label="Search catalog" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="SKU, title, brand, ASIN" /></label><label>Decision<select aria-label="Filter by decision" value={decision} onChange={(event) => setDecision(event.target.value)}><option value="ALL">All decisions</option><option value="BUY">BUY</option><option value="REVIEW">REVIEW</option><option value="PASS">PASS</option></select></label><span>{rows.length} of {state.records.length} records</span></section>
      <section className="panel table-panel"><table><thead><tr><th><button onClick={() => { setSort("sku"); setDescending(sort === "sku" ? !descending : false) }}>SKU</button></th><th><button onClick={() => { setSort("title"); setDescending(sort === "title" ? !descending : false) }}>Product</button></th><th>Brand</th><th>ASIN / provenance</th><th>Price</th><th><button onClick={() => { setSort("profit"); setDescending(sort === "profit" ? !descending : true) }}>Profit</button></th><th><button onClick={() => { setSort("roi"); setDescending(sort === "roi" ? !descending : true) }}>ROI</button></th><th>Risk</th><th><button onClick={() => { setSort("decision"); setDescending(sort === "decision" ? !descending : false) }}>Decision</button></th></tr></thead><tbody>{rows.map((record) => <tr key={record.record_ref}><td className="mono">{record.supplier_sku ?? "—"}</td><td><strong>{text(record.title?.value) || "—"}</strong></td><td>{text(record.brand?.value) || "—"}</td><td><ProvenanceValue value={record.asin} /></td><td><ProvenanceValue value={record.selling_price} /></td><td><ProvenanceValue value={record.profit} /></td><td><ProvenanceValue value={record.roi} /></td><td>{record.hazmat_status ?? "UNKNOWN"} / {record.bulky_status ?? "UNKNOWN"}</td><td>{record.decision ? <StatusBadge value={record.decision} /> : "—"}</td></tr>)}</tbody></table>{rows.length === 0 && <p className="status">No records match these filters.</p>}</section>
      <section className="panel"><p className="eyebrow">DETAIL</p><h2>Product detail is available in Run Detail</h2><p>Run Detail preserves the complete record, decision reasons, issues, risk severity, and every available field's provenance without creating a second product identity.</p></section>
    </>}
  </>
}
