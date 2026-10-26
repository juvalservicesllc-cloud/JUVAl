/**
 * Opt-in live contract check: the real pages against a running JUVAl API.
 *
 * Skipped unless JUVAL_LIVE_API names a disposable local API (never a shared
 * or production one) and VITE_API_BASE_URL points at the same URL. It stores
 * one run from the repository's synthetic fixture, then drives the three
 * integrations through the real HTTP contract:
 *
 *   JUVAL_LIVE_API=http://127.0.0.1:8765 VITE_API_BASE_URL=http://127.0.0.1:8765 \
 *     npx vitest run src/live.contract.test.tsx
 */
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeAll, describe, expect, it, vi } from "vitest"
import { favoriteKey, loadFavorites } from "./favorites"
import { BatchPage } from "./pages/BatchPage"
import { CatalogPage } from "./pages/CatalogPage"
import { DashboardPage } from "./pages/DashboardPage"
import { FavoritesPage } from "./pages/FavoritesPage"
import { ProductDetailPage } from "./pages/ProductDetailPage"
import { RunsPage } from "./pages/RunsPage"
import { UploadPage } from "./pages/UploadPage"

// The app is typed for the browser (no @types/node); this opt-in harness only
// needs these two Node facilities, declared here instead of a new dependency.
declare const process: { env: Record<string, string | undefined>; cwd(): string }
const { readFileSync } = await import("node:" + "fs") as { readFileSync(path: string): Uint8Array<ArrayBuffer> }

const API = process.env.JUVAL_LIVE_API
// Run from frontend-next/ (npm/vitest's working directory).
const FIXTURE = `${process.cwd()}/../tests/fixtures/sample_sourcing_TEST_DATA.xlsx`
const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

/** Test-environment shim, not app code: under vitest's jsdom environment
 *  `fetch` is Node's while `FormData`/`File` are jsdom's, and Node's fetch
 *  sends a jsdom FormData as an empty body. A browser serializes its own
 *  FormData, so here, and only here, it is encoded as standard multipart. */
async function multipart(form: FormData): Promise<{ body: ArrayBuffer; type: string }> {
  const boundary = `----juval-live-${Math.random().toString(16).slice(2)}`
  const encoder = new TextEncoder()
  const parts: Uint8Array[] = []
  for (const [name, value] of form.entries()) {
    if (typeof value === "string") {
      parts.push(encoder.encode(`--${boundary}\r\nContent-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`))
    } else {
      const bytes = new Uint8Array(await new Promise<ArrayBuffer>((done, fail) => {
        const reader = new FileReader()
        reader.onload = () => done(reader.result as ArrayBuffer)
        reader.onerror = () => fail(reader.error)
        reader.readAsArrayBuffer(value)
      }))
      parts.push(encoder.encode(`--${boundary}\r\nContent-Disposition: form-data; name="${name}"; filename="${value.name}"\r\nContent-Type: ${value.type || "application/octet-stream"}\r\n\r\n`), bytes, encoder.encode("\r\n"))
    }
  }
  parts.push(encoder.encode(`--${boundary}--\r\n`))
  const body = new Uint8Array(parts.reduce((n, part) => n + part.length, 0))
  let offset = 0
  for (const part of parts) { body.set(part, offset); offset += part.length }
  return { body: body.buffer, type: `multipart/form-data; boundary=${boundary}` }
}

const nodeFetch = globalThis.fetch
globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  if (!(init?.body instanceof FormData)) return nodeFetch(input, init)
  const { body, type } = await multipart(init.body)
  const headers = new Headers(init.headers)
  headers.set("content-type", type)
  return nodeFetch(input, { ...init, body, headers })
}) as typeof fetch

async function json(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, init)
  expect(response.ok, `${path} -> ${response.status}`).toBe(true)
  return response.json()
}

describe.skipIf(!API)("live API contract", () => {
  let runId = ""
  const fixture = () => new File([readFileSync(FIXTURE)], "sample.xlsx", { type: XLSX })

  beforeAll(async () => {
    expect(import.meta.env.VITE_API_BASE_URL).toBe(API)
    const form = new FormData()
    form.append("file", fixture())
    form.append("thresholds", JSON.stringify({ target_profit: "5", target_roi: "0.3", minimum_estimated_monthly_sales: 0, maximum_risk_severity: "LOW" }))
    form.append("fees", JSON.stringify({ referral_fee: "3", referral_fee_rate: "0.15", fulfillment_fee: "2" }))
    form.append("persist", "true")
    runId = (await json("/api/v1/runs", { method: "POST", body: form })).execution_id
  })

  it("Runs shows the stored decision counts the API returns for that run", async () => {
    const listed = (await json("/api/v1/runs")).items.find((r: { execution_id: string }) => r.execution_id === runId)
    expect(listed.decisions).not.toBeNull()
    render(<RunsPage go={vi.fn()} />)
    const article = (await screen.findAllByText(runId))[0].closest("article")!
    const counts = within(article as HTMLElement).getByLabelText("Decision counts")
    for (const decision of ["BUY", "REVIEW", "PASS"]) expect(counts).toHaveTextContent(`${decision} ${listed.decisions[decision] ?? 0}`)
  })

  it("Catalog filters records and export by an exact brand from the run's analytics", async () => {
    const { brands } = await json(`/api/v1/runs/${runId}/analytics`)
    const brand = brands.items[0]
    const user = userEvent.setup()
    const open = vi.spyOn(window, "open").mockImplementation(() => null)
    render(<CatalogPage initialRunId={runId} />)
    await screen.findByRole("option", { name: `${brand.label} (${brand.count})` })

    await user.selectOptions(screen.getByLabelText("Brand"), brand.label)
    await waitFor(() => expect(screen.getByText(`${brand.count} result${brand.count === 1 ? "" : "s"}`)).toBeInTheDocument())

    await user.click(screen.getByRole("button", { name: /^Export/ }))
    const exportUrl = String(open.mock.calls[0][0])
    expect(new URL(exportUrl).searchParams.get("brand")).toBe(brand.label)
    const exported = await fetch(exportUrl)
    expect(exported.status).toBe(200)
    expect(exported.headers.get("content-type")).toContain("spreadsheetml")
    open.mockRestore()
  })

  it("Preview shows the importer's verdict and creates no run", async () => {
    const before = (await json("/api/v1/runs")).items.length
    const user = userEvent.setup()
    render(<UploadPage go={vi.fn()} />)
    await user.upload(screen.getByLabelText("Supplier files"), [fixture()])
    await user.click(screen.getByRole("button", { name: "Preview sample.xlsx" }))

    const panel = await screen.findByLabelText("Import preview of sample.xlsx", {}, { timeout: 5000 })
    expect(within(panel).getByText("The importer can read this file.")).toBeInTheDocument()
    expect(within(panel).getByRole("heading", { name: /^Recognized columns/ })).toBeInTheDocument()
    expect((await json("/api/v1/runs")).items.length).toBe(before)
  })

  it("Dashboard shows the run's real analytics", async () => {
    const analytics = await json(`/api/v1/runs/${runId}/analytics`)
    render(<DashboardPage initialRunId={runId} go={vi.fn()} />)
    const figures = await screen.findByLabelText("Key figures", {}, { timeout: 5000 })
    expect(within(figures).getByText("Records").closest("article")).toHaveTextContent(String(analytics.records.total_records))
    expect(within(figures).getByText("Sum of verified unit profit").closest("article")).toHaveTextContent(`${analytics.profitability.profit.count} of ${analytics.records.total_records} records`)
  })

  it("Product Detail renders a real snapshot with its source file from stored provenance", async () => {
    const { records } = await json(`/api/v1/runs/${runId}/records?limit=1&confidence=INCLUDE_INFERRED`)
    const ref = records[0].record_ref
    render(<ProductDetailPage executionId={runId} recordRef={ref} go={vi.fn()} />)
    expect(await screen.findByLabelText("Source", {}, { timeout: 5000 })).toHaveTextContent("sample.xlsx")
    expect(await screen.findByText(/no financial document was stored/i)).toBeInTheDocument()
  })

  it("Batch Detail lists each child run's real analytics", async () => {
    const form = new FormData()
    form.append("files", fixture())
    form.append("thresholds", JSON.stringify({ target_profit: "5", target_roi: "0.3", minimum_estimated_monthly_sales: 0, maximum_risk_severity: "LOW" }))
    form.append("fees", JSON.stringify({ referral_fee: "3", referral_fee_rate: "0.15", fulfillment_fee: "2" }))
    form.append("persist", "true")
    const created = await json("/api/v1/batches", { method: "POST", body: form })
    const child = created.files[0].execution_id
    const analytics = await json(`/api/v1/runs/${child}/analytics`)
    render(<BatchPage batchId={created.batch_id} go={vi.fn()} />)
    const table = await screen.findByRole("table", { name: "Per-file analytics" }, { timeout: 5000 })
    await waitFor(() => expect(within(table).getByText("sample.xlsx").closest("tr")!.querySelectorAll("td")[1]).toHaveTextContent(String(analytics.records.total_records)))
  })

  it("Favorites resolves a real starred record of the run and removes it", async () => {
    const { records } = await json(`/api/v1/runs/${runId}/records?limit=1&confidence=INCLUDE_INFERRED`)
    const title = String(records[0].title.value)
    localStorage.setItem("juval.catalog.favorites.v1", JSON.stringify([favoriteKey(runId, records[0].record_ref)]))
    const user = userEvent.setup()
    render(<FavoritesPage initialRunId={runId} go={vi.fn()} />)
    expect(await screen.findByRole("link", { name: title }, { timeout: 5000 })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: `Remove ${title} from favorites` }))
    expect(loadFavorites()).toEqual([])
    localStorage.clear()
  })

  it("Pending demand verification: Catalog filter and Dashboard count match the real API", async () => {
    const pending = await json(`/api/v1/runs/${runId}/records?review_classification=PENDING_DEMAND_VERIFICATION&confidence=INCLUDE_INFERRED&limit=50`)
    expect(pending.records.length).toBeGreaterThan(0)
    expect(pending.records.every((r: { decision: string; review_classification: string }) => r.decision === "REVIEW" && r.review_classification === "PENDING_DEMAND_VERIFICATION")).toBe(true)
    const { review_classification } = await json(`/api/v1/runs/${runId}/analytics`)
    expect(review_classification.pending_demand_verification).toBe(pending.pagination.total)

    sessionStorage.clear()
    render(<CatalogPage initialRunId={runId} initialPendingDemand />)
    await waitFor(() => expect(screen.getByText(`${pending.pagination.total} result${pending.pagination.total === 1 ? "" : "s"}`)).toBeInTheDocument(), { timeout: 5000 })
    expect(screen.getAllByText("demand not verified")).toHaveLength(pending.records.length)
    sessionStorage.clear()
  })

  it("Declared demand: one million declared units are stored as evidence and the decision stays REVIEW", async () => {
    const csv = "marketplace,asin,cost,selling_price,hazmat,bulky,estimated_monthly_sales,demand_window_start,demand_window_end,demand_observed_at,demand_population,demand_method\n"
      + "US,B000000001,3,30,false,false,1000000,2026-09-01T00:00:00-04:00,2026-10-01T00:00:00-04:00,2026-10-01T00:00:00-04:00,synthetic population,synthetic live test\n"
    const form = new FormData()
    form.append("file", new File([csv], "demand.csv", { type: "text/csv" }))
    form.append("thresholds", JSON.stringify({ target_profit: "0", target_roi: "0", minimum_estimated_monthly_sales: 0, maximum_risk_severity: "CRITICAL", allow_restricted: true, allow_approval_required: true, allow_unknown_risk: true }))
    form.append("fees", JSON.stringify({ referral_fee: "1", referral_fee_rate: "0.15" }))
    form.append("persist", "true")
    const demandRun = (await json("/api/v1/runs", { method: "POST", body: form })).execution_id
    const [stored] = (await json(`/api/v1/runs/${demandRun}/records?confidence=INCLUDE_INFERRED`)).records
    expect(stored.decision).toBe("REVIEW")
    expect(stored.decision_reason_codes).toEqual(["DEMAND_UNKNOWN"])
    expect(stored.demand_evidence.observations[0].value).toMatchObject({ value: 1000000, status: "INFERRED", unit: "units" })

    render(<ProductDetailPage executionId={demandRun} recordRef={stored.record_ref} go={vi.fn()} />)
    const panel = await screen.findByLabelText("Declared demand", {}, { timeout: 5000 })
    expect(panel).toHaveTextContent("1,000,000 units")
    expect(panel).toHaveTextContent("Not used for this decision")
    expect(within(screen.getByLabelText("Decision")).getByText("▲ REVIEW")).toBeInTheDocument()
  })
})

