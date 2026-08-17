import type { DashboardSummary, ExecutionRunSummary, ProductRow } from "../types"

// DEMO MODE: temporary presentation data. It never represents a backend response.
export const dashboardSummary: DashboardSummary = {
  totalProducts: 2486,
  processable: 1934,
  excluded: 552,
  hazmat: 87,
  bulky: 142,
  missingAsin: 318,
}

export const products: ProductRow[] = [
  { sku: "WM-10482", product: "Marine Sealant 3 oz", brand: "3M", cost: "$8.40", asin: "B0000AY6CA", asinStatus: "VERIFIED", hazmat: false, bulky: false, decision: "BUY" },
  { sku: "WM-20914", product: "Deep Cycle Battery", brand: "West Marine", cost: "$119.00", asin: "B09DEMO123", asinStatus: "INFERRED", hazmat: true, bulky: true, decision: "REVIEW" },
  { sku: "WM-33081", product: "Stainless Steel Cleat", brand: "Sea-Dog", cost: "$14.25", asin: null, asinStatus: "NOT_FOUND", hazmat: false, bulky: false, decision: "PASS" },
  { sku: "WM-48102", product: "Automatic Bilge Pump", brand: "Rule", cost: "$54.70", asin: "B000O8F7Z6", asinStatus: "VERIFIED", hazmat: false, bulky: false, decision: "BUY" },
  { sku: "WM-55211", product: "Antifouling Paint", brand: "Pettit", cost: "$92.10", asin: "B0DEMO8812", asinStatus: "INFERRED", hazmat: true, bulky: false, decision: "REVIEW" },
]

export const runs: ExecutionRunSummary[] = [
  { executionId: "run-20260817-0942", createdAt: "Aug 17, 2026 · 9:42 AM", status: "SUCCESS", totalRecords: 842, valid: 731, excluded: 111, errors: 0 },
  { executionId: "run-20260816-1618", createdAt: "Aug 16, 2026 · 4:18 PM", status: "PARTIAL_SUCCESS", totalRecords: 1204, valid: 987, excluded: 204, errors: 13 },
  { executionId: "run-20260815-1103", createdAt: "Aug 15, 2026 · 11:03 AM", status: "FAILED", totalRecords: 440, valid: 0, excluded: 0, errors: 440 },
]
