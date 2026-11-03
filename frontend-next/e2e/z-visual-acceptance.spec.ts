import { expect, expectSameTab, markTab, row, test, upload } from "./support"

// Owner-review artifacts against the existing disposable API, not production
// acceptance or proof of legacy feature parity. Run last: d7 starts empty.
let run = ""
test.beforeAll(async ({ browser }, info) => {
  const page = await browser.newPage({ baseURL: info.project.use.baseURL })
  try { run = await upload(page, "no-demand.xlsx") } finally { await page.close() }
})

for (const width of [360, 390, 768, 1440]) {
  for (const dark of [false, true]) {
    const mode = dark ? "dark" : "light"
    test(`owner walkthrough: ${width}px ${mode}`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 900 })
      await page.goto("/appearance")
      await page.getByRole("combobox", { name: "Theme" }).selectOption(String(dark))
      await expect(page.getByRole("switch")).toHaveAttribute("aria-checked", String(dark))
      await markTab(page)
      const navigation = page.getByRole("navigation", { name: "Main navigation" })
      const measurements: unknown[] = []

      async function capture(name: string) {
        await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1)
        await expectSameTab(page)
        await expect(page.locator(".app")).toHaveCSS("color-scheme", mode)
        const layout = await page.evaluate(() => ({
          pageOverflow: document.documentElement.scrollWidth - innerWidth,
          unnamedButtons: [...document.querySelectorAll("button")].filter((b) => !(b.getAttribute("aria-label") || b.textContent?.trim())).length,
          sidebarDirection: getComputedStyle(document.querySelector("aside")!).flexDirection,
          navigationDirection: getComputedStyle(document.querySelector("nav")!).flexDirection,
        }))
        expect(layout.pageOverflow, name).toBeLessThanOrEqual(0)
        expect(layout.unnamedButtons, name).toBe(0)
        expect(layout.navigationDirection).toBe(layout.sidebarDirection)
        measurements.push({ name, width, mode, ...layout })
        await page.screenshot({ path: info.outputPath(`${name}-${width}-${mode}.png`), fullPage: true })
      }

      await navigation.getByRole("button", { name: "Dashboard", exact: true }).click()
      await page.getByLabel("Run", { exact: true }).selectOption(run)
      await expect(page.getByRole("region", { name: "Key figures" })).toBeVisible()
      await expect(page.getByLabel("Decision distribution")).toBeVisible()
      await capture("dashboard")

      await navigation.getByRole("button", { name: "Import", exact: true }).click()
      await expect(page.getByRole("heading", { name: "Import supplier files" })).toBeVisible()
      await expect(page.getByLabel("Target profit", { exact: true })).toHaveValue("")
      await capture("upload")

      await navigation.getByRole("button", { name: "Catalog", exact: true }).click()
      await page.getByLabel("Run", { exact: true }).selectOption(run)
      await expect(page.getByText("3 results", { exact: true })).toBeVisible()
      await expect(row(page, "E2E pending widget").getByText("▲ REVIEW")).toBeVisible()
      await capture("catalog")

      await navigation.getByRole("button", { name: "Runs", exact: true }).click()
      const card = page.locator("article").filter({ has: page.getByText(run, { exact: true }) })
      await expect(card).toBeVisible()
      await capture("runs")
      await card.getByRole("button", { name: "Open", exact: true }).click()
      await expect(page.getByRole("heading", { level: 1, name: "no-demand.xlsx" })).toBeVisible()
      await capture("run-detail")
      const downloaded = page.waitForEvent("download")
      await page.getByRole("link", { name: "Download complete run (.xlsx)" }).click()
      const file = await downloaded
      expect(await file.failure()).toBeNull()
      expect(file.suggestedFilename()).toMatch(/\.xlsx$/)
      await file.saveAs(info.outputPath("complete-run.xlsx"))
      await page.getByRole("button", { name: "Open in Catalog", exact: true }).click()
      await row(page, "E2E pending widget").getByRole("link").click()
      await expect(page.getByRole("region", { name: "Decision", exact: true })).toContainText("DEMAND_UNKNOWN")
      await expect(page.getByRole("region", { name: "Economics", exact: true })).toBeVisible()
      await capture("product-detail")

      await navigation.getByRole("button", { name: "Appearance", exact: true }).click()
      const theme = page.getByRole("combobox", { name: "Theme" })
      await expect(theme).toHaveValue(String(dark))
      await expect(theme).toHaveCSS("color-scheme", mode)
      await theme.focus()
      await page.keyboard.press("Tab")
      await page.keyboard.press("Shift+Tab")
      const focus = await theme.evaluate((element) => {
        const box = element.getBoundingClientRect()
        const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)
        return { visible: element.matches(":focus-visible"), unobscured: !!hit && element.contains(hit) }
      })
      expect(focus).toEqual({ visible: true, unobscured: true })
      measurements.push({ name: "theme-keyboard-focus", ...focus })
      await capture("appearance")

      await navigation.getByRole("button", { name: "Methodology", exact: true }).click()
      await expect(page.getByRole("heading", { level: 1, name: "Methodology" })).toBeVisible()
      await capture("methodology")
      if (width <= 760) {
        const sidebar = page.locator("aside")
        await page.evaluate(() => scrollTo(0, 0))
        await expect.poll(async () => (await sidebar.boundingBox())!.y).toBe(0)
        await page.evaluate(() => scrollTo(0, 500))
        await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(0)
        await expect(sidebar).toHaveCSS("position", "sticky")
        await expect.poll(async () => (await sidebar.boundingBox())!.y).toBe(0)
        // Inspect the live viewport, not sticky placement in a full-page stitch.
        await page.screenshot({ path: info.outputPath(`navigation-scrolled-${width}-${mode}.png`), fullPage: false })
        for (const label of ["Dashboard", "Import", "Catalog", "Runs", "Appearance", "Methodology", "Favorites", "Compare"]) {
          const button = navigation.getByRole("button", { name: label, exact: true })
          await button.scrollIntoViewIfNeeded()
          const box = (await button.boundingBox())!
          // Allow at most 1 CSS pixel for fractional scroll alignment.
          expect(box.x).toBeGreaterThanOrEqual(-1)
          expect(box.x + box.width).toBeLessThanOrEqual(width + 1)
        }
        measurements.push({ name: "mobile-sticky", scrollY: await page.evaluate(() => scrollY), sidebar: await sidebar.boundingBox() })
      }
      await info.attach("layout-measurements", { body: Buffer.from(JSON.stringify({ executionId: run, width, mode, measurements }, null, 2)), contentType: "application/json" })
    })
  }
}
