import { expect, test } from "@playwright/test"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { readFileSync } from "node:fs"

/**
 * Behavioral coverage for the capabilities recovered in this wave:
 * CSV ingestion, percentage ROI/margin semantics, durable batch navigation,
 * per-file batch outcomes and the internal Dashboard analytics.
 *
 * Runs against the real frontend, real FastAPI and real SQLite persistence.
 */

const ROOT = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.resolve(ROOT, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

// Same columns the XLSX fixture declares, so CSV and XLSX are comparable.
const CSV = [
  "marketplace,asin,sku,title,brand,cost,selling_price,hazmat,bulky",
  "US,B0TESTCSV1,CSV-1,Recovered CSV widget,CsvBrand,10,30,false,false",
  "US,B0TESTCSV2,CSV-2,Second CSV widget,CsvBrand,12,20,false,false",
].join("\n")

async function fillConfiguration(page) {
  await page.getByLabel(/target profit/i).fill("5")
  await page.getByLabel(/target roi/i).fill("0.3")
  await page.getByLabel(/minimum estimated monthly sales/i).fill("0")
  await page.getByLabel(/maximum accepted risk severity/i).selectOption("LOW")
  await page.getByLabel(/^referral fee$/i).fill("3")
  await page.getByLabel(/referral fee rate/i).fill("0.15")
  await page.getByLabel(/persist this run/i).check()
}

test("ingests a CSV catalog through the real pipeline and persists it", async ({ page }) => {
  await page.goto("/upload")
  await page.getByLabel(/catalog files/i).setInputFiles({ name: "supplier.csv", mimeType: "text/csv", buffer: Buffer.from(CSV) })
  await expect(page.getByText("1 of 10 files queued")).toBeVisible()
  await expect(page.getByText(/CSV · queued/)).toBeVisible()
  await fillConfiguration(page)
  await page.getByRole("button", { name: /^process catalog$/i }).click()

  await expect(page.getByText("Input file")).toBeVisible({ timeout: 20_000 })
  // The submitted filename survives instead of a generic placeholder.
  await expect(page.getByText("Input file").locator("xpath=following-sibling::dd[1]")).toHaveText("supplier.csv")
  // Both CSV rows became real records with their ASINs preserved.
  await expect(page.getByText("B0TESTCSV1")).toBeVisible()
  await expect(page.getByText("B0TESTCSV2")).toBeVisible()
  await expect(page.getByText("Total records").locator("xpath=following-sibling::dd[1]")).toHaveText("2")
})

test("names every submitted file while a batch is in flight and keeps the batch reachable", async ({ page }) => {
  await page.goto("/upload")
  await page.getByLabel(/catalog files/i).setInputFiles([
    { name: "batch-a.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: readFileSync(FIXTURE) },
    { name: "batch-b.csv", mimeType: "text/csv", buffer: Buffer.from(CSV) },
  ])
  await fillConfiguration(page)
  await page.getByRole("button", { name: /process 2 files/i }).click()

  await expect(page.getByText("BATCH RESULT")).toBeVisible({ timeout: 30_000 })
  // Per-file rows with real counts, and a durable link to the batch itself.
  await expect(page.getByRole("cell", { name: "batch-a.xlsx" })).toBeVisible()
  await expect(page.getByRole("cell", { name: "batch-b.csv" })).toBeVisible()
  await page.getByRole("link", { name: /open batch/i }).click()

  await expect(page).toHaveURL(/\/batches\//)
  await expect(page.getByText("BATCH OUTCOME")).toBeVisible()
  await expect(page.getByRole("cell", { name: "batch-a.xlsx" })).toBeVisible()

  // Reload proves the batch is persisted, not page state.
  await page.reload()
  await expect(page.getByText("BATCH OUTCOME")).toBeVisible()

  // A child run shows its sibling files as batch context.
  await page.getByRole("link", { name: /open run/i }).first().click()
  await expect(page.getByText("BATCH CONTEXT")).toBeVisible()
  await expect(page.getByText("This run", { exact: true })).toBeVisible()
})

test("filters the catalog by ROI as a percentage, not a ratio", async ({ page }) => {
  await page.goto("/products")
  await expect(page.getByLabel(/^catalog run$/i)).toBeVisible({ timeout: 20_000 })

  const request = page.waitForRequest((candidate) => candidate.url().includes("min_roi="))
  await page.getByLabel("Minimum ROI percentage").fill("30")
  const url = new URL((await request).url())

  // The user typed 30 (percent); the canonical query carries the ratio.
  expect(url.searchParams.get("min_roi")).toBe("0.3")
  await expect(page.getByText(/ROI ≥ 30%/)).toBeVisible()
})

test("shows internal analytics derived from canonical fields only", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByText("SELECTED RUN")).toBeVisible({ timeout: 20_000 })

  await expect(page.getByText("SOURCING SPREAD")).toBeVisible()
  await expect(page.getByText("BRAND MIX")).toBeVisible()
  await expect(page.getByText("DATA QUALITY BY TYPE")).toBeVisible()
  // Every panel states its rule rather than charting an assumed value.
  await expect(page.getByText(/VERIFIED selling price and a recorded COG/i)).toBeVisible()
})

test("keeps a media slot for product imagery without inventing a picture", async ({ page }) => {
  await page.goto("/products")
  await expect(page.getByLabel(/^catalog run$/i)).toBeVisible({ timeout: 20_000 })

  await expect(page.getByRole("img", { name: /no product image available/i }).first()).toBeVisible()
  expect(await page.locator("table img").count()).toBe(0)
})
