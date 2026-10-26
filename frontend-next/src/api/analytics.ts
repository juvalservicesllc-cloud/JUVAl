import { requestJson } from "./client"
import type { RunAnalyticsOut } from "./types"

/** One database-aggregated summary of a persisted run. The browser never
 *  aggregates records itself (it never holds more than one page of them).
 *  A body without the contract's sections is refused rather than rendered
 *  with guessed values. */
export async function getRunAnalytics(executionId: string, signal?: AbortSignal): Promise<RunAnalyticsOut> {
  const body = await requestJson(`api/v1/runs/${encodeURIComponent(executionId)}/analytics`, { signal }) as Partial<RunAnalyticsOut> | null
  const p = body?.profitability
  if (!body || typeof body.records?.total_records !== "number" || !body.decisions || !body.data_quality || !body.provenance || !body.risks
    || !p?.profit || !p.roi || !p.margin || !body.brands || !Array.isArray(body.issue_types) || !body.price_spread) {
    throw new Error("The analytics response for this run is incomplete.")
  }
  return body as RunAnalyticsOut
}
