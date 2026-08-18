import type { RunAnalyticsOut } from "../types"
import { requestJson } from "./client"

// GET /api/v1/runs/{execution_id}/analytics -- the sole source of Dashboard
// aggregates. Never derive these numbers from a fetched RecordOut[] page;
// the backend already computed them against the full, persisted run.
export async function getRunAnalytics(executionId: string, signal?: AbortSignal): Promise<RunAnalyticsOut> {
  const body = await requestJson(`/api/v1/runs/${encodeURIComponent(executionId)}/analytics`, { signal })
  if (
    !body ||
    typeof body !== "object" ||
    typeof (body as Record<string, unknown>).execution_id !== "string" ||
    typeof (body as Record<string, unknown>).records !== "object" ||
    typeof (body as Record<string, unknown>).decisions !== "object" ||
    typeof (body as Record<string, unknown>).risks !== "object" ||
    typeof (body as Record<string, unknown>).provenance !== "object" ||
    typeof (body as Record<string, unknown>).data_quality !== "object" ||
    typeof (body as Record<string, unknown>).profitability !== "object"
  ) {
    throw new Error("Analytics API returned an invalid response")
  }
  return body as RunAnalyticsOut
}
