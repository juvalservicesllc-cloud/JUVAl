import type { FieldValueOut, RecordOut } from "../types"

// Never collapse a FieldValue to a bare value (ADR-003/ADR-004): every
// sensitive cell renders both `value` and `status`, exactly as the
// backend sent them. This component computes nothing -- profit, ROI,
// decision, severity all arrive already calculated by the Core.
function FieldValueCell({ fv }: { fv: FieldValueOut }) {
  if (fv.status === null) {
    return <span className="fv fv-empty">—</span>
  }
  const label = fv.value === null ? "(sin valor)" : String(fv.value)
  return (
    <span className={`fv fv-${fv.status.toLowerCase()}`} title={`verification_status: ${fv.status}`}>
      {label} <em className="fv-status">[{fv.status}]</em>
    </span>
  )
}

export function ResultsTable({ records }: { records: RecordOut[] }) {
  if (records.length === 0) {
    return <p>Sin registros procesados.</p>
  }

  return (
    <div className="results-table-wrapper">
      <table className="results-table">
        <thead>
          <tr>
            <th>record_ref</th>
            <th>SKU</th>
            <th>ASIN</th>
            <th>Precio</th>
            <th>Profit</th>
            <th>ROI</th>
            <th>HazMat</th>
            <th>Bulky</th>
            <th>Decisión</th>
            <th>Issues</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.record_ref}>
              <td>{record.record_ref}</td>
              <td>{record.supplier_sku ?? "—"}</td>
              <td>
                <FieldValueCell fv={record.asin} />
              </td>
              <td>
                <FieldValueCell fv={record.selling_price} />
              </td>
              <td>
                <FieldValueCell fv={record.profit} />
              </td>
              <td>
                <FieldValueCell fv={record.roi} />
              </td>
              <td>
                {record.hazmat_status ?? "—"}
                {record.hazmat_severity ? ` (${record.hazmat_severity})` : ""}
              </td>
              <td>
                {record.bulky_status ?? "—"}
                {record.bulky_severity ? ` (${record.bulky_severity})` : ""}
              </td>
              <td className={record.decision ? `decision-${record.decision.toLowerCase()}` : ""}>
                {record.decision ?? "—"}
                {record.decision_reasons.length > 0 && (
                  <ul className="decision-reasons">
                    {record.decision_reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
              </td>
              <td>
                {record.issue_count > 0 ? (
                  <ul className="issues">
                    {record.issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
