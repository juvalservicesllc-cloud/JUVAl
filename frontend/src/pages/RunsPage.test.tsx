import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { RunsPage } from "./RunsPage"

function renderPage() {
  return render(<MemoryRouter><RunsPage /></MemoryRouter>)
}

const RUN = {
  execution_id: "run-1",
  started_at: "2026-08-17T12:00:00Z",
  finished_at: "2026-08-17T12:05:00Z",
  status: "SUCCESS",
  input_filename: "catalog.xlsx",
  input_hash: "abc123",
  records_total: 5,
  records_processed: 4,
  records_successful: 3,
  records_with_errors: 1,
  warnings: 2,
}

describe("RunsPage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("shows a loading state while the request is in flight", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})))
    renderPage()
    expect(screen.getByText(/loading run history/i)).toBeInTheDocument()
  })

  it("renders real run rows from the API, not demo data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [RUN] }) }))
    renderPage()

    expect(await screen.findByText("run-1")).toBeInTheDocument()
    expect(screen.getByText("SUCCESS")).toBeInTheDocument()
    expect(screen.queryByText("DEMO MODE")).not.toBeInTheDocument()
  })

  it("shows an empty state when no runs are persisted", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [] }) }))
    renderPage()
    expect(await screen.findByText(/no persisted runs yet/i)).toBeInTheDocument()
  })

  it("shows an error state with retry, never falling back to demo data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: "unavailable" }) })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i)
    expect(screen.queryByRole("table")).not.toBeInTheDocument()

    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ items: [RUN] }) })
    await user.click(screen.getByRole("button", { name: /retry/i }))

    await waitFor(() => expect(screen.getByText("run-1")).toBeInTheDocument())
  })
})
