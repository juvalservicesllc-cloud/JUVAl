import type { BatchResponse } from "../types"
import { requestJson } from "./client"

function asBatch(body: unknown): BatchResponse {
  if (!body || typeof body !== "object" || typeof (body as Record<string, unknown>).batch_id !== "string" || !Array.isArray((body as Record<string, unknown>).files)) {
    throw new Error("Batch API returned an invalid response")
  }
  return body as BatchResponse
}

export async function getBatch(batchId: string, signal?: AbortSignal): Promise<BatchResponse> {
  return asBatch(await requestJson(`/api/v1/batches/${encodeURIComponent(batchId)}`, { signal }))
}

/**
 * The batch a run was submitted in. Throws ApiError 404 when the run was
 * submitted on its own -- a normal outcome, not an error state, so callers
 * treat 404 as "no batch context" rather than a failure.
 */
export async function getRunBatch(executionId: string, signal?: AbortSignal): Promise<BatchResponse> {
  return asBatch(await requestJson(`/api/v1/runs/${encodeURIComponent(executionId)}/batch`, { signal }))
}
