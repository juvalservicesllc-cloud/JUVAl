import { useEffect, useState } from "react"
import { CaretDown, CaretUp } from "@phosphor-icons/react"
import { Link } from "react-router-dom"
import { getRuns } from "../api/runs"
import { ApiError, apiErrorMessage } from "../api/client"
import { StatusBadge } from "../components/StatusBadge"
import type { RunSummaryOut } from "../types"

type RunsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: RunSummaryOut[] }

type SortKey = "execution_id" | "input_filename" | "started_at" | "status" | "records_total" | "records_processed" | "records_successful" | "records_with_errors" | "warnings"
type SortDirection = "asc" | "desc"

const SORT_LABEL: Record<SortKey, string> = {
  execution_id: "Execution ID", input_filename: "Input file", started_at: "Started at", status: "Status", records_total: "Total records",
  records_processed: "Processed", records_successful: "Successful", records_with_errors: "Errors", warnings: "Warnings",
}
// Client-side only: getRuns() already returns its whole (already-capped)
// page in one call, so sorting the in-memory list is not a second fetch
// and not a re-derivation of anything the backend computed -- it is pure
// presentation ordering over already-correct data.
const DEFAULT_DIRECTION: Record<SortKey, SortDirection> = {
  execution_id: "asc", input_filename: "asc", started_at: "desc", status: "asc",
  records_total: "desc", records_processed: "desc", records_successful: "desc", records_with_errors: "desc", warnings: "desc",
}

function formatTimestamp(value: string | null): string {
  if (value === null) return "—"
  return new Date(value).toLocaleString()
}

function sortRuns(items: RunSummaryOut[], key: SortKey, direction: SortDirection): RunSummaryOut[] {
  const sorted = [...items].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (typeof av === "number" && typeof bv === "number") return av - bv
    return String(av).localeCompare(String(bv))
  })
  return direction === "asc" ? sorted : sorted.reverse()
}

export function RunsPage() {
  const [state, setState] = useState<RunsState>({ status: "loading" })
  const [reloadToken, setReloadToken] = useState(0)
  const [sort, setSort] = useState<SortKey>("started_at")
  const [direction, setDirection] = useState<SortDirection>("desc")

  function changeSort(key: SortKey) {
    if (sort === key) {
      setDirection((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSort(key)
      setDirection(DEFAULT_DIRECTION[key])
    }
  }

  function sortButton(key: SortKey) {
    const active = sort === key
    return (
      <button type="button" onClick={() => changeSort(key)} aria-pressed={active}>
        {SORT_LABEL[key]}
        {active && (direction === "asc" ? <CaretUp size={11} weight="bold" aria-hidden="true" /> : <CaretDown size={11} weight="bold" aria-hidden="true" />)}
      </button>
    )
  }

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
                <th>{sortButton("execution_id")}</th>
                <th>{sortButton("input_filename")}</th>
                <th>{sortButton("started_at")}</th>
                <th>{sortButton("status")}</th>
                <th>{sortButton("records_total")}</th>
                <th>{sortButton("records_processed")}</th>
                <th>{sortButton("records_successful")}</th>
                <th>{sortButton("records_with_errors")}</th>
                <th>{sortButton("warnings")}</th>
              </tr>
            </thead>
            <tbody>
              {sortRuns(state.items, sort, direction).map((run) => (
                <tr key={run.execution_id}>
                  <td className="mono">
                    <Link to={`/runs/${encodeURIComponent(run.execution_id)}`}>{run.execution_id}</Link>
                  </td>
                  <td>{run.input_filename}</td>
                  <td>{formatTimestamp(run.started_at)}</td>
                  <td>
                    <StatusBadge value={run.status} />
                  </td>
                  <td className="numeric-cell">{run.records_total.toLocaleString()}</td>
                  <td className="numeric-cell">{run.records_processed.toLocaleString()}</td>
                  <td className="numeric-cell">{run.records_successful.toLocaleString()}</td>
                  <td className="numeric-cell">{run.records_with_errors.toLocaleString()}</td>
                  <td className="numeric-cell">{run.warnings.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
