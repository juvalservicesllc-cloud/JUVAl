import { expect, test } from "@playwright/test"

for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`appearance controls render and apply a preset at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto("/appearance")
    await expect(page.getByRole("heading", { name: "Appearance", level: 2 })).toBeVisible()
    await page.getByRole("button", { name: "Light" }).click()
    await expect(page.getByText("Preset active")).toBeVisible()
    await expect(page.getByLabel("Accent HEX")).toBeVisible()
    await expect(page.getByText("Logo and background")).toBeVisible()
  })
}
