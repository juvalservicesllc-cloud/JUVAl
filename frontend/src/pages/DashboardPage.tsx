import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRunRecords } from "../api/records"
import { getRuns } from "../api/runs"
import { AnalyticsChart } from "../components/AnalyticsChart"
import { StatusBadge } from "../components/StatusBadge"
import { deriveRunAnalytics, type AverageMetric } from "../runAnalytics"
import type { RecordOut, RunSummaryOut } from "../types"

type RunsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "empty" }
  | { status: "ready"; items: RunSummaryOut[] }

type RecordsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; records: RecordOut[] }

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString()
}

function formatPercent(metric: AverageMetric | null): string {
  if (metric === null) return "No usable data"
  return `${(metric.value * 100).toFixed(1)}%`
}

function formatCurrency(metric: AverageMetric | null): string {
  if (metric === null) return "No usable data"
  return metric.value.toLocaleString(undefined, { style: "currency", currency: "USD" })
}

export function DashboardPage() {
  const [runsState, setRunsState] = useState<RunsState>({ status: "loading" })
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [recordsState, setRecordsState] = useState<RecordsState>({ status: "loading" })
  const [runsReloadToken, setRunsReloadToken] = useState(0)
  const [recordsReloadToken, setRecordsReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setRunsState({ status: "loading" })
    getRuns({ limit: 20, signal: controller.signal })
      .then((response) => {
        if (response.items.length === 0) {
          setRunsState({ status: "empty" })
          return
        }
        setRunsState({ status: "ready", items: response.items })
        setSelectedRunId((current) => current ?? response.items[0].execution_id)
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
        setRunsState({ status: "error", message })
      })
    return () => controller.abort()
  }, [runsReloadToken])

  useEffect(() => {
    if (!selectedRunId) return
    const controller = new AbortController()
    setRecordsState({ status: "loading" })
    getRunRecords(selectedRunId, controller.signal)
      .then((response) => setRecordsState({ status: "ready", records: response.records }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
        setRecordsState({ status: "error", message })
      })
    return () => controller.abort()
  }, [selectedRunId, recordsReloadToken])

  const selectedRun = runsState.status === "ready" ? runsState.items.find((r) => r.execution_id === selectedRunId) ?? null : null
  const analytics = recordsState.status === "ready" ? deriveRunAnalytics(recordsState.records) : null

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">RUN ANALYTICS</p>
          <h2>Dashboard</h2>
          <p>What happened in a processing run, and which records deserve attention.</p>
        </div>
        <Link to="/upload" className="primary-button">
          Upload catalog
        </Link>
      </div>

      {runsState.status === "loading" && (
        <div className="status" aria-live="polite">
          <p>Loading runs…</p>
        </div>
      )}

      {runsState.status === "error" && (
        <div className="status" aria-live="polite">
          <p role="alert" className="error">
            {runsState.message}
          </p>
          <button type="button" className="secondary-button" onClick={() => setRunsReloadToken((n) => n + 1)}>
            Retry
          </button>
        </div>
      )}

      {runsState.status === "empty" && (
        <div className="status" aria-live="polite">
          <p>No persisted runs yet. Process a catalog with "Persist this run" enabled on Upload to see analytics here.</p>
        </div>
      )}

      {runsState.status === "ready" && (
        <>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">SELECTED RUN</p>
                <h2>{selectedRun?.input_filename ?? "—"}</h2>
                {selectedRun && <p>Started {formatTimestamp(selectedRun.started_at)}</p>}
              </div>
              <label>
                <span className="eyebrow">Run</span>
                <select
                  aria-label="Select run"
                  value={selectedRunId ?? ""}
                  onChange={(e) => setSelectedRunId(e.target.value)}
                >
                  {runsState.items.map((run) => (
                    <option key={run.execution_id} value={run.execution_id}>
                      {run.input_filename} — {formatTimestamp(run.started_at)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {selectedRun && (
              <dl className="run-summary">
                <dt>Execution ID</dt>
                <dd className="mono">{selectedRun.execution_id}</dd>
                <dt>Status</dt>
                <dd>
                  <StatusBadge value={selectedRun.status} />
                </dd>
                <dt>Finished at</dt>
                <dd>{selectedRun.finished_at ? formatTimestamp(selectedRun.finished_at) : "—"}</dd>
              </dl>
            )}
            {selectedRunId && (
              <Link to={`/runs/${encodeURIComponent(selectedRunId)}`} className="secondary-button">
                Open Run Detail
              </Link>
            )}
          </section>

          {recordsState.status === "loading" && (
            <div className="status" aria-live="polite">
              <p>Loading analytics…</p>
            </div>
          )}

          {recordsState.status === "error" && (
            <div className="status" aria-live="polite">
              <p role="alert" className="error">
                {recordsState.message}
              </p>
              <button type="button" className="secondary-button" onClick={() => setRecordsReloadToken((n) => n + 1)}>
                Retry
              </button>
            </div>
          )}

          {recordsState.status === "ready" && analytics && (
            <>
              <section className="metric-grid">
                <article className="metric-card">
                  <span>Total records</span>
                  <strong>{selectedRun?.records_total.toLocaleString() ?? recordsState.records.length}</strong>
                  <small>From the run summary</small>
                </article>
                <article className="metric-card">
                  <span>Successful</span>
                  <strong>{selectedRun?.records_successful.toLocaleString() ?? "—"}</strong>
                  <small>Processed without a data error</small>
                </article>
                <article className="metric-card">
                  <span>With errors</span>
                  <strong>{selectedRun?.records_with_errors.toLocaleString() ?? "—"}</strong>
                  <small>Processed with a data error</small>
                </article>
                <article className="metric-card">
                  <span>With issues</span>
                  <strong>{analytics.recordsWithIssuesCount.toLocaleString()}</strong>
                  <small>issue_count &gt; 0, any severity</small>
                </article>
              </section>

              <section className="panel analytics-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">DECISION DISTRIBUTION</p>
                    <h2>How records were decided</h2>
                    <p>From the Decision Engine's own output -- never recalculated here.</p>
                  </div>
                </div>
                <AnalyticsChart
                  chartType="bar"
                  data={[
                    { label: "BUY", value: analytics.decisionCounts.BUY, color: "var(--success)" },
                    { label: "REVIEW", value: analytics.decisionCounts.REVIEW, color: "var(--warning)" },
                    { label: "PASS", value: analytics.decisionCounts.PASS, color: "var(--danger)" },
                    { label: "UNKNOWN", value: analytics.decisionCounts.UNKNOWN, color: "var(--chart-grid)" },
                  ]}
                />
              </section>

              <section className="panel analytics-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">RISK OVERVIEW</p>
                    <h2>HazMat / Bulky presence</h2>
                    <p>Presence only (ADR-020) -- severity is policy-derived, never shown as externally verified.</p>
                  </div>
                </div>
                <AnalyticsChart
                  chartType="bar"
                  data={[
                    { label: "HAZMAT present", value: analytics.hazmatPresentCount, color: "var(--danger)" },
                    { label: "BULKY present", value: analytics.bulkyPresentCount, color: "var(--warning)" },
                    { label: "Neither flag", value: analytics.neitherRiskFlagCount, color: "var(--chart-grid)" },
                  ]}
                />
              </section>

              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">PROFITABILITY</p>
                    <h2>Averages over usable values</h2>
                    <p>NOT_FOUND/INVALID records are excluded, never treated as zero.</p>
                  </div>
                </div>
                <dl className="run-summary">
                  <dt>Average ROI</dt>
                  <dd>
                    {formatPercent(analytics.averageRoi)}
                    {analytics.averageRoi && ` · ${analytics.averageRoi.sampleSize} records`}
                  </dd>
                  <dt>Average profit</dt>
                  <dd>
                    {formatCurrency(analytics.averageProfit)}
                    {analytics.averageProfit && ` · ${analytics.averageProfit.sampleSize} records`}
                  </dd>
                  <dt>Average margin</dt>
                  <dd>
                    {formatPercent(analytics.averageMargin)}
                    {analytics.averageMargin && ` · ${analytics.averageMargin.sampleSize} records`}
                  </dd>
                </dl>
              </section>
            </>
          )}
        </>
      )}
    </>
  )
}
