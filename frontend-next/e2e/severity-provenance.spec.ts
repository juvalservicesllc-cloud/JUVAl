import { join } from "node:path"
import { API, DIR, expect, fixtures, row, test, upload } from "./support"

/**
 * Severity provenance (ADR-020) end to end: the real API and pipeline decide the
 * (status, source type) pair; the browser only puts it into words. Filters,
 * sorting and the decision are unchanged. Screenshots: dark (default) and light,
 * desktop and phone width.
 */

test.describe.configure({ mode: "serial" })

const FILE = "severity-provenance.xlsx"
const HAZMAT = 10, BULKY = 11   // cell index in a Catalog row
let run = ""

test("the Catalog adds a compact source to each risk cell; filters and sorting still work", async ({ page }) => {
  run = await upload(page, FILE)
  await page.goto(`/catalog?run=${run}`)
  await expect(page.getByText("4 results", { exact: true })).toBeVisible()

  const cases: [string, string, string][] = [
    ["E2E hazmat yes", "PRESENT JUVAl", "JUVAl classification (inferred)"],
    ["E2E hazmat no", "ABSENT file", "Absence declared in supplier file"],
    ["E2E hazmat blank", "UNKNOWN N/F", "Not found"],
    ["E2E hazmat unreadable", "UNKNOWN INV", "Invalid in supplier file"],
  ]
  for (const [title, text, label] of cases) {
    const cells = row(page, title).getByRole("cell")
    await expect(cells.nth(HAZMAT)).toHaveText(text)
    await expect(cells.nth(HAZMAT).getByLabel(`HazMat severity provenance: ${label}`)).toHaveAttribute(
      "title", `Severity: ${label} — not an Amazon verification`)
    await expect(cells.nth(BULKY)).toHaveText("ABSENT file")
  }

  await page.getByLabel("Hazmat", { exact: true }).selectOption("PRESENT")
  await expect(page.getByText("1 result", { exact: true })).toBeVisible()
  await expect(row(page, "E2E hazmat yes").getByRole("cell").nth(HAZMAT)).toHaveText("PRESENT JUVAl")
  await page.getByLabel("Hazmat", { exact: true }).selectOption("")
  await page.getByRole("button", { name: /^Hazmat/ }).click()
  await expect(page.getByText("4 results", { exact: true })).toBeVisible()
})

test("Product Detail names each severity source and makes no Amazon claim", async ({ page }) => {
  await page.goto(`/catalog?run=${run}`)
  await row(page, "E2E hazmat yes").getByRole("link", { name: "E2E hazmat yes" }).click()
  const risks = page.getByRole("region", { name: "Risks" })
  await expect(risks).toContainText("HIGH")
  await expect(risks.getByLabel("HazMat severity provenance: JUVAl classification (inferred)")).toHaveText("JUVAl classification (inferred)")
  await expect(risks.getByLabel("Bulky severity provenance: Absence declared in supplier file")).toBeVisible()
  await expect(risks).not.toContainText(/verified by amazon|VERIFIED_SOURCE/i)

  const stored = await (await page.request.get(`${API}/api/v1/runs/${run}/records/row_2`)).json()
  expect([stored.hazmat_severity_status, stored.hazmat_severity_source_type]).toEqual(["INFERRED", "CALCULATED"])
})

test("a historical snapshot keeps its risks and shows no invented source", async ({ page, watch }) => {
  if ((await page.request.get(`${API}/api/v1/runs/e2e-historical`)).status() === 404) fixtures("seed-history", join(DIR, "juval.db"))
  watch.allow(/http 404 GET .*\/runs\/e2e-historical\/(batch|records\/row_2\/financial)$/)
  watch.allow(/status of 404 .*\/runs\/e2e-historical\/(batch|records\/row_2\/financial)$/)
  await page.goto("/catalog?run=e2e-historical")
  const r = row(page, "E2E historical widget")
  await expect(r.getByRole("cell").nth(HAZMAT)).toHaveText("ABSENT")
  await expect(r.getByLabel(/severity provenance/)).toHaveCount(0)
  await r.getByRole("link", { name: "E2E historical widget" }).click()
  const risks = page.getByRole("region", { name: "Risks" })
  await expect(risks).toContainText("ABSENT")
  await expect(risks.getByLabel(/severity provenance/)).toHaveCount(0)
})

test("screenshots: dark and light, desktop and phone", async ({ page }, info) => {
  for (const dark of [true, false]) {
    await page.addInitScript((value) => localStorage.setItem("juval.appearance.dark", value), String(dark))
    for (const [device, size] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]] as const) {
      await page.setViewportSize(size)
      const theme = dark ? "dark" : "light"
      await page.goto(`/catalog?run=${run}`)
      await expect(row(page, "E2E hazmat yes")).toBeVisible()
      await page.screenshot({ path: info.outputPath(`severity-catalog-${theme}-${device}.png`), fullPage: true })
      await row(page, "E2E hazmat yes").getByRole("link", { name: "E2E hazmat yes" }).click()
      await expect(page.getByRole("region", { name: "Risks" })).toBeVisible()
      await page.getByRole("region", { name: "Risks" }).screenshot({ path: info.outputPath(`severity-detail-${theme}-${device}.png`) })
    }
  }
})
