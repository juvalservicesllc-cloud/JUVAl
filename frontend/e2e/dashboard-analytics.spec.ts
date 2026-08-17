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

  // Real KPI totals from the fixture (same numbers test_pipeline_end_to_end.py
  // and smoke.spec.ts already assert): 5 total, 3 successful, 1 with errors.
  const summary = page.locator(".metric-grid")
  await expect(summary.getByText("5")).toBeVisible({ timeout: 10_000 })
  await expect(summary.getByText("3", { exact: true })).toBeVisible()
  await expect(summary.getByText("1", { exact: true })).toBeVisible()

  // Decision distribution and risk overview charts render with real data.
  await expect(page.getByText("How records were decided")).toBeVisible()
  await expect(page.getByText("HazMat / Bulky presence")).toBeVisible()
  await expect(page.getByTestId("analytics-chart").first()).toBeVisible()

  // Averages are computed over usable values only -- never fabricated.
  await expect(page.getByText(/average roi/i)).toBeVisible()
  await expect(page.getByText(/records$/).first()).toBeVisible()

  await page.getByRole("link", { name: /open run detail/i }).click()
  await expect(page).toHaveURL(/\/runs\/.+/)
  await expect(page.getByText(/B0TESTAAA1/)).toBeVisible()
})
