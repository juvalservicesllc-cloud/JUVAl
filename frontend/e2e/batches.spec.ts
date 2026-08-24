import { expect, test } from "@playwright/test"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { readFileSync } from "node:fs"

const FIXTURE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

async function fillConfiguration(page) {
  await page.getByLabel(/target profit/i).fill("5")
  await page.getByLabel(/target roi/i).fill("0.3")
  await page.getByLabel(/minimum estimated monthly sales/i).fill("0")
  await page.getByLabel(/maximum accepted risk severity/i).selectOption("LOW")
  await page.getByLabel(/^referral fee$/i).fill("3")
  await page.getByLabel(/referral fee rate/i).fill("0.15")
}

test("processes two valid workbooks as an ordered batch", async ({ page }) => {
  await page.goto("/upload")
  await page.getByLabel(/catalog files/i).setInputFiles([FIXTURE, FIXTURE])
  await expect(page.getByText("2 of 10 files queued")).toBeVisible()
  await fillConfiguration(page)
  await page.getByRole("button", { name: /process 2 files/i }).click()
  await expect(page.getByText("BATCH RESULT")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText("sample_sourcing_TEST_DATA.xlsx").first()).toBeVisible()
})

test("rejects an unsupported sibling without hiding the valid file", async ({ page }) => {
  await page.goto("/upload")
  await page.getByLabel(/catalog files/i).setInputFiles([{ name: "valid.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: readFileSync(FIXTURE) }, { name: "invalid.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from("not-a-workbook") }])
  await fillConfiguration(page)
  await page.getByRole("button", { name: /process 2 files/i }).click()
  await expect(page.getByText("BATCH RESULT")).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText(/PARTIAL SUCCESS/i).first()).toBeVisible()
  // The unreadable sibling is reported by name; the valid file still ran.
  await expect(page.getByRole("cell", { name: /^invalid\.xlsx/ })).toBeVisible()
  await expect(page.getByRole("cell", { name: /^valid\.xlsx/ })).toBeVisible()
})
