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
  await user.upload(screen.getByLabelText(/catalog \(\.xlsx; \.csv pending\)/i), makeFile())
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

  it("navigates the demo shell and keeps provenance states distinct", async () => {
    const user = userEvent.setup()
    window.history.pushState({}, "", "/")
    render(<App />)

    expect(screen.getByText("Total Products")).toBeInTheDocument()
    await user.click(screen.getByRole("link", { name: /products/i }))

    expect(screen.getByText("Marine Sealant 3 oz")).toBeInTheDocument()
    expect(screen.getAllByText("VERIFIED").length).toBeGreaterThan(0)
    expect(screen.getAllByText("INFERRED").length).toBeGreaterThan(0)
    expect(screen.getByText("NOT FOUND")).toBeInTheDocument()
  })

  it("switches the dashboard chart between line and bars", async () => {
    const user = userEvent.setup()
    window.history.pushState({}, "", "/")
    render(<App />)

    expect(screen.getByRole("button", { name: "Line" })).toHaveAttribute("aria-pressed", "true")
    await user.click(screen.getByRole("button", { name: "Bars" }))
    expect(screen.getByRole("button", { name: "Bars" })).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByTestId("analytics-chart")).toHaveAttribute("aria-label", "bar chart of dashboard metrics")
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
