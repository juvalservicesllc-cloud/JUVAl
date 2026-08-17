import type { RunsListItem, RunsResponse } from "../types"
import { requestJson } from "./client"

const statuses = new Set(["SUCCESS", "PARTIAL_SUCCESS", "FAILED"])

function isRun(value: unknown): value is RunsListItem {
  if (!value || typeof value !== "object") return false
  const run = value as Record<string, unknown>
  return typeof run.execution_id === "string"
    && typeof run.created_at === "string"
    && typeof run.status === "string" && statuses.has(run.status)
    && typeof run.total_records === "number"
    && typeof run.valid === "number"
    && typeof run.excluded === "number"
    && typeof run.errors === "number"
}

export async function getRuns(signal?: AbortSignal): Promise<RunsResponse> {
  const body = await requestJson("/api/v1/runs", { signal })
  if (!body || typeof body !== "object" || !("items" in body) || !Array.isArray(body.items) || !body.items.every(isRun)) {
    throw new Error("Runs API returned an invalid response")
  }
  return { items: body.items }
}
