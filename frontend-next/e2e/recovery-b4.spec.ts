import { readFileSync } from "node:fs"
import { join } from "node:path"
import { API, DIR, expect, fixtures, test, upload, workbookResponseRows } from "./support"

test("B4: consecutive and concurrent browser-generated exports keep independent filters and rows", async ({ page }, info) => {
  const run = await upload(page, "no-demand.xlsx")
  await page.goto(`/catalog?run=${run}`)
  await expect(page.getByText("3 results", { exact: true })).toBeVisible()
  const urls: string[] = []
  for (const decision of ["REVIEW", "PASS"]) {
    await page.getByLabel("Decision", { exact: true }).selectOption(decision)
    await expect(page.getByText(decision === "REVIEW" ? "2 results" : "1 result", { exact: true })).toBeVisible()
    const requested = page.context().waitForEvent("request", (r) => new URL(r.url()).pathname.endsWith("/records/export"))
    await page.getByRole("button", { name: /^Export/ }).click()
    const url = (await requested).url()
    expect(new URL(url).searchParams.get("decision")).toBe(decision)
    urls.push(url)
  }
  async function verify(url: string, response: Awaited<ReturnType<typeof page.request.get>>, name: string) {
    const rows = await workbookResponseRows(response, name)
    const metadata = Object.fromEntries(JSON.parse(fixtures("dump", join(DIR, name), "query_metadata")))
    const requested = new URL(url)
    const filters = JSON.parse(metadata.filters)
    expect(filters.decision).toBe(requested.searchParams.get("decision"))
    requested.pathname = requested.pathname.replace(/\/export$/, "")
    requested.searchParams.set("limit", "100")
    requested.searchParams.set("offset", "0")
    const api = await page.request.get(`${API}${requested.pathname}${requested.search}`)
    expect(api.status()).toBe(200)
    const body = await api.json()
    expect(rows.map((r) => r.record_ref)).toEqual(body.records.map((r: { record_ref: string }) => r.record_ref))
    expect(rows.length).toBeGreaterThan(0)
    for (const record of rows) expect(record.decision).toBe(filters.decision)
  }
  // Consecutive requests, then two started together to the actual button URLs.
  for (const [i, url] of urls.entries()) await verify(url, await page.request.get(url), `b4-consecutive-${i}.xlsx`)
  const concurrent = await Promise.all(urls.map((url) => page.request.get(url)))
  for (const [i, response] of concurrent.entries()) await verify(urls[i], response, `b4-concurrent-${i}.xlsx`)

  // Run with DEBUG=pw:webserver and redirect stdout/stderr to this path. The
  // log assertion is evidence only when capture was supplied by the operator.
  const log = process.env.JUVAL_E2E_SERVER_LOG
  if (log) expect(readFileSync(log, "utf8")).not.toContain("LocalProtocolError")
  else info.annotations.push({ type: "unverified", description: "Server log capture not supplied; LocalProtocolError count not verified." })
})
