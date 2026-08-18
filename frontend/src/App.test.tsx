import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import App from "./App"

function makeFile() {
  return new File(["dummy"], "sample.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  })
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(await screen.findByLabelText(/catalog \(\.xlsx; \.csv pending\)/i), makeFile())
  await user.type(screen.getByLabelText(/target profit/i), "5")
  await user.type(screen.getByLabelText(/target roi/i), "0.3")
  await user.type(screen.getByLabelText(/ventas mensuales/i), "0")
  await user.selectOptions(screen.getByLabelText(/severidad de riesgo máxima/i), "LOW")
  await user.type(screen.getByLabelText(/referral fee \*/i), "3")
  await user.type(screen.getByLabelText(/referral fee rate/i), "0.15")
  await user.click(screen.getByRole("button", { name: /procesar/i }))
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("navigates the shell and keeps Products run-scoped when no persisted catalog exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    const user = userEvent.setup()
    window.history.pushState({}, "", "/")
    render(<App />)

    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: /products/i }))

    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
  })

  it("dashboard renders real run analytics from the API, not demo KPIs", async () => {
    const run = {
      execution_id: "run-1", started_at: "2026-08-17T12:00:00Z", finished_at: "2026-08-17T12:05:00Z",
      status: "PARTIAL_SUCCESS", input_filename: "catalog.xlsx", input_hash: "abc",
      records_total: 2, records_processed: 2, records_successful: 1, records_with_errors: 1, warnings: 0,
    }
    const analytics = {
      execution_id: "run-1",
      records: { total_records: 2 },
      decisions: { BUY: 1, REVIEW: 1 },
      risks: { hazmat: { status: { PRESENT: 1, ABSENT: 1 }, severity: { HIGH: 1 } }, bulky: { status: { ABSENT: 2 }, severity: {} } },
      provenance: { asin: { VERIFIED: 1, NOT_FOUND: 1 }, weight: {}, selling_price: {}, profit: { VERIFIED: 1, NOT_FOUND: 1 }, roi: { VERIFIED: 1, NOT_FOUND: 1 }, margin: {} },
      data_quality: { records_with_issues: 1, total_issue_count: 1 },
      profitability: {
        profit: { count: 1, sum: "5", average: "5", minimum: "5", maximum: "5" },
        roi: { count: 1, sum: "0.4", average: "0.4", minimum: "0.4", maximum: "0.4" },
        margin: { count: 0, sum: null, average: null, minimum: null, maximum: null },
      },
    }
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => Promise.resolve({
        ok: true, status: 200,
        json: async () => (url.includes("/analytics") ? analytics : { items: [run] }),
      })),
    )
    window.history.pushState({}, "", "/")
    render(<App />)

    expect(await screen.findByText("catalog.xlsx")).toBeInTheDocument()
    expect((await screen.findAllByText(/40\.0%/)).length).toBeGreaterThan(0) // average ROI, from the analytics endpoint
    const totalRecordsCard = screen.getByText("Total records").closest("article")
    expect(totalRecordsCard).toHaveTextContent("2") // analytics.records.total_records
    expect(screen.getAllByText(/\$5\.00/).length).toBeGreaterThan(0) // average profit, from analytics.profitability
  })

  it("shows the results table and download link on a successful run -- never invents a value the backend didn't send", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          execution_id: "e1",
          status: "SUCCESS",
          input_filename: "sample.xlsx",
          input_hash: "abc",
          records_total: 1,
          records_processed: 1,
          records_successful: 1,
          records_with_errors: 0,
          warnings: 0,
          persisted: false,
          records: [
            {
              record_ref: "row_2:SUP-001",
              marketplace: "US",
              supplier_sku: "SUP-001",
              asin: { value: "B0TESTAAA1", status: "VERIFIED" },
              upc: { value: null, status: null },
              weight: { value: null, status: null },
              selling_price: { value: "19.99", status: "VERIFIED" },
              cog: "5",
              shipping_per_unit: "1",
              profit: { value: "8.99", status: "VERIFIED" },
              roi: { value: null, status: null },
              margin: { value: null, status: null },
              break_even_price: { value: null, status: null },
              max_cog_target_profit: { value: null, status: null },
              max_cog_target_roi: { value: null, status: null },
              hazmat_status: "ABSENT",
              hazmat_severity: "NONE",
              bulky_status: "ABSENT",
              bulky_severity: "NONE",
              decision: "BUY",
              decision_reasons: [],
              issue_count: 0,
              issues: [],
            },
          ],
        }),
      }),
    )

    window.history.pushState({}, "", "/upload")
    render(<App />)
    await fillAndSubmit(user)

    await waitFor(() => expect(screen.getByText("e1")).toBeInTheDocument())
    expect(screen.getByText(/B0TESTAAA1/)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /download results/i })).toHaveAttribute(
      "href",
      expect.stringContaining("/api/v1/runs/e1/download"),
    )
  })

  it("shows an error state, not a crash, when the API returns an error", async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: "invalid fees: referral_fee_rate must be within [0, 1)" }),
      }),
    )

    window.history.pushState({}, "", "/upload")
    render(<App />)
    await fillAndSubmit(user)

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument())
    expect(screen.getByRole("alert")).toHaveTextContent(/referral_fee_rate/)
  })
})
