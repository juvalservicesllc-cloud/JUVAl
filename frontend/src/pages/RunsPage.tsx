import { StatusBadge } from "../components/StatusBadge"
import { runs } from "../data/demo"

export function RunsPage() {
  return <><div className="page-intro"><div><p className="eyebrow">AUDIT TRAIL</p><h2>Processing Runs</h2><p>Track catalog processing outcomes and record counts.</p></div></div><div className="demo-banner"><strong>DEMO MODE</strong> Run history requires a backend list endpoint.</div><section className="panel table-panel"><table><thead><tr><th>Execution ID</th><th>Created at</th><th>Status</th><th>Total records</th><th>Valid</th><th>Excluded</th><th>Errors</th></tr></thead><tbody>{runs.map(run => <tr key={run.executionId}><td className="mono">{run.executionId}</td><td>{run.createdAt}</td><td><StatusBadge value={run.status} /></td><td>{run.totalRecords.toLocaleString()}</td><td>{run.valid.toLocaleString()}</td><td>{run.excluded.toLocaleString()}</td><td>{run.errors.toLocaleString()}</td></tr>)}</tbody></table></section></>
}
