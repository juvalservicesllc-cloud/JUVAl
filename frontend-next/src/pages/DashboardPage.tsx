import { useEffect, useState } from "react"
import { getRunAnalytics } from "../api/analytics"
import { getRunBatch } from "../api/batches"
import { getRuns } from "../api/catalog"
import { apiErrorMessage } from "../api/client"
import type { BatchResponse, NumericSummaryOut, RunAnalyticsOut, RunSummaryOut } from "../api/types"
import { count, fieldMoney, fieldPercent } from "../format"
import { Badge, ProvenanceBadge } from "./shared"

/**
 * Dashboard — one persisted run, summarised by the backend (ADR-030 migration
 * of Golden's dashboard onto `GET /analytics`).
 *
 * Every figure is a backend aggregate: profit/ROI/margin summaries count
 * VERIFIED values only, so each says how many records it covers. File counts
 * are batch facts and appear only when the run belongs to a batch. No Decision
 * Score, ranking or market data — none has an approved contract.
 */
type RunsState = { kind: "loading" } | { kind: "error"; message: string } | { kind: "empty" } | { kind: "ready"; runs: RunSummaryOut[] }
type DataState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; analytics: RunAnalyticsOut; batch: BatchResponse | null; batchUnavailable: boolean }

const STATUSES = ["VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"] as const
const FIELD_LABELS: Record<string, string> = { asin: "ASIN", weight: "Weight", selling_price: "Selling price", profit: "Profit", roi: "ROI", margin: "Margin" }

const covered = (summary: NumericSummaryOut, total: number) => `${count(summary.count)} of ${count(total)} records, verified only`

/** Text first, bar second: the number is the content, the bar a visual aid. */
function Bars({ label, counts, order }: { label: string; counts: Record<string, number>; order?: string[] }) {
  const keys = order ? [...order, ...Object.keys(counts).filter((k) => !order.includes(k))] : Object.keys(counts)
  const total = Object.values(counts).reduce((n, v) => n + v, 0)
  return <ul className="bars" aria-label={label}>
    {keys.filter((k) => counts[k] !== undefined).map((key) => <li key={key}>
      <span>{key}</span><strong>{count(counts[key])}</strong>
      <span className="bar" aria-hidden="true"><span style={{ width: total ? `${(counts[key] / total) * 100}%` : 0 }} /></span>
    </li>)}
  </ul>
}

function DecisionChart({ counts }: { counts: Record<string, number> }) {
  const [type, setType] = useState("bars")
  const keys = ["BUY", "REVIEW", "PASS", ...Object.keys(counts).filter((key) => !["BUY", "REVIEW", "PASS"].includes(key))]
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0)
  let offset = 0
  return <>
    <div className="chart-controls" role="group" aria-label="Decision chart type">
      <button aria-pressed={type === "donut"} onClick={() => setType("donut")}>Donut</button>
      <button aria-pressed={type === "bars"} onClick={() => setType("bars")}>Bars</button>
    </div>
    {type === "bars" ? <Bars label="Decision distribution" counts={counts} order={["BUY", "REVIEW", "PASS"]} /> :
      <figure className="donut-chart" aria-label="Decision distribution">
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle cx="60" cy="60" r="44" fill="none" stroke="var(--surface-2)" strokeWidth="18" />
          {keys.map((key) => {
            const fraction = total ? (counts[key] ?? 0) / total * 100 : 0
            const start = offset
            offset += fraction
            return <circle key={key} cx="60" cy="60" r="44" fill="none" pathLength="100" strokeWidth="18"
              stroke={`var(--${key === "BUY" ? "success" : key === "REVIEW" ? "warning" : key === "PASS" ? "danger" : "muted"})`}
              strokeDasharray={`${fraction} ${100 - fraction}`} strokeDashoffset={-start} transform="rotate(-90 60 60)" />
          })}
        </svg>
        <figcaption>{total === 0 && <p>No decisions recorded.</p>}<ul>{keys.map((key) => <li key={key}>{key}: {count(counts[key] ?? 0)}</li>)}</ul></figcaption>
      </figure>}
  </>
}

export function DashboardPage({ initialRunId = "", go }: { initialRunId?: string; go: (path: string) => void }) {
  const [runs, setRuns] = useState<RunsState>({ kind: "loading" })
  const [runId, setRunId] = useState(initialRunId)
  const [data, setData] = useState<DataState>({ kind: "loading" })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setRuns({ kind: "loading" })
    getRuns(controller.signal)
      .then(({ items }) => {
        if (!items.length) return setRuns({ kind: "empty" })
        setRuns({ kind: "ready", runs: items })
        setRunId((current) => current || items[0].execution_id)
      })
      .catch((error: unknown) => { if (!controller.signal.aborted) setRuns({ kind: "error", message: apiErrorMessage(error) }) })
    return () => controller.abort()
  }, [reload])

  useEffect(() => {
    if (!runId) return
    const controller = new AbortController()
    setData({ kind: "loading" })
    Promise.all([
      getRunAnalytics(runId, controller.signal),
      // The batch only adds file counts; its failure must not hide the run.
      getRunBatch(runId, controller.signal).then((batch) => ({ batch, unavailable: false }), () => ({ batch: null, unavailable: true })),
    ])
      .then(([analytics, { batch, unavailable }]) => setData({ kind: "ready", analytics, batch, batchUnavailable: unavailable }))
      .catch((error: unknown) => { if (!controller.signal.aborted) setData({ kind: "error", message: apiErrorMessage(error) }) })
    return () => controller.abort()
  }, [runId, reload])

  if (runs.kind === "loading") return <section className="panel"><h1>Dashboard</h1><p aria-live="polite">Loading runs…</p></section>
  if (runs.kind === "error") return <section className="panel"><h1>Dashboard</h1><p role="alert" className="notice">{runs.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>
  if (runs.kind === "empty") return <section className="panel">
    <h1>Dashboard</h1>
    <p>No persisted runs yet. Import a supplier file with "Persist" on to see its analysis here.</p>
    <button onClick={() => go("/import")}>Import a file</button>
  </section>

  const run = runs.runs.find((r) => r.execution_id === runId)
  return <>
    <h1>Dashboard</h1>
    <section className="panel">
      <label className="run-selector">Run <select aria-label="Run" value={runId} onChange={(e) => setRunId(e.target.value)}>
        {runs.runs.map((r) => <option key={r.execution_id} value={r.execution_id}>{r.input_filename} — {new Date(r.started_at).toLocaleString()}</option>)}
      </select></label>{" "}
      <button onClick={() => go(`/catalog?run=${encodeURIComponent(runId)}`)}>Open in Catalog</button>{" "}
      <button onClick={() => go(`/runs/${encodeURIComponent(runId)}`)}>Run detail</button>
      {run && <p className="local-note"><Badge>{run.status}</Badge> {run.input_filename}</p>}
    </section>

    {data.kind === "loading" && <section className="panel"><p aria-live="polite">Loading analytics…</p></section>}
    {data.kind === "error" && <section className="panel"><p role="alert" className="notice">{data.message}</p><button onClick={() => setReload((n) => n + 1)}>Retry</button></section>}
    {data.kind === "ready" && <Analytics {...data} go={go} runId={runId} />}
    <section className="panel" aria-label="Recent runs">
      <h2>Recent runs</h2>
      <p>The six most recent runs in the loaded history (up to 100).</p>
      <ul>{runs.runs.slice(0, 6).map((recent) => <li key={recent.execution_id}>
        <a href={`/runs/${encodeURIComponent(recent.execution_id)}`}>{recent.input_filename}</a>{" "}
        <Badge>{recent.status}</Badge> · {new Date(recent.started_at).toLocaleString()}
      </li>)}</ul>
    </section>
  </>
}

function Analytics({ analytics: a, batch, batchUnavailable, go, runId }: { analytics: RunAnalyticsOut; batch: BatchResponse | null; batchUnavailable: boolean; go: (path: string) => void; runId: string }) {
  const total = a.records.total_records
  const p = a.profitability
  return <>
    <section className="panel" aria-label="Key figures">
      <h2>Key figures</h2>
      <div className="kpis">
        {batch && <>
          <article><small>Files in batch</small><strong>{count(batch.total_files)}</strong></article>
          <article><small>Processed files</small><strong>{count(batch.succeeded_files)}</strong></article>
          <article><small>Failed or rejected files</small><strong>{count(batch.failed_files)}</strong></article>
        </>}
        <article><small>Records</small><strong>{count(total)}</strong></article>
        {(["BUY", "REVIEW", "PASS"] as const).map((d) => <article key={d}><small><Badge>{d}</Badge></small><strong>{count(a.decisions[d] ?? 0)}</strong></article>)}
        <article><small>Records with issues</small><strong>{count(a.data_quality.records_with_issues)}</strong></article>
        <article><small>Issues</small><strong>{count(a.data_quality.total_issue_count)}</strong></article>
        <article><small>Sum of verified unit profit</small><strong>{fieldMoney(p.profit.sum)}</strong><small>{covered(p.profit, total)}; one unit per record, not a sales forecast</small></article>
        <article><small>Average profit</small><strong>{fieldMoney(p.profit.average)}</strong><small>{covered(p.profit, total)}</small></article>
        <article><small>Average ROI</small><strong>{fieldPercent(p.roi.average)}</strong><small>{covered(p.roi, total)}</small></article>
        <article><small>Average margin</small><strong>{fieldPercent(p.margin.average)}</strong><small>{covered(p.margin, total)}</small></article>
      </div>
      {!batch && <p className="local-note">{batchUnavailable ? "This run's batch could not be loaded, so file counts are not shown." : "This run was submitted on its own: one run is one file, so there are no batch file counts."}</p>}
      {(a.decisions.UNKNOWN ?? 0) > 0 && <p className="local-note">{count(a.decisions.UNKNOWN)} records have no decision.</p>}
      <p className="local-note">Profit, ROI and margin figures include VERIFIED values only; inferred, not-found and invalid values are excluded, never counted as zero.</p>
    </section>

    <section className="panel" aria-label="Pending demand verification">
      <h2>REVIEW — pending demand verification</h2>
      {a.review_classification ? <>
        <p><strong>{count(a.review_classification.pending_demand_verification)}</strong> of {count(a.decisions.REVIEW ?? 0)} REVIEW records are held back only because demand could not be determined. Their decision stays REVIEW; demand has not been verified, so they are not BUY.</p>
        {a.review_classification.review_not_classifiable > 0 && <p className="local-note">{count(a.review_classification.review_not_classifiable)} REVIEW records were processed before reason codes were stored and cannot be classified.</p>}
        <button disabled={a.review_classification.pending_demand_verification === 0} onClick={() => go(`/catalog?run=${encodeURIComponent(runId)}&review=pending-demand`)}>Show them in Catalog</button>
      </> : <p className="local-note">Not available from this API version.</p>}
    </section>

    <section className="panel">
      <h2>Decisions</h2>
      <DecisionChart counts={a.decisions} />
    </section>

    <section className="panel">
      <h2>Profitability</h2>
      <div className="table"><table aria-label="Profitability summary">
        <thead><tr><th>Metric</th><th>Records</th><th>Average</th><th>Minimum</th><th>Maximum</th></tr></thead>
        <tbody>{(["profit", "roi", "margin"] as const).map((metric) => {
          const f = metric === "profit" ? fieldMoney : fieldPercent
          return <tr key={metric}><td>{FIELD_LABELS[metric]}</td><td>{count(p[metric].count)}</td><td>{f(p[metric].average)}</td><td>{f(p[metric].minimum)}</td><td>{f(p[metric].maximum)}</td></tr>
        })}</tbody>
      </table></div>
    </section>

    <section className="panel">
      <h2>Risk</h2>
      <div className="grid">
        {(["hazmat", "bulky"] as const).map((risk) => <article key={risk}>
          <small>{risk === "hazmat" ? "HazMat" : "Bulky"} — status</small>
          <Bars label={`${risk === "hazmat" ? "HazMat" : "Bulky"} status`} counts={a.risks[risk]?.status ?? {}} />
          <small>Severity (risk policy, ADR-020)</small>
          <Bars label={`${risk === "hazmat" ? "HazMat" : "Bulky"} severity`} counts={a.risks[risk]?.severity ?? {}} />
        </article>)}
      </div>
    </section>

    <section className="panel">
      <h2>Provenance</h2>
      <div className="grid">{Object.entries(a.provenance).map(([field, counts]) => <article key={field}><h3>{FIELD_LABELS[field] ?? field}</h3><Bars label={`${FIELD_LABELS[field] ?? field} verification distribution`} counts={counts} /></article>)}</div>
      <div className="table"><table aria-label="Provenance by field">
        <thead><tr><th>Field</th>{STATUSES.map((s) => <th key={s}><ProvenanceBadge status={s} /> {s.replace("_", " ")}</th>)}<th>Not recorded</th></tr></thead>
        <tbody>{Object.entries(a.provenance).map(([field, counts]) => <tr key={field}>
          <td>{FIELD_LABELS[field] ?? field}</td>{STATUSES.map((s) => <td key={s}>{count(counts[s] ?? 0)}</td>)}<td>{count(counts.UNKNOWN ?? 0)}</td>
        </tr>)}</tbody>
      </table></div>
    </section>

    <section className="panel">
      <h2>Data quality by issue type</h2>
      {a.issue_types.length > 0 && <Bars label="Issue type distribution" counts={Object.fromEntries(a.issue_types.map((issue) => [issue.code, issue.count]))} />}
      {a.issue_types.length === 0 ? <p>No issue types recorded for this run.</p> : <div className="table"><table aria-label="Issue types">
        <thead><tr><th>Code</th><th>Count</th></tr></thead>
        <tbody>{a.issue_types.map((t) => <tr key={t.code}><td className="mono">{t.code}</td><td>{count(t.count)}</td></tr>)}</tbody>
      </table></div>}
    </section>

    <section className="panel">
      <h2>Brands</h2>
      {a.brands.items.length === 0 ? <p>No brand recorded in this run.</p> : <Bars label="Brand distribution" counts={Object.fromEntries(a.brands.items.map((b) => [b.label, b.count]))} />}
      <p className="local-note">{count(a.brands.distinct)} distinct brand{a.brands.distinct === 1 ? "" : "s"}{a.brands.distinct > a.brands.items.length ? `, the ${a.brands.items.length} most frequent shown` : ""} · {count(a.brands.not_recorded)} records without a brand.</p>
    </section>

    <section className="panel">
      <h2>Price spread</h2>
      <p>Selling price minus COG, over the {count(a.price_spread.count)} records with both a VERIFIED selling price and a recorded COG. It is a spread, not a profit and not a ranking. Bar length shows magnitude; signed amounts are shown beside each bar.</p>
      <div className="kpis">
        <article><small>Average spread</small><strong>{fieldMoney(a.price_spread.average_amount)}</strong></article>
        <article><small>At or below COG</small><strong>{count(a.price_spread.at_or_below_cog)}</strong></article>
      </div>
      {a.price_spread.largest.length > 0 && <ul className="spread-bars" aria-label="Price spread distribution">{a.price_spread.largest.map((entry) => {
        const max = Math.max(...a.price_spread.largest.map((item) => Math.abs(Number(item.amount))))
        return <li key={entry.record_ref}><span>{entry.title || entry.record_ref}</span><strong>{fieldMoney(entry.amount)}</strong><span className="bar" aria-hidden="true"><span style={{ width: max > 0 ? `${Math.abs(Number(entry.amount)) / max * 100}%` : 0 }} /></span></li>
      })}</ul>}
      {a.price_spread.largest.length > 0 && <div className="table"><table aria-label="Largest price spreads">
        <thead><tr><th>Record</th><th>Spread</th><th>% of price</th></tr></thead>
        <tbody>{a.price_spread.largest.map((e) => <tr key={e.record_ref}>
          <td><a href={`/run/${encodeURIComponent(runId)}/product/${encodeURIComponent(e.record_ref)}`}>{e.title || e.record_ref}</a></td>
          <td>{fieldMoney(e.amount)}</td><td>{fieldPercent(e.percent)}</td>
        </tr>)}</tbody>
      </table></div>}
    </section>

    <p><button onClick={() => go(`/catalog?run=${encodeURIComponent(runId)}`)}>Review these records in Catalog</button></p>
  </>
}
