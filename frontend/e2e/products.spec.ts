import { expect, test } from "@playwright/test"

for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`products renders at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/products")

    await expect(page.getByRole("heading", { name: "Products", level: 2 })).toBeVisible()
    await expect(page.getByText("DEMO MODE")).toBeVisible()
    await expect(page.getByRole("table")).toBeVisible()
    await expect(page.getByText("NOT FOUND")).toBeVisible()
    await expect(page.getByRole("link", { name: /upload catalog/i })).toBeVisible()
  })
}
