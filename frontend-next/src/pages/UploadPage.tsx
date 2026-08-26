import { useState } from "react"
import { createBatch } from "../api/batches"
import { apiErrorMessage } from "../api/client"
import { MAX_FILES, SUPPORTED_EXTENSIONS } from "../api/contract"
import type { BatchResponse, FeesIn, ThresholdsIn } from "../api/types"
import { Badge } from "./shared"

/**
 * Golden's Import screen on the real pipeline (ADR-030).
 *
 * Golden's interaction model is kept: a drop zone, a queue of file cards, a
 * per-file remove, a counter against MAX_FILES, and one submit action. Golden's
 * *engine* is gone — the files go to `POST /api/v1/batches`, the backend
 * importer decides what is a valid row, and each file becomes its own
 * ExecutionRun.
 *
 * Golden's twelve-stage progress display is deliberately not carried over. The
 * API reports a completed batch, not granular progress, so this shows an
 * honestly indeterminate state that names every submitted file instead of an
 * invented percentage.
 */

const SEVERITIES = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

type State =
  | { kind: "idle" }
  | { kind: "submitting"; files: string[] }
  | { kind: "error"; message: string }
  | { kind: "done"; batch: BatchResponse }

const accepted = (file: File) => SUPPORTED_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext))

export function UploadPage({ go }: { go: (path: string) => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [notice, setNotice] = useState("")
  const [state, setState] = useState<State>({ kind: "idle" })

  const [targetProfit, setTargetProfit] = useState("")
  const [targetRoi, setTargetRoi] = useState("")
  const [minMonthlySales, setMinMonthlySales] = useState("")
  const [maxRiskSeverity, setMaxRiskSeverity] = useState("")
  const [allowUnknownRisk, setAllowUnknownRisk] = useState(false)
  const [referralFee, setReferralFee] = useState("")
  const [referralFeeRate, setReferralFeeRate] = useState("")
  const [persist, setPersist] = useState(true)

  const busy = state.kind === "submitting"

  /** One ingestion path for the picker and for a drop: the same acceptance
   *  rule, the same cap, the same feedback. */
  function addFiles(incoming: FileList | File[] | null) {
    const candidates = Array.from(incoming ?? [])
    const rejected = candidates.filter((file) => !accepted(file))
    const usable = candidates.filter(accepted)
    const room = MAX_FILES - files.length
    const toAdd = usable.slice(0, Math.max(0, room))
    const overflow = usable.slice(Math.max(0, room))
    const messages = [
      rejected.length ? `Only ${SUPPORTED_EXTENSIONS.join(" and ")} files are supported: ${rejected.map((f) => f.name).join(", ")}.` : "",
      overflow.length ? `At most ${MAX_FILES} files per batch, so these were not queued: ${overflow.map((f) => f.name).join(", ")}.` : "",
    ].filter(Boolean)
    setNotice(messages.join(" "))
    if (toAdd.length) setFiles((current) => [...current, ...toAdd])
  }

  const removeFile = (index: number) => setFiles((current) => current.filter((_, i) => i !== index))

  async function submit() {
    if (!files.length) return setNotice("Choose at least one catalog file to submit.")
    if (!targetProfit || !targetRoi || !minMonthlySales || !maxRiskSeverity || !referralFee || !referralFeeRate) {
      return setNotice("Complete every required threshold and fee. JUVAl does not invent commercial defaults.")
    }
    setNotice("")
    setState({ kind: "submitting", files: files.map((f) => f.name) })
    const thresholds: ThresholdsIn = {
      target_profit: targetProfit, target_roi: targetRoi,
      minimum_estimated_monthly_sales: Number(minMonthlySales),
      maximum_risk_severity: maxRiskSeverity,
      allow_restricted: false, allow_approval_required: false, allow_unknown_risk: allowUnknownRisk,
    }
    const fees: FeesIn = { referral_fee: referralFee, referral_fee_rate: referralFeeRate, fulfillment_fee: "0", other_selling_fees: "0" }
    try {
      const batch = await createBatch(files, thresholds, fees, persist)
      setState({ kind: "done", batch })
    } catch (error: unknown) {
      setState({ kind: "error", message: apiErrorMessage(error) })
    }
  }

  return <>
    <h1>Import supplier files</h1>

    <section className="panel">
      <p>Submit up to {MAX_FILES} supplier files to the real JUVAl validation and processing pipeline. Each file becomes its own auditable run; JUVAl imports {SUPPORTED_EXTENSIONS.join(" and ")}.</p>

      <label
        className={`drop-zone ${dragging ? "dragging" : ""}`}
        onDragEnter={(e) => { e.preventDefault(); if (!busy) setDragging(true) }}
        onDragOver={(e) => { e.preventDefault(); if (!busy) setDragging(true) }}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false) }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!busy) addFiles(e.dataTransfer.files) }}
      >
        Drop CSV or XLSX files here, or choose files
        <input aria-label="Supplier files" type="file" accept=".csv,text/csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" multiple disabled={busy}
          onChange={(e) => { addFiles(e.target.files); e.target.value = "" }} />
      </label>

      <div className="filters">
        <button onClick={() => { setFiles([]); setNotice("") }} disabled={!files.length || busy}>Clear all</button>
        <span>{files.length} / {MAX_FILES} files</span>
      </div>

      {files.length > 0 && <ul className="file-queue" aria-label="File queue">
        {files.map((file, index) => <li key={`${file.name}-${file.size}-${index}`}>
          <span><b>{file.name}</b> <small>{(file.size / 1024).toFixed(0)} KB · {file.name.toLowerCase().endsWith(".csv") ? "CSV" : "XLSX"} · queued</small></span>
          <button onClick={() => removeFile(index)} aria-label={`Remove ${file.name}`} disabled={busy}>Remove</button>
        </li>)}
      </ul>}

      {notice && <p role="alert" className="notice">{notice}</p>}
    </section>

    <section className="panel">
      <h2>Decision configuration</h2>
      <p>These values are submitted to the deterministic pipeline; they are not saved as browser defaults.</p>
      <div className="filters">
        <label>Target profit *<input aria-label="Target profit" value={targetProfit} onChange={(e) => setTargetProfit(e.target.value)} inputMode="decimal" placeholder="e.g. 5" /></label>
        <label>Target ROI *<input aria-label="Target ROI" value={targetRoi} onChange={(e) => setTargetRoi(e.target.value)} inputMode="decimal" placeholder="e.g. 0.3" /></label>
        <label>Minimum monthly sales *<input aria-label="Minimum estimated monthly sales" type="number" min="0" value={minMonthlySales} onChange={(e) => setMinMonthlySales(e.target.value)} placeholder="e.g. 0" /></label>
        <label>Maximum risk severity *<select aria-label="Maximum accepted risk severity" value={maxRiskSeverity} onChange={(e) => setMaxRiskSeverity(e.target.value)}>
          <option value="">Select severity</option>{SEVERITIES.map((s) => <option key={s}>{s}</option>)}
        </select></label>
        <label>Referral fee *<input aria-label="Referral fee" value={referralFee} onChange={(e) => setReferralFee(e.target.value)} inputMode="decimal" placeholder="e.g. 3" /></label>
        <label>Referral fee rate *<input aria-label="Referral fee rate" value={referralFeeRate} onChange={(e) => setReferralFeeRate(e.target.value)} inputMode="decimal" placeholder="e.g. 0.15" /></label>
      </div>
      <p>
        <label><input type="checkbox" checked={allowUnknownRisk} onChange={(e) => setAllowUnknownRisk(e.target.checked)} /> Allow unknown risk</label>
        {" "}
        <label><input type="checkbox" checked={persist} onChange={(e) => setPersist(e.target.checked)} /> Persist this batch for Runs and Catalog</label>
      </p>
      <button onClick={submit} disabled={busy}>{busy ? "Processing…" : files.length > 1 ? `Process ${files.length} files` : "Process catalog"}</button>
    </section>

    {/* Honest indeterminate state: every submitted file is named, and no stage
        or percentage is invented, because the API does not report one. */}
    {state.kind === "submitting" && <section className="panel" aria-live="polite">
      <h2>JUVAl is validating and processing your files</h2>
      <p>{state.files.length === 1 ? <><b>{state.files[0]}</b> has been submitted</> : <><b>{state.files.length} files</b> have been submitted as one batch</>}. The API reports a completed batch rather than granular stage progress, so this status is intentionally indeterminate.</p>
      <ul className="file-queue">{state.files.map((name) => <li key={name}><span><b>{name}</b> <small>submitted · awaiting result</small></span></li>)}</ul>
    </section>}

    {state.kind === "error" && <section className="panel">
      <h2>Batch not completed</h2>
      <p role="alert" className="notice">{state.message}</p>
      <p>No successful backend result is being shown as a completed batch.</p>
      <button onClick={() => setState({ kind: "idle" })}>Try again</button>
    </section>}

    {state.kind === "done" && <section className="panel">
      <h2>Batch result <Badge>{state.batch.status}</Badge></h2>
      <p>{state.batch.succeeded_files} of {state.batch.total_files} file(s) processed · {state.batch.records_total} records · {state.batch.warning_count} warning(s)</p>
      {!state.batch.persisted && <p className="notice">This batch was not persisted, so it will not appear in Runs or Catalog.</p>}
      <button onClick={() => go(`/batch/${encodeURIComponent(state.batch.batch_id)}`)}>Open batch</button>
      <button onClick={() => { setFiles([]); setState({ kind: "idle" }) }}>New batch</button>
    </section>}
  </>
}
