import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { UploadPage } from "./UploadPage"

const file = (name: string) => new File(["a,b\n1,2"], name, { type: "text/csv" })

const column = (position: number, header: string, status: string, extra: Record<string, unknown> = {}) => ({
  position, header, normalized: header.toLowerCase(), status, canonical: null, alias_of: null, target: null, required: false, group: null, ...extra,
})

function previewBody(overrides: Record<string, unknown> = {}) {
  return {
    input_filename: "supplier.csv", input_hash: "f".repeat(64), fatal: false,
    rows_scanned: 2, rows_skipped_blank: 1, records_importable: 2,
    columns: [
      column(1, "SKU", "MAPPED", { canonical: "supplier_sku", alias_of: "supplier_sku", target: "product.identification.supplier_sku", group: "core" }),
      column(2, "ASIN", "MAPPED", { canonical: "asin", target: "product.identification.asin", required: true, group: "core" }),
      column(3, "Brand", "MAPPED", { canonical: "brand", target: "product.info.brand", group: "core" }),
      column(4, "brand", "DUPLICATE", { canonical: "brand" }),
      column(5, "Mystery Column", "UNKNOWN"),
      column(6, "", "BLANK"),
      column(7, "fin_currency", "MAPPED", { canonical: "fin_currency", target: "financial_scenario.currency", group: "native_financial_evidence" }),
    ],
    missing_required_columns: [],
    issue_counts: [{ level: "RECORD_ERROR", code: "INVALID_ASIN_FORMAT", count: 1 }, { level: "WARNING", code: "UNKNOWN_COLUMN", count: 1 }],
    issues: [
      { level: "WARNING", code: "UNKNOWN_COLUMN", message: "Column 'mystery_column' is not recognized and will be ignored.", field: "mystery_column", record_ref: null },
      { level: "RECORD_ERROR", code: "INVALID_ASIN_FORMAT", message: "asin 'X' is not a valid 10-character ASIN.", field: "asin", record_ref: "row_3:S-2" },
    ],
    issues_total: 2, issues_truncated: false,
    ...overrides,
  }
}

function stub(response: { ok: boolean; status: number; body: unknown }) {
  const mock = vi.fn(() => Promise.resolve({ ok: response.ok, status: response.status, json: async () => response.body }))
  vi.stubGlobal("fetch", mock)
  return mock
}

async function queueAndPreview(name = "supplier.csv") {
  const user = userEvent.setup()
  render(<UploadPage go={vi.fn()} />)
  await user.upload(screen.getByLabelText("Supplier files"), [file(name), file("other.csv")])
  await user.click(screen.getByRole("button", { name: `Preview ${name}` }))
  return user
}

describe("Import preview on the upload page", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("sends only the file to the validate-only endpoint and never submits a batch", async () => {
    const mock = stub({ ok: true, status: 200, body: previewBody() })
    await queueAndPreview()
    await screen.findByLabelText("Import preview of supplier.csv")

    expect(mock).toHaveBeenCalledTimes(1)
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit]
    expect(new URL(url).pathname).toBe("/api/v1/runs/preview")
    expect(init.method).toBe("POST")
    const form = init.body as FormData
    expect([...form.keys()]).toEqual(["file"])          // no thresholds, fees or persist: nothing to process
    expect((form.get("file") as File).name).toBe("supplier.csv")
  })

  it("is labelled PREVIEW and says no run was created", async () => {
    stub({ ok: true, status: 200, body: previewBody() })
    await queueAndPreview()
    const panel = await screen.findByLabelText("Import preview of supplier.csv")

    expect(within(panel).getByText("PREVIEW")).toBeInTheDocument()
    expect(within(panel).getByText(/nothing was processed or stored and no run was created/i)).toBeInTheDocument()
    expect(screen.queryByText(/batch result/i)).not.toBeInTheDocument()
  })

  it("shows recognized, unknown, duplicate and blank columns, rows and issues", async () => {
    stub({ ok: true, status: 200, body: previewBody() })
    await queueAndPreview()
    const panel = await screen.findByLabelText("Import preview of supplier.csv")

    expect(within(panel).getByRole("heading", { name: "Recognized columns (4)" })).toBeInTheDocument()
    expect(within(panel).getByText("supplier_sku (alias)")).toBeInTheDocument()
    expect(within(panel).getAllByRole("cell", { name: "Required" })).toHaveLength(1)
    expect(within(panel).getByText(/financial evidence, does not affect decisions/)).toBeInTheDocument()
    expect(within(panel).getByRole("heading", { name: "Unknown columns — ignored (1)" })).toBeInTheDocument()
    expect(within(panel).getByText("Mystery Column")).toBeInTheDocument()
    expect(within(panel).getByRole("heading", { name: "Duplicate columns — ignored (1)" })).toBeInTheDocument()
    expect(within(panel).getByText(/repeats/)).toHaveTextContent("Column 4: brand repeats brand; the first occurrence is used")
    expect(within(panel).getByText(/1 column has no header/)).toBeInTheDocument()

    const kpi = (label: string) => within(panel).getByText(label).closest("article")!
    expect(kpi("Rows read")).toHaveTextContent("2")
    expect(kpi("Importable records")).toHaveTextContent("2")
    expect(kpi("Blank rows skipped")).toHaveTextContent("1")
    expect(within(panel).getByRole("cell", { name: "INVALID_ASIN_FORMAT" })).toBeInTheDocument()
    expect(within(panel).getByText(/Issue details \(2\)/)).toBeInTheDocument()
  })

  it("explains a fatal verdict and lists the missing required columns", async () => {
    stub({ ok: true, status: 200, body: previewBody({
      fatal: true, rows_scanned: 0, records_importable: 0, rows_skipped_blank: 0,
      missing_required_columns: [{ canonical: "marketplace", target: "product.identification.marketplace" }, { canonical: "cost", target: "costs.cog" }],
      issue_counts: [{ level: "FATAL", code: "MISSING_REQUIRED_COLUMN", count: 2 }], issues: [], issues_total: 2,
    }) })
    await queueAndPreview()
    const panel = await screen.findByLabelText("Import preview of supplier.csv")

    expect(within(panel).getByRole("alert")).toHaveTextContent(/required columns are missing/i)
    expect(within(panel).getByText("marketplace")).toBeInTheDocument()
    expect(within(panel).getByText("cost")).toBeInTheDocument()
  })

  it("says when the issue list is truncated while the counts stay complete", async () => {
    stub({ ok: true, status: 200, body: previewBody({ issues_total: 250, issues_truncated: true }) })
    await queueAndPreview()
    const panel = await screen.findByLabelText("Import preview of supplier.csv")
    expect(within(panel).getByText(/first 2 of 250/)).toBeInTheDocument()
  })

  it("shows the server's rejection of an unreadable file", async () => {
    stub({ ok: false, status: 422, body: { detail: "uploaded file is not a valid CSV file: bad bytes" } })
    await queueAndPreview()
    expect(await screen.findByRole("alert")).toHaveTextContent("uploaded file is not a valid CSV file: bad bytes")
  })

  it("hides the preview when its file leaves the queue", async () => {
    stub({ ok: true, status: 200, body: previewBody() })
    const user = await queueAndPreview()
    await screen.findByLabelText("Import preview of supplier.csv")
    await user.click(screen.getByRole("button", { name: "Remove supplier.csv" }))
    await waitFor(() => expect(screen.queryByLabelText("Import preview of supplier.csv")).not.toBeInTheDocument())
    expect(screen.getByText("other.csv")).toBeInTheDocument()   // the rest of the queue is untouched
  })

  it("shows a loading state and leaves the file queue exactly as it was", async () => {
    let resolve!: (value: unknown) => void
    vi.stubGlobal("fetch", vi.fn(() => new Promise((done) => { resolve = done })))
    await queueAndPreview()

    expect(await screen.findByText(/validating columns and rows on the server/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Preview other.csv" })).toBeDisabled()   // one preview at a time
    resolve({ ok: true, status: 200, json: async () => previewBody() })
    await screen.findByLabelText("Import preview of supplier.csv")

    const queue = screen.getByLabelText("File queue")
    expect(within(queue).getAllByRole("listitem").map((li) => li.querySelector("b")?.textContent)).toEqual(["supplier.csv", "other.csv"])
  })
})

