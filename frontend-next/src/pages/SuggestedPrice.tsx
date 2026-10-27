import type { RecordOut } from "../api/types"
import { ProvenanceBadge } from "./shared"

/**
 * Supplier suggested price (ADR-053, GOLDEN 17): what the uploaded file
 * declared as the supplier's suggested resale price. Evidence only -- not the
 * selling price used for profit, not the cost, never a decision input. The
 * amount is shown exactly as stored with its declared currency code: no
 * conversion, no rounding through a float, no "$" assumed.
 */

const STATE_TEXT: Record<string, string> = {
  NOT_DECLARED: "The file had no supplier suggested price columns.",
  NOT_CAPTURED: "This record was processed before the supplier suggested price was captured.",
}

export function SuggestedPriceCell({ record }: { record: RecordOut }) {
  const amount = record.supplier_suggested_price?.amount
  if (!amount?.status) {
    return <span className="local-note" title={STATE_TEXT[record.supplier_suggested_price_state ?? "NOT_CAPTURED"]}>—</span>
  }
  const shown = amount.status === "INFERRED" ? `${amount.value} ${amount.unit}` : amount.status === "INVALID" ? "invalid" : "no value"
  return <span className="fv" title="Declared by the supplier in the uploaded file; not verified and not used for this decision">
    {shown} <ProvenanceBadge status={amount.status} />
  </span>
}

export function SuggestedPricePanel({ record }: { record: RecordOut }) {
  const document = record.supplier_suggested_price
  const amount = document?.amount
  return <section className="panel" aria-label="Supplier suggested price">
    <h2>Supplier suggested price <span className="not-used">Not used for this decision</span></h2>
    <p>What the uploaded file declared as the supplier's suggested resale price. It is not verified, it is not the selling price used for profit and it is not the cost.</p>
    {!document || !amount ? <p className="local-note">{STATE_TEXT[record.supplier_suggested_price_state ?? "NOT_CAPTURED"]}</p> : <>
      <dl>
        <dt>Declared amount</dt>
        <dd>{amount.status === "INFERRED" ? <span className="mono">{String(amount.value)} {amount.unit}</span> : amount.status === "INVALID" ? "Invalid value" : "No value declared"}
          {amount.status && <> <ProvenanceBadge status={amount.status} /></>}
          {amount.raw_value !== null && amount.raw_value !== undefined && <> · raw <span className="mono">{String(amount.raw_value)}</span></>}</dd>
        <dt>Declared currency</dt><dd className="mono">{document.currency_raw ?? "—"}</dd>
        <dt>Method</dt><dd>{amount.provenance?.method ?? "—"}</dd>
        <dt>Source</dt><dd>{amount.provenance ? `${amount.provenance.source_type} · ${amount.provenance.source} · ${amount.provenance.source_reference ?? ""}` : "—"}</dd>
        <dt>Captured at</dt><dd className="mono">{amount.provenance?.retrieved_at ?? "—"}</dd>
      </dl>
      {document.diagnostics.length > 0 && <>
        <h3>Diagnostics</h3>
        <div className="table"><table aria-label="Supplier suggested price diagnostics">
          <thead><tr><th>Code</th><th>Column</th><th>Row</th><th>Raw value</th><th>Message</th></tr></thead>
          <tbody>{document.diagnostics.map((d, i) => <tr key={i}>
            <td className="mono">{d.code}</td><td className="mono">{d.column ?? "—"}</td><td>{d.row}</td>
            <td className="mono">{d.raw_value ?? "—"}</td><td>{d.message}</td>
          </tr>)}</tbody>
        </table></div>
      </>}
    </>}
  </section>
}
