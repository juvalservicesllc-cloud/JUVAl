import { execFileSync } from "node:child_process"
import { writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { test as base, expect, type APIResponse, type Page } from "@playwright/test"

/** Helpers shared by the E2E specs. They run against one disposable API and
 *  database (playwright.config.ts); see README.md. */

export const API = process.env.JUVAL_E2E_API!
export const DIR = process.env.JUVAL_E2E_DIR!
const python = process.env.JUVAL_PYTHON ?? resolve(import.meta.dirname, "../../.venv/bin/python")
export const fixtures = (...args: string[]) => execFileSync(python, [join(import.meta.dirname, "fixtures.py"), ...args], { encoding: "utf8" })

export const DEMAND_HEADERS = ["demand_evidence_state", "demand_declared_units", "demand_status", "demand_raw_value", "demand_window_start", "demand_window_end",
  "demand_observed_at", "demand_population", "demand_method", "demand_source_reference", "demand_diagnostics"]

/** Fails a test on any console error, uncaught exception or HTTP >= 400 it did not declare as expected. */
export const test = base.extend<{ watch: { allow: (pattern: RegExp) => void } }>({
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

/** File name -> execution id of the runs uploaded so far in this worker. */
export const runs: Record<string, string> = {}

export async function upload(page: Page, file: string): Promise<string> {
  await page.goto("/import")
  await page.getByLabel("Supplier files").setInputFiles(join(DIR, "files", file))
  await configureUpload(page)
  await page.getByRole("button", { name: "Process catalog" }).click()
  await expect(page.getByRole("heading", { name: /Batch result/ })).toBeVisible()
  await page.getByRole("button", { name: "Open batch" }).click()
  const open = page.getByRole("row").filter({ hasText: file }).getByRole("link", { name: "Open run" })
  const id = decodeURIComponent((await open.getAttribute("href"))!.replace("/runs/", ""))
  runs[file] = id
  return id
}

export async function configureUpload(page: Page) {
  await page.getByLabel("Target profit").fill("5")
  await page.getByLabel("Target ROI").fill("0")
  await page.getByLabel("Minimum estimated monthly sales").fill("0")
  await page.getByLabel("Maximum accepted risk severity").selectOption("CRITICAL")
  await page.getByLabel("Referral fee", { exact: true }).fill("1")
  await page.getByLabel("Referral fee rate").fill("0.15")
  await page.getByLabel("Allow unknown risk").check()
}

export const markTab = (page: Page) => page.evaluate(() => { (window as unknown as { e2eTab: number }).e2eTab = 1 })
/** Same tab, same document: no new page opened and the marker survived (no reload). */
export async function expectSameTab(page: Page) {
  expect(page.context().pages()).toHaveLength(1)
  expect(await page.evaluate(() => (window as unknown as { e2eTab?: number }).e2eTab)).toBe(1)
}

export const row = (page: Page, title: string) => page.getByRole("row").filter({ has: page.getByRole("link", { name: title, exact: true }) })
export const apiRecord = async (page: Page, run: string, ref = "row_2") => (await page.request.get(`${API}/api/v1/runs/${run}/records/${ref}`)).json()

export async function exportedRows(page: Page, run: string): Promise<Record<string, unknown>[]> {
  await page.goto(`/catalog?run=${encodeURIComponent(run)}`)
  await expect(page.getByText(/^\d+ results?$/)).toBeVisible()
  // Chromium starts the noopener popup's download before Playwright announces the popup, so the
  // download event cannot be awaited reliably; the request the button made is fetched again instead.
  const exported = page.context().waitForEvent("request", (r) => new URL(r.url()).pathname.endsWith("/records/export"))
  await page.getByRole("button", { name: /^Export/ }).click()
  return workbookRows(page, (await exported).url(), `export-${run}.xlsx`)
}

export const downloadedRows = (page: Page, run: string) => workbookRows(page, `${API}/api/v1/runs/${run}/download`, `download-${run}.xlsx`)

export async function workbookRows(page: Page, url: string, name: string): Promise<Record<string, unknown>[]> {
  const response = await page.request.get(url)
  return workbookResponseRows(response, name)
}

/** Parse the response actually received, including concurrent exports. */
export async function workbookResponseRows(response: APIResponse, name: string): Promise<Record<string, unknown>[]> {
  expect(response.status()).toBe(200)
  writeFileSync(join(DIR, name), await response.body())
  const [headers, ...rows] = JSON.parse(fixtures("dump", join(DIR, name))) as unknown[][]
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h as string, r[i]])))
}

export { expect }
