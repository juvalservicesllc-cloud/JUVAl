import path from "node:path"
import { fileURLToPath } from "node:url"
import { expect, test } from "@playwright/test"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.resolve(__dirname, "../../tests/fixtures/sample_sourcing_TEST_DATA.xlsx")

// Products is the run-scoped, server-paginated catalog (no global product
// identity, no demo fixtures -- see docs/architecture/API_CONTRACT.md and
// ADR-012). This is a pure responsive/rendering check, deliberately
// state-agnostic: other E2E specs persist runs concurrently against the
// same backend, so whether the catalog is empty or populated at the
// moment this runs is not under this test's control -- only that it
// renders coherently (real data or the real empty state, never demo data).
for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`products renders at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/products")

    await expect(page.getByRole("heading", { name: "Products", level: 2 })).toBeVisible()
    await expect(page.getByText("DEMO MODE")).not.toBeVisible()
    await expect(page.getByText(/no persisted runs yet/i).or(page.getByRole("table"))).toBeVisible({ timeout: 10_000 })
  })
}

// Product Integration Slice 4: server-side pagination/search/filter/sort
// against the real backend (API_CONTRACT.md). Requires JUVAL_EXECUTION_STORE
// -- see e2e/README.md.
test("catalog searches, filters and paginates real persisted records server-side", async ({ page }) => {
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

  await page.goto("/products")
  await expect(page.getByRole("table")).toBeVisible({ timeout: 10_000 })
  await expect(page.getByText(/showing \d+.\d+ of \d+/i)).toBeVisible()

  // Server-side decision filter: the request re-fetches, not a client-side
  // re-render of an already-loaded page.
  const requestPromise = page.waitForRequest((req) => req.url().includes("/records") && req.url().includes("decision=BUY"))
  await page.getByLabel(/filter by decision/i).selectOption("BUY")
  await requestPromise

  // Server-side search, same contract.
  const searchRequest = page.waitForRequest((req) => req.url().includes("/records") && req.url().includes("search="))
  await page.getByLabel(/search catalog/i).fill("B0TEST")
  await searchRequest
})
