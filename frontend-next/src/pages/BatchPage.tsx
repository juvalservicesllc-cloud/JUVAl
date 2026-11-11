import { useEffect, useState } from "react"
import { getRunAnalytics } from "../api/analytics"
import { getBatch } from "../api/batches"
import { ApiError, apiErrorMessage, canRetryApiError } from "../api/client"
import type { BatchResponse, RunAnalyticsOut } from "../api/types"
import { count, fieldMoney, fieldPercent } from "../format"
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
type State = { kind: "loading" } | { kind: "error"; message: string; retryable: boolean } | { kind: "ready"; batch: BatchResponse }
type FileAnalytics = { kind: "loading" } | { kind: "missing" } | { kind: "error" } | { kind: "ready"; analytics: RunAnalyticsOut }

/**
 * Golden's multi-source analytics table, rebuilt from each child run's own
 * `GET /analytics` (at most ten files, so at most ten requests). One row per
 * file, side by side; nothing is summed across files and no record is matched
 * between them -- that would be Compare, which needs an identity ADR.
 */
function PerFileAnalytics({ batch }: { batch: BatchResponse }) {
  const [rows, setRows] = useState<Record<string, FileAnalytics>>({})

  useEffect(() => {
    const controller = new AbortController()
    const ids = batch.files.flatMap((file) => file.execution_id ? [file.execution_id] : [])
    setRows(Object.fromEntries(ids.map((id) => [id, { kind: "loading" } as FileAnalytics])))
    for (const id of ids) {
      getRunAnalytics(id, controller.signal)
        .then((analytics) => setRows((current) => ({ ...current, [id]: { kind: "ready", analytics } })))
        .catch((error: unknown) => {
          if (controller.signal.aborted) return
          const kind = error instanceof ApiError && error.status === 404 ? "missing" : "error"
          setRows((current) => ({ ...current, [id]: { kind } }))
        })
    }
    return () => controller.abort()
  }, [batch])

  return <section className="panel">
    <h2>Per-file analytics</h2>
    <p>Each file is its own run, summarised by the backend. Profit, ROI and the profit-status columns count VERIFIED values only where stated; files are shown side by side, never merged.</p>
    <div className="table"><table aria-label="Per-file analytics">
      <thead><tr><th>File</th><th>Records</th><th>BUY</th><th>REVIEW</th><th>PASS</th><th>Avg profit (verified)</th><th>Avg ROI (verified)</th><th>With issues</th><th>Profit inferred</th><th>Profit not found / invalid</th></tr></thead>
      <tbody>{batch.files.map((file) => {
        const row = file.execution_id ? rows[file.execution_id] ?? { kind: "loading" } : null
        const cells = (text: string) => <td colSpan={9} className="local-note">{text}</td>
        return <tr key={file.ordinal}>
          <td>{file.execution_id ? <a href={`/?run=${encodeURIComponent(file.execution_id)}`}>{file.filename}</a> : file.filename}</td>
          {row === null ? cells("Never ran — no analytics")
            : row.kind === "loading" ? cells("Loading…")
            : row.kind === "missing" ? cells("Not stored — analytics exist only for persisted runs")
            : row.kind === "error" ? cells("Analytics could not be loaded for this file")
            : (() => {
              const a = row.analytics
              const profit = a.provenance.profit ?? {}
              return <>
                <td>{count(a.records.total_records)}</td>
                {(["BUY", "REVIEW", "PASS"] as const).map((d) => <td key={d}>{count(a.decisions[d] ?? 0)}</td>)}
                <td>{fieldMoney(a.profitability.profit.average)} <small>({count(a.profitability.profit.count)})</small></td>
                <td>{fieldPercent(a.profitability.roi.average)} <small>({count(a.profitability.roi.count)})</small></td>
                <td>{count(a.data_quality.records_with_issues)}</td>
                <td>{count(profit.INFERRED ?? 0)}</td>
                <td>{count((profit.NOT_FOUND ?? 0) + (profit.INVALID ?? 0))}</td>
              </>
            })()}
        </tr>
      })}</tbody>
    </table></div>
    <p className="local-note">The number in brackets is how many records the average covers. Profit with no status recorded is in neither status column.</p>
  </section>
}

export function BatchPage({ batchId, go }: { batchId: string; go: (path: string) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    getBatch(batchId, controller.signal)
      .then((batch) => setState({ kind: "ready", batch }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setState({ kind: "error", message: apiErrorMessage(error), retryable: canRetryApiError(error) }) })
    return () => controller.abort()
  }, [batchId, reload])

  if (state.kind === "loading") return <section className="panel"><h1>Batch</h1><p>Loading batch…</p></section>
  if (state.kind === "error") return <section className="panel"><h1>Batch</h1><p role="alert" className="notice">{state.message}</p>{state.retryable && <button onClick={() => setReload((n) => n + 1)}>Retry</button>}</section>

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
    <div className="table"><table aria-label="Included files">
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

    {batch.persisted && <PerFileAnalytics batch={batch} />}

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
