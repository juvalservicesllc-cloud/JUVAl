import type { RecordOut } from "../api/types"
import { count } from "../format"
import { ProvenanceBadge } from "./shared"

/**
 * Declared demand (ADR-052): what the uploaded file declared, shown as
 * evidence and never as a decision input. The engine's decision is rendered
 * elsewhere and is unaffected; this view says so wherever a value appears.
 * Values, instants and diagnostics are shown as stored -- nothing is
 * converted, summed or ranked here.
 */

const STATE_TEXT: Record<string, string> = {
  NOT_DECLARED: "The file declared no demand columns.",
  NOT_CAPTURED: "This record was processed before declared demand was captured.",
}

export function DeclaredDemandCell({ record }: { record: RecordOut }) {
  const evidence = record.demand_evidence
  const observation = evidence?.observations[0]
  if (!evidence || !observation) {
    const title = evidence ? "Declared demand not usable — see Product Detail" : STATE_TEXT[record.demand_evidence_state ?? "NOT_CAPTURED"]
    return <span className="local-note" title={title}>{evidence ? "not usable" : "—"}</span>
  }
  const { value } = observation
  const shown = value.status === "INFERRED" ? count(Number(value.value)) : value.status === "INVALID" ? "invalid" : "no value"
  return <span className="fv" title="Declared in the uploaded file; not verified and not used for this decision">
    {shown} {value.status && <ProvenanceBadge status={value.status} />}
  </span>
}

export function DeclaredDemandPanel({ record }: { record: RecordOut }) {
  const evidence = record.demand_evidence
  return <section className="panel" aria-label="Declared demand">
    <h2>Declared demand <span className="not-used">Not used for this decision</span></h2>
    <p>What the uploaded file declared about estimated sales. It is not verified, its author is not accredited, and the decision above stays the engine's.</p>
    {!evidence ? <p className="local-note">{STATE_TEXT[record.demand_evidence_state ?? "NOT_CAPTURED"]}</p> : <>
      {evidence.observations.length === 0 && <p>No usable declaration: the file's demand cells for this record were empty or lacked the required context.</p>}
      {evidence.observations.map((o) => <dl key={o.observation_id}>
        <dt>Declared value</dt>
        <dd>{o.value.status === "INFERRED" ? `${count(Number(o.value.value))} ${o.value.unit ?? ""}` : o.value.status === "INVALID" ? "Invalid value" : "No value declared"}
          {o.value.status && <> <ProvenanceBadge status={o.value.status} /></>}
          {o.value.raw_value !== null && o.value.raw_value !== undefined && <> · raw <span className="mono">{String(o.value.raw_value)}</span></>}</dd>
        <dt>Window</dt><dd className="mono">{o.window.start} → {o.window.end}{o.window_source === "DECLARED_MONTH" ? ` (declared month ${o.declared_month}, ${o.declared_timezone})` : ""}</dd>
        <dt>Observed at</dt><dd className="mono">{o.observed_at}</dd>
        <dt>Population</dt><dd>{o.population_definition}</dd>
        <dt>Method</dt><dd>{o.value.provenance?.method ?? "—"}</dd>
        <dt>Source</dt><dd>{o.value.provenance ? `${o.value.provenance.source_type} · ${o.value.provenance.source} · ${o.value.provenance.source_reference ?? ""}` : "—"}</dd>
        <dt>Captured at</dt><dd className="mono">{evidence.captured_at}</dd>
      </dl>)}
      {evidence.diagnostics.length > 0 && <>
        <h3>Diagnostics</h3>
        <div className="table"><table aria-label="Declared demand diagnostics">
          <thead><tr><th>Code</th><th>Column</th><th>Row</th><th>Raw value</th><th>Message</th></tr></thead>
          <tbody>{evidence.diagnostics.map((d, i) => <tr key={i}>
            <td className="mono">{d.code}</td><td className="mono">{d.column ?? "—"}</td><td>{d.row}</td>
            <td className="mono">{d.raw_value ?? "—"}</td><td>{d.message}</td>
          </tr>)}</tbody>
        </table></div>
      </>}
    </>}
  </section>
}
