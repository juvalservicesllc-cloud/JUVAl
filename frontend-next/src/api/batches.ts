import { apiUrl, ApiError } from "./client"
import { MAX_FILES } from "./contract"
import type { BatchResponse, FeesIn, ThresholdsIn } from "./types"

/**
 * POST /api/v1/batches — the real ingestion path.
 *
 * Golden parsed CSV/XLSX in the browser and produced records locally. Nothing
 * of that survives: the files go to the backend importer, which is the single
 * authority on what is a valid row, and each file becomes its own auditable
 * ExecutionRun. One rejected file never aborts the batch.
 */
export async function createBatch(
  files: File[],
  thresholds: ThresholdsIn,
  fees: FeesIn,
  persist: boolean,
  signal?: AbortSignal,
): Promise<BatchResponse> {
  // The server enforces this independently; the client check is a courtesy so
  // an operator is told before a large upload, never the authority.
  if (files.length === 0) throw new Error("Choose at least one catalog file to submit.")
  if (files.length > MAX_FILES) throw new Error(`A batch may contain at most ${MAX_FILES} files.`)

  const form = new FormData()
  for (const file of files) form.append("files", file, file.name)
  form.append("thresholds", JSON.stringify(thresholds))
  form.append("fees", JSON.stringify(fees))
  form.append("persist", String(persist))

  const response = await fetch(apiUrl("api/v1/batches"), { method: "POST", body: form, signal })
  let body: unknown
  try { body = await response.json() } catch { body = null }
  if (!response.ok) throw new ApiError(response.status, body)
  return body as BatchResponse
}

export async function getBatch(batchId: string, signal?: AbortSignal): Promise<BatchResponse> {
  const response = await fetch(apiUrl(`api/v1/batches/${encodeURIComponent(batchId)}`), { signal })
  let body: unknown
  try { body = await response.json() } catch { body = null }
  if (!response.ok) throw new ApiError(response.status, body)
  return body as BatchResponse
}
