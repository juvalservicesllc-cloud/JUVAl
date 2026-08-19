import { Link } from "react-router-dom"
import type { RecordOut } from "../types"
import { ProvenanceValue } from "./ProvenanceValue"
import { StatusBadge } from "./StatusBadge"

// Canonical run-result rendering. Values stay paired with provenance; no
// financial, decision, or risk value is computed in the browser.
// `executionId` is optional -- when known (Upload's just-processed result,
// Run Detail's own page), the record becomes a link into Product Detail,
// carrying the already-fetched record via router state so that page never
// needs a redundant fetch for the common click-through path.
export function ResultsTable({ records, executionId }: { records: RecordOut[]; executionId?: string }) {
  if (records.length === 0) return <p>No processed records.</p>

  return <div className="results-table-wrapper"><table className="results-table">
    <thead><tr><th>Record</th><th>SKU</th><th>ASIN</th><th>Price</th><th>Profit</th><th>ROI</th><th>HazMat</th><th>Bulky</th><th>Decision</th><th>Issues</th></tr></thead>
    <tbody>{records.map((record) => <tr key={record.record_ref}>
      <td className="mono">
        {executionId
          ? <Link to={`/runs/${encodeURIComponent(executionId)}/records/${encodeURIComponent(record.record_ref)}`} state={{ record }}>{record.record_ref}</Link>
          : record.record_ref}
      </td><td>{record.supplier_sku ?? "—"}</td>
      <td><ProvenanceValue value={record.asin} /></td><td className="numeric-cell"><ProvenanceValue value={record.selling_price} /></td>
      <td className="numeric-cell"><ProvenanceValue value={record.profit} /></td><td className="numeric-cell"><ProvenanceValue value={record.roi} /></td>
      <td><StatusBadge value={record.hazmat_status ?? "UNKNOWN"} />{record.hazmat_severity && record.hazmat_severity !== "NONE" && <> <StatusBadge value={record.hazmat_severity} /></>}</td>
      <td><StatusBadge value={record.bulky_status ?? "UNKNOWN"} />{record.bulky_severity && record.bulky_severity !== "NONE" && <> <StatusBadge value={record.bulky_severity} /></>}</td>
      <td className={record.decision ? `decision-${record.decision.toLowerCase()}` : ""}>{record.decision ? <StatusBadge value={record.decision} /> : "—"}{record.decision_reasons.length > 0 && <ul className="decision-reasons">{record.decision_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}</td>
      <td>{record.issue_count > 0 ? <ul className="issues">{record.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : "—"}</td>
    </tr>)}</tbody>
  </table></div>
}
