import { useState } from "react"
import { ApiError, downloadUrl, submitRun } from "../api"
import { ResultsTable } from "../components/ResultsTable"
import { RunForm, type RunFormValues } from "../components/RunForm"
import type { RunResponse, RunState } from "../types"
import { apiErrorMessage } from "../api/client"

export function UploadPage() {
  const [state, setState] = useState<RunState>({ status: "idle" })
  async function handleSubmit(values: RunFormValues) {
    if (values.file.name.toLowerCase().endsWith(".csv")) {
      setState({ status: "error", message: "CSV is visible for the MVP but needs a backend import contract. Use .xlsx for real processing." })
      return
    }
    setState({ status: "uploading" })
    try {
      setState({ status: "processing" })
      const result = await submitRun(values.file, values.thresholds, values.fees, values.persist)
      setState("message" in result ? { status: "error", message: result.message } : { status: "success", result: result as RunResponse })
    } catch (error) {
      const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
      setState({ status: "error", message })
    }
  }
  const busy = state.status === "uploading" || state.status === "processing"
  return <><div className="page-intro"><div><p className="eyebrow">NEW RUN</p><h2>Upload Catalog</h2><p>Process a supplier catalog through the existing JUVAl backend.</p></div></div><div className="demo-banner"><strong>LIVE API FOR XLSX</strong> CSV selection is UI-only until the backend supports it.</div><section className="panel upload-panel"><RunForm disabled={busy} onSubmit={handleSubmit} /><div className="status" aria-live="polite">{state.status === "idle" && <p>Select a catalog and provide the explicit processing parameters.</p>}{state.status === "uploading" && <p>Uploading catalog…</p>}{state.status === "processing" && <p>Processing catalog…</p>}{state.status === "error" && <p role="alert" className="error">{state.message}</p>}{state.status === "success" && <div className="success"><div className="result-heading"><div><p className="eyebrow">COMPLETE</p><h2>{state.result.status}</h2></div><a href={downloadUrl(state.result.execution_id)} download className="primary-button">Download results</a></div><dl className="run-summary"><dt>Execution ID</dt><dd>{state.result.execution_id}</dd><dt>Total records</dt><dd>{state.result.records_total}</dd><dt>Processed</dt><dd>{state.result.records_processed}</dd><dt>Errors</dt><dd>{state.result.records_with_errors}</dd><dt>Warnings</dt><dd>{state.result.warnings}</dd></dl><ResultsTable records={state.result.records} /></div>}</div></section></>
}
