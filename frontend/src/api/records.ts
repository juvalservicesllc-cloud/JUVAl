import type { RecordOut, RunRecordsQuery, RunRecordsResponse } from "../types"
import { requestJson } from "./client"

// GET /api/v1/runs/{execution_id}/records (ADR-019). RecordOut is the
// same shape RunResponse.records already carries from POST /api/v1/runs
// -- api.ts's submitRun() trusts that shape without a deep per-field
// runtime check, so this follows the same precedent rather than
// duplicating a large FieldValueOut-by-field validator (see api/products.ts
// for why that extra scrutiny existed there: reconciling a stale demo
// shape, not the case here).
//
// Query, filter, sort and pagination are entirely server-side
// (API_CONTRACT.md) -- this client never fetches more than one page and
// never re-derives these behaviors in the browser.
function buildQuery(query?: RunRecordsQuery): string {
  if (!query) return ""
  const params = new URLSearchParams()
  if (query.limit !== undefined) params.set("limit", String(query.limit))
  if (query.offset !== undefined) params.set("offset", String(query.offset))
  if (query.search) params.set("search", query.search)
  if (query.decision) params.set("decision", query.decision)
  if (query.sort) params.set("sort", query.sort)
  if (query.direction) params.set("direction", query.direction)
  if (query.min_roi) params.set("min_roi", query.min_roi)
  if (query.min_profit) params.set("min_profit", query.min_profit)
  if (query.min_margin) params.set("min_margin", query.min_margin)
  if (query.confidence) params.set("confidence", query.confidence)
  if (query.hazmat) params.set("hazmat", query.hazmat)
  if (query.bulky) params.set("bulky", query.bulky)
  if (query.provenance_field) params.set("provenance_field", query.provenance_field)
  if (query.provenance_status) params.set("provenance_status", query.provenance_status)
  const serialized = params.toString()
  return serialized ? `?${serialized}` : ""
}

export async function getRunRecords(
  executionId: string,
  query?: RunRecordsQuery,
  signal?: AbortSignal,
): Promise<RunRecordsResponse> {
  const body = await requestJson(`/api/v1/runs/${encodeURIComponent(executionId)}/records${buildQuery(query)}`, { signal })
  if (
    !body ||
    typeof body !== "object" ||
    typeof (body as Record<string, unknown>).execution_id !== "string" ||
    !Array.isArray((body as Record<string, unknown>).records) ||
    typeof (body as Record<string, unknown>).pagination !== "object"
  ) {
    throw new Error("Records API returned an invalid response")
  }
  return body as RunRecordsResponse
}

export async function getRunRecord(
  executionId: string,
  recordRef: string,
  signal?: AbortSignal,
): Promise<RecordOut> {
  const body = await requestJson(
    `/api/v1/runs/${encodeURIComponent(executionId)}/records/${encodeURIComponent(recordRef)}`,
    { signal },
  )
  if (!body || typeof body !== "object" || typeof (body as Record<string, unknown>).record_ref !== "string") {
    throw new Error("Record API returned an invalid response")
  }
  return body as RecordOut
}
