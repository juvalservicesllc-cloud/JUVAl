import { join } from "node:path"
import { API, DIR, apiRecord, downloadedRows, expect, exportedRows, fixtures, row, test, upload } from "./support"

/**
 * GOLDEN 17 (ADR-053): the supplier suggested price end to end in a real
 * browser against the real API and pipeline. It is evidence only -- the
 * selling price, cost, profit and decision of every row stay the engine's.
 */

test.describe.configure({ mode: "serial" })

const FILE = "suggested-price.xlsx"
const HEADERS = ["supplier_suggested_price_state", "supplier_suggested_price", "supplier_suggested_price_currency", "supplier_suggested_price_status",
  "supplier_suggested_price_raw", "supplier_suggested_price_currency_raw", "supplier_suggested_price_source_reference", "supplier_suggested_price_diagnostics"]
let run = ""

test("preview groups the columns, and the Catalog shows the declared amounts beside the engine's values", async ({ page }) => {
  await page.goto("/import")
  await page.getByLabel("Supplier files").setInputFiles(join(DIR, "files", FILE))
  await page.getByRole("button", { name: `Preview ${FILE}` }).click()
  await expect(page.getByText(/supplier suggested price, does not affect decisions/)).toHaveCount(2)

  run = await upload(page, FILE)
  await page.goto(`/catalog?run=${run}`)
  await expect(page.getByText("3 results", { exact: true })).toBeVisible()
  const header = page.getByRole("columnheader", { name: "Suggested (supplier)" })
  await expect(header.getByRole("button")).toHaveCount(0)               // not sortable: amounts can be in different currencies
  const labels = await page.getByRole("columnheader").allTextContents()
  const at = labels.indexOf("Suggested (supplier)")
  expect([labels[at - 1], labels[at + 1]].map((l) => l.split(" ")[0])).toEqual(["Cost", "Selling"])

  const euro = row(page, "E2E suggested euro")
  await expect(euro.getByRole("cell").nth(5)).toHaveText("24.99 EUR INF")
  await expect(euro.getByRole("cell").nth(6)).toContainText("$30.00")    // the selling price is the file's selling_price
  await expect(euro.getByText("▲ REVIEW")).toBeVisible()
  await expect(row(page, "E2E suggested bad currency").getByRole("cell").nth(5)).toHaveText("invalid INV")
  await expect(row(page, "E2E suggested zero").getByRole("cell").nth(5)).toHaveText("invalid INV")
})

test("Product Detail shows the amount, currency, status and source, and the decision is unchanged", async ({ page }) => {
  await page.goto(`/catalog?run=${run}`)
  await row(page, "E2E suggested euro").getByRole("link", { name: "E2E suggested euro" }).click()
  const panel = page.getByRole("region", { name: "Supplier suggested price", exact: true })
  await expect(panel.getByText("Not used for this decision")).toBeVisible()
  await expect(panel).toContainText("24.99 EUR")
  await expect(panel.getByLabel("Status: INFERRED")).toBeVisible()
  await expect(panel).toContainText(`SUPPLIER_FILE · ${FILE} · row=2;column=supplier_suggested_price`)
  await expect(panel).toContainText("declared_in_uploaded_file")
  await expect(panel).not.toContainText("VERIFIED")
  await expect(panel).not.toContainText("$")
  const decision = page.getByLabel("Decision")
  await expect(decision.getByText("▲ REVIEW")).toBeVisible()
  await expect(decision.getByRole("listitem")).toHaveText(["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."])

  await page.goto(`/run/${run}/product/row_3`)
  const bad = page.getByRole("region", { name: "Supplier suggested price", exact: true })
  await expect(bad).toContainText("Invalid value")
  await expect(bad).toContainText("raw 19.50")
  await expect(bad.getByRole("table", { name: "Supplier suggested price diagnostics" })).toContainText("SUGGESTED_PRICE_CURRENCY_INVALID")
  await expect(bad.getByRole("table")).toContainText("usd")

  for (const [ref, code] of [["row_2", null], ["row_3", "SUGGESTED_PRICE_CURRENCY_INVALID"], ["row_4", "SUGGESTED_PRICE_NOT_POSITIVE"]] as const) {
    const record = await apiRecord(page, run, ref)
    expect([record.decision, record.decision_reason_codes, record.selling_price.value, record.cog]).toEqual(["REVIEW", ["DEMAND_UNKNOWN"], "30", "3"])
    expect(record.supplier_suggested_price.diagnostics.map((d: { code: string }) => d.code)).toEqual(code ? [code] : [])
  }
})

test("the Catalog export, the run download and the API agree on every suggested-price column", async ({ page }) => {
  const expected: Record<string, Record<string, unknown>> = {
    row_2: { supplier_suggested_price_state: "DECLARED", supplier_suggested_price: "24.99", supplier_suggested_price_currency: "EUR",
      supplier_suggested_price_status: "INFERRED", supplier_suggested_price_raw: null, supplier_suggested_price_currency_raw: "EUR",
      supplier_suggested_price_source_reference: "row=2;column=supplier_suggested_price", supplier_suggested_price_diagnostics: null },
    row_3: { supplier_suggested_price: null, supplier_suggested_price_status: "INVALID", supplier_suggested_price_raw: "19.50",
      supplier_suggested_price_currency_raw: "usd", supplier_suggested_price_diagnostics: "SUGGESTED_PRICE_CURRENCY_INVALID" },
    row_4: { supplier_suggested_price: null, supplier_suggested_price_status: "INVALID", supplier_suggested_price_raw: "0",
      supplier_suggested_price_diagnostics: "SUGGESTED_PRICE_NOT_POSITIVE" },
  }
  const exported = await exportedRows(page, run)
  const downloaded = await downloadedRows(page, run)
  for (const [ref, values] of Object.entries(expected)) {
    const e = exported.find((r) => r.record_ref === ref)!
    const d = downloaded.find((r) => r.record_ref === ref)!
    expect(e, `filtered export ${ref}`).toMatchObject({ ...values, decision: "REVIEW" })
    expect(Object.fromEntries(HEADERS.map((h) => [h, d[h]])), `run download ${ref}`).toEqual(Object.fromEntries(HEADERS.map((h) => [h, e[h]])))
    const amount = (await apiRecord(page, run, ref)).supplier_suggested_price.amount
    expect([amount.value, amount.status], `API ${ref}`).toEqual([e.supplier_suggested_price, e.supplier_suggested_price_status])
  }
})

test("a historical snapshot shows NOT_CAPTURED", async ({ page, watch }) => {
  // d7-demand.spec.ts seeds it when both specs run; seed it here when this spec runs alone.
  if ((await page.request.get(`${API}/api/v1/runs/e2e-historical`)).status() === 404) fixtures("seed-history", join(DIR, "juval.db"))
  watch.allow(/http 404 GET .*\/runs\/e2e-historical\/(batch|records\/row_2\/financial)$/)
  watch.allow(/status of 404 .*\/runs\/e2e-historical\/(batch|records\/row_2\/financial)$/)
  await page.goto("/catalog?run=e2e-historical")
  const r = row(page, "E2E historical widget")
  await expect(r.getByRole("cell").nth(5)).toHaveText("—")
  await r.getByRole("link", { name: "E2E historical widget" }).click()
  await expect(page.getByRole("region", { name: "Supplier suggested price", exact: true }))
    .toContainText("This record was processed before the supplier suggested price was captured.")
  const record = await apiRecord(page, "e2e-historical")
  expect([record.supplier_suggested_price, record.supplier_suggested_price_state]).toEqual([null, "NOT_CAPTURED"])
  const exported = (await exportedRows(page, "e2e-historical")).find((x) => x.record_ref === "row_2")!
  expect([exported.supplier_suggested_price_state, exported.supplier_suggested_price]).toEqual(["NOT_CAPTURED", null])
})

test("desktop visual and basic accessibility of the suggested-price screens", async ({ page }, info) => {
  for (const [name, path] of [["catalog-suggested", `/catalog?run=${run}`], ["detail-suggested", `/run/${run}/product/row_2`],
    ["detail-suggested-invalid", `/run/${run}/product/row_3`]]) {
    await page.goto(path)
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1)
    await expect(page.getByText(/Loading/)).toHaveCount(0)
    const audit = await page.evaluate(() => ({
      panelOverflow: [...document.querySelectorAll('[aria-label="Supplier suggested price"]')]
        .map((e) => e.scrollWidth - e.clientWidth).filter((d) => d > 0).length,
      unnamedButtons: [...document.querySelectorAll("button")].filter((b) => !(b.getAttribute("aria-label") || b.textContent?.trim())).length,
      pageOverflow: document.documentElement.scrollWidth - innerWidth,
    }))
    expect(audit, name).toEqual({ panelOverflow: 0, unnamedButtons: 0, pageOverflow: 0 })
    await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true })
  }
})
