import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

// Closes the vertical slice smoke.spec.ts does not cover: persist=true
// on Upload must make the run appear in GET /api/v1/runs (ADR-019).
// Requires the backend to have JUVAL_EXECUTION_STORE configured -- see
// e2e/README.md.
test("persisted run appears in Runs history", async ({ page }) => {
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

  const executionId = await page.getByText("Execution ID").locator("xpath=following-sibling::dd[1]").innerText()

  await page.goto("/runs")
  await expect(page.getByText(executionId)).toBeVisible({ timeout: 10_000 })
  // StatusBadge renders "_" as a space (see components/StatusBadge.tsx).
  await expect(page.getByText("PARTIAL SUCCESS").first()).toBeVisible()
})
