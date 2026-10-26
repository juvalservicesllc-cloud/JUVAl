import { apiUrl, ApiError } from "./client"
import type { ImportPreviewResponse } from "./types"

/** POST /api/v1/runs/preview — validate-only. The server's importer reads the
 *  file exactly as a run would and reports what it decided; it processes,
 *  decides and stores nothing, so no ExecutionRun is created. The browser never
 *  parses the file itself. */
export async function previewImport(file: File, signal?: AbortSignal): Promise<ImportPreviewResponse> {
  const form = new FormData()
  form.append("file", file, file.name)
  const response = await fetch(apiUrl("api/v1/runs/preview"), { method: "POST", body: form, signal })
  let body: unknown
  try { body = await response.json() } catch { body = null }
  if (!response.ok) throw new ApiError(response.status, body)
  return body as ImportPreviewResponse
}
