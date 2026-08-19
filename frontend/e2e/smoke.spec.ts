import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
// Reuses the real backend fixture -- no frontend fixture is duplicated.
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

test("upload Excel -> real backend -> review-ready result -> download", async ({ page }) => {
  await page.goto("/upload")

  await page.getByLabel(/catalog workbook/i).setInputFiles(FIXTURE)
  await page.getByLabel(/target profit/i).fill("5")
  await page.getByLabel(/target roi/i).fill("0.3")
  await page.getByLabel(/minimum estimated monthly sales/i).fill("0")
  await page.getByLabel(/maximum accepted risk severity/i).selectOption("LOW")
  await page.getByLabel(/^referral fee$/i).fill("3")
  await page.getByLabel(/referral fee rate/i).fill("0.15")
  await page.getByLabel(/fulfillment fee/i).fill("2")

  await page.getByRole("button", { name: /process catalog/i }).click()

  await expect(page.getByText("PARTIAL SUCCESS")).toBeVisible({ timeout: 15_000 })
  // Same fixture/thresholds as the backend's pipeline integration test.
  await expect(page.getByText("4", { exact: true })).toBeVisible()
  await expect(page.getByText(/B0TESTAAA1/)).toBeVisible()
  await expect(page.getByText("VERIFIED", { exact: true }).first()).toBeVisible()

  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("link", { name: /download results/i }).click()
  expect((await downloadPromise).suggestedFilename()).toMatch(/\.xlsx$/)
})
