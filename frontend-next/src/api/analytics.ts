import { requestJson } from "./client"
import type { RunAnalyticsOut } from "./types"

/** One database-aggregated summary of a persisted run. The browser never
 *  aggregates records itself (it never holds more than one page of them). */
export async function getRunAnalytics(executionId: string, signal?: AbortSignal): Promise<RunAnalyticsOut> {
  return await requestJson(`api/v1/runs/${encodeURIComponent(executionId)}/analytics`, { signal }) as RunAnalyticsOut
}
