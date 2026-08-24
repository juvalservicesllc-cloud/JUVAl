import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

// Requires JUVAL_EXECUTION_STORE configured -- see e2e/README.md.
test("persisted run appears in Runs history", async ({ page }) => {
  await page.goto("/upload")

  await page.getByLabel(/catalog files/i).setInputFiles(FIXTURE)
  await page.getByLabel(/target profit/i).fill("5")
  await page.getByLabel(/target roi/i).fill("0.3")
  await page.getByLabel(/minimum estimated monthly sales/i).fill("0")
  await page.getByLabel(/maximum accepted risk severity/i).selectOption("LOW")
  await page.getByLabel(/^referral fee$/i).fill("3")
  await page.getByLabel(/referral fee rate/i).fill("0.15")
  await page.getByLabel(/fulfillment fee/i).fill("2")
  await page.getByLabel(/persist this run/i).check()

  await page.getByRole("button", { name: /process catalog/i }).click()
  await expect(page.getByText("PARTIAL SUCCESS").first()).toBeVisible({ timeout: 15_000 })

  const executionId = await page.getByText("Execution ID").locator("xpath=following-sibling::dd[1]").innerText()

  await page.goto("/runs")
  await expect(page.getByText(executionId)).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText("PARTIAL SUCCESS").first()).toBeVisible()

  // Full slice: Runs -> Run Detail -> canonical record/provenance -> download.
  await page.getByRole("link", { name: executionId }).click()
  await expect(page).toHaveURL(new RegExp(`/runs/${executionId}$`))
  await expect(page.getByText(/\.xlsx$/).first()).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(/B0TESTAAA1/)).toBeVisible()
  await expect(page.getByText("VERIFIED", { exact: true }).first()).toBeVisible()

  // Refresh must work from the URL alone, not in-memory state.
  await page.reload()
  await expect(page.getByText(executionId).first()).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(/B0TESTAAA1/)).toBeVisible()

  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("link", { name: /download results/i }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/)

  await page.getByRole("link", { name: "Open Catalog" }).click()
  await expect(page).toHaveURL(/\/products$/)
})

test("unknown execution id shows a not-found state, never demo data", async ({ page }) => {
  await page.goto("/runs/00000000-0000-0000-0000-000000000000")
  await expect(page.getByText(/no run found/i)).toBeVisible({ timeout: 10_000 })
})
