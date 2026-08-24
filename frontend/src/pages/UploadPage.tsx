import { useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, downloadUrl, submitBatch, submitRun } from "../api"
import { apiErrorMessage } from "../api/client"
import { BatchSummary } from "../components/BatchSummary"
import { ResultsTable } from "../components/ResultsTable"
import { RunForm, type RunFormValues } from "../components/RunForm"
import { StatusBadge } from "../components/StatusBadge"
import type { BatchResponse, RunResponse, RunState } from "../types"

function resultMessage(result: RunResponse): string {
  if (result.status === "PARTIAL_SUCCESS") return "Processing completed, but some records or warnings require review before acting on the result."
  return "Processing completed. Review the run details or download the canonical output."
}

export function UploadPage() {
  const [state, setState] = useState<RunState>({ status: "idle" })
  const [submission, setSubmission] = useState<RunFormValues | null>(null)
  const [batchResult, setBatchResult] = useState<BatchResponse | null>(null)

  async function handleSubmit(values: RunFormValues) {
    setSubmission(values)
    setBatchResult(null)
    setState({ status: "processing" })
    try {
      if (values.files.length > 1) {
        setBatchResult(await submitBatch(values.files, values.thresholds, values.fees, values.persist))
        setState({ status: "idle" })
      } else {
        const result = await submitRun(values.file, values.thresholds, values.fees, values.persist)
        setState("message" in result ? { status: "error", message: result.message } : { status: "success", result: result as RunResponse })
      }
    } catch (error) {
      const message = error instanceof ApiError ? apiErrorMessage(error) : error instanceof Error ? error.message : String(error)
      setState({ status: "error", message })
    }
  }

  const busy = state.status === "uploading" || state.status === "processing"
  const result = state.status === "success" ? state.result : null

  return <>
    <div className="page-intro"><div><p className="eyebrow">NEW RUN</p><h2>Upload catalog</h2><p>Submit up to ten supplier files to the real JUVAl validation and processing pipeline. Each file becomes its own auditable run.</p></div></div>
    <section className="panel upload-panel">
      <RunForm disabled={busy} onSubmit={handleSubmit} />

      <div className="status" aria-live="polite" aria-busy={busy}>
        {state.status === "idle" && !batchResult && <p>Choose one or more catalog files, declare the processing configuration, then submit the run.</p>}
        {busy && <div className="processing-state">
          <p className="eyebrow">PROCESSING</p>
          <h2>JUVAl is validating and processing your catalog</h2>
          {submission
            ? <>
                {/* Every submitted file is named, not just the first: claiming one
                    file is in flight while ten were sent would be a false status.
                    No invented stage or percentage is shown either -- the API
                    reports a completed run, not granular progress. */}
                <p>{submission.files.length === 1 ? <><strong>{submission.files[0].name}</strong> has been submitted</> : <><strong>{submission.files.length} files</strong> have been submitted as one batch</>} with the configuration shown above. The API does not expose granular stage progress, so this status is intentionally indeterminate.</p>
                <ul className="file-queue" aria-label="Files awaiting a processing result">
                  {submission.files.map((file) => <li key={file.name}><span><strong>{file.name}</strong><small>submitted · awaiting result</small></span></li>)}
                </ul>
              </>
            : <p>Waiting for the processing response…</p>}
        </div>}
        {state.status === "error" && <div className="result-state result-error"><p className="eyebrow">RUN NOT COMPLETED</p><h2>Check the submission and try again</h2><p role="alert" className="error">{state.message}</p><p className="text-muted">No successful backend result is being shown as a completed run.</p></div>}
        {batchResult && <div className={`result-state ${batchResult.status === "PARTIAL_SUCCESS" ? "result-partial" : batchResult.status === "FAILED" ? "result-error" : "result-success"}`}>
          <p className="eyebrow">BATCH RESULT</p>
          <h2><StatusBadge value={batchResult.status} /></h2>
          <p>{batchResult.succeeded_files} of {batchResult.total_files} files produced child runs. Failed or rejected files remain listed for follow-up.</p>
          <BatchSummary batch={batchResult} />
          <div className="run-actions">
            {batchResult.persisted && <Link to={`/batches/${encodeURIComponent(batchResult.batch_id)}`} className="primary-button">Open batch</Link>}
          </div>
          {!batchResult.persisted && <p className="review-note">This batch was not persisted, so it cannot be reopened. Enable persistence to keep the batch and its child runs reviewable.</p>}
          <p className="review-note">Retry failed files by submitting them again as a new batch; child runs are never mutated.</p>
        </div>}
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
