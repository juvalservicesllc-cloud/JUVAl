import { requestJson } from "./client"
import type { RunSummaryOut, RunsListResponse } from "./types"

export async function listRuns(limit = 100, signal?: AbortSignal): Promise<RunsListResponse> {
  return await requestJson(`api/v1/runs?limit=${limit}`, { signal }) as RunsListResponse
}

export async function getRun(executionId: string, signal?: AbortSignal): Promise<RunSummaryOut> {
  return await requestJson(`api/v1/runs/${encodeURIComponent(executionId)}`, { signal }) as RunSummaryOut
}
