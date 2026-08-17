import type { RunRecordsResponse } from "../types"
import { requestJson } from "./client"

// GET /api/v1/runs/{execution_id}/records (ADR-019). RecordOut is the
// same shape RunResponse.records already carries from POST /api/v1/runs
// -- api.ts's submitRun() trusts that shape without a deep per-field
// runtime check, so this follows the same precedent rather than
// duplicating a large FieldValueOut-by-field validator (see api/products.ts
// for why that extra scrutiny existed there: reconciling a stale demo
// shape, not the case here).
export async function getRunRecords(executionId: string, signal?: AbortSignal): Promise<RunRecordsResponse> {
  const body = await requestJson(`/api/v1/runs/${encodeURIComponent(executionId)}/records`, { signal })
  if (!body || typeof body !== "object" || typeof (body as Record<string, unknown>).execution_id !== "string" || !Array.isArray((body as Record<string, unknown>).records)) {
    throw new Error("Records API returned an invalid response")
  }
  return body as RunRecordsResponse
}
