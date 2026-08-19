import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RunsPage } from "./RunsPage"

const RUN_A = { execution_id: "run-a", started_at: "2026-08-17T12:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "a.xlsx", input_hash: "a", records_total: 5, records_processed: 5, records_successful: 5, records_with_errors: 0, warnings: 0 }
const RUN_B = { execution_id: "run-b", started_at: "2026-08-18T12:00:00Z", finished_at: null, status: "SUCCESS", input_filename: "b.xlsx", input_hash: "b", records_total: 50, records_processed: 50, records_successful: 50, records_with_errors: 0, warnings: 0 }

function renderPage() {
  return render(<MemoryRouter><RunsPage /></MemoryRouter>)
}

function rowExecutionIds() {
  const rows = screen.getAllByRole("row").slice(1) // drop header row
  return rows.map((row) => within(row).getAllByRole("cell")[0].textContent)
}

describe("RunsPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while the persisted-run request is in flight", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderPage()

    expect(screen.getByText(/loading run history/i)).toBeInTheDocument()
  })

  it("renders persisted API rows and never substitutes demo data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [RUN_A] }) }))
    renderPage()

    expect(await screen.findByText("run-a")).toBeInTheDocument()
    expect(screen.getByText("a.xlsx")).toBeInTheDocument()
    expect(screen.queryByText("DEMO MODE")).not.toBeInTheDocument()
  })

  it("explains when no persisted runs are available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    renderPage()

    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
  })

  it("shows an API error and retries without falling back to demo data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "unavailable" }) })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i)
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.queryByText("DEMO MODE")).not.toBeInTheDocument()

    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [RUN_A] }) })
    await user.click(screen.getByRole("button", { name: /retry/i }))

    expect(await screen.findByText("run-a")).toBeInTheDocument()
  })

  it("sorts by a numeric column ascending/descending on repeated header clicks", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [RUN_A, RUN_B] }) }))
    const user = userEvent.setup()
    renderPage()

    await screen.findByText("run-a")
    // Default sort is Started at, descending -- run-b (later) first.
    expect(rowExecutionIds()).toEqual(["run-b", "run-a"])

    await user.click(screen.getByRole("button", { name: /^total records/i }))
    expect(rowExecutionIds()).toEqual(["run-b", "run-a"]) // 50 desc before 5

    await user.click(screen.getByRole("button", { name: /^total records/i }))
    expect(rowExecutionIds()).toEqual(["run-a", "run-b"]) // toggled to ascending
  })
})
