import type { ProductRow } from "../types"

// DEMO MODE: temporary presentation data. It never represents a backend response.
// (Dashboard/Runs fixtures were removed once those pages moved to real
// backend data -- see docs/FRONTEND_BACKEND_HANDOFF.md. Only Products,
// still demo, consumes this file now.)
export const products: ProductRow[] = [
  { sku: "WM-10482", product: "Marine Sealant 3 oz", brand: "3M", cost: "$8.40", asin: "B0000AY6CA", asinStatus: "VERIFIED", hazmat: false, bulky: false, decision: "BUY" },
  { sku: "WM-20914", product: "Deep Cycle Battery", brand: "West Marine", cost: "$119.00", asin: "B09DEMO123", asinStatus: "INFERRED", hazmat: true, bulky: true, decision: "REVIEW" },
  { sku: "WM-33081", product: "Stainless Steel Cleat", brand: "Sea-Dog", cost: "$14.25", asin: null, asinStatus: "NOT_FOUND", hazmat: false, bulky: false, decision: "PASS" },
  { sku: "WM-48102", product: "Automatic Bilge Pump", brand: "Rule", cost: "$54.70", asin: "B000O8F7Z6", asinStatus: "VERIFIED", hazmat: false, bulky: false, decision: "BUY" },
  { sku: "WM-55211", product: "Antifouling Paint", brand: "Pettit", cost: "$92.10", asin: "B0DEMO8812", asinStatus: "INFERRED", hazmat: true, bulky: false, decision: "REVIEW" },
]
