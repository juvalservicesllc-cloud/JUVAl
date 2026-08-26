import { useEffect, useState } from "react"
import { apiErrorMessage, ApiError } from "../api/client"
import { getRun } from "../api/runs"
import type { RunSummaryOut } from "../api/types"
import { count } from "../format"
import { Badge } from "./shared"

/**
 * Minimum run detail needed to close the navigation loop
 * Import → Batch → Runs → Run Detail → Catalog scoped to that run.
 *
 * Only ExecutionRun's own persisted fields are shown. Decision outcomes and
 * analytics belong to the analytics endpoint and arrive with the Dashboard
 * migration; nothing is derived here to fill the gap.
 */
type State =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "error"; message: string }
  | { kind: "ready"; run: RunSummaryOut }

export function RunDetailPage({ executionId, go }: { executionId: string; go: (path: string) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    getRun(executionId, controller.signal)
      .then((run) => setState({ kind: "ready", run }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        // An unknown execution id is a real 404, not a transport failure --
        // saying "retry" there would be misleading.
        if (error instanceof ApiError && error.status === 404) return setState({ kind: "missing" })
        setState({ kind: "error", message: apiErrorMessage(error) })
      })
    return () => controller.abort()
  }, [executionId, reload])

  if (state.kind === "loading") return <section className="panel"><h1>Run detail</h1><p>Loading run…</p></section>
  if (state.kind === "missing") return <section className="panel">
    <h1>Run not found</h1>
    <p>No persisted run matches this execution id. It may never have been persisted, or the id may be wrong.</p>
    <button onClick={() => go("/runs")}>Back to Runs</button>
  </section>
  if (state.kind === "error") return <section className="panel"><h1>Run detail</h1><p role="alert" className="notice">{state.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>

  const { run } = state
  return <>
    <h1>{run.input_filename}</h1>
    <section className="panel">
      <p><Badge>{run.status}</Badge> · started {new Date(run.started_at).toLocaleString()}{run.finished_at ? ` · finished ${new Date(run.finished_at).toLocaleString()}` : ""}</p>
      <p className="mono"><small>{run.execution_id}</small></p>
      <div className="kpis">
        <article><small>Records</small><strong>{count(run.records_total)}</strong></article>
        <article><small>Processed</small><strong>{count(run.records_processed)}</strong></article>
        <article><small>Successful</small><strong>{count(run.records_successful)}</strong></article>
        <article><small>With errors</small><strong>{count(run.records_with_errors)}</strong></article>
        <article><small>Warnings</small><strong>{count(run.warnings)}</strong></article>
      </div>
      <p><small>Input hash <span className="mono">{run.input_hash}</span></small></p>
    </section>
    <section className="panel">
      <h2>Review the records</h2>
      <p>Catalog opens scoped to this run: its records only, queried on the server.</p>
      <button onClick={() => go(`/catalog?run=${encodeURIComponent(run.execution_id)}`)}>Open in Catalog</button>
      <button onClick={() => go("/runs")}>All runs</button>
    </section>
  </>
}
