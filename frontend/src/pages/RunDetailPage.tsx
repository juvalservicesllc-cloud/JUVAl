import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { downloadUrl } from "../api"
import { getRunAnalytics } from "../api/analytics"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRunRecords } from "../api/records"
import { getRun } from "../api/runs"
import { ResultsTable } from "../components/ResultsTable"
import { StatusBadge } from "../components/StatusBadge"
import type { RecordOut, RunAnalyticsOut, RunSummaryOut } from "../types"

type DetailState =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error"; message: string }
  | { status: "ready"; run: RunSummaryOut; records: RecordOut[]; analytics: RunAnalyticsOut }

function formatTimestamp(value: string | null): string {
  if (value === null) return "—"
  return new Date(value).toLocaleString()
}

export function RunDetailPage() {
  const { executionId } = useParams<{ executionId: string }>()
  const [state, setState] = useState<DetailState>({ status: "loading" })
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!executionId) return
    const controller = new AbortController()
    setState({ status: "loading" })
    Promise.all([getRun(executionId, controller.signal), getRunRecords(executionId, { limit: 100 }, controller.signal), getRunAnalytics(executionId, controller.signal)])
      .then(([run, recordsResponse, analytics]) => setState({ status: "ready", run, records: recordsResponse.records, analytics }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "not-found" })
          return
        }
        const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
        setState({ status: "error", message })
      })
    return () => controller.abort()
  }, [executionId, reloadToken])

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">RUN DETAIL</p>
          <h2>{executionId ?? "Unknown run"}</h2>
          <p>Metadata, records, and download for one processing run.</p>
        </div>
      </div>

      {state.status === "loading" && (
        <div className="status" aria-live="polite">
          <p>Loading run…</p>
        </div>
      )}

      {state.status === "not-found" && (
        <div className="status" aria-live="polite">
          <p role="alert" className="error">
            No run found for this execution ID.
          </p>
        </div>
      )}

      {state.status === "error" && (
        <div className="status" aria-live="polite">
          <p role="alert" className="error">
            {state.message}
          </p>
          <button type="button" className="secondary-button" onClick={() => setReloadToken((n) => n + 1)}>
            Retry
          </button>
        </div>
      )}

      {state.status === "ready" && (
        <>
          <section className="panel upload-panel">
            <div className="result-heading">
              <div>
                <p className="eyebrow">RUN SUMMARY</p>
                <h2>
                  <StatusBadge value={state.run.status} />
                </h2>
                <p>{state.run.status === "PARTIAL_SUCCESS" ? "Processing completed with records or warnings that require review." : "Processing completed with the recorded run outcome below."}</p>
              </div>
              {executionId && (
                <a href={downloadUrl(executionId)} download className="primary-button">
                  Download results
                </a>
              )}
            </div>
            <dl className="run-summary">
              <dt>Execution ID</dt>
              <dd className="mono">{state.run.execution_id}</dd>
              <dt>Input file</dt>
              <dd>{state.run.input_filename}</dd>
              <dt>Started at</dt>
              <dd>{formatTimestamp(state.run.started_at)}</dd>
              <dt>Finished at</dt>
              <dd>{formatTimestamp(state.run.finished_at)}</dd>
              <dt>Total records</dt>
              <dd>{state.run.records_total}</dd>
              <dt>Processed</dt>
              <dd>{state.run.records_processed}</dd>
              <dt>Successful</dt>
              <dd>{state.run.records_successful}</dd>
              <dt>Errors</dt>
              <dd>{state.run.records_with_errors}</dd>
              <dt>Warnings</dt>
              <dd>{state.run.warnings}</dd>
            </dl>
          </section>
          <section className="metric-grid run-metrics" aria-label="Run totals">
            <article className="metric-card"><span>Total records</span><strong>{state.run.records_total}</strong><small>Submitted in this run</small></article>
            <article className="metric-card"><span>Processed</span><strong>{state.run.records_processed}</strong><small>{state.run.records_successful} successful</small></article>
            <article className="metric-card"><span>Records with errors</span><strong>{state.run.records_with_errors}</strong><small>Require record-level review</small></article>
            <article className="metric-card"><span>Warnings</span><strong>{state.run.warnings}</strong><small>Reported by processing</small></article>
          </section>
          <section className="panel run-outcomes">
            <div className="panel-heading"><div><p className="eyebrow">DECISION OUTCOMES</p><h2>Canonical run totals</h2><p>Aggregated by the backend across the persisted run; not calculated from this page of records.</p></div></div>
            <dl className="decision-summary">
              {(["BUY", "REVIEW", "PASS"] as const).map((decision) => <div key={decision}><dt><StatusBadge value={decision} /></dt><dd>{state.analytics.decisions[decision] ?? 0}</dd></div>)}
            </dl>
          </section>
          <section className="panel table-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">RECORDS</p>
                <h2>Processed records</h2>
                <p>Run-scoped snapshot -- identity is (execution_id, record_ref), never a global product ID. This review shows the first persisted page only; Catalog expansion belongs to M2.</p>
              </div>
            </div>
            <ResultsTable records={state.records} executionId={executionId} />
          </section>
          <section className="panel run-next-action">
            <p className="eyebrow">NEXT ACTION</p>
            <h2>Continue in Catalog</h2>
            <p>Use Catalog to continue working with the run-scoped records. Its structural migration remains M2.</p>
            <Link to="/products" className="secondary-button">Open Catalog</Link>
          </section>
        </>
      )}
    </>
  )
}
