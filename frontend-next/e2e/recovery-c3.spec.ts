import { expect, expectSameTab, markTab, test } from "./support"

test("C3: Methodology explains real limits in light and dark, in the same tab", async ({ page }, info) => {
  await page.goto("/appearance")
  await markTab(page)
  await page.getByRole("button", { name: "Methodology", exact: true }).click()
  await expect(page).toHaveURL("/about")
  await expectSameTab(page)
  await expect(page.getByRole("heading", { level: 1, name: "Methodology" })).toBeVisible()
  await expect(page.getByRole("region", { name: "Processing workflow" })).toContainText("DEMAND_UNKNOWN")
  await expect(page.getByRole("region", { name: "Current capabilities" })).toContainText("Amazon and Keepa are not connected")
  for (const dark of [false, true]) {
    if (await page.getByRole("switch").getAttribute("aria-checked") !== String(dark)) await page.getByRole("switch").click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`methodology-${dark ? "dark" : "light"}.png`), fullPage: true })
  }
})
