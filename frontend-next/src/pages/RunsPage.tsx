import { useEffect, useState } from "react"
import { apiErrorMessage, canRetryApiError } from "../api/client"
import { listRuns } from "../api/runs"
import type { RunSummaryOut } from "../api/types"
import { count } from "../format"
import { Badge, DecisionCounts } from "./shared"

/**
 * Golden's run history on real persisted ExecutionRuns.
 *
 * Golden's row hierarchy is kept — filename first, status badge, counts,
 * timestamp, one drill-down action, and BUY/REVIEW/PASS per row. Golden counted
 * those from records in memory; here they are the stored-snapshot counts
 * `GET /api/v1/runs` returns in `decisions` (one grouped query server-side),
 * and a run without stored records says so instead of showing zeros.
 *
 * Duplicate and Delete are not implemented: both need run lifecycle semantics
 * that no ADR covers yet.
 */
type State = { kind: "loading" } | { kind: "error"; message: string; retryable: boolean } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }
const SORTS = { started_at: "Started at", input_filename: "Input file", execution_id: "Execution ID", status: "Status", records_total: "Total records", records_processed: "Processed", records_successful: "Successful", records_with_errors: "Errors", warnings: "Warnings" } as const
type Sort = keyof typeof SORTS

export function RunsPage({ go }: { go: (path: string) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [reload, setReload] = useState(0)
  const [sort, setSort] = useState<Sort>("started_at")
  const [direction, setDirection] = useState<"asc" | "desc">("desc")

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    listRuns(100, controller.signal)
      .then((r) => setState(r.items.length ? { kind: "ready", runs: r.items } : { kind: "empty" }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: "error", message: apiErrorMessage(error), retryable: canRetryApiError(error) }) })
    return () => controller.abort()
  }, [reload])

  return <>
    <h1>Processing runs</h1>
    {state.kind === "loading" && <p className="panel">Loading runs…</p>}
    {state.kind === "error" && <section className="panel"><p role="alert" className="notice">{state.message}</p>{state.retryable && <button onClick={() => setReload((n) => n + 1)}>Retry</button>}</section>}
    {state.kind === "empty" && <p className="panel">No persisted runs yet. Process a batch with persistence enabled to see it here.</p>}
    {state.kind === "ready" && <section className="panel">
      <p aria-live="polite">{count(state.runs.length)} persisted run{state.runs.length === 1 ? "" : "s"} (up to 100), ordered by {SORTS[sort]}, {direction === "asc" ? "ascending" : "descending"}. Each run is one supplier file.</p>
      <div className="chart-controls">
        <label>Sort runs<select value={sort} onChange={(event) => {
          const key = event.target.value as Sort
          setSort(key); setDirection(["input_filename", "execution_id", "status"].includes(key) ? "asc" : "desc")
        }}>{Object.entries(SORTS).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
        <label>Run sort direction<select value={direction} onChange={(event) => setDirection(event.target.value as "asc" | "desc")}><option value="asc">Ascending</option><option value="desc">Descending</option></select></label>
      </div>
      {[...state.runs].sort((a, b) => {
        const av = sort === "started_at" ? Date.parse(a.started_at) : a[sort]
        const bv = sort === "started_at" ? Date.parse(b.started_at) : b[sort]
        const compared = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv))
        return (direction === "asc" ? compared : -compared) || a.execution_id.localeCompare(b.execution_id)
      }).map((run) => <article key={run.execution_id}>
        <b>{run.input_filename}</b>
        <p>
          <Badge>{run.status}</Badge>{" "}
          {count(run.records_total)} records · {count(run.records_successful)} successful · {count(run.records_with_errors)} with errors · {count(run.warnings)} warning(s) · {new Date(run.started_at).toLocaleString()}
        </p>
        <p><DecisionCounts decisions={run.decisions} /></p>
        <p className="mono"><small>{run.execution_id}</small></p>
        <button onClick={() => go(`/runs/${encodeURIComponent(run.execution_id)}`)}>Open</button>
        <button onClick={() => go(`/catalog?run=${encodeURIComponent(run.execution_id)}`)}>Open in Catalog</button>
      </article>)}
    </section>}
  </>
}
