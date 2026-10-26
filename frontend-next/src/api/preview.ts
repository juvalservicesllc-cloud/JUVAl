import { requestJson } from "./client"
import type { ImportPreviewResponse } from "./types"

/** POST /api/v1/runs/preview — validate-only. The server's importer reads the
 *  file exactly as a run would and reports what it decided; it processes,
 *  decides and stores nothing, so no ExecutionRun is created. The browser never
 *  parses the file itself. */
export async function previewImport(file: File, signal?: AbortSignal): Promise<ImportPreviewResponse> {
  const form = new FormData()
  form.append("file", file, file.name)
  return await requestJson("api/v1/runs/preview", { method: "POST", body: form, signal }) as ImportPreviewResponse
}
