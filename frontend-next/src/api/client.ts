/** Real JUVAl API client for the Golden-first production candidate (ADR-030).
 *
 * `frontend-next/` keeps Golden's application and UI; what it does not keep is
 * Golden's data. Every value that reaches a screen from here comes from the
 * FastAPI backend with its provenance attached — nothing is generated, hashed
 * or simulated in the browser.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  constructor(readonly status: number, readonly body: unknown) {
    super(`API request failed with status ${status}`)
  }
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === "object" && "detail" in error.body) {
    const detail = (error.body as { detail: unknown }).detail
    if (typeof detail === "string" && detail.length <= 300 && !detail.includes("\n")) return detail
  }
  if (error instanceof ApiError) return "The API request failed. Please try again."
  return error instanceof Error ? error.message : String(error)
}

export function apiUrl(path: string): string {
  return new URL(path, `${API_BASE_URL.replace(/\/$/, "")}/`).toString()
}

export async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(apiUrl(path), init)
  let body: unknown
  try { body = await response.json() } catch { body = null }
  if (!response.ok) throw new ApiError(response.status, body)
  return body
}
