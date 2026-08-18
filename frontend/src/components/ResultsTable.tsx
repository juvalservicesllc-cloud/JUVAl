import type { RecordOut } from "../types"
import { ProvenanceValue } from "./ProvenanceValue"

// Canonical run-result rendering. Values stay paired with provenance; no
// financial, decision, or risk value is computed in the browser.
export function ResultsTable({ records }: { records: RecordOut[] }) {
  if (records.length === 0) return <p>No processed records.</p>

  return <div className="results-table-wrapper"><table className="results-table">
    <thead><tr><th>Record</th><th>SKU</th><th>ASIN</th><th>Price</th><th>Profit</th><th>ROI</th><th>HazMat</th><th>Bulky</th><th>Decision</th><th>Issues</th></tr></thead>
    <tbody>{records.map((record) => <tr key={record.record_ref}>
      <td className="mono">{record.record_ref}</td><td>{record.supplier_sku ?? "—"}</td>
      <td><ProvenanceValue value={record.asin} /></td><td><ProvenanceValue value={record.selling_price} /></td>
      <td><ProvenanceValue value={record.profit} /></td><td><ProvenanceValue value={record.roi} /></td>
      <td>{record.hazmat_status ?? "—"}{record.hazmat_severity ? ` (${record.hazmat_severity})` : ""}</td>
      <td>{record.bulky_status ?? "—"}{record.bulky_severity ? ` (${record.bulky_severity})` : ""}</td>
      <td className={record.decision ? `decision-${record.decision.toLowerCase()}` : ""}>{record.decision ?? "—"}{record.decision_reasons.length > 0 && <ul className="decision-reasons">{record.decision_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}</td>
      <td>{record.issue_count > 0 ? <ul className="issues">{record.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : "—"}</td>
    </tr>)}</tbody>
  </table></div>
}
