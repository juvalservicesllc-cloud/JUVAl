import { Fragment, type ReactNode } from "react"
import type { RecordFinancialOut, StoredPayloadOut } from "../api/types"
import { ProvenanceBadge } from "./shared"

/**
 * A readable view of the stored ADR-047 documents (API_CONTRACT §2e).
 *
 * It only *reads*: every number is the stored Decimal string, shown exactly,
 * never parsed, rounded or recomputed; every value keeps its own verification
 * status and source. Known blocks of `juval.adr047.financial-record` v1/v2 and
 * `juval.adr047.capture-diagnostics` v1 get a layout; any key this view does
 * not know is listed as stored, and the original JSON is always one click away.
 */

type Json = unknown
const obj = (v: Json): Record<string, Json> | null => v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, Json> : null
const arr = (v: Json): Json[] => Array.isArray(v) ? v : []
const str = (v: Json): string | null => typeof v === "string" ? v : null

const DOCUMENT_KEYS = new Set(["format", "version", "evidence", "selling_price", "resolution", "calculations", "supplied_inputs", "capture_problems", "implementation"])
const DIAGNOSTICS_KEYS = new Set(["format", "version", "execution_id", "record_ref", "diagnostics"])

/** The serialized scalar: {"decimal": "4.50"}, {"bool": true}, {"str": "x"}. */
function Scalar({ value }: { value: Json }) {
  const o = obj(value)
  if (value === null || value === undefined) return <span className="local-note">No value</span>
  if (typeof value === "string" || typeof value === "number") return <span className="mono">{String(value)}</span>
  if (o && typeof o.decimal === "string") return <span className="mono">{o.decimal}</span>
  if (o && typeof o.bool === "boolean") return <>{o.bool ? "yes" : "no"}</>
  if (o && typeof o.str === "string") return <>{o.str}</>
  return <code className="mono">{JSON.stringify(value)}</code>
}

/** A serialized FieldValue: exact value, unit, its own status, its source. */
function Field({ value, empty = "Not supplied" }: { value: Json; empty?: string }) {
  const field = obj(value)
  if (!field) return <span className="local-note">{empty}</span>
  const provenance = obj(field.provenance)
  const status = str(provenance?.verification_status)
  return <span className="fin-field">
    <Scalar value={field.value} />{str(field.unit) ? ` ${field.unit}` : ""} {status && <ProvenanceBadge status={status} />}
    {field.raw_value !== null && field.raw_value !== undefined && <small> raw <Scalar value={field.raw_value} /></small>}
    {provenance && <small className="fin-source">{[str(provenance.source_type), str(provenance.source), str(provenance.source_reference)].filter(Boolean).join(" · ")}</small>}
    {str(provenance?.evidence) && <small className="fin-source">{String(provenance!.evidence)}</small>}
  </span>
}

function Table({ label, head, rows }: { label: string; head: string[]; rows: ReactNode[][] }) {
  return <div className="table"><table aria-label={label}>
    <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((cells, i) => <tr key={i}>{cells.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
  </table></div>
}

const yesNo = (v: Json) => v === true ? "yes" : v === false ? "no" : "—"

function Calculations({ calculations }: { calculations: Json }) {
  const block = obj(calculations)
  const rows = arr(block?.calculations).map((raw) => {
    const c = obj(raw) ?? {}
    return [
      <b>{str(c.result) ?? "—"}</b>,
      <Field value={c.value} empty="No value" />,
      <span className="mono">{str(c.expression) ?? "—"}</span>,
      str(c.blocker) ? <span className="notice-inline">{String(c.blocker)}</span> : "—",
      arr(c.preconditions).length ? <ul className="fin-list">{arr(c.preconditions).map((p, i) => {
        const pre = obj(p) ?? {}
        return <li key={i}><span className="mono">{str(pre.expression)}</span> with <Scalar value={pre.operand} />: {pre.satisfied === true ? "satisfied" : pre.satisfied === false ? "NOT satisfied" : "unknown"}</li>
      })}</ul> : "—",
      arr(c.undeclared_terms).length ? arr(c.undeclared_terms).map(String).join(", ") : "—",
      yesNo(c.exact),
    ]
  })
  return <>
    <h3>Calculated results</h3>
    <p className="local-note">Results of the ADR-047 calculator as stored{str(block?.decimal_rounding) || block?.decimal_precision !== undefined ? ` (precision ${String(block?.decimal_precision ?? "—")}, rounding ${String(block?.decimal_rounding ?? "—")})` : ""}. They do not change this record's profit, ROI or decision.</p>
    {rows.length ? <Table label="Calculated results" head={["Result", "Value", "Expression", "Blocker", "Preconditions", "Undeclared terms", "Exact"]} rows={rows} /> : <p>No calculated results stored.</p>}
  </>
}

function Terms({ evidence }: { evidence: Json }) {
  const e = obj(evidence)
  const scenario = obj(e?.scenario)
  const rows = arr(e?.terms).map((raw) => {
    const t = obj(raw) ?? {}
    const applicability = obj(t.applicability)
    const context = obj(t.context)
    return [
      <b>{str(t.term) ?? "—"}</b>,
      <Field value={applicability?.applies} empty="Not declared" />,
      <Field value={t.amount} empty="No amount" />,
      str(context?.basis_definition) ?? "—",
      [str(context?.effective_at), str(context?.effective_until)].filter(Boolean).join(" → ") || "—",
      str(t.allocation_method) ?? "—",
      arr(t.depends_on).map(String).join(", ") || "—",
      str(applicability?.justification) ?? "—",
    ]
  })
  return <>
    <h3>Scenario</h3>
    {scenario ? <dl>
      <dt>Scenario</dt><dd>{str(scenario.scenario_id)}@{str(scenario.scenario_version)}</dd>
      <dt>Currency</dt><dd>{str(scenario.currency) ?? "—"}</dd>
      <dt>Policy</dt><dd>{str(scenario.policy_identity) ?? "—"}</dd>
      <dt>Sellable unit</dt><dd>{str(scenario.sellable_unit_definition) ?? "—"}</dd>
      <dt>Required terms</dt><dd>{arr(scenario.required_terms).map(String).join(", ") || "—"}</dd>
    </dl> : <p>No scenario stored.</p>}
    <h3>Declared terms</h3>
    {rows.length ? <Table label="Declared terms" head={["Term", "Applies", "Amount", "Basis", "Effective", "Allocation", "Depends on", "Justification"]} rows={rows} /> : <p>No terms stored.</p>}
  </>
}

function Resolution({ resolution }: { resolution: Json }) {
  const results = arr(obj(resolution)?.results)
  if (!results.length) return null
  return <>
    <h3>Dependency resolution</h3>
    {results.map((raw, i) => {
      const r = obj(raw) ?? {}
      const deps = arr(r.dependencies).map((d) => obj(d) ?? {})
      const blocked = deps.filter((d) => d.blocker)
      const excluded = deps.filter((d) => d.excluded === true)
      return <details key={i} className="evidence">
        <summary>{str(r.result) ?? "—"}: {deps.length - blocked.length - excluded.length} resolved · {excluded.length} excluded · {blocked.length} blocked</summary>
        <Table label={`${str(r.result) ?? "Result"} dependencies`} head={["Dependency", "State", "Operand", "Detail"]} rows={deps.map((d) => [
          str(d.dependency) ?? str(d.term) ?? "—",
          d.blocker ? `blocked: ${String(d.blocker)}` : d.excluded === true ? "excluded (does not apply)" : "resolved",
          <Field value={d.operand} empty="—" />,
          str(d.detail) ?? "—",
        ])} />
      </details>
    })}
  </>
}

function Problems({ label, items }: { label: string; items: Json[] }) {
  if (!items.length) return <p>None stored.</p>
  return <Table label={label} head={["Code", "Subject", "Column", "Row", "Raw value", "Message"]} rows={items.map((raw) => {
    const p = obj(raw) ?? {}
    return [str(p.code) ?? "—", str(p.subject) ?? "—", <span className="mono">{str(p.column) ?? "—"}</span>, p.row === null || p.row === undefined ? "—" : String(p.row),
      p.raw_value === null || p.raw_value === undefined ? "—" : typeof p.raw_value === "string" ? <span className="mono">{p.raw_value}</span> : <Scalar value={p.raw_value} />,
      str(p.message) ?? str(p.text) ?? "—"]
  })} />
}

function Unknown({ payload, known }: { payload: Record<string, Json>; known: Set<string> }) {
  const extra = Object.keys(payload).filter((k) => !known.has(k))
  if (!extra.length) return null
  return <>
    <h3>Other stored fields</h3>
    <p className="local-note">Stored but not laid out by this view; shown exactly as persisted.</p>
    {extra.map((key) => <details key={key}><summary className="mono">{key}</summary><pre className="mono stored-json">{JSON.stringify(payload[key], null, 2)}</pre></details>)}
  </>
}

function Raw({ label, stored }: { label: string; stored: StoredPayloadOut }) {
  return <details><summary>{label}: original stored JSON ({stored.format} v{stored.version})</summary><pre className="mono stored-json">{JSON.stringify(stored.payload, null, 2)}</pre></details>
}

export function FinancialEvidenceView({ financial }: { financial: RecordFinancialOut }) {
  const doc = financial.financial_document
  const diagnostics = financial.capture_diagnostics
  const payload = obj(doc?.payload) ?? {}
  const supplied = obj(payload.supplied_inputs)
  const implementation = obj(payload.implementation)
  const selling = obj(payload.selling_price)
  const diagnosticItems = arr(obj(diagnostics?.payload)?.diagnostics)

  return <div className="financial-evidence">
    {financial.inconsistencies.length > 0 && <>
      <p role="status" className="notice">The stored document and its diagnostics disagree; neither is preferred:</p>
      <ul>{financial.inconsistencies.map((item, i) => <li key={i}>{item}</li>)}</ul>
    </>}

    {doc ? <section aria-label="Financial document">
      <p><b>{doc.format}</b> version {doc.version}{doc.version === 1 ? " — v1 documents do not store supplied inputs, capture problems or implementation identity" : ""}</p>
      <Calculations calculations={payload.calculations} />
      <h3>Selling price used</h3>
      <p><Field value={selling?.amount} empty="No selling price stored" />{str(obj(selling?.context)?.basis_definition) ? ` — ${String(obj(selling?.context)!.basis_definition)}` : ""}</p>
      <Terms evidence={payload.evidence} />
      <Resolution resolution={payload.resolution} />
      {supplied && <>
        <h3>Supplied inputs</h3>
        <Table label="Supplied inputs" head={["Input", "As supplied"]} rows={Object.entries(supplied).map(([key, value]) => [key, <Field value={value} />])} />
      </>}
      {Array.isArray(payload.capture_problems) && <>
        <h3>Capture problems in this document</h3>
        <Problems label="Capture problems" items={payload.capture_problems} />
      </>}
      {implementation && <>
        <h3>Implementation</h3>
        <dl>{Object.entries(implementation).map(([key, value]) => <Fragment key={key}><dt>{key}</dt><dd className="mono">{value === null ? "—" : Array.isArray(value) ? value.map(String).join(", ") || "—" : String(value)}</dd></Fragment>)}</dl>
      </>}
      <Unknown payload={payload} known={DOCUMENT_KEYS} />
      <Raw label="Financial document" stored={doc} />
    </section> : <p>No financial document was stored for this record (older run, no declared scenario, or the opt-in was not used).</p>}

    {diagnostics ? <section aria-label="Capture diagnostics">
      <h3>Capture diagnostics</h3>
      <Problems label="Capture diagnostics" items={diagnosticItems} />
      <Unknown payload={obj(diagnostics.payload) ?? {}} known={DIAGNOSTICS_KEYS} />
      <Raw label="Capture diagnostics" stored={diagnostics} />
    </section> : <p>No capture diagnostics were stored.</p>}
  </div>
}
