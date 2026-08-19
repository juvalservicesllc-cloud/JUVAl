import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
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
    expect(screen.getByLabelText(/catalog workbook/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/target profit/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/target roi/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/maximum accepted risk severity/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^referral fee$/i)).toBeInTheDocument()
  })

  it("blocks submit when no file is selected", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    await user.click(screen.getByRole("button", { name: /^process catalog$/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole("alert")).toHaveTextContent(/choose the excel workbook/i)
  })

  it("blocks submit and shows an error when required parameters are empty -- never invents a commercial default", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText(/catalog workbook/i), makeFile())
    await user.click(screen.getByRole("button", { name: /^process catalog$/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole("alert")).toHaveTextContent(/does not invent commercial defaults/i)
  })

  it("submits the exact thresholds/fees shape the backend expects once all required fields are filled", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    const fileInput = screen.getByLabelText(/catalog workbook/i)
    await user.upload(fileInput, makeFile())

    await user.type(screen.getByLabelText(/target profit/i), "5")
    await user.type(screen.getByLabelText(/target roi/i), "0.3")
    await user.type(screen.getByLabelText(/minimum estimated monthly sales/i), "0")
    await user.selectOptions(screen.getByLabelText(/maximum accepted risk severity/i), "LOW")
    await user.type(screen.getByLabelText(/^referral fee$/i), "3")
    await user.type(screen.getByLabelText(/referral fee rate/i), "0.15")

    await user.click(screen.getByRole("button", { name: /^process catalog$/i }))

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
    expect(values.persist).toBe(false)
  })

  it("submits persist=true when the persistence checkbox is checked", async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={onSubmit} />)

    await user.upload(screen.getByLabelText(/catalog workbook/i), makeFile())
    await user.type(screen.getByLabelText(/target profit/i), "5")
    await user.type(screen.getByLabelText(/target roi/i), "0.3")
    await user.type(screen.getByLabelText(/minimum estimated monthly sales/i), "0")
    await user.selectOptions(screen.getByLabelText(/maximum accepted risk severity/i), "LOW")
    await user.type(screen.getByLabelText(/^referral fee$/i), "3")
    await user.type(screen.getByLabelText(/referral fee rate/i), "0.15")
    await user.click(screen.getByLabelText(/persist this run/i))

    await user.click(screen.getByRole("button", { name: /^process catalog$/i }))

    expect(onSubmit.mock.calls[0][0].persist).toBe(true)
  })

  it("shows selected-file feedback and rejects a CSV before submission", async () => {
    const user = userEvent.setup()
    render(<RunForm disabled={false} onSubmit={vi.fn()} />)

    await user.upload(screen.getByLabelText(/catalog workbook/i), makeFile())
    expect(screen.getByText("sample.xlsx")).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/catalog workbook/i), { target: { files: [new File(["csv"], "sample.csv", { type: "text/csv" })] } })
    expect(screen.getByRole("alert")).toHaveTextContent(/processes excel workbooks/i)
  })
})
