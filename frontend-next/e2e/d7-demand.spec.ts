import { execFileSync } from "node:child_process"
import { writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { test as base, expect, type Page } from "@playwright/test"

/**
 * D7-D (pending demand verification) and D7-B (declared demand evidence) end to
 * end in a real browser against the real API and pipeline. The tests share one
 * disposable database and run in order: later ones use the runs earlier ones
 * created. Declared demand must stay evidence -- every run here is REVIEW.
 */

const API = process.env.JUVAL_E2E_API!
const DIR = process.env.JUVAL_E2E_DIR!
const python = process.env.JUVAL_PYTHON ?? resolve(import.meta.dirname, "../../.venv/bin/python")
const fixtures = (...args: string[]) => execFileSync(python, [join(import.meta.dirname, "fixtures.py"), ...args], { encoding: "utf8" })

const DEMAND_HEADERS = ["demand_evidence_state", "demand_declared_units", "demand_status", "demand_raw_value", "demand_window_start", "demand_window_end",
  "demand_observed_at", "demand_population", "demand_method", "demand_source_reference", "demand_diagnostics"]

/** Fails a test on any console error, uncaught exception or HTTP >= 400 it did not declare as expected. */
const test = base.extend<{ watch: { allow: (pattern: RegExp) => void } }>({
  watch: [async ({ page }, use) => {
    const allowed: RegExp[] = []
    const seen: string[] = []
    page.on("console", (m) => { if (m.type() === "error") seen.push(`console: ${m.text()} @ ${m.location().url}`) })
    page.on("pageerror", (e) => seen.push(`pageerror: ${e.message}`))
    page.on("response", (r) => { if (r.status() >= 400) seen.push(`http ${r.status()} ${r.request().method()} ${r.url()}`) })
    await use({ allow: (pattern) => allowed.push(pattern) })
    expect(seen.filter((s) => !allowed.some((p) => p.test(s))), "unexpected console or HTTP errors").toEqual([])
  }, { auto: true }],
})
test.describe.configure({ mode: "serial" })

const runs: Record<string, string> = {}

async function upload(page: Page, file: string): Promise<string> {
  await page.goto("/import")
  await page.getByLabel("Supplier files").setInputFiles(join(DIR, "files", file))
  await page.getByLabel("Target profit").fill("5")
  await page.getByLabel("Target ROI").fill("0")
  await page.getByLabel("Minimum estimated monthly sales").fill("0")
  await page.getByLabel("Maximum accepted risk severity").selectOption("CRITICAL")
  await page.getByLabel("Referral fee", { exact: true }).fill("1")
  await page.getByLabel("Referral fee rate").fill("0.15")
  await page.getByLabel("Allow unknown risk").check()
  await page.getByRole("button", { name: "Process catalog" }).click()
  await expect(page.getByRole("heading", { name: /Batch result/ })).toBeVisible()
  await page.getByRole("button", { name: "Open batch" }).click()
  const open = page.getByRole("row").filter({ hasText: file }).getByRole("link", { name: "Open run" })
  const id = decodeURIComponent((await open.getAttribute("href"))!.replace("/runs/", ""))
  runs[file] = id
  return id
}

const markTab = (page: Page) => page.evaluate(() => { (window as unknown as { e2eTab: number }).e2eTab = 1 })
/** Same tab, same document: no new page opened and the marker survived (no reload). */
async function expectSameTab(page: Page) {
  expect(page.context().pages()).toHaveLength(1)
  expect(await page.evaluate(() => (window as unknown as { e2eTab?: number }).e2eTab)).toBe(1)
}

const row = (page: Page, title: string) => page.getByRole("row").filter({ has: page.getByRole("link", { name: title, exact: true }) })
const apiRecord = async (page: Page, run: string, ref = "row_2") => (await page.request.get(`${API}/api/v1/runs/${run}/records/${ref}`)).json()

async function exportedRows(page: Page, run: string): Promise<Record<string, unknown>[]> {
  await page.goto(`/catalog?run=${encodeURIComponent(run)}`)
  await expect(page.getByText(/^\d+ results?$/)).toBeVisible()
  // Chromium starts the noopener popup's download before Playwright announces the popup, so the
  // download event cannot be awaited reliably; the request the button made is fetched again instead.
  const exported = page.context().waitForEvent("request", (r) => new URL(r.url()).pathname.endsWith("/records/export"))
  await page.getByRole("button", { name: /^Export/ }).click()
  return workbookRows(page, (await exported).url(), `export-${run}.xlsx`)
}

const downloadedRows = (page: Page, run: string) => workbookRows(page, `${API}/api/v1/runs/${run}/download`, `download-${run}.xlsx`)

async function workbookRows(page: Page, url: string, name: string): Promise<Record<string, unknown>[]> {
  const response = await page.request.get(url)
  expect(response.status()).toBe(200)
  writeFileSync(join(DIR, name), await response.body())
  const [headers, ...rows] = JSON.parse(fixtures("dump", join(DIR, name))) as unknown[][]
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h as string, r[i]])))
}

test("empty and loading states before any run exists", async ({ page }) => {
  await page.route("**/api/v1/runs?*", async (route) => { await new Promise((r) => setTimeout(r, 1500)); await route.continue() })
  await page.goto("/catalog")
  await expect(page.getByText("Loading persisted runs…")).toBeVisible()
  await expect(page.getByText(/No persisted runs yet/)).toBeVisible()
  await page.unroute("**/api/v1/runs?*")
  await page.goto("/")
  await expect(page.getByRole("button", { name: "Import a file" })).toBeVisible()
})

test("1-2: a file without demand gives REVIEW with DEMAND_UNKNOWN", async ({ page }) => {
  const run = await upload(page, "no-demand.xlsx")
  await markTab(page)
  await page.getByRole("link", { name: "Open run" }).click()
  await expect(page.getByRole("heading", { level: 1, name: "no-demand.xlsx" })).toBeVisible()
  await page.getByRole("button", { name: "Open in Catalog" }).click()
  await expect(page).toHaveURL(new RegExp(`/catalog\\?run=${run}$`))
  await expectSameTab(page)

  const pending = row(page, "E2E pending widget")
  await expect(pending.getByText("▲ REVIEW")).toBeVisible()
  await expect(pending.getByText("demand not verified")).toBeVisible()
  await expect(row(page, "E2E low-profit widget").getByText("▲ REVIEW")).toBeVisible()
  await expect(row(page, "E2E low-profit widget").getByText("demand not verified")).toHaveCount(0)
  await expect(row(page, "E2E loss widget")).toContainText("PASS")
  await expect(page.getByRole("cell", { name: /BUY/ })).toHaveCount(0)

  const record = await apiRecord(page, run)
  expect([record.decision, record.decision_reason_codes, record.review_classification, record.demand_evidence_state])
    .toEqual(["REVIEW", ["DEMAND_UNKNOWN"], "PENDING_DEMAND_VERIFICATION", "NOT_DECLARED"])
  expect((await apiRecord(page, run, "row_3")).decision_reason_codes).toEqual(["PROFIT_BELOW_TARGET", "DEMAND_UNKNOWN"])
})

test("3: the Pending demand verification filter is applied by the server", async ({ page }) => {
  const run = runs["no-demand.xlsx"]
  await page.goto(`/catalog?run=${run}`)
  await expect(page.getByText("3 results", { exact: true })).toBeVisible()
  const request = page.waitForRequest((r) => new URL(r.url()).searchParams.get("review_classification") === "PENDING_DEMAND_VERIFICATION")
  await page.getByLabel("Review status").selectOption("pending")
  await request
  await expect(page.getByText("1 result", { exact: true })).toBeVisible()
  await expect(row(page, "E2E pending widget")).toBeVisible()
  await expect(row(page, "E2E low-profit widget")).toHaveCount(0)
  await expect(page.getByRole("status")).toContainText("not a BUY recommendation")
  await page.getByLabel("Review status").selectOption("")
  await expect(page.getByText("3 results", { exact: true })).toBeVisible()
})

test("4 and 14: the Dashboard counts them and opens the filtered Catalog in the same tab", async ({ page }) => {
  const run = runs["no-demand.xlsx"]
  await page.goto(`/?run=${run}`)
  await markTab(page)
  const panel = page.getByLabel("Pending demand verification")
  await expect(panel).toContainText("1 of 2 REVIEW records are held back only because demand could not be determined")
  await expect(panel).toContainText("they are not BUY")
  await panel.getByRole("button", { name: "Show them in Catalog" }).click()
  await expect(page).toHaveURL(new RegExp(`/catalog\\?run=${run}&review=pending-demand$`))
  await expect(page.getByLabel("Review status")).toHaveValue("pending")
  await expect(page.getByText("1 result", { exact: true })).toBeVisible()
  await expectSameTab(page)
})

test("5 and 14: Product Detail opens from the Catalog link in the same tab and Back returns", async ({ page }) => {
  const run = runs["no-demand.xlsx"]
  await page.goto(`/catalog?run=${run}`)
  await markTab(page)
  await page.getByRole("link", { name: "E2E pending widget", exact: true }).click()
  await expect(page).toHaveURL(`/run/${run}/product/row_2`)
  await expectSameTab(page)
  const decision = page.getByLabel("Decision")
  await expect(decision.getByText("▲ REVIEW")).toBeVisible()
  await expect(decision).toContainText("DEMAND_UNKNOWN: Estimated monthly sales could not be determined.")
  await expect(decision.getByRole("status")).toContainText("this is not a BUY")
  await expect(page.getByRole("region", { name: "Declared demand", exact: true })).toContainText("The file declared no demand columns.")
  await page.goBack()
  await expect(page).toHaveURL(`/catalog?run=${run}`)
  await expect(row(page, "E2E pending widget")).toBeVisible()
  await expectSameTab(page)
})

test("6-9: a declared 1,000,000 units is shown as INFERRED evidence, not used, and the decision stays REVIEW", async ({ page }) => {
  await page.goto("/import")
  await page.getByLabel("Supplier files").setInputFiles(join(DIR, "files", "demand-valid.xlsx"))
  await page.getByRole("button", { name: "Preview demand-valid.xlsx" }).click()
  await expect(page.getByText(/declared demand, does not affect decisions/).first()).toBeVisible()

  const run = await upload(page, "demand-valid.xlsx")
  await page.goto(`/catalog?run=${run}`)
  const r = row(page, "E2E declared million")
  await expect(r.getByText("▲ REVIEW")).toBeVisible()
  await expect(r.getByText("demand not verified")).toBeVisible()
  await expect(r).toContainText("1,000,000")
  await expect(page.getByRole("columnheader", { name: "Declared demand" }).getByRole("button")).toHaveCount(0)

  await r.getByRole("link", { name: "E2E declared million" }).click()
  const panel = page.getByRole("region", { name: "Declared demand", exact: true })
  await expect(panel.getByText("Not used for this decision")).toBeVisible()
  await expect(panel).toContainText("1,000,000 units")
  await expect(panel.getByLabel("Status: INFERRED")).toBeVisible()
  await expect(panel).toContainText("USER_INPUT · demand-valid.xlsx · row=2;column=estimated_monthly_sales")
  await expect(panel).toContainText("synthetic E2E declaration")
  await expect(panel).toContainText("2026-09-01T00:00:00-04:00 → 2026-10-01T00:00:00-04:00")
  await expect(panel).not.toContainText("VERIFIED")
  const decision = page.getByLabel("Decision")
  await expect(decision.getByText("▲ REVIEW")).toBeVisible()
  await expect(decision.getByRole("listitem")).toHaveText(["DEMAND_UNKNOWN: Estimated monthly sales could not be determined."])

  const record = await apiRecord(page, run)
  expect([record.decision, record.decision_reason_codes]).toEqual(["REVIEW", ["DEMAND_UNKNOWN"]])
  const value = record.demand_evidence.observations[0].value
  expect([value.value, value.status, value.provenance.source_type]).toEqual([1000000, "INFERRED", "USER_INPUT"])
})

test("10: an invalid declared value keeps its raw text and diagnostic", async ({ page }) => {
  const run = await upload(page, "demand-invalid.xlsx")
  await page.goto(`/catalog?run=${run}`)
  await expect(row(page, "E2E declared invalid")).toContainText("invalid")
  await page.getByRole("link", { name: "E2E declared invalid" }).click()
  const panel = page.getByRole("region", { name: "Declared demand", exact: true })
  await expect(panel).toContainText("Invalid value")
  await expect(panel).toContainText("raw approx 400")
  await expect(panel.getByLabel("Status: INVALID")).toBeVisible()
  await expect(page.getByRole("table", { name: "Declared demand diagnostics" }).getByRole("row").nth(1))
    .toContainText(/DEMAND_VALUE_INVALID\s*estimated_monthly_sales\s*2\s*approx 400/)
  await expect(page.getByLabel("Decision").getByText("▲ REVIEW")).toBeVisible()
})

test("11: incomplete context keeps the declared value raw and unusable", async ({ page }) => {
  const run = await upload(page, "demand-incomplete.xlsx")
  await page.goto(`/catalog?run=${run}`)
  await expect(row(page, "E2E declared incomplete")).toContainText("not usable")
  await page.getByRole("link", { name: "E2E declared incomplete" }).click()
  const panel = page.getByRole("region", { name: "Declared demand", exact: true })
  await expect(panel).toContainText("No usable declaration")
  const diagnostics = page.getByRole("table", { name: "Declared demand diagnostics" }).getByRole("row")
  await expect(diagnostics.nth(1)).toContainText(/DEMAND_VALUE_NOT_USABLE\s*estimated_monthly_sales\s*2\s*420/)
  await expect(diagnostics.nth(2)).toContainText(/DEMAND_CONTEXT_MISSING\s*demand_observed_at\s*2\s*—/)
  await expect(page.getByLabel("Decision").getByText("▲ REVIEW")).toBeVisible()
  const record = await apiRecord(page, run)
  expect(record.demand_evidence.diagnostics.map((d: { code: string; raw_value: unknown }) => [d.code, d.raw_value]))
    .toEqual([["DEMAND_VALUE_NOT_USABLE", "420"], ["DEMAND_CONTEXT_MISSING", null]])
})

test("13: a historical snapshot shows NOT_CAPTURED and is not classified", async ({ page, watch }) => {
  fixtures("seed-history", join(DIR, "juval.db"))
  watch.allow(/http 404 GET .*\/runs\/e2e-historical\/(batch|records\/row_2\/financial)$/)
  watch.allow(/status of 404 .*\/runs\/e2e-historical\/(batch|records\/row_2\/financial)$/)
  await page.goto("/catalog?run=e2e-historical")
  const r = row(page, "E2E historical widget")
  await expect(r.getByText("▲ REVIEW")).toBeVisible()
  await expect(r.getByText("demand not verified")).toHaveCount(0)
  await expect(r.getByRole("cell").nth(12)).toHaveText("—")
  await r.getByRole("link", { name: "E2E historical widget" }).click()
  await expect(page.getByRole("region", { name: "Declared demand", exact: true })).toContainText("This record was processed before declared demand was captured.")
  await expect(page.getByLabel("Decision")).toContainText("Reason codes were not stored for this earlier record")
  const record = await apiRecord(page, "e2e-historical")
  expect([record.demand_evidence, record.demand_evidence_state, record.review_classification]).toEqual([null, "NOT_CAPTURED", "NOT_CLASSIFIABLE"])
})

test("12: the Catalog export, the run download and the API agree on every demand column", async ({ page, watch }) => {
  watch.allow(/http 404 GET .*\/runs\/e2e-historical\/batch$/)
  const cases: [run: string, expected: Record<string, unknown>][] = [
    [runs["no-demand.xlsx"], { demand_evidence_state: "NOT_DECLARED", demand_declared_units: null, demand_status: null, demand_diagnostics: null }],
    [runs["demand-valid.xlsx"], { demand_evidence_state: "DECLARED", demand_declared_units: 1000000, demand_status: "INFERRED",
      demand_source_reference: "row=2;column=estimated_monthly_sales", demand_method: "synthetic E2E declaration", demand_diagnostics: null }],
    [runs["demand-invalid.xlsx"], { demand_evidence_state: "DECLARED", demand_declared_units: null, demand_status: "INVALID", demand_raw_value: "approx 400",
      demand_diagnostics: "DEMAND_VALUE_INVALID" }],
    [runs["demand-incomplete.xlsx"], { demand_evidence_state: "DECLARED", demand_declared_units: null, demand_status: null,
      demand_diagnostics: "DEMAND_VALUE_NOT_USABLE; DEMAND_CONTEXT_MISSING" }],
    ["e2e-historical", { demand_evidence_state: "NOT_CAPTURED", demand_declared_units: null, demand_diagnostics: null }],
  ]
  for (const [run, expected] of cases) {
    const exported = (await exportedRows(page, run)).find((r) => r.record_ref === "row_2")!
    expect(exported, `filtered export of ${run}`).toMatchObject({ ...expected, decision: "REVIEW" })
    if (run !== "e2e-historical") {                          // a seeded run has no stored source workbook to download
      const downloaded = (await downloadedRows(page, run)).find((r) => r.record_ref === "row_2")!
      expect(Object.fromEntries(DEMAND_HEADERS.map((h) => [h, downloaded[h]])), `run download of ${run}`)
        .toEqual(Object.fromEntries(DEMAND_HEADERS.map((h) => [h, exported[h]])))
    }
    const record = await apiRecord(page, run)
    expect(record.demand_evidence_state).toBe(expected.demand_evidence_state)
    expect(record.decision).toBe("REVIEW")
  }
})

test("error states: a failed request offers Retry and recovers; an unknown record says so", async ({ page, watch }) => {
  const run = runs["no-demand.xlsx"]
  watch.allow(/net::ERR_FAILED|Failed to fetch/)
  watch.allow(/http 404 GET .*\/records\/row_404(\/financial)?$/)
  watch.allow(/status of 404 .*\/records\/row_404(\/financial)?$/)
  await page.route("**/records?*", (route) => route.abort())
  await page.goto(`/catalog?run=${run}`)
  await expect(page.getByRole("alert")).toBeVisible()
  await page.unroute("**/records?*")
  await page.getByRole("button", { name: "Retry" }).click()
  await expect(page.getByText("3 results", { exact: true })).toBeVisible()
  await page.goto(`/run/${run}/product/row_404`)
  await expect(page.getByRole("heading", { name: "Record not found" })).toBeVisible()
})

test("desktop visual and basic accessibility of the D7 screens", async ({ page }, info) => {
  const screens: [name: string, path: string][] = [
    ["dashboard", `/?run=${runs["no-demand.xlsx"]}`],
    ["catalog-pending", `/catalog?run=${runs["no-demand.xlsx"]}&review=pending-demand`],
    ["detail-valid", `/run/${runs["demand-valid.xlsx"]}/product/row_2`],
    ["detail-invalid", `/run/${runs["demand-invalid.xlsx"]}/product/row_2`],
    ["detail-incomplete", `/run/${runs["demand-incomplete.xlsx"]}/product/row_2`],
    ["import", "/import"],
  ]
  for (const [name, path] of screens) {
    await page.goto(path)
    await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1)
    await expect(page.getByText(/Loading/)).toHaveCount(0)
    const audit = await page.evaluate(() => ({
      // The D7 panels must fit their own box (the diagnostics table scrolls inside its .table wrapper by design).
      d7Overflow: [...document.querySelectorAll('[aria-label="Declared demand"], [aria-label="Pending demand verification"]')]
        .map((e) => e.scrollWidth - e.clientWidth).filter((d) => d > 0).length,
      unnamedButtons: [...document.querySelectorAll("button")].filter((b) => !(b.getAttribute("aria-label") || b.textContent?.trim())).length,
      unlabelledControls: [...document.querySelectorAll("input, select")].filter((c) => !(c.getAttribute("aria-label") || c.closest("label"))).length,
      pageOverflow: document.documentElement.scrollWidth - innerWidth,
      themeSwitchClipped: document.querySelector('header [role="switch"]')!.getBoundingClientRect().right > innerWidth,
    }))
    expect(audit, name).toEqual({ d7Overflow: 0, unnamedButtons: 0, unlabelledControls: 0, pageOverflow: 0, themeSwitchClipped: false })
    await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true })
  }
})
