import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { getRuns } from "../api/runs"
import { ApiError, apiErrorMessage } from "../api/client"
import { StatusBadge } from "../components/StatusBadge"
import type { RunSummaryOut } from "../types"

type RunsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: RunSummaryOut[] }

function formatTimestamp(value: string | null): string {
  if (value === null) return "—"
  return new Date(value).toLocaleString()
}

export function RunsPage() {
  const [state, setState] = useState<RunsState>({ status: "loading" })
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: "loading" })
    getRuns({ signal: controller.signal })
      .then((response) => setState({ status: "ready", items: response.items }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
        setState({ status: "error", message })
      })
    return () => controller.abort()
  }, [reloadToken])

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">AUDIT TRAIL</p>
          <h2>Processing Runs</h2>
          <p>Execution history for catalogs processed with persist enabled.</p>
        </div>
      </div>
      <div className="demo-banner">
        <strong>LIVE API</strong> Only runs uploaded with "Persist this run" enabled appear here.
      </div>
      <section className="panel table-panel">
        {state.status === "loading" && (
          <div className="status" aria-live="polite">
            <p>Loading run history…</p>
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
        {state.status === "ready" && state.items.length === 0 && (
          <div className="status" aria-live="polite">
            <p>No persisted runs yet. Enable "Persist this run" on Upload to build history here.</p>
          </div>
        )}
        {state.status === "ready" && state.items.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Execution ID</th>
                <th>Started at</th>
                <th>Status</th>
                <th>Total records</th>
                <th>Processed</th>
                <th>Successful</th>
                <th>Errors</th>
                <th>Warnings</th>
              </tr>
            </thead>
            <tbody>
              {state.items.map((run) => (
                <tr key={run.execution_id}>
                  <td className="mono">
                    <Link to={`/runs/${encodeURIComponent(run.execution_id)}`}>{run.execution_id}</Link>
                  </td>
                  <td>{formatTimestamp(run.started_at)}</td>
                  <td>
                    <StatusBadge value={run.status} />
                  </td>
                  <td>{run.records_total.toLocaleString()}</td>
                  <td>{run.records_processed.toLocaleString()}</td>
                  <td>{run.records_successful.toLocaleString()}</td>
                  <td>{run.records_with_errors.toLocaleString()}</td>
                  <td>{run.warnings.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
