import { MemoryRouter } from "react-router-dom"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { submitRun } from "../api"
import type { RecordOut } from "../types"
import { UploadPage } from "./UploadPage"

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  submitRun: vi.fn(),
}))

const RECORD: RecordOut = {
  record_ref: "row_1:SUP-001", marketplace: "US", supplier_sku: "SUP-001",
  asin: { value: "B0TESTAAA1", status: "VERIFIED" }, upc: { value: null, status: "NOT_FOUND" }, weight: { value: "1", status: "VERIFIED" }, selling_price: { value: "19.99", status: "VERIFIED" },
  cog: "5", shipping_per_unit: "1", profit: { value: "8", status: "VERIFIED" }, roi: { value: "1", status: "VERIFIED" }, margin: { value: "0.4", status: "VERIFIED" }, break_even_price: { value: "9", status: "VERIFIED" }, max_cog_target_profit: { value: "8", status: "VERIFIED" }, max_cog_target_roi: { value: "9", status: "VERIFIED" },
  hazmat_status: "ABSENT", hazmat_severity: "NONE", bulky_status: "ABSENT", bulky_severity: "NONE", decision: "REVIEW", decision_reasons: [], issue_count: 0, issues: [],
}

function renderPage() {
  return render(<MemoryRouter><UploadPage /></MemoryRouter>)
}

async function submitValidForm() {
  const user = userEvent.setup()
  await user.upload(screen.getByLabelText(/catalog workbook/i), new File(["xlsx"], "catalog.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }))
  await user.type(screen.getByLabelText(/target profit/i), "5")
  await user.type(screen.getByLabelText(/target roi/i), "0.3")
  await user.type(screen.getByLabelText(/minimum estimated monthly sales/i), "0")
  await user.selectOptions(screen.getByLabelText(/maximum accepted risk severity/i), "LOW")
  await user.type(screen.getByLabelText(/^referral fee$/i), "3")
  await user.type(screen.getByLabelText(/referral fee rate/i), "0.15")
  await user.click(screen.getByRole("button", { name: /^process catalog$/i }))
  return user
}

describe("UploadPage", () => {
  afterEach(() => vi.clearAllMocks())

  it("shows an honest indeterminate processing state with the submitted filename", async () => {
    let resolveRun!: (value: unknown) => void
    vi.mocked(submitRun).mockReturnValue(new Promise((resolve) => { resolveRun = resolve }) as never)
    renderPage()

    await submitValidForm()
    expect(screen.getByText(/validating and processing your catalog/i)).toBeInTheDocument()
    expect(screen.getByText(/API does not expose granular stage progress/i)).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    resolveRun({})
  })

  it("treats partial success as review-needed and links to persisted Run Detail", async () => {
    vi.mocked(submitRun).mockResolvedValue({ execution_id: "run-1", status: "PARTIAL_SUCCESS", input_filename: "catalog.xlsx", input_hash: "hash", records_total: 2, records_processed: 2, records_successful: 1, records_with_errors: 1, warnings: 1, persisted: true, records: [RECORD] })
    renderPage()

    await submitValidForm()
    expect(await screen.findByText(/completed with review needed/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /review run/i }).getAttribute("href")).toBe("/runs/run-1")
  })

  it("does not offer review for a non-persisted run and explains the limitation", async () => {
    vi.mocked(submitRun).mockResolvedValue({ execution_id: "run-2", status: "SUCCESS", input_filename: "catalog.xlsx", input_hash: "hash", records_total: 1, records_processed: 1, records_successful: 1, records_with_errors: 0, warnings: 0, persisted: false, records: [RECORD] })
    renderPage()

    await submitValidForm()
    expect(await screen.findByText(/was not persisted/i)).toBeInTheDocument()
    expect(screen.queryByRole("link", { name: /review run/i })).not.toBeInTheDocument()
  })

  it("keeps an API failure distinct from a completed result", async () => {
    vi.mocked(submitRun).mockRejectedValue(new Error("network unavailable"))
    renderPage()

    await submitValidForm()
    expect(await screen.findByRole("alert")).toHaveTextContent(/network unavailable/i)
    expect(screen.queryByText(/^completed$/i)).not.toBeInTheDocument()
  })
})
