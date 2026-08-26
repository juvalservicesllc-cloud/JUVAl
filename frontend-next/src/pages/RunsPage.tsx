import { useEffect, useState } from "react"
import { apiErrorMessage } from "../api/client"
import { listRuns } from "../api/runs"
import type { RunSummaryOut } from "../api/types"
import { count } from "../format"
import { Badge } from "./shared"

/**
 * Golden's run history on real persisted ExecutionRuns.
 *
 * Golden's row hierarchy is kept — filename first, status badge, counts,
 * timestamp, one drill-down action. Golden also showed BUY/REVIEW/PASS per row,
 * which it could do because every record was in memory. `GET /api/v1/runs`
 * returns no decision counts, and deriving them would mean one analytics
 * request per row, so they are deliberately absent rather than invented.
 *
 * Duplicate and Delete are not implemented: both need run lifecycle semantics
 * that no ADR covers yet.
 */
type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }

export function RunsPage({ go }: { go: (path: string) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    listRuns(100, controller.signal)
      .then((r) => setState(r.items.length ? { kind: "ready", runs: r.items } : { kind: "empty" }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: "error", message: apiErrorMessage(error) }) })
    return () => controller.abort()
  }, [reload])

  return <>
    <h1>Processing runs</h1>
    {state.kind === "loading" && <p className="panel">Loading runs…</p>}
    {state.kind === "error" && <section className="panel"><p role="alert" className="notice">{state.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>}
    {state.kind === "empty" && <p className="panel">No persisted runs yet. Process a batch with persistence enabled to see it here.</p>}
    {state.kind === "ready" && <section className="panel">
      <p>{count(state.runs.length)} persisted run{state.runs.length === 1 ? "" : "s"}, newest first. Each run is one supplier file.</p>
      {state.runs.map((run) => <article key={run.execution_id}>
        <b>{run.input_filename}</b>
        <p>
          <Badge>{run.status}</Badge>{" "}
          {count(run.records_total)} records · {count(run.records_successful)} successful · {count(run.records_with_errors)} with errors · {count(run.warnings)} warning(s) · {new Date(run.started_at).toLocaleString()}
        </p>
        <p className="mono"><small>{run.execution_id}</small></p>
        <button onClick={() => go(`/runs/${encodeURIComponent(run.execution_id)}`)}>Open</button>
        <button onClick={() => go(`/catalog?run=${encodeURIComponent(run.execution_id)}`)}>Open in Catalog</button>
      </article>)}
    </section>}
  </>
}
