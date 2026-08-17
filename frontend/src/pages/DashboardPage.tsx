import { useState } from "react"
import { Link } from "react-router-dom"
import { AnalyticsChart, type ChartType } from "../components/AnalyticsChart"
import { StatusBadge } from "../components/StatusBadge"
import { dashboardSummary, runs } from "../data/demo"

const cards = [
  ["Total Products", dashboardSummary.totalProducts, "All catalog records"],
  ["Processable", dashboardSummary.processable, "Ready for evaluation"],
  ["Excluded", dashboardSummary.excluded, "Failed validation"],
  ["Missing ASIN", dashboardSummary.missingAsin, "Needs enrichment"],
] as const

const chartData = [
  { label: "Processable", value: dashboardSummary.processable },
  { label: "Excluded", value: dashboardSummary.excluded },
  { label: "Hazmat", value: dashboardSummary.hazmat },
  { label: "Bulky", value: dashboardSummary.bulky },
  { label: "Missing ASIN", value: dashboardSummary.missingAsin },
]

export function DashboardPage() {
  const [chartType, setChartType] = useState<ChartType>("line")

  return <>
    <div className="page-intro"><div><p className="eyebrow">CATALOG OVERVIEW <span className="demo-indicator">Demo data</span></p><h2>Catalog operations</h2><p>Snapshot of the current typed catalog fixture.</p></div><Link to="/upload" className="primary-button">Upload catalog</Link></div>
    <div className="demo-banner"><strong>DEMO MODE</strong> Dashboard metrics and activity are typed presentation fixtures.</div>
    <section className="metric-grid">{cards.map(([label, value, note]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value.toLocaleString()}</strong><small>{note}</small></article>)}</section>
    <section className="panel analytics-panel"><div className="panel-heading"><div><p className="eyebrow">DISTRIBUTION</p><h2>Catalog signal mix</h2><p>Current fixture counts by operational state.</p></div><div className="segmented-control" aria-label="Chart type"><button type="button" className={chartType === "line" ? "selected" : ""} aria-pressed={chartType === "line"} onClick={() => setChartType("line")}>Line</button><button type="button" className={chartType === "bar" ? "selected" : ""} aria-pressed={chartType === "bar"} onClick={() => setChartType("bar")}>Bars</button></div></div><AnalyticsChart data={chartData} chartType={chartType} /></section>
    <section className="panel"><div className="panel-heading"><div><p className="eyebrow">ACTIVITY</p><h2>Recent Runs</h2></div><Link to="/runs">View all</Link></div><div className="run-list">{runs.map(run => <article key={run.executionId}><div className="run-icon">XL</div><div><strong>{run.executionId}</strong><small>{run.createdAt} · {run.totalRecords.toLocaleString()} records</small></div><StatusBadge value={run.status} /></article>)}</div></section>
  </>
}
