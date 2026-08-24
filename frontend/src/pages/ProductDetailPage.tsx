import { useEffect, useMemo, useState } from "react"
import { Link, useLocation, useParams } from "react-router-dom"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRunRecord } from "../api/records"
import { AnalyticsChart, type ChartType } from "../components/AnalyticsChart"
import { ProvenanceValue } from "../components/ProvenanceValue"
import { StatusBadge } from "../components/StatusBadge"
import type { FieldValueOut, RecordOut } from "../types"
import { money, percent } from "../format"

type DetailState =
  | { status: "loading" }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; record: RecordOut }

function text(value: unknown): string {
  return value === null || value === undefined ? "" : String(value)
}

function formatCurrency(value: string | null): string {
  if (value === null) return "—"
  const n = Number(value)
  return Number.isFinite(n) ? money(n) : "—"
}

function formatPercent(value: FieldValueOut): string {
  if (value.value === null || value.value === undefined) return "No value"
  const n = Number(value.value)
  return Number.isFinite(n) ? percent(n) : "No value"
}

function formatMoneyField(value: FieldValueOut): string {
  if (value.value === null || value.value === undefined) return "No value"
  const n = Number(value.value)
  return Number.isFinite(n) ? money(n) : "No value"
}

function Field({ label, value }: { label: string; value: FieldValueOut }) {
  return (
    <>
      <dt>{label}</dt>
      <dd><ProvenanceValue value={value} /></dd>
    </>
  )
}

function FormattedField({ label, value, formatter }: { label: string; value: FieldValueOut; formatter: (value: FieldValueOut) => string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd><span className="provenance-value"><span>{value.status === null ? "—" : formatter(value)}</span>{value.status !== null && <StatusBadge value={value.status} />}</span></dd>
    </>
  )
}

// "money"/"percent" fields are Decimals whose stored precision runs to dozens
// of digits (ROI is a division). Showing that raw in a scannable summary is
// unreadable and reads as false precision, so the summary is formatted and the
// exact stored value is disclosed inside the expanded evidence instead.
type EvidenceFormat = "text" | "money" | "percent"
const EVIDENCE_FIELDS: Array<[keyof RecordOut, string, EvidenceFormat]> = [
  ["title", "Title", "text"], ["brand", "Brand", "text"], ["category", "Category", "text"], ["asin", "ASIN", "text"], ["upc", "UPC", "text"],
  ["weight", "Weight", "text"], ["height", "Height", "text"], ["width", "Width", "text"], ["length", "Length", "text"], ["selling_price", "Selling price", "money"],
  ["profit", "Profit", "money"], ["roi", "ROI", "percent"], ["margin", "Margin", "percent"], ["break_even_price", "Break-even price", "money"],
  ["max_cog_target_profit", "Max COG (target profit)", "money"], ["max_cog_target_roi", "Max COG (target ROI)", "money"],
]

function formatEvidence(value: FieldValueOut, format: EvidenceFormat): string {
  if (value.value === null || value.value === undefined) return "No value"
  if (format === "money") return formatMoneyField(value)
  if (format === "percent") return formatPercent(value)
  return String(value.value)
}

// The exact persisted Decimal at full precision. The summary above it is
// formatted for scanning; auditing needs the stored value itself, so both are
// available and neither replaces the other. Text fields are already shown
// verbatim in the summary, so repeating them here would be noise.
function StoredValue({ value, format }: { value: FieldValueOut; format: EvidenceFormat }) {
  if (format === "text" || value.value === null || value.value === undefined) return null
  return <><dt>Stored value</dt><dd className="mono">{String(value.value)}</dd></>
}

function ProvenanceSection({ record }: { record: RecordOut }) {
  const fields = useMemo(() => EVIDENCE_FIELDS.flatMap(([key, label, format]) => {
    const value = record[key]
    return value && typeof value === "object" && "status" in value ? [{ key, label, format, value: value as FieldValueOut }] : []
  }), [record])
  const legacyFields = fields.filter(({ value }) => value.status !== null && !value.provenance)
  const sources = [...new Set(fields.flatMap(({ value }) => value.provenance?.source ? [value.provenance.source] : []))]

  return (
    <section className="panel provenance-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">PROVENANCE</p><h2>Evidence and confidence</h2><p>Each value remains paired with its verification state and origin.</p></div>
        <span className="badge badge-neutral">{legacyFields.length ? "Legacy detail" : "Field evidence"}</span>
      </div>
      {sources.length > 0 && <p className="provenance-source-summary"><strong>Sources:</strong> {sources.join(", ")}</p>}
      {legacyFields.length > 0 && <div className="legacy-notice" role="status">Detailed provenance was not stored for this historical snapshot.</div>}
      <div className="evidence-list">
        {fields.map(({ key, label, format, value }) => (
          <details className="evidence-item" key={String(key)}>
            <summary>
              <span>{label}</span>
              <span className="evidence-summary-value">{value.status === null ? "Not available" : formatEvidence(value, format)} {value.status && <StatusBadge value={value.status} />}</span>
            </summary>
            {value.provenance ? (
              <dl className="evidence-details">
                <dt>Source</dt><dd>{value.provenance.source}</dd>
                <dt>Source type</dt><dd>{value.provenance.source_type}</dd>
                {value.provenance.source_reference && <><dt>Reference</dt><dd className="mono">{value.provenance.source_reference}</dd></>}
                <dt>Method</dt><dd>{value.provenance.method}</dd>
                <dt>Retrieved</dt><dd>{new Date(value.provenance.retrieved_at).toLocaleString()}</dd>
                {value.provenance.confidence !== null && <><dt>Confidence</dt><dd>{(value.provenance.confidence * 100).toFixed(0)}%</dd></>}
                {value.provenance.evidence && <><dt>Evidence</dt><dd>{value.provenance.evidence}</dd></>}
                {value.unit && <><dt>Unit</dt><dd>{value.unit}</dd></>}
                {value.raw_value !== null && value.raw_value !== undefined && <><dt>Raw value</dt><dd className="mono">{String(value.raw_value)}</dd></>}
                <StoredValue value={value} format={format} />
              </dl>
            ) : value.status !== null ? (
              <>
                <p className="text-muted">Detailed provenance was not stored for this historical snapshot.</p>
                {/* The exact value is still disclosed: a legacy snapshot lacks
                    provenance, not the value it recorded. */}
                <dl className="evidence-details"><StoredValue value={value} format={format} /></dl>
              </>
            ) : (
              <p className="text-muted">No value was recorded for this field.</p>
            )}
          </details>
        ))}
      </div>
    </section>
  )
}

// Source context is read from provenance the importer already recorded: it
// sets `source` to the real file name and `source_reference` to "row=N".
// Nothing is invented -- a field with no provenance simply contributes
// nothing, and a snapshot with none at all reports the honest unknown.
function sourceContext(record: RecordOut): { file: string | null; row: string | null; sourceType: string | null } {
  const provenances = Object.values(record)
    .filter((value): value is FieldValueOut => Boolean(value) && typeof value === "object" && "provenance" in (value as object))
    .map((value) => value.provenance)
    .filter((provenance): provenance is NonNullable<FieldValueOut["provenance"]> => Boolean(provenance))
  const fromFile = provenances.find((provenance) => provenance.source_type === "SUPPLIER_FILE")
  const rowReference = provenances.map((provenance) => provenance.source_reference).find((reference) => reference?.startsWith("row="))
  return {
    file: fromFile?.source ?? null,
    row: rowReference ? rowReference.slice("row=".length) : null,
    sourceType: fromFile?.source_type ?? null,
  }
}

// Deterministic, non-random placeholder trend -- same record_ref always
// produces the same shape, so this is a stable fixture, not noise that
// could be mistaken for a live feed. It is never a live/Keepa integration;
// see the DEMO_FIXTURE banner rendered with it.
function demoPriceSeries(recordRef: string, basePrice: number): { label: string; value: number }[] {
  let seed = 0
  for (let i = 0; i < recordRef.length; i++) seed = (seed * 31 + recordRef.charCodeAt(i)) % 9973
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  return months.map((label, i) => {
    const wobble = Math.sin(seed + i * 1.7) * 0.08
    return { label, value: Math.max(0, Number((basePrice * (1 + wobble)).toFixed(2))) }
  })
}

export function ProductDetailPage() {
  const { executionId, recordRef } = useParams<{ executionId: string; recordRef: string }>()
  const location = useLocation()
  const passedRecord = (location.state as { record?: RecordOut } | null)?.record
  const [state, setState] = useState<DetailState>(passedRecord ? { status: "ready", record: passedRecord } : { status: "loading" })
  const [reloadToken, setReloadToken] = useState(0)
  const [marketChart, setMarketChart] = useState<ChartType>("line")

  useEffect(() => {
    if (passedRecord) return
    if (!executionId || !recordRef) return
    const controller = new AbortController()
    setState({ status: "loading" })
    getRunRecord(executionId, recordRef, controller.signal)
      .then((record) => setState({ status: "ready", record }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "unavailable", message: "This record does not exist in the selected run." })
          return
        }
        setState({ status: "error", message: error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error) })
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionId, recordRef, reloadToken])

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">RECORD DETAIL</p>
          <h2 className="mono">{recordRef ?? "Unknown record"}</h2>
          <p>Everything JUVAl knows about one record within one run -- never a global product identity (ADR-012/019).</p>
        </div>
        {executionId && (
          <Link to={`/runs/${encodeURIComponent(executionId)}`} className="secondary-button">
            Back to Run Detail
          </Link>
        )}
      </div>

      {state.status === "loading" && <div className="status" aria-live="polite"><p>Loading record…</p></div>}

      {state.status === "unavailable" && (
        <div className="status" aria-live="polite">
          <p>{state.message}</p>
          {executionId && <Link to={`/runs/${encodeURIComponent(executionId)}`} className="secondary-button">Open Run Detail</Link>}
        </div>
      )}

      {state.status === "error" && (
        <div className="status" aria-live="polite">
          <p role="alert" className="error">{state.message}</p>
          <button type="button" className="secondary-button" onClick={() => setReloadToken((n) => n + 1)}>Retry</button>
        </div>
      )}

      {state.status === "ready" && (() => {
        const record = state.record
        const source = sourceContext(record)
        return (
          <>
            {/* DECISION + EXPLANATION -- the headline: what did the engine decide, and why. */}
            <section className="panel result-heading decision-summary">
              <div>
                <p className="eyebrow">DECISION</p>
                <h2>{record.decision ? <StatusBadge value={record.decision} /> : "—"}</h2>
                {record.decision_reasons.length > 0 ? (
                  <ul className="decision-reasons">
                    {record.decision_reasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                ) : (
                  <p className="text-muted">No disqualifying or review reasons recorded.</p>
                )}
                <p className="decision-context"><strong>Risk context:</strong> HazMat {record.hazmat_status ?? "UNKNOWN"} · Bulky {record.bulky_status ?? "UNKNOWN"}</p>
              </div>
            </section>

            {/* IDENTITY */}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">IDENTITY</p><h2>{text(record.title?.value) || record.supplier_sku || record.record_ref}</h2>{record.brand?.value && <p>{text(record.brand.value)}</p>}</div></div>
              <dl className="run-summary">
                <dt>Record ref</dt><dd className="mono">{record.record_ref}</dd>
                <dt>Marketplace</dt><dd>{record.marketplace ?? "—"}</dd>
                <dt>Supplier SKU</dt><dd>{record.supplier_sku ?? "—"}</dd>
                <Field label="ASIN" value={record.asin} />
                <Field label="UPC" value={record.upc} />
                {record.category && <Field label="Category" value={record.category} />}
                <Field label="Weight" value={record.weight} />
                {record.height && <Field label="Height" value={record.height} />}
                {record.width && <Field label="Width" value={record.width} />}
                {record.length && <Field label="Length" value={record.length} />}
              </dl>
              <div className="no-image-state"><span className="eyebrow">MEDIA</span><span>No canonical product image is attached to this snapshot. JUVAl has no approved image source, rights or provenance contract yet, so no picture is shown rather than an unverified one.</span></div>
            </section>

            {/* SOURCE -- which file and row this record came from, straight from
                the provenance the importer stored. */}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">SOURCE</p><h2>Where this record came from</h2><p>Read from stored field provenance, never reconstructed.</p></div></div>
              <dl className="run-summary">
                <dt>Source file</dt><dd>{source.file ?? <span className="text-muted">Not recorded on this snapshot</span>}</dd>
                <dt>Source row</dt><dd>{source.row ?? <span className="text-muted">Not recorded on this snapshot</span>}</dd>
                <dt>Source type</dt><dd>{source.sourceType ?? <span className="text-muted">Not recorded on this snapshot</span>}</dd>
                <dt>Execution</dt><dd className="mono">{executionId ?? "—"}</dd>
              </dl>
              <p className="text-muted">No supplier or marketplace URL is stored: there is no approved canonical link field, so none is shown.</p>
            </section>

            {/* ECONOMICS */}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">ECONOMICS</p><h2>Profitability</h2><p>Backend-computed only; never recalculated in the browser (ADR-006).</p></div></div>
              <dl className="run-summary">
                <FormattedField label="Selling price" value={record.selling_price} formatter={formatMoneyField} />
                <dt>COG</dt><dd>{formatCurrency(record.cog)}</dd>
                <dt>Shipping / unit</dt><dd>{formatCurrency(record.shipping_per_unit)}</dd>
                {/* Intermediate Profitability Engine terms. `null` means the
                    snapshot did not store them -- either the selling price was
                    unusable, or the snapshot predates the field. Never 0. */}
                <dt>Selling fees</dt><dd>{formatCurrency(record.total_fees ?? null)}</dd>
                <dt>Seller proceeds</dt><dd>{formatCurrency(record.seller_proceeds ?? null)}</dd>
                <dt>Total landed cost</dt><dd>{formatCurrency(record.total_cost ?? null)}</dd>
                <FormattedField label="Profit" value={record.profit} formatter={formatMoneyField} />
                <FormattedField label="ROI" value={record.roi} formatter={formatPercent} />
                <FormattedField label="Margin" value={record.margin} formatter={formatPercent} />
                <FormattedField label="Break-even price" value={record.break_even_price} formatter={formatMoneyField} />
                <FormattedField label="Max COG (target profit)" value={record.max_cog_target_profit} formatter={formatMoneyField} />
                <FormattedField label="Max COG (target ROI)" value={record.max_cog_target_roi} formatter={formatMoneyField} />
              </dl>
            </section>

            {/* RISKS */}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">RISKS</p><h2>HazMat / Bulky</h2><p>Presence and policy-derived severity (ADR-020) -- severity is never shown as externally verified.</p></div></div>
              <dl className="run-summary">
                <dt>HazMat</dt><dd><StatusBadge value={record.hazmat_status ?? "UNKNOWN"} />{record.hazmat_severity && record.hazmat_severity !== "NONE" && <> <StatusBadge value={record.hazmat_severity} /></>}</dd>
                <dt>Bulky</dt><dd><StatusBadge value={record.bulky_status ?? "UNKNOWN"} />{record.bulky_severity && record.bulky_severity !== "NONE" && <> <StatusBadge value={record.bulky_severity} /></>}</dd>
              </dl>
            </section>

            {/* DATA QUALITY */}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">DATA QUALITY</p><h2>{record.issue_count > 0 ? `${record.issue_count} issue${record.issue_count === 1 ? "" : "s"}` : "No issues"}</h2></div></div>
              {record.issues.length > 0 ? (
                <ul className="issues">{record.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
              ) : (
                <p className="text-muted">No data-quality issues recorded for this record.</p>
              )}
            </section>

            <ProvenanceSection record={record} />

            {/* MARKET -- explicitly a demo fixture; no live/Keepa integration exists yet. */}
            <section className="panel analytics-panel">
              <div className="panel-heading"><div><p className="eyebrow">MARKET</p><h2>Price trend</h2><p>Illustrative only — JUVAl has no live price-history integration approved or connected yet.</p></div></div>
              <div className="demo-banner"><strong>DEMO_FIXTURE</strong> Simulated series for layout purposes. <strong>NOT VERIFIED</strong> <strong>NOT INFERRED FROM PRODUCTION DATA</strong> — not connected to Amazon or any market data provider.</div>
              {Number.isFinite(Number(record.selling_price.value)) ? (
                <>
                  <div className="segmented-control" aria-label="Market chart type">
                    <button type="button" className={marketChart === "line" ? "selected" : ""} aria-pressed={marketChart === "line"} onClick={() => setMarketChart("line")}>Line</button>
                    <button type="button" className={marketChart === "bar" ? "selected" : ""} aria-pressed={marketChart === "bar"} onClick={() => setMarketChart("bar")}>Bar</button>
                  </div>
                  <AnalyticsChart chartType={marketChart} data={demoPriceSeries(record.record_ref, Number(record.selling_price.value))} />
                </>
              ) : <p className="text-muted">Market fixture unavailable because no selling price was recorded.</p>}
            </section>

            {/* ACTIONS */}
            <section className="panel">
              <p className="eyebrow">ACTIONS</p>
              <div className="asset-actions" style={{ marginTop: 8 }}>
                {executionId && <Link to={`/runs/${encodeURIComponent(executionId)}`} className="secondary-button">Back to Run Detail</Link>}
                <Link to="/products" className="secondary-button">Back to Catalog</Link>
              </div>
            </section>
          </>
        )
      })()}
    </>
  )
}
