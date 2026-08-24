import { useEffect, useState } from "react"
import { ClockCounterClockwise } from "@phosphor-icons/react"
import { Link } from "react-router-dom"
import { getRunAnalytics } from "../api/analytics"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRuns } from "../api/runs"
import { AnalyticsChart, ChartTextSummary, type AnalyticsDatum, type ChartType } from "../components/AnalyticsChart"
import { ProvenanceBreakdown } from "../components/ProvenanceBreakdown"
import { StatusBadge } from "../components/StatusBadge"
import type { NumericSummary, RunAnalyticsOut, RunSummaryOut } from "../types"
import { count, money, percent } from "../format"

type RunsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "empty" }
  | { status: "ready"; items: RunSummaryOut[] }

type AnalyticsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; analytics: RunAnalyticsOut }

const DECISION_ORDER = ["BUY", "REVIEW", "PASS", "UNKNOWN"]
const DECISION_COLOR: Record<string, string> = {
  BUY: "var(--success)",
  REVIEW: "var(--warning)",
  PASS: "var(--danger)",
  UNKNOWN: "var(--chart-grid)",
}
const RISK_STATUS_COLOR: Record<string, string> = { PRESENT: "var(--danger)", ABSENT: "var(--chart-grid)", UNKNOWN: "var(--warning)" }
const SEVERITY_ORDER = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
const SEVERITY_COLOR: Record<string, string> = {
  NONE: "var(--chart-grid)",
  LOW: "var(--success)",
  MEDIUM: "var(--warning)",
  HIGH: "var(--danger)",
  CRITICAL: "var(--danger)",
}

function toChartData(counts: Record<string, number>, order: string[] = [], colors: Record<string, string> = {}): AnalyticsDatum[] {
  const keys = [...order.filter((key) => key in counts), ...Object.keys(counts).filter((key) => !order.includes(key))]
  return keys.map((key) => ({ label: key, value: counts[key] ?? 0, color: colors[key] }))
}

function formatCurrency(value: string | null): string {
  if (value === null) return "—"
  const n = Number(value)
  return Number.isFinite(n) ? money(n) : "—"
}

function formatPercent(value: string | null): string {
  if (value === null) return "—"
  const n = Number(value)
  return Number.isFinite(n) ? percent(n, 1) : "—"
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString()
}

function SummaryCards({ title, summary, format }: { title: string; summary: NumericSummary; format: (v: string | null) => string }) {
  return (
    <div className="numeric-summary">
      <p className="eyebrow">{title.toUpperCase()}</p>
      {summary.count === 0 ? (
        <p className="status" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>No usable data (VERIFIED only).</p>
      ) : (
        <dl className="run-summary">
          <dt>Average</dt>
          <dd>{format(summary.average)}</dd>
          <dt>Minimum</dt>
          <dd>{format(summary.minimum)}</dd>
          <dt>Maximum</dt>
          <dd>{format(summary.maximum)}</dd>
          <dt>Count</dt>
          <dd>{count(summary.count)} records</dd>
        </dl>
      )}
    </div>
  )
}

// Internal analytics recovered from canonical snapshot fields. None of these
// need an external provider: brand, issue code, selling price and COG are all
// data JUVAl already imported and persisted.
function BrandPanel({ brands }: { brands: RunAnalyticsOut["brands"] | undefined }) {
  const data = (brands?.items ?? []).map((item) => ({ label: item.label, value: item.count }))
  return (
    <section className="panel analytics-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">BRAND MIX</p>
          <h2>Records per brand</h2>
          <p>Brands as recorded by the supplier file. {brands?.distinct ?? 0} distinct brand{brands?.distinct === 1 ? "" : "s"}; {count(brands?.not_recorded ?? 0)} record{brands?.not_recorded === 1 ? "" : "s"} carry no brand and are counted separately, never merged into one.</p>
        </div>
      </div>
      {data.length === 0 ? (
        <p className="status">No brand was recorded on any record in this run.</p>
      ) : (
        <>
          <AnalyticsChart chartType="bar" data={data} />
          <ChartTextSummary title="Brand distribution" data={data} />
        </>
      )}
    </section>
  )
}

function IssueTypePanel({ issueTypes }: { issueTypes: RunAnalyticsOut["issue_types"] | undefined }) {
  const data = (issueTypes ?? []).slice(0, 10).map((item) => ({ label: item.code, value: item.count }))
  return (
    <section className="panel analytics-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">DATA QUALITY BY TYPE</p>
          <h2>Which issues occurred</h2>
          <p>Grouped by the canonical ProcessingIssue code, so a run's total issue count breaks down into the problems that actually need fixing.</p>
        </div>
      </div>
      {data.length === 0 ? (
        <p className="status">No issue codes are recorded for this run.</p>
      ) : (
        <>
          <AnalyticsChart chartType="bar" data={data} />
          <ChartTextSummary title="Issue types" data={data} />
        </>
      )}
    </section>
  )
}

function PriceSpreadPanel({ spread }: { spread: RunAnalyticsOut["price_spread"] | undefined }) {
  const largest = spread?.largest ?? []
  // Axis labels use record_ref, not title: two records from the same supplier
  // often share a title, and two identically labelled bars are unreadable.
  // The title stays in the text summary, where there is room for it.
  const data = largest.map((entry) => ({ label: entry.record_ref, value: Number(entry.amount) }))
  return (
    <section className="panel analytics-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">SOURCING SPREAD</p>
          <h2>Selling price over cost of goods</h2>
          <p>Gross spread per unit before fees, across the {count(spread?.count ?? 0)} record{spread?.count === 1 ? "" : "s"} with a VERIFIED selling price and a recorded COG. Records without both are excluded, never assumed.</p>
        </div>
      </div>
      {data.length === 0 ? (
        <p className="status">No record in this run has both a VERIFIED selling price and a recorded COG.</p>
      ) : (
        <>
          <dl className="run-summary">
            <dt>Average spread</dt><dd>{formatCurrency(spread?.average_amount ?? null)}</dd>
            <dt>At or below cost</dt><dd>{count(spread?.at_or_below_cog ?? 0)} record{spread?.at_or_below_cog === 1 ? "" : "s"}</dd>
          </dl>
          <AnalyticsChart chartType="bar" data={data} />
          <ul className="chart-text-summary" aria-label="Largest sourcing spreads, as text">
            {largest.map((entry) => (
              <li key={entry.record_ref}>
                <span className="mono">{entry.record_ref}</span>
                {entry.title && <span className="text-muted">{entry.title}</span>}
                <strong>{formatCurrency(entry.amount)}{entry.percent !== null && <em>{` (${(Number(entry.percent) * 100).toFixed(1)}% of price)`}</em>}</strong>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function RiskPanel({ title, risk }: { title: string; risk: RunAnalyticsOut["risks"][string] | undefined }) {
  const statusData = toChartData(risk?.status ?? {}, ["PRESENT", "ABSENT", "UNKNOWN"], RISK_STATUS_COLOR)
  const severityData = toChartData(risk?.severity ?? {}, SEVERITY_ORDER, SEVERITY_COLOR)
  return (
    <div className="risk-panel">
      <p className="eyebrow">{title.toUpperCase()}</p>
      {statusData.length === 0 ? (
        <p className="status" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>No {title.toLowerCase()} data.</p>
      ) : (
        <>
          <AnalyticsChart chartType="bar" data={statusData} height={150} />
          <ChartTextSummary title={`${title} status`} data={statusData} />
          {severityData.length > 0 && (
            <>
              <p className="eyebrow" style={{ marginTop: 10 }}>SEVERITY</p>
              <ChartTextSummary title={`${title} severity`} data={severityData} />
            </>
          )}
        </>
      )}
    </div>
  )
}

export function DashboardPage() {
  const [runsState, setRunsState] = useState<RunsState>({ status: "loading" })
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [analyticsState, setAnalyticsState] = useState<AnalyticsState>({ status: "loading" })
  const [runsReloadToken, setRunsReloadToken] = useState(0)
  const [analyticsReloadToken, setAnalyticsReloadToken] = useState(0)
  const [decisionChartType, setDecisionChartType] = useState<ChartType>("donut")

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
    setAnalyticsState({ status: "loading" })
    getRunAnalytics(selectedRunId, controller.signal)
      .then((analytics) => setAnalyticsState({ status: "ready", analytics }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
        setAnalyticsState({ status: "error", message })
      })
    return () => controller.abort()
  }, [selectedRunId, analyticsReloadToken])

  const selectedRun = runsState.status === "ready" ? runsState.items.find((r) => r.execution_id === selectedRunId) ?? null : null
  const analytics = analyticsState.status === "ready" ? analyticsState.analytics : null
  const decisionData = analytics ? toChartData(analytics.decisions, DECISION_ORDER, DECISION_COLOR) : []

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
                <select aria-label="Select run" value={selectedRunId ?? ""} onChange={(e) => setSelectedRunId(e.target.value)}>
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

          {analyticsState.status === "loading" && (
            <div className="status" aria-live="polite">
              <p>Loading analytics…</p>
            </div>
          )}

          {analyticsState.status === "error" && (
            <div className="status" aria-live="polite">
              <p role="alert" className="error">
                {analyticsState.message}
              </p>
              <button type="button" className="secondary-button" onClick={() => setAnalyticsReloadToken((n) => n + 1)}>
                Retry
              </button>
            </div>
          )}

          {analytics && (
            <>
              {analytics.records.total_records === 0 ? (
                <div className="status" aria-live="polite">
                  <p>This run has no records to analyze.</p>
                </div>
              ) : (
                <>
                  {/* B. Primary KPIs -- headline numbers only. Decision counts live in
                      the Decision Distribution chart below, not duplicated here. */}
                  <section className="metric-grid">
                    <article className="metric-card">
                      <span>Total records</span>
                      <strong>{count(analytics.records.total_records)}</strong>
                      <small>From the analytics endpoint</small>
                    </article>
                    <article className="metric-card">
                      <span>With issues</span>
                      <strong>{count(analytics.data_quality.records_with_issues)}</strong>
                      <small>{count(analytics.data_quality.total_issue_count)} total issues</small>
                    </article>
                    <article className="metric-card">
                      <span>Average ROI</span>
                      <strong>{formatPercent(analytics.profitability.roi.average)}</strong>
                      <small>{count(analytics.profitability.roi.count)} VERIFIED records</small>
                    </article>
                    <article className="metric-card">
                      <span>Average profit</span>
                      <strong>{formatCurrency(analytics.profitability.profit.average)}</strong>
                      <small>{count(analytics.profitability.profit.count)} VERIFIED records</small>
                    </article>
                  </section>

                  {/* C. Decision distribution -- the single place BUY/REVIEW/PASS/UNKNOWN counts live. */}
                  <section className="panel analytics-panel">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">DECISION DISTRIBUTION</p>
                        <h2>How records were decided</h2>
                        <p>From the Decision Engine's own output — never recalculated here.</p>
                      </div>
                      <div className="segmented-control" role="group" aria-label="Decision chart type">
                        <button type="button" className={decisionChartType === "donut" ? "selected" : ""} onClick={() => setDecisionChartType("donut")} aria-pressed={decisionChartType === "donut"}>
                          Donut
                        </button>
                        <button type="button" className={decisionChartType === "bar" ? "selected" : ""} onClick={() => setDecisionChartType("bar")} aria-pressed={decisionChartType === "bar"}>
                          Bars
                        </button>
                      </div>
                    </div>
                    {decisionData.length === 0 ? (
                      <p className="status">No decisions yet.</p>
                    ) : (
                      <>
                        <AnalyticsChart chartType={decisionChartType} data={decisionData} />
                        <ChartTextSummary title="Decision distribution" data={decisionData} />
                      </>
                    )}
                  </section>

                  {/* D. Profitability intelligence */}
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">PROFITABILITY</p>
                        <h2>Backend-computed summaries</h2>
                        <p>Only VERIFIED values participate; INFERRED/NOT_FOUND/INVALID are excluded, never treated as zero.</p>
                      </div>
                    </div>
                    <div className="profitability-grid">
                      <SummaryCards title="Profit" summary={analytics.profitability.profit} format={formatCurrency} />
                      <SummaryCards title="ROI" summary={analytics.profitability.roi} format={formatPercent} />
                      <SummaryCards title="Margin" summary={analytics.profitability.margin} format={formatPercent} />
                    </div>
                  </section>

                  {/* E. Risk intelligence */}
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">RISK OVERVIEW</p>
                        <h2>HazMat / Bulky</h2>
                        <p>Presence and policy-derived severity (ADR-020) — never shown as externally verified.</p>
                      </div>
                    </div>
                    <div className="risk-grid">
                      <RiskPanel title="HazMat" risk={analytics.risks.hazmat} />
                      <RiskPanel title="Bulky" risk={analytics.risks.bulky} />
                    </div>
                  </section>

                  {/* F. Data quality / provenance */}
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <p className="eyebrow">DATA CONFIDENCE</p>
                        <h2>Provenance by field</h2>
                        <p>VERIFIED / INFERRED / NOT_FOUND / INVALID — never collapsed into a single confidence rating (ADR-003/ADR-004).</p>
                      </div>
                    </div>
                    <ProvenanceBreakdown provenance={analytics.provenance} />
                  </section>

                  {/* G. Internal analytics -- supplier/brand/issue intelligence
                      derived from canonical persisted fields, no provider. */}
                  <PriceSpreadPanel spread={analytics.price_spread} />
                  <div className="analytics-duo">
                    <BrandPanel brands={analytics.brands} />
                    <IssueTypePanel issueTypes={analytics.issue_types} />
                  </div>
                </>
              )}
            </>
          )}

          {/* G. Recent runs / actionable items -- reuses the run list already
              fetched for the selector above; no second API call. Excludes the
              run already shown as "Selected Run" above -- otherwise its
              filename would render twice on the same page. */}
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">RECENT RUNS</p>
                <h2>Jump back into another run</h2>
                <p>Newest first. Open a run to see its full record table and download.</p>
              </div>
              <Link to="/runs">View all runs</Link>
            </div>
            {runsState.items.filter((run) => run.execution_id !== selectedRunId).length === 0 ? (
              <p className="status" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>No other persisted runs yet.</p>
            ) : (
            <div className="run-list">
              {runsState.items.filter((run) => run.execution_id !== selectedRunId).slice(0, 6).map((run) => (
                <article key={run.execution_id}>
                  <span className="run-icon" aria-hidden="true">
                    <ClockCounterClockwise size={16} weight="regular" />
                  </span>
                  <div>
                    <Link to={`/runs/${encodeURIComponent(run.execution_id)}`}>{run.input_filename}</Link>
                    <small>{formatTimestamp(run.started_at)} · {count(run.records_total)} records</small>
                  </div>
                  <StatusBadge value={run.status} />
                </article>
              ))}
            </div>
            )}
          </section>
        </>
      )}
    </>
  )
}
