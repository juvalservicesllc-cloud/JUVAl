import { ApiError, requestJson } from "./client"
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

  return await requestJson("api/v1/batches", { method: "POST", body: form, signal }) as BatchResponse
}

export async function getBatch(batchId: string, signal?: AbortSignal): Promise<BatchResponse> {
  return await requestJson(`api/v1/batches/${encodeURIComponent(batchId)}`, { signal }) as BatchResponse
}

/** The batch a run belongs to, or `null` when it was submitted on its own
 *  (the API's 404 there is a normal outcome, not an error). */
export async function getRunBatch(executionId: string, signal?: AbortSignal): Promise<BatchResponse | null> {
  try {
    return await requestJson(`api/v1/runs/${encodeURIComponent(executionId)}/batch`, { signal }) as BatchResponse
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}
