import { useEffect, useState } from "react"
import { getRunBatch } from "../api/batches"
import { getRunRecords } from "../api/catalog"
import { apiErrorMessage } from "../api/client"
import type { BatchResponse, RunRecordsResponse } from "../api/types"
import { Badge, ProvenanceBadge } from "./shared"

/** Bounded, read-only preview; independent failures must not hide run metadata. */
export function RunContext({ executionId }: { executionId: string }) {
  const [batch, setBatch] = useState<BatchResponse | null>()
  const [preview, setPreview] = useState<RunRecordsResponse>()
  const [batchError, setBatchError] = useState("")
  const [previewError, setPreviewError] = useState("")
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setBatch(undefined); setPreview(undefined); setBatchError(""); setPreviewError("")
    getRunBatch(executionId, controller.signal).then((value) => { if (!controller.signal.aborted) setBatch(value) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setBatchError(apiErrorMessage(error)) })
    getRunRecords(executionId, { limit: 25, offset: 0, search: "", brand: "", decision: "ALL", sort: "record_ref", direction: "asc", minRoi: "", minProfit: "", minMargin: "", confidence: "INCLUDE_INFERRED", hazmat: "", bulky: "", provenanceField: "", provenanceStatus: "", pendingDemand: false }, controller.signal)
      .then((value) => { if (!controller.signal.aborted) setPreview(value) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setPreviewError(apiErrorMessage(error)) })
    return () => controller.abort()
  }, [executionId, reload])
  return <section className="panel" aria-label="Run context and preview">
    <h2>Batch context</h2>
    {batchError ? <p role="alert">Batch context unavailable: {batchError}</p> : batch === undefined ? <p>Loading batch context…</p> : batch === null ? <p>This run was submitted on its own.</p> : <>
      <p><a href={`/batch/${encodeURIComponent(batch.batch_id)}`}>Open batch</a> · {batch.total_files} files · {batch.status}</p>
      <ul>{batch.files.map((file) => <li key={file.ordinal}>{file.filename}: {file.status}{file.execution_id && <> · <a href={`/runs/${encodeURIComponent(file.execution_id)}`}>Open child run</a></>}</li>)}</ul>
    </>}
    <h2>Record preview</h2>
    {previewError ? <p role="alert">Preview unavailable: {previewError}</p> : !preview ? <p>Loading preview…</p> : <>
      <p>First {preview.records.length} of {preview.pagination.total} records, ordered by record reference. Preview only; full filtering and export remain in Catalog.</p>
      {preview.records.length === 0 ? <p>No persisted records available.</p> : <div className="table"><table aria-label="Run record preview">
        <thead><tr><th>Record</th><th>Title</th><th>Decision</th><th>Issues</th></tr></thead>
        <tbody>{preview.records.map((record) => <tr key={record.record_ref}>
          <td>{record.record_ref}</td><td><a href={`/run/${encodeURIComponent(executionId)}/product/${encodeURIComponent(record.record_ref)}`}>{record.title.value === null ? record.record_ref : String(record.title.value)}</a> {record.title.status ? <ProvenanceBadge status={record.title.status} /> : <small>Not recorded</small>}</td>
          <td>{record.decision ? <Badge>{record.decision}</Badge> : "Not recorded"}</td><td>{record.issue_count}</td>
        </tr>)}</tbody>
      </table></div>}
    </>}
    {(batchError || previewError) && <button onClick={() => setReload((value) => value + 1)}>Retry context and preview</button>}
  </section>
}
