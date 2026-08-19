import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

// Products is the run-scoped, server-paginated catalog; this rendering check
// remains state-agnostic because E2E specs share the configured backend.
for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`products renders at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/products")

    await expect(page.getByRole("heading", { name: "Products", level: 2 })).toBeVisible()
    await expect(page.getByText("DEMO MODE")).not.toBeVisible()
    await expect(page.getByText(/no persisted runs yet/i).or(page.getByRole("table"))).toBeVisible({ timeout: 10_000 })
  })
}

// Requires JUVAL_EXECUTION_STORE -- see e2e/README.md.
test("catalog searches, filters and paginates real persisted records server-side", async ({ page }) => {
  await page.goto("/upload")
  await page.getByLabel(/catalog workbook/i).setInputFiles(FIXTURE)
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

  await page.goto("/products")
  await expect(page.getByRole("table")).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(/showing \d+.\d+ of \d+/i)).toBeVisible()

  // The decision filter must re-fetch the records endpoint.
  const requestPromise = page.waitForRequest((req) => req.url().includes("/records") && req.url().includes("decision=BUY"))
  await page.getByLabel(/filter by decision/i).selectOption("BUY")
  await requestPromise

  // The same is true for search.
  const searchRequest = page.waitForRequest((req) => req.url().includes("/records") && req.url().includes("search="))
  await page.getByLabel(/search catalog/i).fill("B0TEST")
  await searchRequest
})
