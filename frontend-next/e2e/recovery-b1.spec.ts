import { join } from "node:path"
import { API, DIR, configureUpload, expect, test } from "./support"

for (const count of [2, 10]) {
  test(`B1: ${count} synthetic XLSX files, individual previews, statuses and analytics`, async ({ page }) => {
    const files = Array.from({ length: count }, (_, i) => `batch-${String(i + 1).padStart(2, "0")}.xlsx`)
    await page.goto("/import")
    await page.getByLabel("Supplier files").setInputFiles(files.map((file) => join(DIR, "files", file)))
    await expect(page.getByText(`${count} / 10 files`, { exact: true })).toBeVisible()
    for (const file of files) {
      const queued = page.getByRole("list", { name: "File queue" }).getByRole("listitem").filter({ hasText: file })
      await expect(queued).toContainText("queued")
      await queued.getByRole("button", { name: `Preview ${file}`, exact: true }).click()
      const preview = page.getByRole("region", { name: `Import preview of ${file}`, exact: true })
      await expect(preview).toContainText("The importer can read this file.")
      await preview.getByRole("button", { name: "Close preview" }).click()
    }
    await configureUpload(page)
    let release!: () => void
    const gate = new Promise<void>((resolve) => { release = resolve })
    await page.route("**/api/v1/batches", async (route) => { await gate; await route.continue() })
    await page.getByRole("button", { name: `Process ${count} files`, exact: true }).click()
    try {
      const submitting = page.locator("section").filter({ has: page.getByRole("heading", { name: "JUVAl is validating and processing your files" }) })
      for (const file of files) await expect(submitting.getByRole("listitem").filter({ hasText: file })).toContainText("submitted · awaiting result")
    } finally { release() }
    await expect(page.getByRole("heading", { name: /Batch result/ })).toBeVisible()
    await page.getByRole("button", { name: "Open batch" }).click()
    await expect(page.getByRole("heading", { name: "Batch summary" })).toBeVisible()
    const batchId = page.url().split("/batch/")[1]
    const response = await page.request.get(`${API}/api/v1/batches/${batchId}`)
    expect(response.status()).toBe(200)
    const batch = await response.json()
    expect([batch.total_files, batch.succeeded_files, batch.failed_files]).toEqual([count, count, 0])
    for (const file of files) {
      const included = page.getByRole("table", { name: "Included files" }).getByRole("row").filter({ hasText: file })
      const stored = batch.files.find((f: { filename: string }) => f.filename === file)
      await expect(included.getByRole("cell").nth(2)).toHaveText(stored.status)
      await expect(included.getByRole("link", { name: "Open run" })).toHaveAttribute("href", `/runs/${stored.execution_id}`)
      const analyticsResponse = await page.request.get(`${API}/api/v1/runs/${stored.execution_id}/analytics`)
      expect(analyticsResponse.status()).toBe(200)
      const a = await analyticsResponse.json()
      const analytic = page.getByRole("table", { name: "Per-file analytics" }).getByRole("row").filter({ hasText: file })
      await expect(analytic.getByRole("cell").nth(1)).toHaveText(String(a.records.total_records))
      for (const [i, decision] of ["BUY", "REVIEW", "PASS"].entries()) await expect(analytic.getByRole("cell").nth(i + 2)).toHaveText(String(a.decisions[decision] ?? 0))
    }
  })
}

test("B1: selecting eleven names the rejected overflow and sends no upload or preview request", async ({ page }) => {
  await page.goto("/import")
  const requests: string[] = []
  page.on("request", (r) => { if (new URL(r.url()).pathname.startsWith("/api/")) requests.push(`${r.method()} ${r.url()}`) })
  await page.getByLabel("Supplier files").setInputFiles(Array.from({ length: 11 }, (_, i) => join(DIR, "files", `batch-${String(i + 1).padStart(2, "0")}.xlsx`)))
  await expect(page.getByRole("alert")).toHaveText("At most 10 files per batch, so these were not queued: batch-11.xlsx.")
  await expect(page.getByRole("list", { name: "File queue" }).getByRole("listitem")).toHaveCount(10)
  // Only the shell's session GET is allowed; uploads, previews and other API calls still fail.
  expect(requests.filter((request) => request !== `GET ${API}/api/v1/auth/session`)).toEqual([])
})
