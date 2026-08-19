import { useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, downloadUrl, submitRun } from "../api"
import { apiErrorMessage } from "../api/client"
import { ResultsTable } from "../components/ResultsTable"
import { RunForm, type RunFormValues } from "../components/RunForm"
import { StatusBadge } from "../components/StatusBadge"
import type { RunResponse, RunState } from "../types"

function resultMessage(result: RunResponse): string {
  if (result.status === "PARTIAL_SUCCESS") return "Processing completed, but some records or warnings require review before acting on the result."
  return "Processing completed. Review the run details or download the canonical output."
}

export function UploadPage() {
  const [state, setState] = useState<RunState>({ status: "idle" })
  const [submission, setSubmission] = useState<RunFormValues | null>(null)

  async function handleSubmit(values: RunFormValues) {
    setSubmission(values)
    setState({ status: "processing" })
    try {
      const result = await submitRun(values.file, values.thresholds, values.fees, values.persist)
      setState("message" in result ? { status: "error", message: result.message } : { status: "success", result: result as RunResponse })
    } catch (error) {
      const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
      setState({ status: "error", message })
    }
  }

  const busy = state.status === "uploading" || state.status === "processing"
  const result = state.status === "success" ? state.result : null

  return <>
    <div className="page-intro"><div><p className="eyebrow">NEW RUN</p><h2>Upload catalog</h2><p>Submit one supplier workbook to the real JUVAl validation and processing pipeline.</p></div></div>
    <section className="panel upload-panel">
      <RunForm disabled={busy} onSubmit={handleSubmit} />

      <div className="status" aria-live="polite" aria-busy={busy}>
        {state.status === "idle" && <p>Choose an Excel workbook, declare the processing configuration, then submit the run.</p>}
        {busy && <div className="processing-state"><p className="eyebrow">PROCESSING</p><h2>JUVAl is validating and processing your catalog</h2><p>{submission ? <><strong>{submission.file.name}</strong> has been submitted with the configuration shown above. The API does not expose granular stage progress, so this status is intentionally indeterminate.</> : "Waiting for the processing response…"}</p></div>}
        {state.status === "error" && <div className="result-state result-error"><p className="eyebrow">RUN NOT COMPLETED</p><h2>Check the submission and try again</h2><p role="alert" className="error">{state.message}</p><p className="text-muted">No successful backend result is being shown as a completed run.</p></div>}
        {result && <div className={`result-state ${result.status === "PARTIAL_SUCCESS" ? "result-partial" : "result-success"}`}>
          <div className="result-heading"><div><p className="eyebrow">{result.status === "PARTIAL_SUCCESS" ? "COMPLETED WITH REVIEW NEEDED" : "COMPLETED"}</p><h2><StatusBadge value={result.status} /></h2><p>{resultMessage(result)}</p></div></div>
          <dl className="run-summary"><dt>Execution ID</dt><dd className="mono">{result.execution_id}</dd><dt>Input file</dt><dd>{result.input_filename}</dd><dt>Total records</dt><dd>{result.records_total}</dd><dt>Processed</dt><dd>{result.records_processed}</dd><dt>Records with errors</dt><dd>{result.records_with_errors}</dd><dt>Warnings</dt><dd>{result.warnings}</dd><dt>Stored for review</dt><dd>{result.persisted ? "Yes" : "No"}</dd></dl>
          <div className="run-actions">
            {result.persisted && <Link to={`/runs/${encodeURIComponent(result.execution_id)}`} className="primary-button">Review run</Link>}
            <a href={downloadUrl(result.execution_id)} download className="secondary-button">Download results</a>
          </div>
          {!result.persisted && <p className="review-note">This run was not persisted, so it cannot be reopened under Runs. Download the output now; enable persistence on the next run to use the review workflow.</p>}
          <div className="result-records"><p className="eyebrow">PROCESSING RESULT</p><ResultsTable records={result.records} executionId={result.execution_id} /></div>
        </div>}
      </div>
    </section>
  </>
}
