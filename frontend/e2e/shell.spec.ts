import { expect, test } from "@playwright/test"

// Dashboard is real API data now (GET /api/v1/runs + records, ADR-019 /
// Product Integration Slice 3) -- this stays a routing/responsive check,
// not a data-content check (that lives in DashboardPage.test.tsx with
// mocked fetch). It must not assert "DEMO MODE": with a fresh/unconfigured
// backend the page legitimately renders its own empty or error state.
for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`dashboard navigation renders at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/")

    await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible()
    await expect(page.getByText("DEMO MODE")).not.toBeVisible()
    await expect(page.getByText(/loading runs/i)).not.toBeVisible({ timeout: 10_000 })
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
