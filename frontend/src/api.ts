// Thin HTTP client for docs/architecture/API_CONTRACT.md. No business
// logic -- never computes profit/ROI/decision/severity, only shapes an
// HTTP request and parses the response. The backend base URL is never
// hardcoded (VITE_API_BASE_URL, see .env.example / README).
import type { FeesIn, RunFailedResponse, RunResponse, ThresholdsIn } from "./types"
import { ApiError, apiUrl, requestJson } from "./api/client"

export { ApiError }

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

  const body = await requestJson("/api/v1/runs", {
    method: "POST",
    body: form,
  })
  return body as RunResponse | RunFailedResponse
}

export function downloadUrl(executionId: string): string {
  return apiUrl(`/api/v1/runs/${encodeURIComponent(executionId)}/download`)
}
