import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
// Reuses the real backend fixture -- no fixture duplicated for the
// frontend, same file the Python test suite already uses.
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

test("upload Excel -> real backend -> results -> download", async ({ page }) => {
  await page.goto("/upload")

  await page.getByLabel(/catalog \(\.xlsx or \.csv\)/i).setInputFiles(FIXTURE)
  await page.getByLabel(/target profit/i).fill("5")
  await page.getByLabel(/target roi/i).fill("0.3")
  await page.getByLabel(/ventas mensuales/i).fill("0")
  await page.getByLabel(/severidad de riesgo máxima/i).selectOption("LOW")
  await page.getByLabel(/referral fee \*/i).fill("3")
  await page.getByLabel(/referral fee rate/i).fill("0.15")
  await page.getByLabel(/fulfillment fee/i).fill("2")

  await page.getByRole("button", { name: /procesar/i }).click()

  await expect(page.getByText("PARTIAL_SUCCESS")).toBeVisible({ timeout: 15_000 })
  // Same fixture/thresholds as the backend's own test_pipeline_end_to_end.py
  await expect(page.getByText("4", { exact: true })).toBeVisible() // records_processed
  await expect(page.getByText(/B0TESTAAA1/)).toBeVisible() // real ASIN from the real Core
  await expect(page.getByText(/\[VERIFIED\]/).first()).toBeVisible() // provenance preserved, not flattened

  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("link", { name: /download results/i }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/)
})
