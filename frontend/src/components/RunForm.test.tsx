import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { RunForm } from "./RunForm"

function makeFile() {
  return new File(["dummy"], "sample.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  })
}

describe("RunForm", () => {
  it("renders the file upload input and required parameter fields", () => {
    render(<RunForm disabled={false} onSubmit={vi.fn()} />)
    expect(screen.getByLabelText(/catalog \(\.xlsx or \.csv\)/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/target profit/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/target roi/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/severidad de riesgo máxima/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/referral fee \*/i)).toBeInTheDocument()
  })

  it("blocks submit when no file is selected", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    await user.click(screen.getByRole("button", { name: /procesar/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole("alert")).toHaveTextContent(/selecciona un archivo/i)
  })

  it("blocks submit and shows an error when required parameters are empty -- never invents a commercial default", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText(/catalog \(\.xlsx or \.csv\)/i), makeFile())
    await user.click(screen.getByRole("button", { name: /procesar/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole("alert")).toHaveTextContent(/no existe un valor comercial por defecto/i)
  })

  it("submits the exact thresholds/fees shape the backend expects once all required fields are filled", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    const fileInput = screen.getByLabelText(/catalog \(\.xlsx or \.csv\)/i)
    await user.upload(fileInput, makeFile())

    await user.type(screen.getByLabelText(/target profit/i), "5")
    await user.type(screen.getByLabelText(/target roi/i), "0.3")
    await user.type(screen.getByLabelText(/ventas mensuales/i), "0")
    await user.selectOptions(screen.getByLabelText(/severidad de riesgo máxima/i), "LOW")
    await user.type(screen.getByLabelText(/referral fee \*/i), "3")
    await user.type(screen.getByLabelText(/referral fee rate/i), "0.15")

    await user.click(screen.getByRole("button", { name: /procesar/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const values = onSubmit.mock.calls[0][0]
    expect(values.thresholds).toEqual({
      target_profit: "5",
      target_roi: "0.3",
      minimum_estimated_monthly_sales: 0,
      maximum_risk_severity: "LOW",
      allow_restricted: false,
      allow_approval_required: false,
      allow_unknown_risk: false,
    })
    expect(values.fees).toEqual({
      referral_fee: "3",
      referral_fee_rate: "0.15",
      fulfillment_fee: "0",
      other_selling_fees: "0",
    })
  })
})
