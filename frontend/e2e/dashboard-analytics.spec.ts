import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

// Product Integration Slice 3: Dashboard moves from demo KPIs to real
// run analytics. Requires the backend to have JUVAL_EXECUTION_STORE
// configured -- see e2e/README.md.
test("dashboard shows real analytics for the latest persisted run, then opens Run Detail", async ({ page }) => {
  await page.goto("/upload")
  await page.getByLabel(/catalog \(\.xlsx; \.csv pending\)/i).setInputFiles(FIXTURE)
  await page.getByLabel(/target profit/i).fill("5")
  await page.getByLabel(/target roi/i).fill("0.3")
  await page.getByLabel(/ventas mensuales/i).fill("0")
  await page.getByLabel(/severidad de riesgo máxima/i).selectOption("LOW")
  await page.getByLabel(/referral fee \*/i).fill("3")
  await page.getByLabel(/referral fee rate/i).fill("0.15")
  await page.getByLabel(/fulfillment fee/i).fill("2")
  await page.getByLabel(/persist this run/i).check()
  await page.getByRole("button", { name: /procesar/i }).click()
  await expect(page.getByText("PARTIAL_SUCCESS")).toBeVisible({ timeout: 15_000 })

  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible()
  await expect(page.getByText("DEMO MODE")).not.toBeVisible()

  // Real KPI totals from GET /analytics (never fetched/derived from
  // RecordOut[] in the browser -- API_CONTRACT.md). analytics.records.total_records
  // counts persisted snapshots, i.e. records_processed (4 for this fixture,
  // same number smoke.spec.ts asserts) -- not run.records_total (5), which
  // also counts a row that never became a SourcingRecord at all.
  const totalRecordsCard = page.locator("article.metric-card", { hasText: "Total records" })
  await expect(totalRecordsCard).toBeVisible({ timeout: 10_000 })
  await expect(totalRecordsCard.getByText("4", { exact: true })).toBeVisible()

  // Decision distribution and risk overview charts render with real data.
  await expect(page.getByText("How records were decided")).toBeVisible()
  await expect(page.getByRole("heading", { name: "HazMat / Bulky" })).toBeVisible()
  await expect(page.getByTestId("analytics-chart").first()).toBeVisible()

  // Data confidence (provenance) and profitability sections use the
  // backend's own aggregation -- never recalculated in the browser.
  await expect(page.getByText("Provenance by field")).toBeVisible()
  await expect(page.getByText(/average roi/i)).toBeVisible()

  // The decision chart's bar/donut toggle is interactive.
  await page.getByRole("button", { name: "Bars" }).click()
  await expect(page.getByRole("button", { name: "Bars" })).toHaveAttribute("aria-pressed", "true")

  await page.getByRole("link", { name: /open run detail/i }).click()
  await expect(page).toHaveURL(/\/runs\/.+/)
  await expect(page.getByText(/B0TESTAAA1/)).toBeVisible()
})
