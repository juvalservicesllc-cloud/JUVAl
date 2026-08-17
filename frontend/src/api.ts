// Thin HTTP client for docs/architecture/API_CONTRACT.md. No business
// logic -- never computes profit/ROI/decision/severity, only shapes an
// HTTP request and parses the response. The backend base URL is never
// hardcoded (VITE_API_BASE_URL, see .env.example / README).
import type { FeesIn, RunFailedResponse, RunResponse, ThresholdsIn } from "./types"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`)
    this.status = status
    this.body = body
  }
}

export async function submitRun(
  file: File,
  thresholds: ThresholdsIn,
  fees: FeesIn,
  persist: boolean,
): Promise<RunResponse | RunFailedResponse> {
  const form = new FormData()
  form.append("file", file)
  form.append("thresholds", JSON.stringify(thresholds))
  form.append("fees", JSON.stringify(fees))
  form.append("persist", String(persist))

  const response = await fetch(`${API_BASE_URL}/api/v1/runs`, {
    method: "POST",
    body: form,
  })

  const body = await response.json()
  if (response.status === 200) {
    return body as RunResponse
  }
  if (response.status === 422 && body?.status === "FAILED") {
    return body as RunFailedResponse
  }
  throw new ApiError(response.status, body)
}

export function downloadUrl(executionId: string): string {
  return `${API_BASE_URL}/api/v1/runs/${encodeURIComponent(executionId)}/download`
}
