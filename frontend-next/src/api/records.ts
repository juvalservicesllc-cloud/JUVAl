import { requestJson } from "./client"
import type { RecordFinancialOut, RecordOut } from "./types"

const recordPath = (executionId: string, recordRef: string) =>
  `api/v1/runs/${encodeURIComponent(executionId)}/records/${encodeURIComponent(recordRef)}`

/** One immutable snapshot by `(execution_id, record_ref)`; never a page scan.
 *  Unknown run and unknown record share one 404 (non-enumerating). */
export async function getRunRecord(executionId: string, recordRef: string, signal?: AbortSignal): Promise<RecordOut> {
  return await requestJson(recordPath(executionId, recordRef), { signal }) as RecordOut
}

/** Stored ADR-047 evidence for the same identity (§2e); read-only. */
export async function getRecordFinancial(executionId: string, recordRef: string, signal?: AbortSignal): Promise<RecordFinancialOut> {
  return await requestJson(`${recordPath(executionId, recordRef)}/financial`, { signal }) as RecordFinancialOut
}
