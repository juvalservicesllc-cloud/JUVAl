// Frontend aggregation layer for one ExecutionRun's already-fetched
// records (Dashboard/Run analytics). Deliberately dumb: every number
// here is a count or an average over values the backend already
// computed (profit/ROI/margin/decision/risk) -- this module never
// recalculates any of them, never invents a business rule, and never
// treats a missing/invalid value as zero.
//
// Documented per-metric below (NAME / SOURCE / FORMULA / MISSING POLICY),
// mirrored in docs/FRONTEND_BACKEND_HANDOFF.md so backend aggregation
// can replace this later without changing the semantics.

import type { FieldValueOut, RecordOut } from "./types"

export interface AverageMetric {
  value: number
  sampleSize: number
}

export interface RunAnalytics {
  decisionCounts: { BUY: number; REVIEW: number; PASS: number; UNKNOWN: number }
  hazmatPresentCount: number
  bulkyPresentCount: number
  neitherRiskFlagCount: number
  recordsWithIssuesCount: number
  averageRoi: AverageMetric | null
  averageProfit: AverageMetric | null
  averageMargin: AverageMetric | null
}

// A FieldValue is "usable" for an average the same way the domain
// itself defines it (FieldValue.is_usable, domain/provenance.py):
// VERIFIED or INFERRED only. NOT_FOUND/INVALID are excluded, never
// coerced to 0 -- see docs/FRONTEND_BACKEND_HANDOFF.md "Averages".
function usableNumber(fv: FieldValueOut): number | null {
  if (fv.status !== "VERIFIED" && fv.status !== "INFERRED") return null
  if (fv.value === null) return null
  const parsed = Number(fv.value)
  return Number.isFinite(parsed) ? parsed : null
}

function average(records: RecordOut[], pick: (r: RecordOut) => FieldValueOut): AverageMetric | null {
  const values = records.map(pick).map(usableNumber).filter((v): v is number => v !== null)
  if (values.length === 0) return null
  return { value: values.reduce((sum, v) => sum + v, 0) / values.length, sampleSize: values.length }
}

// DECISION DISTRIBUTION -- SOURCE: RecordOut.decision. FORMULA: count by
// exact value. MISSING POLICY: a null decision (record never reached
// the Decision Engine, e.g. a fatal import row) counts as UNKNOWN, never
// silently dropped or folded into an existing bucket.
//
// RISK OVERVIEW -- SOURCE: RecordOut.hazmat_status/bulky_status. FORMULA:
// count where status === "PRESENT" (RiskStatus, not verification_status
// -- ADR-020, presence only). MISSING POLICY: ABSENT/UNKNOWN both count
// toward "neither present" -- this endpoint does not expose enough to
// distinguish "confirmed absent" from "unknown" (see FRONTEND_BACKEND_HANDOFF.md).
//
// RECORDS WITH ISSUES -- SOURCE: RecordOut.issue_count. FORMULA: count
// where issue_count > 0. This is the one data-quality metric implemented
// this slice -- see FRONTEND_BACKEND_HANDOFF.md for why a broader
// VERIFIED/INFERRED/NOT_FOUND/INVALID rollup across heterogeneous fields
// was NOT implemented (no unambiguous single formula for it yet).
//
// AVERAGE ROI/PROFIT/MARGIN -- SOURCE: RecordOut.roi/profit/margin.
// FORMULA: arithmetic mean over usable values only (see `usableNumber`).
// MISSING POLICY: sampleSize reported alongside every average; null
// (not 0, not omitted) when sampleSize is 0.
export function deriveRunAnalytics(records: RecordOut[]): RunAnalytics {
  const decisionCounts = { BUY: 0, REVIEW: 0, PASS: 0, UNKNOWN: 0 }
  let hazmatPresentCount = 0
  let bulkyPresentCount = 0
  let neitherRiskFlagCount = 0
  let recordsWithIssuesCount = 0

  for (const record of records) {
    if (record.decision === "BUY" || record.decision === "REVIEW" || record.decision === "PASS") {
      decisionCounts[record.decision] += 1
    } else {
      decisionCounts.UNKNOWN += 1
    }

    const hazmatPresent = record.hazmat_status === "PRESENT"
    const bulkyPresent = record.bulky_status === "PRESENT"
    if (hazmatPresent) hazmatPresentCount += 1
    if (bulkyPresent) bulkyPresentCount += 1
    if (!hazmatPresent && !bulkyPresent) neitherRiskFlagCount += 1

    if (record.issue_count > 0) recordsWithIssuesCount += 1
  }

  return {
    decisionCounts,
    hazmatPresentCount,
    bulkyPresentCount,
    neitherRiskFlagCount,
    recordsWithIssuesCount,
    averageRoi: average(records, (r) => r.roi),
    averageProfit: average(records, (r) => r.profit),
    averageMargin: average(records, (r) => r.margin),
  }
}
