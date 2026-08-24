import { Link } from "react-router-dom"
import { StatusBadge } from "./StatusBadge"
import type { BatchResponse } from "../types"
import { count } from "../format"

/**
 * The included-file table for one multi-file submission.
 *
 * One implementation shared by the Upload result, the Batch page and Run
 * Detail's batch context, so a file's outcome reads identically everywhere.
 *
 * A Batch groups independent child runs; it never merges them. Each row's
 * counts come from that file's own ExecutionRun, and a REJECTED file (never
 * processed) shows no counts at all rather than a misleading zero.
 */
export function BatchSummary({ batch, currentExecutionId }: { batch: BatchResponse; currentExecutionId?: string }) {
  return (
    <>
      <dl className="run-summary">
        <dt>Batch ID</dt><dd className="mono">{batch.batch_id}</dd>
        <dt>Submitted</dt><dd>{new Date(batch.created_at).toLocaleString()}</dd>
        <dt>Files</dt><dd>{batch.total_files} ({batch.succeeded_files} produced a run, {batch.failed_files} did not)</dd>
        <dt>Rows scanned</dt><dd>{count(batch.records_total)}</dd>
        <dt>Records processed</dt><dd>{count(batch.records_processed)}</dd>
        <dt>Records with errors</dt><dd>{count(batch.records_with_errors)}</dd>
        <dt>Warnings</dt><dd>{count(batch.warning_count)}</dd>
      </dl>
      <div className="batch-file-scroll">
        <table className="batch-file-table">
          <caption className="sr-only">Files included in batch {batch.batch_id}</caption>
          <thead>
            <tr><th>#</th><th>File</th><th>Type</th><th>Size</th><th>Status</th><th>Rows</th><th>Processed</th><th>Errors</th><th>Warnings</th><th>Run</th></tr>
          </thead>
          <tbody>
            {batch.files.map((file) => {
              const processed = file.status !== "REJECTED"
              return (
                <tr key={`${file.ordinal}-${file.filename}`} className={file.execution_id && file.execution_id === currentExecutionId ? "batch-file-current" : undefined}>
                  <td className="mono">{file.ordinal + 1}</td>
                  <td>
                    <strong>{file.filename}</strong>
                    {file.errors.length > 0 && <ul className="issues">{file.errors.map((error) => <li key={error}>{error}</li>)}</ul>}
                    {file.warnings.length > 0 && <ul className="issues">{file.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
                  </td>
                  <td>{file.filename.toLowerCase().endsWith(".csv") ? "CSV" : "XLSX"}</td>
                  <td className="numeric-cell">{(file.size_bytes / 1024).toFixed(0)} KB</td>
                  <td><StatusBadge value={file.status} /></td>
                  {/* "—" for a rejected file: it never ran, so it has no count. */}
                  <td className="numeric-cell">{processed ? count(file.records_total) : "—"}</td>
                  <td className="numeric-cell">{processed ? count(file.records_processed) : "—"}</td>
                  <td className="numeric-cell">{processed ? count(file.records_with_errors) : "—"}</td>
                  <td className="numeric-cell">{processed ? count(file.warning_count) : "—"}</td>
                  <td>
                    {file.execution_id && batch.persisted
                      ? file.execution_id === currentExecutionId
                        ? <span className="text-muted">This run</span>
                        : <Link to={`/runs/${encodeURIComponent(file.execution_id)}`}>Open run</Link>
                      : <span className="text-muted">{file.execution_id ? "Not persisted" : "No run"}</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}
