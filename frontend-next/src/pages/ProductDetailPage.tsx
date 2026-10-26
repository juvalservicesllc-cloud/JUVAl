import { useEffect, useState } from "react"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRecordFinancial, getRunRecord } from "../api/records"
import type { FieldValueOut, ProvenanceStatus, RecordFinancialOut, RecordOut } from "../api/types"
import { fieldMoney, fieldPercent } from "../format"
import { METRIC_EXPLANATIONS } from "../metricExplanations"
import { FinancialEvidenceView } from "./FinancialEvidence"
import { Badge, ProvenanceBadge } from "./shared"

/**
 * Product Detail — one record *within one run* (ADR-011/012: there is no
 * global product identity), migrated into the Golden-first app (ADR-030).
 *
 * Every value comes from `GET .../records/{ref}` with its verification status
 * and stored provenance; ADR-047 evidence from `.../financial`. Nothing is
 * recalculated (ADR-006), no image, URL or market price is shown because no
 * approved source exists, and Golden's simulated price chart is deliberately
 * not carried over: it would be a fabricated market series.
 */
type State =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "error"; message: string }
  | { kind: "ready"; record: RecordOut }

type FinancialState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; financial: RecordFinancialOut }

type Format = "text" | "money" | "percent"
const FIELDS: [key: keyof RecordOut, label: string, format: Format][] = [
  ["title", "Title", "text"], ["brand", "Brand", "text"], ["category", "Category", "text"],
  ["asin", "ASIN", "text"], ["upc", "UPC", "text"], ["weight", "Weight", "text"],
  ["height", "Height", "text"], ["width", "Width", "text"], ["length", "Length", "text"],
  ["selling_price", "Selling price", "money"], ["profit", "Profit", "money"], ["roi", "ROI", "percent"],
  ["margin", "Margin", "percent"], ["break_even_price", "Break-even price", "money"],
  ["max_cog_target_profit", "Max COG (target profit)", "money"], ["max_cog_target_roi", "Max COG (target ROI)", "money"],
]
const GROUPS: [status: ProvenanceStatus | null, label: string][] = [
  ["VERIFIED", "Verified"], ["INFERRED", "Inferred"], ["NOT_FOUND", "Not found"], ["INVALID", "Invalid"], [null, "Not recorded"],
]

const isField = (value: unknown): value is FieldValueOut => Boolean(value) && typeof value === "object" && "status" in (value as object)

function shown(value: FieldValueOut, format: Format): string {
  if (value.value === null || value.value === undefined) return "No value"
  if (format === "money") return fieldMoney(value.value)
  if (format === "percent") return fieldPercent(value.value)
  return `${value.value}${value.unit ? ` ${value.unit}` : ""}`
}

function recordFields(record: RecordOut) {
  return FIELDS.flatMap(([key, label, format]) => {
    const value = record[key]
    return isField(value) ? [{ key, label, format, value }] : []
  })
}

/** File, row and source type read from provenance the importer stored
 *  (`source` = file name, `source_reference` = "row=N"). Nothing inferred. */
function sourceOf(record: RecordOut) {
  const provenances = recordFields(record).flatMap(({ value }) => value.provenance ? [value.provenance] : [])
  const fromFile = provenances.find((p) => p.source_type === "SUPPLIER_FILE")
  const row = provenances.map((p) => p.source_reference).find((ref) => ref?.startsWith("row="))
  return { file: fromFile?.source ?? null, type: fromFile?.source_type ?? null, row: row ? row.slice(4) : null }
}

const notRecorded = <span className="local-note">Not recorded on this snapshot</span>

function Value({ value, format }: { value: FieldValueOut | undefined; format: Format }) {
  if (!value || value.status === null) return <span className="local-note">Not recorded</span>
  return <span className="fv">{shown(value, format)} <ProvenanceBadge status={value.status} /></span>
}

function Metric({ label, value, format, explain }: { label: string; value: FieldValueOut | undefined; format: Format; explain?: string }) {
  return <article>
    <small>{label}</small>
    <strong><Value value={value} format={format} /></strong>
    {explain && <details className="explain"><summary>What does this mean?</summary><p>{explain}</p></details>}
  </article>
}

/** A Decimal the engine stored outside a FieldValue (COG, fees, proceeds). */
function Amount({ label, value, explain }: { label: string; value: string | null | undefined; explain?: string }) {
  return <article>
    <small>{label}</small>
    <strong>{value === null || value === undefined ? <span className="local-note">Not stored</span> : fieldMoney(value)}</strong>
    {explain && <details className="explain"><summary>What does this mean?</summary><p>{explain}</p></details>}
  </article>
}

function Evidence({ record }: { record: RecordOut }) {
  return <section className="panel">
    <h2>Evidence by field</h2>
    <p>Each value with its verification state and the provenance stored with it. Money and percentages are formatted above; the exact stored value is disclosed here.</p>
    {recordFields(record).map(({ key, label, format, value }) => <details key={String(key)} className="evidence">
      <summary>{label}: {value.status === null ? "Not recorded" : shown(value, format)} {value.status && <ProvenanceBadge status={value.status} />}</summary>
      {value.status === null ? <p className="local-note">No value was recorded for this field.</p> : <dl>
        {value.provenance ? <>
          <dt>Source</dt><dd>{value.provenance.source}</dd>
          <dt>Source type</dt><dd>{value.provenance.source_type}</dd>
          {value.provenance.source_reference && <><dt>Reference</dt><dd className="mono">{value.provenance.source_reference}</dd></>}
          <dt>Method</dt><dd>{value.provenance.method}</dd>
          <dt>Retrieved</dt><dd>{new Date(value.provenance.retrieved_at).toLocaleString()}</dd>
          {value.provenance.evidence && <><dt>Evidence</dt><dd>{value.provenance.evidence}</dd></>}
        </> : <><dt>Provenance</dt><dd className="local-note">Not stored for this historical snapshot</dd></>}
        {value.raw_value !== null && value.raw_value !== undefined && <><dt>Raw value</dt><dd className="mono">{String(value.raw_value)}</dd></>}
        {format !== "text" && value.value !== null && <><dt>Stored value</dt><dd className="mono">{String(value.value)}</dd></>}
      </dl>}
    </details>)}
  </section>
}

/** Golden grouped data quality by provenance. Statuses are read, never derived. */
function ConfidenceGroups({ record }: { record: RecordOut }) {
  const fields = recordFields(record)
  return <div className="confidence-groups">
    {GROUPS.map(([status, label]) => {
      const members = fields.filter(({ value }) => value.status === status)
      return <article key={label} aria-label={`${label} fields`}>
        <small>{status ? <ProvenanceBadge status={status} /> : null} {label} ({members.length})</small>
        <p>{members.length ? members.map(({ label: name }) => name).join(", ") : "None"}</p>
      </article>
    })}
  </div>
}

function FinancialEvidence({ state }: { state: FinancialState }) {
  return <section className="panel" aria-label="Native financial evidence">
    <h2>Native financial evidence (ADR-047)</h2>
    <p>Stored supplier-declared evidence and the ADR-047 calculator's stored results, shown exactly as persisted. They do not change this record's profit, ROI or decision, and they are never Amazon verification.</p>
    {state.kind === "loading" && <p>Loading stored evidence…</p>}
    {state.kind === "error" && <p className="local-note">Stored financial evidence could not be loaded; nothing is assumed about it.</p>}
    {state.kind === "ready" && <FinancialEvidenceView financial={state.financial} />}
  </section>
}

export function ProductDetailPage({ executionId, recordRef, go }: { executionId: string; recordRef: string; go: (path: string) => void }) {
  const [state, setState] = useState<State>({ kind: "loading" })
  const [financial, setFinancial] = useState<FinancialState>({ kind: "loading" })
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: "loading" })
    setFinancial({ kind: "loading" })
    getRunRecord(executionId, recordRef, controller.signal)
      .then((record) => {
        setState({ kind: "ready", record })
        // Evidence is secondary: its failure never hides the record.
        getRecordFinancial(executionId, recordRef, controller.signal)
          .then((value) => setFinancial({ kind: "ready", financial: value }))
          .catch(() => { if (!controller.signal.aborted) setFinancial({ kind: "error" }) })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) return setState({ kind: "missing" })
        setState({ kind: "error", message: apiErrorMessage(error) })
      })
    return () => controller.abort()
  }, [executionId, recordRef, reload])

  const catalog = `/catalog?run=${encodeURIComponent(executionId)}`
  const actions = <p>
    <button onClick={() => go(catalog)}>Back to Catalog</button>{" "}
    <button onClick={() => go(`/runs/${encodeURIComponent(executionId)}`)}>Run detail</button>
  </p>

  if (state.kind === "loading") return <section className="panel"><h1>Product detail</h1><p aria-live="polite">Loading record…</p></section>
  if (state.kind === "missing") return <section className="panel">
    <h1>Record not found</h1>
    <p>This run has no record <span className="mono">{recordRef}</span>, or the run does not exist.</p>
    {actions}
  </section>
  if (state.kind === "error") return <section className="panel">
    <h1>Product detail</h1>
    <p role="alert" className="notice">{state.message}</p>
    <button onClick={() => setReload((n) => n + 1)}>Retry</button>
  </section>

  const { record } = state
  const source = sourceOf(record)
  const title = record.title?.value ? String(record.title.value) : record.supplier_sku || record.record_ref
  return <>
    <h1>{title}</h1>
    <p className="local-note">One record within one run — <span className="mono">{record.record_ref}</span> · run <span className="mono">{executionId}</span></p>

    <section className="panel" aria-label="Decision">
      <h2>Decision {record.decision ? <Badge>{record.decision}</Badge> : <span className="local-note">— not recorded</span>}</h2>
      {record.decision_reasons.length
        ? <ul>{record.decision_reasons.map((reason, i) => <li key={i}>{reason}</li>)}</ul>
        : <p>No disqualifying or review reasons recorded.</p>}
      <details className="explain"><summary>What does this mean?</summary><p>{METRIC_EXPLANATIONS.decision}</p></details>
      <p>Risk context: HazMat {record.hazmat_status ?? "UNKNOWN"} · Bulky {record.bulky_status ?? "UNKNOWN"}</p>
      <p className="threshold-unavailable">The thresholds this run used are not stored with the run yet, so they are not shown here.</p>
    </section>

    <section className="panel" aria-label="Identity">
      <h2>Identity</h2>
      <div className="grid">
        <article><small>Supplier SKU</small><strong>{record.supplier_sku ?? "—"}</strong></article>
        <article><small>Marketplace</small><strong>{record.marketplace ?? "—"}</strong></article>
        <Metric label="ASIN" value={record.asin} format="text" />
        <Metric label="UPC" value={record.upc} format="text" />
        <Metric label="Brand" value={record.brand} format="text" />
        <Metric label="Category" value={record.category} format="text" />
        <Metric label="Weight" value={record.weight} format="text" />
      </div>
      <p className="local-note">No product image or supplier link is shown: JUVAl has no approved image/URL source or rights policy yet, so nothing unverified is displayed.</p>
    </section>

    <section className="panel" aria-label="Source">
      <h2>Source</h2>
      <dl>
        <dt>File</dt><dd>{source.file ?? notRecorded}</dd>
        <dt>Row</dt><dd>{source.row ?? notRecorded}</dd>
        <dt>Source type</dt><dd>{source.type ?? notRecorded}</dd>
      </dl>
    </section>

    <section className="panel" aria-label="Economics">
      <h2>Economics</h2>
      <p>Computed by the backend Profitability Engine and stored with the run; never recalculated here.</p>
      <div className="grid">
        <Metric label="Selling price" value={record.selling_price} format="money" explain={METRIC_EXPLANATIONS.selling_price} />
        <Amount label="COG" value={record.cog} explain={METRIC_EXPLANATIONS.cog} />
        <Amount label="Shipping / unit" value={record.shipping_per_unit} />
        <Amount label="Selling fees" value={record.total_fees} />
        <Amount label="Seller proceeds" value={record.seller_proceeds} />
        <Amount label="Total landed cost" value={record.total_cost} />
        <Metric label="Profit" value={record.profit} format="money" explain={METRIC_EXPLANATIONS.profit} />
        <Metric label="ROI" value={record.roi} format="percent" explain={METRIC_EXPLANATIONS.roi} />
        <Metric label="Margin" value={record.margin} format="percent" explain={METRIC_EXPLANATIONS.margin} />
        <Metric label="Break-even price" value={record.break_even_price} format="money" explain={METRIC_EXPLANATIONS.break_even_price} />
        <Metric label="Max COG (target profit)" value={record.max_cog_target_profit} format="money" explain={METRIC_EXPLANATIONS.max_cog_target_profit} />
        <Metric label="Max COG (target ROI)" value={record.max_cog_target_roi} format="money" explain={METRIC_EXPLANATIONS.max_cog_target_roi} />
      </div>
    </section>

    <section className="panel" aria-label="Risks">
      <h2>Risks</h2>
      <p>HazMat <Badge>{record.hazmat_status ?? "UNKNOWN"}</Badge>{record.hazmat_severity && record.hazmat_severity !== "NONE" && <> severity <Badge>{record.hazmat_severity}</Badge></>}
        {" · "}Bulky <Badge>{record.bulky_status ?? "UNKNOWN"}</Badge>{record.bulky_severity && record.bulky_severity !== "NONE" && <> severity <Badge>{record.bulky_severity}</Badge></>}</p>
      <p className="local-note">Severity is derived by the run's risk policy (ADR-020), not verified externally.</p>
    </section>

    <section className="panel" aria-label="Data quality">
      <h2>Data quality — {record.issue_count ? `${record.issue_count} issue${record.issue_count === 1 ? "" : "s"}` : "no issues"}</h2>
      {record.issues.length > 0 && <ul>{record.issues.map((issue, i) => <li key={i}>{issue}</li>)}</ul>}
      <h3>Fields by confidence</h3>
      <ConfidenceGroups record={record} />
    </section>

    <Evidence record={record} />
    <FinancialEvidence state={financial} />
    {actions}
  </>
}
