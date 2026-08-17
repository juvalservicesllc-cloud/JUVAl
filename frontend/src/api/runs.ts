import type { RunSummaryOut, RunsListResponse } from "../types"
import { requestJson } from "./client"

const statuses = new Set(["RUNNING", "SUCCESS", "PARTIAL_SUCCESS", "FAILED"])

function isRun(value: unknown): value is RunSummaryOut {
  if (!value || typeof value !== "object") return false
  const run = value as Record<string, unknown>
  return typeof run.execution_id === "string"
    && typeof run.started_at === "string"
    && (run.finished_at === null || typeof run.finished_at === "string")
    && typeof run.status === "string" && statuses.has(run.status)
    && typeof run.input_filename === "string"
    && typeof run.input_hash === "string"
    && typeof run.records_total === "number"
    && typeof run.records_processed === "number"
    && typeof run.records_successful === "number"
    && typeof run.records_with_errors === "number"
    && typeof run.warnings === "number"
}

// GET /api/v1/runs -- newest first, `limit` capped server-side at 100
// (API_CONTRACT.md §2b). Omit `limit` to use the backend default (20).
export async function getRuns(options?: { limit?: number; signal?: AbortSignal }): Promise<RunsListResponse> {
  const path = options?.limit === undefined ? "/api/v1/runs" : `/api/v1/runs?limit=${options.limit}`
  const body = await requestJson(path, { signal: options?.signal })
  if (!body || typeof body !== "object" || !("items" in body) || !Array.isArray(body.items) || !body.items.every(isRun)) {
    throw new Error("Runs API returned an invalid response")
  }
  return { items: body.items }
}
