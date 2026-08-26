import { apiUrl, requestJson } from "./client"
import { percentInputToRatio } from "./contract"
import type { CatalogQuery, RunRecordsResponse, RunsListResponse } from "./types"

/** Every filter, sort and page is a server-side query parameter
 *  (API_CONTRACT.md). This client never fetches more than one page and never
 *  re-derives filtering or sorting in the browser — which is exactly what the
 *  Golden demo did locally, and the single biggest thing productionization
 *  changes underneath an unchanged UI. */
export function catalogSearchParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams()
  params.set("limit", String(query.limit))
  params.set("offset", String(query.offset))
  params.set("sort", query.sort)
  params.set("direction", query.direction)
  params.set("confidence", query.confidence)
  if (query.search) params.set("search", query.search)
  if (query.decision && query.decision !== "ALL") params.set("decision", query.decision)
  const roi = percentInputToRatio(query.minRoi)
  const margin = percentInputToRatio(query.minMargin)
  if (roi) params.set("min_roi", roi)
  if (query.minProfit.trim() !== "" && Number.isFinite(Number(query.minProfit))) params.set("min_profit", query.minProfit)
  if (margin) params.set("min_margin", margin)
  if (query.hazmat) params.set("hazmat", query.hazmat)
  if (query.bulky) params.set("bulky", query.bulky)
  if (query.provenanceField) params.set("provenance_field", query.provenanceField)
  if (query.provenanceStatus) params.set("provenance_status", query.provenanceStatus)
  return params
}

export async function getRuns(signal?: AbortSignal): Promise<RunsListResponse> {
  return await requestJson("api/v1/runs?limit=100", { signal }) as RunsListResponse
}

export async function getRunRecords(executionId: string, query: CatalogQuery, signal?: AbortSignal): Promise<RunRecordsResponse> {
  const params = catalogSearchParams(query)
  return await requestJson(`api/v1/runs/${encodeURIComponent(executionId)}/records?${params}`, { signal }) as RunRecordsResponse
}

/** The export must issue the identical canonical query the table is showing,
 *  percentage conversion included, or the file would not match the view.
 *  Pagination is dropped on purpose: an export covers the whole filtered set. */
export function filteredExportUrl(executionId: string, query: CatalogQuery): string {
  const params = catalogSearchParams(query)
  params.delete("limit")
  params.delete("offset")
  return apiUrl(`api/v1/runs/${encodeURIComponent(executionId)}/records/export?${params}`)
}
