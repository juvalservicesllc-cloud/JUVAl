import { expect, expectSameTab, markTab, row, test, upload } from "./support"

test("C2: columns persist without changing records requests or export, in both themes", async ({ page }, info) => {
  const run = await upload(page, "no-demand.xlsx")
  const requests: string[] = []
  page.on("request", (r) => { if (new URL(r.url()).pathname.endsWith("/records")) requests.push(r.url()) })
  await page.goto(`/catalog?run=${run}`)
  await expect(row(page, "E2E pending widget")).toBeVisible()
  const before = requests.at(-1)
  async function exportUrl() {
    const request = page.context().waitForEvent("request", (r) => new URL(r.url()).pathname.endsWith("/records/export"))
    await page.getByRole("button", { name: /^Export/ }).click()
    return (await request).url()
  }
  const exportBefore = await exportUrl()
  await page.getByText("Catalog columns", { exact: true }).click()
  await expect(page.getByLabel("Show Title column")).toBeDisabled()
  await page.getByLabel("Show Cost column").uncheck()
  await page.getByRole("button", { name: "Move ROI up", exact: true }).click()
  await expect(page.getByRole("columnheader", { name: /^Cost/ })).toHaveCount(0)
  expect(await exportUrl()).toBe(exportBefore)
  expect(requests.at(-1)).toBe(before)
  await page.reload()
  await expect(row(page, "E2E pending widget")).toBeVisible()
  expect(requests.at(-1)).toBe(before)
  await expect(page.getByRole("columnheader", { name: /^Cost/ })).toHaveCount(0)
  for (const dark of [false, true]) {
    if (await page.getByRole("switch").getAttribute("aria-checked") !== String(dark)) await page.getByRole("switch").click()
    await page.screenshot({ path: info.outputPath(`catalog-columns-${dark ? "dark" : "light"}.png`), fullPage: true })
  }
  await markTab(page)
  await row(page, "E2E pending widget").getByRole("link").click()
  await expect(page.getByRole("region", { name: "Decision", exact: true })).toBeVisible()
  await expectSameTab(page)
})
