import { expect, test } from "@playwright/test"

for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`dashboard navigation renders at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/")

    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible()
    await expect(page.getByText("DEMO MODE")).toBeVisible()
    await page.getByRole("button", { name: "Bars" }).click()
    await expect(page.getByRole("button", { name: "Bars" })).toHaveAttribute("aria-pressed", "true")
    await page.getByRole("button", { name: "Line" }).click()
    await expect(page.getByRole("button", { name: "Line" })).toHaveAttribute("aria-pressed", "true")
    await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: /upload catalog/i })).toBeVisible()
    await page.getByRole("link", { name: /products/i }).click()
    await expect(page).toHaveURL(/\/products$/)
  })

  test(`upload remains clearly live at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/upload")

    if (width > 600) await expect(page.getByText("Live processing")).toBeVisible()
    await expect(page.getByText("LIVE API FOR XLSX")).toBeVisible()
    await expect(page.getByLabel(/catalog \(\.xlsx; \.csv pending\)/i)).toBeVisible()
    await expect(page.getByText("DEMO MODE")).not.toBeVisible()
  })
}
