import { expect, test } from "@playwright/test"

for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`appearance mode switch renders and persists at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto("/appearance")
    await expect(page.getByRole("heading", { name: "Appearance", level: 2 })).toBeVisible()
    const switchControl = page.getByRole("switch", { name: /appearance mode/i })
    await expect(switchControl).toHaveAttribute("aria-checked", "true")
    await switchControl.click()
    await expect(switchControl).toHaveAttribute("aria-checked", "false")
    await page.reload()
    await expect(page.getByRole("switch", { name: /appearance mode/i })).toHaveAttribute("aria-checked", "false")
    await expect(page.getByLabel("Accent HEX")).toBeVisible()
    await expect(page.getByText("Logo and background")).toBeVisible()
  })
}
