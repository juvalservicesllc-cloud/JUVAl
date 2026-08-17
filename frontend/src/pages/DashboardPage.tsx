import { Link } from "react-router-dom"
import { StatusBadge } from "../components/StatusBadge"
import { dashboardSummary, runs } from "../data/demo"

const cards = [
  ["Total Products", dashboardSummary.totalProducts, "All catalog records"],
  ["Processable", dashboardSummary.processable, "Ready for evaluation"],
  ["Excluded", dashboardSummary.excluded, "Failed validation"],
  ["Hazmat", dashboardSummary.hazmat, "Requires review"],
  ["Bulky", dashboardSummary.bulky, "Oversize products"],
  ["Missing ASIN", dashboardSummary.missingAsin, "Needs enrichment"],
] as const

export function DashboardPage() {
  return <>
    <div className="page-intro"><div><p className="eyebrow">CATALOG OVERVIEW</p><h2>Good afternoon</h2><p>Here is the latest sourcing snapshot from West Marine Pro.</p></div><Link to="/upload" className="primary-button">Upload catalog</Link></div>
    <div className="demo-banner"><strong>DEMO MODE</strong> Summary and recent run data are typed presentation fixtures.</div>
    <section className="metric-grid">{cards.map(([label, value, note]) => <article className="metric-card" key={label}><span>{label}</span><strong>{value.toLocaleString()}</strong><small>{note}</small></article>)}</section>
    <section className="panel"><div className="panel-heading"><div><p className="eyebrow">ACTIVITY</p><h2>Recent Runs</h2></div><Link to="/runs">View all</Link></div><div className="run-list">{runs.map(run => <article key={run.executionId}><div className="run-icon">XL</div><div><strong>{run.executionId}</strong><small>{run.createdAt} · {run.totalRecords.toLocaleString()} records</small></div><StatusBadge value={run.status} /></article>)}</div></section>
  </>
}
