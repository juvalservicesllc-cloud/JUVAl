import { describe, expect, it } from "vitest"
import { deriveRunAnalytics } from "./runAnalytics"
import type { FieldValueOut, RecordOut } from "./types"

const EMPTY_FV: FieldValueOut = { value: null, status: null }

function fv(value: string, status: FieldValueOut["status"]): FieldValueOut {
  return { value, status }
}

function record(overrides: Partial<RecordOut>): RecordOut {
  return {
    record_ref: "row_1",
    marketplace: "US",
    supplier_sku: "SKU",
    asin: EMPTY_FV,
    upc: EMPTY_FV,
    weight: EMPTY_FV,
    selling_price: EMPTY_FV,
    cog: null,
    shipping_per_unit: null,
    profit: EMPTY_FV,
    roi: EMPTY_FV,
    margin: EMPTY_FV,
    break_even_price: EMPTY_FV,
    max_cog_target_profit: EMPTY_FV,
    max_cog_target_roi: EMPTY_FV,
    hazmat_status: null,
    hazmat_severity: null,
    bulky_status: null,
    bulky_severity: null,
    decision: null,
    decision_reasons: [],
    issue_count: 0,
    issues: [],
    ...overrides,
  }
}

describe("deriveRunAnalytics", () => {
  it("returns zeroed counts and null averages for an empty dataset", () => {
    const analytics = deriveRunAnalytics([])
    expect(analytics.decisionCounts).toEqual({ BUY: 0, REVIEW: 0, PASS: 0, UNKNOWN: 0 })
    expect(analytics.hazmatPresentCount).toBe(0)
    expect(analytics.bulkyPresentCount).toBe(0)
    expect(analytics.neitherRiskFlagCount).toBe(0)
    expect(analytics.recordsWithIssuesCount).toBe(0)
    expect(analytics.averageRoi).toBeNull()
    expect(analytics.averageProfit).toBeNull()
    expect(analytics.averageMargin).toBeNull()
  })

  it("counts decisions by exact value, with null decisions as UNKNOWN", () => {
    const analytics = deriveRunAnalytics([
      record({ decision: "BUY" }),
      record({ decision: "BUY" }),
      record({ decision: "REVIEW" }),
      record({ decision: "PASS" }),
      record({ decision: null }),
    ])
    expect(analytics.decisionCounts).toEqual({ BUY: 2, REVIEW: 1, PASS: 1, UNKNOWN: 1 })
  })

  it("counts risk presence independently -- a record can be both hazmat and bulky", () => {
    const analytics = deriveRunAnalytics([
      record({ hazmat_status: "PRESENT", bulky_status: "PRESENT" }),
      record({ hazmat_status: "PRESENT", bulky_status: "ABSENT" }),
      record({ hazmat_status: "ABSENT", bulky_status: "ABSENT" }),
      record({ hazmat_status: "UNKNOWN", bulky_status: null }),
    ])
    expect(analytics.hazmatPresentCount).toBe(2)
    expect(analytics.bulkyPresentCount).toBe(1)
    expect(analytics.neitherRiskFlagCount).toBe(2)
  })

  it("counts records with any issue", () => {
    const analytics = deriveRunAnalytics([
      record({ issue_count: 0 }),
      record({ issue_count: 1 }),
      record({ issue_count: 3 }),
    ])
    expect(analytics.recordsWithIssuesCount).toBe(2)
  })

  it("averages only VERIFIED/INFERRED values, excluding NOT_FOUND and INVALID -- never as zero", () => {
    const analytics = deriveRunAnalytics([
      record({ roi: fv("0.30", "VERIFIED") }),
      record({ roi: fv("0.50", "INFERRED") }),
      record({ roi: fv("999", "NOT_FOUND") }), // status contradicts value on purpose: proves status gates it, not value presence
      record({ roi: EMPTY_FV }),
      record({ roi: fv("abc", "INVALID") }),
    ])
    expect(analytics.averageRoi).toEqual({ value: 0.4, sampleSize: 2 })
  })

  it("returns null (not 0) when no record has a usable value for that field", () => {
    const analytics = deriveRunAnalytics([
      record({ profit: fv(null as unknown as string, "NOT_FOUND") }),
      record({ profit: fv("bad", "INVALID") }),
    ])
    expect(analytics.averageProfit).toBeNull()
  })

  it("reports sample size alongside the average margin", () => {
    const analytics = deriveRunAnalytics([
      record({ margin: fv("0.10", "VERIFIED") }),
      record({ margin: fv("0.20", "VERIFIED") }),
      record({ margin: fv("0.30", "VERIFIED") }),
    ])
    expect(analytics.averageMargin).toEqual({ value: expect.closeTo(0.2, 10), sampleSize: 3 })
  })
})
