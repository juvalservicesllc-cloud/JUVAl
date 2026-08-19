import { useEffect, useState } from "react"
import { Link, useLocation, useParams } from "react-router-dom"
import { ApiError, apiErrorMessage } from "../api/client"
import { getRunRecords } from "../api/records"
import { AnalyticsChart } from "../components/AnalyticsChart"
import { ProvenanceValue } from "../components/ProvenanceValue"
import { StatusBadge } from "../components/StatusBadge"
import type { FieldValueOut, RecordOut } from "../types"

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
  return Number.isFinite(n) ? n.toLocaleString(undefined, { style: "currency", currency: "USD" }) : "—"
}

function Field({ label, value }: { label: string; value: FieldValueOut }) {
  return (
    <>
      <dt>{label}</dt>
      <dd><ProvenanceValue value={value} /></dd>
    </>
  )
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

  useEffect(() => {
    if (passedRecord) return
    if (!executionId || !recordRef) return
    const controller = new AbortController()
    setState({ status: "loading" })
    // No backend capability exists to fetch a single record by record_ref
    // (ADR-012/019: record_ref is only unique within a run, there is no
    // dedicated lookup endpoint). This reuses the same run-scoped records
    // page Run Detail already fetches (up to 100) and matches client-side --
    // it does not invent a new endpoint or query parameter. Direct/refreshed
    // navigation to a record beyond that page size is an honest, disclosed
    // limitation, not a fabricated "not found".
    getRunRecords(executionId, { limit: 100 }, controller.signal)
      .then((response) => {
        const match = response.records.find((r) => r.record_ref === recordRef)
        if (match) {
          setState({ status: "ready", record: match })
        } else {
          setState({
            status: "unavailable",
            message: response.pagination.total > response.records.length
              ? "This record wasn't in the first 100 records of the run and can't be looked up directly yet. Open it from Products (search) or Run Detail instead."
              : "This record could not be found in the run.",
          })
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
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
        return (
          <>
            {/* DECISION + EXPLANATION -- the headline: what did the engine decide, and why. */}
            <section className="panel result-heading">
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
            </section>

            {/* ECONOMICS */}
            <section className="panel">
              <div className="panel-heading"><div><p className="eyebrow">ECONOMICS</p><h2>Profitability</h2><p>Backend-computed only; never recalculated in the browser (ADR-006).</p></div></div>
              <dl className="run-summary">
                <dt>Selling price</dt><dd><ProvenanceValue value={record.selling_price} /></dd>
                <dt>COG</dt><dd>{formatCurrency(record.cog)}</dd>
                <dt>Shipping / unit</dt><dd>{formatCurrency(record.shipping_per_unit)}</dd>
                <Field label="Profit" value={record.profit} />
                <Field label="ROI" value={record.roi} />
                <Field label="Margin" value={record.margin} />
                <Field label="Break-even price" value={record.break_even_price} />
                <Field label="Max COG (target profit)" value={record.max_cog_target_profit} />
                <Field label="Max COG (target ROI)" value={record.max_cog_target_roi} />
              </dl>
            </section>

            {/* MARKET -- explicitly a demo fixture; no live/Keepa integration exists yet. */}
            <section className="panel analytics-panel">
              <div className="panel-heading"><div><p className="eyebrow">MARKET</p><h2>Price trend</h2><p>Illustrative only -- JUVAl has no live price-history integration (Keepa or equivalent) approved or connected yet.</p></div></div>
              <div className="demo-banner"><strong>DEMO_FIXTURE</strong> Simulated series for layout purposes. Not VERIFIED, not INFERRED, not connected to Amazon or any market data provider.</div>
              <AnalyticsChart chartType="line" data={demoPriceSeries(record.record_ref, Number(record.selling_price.value) || 20)} />
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

            {/* ACTIONS */}
            <section className="panel">
              <p className="eyebrow">ACTIONS</p>
              <div className="asset-actions" style={{ marginTop: 8 }}>
                {executionId && <Link to={`/runs/${encodeURIComponent(executionId)}`} className="secondary-button">Back to Run Detail</Link>}
                <Link to="/products" className="secondary-button">Back to Products</Link>
              </div>
            </section>
          </>
        )
      })()}
    </>
  )
}
