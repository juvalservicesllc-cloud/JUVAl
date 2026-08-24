import { expect, test } from "@playwright/test"

// Runs is real API data now (GET /api/v1/runs) -- this stays a
// responsive/routing check, not a data-content check (that lives in
// RunsPage.test.tsx with a mocked fetch). It must not assert "DEMO
// MODE" or an unconditionally-populated table: with a fresh/unconfigured
// backend the page legitimately renders its empty or error state.
for (const [name, width] of [["desktop", 1280], ["tablet", 768], ["mobile", 390]] as const) {
  test(`runs renders at ${name} width`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/runs")

    await expect(page.getByRole("heading", { name: "Processing Runs", level: 2 })).toBeVisible()
    await expect(page.getByText("DEMO MODE")).not.toBeVisible()
    await expect(page.getByText(/loading run history/i)).not.toBeVisible({ timeout: 10_000 })
    await expect(page.getByRole("link", { name: "Upload" })).toBeVisible()
  })
}
