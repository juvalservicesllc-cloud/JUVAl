import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { UploadPage } from "./UploadPage"

const file = (name: string) => new File(["a,b\n1,2"], name, { type: "text/csv" })

function batchResponse(overrides: Record<string, unknown> = {}) {
  return {
    batch_id: "batch-1", created_at: "2026-08-26T10:00:00Z", status: "SUCCESS",
    total_files: 1, succeeded_files: 1, failed_files: 0, persisted: true,
    records_total: 5, records_processed: 5, records_with_errors: 0, warning_count: 0,
    files: [{ ordinal: 0, filename: "a.csv", content_type: "text/csv", size_bytes: 10, status: "SUCCESS", execution_id: "run-1", warnings: [], errors: [], records_total: 5, records_processed: 5, records_with_errors: 0, warning_count: 0 }],
    ...overrides,
  }
}

function fillConfiguration() {
  fireEvent.change(screen.getByLabelText("Target profit"), { target: { value: "5" } })
  fireEvent.change(screen.getByLabelText("Target ROI"), { target: { value: "0.3" } })
  fireEvent.change(screen.getByLabelText("Minimum estimated monthly sales"), { target: { value: "0" } })
  fireEvent.change(screen.getByLabelText("Maximum accepted risk severity"), { target: { value: "MEDIUM" } })
  fireEvent.change(screen.getByLabelText("Referral fee"), { target: { value: "3" } })
  fireEvent.change(screen.getByLabelText("Referral fee rate"), { target: { value: "0.15" } })
}

const dropZone = () => document.querySelector(".drop-zone") as HTMLElement

describe("UploadPage on the real pipeline", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("queues files from the picker", async () => {
    render(<UploadPage go={vi.fn()} />)
    await userEvent.setup().upload(screen.getByLabelText("Supplier files"), [file("a.csv"), file("b.xlsx")])

    expect(screen.getByText("a.csv")).toBeInTheDocument()
    expect(screen.getByText("b.xlsx")).toBeInTheDocument()
    expect(screen.getByText("2 / 10 files")).toBeInTheDocument()
  })

  it("queues dropped files through the same validation path as the picker", () => {
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv"), file("nope.pdf")] } })

    expect(screen.getByText("a.csv")).toBeInTheDocument()
    expect(screen.queryByText("nope.pdf")).not.toBeInTheDocument()
    expect(screen.getByRole("alert")).toHaveTextContent(/nope\.pdf/)
  })

  it("shows a dragover state and clears it on drop", () => {
    render(<UploadPage go={vi.fn()} />)
    fireEvent.dragOver(dropZone())
    expect(dropZone()).toHaveClass("dragging")
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv")] } })
    expect(dropZone()).not.toHaveClass("dragging")
  })

  it("enforces the ten-file cap and names what was not queued", () => {
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: Array.from({ length: 12 }, (_, i) => file(`f${i}.csv`)) } })

    expect(screen.getByText("10 / 10 files")).toBeInTheDocument()
    expect(screen.getByRole("alert")).toHaveTextContent(/f10\.csv/)
    expect(screen.getByRole("alert")).toHaveTextContent(/f11\.csv/)
  })

  it("removes a single queued file", async () => {
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv"), file("b.csv")] } })

    await userEvent.setup().click(screen.getByRole("button", { name: "Remove a.csv" }))
    expect(screen.queryByText("a.csv")).not.toBeInTheDocument()
    expect(screen.getByText("b.csv")).toBeInTheDocument()
  })

  it("refuses to submit without a complete configuration, inventing no defaults", async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv")] } })

    await userEvent.setup().click(screen.getByRole("button", { name: /process catalog/i }))

    expect(screen.getByRole("alert")).toHaveTextContent(/does not invent commercial defaults/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("posts a real multipart batch with thresholds, fees and persist", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => batchResponse() }))
    vi.stubGlobal("fetch", fetchMock)
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv")] } })
    fillConfiguration()

    await userEvent.setup().click(screen.getByRole("button", { name: /process catalog/i }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(String(url)).toContain("/api/v1/batches")
    expect(init.method).toBe("POST")
    const body = init.body as FormData
    expect(body.getAll("files")).toHaveLength(1)
    expect(JSON.parse(String(body.get("thresholds"))).target_roi).toBe("0.3")
    expect(JSON.parse(String(body.get("fees"))).referral_fee_rate).toBe("0.15")
    expect(body.get("persist")).toBe("true")
  })

  it("shows an honest indeterminate state that names every submitted file", async () => {
    // Never resolves: this is the in-flight state.
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})))
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv"), file("b.csv")] } })
    fillConfiguration()

    await userEvent.setup().click(screen.getByRole("button", { name: /process 2 files/i }))

    expect(await screen.findByText(/intentionally indeterminate/i)).toBeInTheDocument()
    expect(screen.getAllByText("a.csv").length).toBeGreaterThan(0)
    expect(screen.getAllByText("b.csv").length).toBeGreaterThan(0)
    // No invented stage list or percentage.
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    expect(screen.queryByText(/normalize/i)).not.toBeInTheDocument()
  })

  it("reports a backend failure without claiming a completed batch", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: "a batch may contain at most 10 files" }) })))
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv")] } })
    fillConfiguration()

    await userEvent.setup().click(screen.getByRole("button", { name: /process catalog/i }))

    expect(await screen.findByRole("alert")).toHaveTextContent(/at most 10 files/i)
    expect(screen.getByText(/no successful backend result/i)).toBeInTheDocument()
  })

  it("surfaces a partial success and routes into the batch", async () => {
    const partial = batchResponse({ status: "PARTIAL_SUCCESS", total_files: 2, succeeded_files: 1, failed_files: 1 })
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => partial })))
    const go = vi.fn()
    render(<UploadPage go={go} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv")] } })
    fillConfiguration()
    const user = userEvent.setup()

    await user.click(screen.getByRole("button", { name: /process catalog/i }))
    expect(await screen.findByText("PARTIAL_SUCCESS")).toBeInTheDocument()
    expect(screen.getByText(/1 of 2 file/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /open batch/i }))
    expect(go).toHaveBeenCalledWith("/batch/batch-1")
  })

  it("warns when a batch was not persisted, so it will not reach Runs", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => batchResponse({ persisted: false }) })))
    render(<UploadPage go={vi.fn()} />)
    fireEvent.drop(dropZone(), { dataTransfer: { files: [file("a.csv")] } })
    fillConfiguration()

    await userEvent.setup().click(screen.getByRole("button", { name: /process catalog/i }))

    expect(await screen.findByText(/was not persisted/i)).toBeInTheDocument()
  })
})
