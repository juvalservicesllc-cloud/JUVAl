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

export function apiErrorMessage(error: ApiError): string {
  if (error.body && typeof error.body === "object" && "detail" in error.body) {
    const detail = (error.body as { detail: unknown }).detail
    if (typeof detail === "string" && detail.length <= 300 && !detail.includes("\n")) return detail
  }
  return "The API request failed. Please try again."
}

export function apiUrl(path: string): string {
  return new URL(path, `${API_BASE_URL.replace(/\/$/, "")}/`).toString()
}

export async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(apiUrl(path), init)
  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) throw new ApiError(response.status, body)
  return body
}
