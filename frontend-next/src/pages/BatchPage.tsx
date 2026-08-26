import { useEffect, useState } from "react"
import { getBatch } from "../api/batches"
import { apiErrorMessage } from "../api/client"
import type { BatchResponse } from "../api/types"
import { Badge } from "./shared"

/**
 * Batch detail — a production resource Golden never had.
 *
 * Golden modelled one run holding many files. Production creates one
 * ExecutionRun *per file* and groups them under a batch, which keeps per-file
 * provenance and makes each file independently auditable. That is the stronger
 * model, so it wins; what it borrows from Golden is the presentation — a
 * compact included-files table with per-file status and a drill-down.
 *
 * A REJECTED file never ran: it has no execution_id and its counts stay 0,
 * which is "never processed", not a measured zero.
 */
type State = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; batch: BatchResponse }

export function BatchPage({ batchId, go }: { batchId: string; go: (path: string) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    getBatch(batchId, controller.signal)
      .then((batch) => setState({ kind: "ready", batch }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: "error", message: apiErrorMessage(error) }) })
    return () => controller.abort()
  }, [batchId, reload])

  if (state.kind === "loading") return <section className="panel"><h1>Batch</h1><p>Loading batch…</p></section>
  if (state.kind === "error") return <section className="panel"><h1>Batch</h1><p role="alert" className="notice">{state.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>

  const { batch } = state
  return <>
    <h1>Batch summary</h1>
    <section className="panel">
      <p><Badge>{batch.status}</Badge> · <span className="mono">{batch.batch_id}</span> · {new Date(batch.created_at).toLocaleString()}</p>
      <div className="kpis">
        <article><small>Files</small><strong>{batch.total_files}</strong></article>
        <article><small>Succeeded</small><strong>{batch.succeeded_files}</strong></article>
        <article><small>Failed</small><strong>{batch.failed_files}</strong></article>
        <article><small>Records</small><strong>{batch.records_total}</strong></article>
        <article><small>With errors</small><strong>{batch.records_with_errors}</strong></article>
        <article><small>Warnings</small><strong>{batch.warning_count}</strong></article>
      </div>
      {!batch.persisted && <p className="notice">This batch was not persisted, so its runs do not appear in Runs or Catalog.</p>}
    </section>

    <h2>Included files</h2>
    <div className="table"><table>
      <thead><tr><th>#</th><th>File</th><th>Status</th><th>Records</th><th>With errors</th><th>Notes</th><th>Run</th></tr></thead>
      <tbody>
        {batch.files.map((file) => <tr key={file.ordinal}>
          <td>{file.ordinal + 1}</td>
          <td>{file.filename}</td>
          <td><Badge>{file.status}</Badge></td>
          <td>{file.status === "REJECTED" ? "—" : file.records_total}</td>
          <td>{file.status === "REJECTED" ? "—" : file.records_with_errors}</td>
          <td>{[...file.errors, ...file.warnings].join(" · ") || "—"}</td>
          <td>{file.execution_id
            ? <a href={`/runs/${encodeURIComponent(file.execution_id)}`}>Open run</a>
            : <small>never ran</small>}</td>
        </tr>)}
      </tbody>
    </table></div>

    {batch.failed_files > 0 && <section className="panel">
      <h2>Retrying a failed file</h2>
      {/* Retry is a new submission by design: a batch and its child runs are an
          immutable record of what happened, so a rejected file is fixed and
          submitted again as a new batch rather than mutated in place. */}
      <p>Fix the file and submit it again from Import. A batch and its runs are an immutable record of what was processed, so retrying creates a new batch rather than changing this one.</p>
      <button onClick={() => go("/import")}>Back to Import</button>
    </section>}

    <p><button onClick={() => go("/runs")}>All runs</button></p>
  </>
}
