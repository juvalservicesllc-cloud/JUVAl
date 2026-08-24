import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { getBatch } from "../api/batches"
import { ApiError, apiErrorMessage } from "../api/client"
import { BatchSummary } from "../components/BatchSummary"
import { StatusBadge } from "../components/StatusBadge"
import type { BatchResponse } from "../types"

type State =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error"; message: string }
  | { status: "ready"; batch: BatchResponse }

export function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>()
  const [state, setState] = useState<State>({ status: "loading" })
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!batchId) return
    const controller = new AbortController()
    setState({ status: "loading" })
    getBatch(batchId, controller.signal)
      .then((batch) => setState({ status: "ready", batch }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) return setState({ status: "not-found" })
        setState({ status: "error", message: error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error) })
      })
    return () => controller.abort()
  }, [batchId, reloadToken])

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">BATCH DETAIL</p>
          <h2 className="mono">{batchId ?? "Unknown batch"}</h2>
          <p>One multi-file submission and the independent runs it produced. A batch groups child runs; it never merges their records.</p>
        </div>
        <Link to="/runs" className="secondary-button">All runs</Link>
      </div>

      {state.status === "loading" && <div className="status" aria-live="polite"><p>Loading batch…</p></div>}

      {state.status === "not-found" && (
        <div className="status" aria-live="polite">
          <p role="alert" className="error">No persisted batch found for this ID.</p>
          <p className="text-muted">A batch is only reviewable here when it was submitted with persistence enabled.</p>
        </div>
      )}

      {state.status === "error" && (
        <div className="status" aria-live="polite">
          <p role="alert" className="error">{state.message}</p>
          <button type="button" className="secondary-button" onClick={() => setReloadToken((n) => n + 1)}>Retry</button>
        </div>
      )}

      {state.status === "ready" && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">BATCH OUTCOME</p>
              <h2><StatusBadge value={state.batch.status} /></h2>
              <p>{state.batch.succeeded_files} of {state.batch.total_files} files produced a child run.</p>
            </div>
          </div>
          <BatchSummary batch={state.batch} />
        </section>
      )}
    </>
  )
}
