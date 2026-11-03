import { expect, test } from "./support"

test("C1: local appearance, image rejection, persistence and light/dark preview", async ({ page }, info) => {
  await page.goto("/appearance")
  const writes: string[] = []
  page.on("request", (r) => { if (r.method() !== "GET") writes.push(r.url()) })
  await page.getByLabel("Accent hex").fill("#ffffff")
  await expect(page.getByRole("status")).toContainText("Insufficient contrast")
  await page.getByLabel("Logo image").setInputFiles({ name: "bad.svg", mimeType: "image/svg+xml", buffer: Buffer.from("<svg/>") })
  await expect(page.getByRole("alert")).toContainText("SVG is not supported")
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9xkAAAAASUVORK5CYII=", "base64")
  await page.getByLabel("Logo image").setInputFiles({ name: "logo.png", mimeType: "image/png", buffer: png })
  await expect(page.getByAltText("Logo preview")).toBeVisible()
  // Browser-local appearance fixtures, never product or market evidence.
  const backgrounds = await page.evaluate(() => {
    const canvas = document.createElement("canvas")
    canvas.width = canvas.height = 96
    const context = canvas.getContext("2d")!
    return ["light", "dark", "checker"].map((name) => {
      context.fillStyle = name === "dark" ? "#111111" : "#ffffff"
      context.fillRect(0, 0, 96, 96)
      if (name === "checker") {
        context.fillStyle = "#111111"
        context.fillRect(0, 0, 48, 48)
        context.fillRect(48, 48, 48, 48)
      }
      return { name, data: canvas.toDataURL("image/png") }
    })
  })
  async function background(image: typeof backgrounds[number]) {
    await page.getByLabel("Background image").setInputFiles({ name: `${image.name}.png`, mimeType: "image/png", buffer: Buffer.from(image.data.split(",")[1], "base64") })
    await expect.poll(() => page.locator(".app").evaluate((e) => (e as HTMLElement).style.backgroundImage)).toContain(image.data)
  }
  await background(backgrounds[0])
  await expect.poll(() => page.evaluate(() => localStorage.getItem("juval.appearance.background"))).toContain("data:image/png;base64,")
  await page.reload()
  await expect(page.getByLabel("Accent hex")).toHaveValue("#ffffff")
  await expect(page.getByAltText("Custom JUVAl logo")).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem("juval.appearance.background"))).toBe(backgrounds[0].data)
  const theme = page.getByRole("combobox", { name: "Theme" })
  await expect(theme).toHaveCount(1)

  async function readable(accent: string) {
    await expect(page.getByLabel("Accent hex")).toHaveValue(accent)
    await page.getByRole("button", { name: "Reset appearance defaults" }).focus()
    await page.keyboard.press("Tab")
    await page.keyboard.press("Shift+Tab")
    const result = await page.evaluate((chosen) => {
      // Independent WCAG calculation against actual computed CSS, not the
      // production color helper or screenshots as an oracle.
      function rgba(color: string) {
        const channels = color.match(/[\d.]+/g)!.map(Number)
        return [...channels.slice(0, 3), channels[3] ?? 1]
      }
      function contrast(first: string, second: string) {
        function luminance(color: string) {
          const rgb = rgba(color).slice(0, 3).map((v) => v / 255).map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
          return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
        }
        const a = luminance(first), b = luminance(second)
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
      }
      const app = document.querySelector(".app")!
      const main = app.querySelector("main")!
      const live = main.querySelector("header > span")!
      const reset = [...main.querySelectorAll("button")].find((b) => b.textContent === "Reset appearance defaults")!
      const mainBackground = getComputedStyle(main).backgroundColor
      const ratios = [
        { label: "page title", ratio: contrast(getComputedStyle(main.querySelector("h1")!).color, mainBackground) },
        { label: "LIVE", ratio: contrast(getComputedStyle(live).color, getComputedStyle(live).backgroundColor) },
        ...[...app.querySelectorAll("aside button")].map((button) => ({
          label: `navigation ${button.textContent}`,
          ratio: contrast(getComputedStyle(button).color, button.getAttribute("aria-current") === "page" ? getComputedStyle(button).backgroundColor : getComputedStyle(app.querySelector("aside")!).backgroundColor),
        })),
        ...[...main.querySelectorAll("button")].filter((b) => !b.disabled).map((button) => ({
          label: button.textContent,
          ratio: contrast(getComputedStyle(button).color, getComputedStyle(button).backgroundColor),
        })),
      ]
      reset.focus()
      return {
        ratios,
        opaque: rgba(mainBackground)[3] === 1 && getComputedStyle(main).backgroundImage === "none",
        imageVisible: getComputedStyle(app).backgroundImage.includes("data:image/png")
          && getComputedStyle(main.querySelector(".appearance-preview")!).backgroundImage.includes("data:image/png")
          && app.getBoundingClientRect().right - main.getBoundingClientRect().right >= 8,
        chosenFill: getComputedStyle(reset).backgroundColor === `rgb(${[1, 3, 5].map((at) => parseInt(chosen.slice(at, at + 2), 16)).join(", ")})`,
        focusContrast: contrast(getComputedStyle(reset).outlineColor, mainBackground),
        focusVisible: reset.matches(":focus-visible"),
        overflow: document.documentElement.scrollWidth - innerWidth,
      }
    }, accent)
    expect(result.opaque).toBe(true)
    expect(result.imageVisible).toBe(true)
    expect(result.chosenFill).toBe(true) // the selected accent was not replaced
    expect(result.overflow).toBeLessThanOrEqual(0)
    expect(result.focusContrast).toBeGreaterThanOrEqual(3)
    expect(result.focusVisible).toBe(true)
    for (const { label, ratio } of result.ratios) expect(ratio, `${label}: text contrast`).toBeGreaterThanOrEqual(4.5)
  }

  for (const dark of [false, true]) {
    await theme.selectOption(String(dark))
    await expect(page.getByRole("switch")).toHaveAttribute("aria-checked", String(dark))
    const mode = dark ? "dark" : "light"
    await page.getByLabel("Accent hex").fill("#6d5dfc")
    for (const image of backgrounds) {
      await background(image)
      await readable("#6d5dfc")
      await page.screenshot({ path: info.outputPath(`appearance-normal-${image.name}-${mode}.png`), fullPage: true })
    }
    for (const accent of ["#ffffff", "#000000"]) {
      await page.getByLabel("Accent hex").fill(accent)
      await readable(accent)
      await page.screenshot({ path: info.outputPath(`appearance-${accent === "#ffffff" ? "white" : "black"}-accent-${mode}.png`), fullPage: true })
    }
    await page.getByLabel("Accent hex").fill("#6d5dfc")
    await page.setViewportSize({ width: 390, height: 844 })
    await readable("#6d5dfc")
    await page.screenshot({ path: info.outputPath(`appearance-normal-checker-${mode}-mobile.png`), fullPage: true })
    await page.setViewportSize({ width: 1440, height: 900 })
  }
  await page.getByRole("button", { name: "Reset appearance defaults" }).click()
  await expect(page.getByAltText("Logo preview")).toHaveCount(0)
  await expect(page.locator(".app")).not.toHaveClass(/has-custom-background/)
  await expect(theme).toHaveValue("true")
  await expect(page.getByLabel("Accent hex")).toHaveValue("")
  expect(await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("juval.appearance.")))).toEqual([])
  expect(writes).toEqual([])
})
