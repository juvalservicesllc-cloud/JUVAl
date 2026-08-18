import type { RunRecordsQuery, RunRecordsResponse } from "../types"
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
