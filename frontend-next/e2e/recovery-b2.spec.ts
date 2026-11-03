import { join } from "node:path"
import { API, DIR, expect, fixtures, row, test, upload, workbookRows } from "./support"

test("B2: ROI percent input, canonical records query and XLSX metadata agree", async ({ page }) => {
  const run = await upload(page, "no-demand.xlsx")
  await page.goto(`/catalog?run=${run}`)
  await expect(page.getByText("3 results", { exact: true })).toBeVisible()
  const requested = page.waitForRequest((r) => new URL(r.url()).pathname.endsWith("/records") && new URL(r.url()).searchParams.get("min_roi") === "0.3")
  await page.getByLabel("Minimum ROI filter", { exact: true }).fill("30")
  const url = new URL((await requested).url())
  expect(url.searchParams.get("min_roi")).toBe("0.3")
  await expect(page.getByText("Minimum ROI: 30%", { exact: true })).toBeVisible()
  await expect(page.getByText("2 results", { exact: true })).toBeVisible()
  await expect(row(page, "E2E loss widget")).toHaveCount(0)

  const requestedExport = page.context().waitForEvent("request", (r) => new URL(r.url()).pathname.endsWith("/records/export"))
  await page.getByRole("button", { name: "Export 2 results" }).click()
  const exportUrl = new URL((await requestedExport).url())
  const expectedParams = new URLSearchParams(url.search)
  expectedParams.delete("limit")
  expectedParams.delete("offset")
  expect(exportUrl.searchParams.toString()).toBe(expectedParams.toString())

  const exported = await workbookRows(page, exportUrl.href, "b2-roi.xlsx")
  const metadata = Object.fromEntries(JSON.parse(fixtures("dump", join(DIR, "b2-roi.xlsx"), "query_metadata")))
  expect(JSON.parse(metadata.filters).min_roi).toBe("0.3")
  expect(metadata.units).toBe("min_roi and min_margin are ratios (0.30 = 30%); min_profit and prices are absolute currency amounts")
  const response = await page.request.get(`${API}${url.pathname}?${url.searchParams}`)
  expect(response.status()).toBe(200)
  const records = (await response.json()).records as { record_ref: string; roi: { value: string } }[]
  expect(exported.map((r) => r.record_ref)).toEqual(records.map((r) => r.record_ref))
  expect(exported).toHaveLength(2)
  for (const record of records) {
    expect(Number(record.roi.value)).toBeGreaterThanOrEqual(0.3)
    expect(Number(exported.find((r) => r.record_ref === record.record_ref)!.roi)).toBe(Number(record.roi.value))
  }
})
